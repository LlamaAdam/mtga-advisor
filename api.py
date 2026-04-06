"""
17Lands API client.

Fetches card ratings and set metadata from 17lands.com.
Matches the API usage in bstaple1/MTGA_Draft_17Lands.

Endpoints used:
  - https://www.17lands.com/data/filters          (available sets)
  - https://www.17lands.com/card_ratings/data      (card win rates)
  - https://www.17lands.com/color_ratings/data     (color pair win rates)
"""

import json
import math
import os
import time
from datetime import date, timedelta
from typing import Any

import requests

import config

# 17Lands JSON field -> our internal key
_FIELD_MAP = {
    "ever_drawn_win_rate":      "GIHWR",
    "opening_hand_win_rate":    "OHWR",
    "win_rate":                 "GPWR",
    "avg_seen":                 "ALSA",
    "drawn_improvement_win_rate": "IWD",
    "avg_pick":                 "ATA",
    "game_count":               "NGP",
    "opening_hand_game_count":  "NGOH",
    "ever_drawn_game_count":    "GIH",
    "never_drawn_win_rate":     "GNSWR",
    "never_drawn_game_count":   "NGND",
    "drawn_win_rate":           "GDWR",
    "drawn_game_count":         "NGD",
}

# Color filters to fetch (mirrors bstaple1's approach)
_COLOR_FILTERS = [
    "",           # All Decks (no colors param)
    "W", "U", "B", "R", "G",
    "WU", "WB", "WR", "WG",
    "UB", "UR", "UG",
    "BR", "BG",
    "RG",
]

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) MTGA-Draft-Helper/1.0"
}


# ---------------------------------------------------------------------------
# Set list
# ---------------------------------------------------------------------------

def fetch_available_sets() -> list[dict]:
    """
    Fetch the list of sets available on 17Lands.
    Returns list of dicts with 'label' and 'value' keys (set code).
    """
    resp = requests.get(
        "https://www.17lands.com/data/filters",
        headers=_HEADERS,
        timeout=10,
    )
    resp.raise_for_status()
    data = resp.json()
    # The filters endpoint returns expansions under data["expansions"]
    expansions = data.get("expansions", [])
    return expansions


# ---------------------------------------------------------------------------
# Card ratings
# ---------------------------------------------------------------------------

def fetch_card_ratings(
    set_code: str,
    draft_format: str = "PremierDraft",
    start_date: str = config.RATINGS_START_DATE,
    end_date: str | None = None,
    color_filter: str = "",
) -> list[dict]:
    """
    Fetch raw card rating data from 17Lands for one color filter.

    Args:
        set_code:     e.g. "BLB", "DSK", "MKM"
        draft_format: "PremierDraft", "QuickDraft", "TradDraft"
        start_date:   "YYYY-MM-DD"
        end_date:     "YYYY-MM-DD" (defaults to today)
        color_filter: "" = All Decks, "WU" = Azorius, etc.

    Returns list of raw card dicts from 17Lands.
    """
    if end_date is None:
        end_date = date.today().isoformat()

    params: dict[str, str] = {
        "expansion":  set_code,
        "format":     draft_format,
        "start_date": start_date,
        "end_date":   end_date,
    }
    if color_filter:
        params["colors"] = color_filter

    resp = requests.get(
        "https://www.17lands.com/card_ratings/data",
        params=params,
        headers=_HEADERS,
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()


def _parse_card_ratings(raw_cards: list[dict]) -> dict[str, dict]:
    """
    Parse a list of 17Lands card dicts into our internal format.
    Keyed by card name (lowercased).

    Each card stores:
      {
        "name": str,
        "colors": list[str],
        "cmc": int,
        "types": list[str],
        "GIHWR": float | None,   # Games-In-Hand Win Rate (%)
        "OHWR": float | None,
        "GPWR": float | None,
        "ALSA": float | None,
        "ATA":  float | None,
        "GIH":  int,
        "NGP":  int,
      }
    """
    parsed: dict[str, dict] = {}
    for card in raw_cards:
        name = card.get("name", "").strip()
        if not name:
            continue

        entry: dict[str, Any] = {
            "name":   name,
            "colors": card.get("color", "").split() if card.get("color") else [],
            "cmc":    int(card.get("cmc", 0) or 0),
            "types":  _extract_types(card.get("types", "")),
        }

        for api_field, internal_key in _FIELD_MAP.items():
            raw_val = card.get(api_field)
            if raw_val is None:
                entry[internal_key] = None
            elif internal_key in ("NGP", "NGOH", "GIH", "NGND", "NGD"):
                entry[internal_key] = int(raw_val)
            elif internal_key in ("ALSA", "ATA"):
                entry[internal_key] = round(float(raw_val), 2)
            else:
                # Win rates: multiply by 100
                entry[internal_key] = round(float(raw_val) * 100.0, 2)

        parsed[name.lower()] = entry

    return parsed


def _extract_types(type_line: str) -> list[str]:
    """Extract card type keywords from type line string."""
    if not type_line:
        return []
    known = ["Creature", "Instant", "Sorcery", "Enchantment",
             "Artifact", "Land", "Planeswalker", "Battle"]
    return [t for t in known if t in type_line]


# ---------------------------------------------------------------------------
# Full set data fetch (all color filters)
# ---------------------------------------------------------------------------

def fetch_all_ratings(
    set_code: str,
    draft_format: str = "PremierDraft",
    start_date: str = config.RATINGS_START_DATE,
    progress_callback=None,
) -> dict[str, dict]:
    """
    Fetch ratings for ALL color filters and merge into a single dict.

    Each card entry gets a "deck_colors" sub-dict:
      card["deck_colors"]["All Decks"] = {GIHWR, OHWR, ...}
      card["deck_colors"]["WU"] = {...}
      ...

    Also computes SetMetrics (mean + std dev of GIHWR across All Decks).

    Returns dict keyed by lowercase card name.
    """
    merged: dict[str, dict] = {}
    total = len(_COLOR_FILTERS)

    for i, color in enumerate(_COLOR_FILTERS):
        label = color if color else "All Decks"
        if progress_callback:
            progress_callback(i, total, f"Fetching {label}…")
        try:
            raw = fetch_card_ratings(set_code, draft_format, start_date,
                                     color_filter=color)
            parsed = _parse_card_ratings(raw)

            for key, card in parsed.items():
                if key not in merged:
                    # First time seeing this card — copy base fields
                    merged[key] = {
                        "name":       card["name"],
                        "colors":     card["colors"],
                        "cmc":        card["cmc"],
                        "types":      card["types"],
                        "deck_colors": {},
                    }
                # Store ratings under the color filter key
                rating_fields = {k: v for k, v in card.items()
                                 if k not in ("name", "colors", "cmc", "types")}
                merged[key]["deck_colors"][label] = rating_fields

            time.sleep(0.15)  # Rate-limit courtesy

        except Exception as e:
            print(f"[api] Warning: failed to fetch {label} for {set_code}: {e}")

    # Compute set-level stats for grading
    _attach_set_metrics(merged)
    return merged


def _attach_set_metrics(cards: dict[str, dict]):
    """
    Compute mean and std dev of GIHWR (All Decks) across the set.
    Stores as cards["__meta__"]["mean"] and ["std_dev"].
    Applies Bayesian smoothing if configured.
    """
    win_rates = []
    for card in cards.values():
        wr = _get_gihwr(card, "All Decks")
        count = _get_gih(card, "All Decks")
        if wr is not None and count is not None:
            effective = _bayesian_winrate(wr, count) if config.BAYESIAN_ENABLED else (
                wr if count >= config.MIN_GAME_COUNT else None
            )
            if effective is not None:
                win_rates.append(effective)

    if not win_rates:
        mean, std_dev = 50.0, 3.0
    else:
        mean = sum(win_rates) / len(win_rates)
        variance = sum((x - mean) ** 2 for x in win_rates) / max(len(win_rates) - 1, 1)
        std_dev = math.sqrt(variance) if variance > 0 else 1.0

    cards["__meta__"] = {"mean": mean, "std_dev": std_dev}


def _get_gihwr(card: dict, color: str = "All Decks") -> float | None:
    return card.get("deck_colors", {}).get(color, {}).get("GIHWR")


def _get_gih(card: dict, color: str = "All Decks") -> int | None:
    return card.get("deck_colors", {}).get(color, {}).get("GIH")


def _bayesian_winrate(winrate: float, count: int) -> float:
    """Bayesian smoothing with a prior of 50% win rate, weight 200 games."""
    if count < 1:
        return 50.0
    raw_wins = winrate / 100.0 * count
    smoothed = (raw_wins + 100) / (count + 200)
    return round(smoothed * 100.0, 2)


# ---------------------------------------------------------------------------
# Color ratings
# ---------------------------------------------------------------------------

def fetch_color_ratings(
    set_code: str,
    draft_format: str = "PremierDraft",
    start_date: str = config.RATINGS_START_DATE,
) -> dict[str, float]:
    """
    Fetch color pair win rates from 17Lands.
    Returns dict like {"W": 51.2, "WU": 54.1, ...}
    Only includes color combos with >5000 games.
    """
    end_date = date.today().isoformat()
    resp = requests.get(
        "https://www.17lands.com/color_ratings/data",
        params={
            "expansion":      set_code,
            "event_type":     draft_format,
            "start_date":     start_date,
            "end_date":       end_date,
            "combine_splash": "true",
        },
        headers=_HEADERS,
        timeout=10,
    )
    resp.raise_for_status()
    raw = resp.json()

    result: dict[str, float] = {}
    for entry in raw:
        games = entry.get("games", 0) or 0
        if games < 5000:
            continue
        color = entry.get("color_name", "")
        wr = entry.get("win_rate")
        if color and wr is not None:
            result[color] = round(float(wr) * 100.0, 2)
    return result


# ---------------------------------------------------------------------------
# Caching
# ---------------------------------------------------------------------------

def save_cache(set_code: str, draft_format: str, ratings: dict):
    """Save fetched ratings to a local JSON cache file."""
    cache = _load_cache_file()
    key = f"{set_code}_{draft_format}"
    cache[key] = {
        "fetched_date": date.today().isoformat(),
        "ratings": ratings,
    }
    with open(config.RATINGS_CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f)


def load_cache(set_code: str, draft_format: str) -> dict | None:
    """Load cached ratings if they exist and are less than 7 days old."""
    cache = _load_cache_file()
    key = f"{set_code}_{draft_format}"
    entry = cache.get(key)
    if entry:
        fetched = entry.get("fetched_date", "")
        cutoff = (date.today() - timedelta(days=7)).isoformat()
        if fetched >= cutoff:
            print(f"[api] Cache hit for {key} (fetched {fetched})")
            return entry["ratings"]
    return None


def _load_cache_file() -> dict:
    if os.path.exists(config.RATINGS_CACHE_FILE):
        try:
            with open(config.RATINGS_CACHE_FILE, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

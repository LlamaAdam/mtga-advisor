"""
Card rating and grading engine.

Uses 17Lands GIH win rates and grades cards relative to the set's
mean + standard deviation (same methodology as bstaple1/MTGA_Draft_17Lands).

Grade thresholds (standard deviations from set mean):
  A+  >= +2.0σ
  A   >= +1.5σ
  A-  >= +1.0σ
  B+  >= +0.5σ
  B   >= +0.17σ
  B-  >= -0.17σ
  C+  >= -0.33σ
  C   >= -0.5σ
  C-  >= -0.83σ
  D+  >= -1.0σ
  D   >= -1.33σ
  D-  >= -1.67σ
  F   = below all
"""

import difflib

from . import config


# Loaded ratings: {"lowercase card name": {...card data...}}
_ratings: dict = {}
_set_mean: float = 50.0
_set_std:  float = 3.0


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------

def load(ratings_data: dict):
    """
    Load ratings returned by api.fetch_all_ratings().
    Extracts set-level stats from __meta__ key.
    """
    global _ratings, _set_mean, _set_std
    meta = ratings_data.get("__meta__", {})
    _set_mean = meta.get("mean", 50.0)
    _set_std  = meta.get("std_dev", 3.0)
    _ratings  = {k: v for k, v in ratings_data.items() if k != "__meta__"}
    print(f"[ratings] Loaded {len(_ratings)} cards. "
          f"Set mean GIHWR: {_set_mean:.1f}% ± {_set_std:.1f}%")


def is_loaded() -> bool:
    return bool(_ratings)


# ---------------------------------------------------------------------------
# Lookup
# ---------------------------------------------------------------------------

def _lookup(card_name: str) -> dict | None:
    """Find card data by name, with fuzzy matching for OCR/log noise."""
    key = card_name.strip().lower()

    if key in _ratings:
        return _ratings[key]

    # Fuzzy match (handles minor name mismatches)
    matches = difflib.get_close_matches(key, _ratings.keys(), n=1, cutoff=0.85)
    if matches:
        return _ratings[matches[0]]

    return None


def get_winrate(card_name: str, color_filter: str = "All Decks") -> float | None:
    """
    Return the GIH win rate for a card under the given color filter.
    Returns None if the card is not found or has insufficient data.
    """
    card = _lookup(card_name)
    if card is None:
        return None

    deck_colors = card.get("deck_colors", {})

    # Try requested color filter, fall back to All Decks
    for cf in [color_filter, "All Decks"]:
        wr = deck_colors.get(cf, {}).get("GIHWR")
        count = deck_colors.get(cf, {}).get("GIH", 0) or 0
        if wr is not None:
            if config.BAYESIAN_ENABLED:
                return _bayesian(wr, count)
            if count >= config.MIN_GAME_COUNT:
                return wr
            return None  # Not enough data

    return None


def _bayesian(winrate: float, count: int) -> float:
    """Bayesian smoothing toward 50% with prior weight of 200 games."""
    raw_wins = winrate / 100.0 * count
    smoothed = (raw_wins + 100) / (count + 200)
    return round(smoothed * 100.0, 2)


# ---------------------------------------------------------------------------
# Grading
# ---------------------------------------------------------------------------

def winrate_to_grade(winrate: float | None) -> str:
    """
    Convert a raw GIH win rate to a letter grade using std-dev thresholds.
    Matches bstaple1's grading methodology.
    """
    if winrate is None or _set_std == 0:
        return "?"

    z = (winrate - _set_mean) / _set_std

    for grade, threshold in config.GRADE_THRESHOLDS:
        if z >= threshold:
            return grade

    return "F"


def grade_color(grade: str) -> str:
    return config.GRADE_COLORS.get(grade, "#555555")


# ---------------------------------------------------------------------------
# Full card info
# ---------------------------------------------------------------------------

def get_card_info(card_name: str) -> dict | None:
    """Return the full card data dict, or None if not found."""
    return _lookup(card_name)


def get_colors(card_name: str) -> list[str]:
    card = _lookup(card_name)
    colors = card.get("colors", []) if card else []
    if not colors:
        # Fall back to inferring colors from mana cost pips in Scryfall cache
        import re as _re
        from . import card_db as _card_db
        mc = _card_db.get_mana_cost(card_name)
        if mc:
            colors = list(dict.fromkeys(_re.findall(r'\{([WUBRG])\}', mc)))
    return colors


def get_cmc(card_name: str) -> int:
    card = _lookup(card_name)
    cmc = card.get("cmc", 0) if card else 0
    if not cmc:
        from . import card_db
        cmc = card_db.get_cmc(card_name)
    return cmc


def get_types(card_name: str) -> list[str]:
    card = _lookup(card_name)
    return card.get("types", []) if card else []


def get_alsa(card_name: str) -> float | None:
    """Average Last Seen At — when this card wheels on average."""
    card = _lookup(card_name)
    if card:
        return card.get("deck_colors", {}).get("All Decks", {}).get("ALSA")
    return None


def get_ata(card_name: str) -> float | None:
    """Average Taken At — average pick position."""
    card = _lookup(card_name)
    if card:
        return card.get("deck_colors", {}).get("All Decks", {}).get("ATA")
    return None

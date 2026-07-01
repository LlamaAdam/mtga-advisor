"""Tests for api.py — 17Lands client.

Network is mocked via monkeypatch on `requests.get`. Tests cover:
- field mapping (raw 17Lands JSON → internal keys)
- win-rate scaling (17Lands ships fractions, we store percentages)
- color-pair filtering by min-game threshold
- set-level mean/std-dev computation
- Bayesian smoothing for low-game-count cards
- cache hit / miss / stale invalidation
- progress callback fires per color filter
"""
from __future__ import annotations

import json
from datetime import date, timedelta
from typing import Any

import pytest

from draft_helper import api


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class _FakeResp:
    """Minimal stand-in for `requests.Response`."""

    def __init__(self, payload: Any, status: int = 200) -> None:
        self._payload = payload
        self._status = status

    def json(self) -> Any:
        return self._payload

    def raise_for_status(self) -> None:
        if self._status >= 400:
            raise RuntimeError(f"HTTP {self._status}")


def _card(
    name: str = "Test Bear",
    ever_drawn_win_rate: float = 0.55,
    win_rate: float = 0.52,
    ever_drawn_game_count: int = 5000,
    color: str = "G",
    cmc: int = 2,
    types: str = "Creature",
) -> dict:
    """Build a synthetic 17Lands card record."""
    return {
        "name": name,
        "color": color,
        "cmc": cmc,
        "types": types,
        "ever_drawn_win_rate": ever_drawn_win_rate,
        "opening_hand_win_rate": 0.50,
        "win_rate": win_rate,
        "avg_seen": 4.5,
        "drawn_improvement_win_rate": 0.02,
        "avg_pick": 5.1,
        "game_count": 8000,
        "opening_hand_game_count": 1000,
        "ever_drawn_game_count": ever_drawn_game_count,
        "never_drawn_win_rate": 0.48,
        "never_drawn_game_count": 3000,
        "drawn_win_rate": 0.55,
        "drawn_game_count": 4000,
    }


# ---------------------------------------------------------------------------
# fetch_available_sets
# ---------------------------------------------------------------------------

def test_fetch_available_sets_returns_expansions(monkeypatch):
    payload = {"expansions": [
        {"label": "Bloomburrow", "value": "BLB"},
        {"label": "Duskmourn", "value": "DSK"},
    ]}
    monkeypatch.setattr(
        "draft_helper.api.requests.get", lambda *a, **kw: _FakeResp(payload),
    )
    sets = api.fetch_available_sets()
    assert sets == payload["expansions"]


def test_fetch_available_sets_handles_empty_response(monkeypatch):
    monkeypatch.setattr(
        "draft_helper.api.requests.get", lambda *a, **kw: _FakeResp({}),
    )
    assert api.fetch_available_sets() == []


# ---------------------------------------------------------------------------
# fetch_card_ratings
# ---------------------------------------------------------------------------

def test_fetch_card_ratings_passes_set_and_format(monkeypatch):
    captured: dict[str, Any] = {}

    def fake_get(url, params=None, headers=None, timeout=None):
        captured["url"] = url
        captured["params"] = params
        return _FakeResp([_card()])

    monkeypatch.setattr("draft_helper.api.requests.get", fake_get)
    out = api.fetch_card_ratings(
        "BLB", draft_format="PremierDraft", start_date="2026-01-01",
    )
    assert captured["params"]["expansion"] == "BLB"
    assert captured["params"]["format"] == "PremierDraft"
    assert captured["params"]["start_date"] == "2026-01-01"
    # Default end date = today.
    assert captured["params"]["end_date"] == date.today().isoformat()
    assert isinstance(out, list)


def test_fetch_card_ratings_omits_colors_when_empty(monkeypatch):
    captured: dict[str, Any] = {}

    def fake_get(url, params=None, headers=None, timeout=None):
        captured["params"] = params
        return _FakeResp([])

    monkeypatch.setattr("draft_helper.api.requests.get", fake_get)
    api.fetch_card_ratings("BLB", color_filter="")
    assert "colors" not in captured["params"]


def test_fetch_card_ratings_includes_colors_when_set(monkeypatch):
    captured: dict[str, Any] = {}

    def fake_get(url, params=None, headers=None, timeout=None):
        captured["params"] = params
        return _FakeResp([])

    monkeypatch.setattr("draft_helper.api.requests.get", fake_get)
    api.fetch_card_ratings("BLB", color_filter="WU")
    assert captured["params"]["colors"] == "WU"


# ---------------------------------------------------------------------------
# _parse_card_ratings — field mapping + win-rate scaling
# ---------------------------------------------------------------------------

def test_parse_card_ratings_maps_internal_keys():
    raw = [_card("Bear", ever_drawn_win_rate=0.60)]
    parsed = api._parse_card_ratings(raw)
    assert "bear" in parsed
    entry = parsed["bear"]
    assert entry["name"] == "Bear"
    assert entry["GIHWR"] == 60.0  # 0.60 → 60.0
    assert entry["GPWR"] == 52.0   # win_rate × 100
    assert entry["NGP"] == 8000
    assert entry["GIH"] == 5000
    assert entry["ALSA"] == 4.5
    assert "Creature" in entry["types"]


def test_parse_card_ratings_skips_blank_names():
    raw = [_card(name=""), _card(name="Real")]
    parsed = api._parse_card_ratings(raw)
    assert "real" in parsed
    assert "" not in parsed
    assert len(parsed) == 1


def test_parse_card_ratings_handles_null_win_rate():
    raw = [_card()]
    raw[0]["ever_drawn_win_rate"] = None
    parsed = api._parse_card_ratings(raw)
    assert parsed["test bear"]["GIHWR"] is None


def test_extract_types_finds_known_keywords():
    assert api._extract_types("Legendary Creature - Beast") == ["Creature"]
    assert api._extract_types("Artifact Land") == ["Artifact", "Land"]
    assert api._extract_types("") == []
    assert api._extract_types(None or "") == []


# ---------------------------------------------------------------------------
# fetch_all_ratings — multi-color-filter merge + progress callback
# ---------------------------------------------------------------------------

def test_fetch_all_ratings_merges_color_filters(monkeypatch):
    """One card surfaces across All Decks + WU; both should land in
    deck_colors."""
    monkeypatch.setattr("draft_helper.api.time.sleep", lambda *a, **kw: None)

    def fake_get(url, params=None, headers=None, timeout=None):
        return _FakeResp([_card("Bear")])

    monkeypatch.setattr("draft_helper.api.requests.get", fake_get)
    monkeypatch.setattr("draft_helper.config.MIN_GAME_COUNT", 100, raising=False)
    monkeypatch.setattr("draft_helper.config.BAYESIAN_ENABLED", False, raising=False)
    monkeypatch.setattr("draft_helper.config.RATINGS_START_DATE", "2026-01-01", raising=False)

    merged = api.fetch_all_ratings("BLB")
    assert "bear" in merged
    deck_colors = merged["bear"]["deck_colors"]
    # We sent the same card for every filter, so every label should appear.
    assert "All Decks" in deck_colors
    assert "WU" in deck_colors
    # Set-level metrics should be attached.
    assert "__meta__" in merged
    assert "mean" in merged["__meta__"]
    assert "std_dev" in merged["__meta__"]


def test_fetch_all_ratings_invokes_progress_callback(monkeypatch):
    monkeypatch.setattr("draft_helper.api.time.sleep", lambda *a, **kw: None)
    monkeypatch.setattr(
        "draft_helper.api.requests.get", lambda *a, **kw: _FakeResp([_card()]),
    )
    monkeypatch.setattr("draft_helper.config.MIN_GAME_COUNT", 100, raising=False)
    monkeypatch.setattr("draft_helper.config.BAYESIAN_ENABLED", False, raising=False)
    monkeypatch.setattr("draft_helper.config.RATINGS_START_DATE", "2026-01-01", raising=False)

    calls: list[tuple[int, int, str]] = []
    api.fetch_all_ratings("BLB", progress_callback=lambda i, t, m: calls.append((i, t, m)))
    # One callback per color filter.
    assert len(calls) == len(api._COLOR_FILTERS)
    # First call should reference "All Decks" (empty color).
    assert "All Decks" in calls[0][2]


def test_fetch_all_ratings_warns_on_filter_failure(monkeypatch, capsys):
    """One filter throws; others succeed → set still builds."""
    monkeypatch.setattr("draft_helper.api.time.sleep", lambda *a, **kw: None)
    monkeypatch.setattr("draft_helper.config.MIN_GAME_COUNT", 100, raising=False)
    monkeypatch.setattr("draft_helper.config.BAYESIAN_ENABLED", False, raising=False)
    monkeypatch.setattr("draft_helper.config.RATINGS_START_DATE", "2026-01-01", raising=False)

    call_count = {"n": 0}

    def fake_get(url, params=None, headers=None, timeout=None):
        call_count["n"] += 1
        if call_count["n"] == 3:  # third filter fails
            raise RuntimeError("simulated network error")
        return _FakeResp([_card()])

    monkeypatch.setattr("draft_helper.api.requests.get", fake_get)
    merged = api.fetch_all_ratings("BLB")
    captured = capsys.readouterr()
    assert "Warning" in captured.out
    # Should still have built the set despite one failure.
    assert "test bear" in merged


# ---------------------------------------------------------------------------
# _attach_set_metrics
# ---------------------------------------------------------------------------

def test_attach_set_metrics_computes_mean_and_std(monkeypatch):
    monkeypatch.setattr("draft_helper.config.MIN_GAME_COUNT", 100, raising=False)
    monkeypatch.setattr("draft_helper.config.BAYESIAN_ENABLED", False, raising=False)

    cards = {
        "a": {"deck_colors": {"All Decks": {"GIHWR": 50.0, "GIH": 1000}}},
        "b": {"deck_colors": {"All Decks": {"GIHWR": 55.0, "GIH": 1000}}},
        "c": {"deck_colors": {"All Decks": {"GIHWR": 45.0, "GIH": 1000}}},
    }
    api._attach_set_metrics(cards)
    assert cards["__meta__"]["mean"] == pytest.approx(50.0)
    assert cards["__meta__"]["std_dev"] > 0


def test_attach_set_metrics_falls_back_when_no_data(monkeypatch):
    monkeypatch.setattr("draft_helper.config.MIN_GAME_COUNT", 100, raising=False)
    monkeypatch.setattr("draft_helper.config.BAYESIAN_ENABLED", False, raising=False)
    cards: dict = {}
    api._attach_set_metrics(cards)
    assert cards["__meta__"]["mean"] == 50.0
    assert cards["__meta__"]["std_dev"] == 3.0


def test_attach_set_metrics_filters_low_game_counts(monkeypatch):
    """Cards below MIN_GAME_COUNT shouldn't influence the mean
    when bayesian smoothing is off."""
    monkeypatch.setattr("draft_helper.config.MIN_GAME_COUNT", 500, raising=False)
    monkeypatch.setattr("draft_helper.config.BAYESIAN_ENABLED", False, raising=False)
    cards = {
        "real": {"deck_colors": {"All Decks": {"GIHWR": 60.0, "GIH": 1000}}},
        "noise": {"deck_colors": {"All Decks": {"GIHWR": 99.0, "GIH": 10}}},
    }
    api._attach_set_metrics(cards)
    # Only the real card contributes → mean ≈ 60.
    assert cards["__meta__"]["mean"] == pytest.approx(60.0)


# ---------------------------------------------------------------------------
# Bayesian smoothing
# ---------------------------------------------------------------------------

def test_bayesian_winrate_pulls_low_count_toward_50():
    """A 100% winrate over 5 games should be heavily smoothed."""
    smoothed = api._bayesian_winrate(100.0, 5)
    assert 50.0 < smoothed < 60.0  # nudged up only slightly


def test_bayesian_winrate_high_count_barely_moves():
    """A 60% winrate over 5000 games should stay close to 60."""
    smoothed = api._bayesian_winrate(60.0, 5000)
    assert 59.0 < smoothed < 60.5


def test_bayesian_winrate_zero_count_returns_prior():
    assert api._bayesian_winrate(99.0, 0) == 50.0


# ---------------------------------------------------------------------------
# fetch_color_ratings
# ---------------------------------------------------------------------------

def test_fetch_color_ratings_filters_low_game_combos(monkeypatch):
    payload = [
        {"color_name": "WU", "win_rate": 0.55, "games": 10000},
        {"color_name": "BR", "win_rate": 0.99, "games": 100},  # too few
        {"color_name": "G",  "win_rate": 0.51, "games": 8000},
    ]
    monkeypatch.setattr(
        "draft_helper.api.requests.get", lambda *a, **kw: _FakeResp(payload),
    )
    monkeypatch.setattr("draft_helper.config.RATINGS_START_DATE", "2026-01-01", raising=False)

    out = api.fetch_color_ratings("BLB")
    assert "WU" in out
    assert "G" in out
    assert "BR" not in out  # filtered by games < 5000
    assert out["WU"] == 55.0


def test_fetch_color_ratings_ignores_entries_without_winrate(monkeypatch):
    payload = [
        {"color_name": "WU", "win_rate": None, "games": 10000},
        {"color_name": "",   "win_rate": 0.55, "games": 10000},
    ]
    monkeypatch.setattr(
        "draft_helper.api.requests.get", lambda *a, **kw: _FakeResp(payload),
    )
    monkeypatch.setattr("draft_helper.config.RATINGS_START_DATE", "2026-01-01", raising=False)
    out = api.fetch_color_ratings("BLB")
    assert out == {}


# ---------------------------------------------------------------------------
# Cache I/O
# ---------------------------------------------------------------------------

def test_save_and_load_cache_roundtrip(tmp_path, monkeypatch):
    cache_file = tmp_path / "ratings_cache.json"
    monkeypatch.setattr("draft_helper.config.RATINGS_CACHE_FILE", str(cache_file), raising=False)
    ratings = {"bear": {"name": "Bear", "GIHWR": 55.0}}
    api.save_cache("BLB", "PremierDraft", ratings)
    loaded = api.load_cache("BLB", "PremierDraft")
    assert loaded == ratings


def test_load_cache_miss_returns_none(tmp_path, monkeypatch):
    cache_file = tmp_path / "missing.json"
    monkeypatch.setattr("draft_helper.config.RATINGS_CACHE_FILE", str(cache_file), raising=False)
    assert api.load_cache("BLB", "PremierDraft") is None


def test_load_cache_stale_returns_none(tmp_path, monkeypatch):
    """A cache file older than 7 days should be invalidated."""
    cache_file = tmp_path / "ratings_cache.json"
    stale_date = (date.today() - timedelta(days=10)).isoformat()
    cache_file.write_text(json.dumps({
        "BLB_PremierDraft": {
            "fetched_date": stale_date,
            "ratings": {"bear": {"name": "Bear"}},
        },
    }))
    monkeypatch.setattr("draft_helper.config.RATINGS_CACHE_FILE", str(cache_file), raising=False)
    assert api.load_cache("BLB", "PremierDraft") is None


def test_load_cache_corrupt_file_returns_none(tmp_path, monkeypatch):
    cache_file = tmp_path / "ratings_cache.json"
    cache_file.write_text("not valid json {")
    monkeypatch.setattr("draft_helper.config.RATINGS_CACHE_FILE", str(cache_file), raising=False)
    assert api.load_cache("BLB", "PremierDraft") is None


def test_save_cache_overwrites_existing_entry(tmp_path, monkeypatch):
    cache_file = tmp_path / "ratings_cache.json"
    monkeypatch.setattr("draft_helper.config.RATINGS_CACHE_FILE", str(cache_file), raising=False)
    api.save_cache("BLB", "PremierDraft", {"old": "data"})
    api.save_cache("BLB", "PremierDraft", {"new": "data"})
    loaded = api.load_cache("BLB", "PremierDraft")
    assert loaded == {"new": "data"}

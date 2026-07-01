"""Tests for ratings.py — 17lands rating + grading logic.

Pure-logic tests (no network); all data is injected via `ratings.load()`
with synthetic 17lands-shaped dicts. Mirrors the structure produced by
`api.fetch_all_ratings()`.
"""
from __future__ import annotations

import pytest

from draft_helper import config
from draft_helper import ratings


@pytest.fixture(autouse=True)
def isolate_ratings_module():
    """Snapshot/restore module state so tests don't leak ratings data."""
    orig_ratings = ratings._ratings.copy()
    orig_mean = ratings._set_mean
    orig_std = ratings._set_std
    yield
    ratings._ratings.clear()
    ratings._ratings.update(orig_ratings)
    ratings._set_mean = orig_mean
    ratings._set_std = orig_std


def _bolt_record(gihwr: float = 60.0, gih_count: int = 1000) -> dict:
    """Synthetic 17lands card record matching the live shape."""
    return {
        "colors": ["R"],
        "cmc": 1,
        "types": ["Instant"],
        "deck_colors": {
            "All Decks": {"GIHWR": gihwr, "GIH": gih_count, "ALSA": 2.5, "ATA": 1.8},
            "WU": {"GIHWR": 50.0, "GIH": gih_count},
        },
    }


# ---------------------------------------------------------------------------
# load + is_loaded
# ---------------------------------------------------------------------------

def test_is_loaded_false_on_fresh_module():
    ratings._ratings.clear()
    assert ratings.is_loaded() is False


def test_load_populates_ratings():
    data = {
        "__meta__": {"mean": 55.0, "std_dev": 4.0},
        "lightning bolt": _bolt_record(),
    }
    ratings.load(data)
    assert ratings.is_loaded() is True
    assert ratings._set_mean == 55.0
    assert ratings._set_std == 4.0


def test_load_excludes_meta_from_ratings_dict():
    """The __meta__ key should be stored as scalar fields, not card data."""
    data = {
        "__meta__": {"mean": 50.0, "std_dev": 3.0},
        "card a": _bolt_record(),
        "card b": _bolt_record(),
    }
    ratings.load(data)
    assert "__meta__" not in ratings._ratings
    assert len(ratings._ratings) == 2


def test_load_uses_defaults_when_meta_missing():
    """No __meta__ key → fall back to mean=50, std=3."""
    ratings.load({"card a": _bolt_record()})
    assert ratings._set_mean == 50.0
    assert ratings._set_std == 3.0


# ---------------------------------------------------------------------------
# _lookup — exact + fuzzy
# ---------------------------------------------------------------------------

def test_lookup_exact_match_lowercase():
    ratings.load({
        "__meta__": {"mean": 50.0, "std_dev": 3.0},
        "lightning bolt": _bolt_record(60.0),
    })
    found = ratings._lookup("Lightning Bolt")
    assert found is not None
    assert found["deck_colors"]["All Decks"]["GIHWR"] == 60.0


def test_lookup_strips_whitespace():
    ratings.load({"sol ring": _bolt_record()})
    assert ratings._lookup("  Sol Ring  ") is not None


def test_lookup_fuzzy_match_close_typo():
    """Off-by-one typo should match via difflib.close_matches."""
    ratings.load({"lightning bolt": _bolt_record()})
    # "Lightning Bot" → fuzzy match to "lightning bolt"
    assert ratings._lookup("Lightning Bot") is not None


def test_lookup_returns_none_for_unrelated_string():
    ratings.load({"lightning bolt": _bolt_record()})
    assert ratings._lookup("Atraxa Praetors Voice") is None


# ---------------------------------------------------------------------------
# get_winrate — color filter + Bayesian
# ---------------------------------------------------------------------------

def test_get_winrate_returns_color_filter_value(monkeypatch):
    """Asking for a specific color filter should return that filter's GIHWR."""
    monkeypatch.setattr(config, "BAYESIAN_ENABLED", False)
    monkeypatch.setattr(config, "MIN_GAME_COUNT", 100)
    ratings.load({
        "card a": {
            "deck_colors": {
                "All Decks": {"GIHWR": 55.0, "GIH": 1000},
                "RG":        {"GIHWR": 62.0, "GIH": 500},
            },
        },
    })
    assert ratings.get_winrate("Card A", "RG") == 62.0


def test_get_winrate_falls_back_to_all_decks(monkeypatch):
    """Unknown color filter → fall back to All Decks."""
    monkeypatch.setattr(config, "BAYESIAN_ENABLED", False)
    monkeypatch.setattr(config, "MIN_GAME_COUNT", 100)
    ratings.load({
        "card a": {
            "deck_colors": {"All Decks": {"GIHWR": 55.0, "GIH": 1000}},
        },
    })
    # "WUBRG" filter not present; falls back to All Decks
    assert ratings.get_winrate("Card A", "WUBRG") == 55.0


def test_get_winrate_returns_none_when_below_min_count(monkeypatch):
    """Below MIN_GAME_COUNT and Bayesian off → None."""
    monkeypatch.setattr(config, "BAYESIAN_ENABLED", False)
    monkeypatch.setattr(config, "MIN_GAME_COUNT", 100)
    ratings.load({
        "card a": {
            "deck_colors": {"All Decks": {"GIHWR": 60.0, "GIH": 50}},
        },
    })
    assert ratings.get_winrate("Card A") is None


def test_get_winrate_returns_none_for_missing_card():
    ratings.load({"card a": _bolt_record()})
    assert ratings.get_winrate("Definitely Missing") is None


def test_bayesian_smoothing_pulls_toward_fifty():
    """Few-games card with high observed wr should be pulled toward 50%."""
    smoothed = ratings._bayesian(80.0, 10)  # 8 wins out of 10
    # Bayesian: (8 + 100) / (10 + 200) = 108 / 210 ≈ 51.4%
    assert 50.0 < smoothed < 55.0


def test_bayesian_smoothing_high_count_close_to_observed():
    """Lots-of-games card should stay close to observed."""
    smoothed = ratings._bayesian(60.0, 10000)
    # (6000 + 100) / (10200) ≈ 59.8% — very close to 60.
    assert 59.5 < smoothed < 60.0


# ---------------------------------------------------------------------------
# winrate_to_grade
# ---------------------------------------------------------------------------

def test_winrate_to_grade_returns_question_for_none():
    ratings._set_std = 3.0
    assert ratings.winrate_to_grade(None) == "?"


def test_winrate_to_grade_returns_question_for_zero_std():
    """With zero std-dev, division would fail; return '?' instead."""
    ratings.load({"__meta__": {"mean": 50.0, "std_dev": 0.0}})
    assert ratings.winrate_to_grade(60.0) == "?"


def test_winrate_to_grade_high_winrate_high_grade():
    """A wr 2 std above mean should be A+ (or whatever the highest threshold is)."""
    ratings.load({"__meta__": {"mean": 50.0, "std_dev": 3.0}})
    grade = ratings.winrate_to_grade(60.0)  # z = +3.33
    assert grade in {"A+", "A"}


def test_winrate_to_grade_low_winrate_low_grade():
    ratings.load({"__meta__": {"mean": 50.0, "std_dev": 3.0}})
    grade = ratings.winrate_to_grade(40.0)  # z = -3.33
    assert grade in {"D-", "F"}


def test_winrate_to_grade_average_winrate_middle_grade():
    """Wr at the set mean should land in the middle (B-, C+, or B)."""
    ratings.load({"__meta__": {"mean": 50.0, "std_dev": 3.0}})
    grade = ratings.winrate_to_grade(50.0)  # z = 0
    assert grade in {"B-", "B", "C+"}


# ---------------------------------------------------------------------------
# get_colors / get_cmc / get_types — fall-throughs
# ---------------------------------------------------------------------------

def test_get_colors_returns_card_colors():
    ratings.load({"card a": {"colors": ["U", "B"]}})
    assert ratings.get_colors("Card A") == ["U", "B"]


def test_get_cmc_returns_card_cmc():
    ratings.load({"sol ring": _bolt_record(gihwr=70.0)})
    # _bolt_record sets cmc=1
    assert ratings.get_cmc("Sol Ring") == 1


def test_get_types_returns_types_or_empty():
    ratings.load({"sol ring": _bolt_record()})  # _bolt_record sets types=["Instant"]
    assert ratings.get_types("Sol Ring") == ["Instant"]
    assert ratings.get_types("Unknown Card") == []


# ---------------------------------------------------------------------------
# get_alsa / get_ata — pick-timing metrics
# ---------------------------------------------------------------------------

def test_get_alsa_returns_value_when_present():
    ratings.load({"sol ring": _bolt_record()})
    assert ratings.get_alsa("Sol Ring") == 2.5


def test_get_ata_returns_value_when_present():
    ratings.load({"sol ring": _bolt_record()})
    assert ratings.get_ata("Sol Ring") == 1.8


def test_get_alsa_returns_none_for_missing_card():
    ratings.load({"sol ring": _bolt_record()})
    assert ratings.get_alsa("Definitely Missing") is None

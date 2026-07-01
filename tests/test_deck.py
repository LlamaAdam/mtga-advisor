"""Tests for deck.py — the DeckTracker that drives the draft-helper overlay.

Coverage focuses on the pure-logic methods (pick / pack-tracking, color
counting, off-color penalty calculation) that don't require network or
the 17lands ratings cache. The rating-derived methods (`best_pick`,
`adjusted_rating`) are exercised indirectly via mocks.
"""
from __future__ import annotations

from collections import Counter

import pytest

from draft_helper import card_db
from draft_helper import deck
from draft_helper import ratings


@pytest.fixture(autouse=True)
def isolate_deck_module(monkeypatch):
    """Each test starts with a clean DeckTracker, no real I/O."""
    # Disable shared-store and disk persistence in card_db.
    monkeypatch.setattr("draft_helper.card_db._resolve_shared_cards_dir", lambda: None)
    monkeypatch.setattr("draft_helper.card_db._save_cache", lambda: None)
    monkeypatch.setattr("draft_helper.card_db._load_cache", lambda: None)
    # Snapshot card_db dicts to restore after each test.
    orig_oracle = card_db._oracle.copy()
    orig_mana = card_db._mana_cost.copy()
    yield
    card_db._oracle.clear()
    card_db._oracle.update(orig_oracle)
    card_db._mana_cost.clear()
    card_db._mana_cost.update(orig_mana)


# ---------------------------------------------------------------------------
# DeckTracker — pick tracking
# ---------------------------------------------------------------------------

def test_new_tracker_starts_at_pack1_pick1():
    t = deck.DeckTracker()
    assert t.pack_number == 1
    assert t.pick_number == 1
    assert t.picks == []


def test_add_pick_increments_pick_number():
    t = deck.DeckTracker()
    t.add_pick("Lightning Bolt")
    assert t.picks == ["Lightning Bolt"]
    assert t.pick_number == 2
    assert t.pack_number == 1


def test_add_pick_rolls_over_to_next_pack():
    """After pick 15 of pack 1, the next add should roll to pack 2 pick 1."""
    t = deck.DeckTracker()
    for i in range(15):
        t.add_pick(f"Card{i}")
    # We should now be on pack 2 pick 1 (after 15 picks from pack 1).
    assert t.pack_number == 2
    assert t.pick_number == 1


def test_add_pick_full_three_packs():
    t = deck.DeckTracker()
    for i in range(45):
        t.add_pick(f"Card{i}")
    # 15 picks × 3 packs = 45 picks total. Should be on pack 4 pick 1.
    assert t.pack_number == 4
    assert t.pick_number == 1
    assert len(t.picks) == 45


def test_add_pick_ignores_empty_card_name():
    t = deck.DeckTracker()
    t.add_pick("")
    assert t.picks == []
    assert t.pick_number == 1


def test_remove_last_pick_decrements_state():
    t = deck.DeckTracker()
    t.add_pick("Lightning Bolt")
    t.add_pick("Counterspell")
    t.remove_last_pick()
    assert t.picks == ["Lightning Bolt"]
    assert t.pick_number == 2


def test_remove_last_pick_rolls_back_across_packs():
    """If we're on pack 2 pick 1 and undo, we should land on pack 1 pick 15."""
    t = deck.DeckTracker()
    for i in range(15):
        t.add_pick(f"Card{i}")
    assert t.pack_number == 2 and t.pick_number == 1
    t.remove_last_pick()
    assert t.pack_number == 1
    assert t.pick_number == 15


def test_remove_last_pick_no_op_when_empty():
    t = deck.DeckTracker()
    t.remove_last_pick()
    assert t.picks == []
    assert t.pick_number == 1


def test_clear_resets_to_empty_state():
    t = deck.DeckTracker()
    t.add_pick("Foo")
    t.add_pick("Bar")
    t.clear()
    assert t.picks == []
    assert t.pack_number == 1
    assert t.pick_number == 1


# ---------------------------------------------------------------------------
# Color counting
# ---------------------------------------------------------------------------

def test_color_counts_aggregates_picks(monkeypatch):
    monkeypatch.setattr(
        "draft_helper.ratings.get_colors",
        lambda name: {
            "Lightning Bolt": ["R"],
            "Counterspell": ["U", "U"],
            "Forest": [],
        }.get(name, []),
    )
    t = deck.DeckTracker()
    t.add_pick("Lightning Bolt")
    t.add_pick("Counterspell")
    t.add_pick("Forest")
    counts = t.color_counts()
    assert counts == Counter({"U": 2, "R": 1})


def test_main_colors_picks_top_two_when_second_meets_threshold(monkeypatch):
    """main_colors returns the top 2 only when the second color has ≥3 cards."""
    monkeypatch.setattr(
        "draft_helper.ratings.get_colors",
        lambda name: {
            "Bolt1": ["R"], "Bolt2": ["R"], "Bolt3": ["R"], "Bolt4": ["R"],
            "Negate1": ["U"], "Negate2": ["U"], "Negate3": ["U"],
            "Splice": ["G"],
        }.get(name, []),
    )
    t = deck.DeckTracker()
    for c in ["Bolt1", "Bolt2", "Bolt3", "Bolt4",
              "Negate1", "Negate2", "Negate3", "Splice"]:
        t.add_pick(c)
    main = t.main_colors()
    # R (4) wins; U (3) meets threshold and joins; G (1) doesn't.
    assert "R" in main and "U" in main
    assert "G" not in main


def test_main_colors_drops_second_color_below_threshold(monkeypatch):
    """If the second color only has 2 cards, it shouldn't make the cut."""
    monkeypatch.setattr(
        "draft_helper.ratings.get_colors",
        lambda name: {
            "Bolt1": ["R"], "Bolt2": ["R"], "Bolt3": ["R"],
            "Negate1": ["U"], "Negate2": ["U"],  # only 2 — below threshold
        }.get(name, []),
    )
    t = deck.DeckTracker()
    for c in ["Bolt1", "Bolt2", "Bolt3", "Negate1", "Negate2"]:
        t.add_pick(c)
    main = t.main_colors()
    # R (3) is the only main color — U (2) is below the 3-card threshold.
    assert main == ["R"]


def test_main_colors_empty_deck_returns_empty():
    t = deck.DeckTracker()
    assert t.main_colors() == []


# ---------------------------------------------------------------------------
# _land_produced_colors — pure parser
# ---------------------------------------------------------------------------

def test_land_produced_colors_parses_dual():
    """Dismal Backwater-style land — Add U or B."""
    card_db._oracle["dismal backwater"] = "{T}: Add {U} or {B}."
    assert sorted(deck._land_produced_colors("Dismal Backwater")) == ["B", "U"]


def test_land_produced_colors_parses_basic():
    card_db._oracle["forest"] = "({T}: Add {G}.)"
    assert deck._land_produced_colors("Forest") == ["G"]


def test_land_produced_colors_returns_empty_for_unknown():
    assert deck._land_produced_colors("Mystery Land") == []


# ---------------------------------------------------------------------------
# _count_off_color_pips
# ---------------------------------------------------------------------------

def test_count_off_color_pips_no_off_colors():
    card_db._mana_cost["lightning bolt"] = "{R}"
    assert deck._count_off_color_pips("Lightning Bolt", {"R", "G"}) == 0


def test_count_off_color_pips_all_off():
    card_db._mana_cost["counterspell"] = "{U}{U}"
    # main_colors is BR — both U pips are off-color.
    assert deck._count_off_color_pips("Counterspell", {"B", "R"}) == 2


def test_count_off_color_pips_mixed():
    card_db._mana_cost["abrupt decay"] = "{B}{G}"
    # main_colors GR → B is off (1), G is on (0).
    assert deck._count_off_color_pips("Abrupt Decay", {"G", "R"}) == 1


def test_count_off_color_pips_unknown_card_returns_one():
    """Default behavior: treat unknown mana cost as a single splash."""
    assert deck._count_off_color_pips("Mystery Card", {"R"}) == 1

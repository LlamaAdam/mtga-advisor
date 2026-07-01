"""Tests for mtga_local_db.py — local MTGA SQLite fallback for cards
Scryfall doesn't have arena_id mappings for yet (brand-new sets where
Scryfall data lags behind MTGA releases).

Tests focus on the pure parser helpers (`_parse_mana_cost`, `_compute_cmc`,
`_build_type_line`) — the actual SQLite lookup is exercised by
integration runs since it depends on the user's MTGA install.
"""
from __future__ import annotations

import pytest

from draft_helper import mtga_local_db


# ---------------------------------------------------------------------------
# _parse_mana_cost — MTGA internal encoding → Scryfall format
# ---------------------------------------------------------------------------

def test_parse_mana_cost_simple_generic():
    """o2 → {2}"""
    assert mtga_local_db._parse_mana_cost("o2") == "{2}"


def test_parse_mana_cost_colored_pip():
    """oW → {W}"""
    assert mtga_local_db._parse_mana_cost("oW") == "{W}"


def test_parse_mana_cost_combined():
    """o2oWoW → {2}{W}{W} (Wrath of God-style)"""
    assert mtga_local_db._parse_mana_cost("o2oWoW") == "{2}{W}{W}"


def test_parse_mana_cost_five_color():
    """oWoUoBoRoG → {W}{U}{B}{R}{G}"""
    assert mtga_local_db._parse_mana_cost("oWoUoBoRoG") == "{W}{U}{B}{R}{G}"


def test_parse_mana_cost_empty_input():
    assert mtga_local_db._parse_mana_cost("") == ""


def test_parse_mana_cost_x_pip():
    """oXoR → {X}{R} (Fireball)"""
    assert mtga_local_db._parse_mana_cost("oXoR") == "{X}{R}"


# ---------------------------------------------------------------------------
# _compute_cmc — sum the pips
# ---------------------------------------------------------------------------

def test_compute_cmc_simple_generic():
    assert mtga_local_db._compute_cmc("o2") == 2


def test_compute_cmc_combined():
    """o2oWoW = 2 + 1 + 1 = 4"""
    assert mtga_local_db._compute_cmc("o2oWoW") == 4


def test_compute_cmc_five_color_singleton():
    """oWoUoBoRoG = 5 colored pips, cmc 5"""
    assert mtga_local_db._compute_cmc("oWoUoBoRoG") == 5


def test_compute_cmc_x_counts_as_zero():
    """oXoR = X (0) + R (1) = 1"""
    assert mtga_local_db._compute_cmc("oXoR") == 1


def test_compute_cmc_empty_input():
    assert mtga_local_db._compute_cmc("") == 0


def test_compute_cmc_high_generic():
    """o9 = 9"""
    assert mtga_local_db._compute_cmc("o9") == 9


# ---------------------------------------------------------------------------
# _build_type_line — assemble Scryfall-style type line
# ---------------------------------------------------------------------------

def test_build_type_line_creature_only(monkeypatch):
    """Pure types, no subtypes or supertypes."""
    monkeypatch.setattr(mtga_local_db, "_type_map", {"6": "Creature"})
    monkeypatch.setattr(mtga_local_db, "_supertype_map", {})
    monkeypatch.setattr(mtga_local_db, "_subtype_map", {})
    line = mtga_local_db._build_type_line("6", "", "")
    assert line == "Creature"


def test_build_type_line_with_subtype(monkeypatch):
    """Creature with subtypes — joined with em-dash."""
    monkeypatch.setattr(mtga_local_db, "_type_map", {"6": "Creature"})
    monkeypatch.setattr(mtga_local_db, "_supertype_map", {})
    monkeypatch.setattr(mtga_local_db, "_subtype_map", {"1": "Angel", "2": "Warrior"})
    line = mtga_local_db._build_type_line("6", "1,2", "")
    assert line == "Creature — Angel Warrior"


def test_build_type_line_with_supertype_and_subtype(monkeypatch):
    """Legendary Creature — Angel"""
    monkeypatch.setattr(mtga_local_db, "_type_map", {"6": "Creature"})
    monkeypatch.setattr(mtga_local_db, "_supertype_map", {"1": "Legendary"})
    monkeypatch.setattr(mtga_local_db, "_subtype_map", {"1": "Angel"})
    line = mtga_local_db._build_type_line("6", "1", "1")
    assert line == "Legendary Creature — Angel"


def test_build_type_line_basic_land(monkeypatch):
    """Basic Land — Forest"""
    monkeypatch.setattr(mtga_local_db, "_type_map", {"5": "Land"})
    monkeypatch.setattr(mtga_local_db, "_supertype_map", {"3": "Basic"})
    monkeypatch.setattr(mtga_local_db, "_subtype_map", {"5": "Forest"})
    line = mtga_local_db._build_type_line("5", "5", "3")
    assert line == "Basic Land — Forest"


def test_build_type_line_no_known_subtypes(monkeypatch):
    """Subtype IDs that don't resolve fall through as raw values."""
    monkeypatch.setattr(mtga_local_db, "_type_map", {"3": "Artifact"})
    monkeypatch.setattr(mtga_local_db, "_supertype_map", {})
    monkeypatch.setattr(mtga_local_db, "_subtype_map", {})
    line = mtga_local_db._build_type_line("3", "", "")
    assert line == "Artifact"


def test_build_type_line_empty_returns_empty():
    """All inputs blank → empty string."""
    line = mtga_local_db._build_type_line("", "", "")
    assert line == ""

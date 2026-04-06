"""Tests for deck_manager.py — persistent named deck storage."""
import json
import pathlib
import pytest
import deck_manager


@pytest.fixture(autouse=True)
def isolated_decks_file(tmp_path, monkeypatch):
    """Redirect _DECKS_FILE to a temp path so tests don't touch the real file."""
    fake_path = tmp_path / "saved_decks.json"
    monkeypatch.setattr(deck_manager, "_DECKS_FILE", fake_path)
    yield fake_path


# ---------------------------------------------------------------------------
# list_decks
# ---------------------------------------------------------------------------

def test_list_decks_empty_when_no_file():
    assert deck_manager.list_decks() == []


def test_list_decks_returns_sorted_names():
    deck_manager.save_deck("Zebra Deck", {"Plains": 24, "Shock": 16})
    deck_manager.save_deck("Alpha Deck", {"Island": 24, "Cancel": 16})
    assert deck_manager.list_decks() == ["Alpha Deck", "Zebra Deck"]


# ---------------------------------------------------------------------------
# save_deck / load_deck
# ---------------------------------------------------------------------------

def test_save_and_load_deck():
    original = {"Plains": 14, "Mountain": 4, "Shock": 8, "Goblin": 14}
    deck_manager.save_deck("Boros Aggro", original)
    loaded = deck_manager.load_deck("Boros Aggro")
    assert loaded == original


def test_load_deck_returns_none_for_unknown_name():
    assert deck_manager.load_deck("Nonexistent") is None


def test_save_deck_overwrites_existing():
    deck_manager.save_deck("My Deck", {"Plains": 24})
    deck_manager.save_deck("My Deck", {"Island": 24, "Cancel": 16})
    loaded = deck_manager.load_deck("My Deck")
    assert loaded == {"Island": 24, "Cancel": 16}


def test_save_deck_ignores_empty_name():
    deck_manager.save_deck("", {"Plains": 24})
    assert deck_manager.list_decks() == []


def test_save_deck_ignores_empty_deck():
    deck_manager.save_deck("Empty", {})
    assert deck_manager.list_decks() == []


# ---------------------------------------------------------------------------
# delete_deck
# ---------------------------------------------------------------------------

def test_delete_existing_deck_returns_true():
    deck_manager.save_deck("To Delete", {"Plains": 24})
    assert deck_manager.delete_deck("To Delete") is True
    assert deck_manager.load_deck("To Delete") is None


def test_delete_nonexistent_deck_returns_false():
    assert deck_manager.delete_deck("Phantom") is False


def test_delete_leaves_other_decks_intact():
    deck_manager.save_deck("Keep Me", {"Plains": 24})
    deck_manager.save_deck("Delete Me", {"Island": 24})
    deck_manager.delete_deck("Delete Me")
    assert deck_manager.load_deck("Keep Me") == {"Plains": 24}
    assert deck_manager.list_decks() == ["Keep Me"]


# ---------------------------------------------------------------------------
# rename_deck
# ---------------------------------------------------------------------------

def test_rename_deck_succeeds():
    deck_manager.save_deck("Old Name", {"Plains": 24})
    result = deck_manager.rename_deck("Old Name", "New Name")
    assert result is True
    assert deck_manager.load_deck("New Name") == {"Plains": 24}
    assert deck_manager.load_deck("Old Name") is None


def test_rename_nonexistent_deck_returns_false():
    assert deck_manager.rename_deck("Ghost", "Real") is False


def test_rename_to_same_name_returns_false():
    deck_manager.save_deck("Same", {"Plains": 24})
    assert deck_manager.rename_deck("Same", "Same") is False


# ---------------------------------------------------------------------------
# deck_card_count
# ---------------------------------------------------------------------------

def test_deck_card_count_correct():
    deck_manager.save_deck("Counted", {"Plains": 14, "Shock": 12, "Mountain": 14})
    assert deck_manager.deck_card_count("Counted") == 40


def test_deck_card_count_zero_for_unknown():
    assert deck_manager.deck_card_count("Missing") == 0


# ---------------------------------------------------------------------------
# Persistence across calls
# ---------------------------------------------------------------------------

def test_multiple_decks_persist_independently():
    deck_manager.save_deck("Limited", {"Forest": 17, "Elf": 23})
    deck_manager.save_deck("Constructed", {"Island": 20, "Counterspell": 40})
    assert len(deck_manager.list_decks()) == 2
    assert deck_manager.deck_card_count("Limited") == 40
    assert deck_manager.deck_card_count("Constructed") == 60

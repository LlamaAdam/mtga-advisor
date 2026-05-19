import pytest
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent.parent))
import card_db
import card_helpers


@pytest.fixture(autouse=True)
def clean_card_db_caches(monkeypatch):
    """Restore module dicts after each test, AND disable the shared-store
    lookup so synthetic test data takes effect (tests set local cache
    entries directly and expect those to win)."""
    monkeypatch.setattr("card_db._resolve_shared_cards_dir", lambda: None)
    orig_mana = card_db._mana_cost.copy()
    orig_oracle = card_db._oracle.copy()
    yield
    card_db._mana_cost.clear()
    card_db._mana_cost.update(orig_mana)
    card_db._oracle.clear()
    card_db._oracle.update(orig_oracle)


def test_get_colors_red_card():
    card_db._mana_cost["lightning strike"] = "{1}{R}"
    result = card_helpers.get_colors("Lightning Strike")
    assert result == ["R"]


def test_get_colors_multicolor():
    card_db._mana_cost["dreadbore"] = "{B}{R}"
    result = card_helpers.get_colors("Dreadbore")
    assert sorted(result) == ["B", "R"]


def test_get_colors_colorless():
    card_db._mana_cost["sol ring"] = "{1}"
    result = card_helpers.get_colors("Sol Ring")
    assert result == []


def test_get_keywords_flying():
    card_db._oracle["warden of the inner sky"] = "Flying\nWard {1}"
    result = card_helpers.get_keywords("Warden of the Inner Sky")
    assert "flying" in result


def test_get_keywords_deathtouch_and_lifelink():
    card_db._oracle["vampire nighthawk"] = "Flying, Deathtouch, Lifelink"
    result = card_helpers.get_keywords("Vampire Nighthawk")
    assert "deathtouch" in result
    assert "lifelink" in result


def test_get_keywords_empty_for_unknown():
    result = card_helpers.get_keywords("Nonexistent Card XYZZY")
    assert result == []

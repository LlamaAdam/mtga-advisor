import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent.parent))
import card_db
import card_helpers


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

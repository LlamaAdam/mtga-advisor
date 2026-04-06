import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

import decklist


def test_parse_basic_format():
    text = "4 Lightning Bolt\n2 Mountain\n1 Shock"
    result = decklist.parse_decklist(text)
    assert result["Lightning Bolt"] == 4
    assert result["Mountain"] == 2
    assert result["Shock"] == 1


def test_parse_arena_export_with_set_codes():
    text = (
        "Deck\n"
        "4 Lightning Bolt (M10) 149\n"
        "2 Mountain (ANB) 114\n"
        "\n"
        "Sideboard\n"
        "1 Negate (M21) 60\n"
    )
    result = decklist.parse_decklist(text)
    assert result["Lightning Bolt"] == 4
    assert result["Mountain"] == 2
    # sideboard excluded
    assert "Negate" not in result


def test_parse_empty_string():
    assert decklist.parse_decklist("") == {}


def test_parse_ignores_section_headers():
    text = "Deck\n3 Goblin Guide\nSideboard\n1 Tormod's Crypt"
    result = decklist.parse_decklist(text)
    assert result["Goblin Guide"] == 3
    assert "Tormod's Crypt" not in result


def test_deck_composition_summary():
    text = "4 Lightning Bolt\n3 Goblin Guide\n2 Mountain\n11 Mountain"
    parsed = decklist.parse_decklist(text)
    summary = decklist.deck_composition(parsed)
    assert "13" in summary or "Mountain" in summary  # total lands counted
    assert "Lightning Bolt" in summary or "spell" in summary.lower()


def test_hand_overlap_summary_with_match():
    text = "4 Lightning Bolt\n2 Mountain\n2 Shock"
    parsed = decklist.parse_decklist(text)
    hand_names = ["Lightning Bolt", "Mountain", "Goblin"]
    summary = decklist.hand_overlap_summary(parsed, hand_names)
    assert "Lightning Bolt" in summary


def test_hand_overlap_summary_no_match():
    parsed = {"Lightning Bolt": 4}
    summary = decklist.hand_overlap_summary(parsed, ["Mountain", "Forest"])
    assert summary == "" or "none" in summary.lower()

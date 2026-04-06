import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent.parent))
import card_db


def test_get_type_line_returns_cached_value():
    card_db._type_line["lightning bolt"] = "Instant"
    result = card_db.get_type_line("Lightning Bolt")
    assert result == "Instant"


def test_get_type_line_returns_empty_for_unknown():
    result = card_db.get_type_line("Nonexistent Card XYZZY")
    assert result == ""

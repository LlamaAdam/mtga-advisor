import pytest
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent.parent))
import card_db


@pytest.fixture(autouse=True)
def clean_type_line_cache():
    """Restore _type_line to its original state after each test."""
    original = card_db._type_line.copy()
    yield
    card_db._type_line.clear()
    card_db._type_line.update(original)


def test_get_type_line_returns_cached_value():
    card_db._type_line["lightning bolt"] = "Instant"
    result = card_db.get_type_line("Lightning Bolt")
    assert result == "Instant"


def test_get_type_line_returns_empty_for_unknown():
    result = card_db.get_type_line("Nonexistent Card XYZZY")
    assert result == ""

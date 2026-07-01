"""
Wrappers around parent card_db that provide keyword and color extraction.
card_db stores oracle text and mana cost but doesn't parse them into
structured keyword lists or color lists — that's done here.
"""
import re
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
from draft_helper import card_db  # shared with the draft helper (FP-C)

_COLOR_SYMBOLS = {"W", "U", "B", "R", "G"}

# Common combat-relevant keywords. MTG has 100+ keywords; this list
# covers those most useful for advisor alerts (threats, blocks, combat).
_KEYWORDS = [
    "flying", "trample", "lifelink", "deathtouch", "haste",
    "first strike", "double strike", "menace", "vigilance",
    "reach", "indestructible", "hexproof", "ward", "flash",
    "protection", "persist", "undying", "landfall",
]


def get_colors(card_name: str) -> list[str]:
    """Return sorted list of color symbols from a card's mana cost. e.g. ['R'] for {1}{R}."""
    mc = card_db.get_mana_cost(card_name)
    # Matches simple single-letter pips only (W, U, B, R, G).
    # Hybrid ({W/U}) and Phyrexian ({W/P}) pips are not extracted.
    pips = re.findall(r'\{([A-Z])\}', mc)
    return sorted(set(p for p in pips if p in _COLOR_SYMBOLS))


def get_keywords(card_name: str) -> list[str]:
    """Return list of keyword abilities found in oracle text (lowercase)."""
    oracle = card_db.get_oracle(card_name).lower()
    if not oracle:
        return []
    return [kw for kw in _KEYWORDS if kw in oracle]

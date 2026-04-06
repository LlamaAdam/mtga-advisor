"""
Decklist parser for MTGA export format.

Supports both plain format ("4 Lightning Bolt") and Arena export format
("4 Lightning Bolt (M10) 149").  Sideboard section is excluded.

Public API:
  parse_decklist(text: str) -> dict[str, int]
  deck_composition(deck: dict[str, int]) -> str
  hand_overlap_summary(deck: dict[str, int], hand_names: list[str]) -> str
"""
from __future__ import annotations
import re
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
import card_db

# Module-level active decklist (set by main.py at startup)
active_deck: dict[str, int] = {}

_LINE_RE = re.compile(r"^(\d+)\s+([^(]+?)(?:\s+\([A-Z0-9]+\)\s+\d+)?$")


def parse_decklist(text: str) -> dict[str, int]:
    """Parse MTGA export text and return {card_name: count}.

    Stops processing when it hits a 'Sideboard' section header.
    Ignores blank lines and section headers like 'Deck'.
    """
    deck: dict[str, int] = {}
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        lower = line.lower()
        if lower == "sideboard":
            break  # everything after this is sideboard
        if lower in ("deck", "companion"):
            continue
        m = _LINE_RE.match(line)
        if m:
            count = int(m.group(1))
            name = m.group(2).strip()
            deck[name] = deck.get(name, 0) + count
    return deck


def deck_composition(deck: dict[str, int]) -> str:
    """Return a concise summary string of the deck for LLM context."""
    if not deck:
        return "No decklist provided."

    lands: list[str] = []
    spells: list[str] = []
    for name, count in sorted(deck.items(), key=lambda x: -x[1]):
        type_line = card_db.get_type_line(name).lower()
        entry = f"{count}x {name}"
        if "land" in type_line:
            lands.append(entry)
        else:
            spells.append(entry)

    parts: list[str] = []
    total_lands = sum(c for n, c in deck.items() if "land" in card_db.get_type_line(n).lower())
    total_spells = sum(deck.values()) - total_lands
    parts.append(f"Deck: {total_lands} lands, {total_spells} spells")
    if spells:
        parts.append("Key spells: " + ", ".join(spells[:8]))
    if lands:
        parts.append("Lands: " + ", ".join(lands[:6]))
    return " | ".join(parts)


def hand_overlap_summary(deck: dict[str, int], hand_names: list[str]) -> str:
    """Return a string describing which hand cards are in the decklist."""
    if not deck:
        return ""
    in_deck = [name for name in hand_names if name in deck]
    if not in_deck:
        return ""
    return "In your decklist: " + ", ".join(f"{name} ({deck[name]}x)" for name in in_deck)

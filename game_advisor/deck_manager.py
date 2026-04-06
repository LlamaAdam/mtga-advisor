"""
Persistent deck storage for the MTGA Game Advisor.

Decks are saved by name to saved_decks.json next to this file so the
user doesn't have to paste their list on every launch.

Public API
----------
list_decks()                -> list[str]
load_deck(name)             -> dict[str, int] | None
save_deck(name, deck)       -> None
delete_deck(name)           -> bool
rename_deck(old, new)       -> bool
"""
from __future__ import annotations

import json
import pathlib
from typing import Optional

_DECKS_FILE = pathlib.Path(__file__).parent / "saved_decks.json"


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _load_all() -> dict[str, dict[str, int]]:
    """Return the full saved-decks mapping from disk, or {} if none yet."""
    if not _DECKS_FILE.exists():
        return {}
    try:
        with _DECKS_FILE.open(encoding="utf-8") as f:
            data = json.load(f)
        # Validate: top-level must be a dict of {name: {card: count}}
        if not isinstance(data, dict):
            return {}
        return {k: v for k, v in data.items() if isinstance(v, dict)}
    except Exception:
        return {}


def _save_all(decks: dict[str, dict[str, int]]) -> None:
    """Persist the full deck mapping to disk."""
    try:
        with _DECKS_FILE.open("w", encoding="utf-8") as f:
            json.dump(decks, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"[deck_manager] Could not save decks: {e}")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def list_decks() -> list[str]:
    """Return saved deck names sorted alphabetically."""
    return sorted(_load_all().keys())


def load_deck(name: str) -> Optional[dict[str, int]]:
    """Return the deck dict for *name*, or None if not found."""
    return _load_all().get(name)


def save_deck(name: str, deck: dict[str, int]) -> None:
    """Persist *deck* under *name*.  Overwrites if the name already exists."""
    if not name or not deck:
        return
    decks = _load_all()
    decks[name] = deck
    _save_all(decks)


def delete_deck(name: str) -> bool:
    """Remove deck *name*.  Returns True if it existed, False otherwise."""
    decks = _load_all()
    if name not in decks:
        return False
    del decks[name]
    _save_all(decks)
    return True


def rename_deck(old_name: str, new_name: str) -> bool:
    """Rename a saved deck.  Returns True on success."""
    if not old_name or not new_name or old_name == new_name:
        return False
    decks = _load_all()
    if old_name not in decks:
        return False
    decks[new_name] = decks.pop(old_name)
    _save_all(decks)
    return True


def deck_card_count(name: str) -> int:
    """Total card count for a saved deck (0 if not found)."""
    deck = load_deck(name)
    return sum(deck.values()) if deck else 0

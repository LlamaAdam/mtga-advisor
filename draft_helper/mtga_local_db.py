"""
Reads the local MTGA SQLite card database (Raw_CardDatabase_*.mtga) to resolve
Arena card IDs (grpIds) to card names and metadata without Scryfall.

This is the ground-truth source for card data — MTGA's own database contains
every card the game knows about, including new sets that Scryfall's arena_id
mapping hasn't caught up with yet.

Usage:
    import mtga_local_db
    result = mtga_local_db.lookup(arena_id)  # returns dict or None
    mtga_local_db.preload_into_card_db()      # bulk-load all cards into card_db caches
"""

import glob
import os
import re
import sqlite3
from typing import Optional

# Common MTGA installation paths (Steam + standalone installer)
_SEARCH_PATHS = [
    r"C:\Program Files (x86)\Steam\steamapps\common\MTGA\MTGA_Data\Downloads\Raw",
    r"C:\Program Files\Steam\steamapps\common\MTGA\MTGA_Data\Downloads\Raw",
    r"C:\Program Files (x86)\Wizards of the Coast\MTGA\MTGA_Data\Downloads\Raw",
    r"C:\Program Files\Wizards of the Coast\MTGA\MTGA_Data\Downloads\Raw",
    os.path.expandvars(r"%LOCALAPPDATA%\MTGA\MTGA_Data\Downloads\Raw"),
    os.path.expandvars(r"%PROGRAMFILES(X86)%\Steam\steamapps\common\MTGA\MTGA_Data\Downloads\Raw"),
]

_db_path: Optional[str] = None   # Cached path once found
_conn: Optional[sqlite3.Connection] = None  # Cached connection

# Lookup tables (built once on first use)
_type_map: dict[str, str] = {}
_subtype_map: dict[str, str] = {}
_supertype_map: dict[str, str] = {}
_loaded: bool = False


def _find_db() -> Optional[str]:
    """Locate the Raw_CardDatabase_*.mtga file in known MTGA install locations."""
    for base in _SEARCH_PATHS:
        if not os.path.isdir(base):
            continue
        matches = glob.glob(os.path.join(base, "Raw_CardDatabase_*.mtga"))
        if matches:
            return matches[0]
    return None


def _get_connection() -> Optional[sqlite3.Connection]:
    global _db_path, _conn
    if _conn is not None:
        return _conn
    path = _find_db()
    if not path:
        return None
    try:
        # check_same_thread=False is safe here — the connection is read-only
        # and SQLite allows concurrent reads from multiple threads.
        _conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True, check_same_thread=False)
        _db_path = path
        print(f"[mtga_local_db] Connected to {os.path.basename(path)}")
        return _conn
    except Exception as e:
        print(f"[mtga_local_db] Could not open local MTGA database: {e}")
        return None


def _ensure_maps(conn: sqlite3.Connection) -> None:
    """Build CardType / SubType / SuperType enum lookup maps (once)."""
    global _type_map, _subtype_map, _supertype_map, _loaded
    if _loaded:
        return

    def _enum_map(enum_type: str) -> dict[str, str]:
        rows = conn.execute(
            "SELECT Value, LocId FROM Enums WHERE Type=?", (enum_type,)
        ).fetchall()
        result: dict[str, str] = {}
        for val, loc_id in rows:
            row = conn.execute(
                "SELECT Loc FROM Localizations_enUS WHERE LocId=?", (loc_id,)
            ).fetchone()
            if row:
                result[str(val)] = row[0]
        return result

    _type_map = _enum_map("CardType")
    _subtype_map = _enum_map("SubType")
    _supertype_map = _enum_map("SuperType")
    _loaded = True


def _build_type_line(types_str: str, subtypes_str: str, supertypes_str: str) -> str:
    supers = " ".join(
        _supertype_map.get(s, s) for s in supertypes_str.split(",") if s.strip()
    ) if supertypes_str else ""
    types = " ".join(
        _type_map.get(t, t) for t in types_str.split(",") if t.strip()
    ) if types_str else ""
    subs = " ".join(
        _subtype_map.get(s, s) for s in subtypes_str.split(",") if s.strip()
    ) if subtypes_str else ""
    line = " ".join(x for x in [supers, types] if x)
    if subs:
        line += " \u2014 " + subs
    return line


def _parse_mana_cost(raw: str) -> str:
    """Convert MTGA internal mana encoding (e.g. 'o2oW') to Scryfall format '{2}{W}'."""
    if not raw:
        return ""
    result = ""
    # Each pip is prefixed by 'o'; split on 'o' boundary (not inside parens)
    # Simple approach: split on literal 'o' then re-join skipping empty
    # Works for standard pips, hybrid (e.g. o(R/G)), phyrexian, etc.
    for part in re.split(r"(?<!\()o(?![\)])", raw):
        if not part:
            continue
        result += "{" + part + "}"
    return result


def _compute_cmc(raw: str) -> int:
    """Compute converted mana cost from MTGA mana encoding string."""
    if not raw:
        return 0
    cmc = 0
    for match in re.finditer(r"o([^o]+)", raw):
        sym = match.group(1)
        stripped = sym.strip("()")
        if stripped.isdigit():
            cmc += int(stripped)
        elif stripped.upper() == "X":
            pass  # X counts as 0
        else:
            cmc += 1  # any colored/hybrid pip = 1
    return cmc


def lookup(arena_id: int | str) -> Optional[dict]:
    """
    Look up a single card by Arena grpId.

    Returns a dict with keys: name, type_line, mana_cost, cmc, colors
    or None if the card is not in the local database.
    """
    conn = _get_connection()
    if conn is None:
        return None
    _ensure_maps(conn)

    row = conn.execute(
        "SELECT GrpId, TitleId, OldSchoolManaText, Types, Subtypes, Supertypes, Colors "
        "FROM Cards WHERE GrpId=?",
        (int(arena_id),),
    ).fetchone()
    if not row:
        return None

    grp_id, title_id, mana_raw, types_str, subtypes_str, supertypes_str, colors_str = row

    name_row = conn.execute(
        "SELECT Loc FROM Localizations_enUS WHERE LocId=?", (title_id,)
    ).fetchone()
    if not name_row:
        return None
    name = name_row[0]

    type_line = _build_type_line(types_str or "", subtypes_str or "", supertypes_str or "")
    mana_cost = _parse_mana_cost(mana_raw or "")
    cmc = _compute_cmc(mana_raw or "")

    # Colors: comma-separated ints (1=W,2=U,3=B,4=R,5=G)
    _COLOR_NUM = {"1": "W", "2": "U", "3": "B", "4": "R", "5": "G"}
    colors = [_COLOR_NUM[c] for c in (colors_str or "").split(",") if c in _COLOR_NUM]

    return {
        "name": name,
        "type_line": type_line,
        "mana_cost": mana_cost,
        "cmc": cmc,
        "colors": colors,
    }


def preload_into_card_db() -> int:
    """
    Bulk-load all primary cards from the local MTGA database into card_db caches.

    Returns the number of cards loaded, or 0 if the local database is unavailable.
    This should be called once at startup so every grpId has a name before Scryfall
    is ever needed — including cards from new sets that Scryfall hasn't mapped yet.
    """
    from . import card_db  # imported here to avoid circular imports at module level

    conn = _get_connection()
    if conn is None:
        print("[mtga_local_db] Local MTGA database not found — skipping preload.")
        return 0

    _ensure_maps(conn)

    rows = conn.execute(
        "SELECT GrpId, TitleId, OldSchoolManaText, Types, Subtypes, Supertypes, Colors "
        "FROM Cards WHERE IsPrimaryCard=1"
    ).fetchall()

    _COLOR_NUM = {"1": "W", "2": "U", "3": "B", "4": "R", "5": "G"}
    count = 0

    for grp_id, title_id, mana_raw, types_str, subtypes_str, supertypes_str, colors_str in rows:
        name_row = conn.execute(
            "SELECT Loc FROM Localizations_enUS WHERE LocId=?", (title_id,)
        ).fetchone()
        if not name_row:
            continue
        name = name_row[0]
        if not name:
            continue

        key = name.lower()
        arena_id = str(grp_id)

        # Only populate if not already in cache (don't overwrite Scryfall data)
        if arena_id not in card_db._cache:
            card_db._cache[arena_id] = name

        type_line = _build_type_line(types_str or "", subtypes_str or "", supertypes_str or "")
        mana_cost = _parse_mana_cost(mana_raw or "")
        cmc = _compute_cmc(mana_raw or "")

        if key not in card_db._type_line:
            card_db._type_line[key] = type_line
        if key not in card_db._cmc:
            card_db._cmc[key] = cmc
        if key not in card_db._mana_cost and mana_cost:
            card_db._mana_cost[key] = mana_cost

        count += 1

    if count:
        print(f"[mtga_local_db] Preloaded {count} cards from local MTGA database.")
        card_db._save_cache()

    return count


def is_available() -> bool:
    """Return True if the local MTGA database file can be found."""
    return _find_db() is not None

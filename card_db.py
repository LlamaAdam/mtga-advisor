"""
Resolves Arena card IDs (GrpIds) to card names via Scryfall.

Two strategies:
  1. preload_set(set_code) — fetch ALL cards for a set up front.
     Called when a draft starts. Fast lookups after that.
  2. resolve(ids) — individual/batch fallback via /cards/collection.

Results cached in arena_id_cache.json between sessions.
"""

import json
import os
import pathlib
import queue
import threading
import time
import requests

_CACHE_FILE = str(pathlib.Path(__file__).parent / "arena_id_cache.json")
_cache: dict[str, str] = {}          # str(arena_id) -> card name
_oracle: dict[str, str] = {}         # card_name.lower() -> oracle text
_cmc: dict[str, int] = {}            # card_name.lower() -> converted mana cost
_mana_cost: dict[str, str] = {}      # card_name.lower() -> mana cost string e.g. "{2}{B}{B}"
_type_line: dict[str, str] = {}      # card_name.lower() -> full type line e.g. "Creature — Angel Warrior"
_bad_ids: set[str] = set()           # arena IDs permanently rejected by Scryfall
_preloaded_sets: set[str] = set()
_save_lock = threading.Lock()  # Prevents concurrent writes to the cache file

# Queue of arena ID strings that couldn't be resolved — resolver thread consumes these
pending_unknowns: queue.Queue = queue.Queue()
_queued_unknowns: set[str] = set()   # Tracks what's already been enqueued this session


def _load_cache():
    global _cache, _oracle, _cmc, _mana_cost, _type_line, _bad_ids
    if os.path.exists(_CACHE_FILE):
        try:
            with open(_CACHE_FILE, encoding="utf-8") as f:
                data = json.load(f)
                _cache = data.get("cards", {})
                _oracle = data.get("oracle", {})
                _cmc = data.get("cmc", {})
                _mana_cost = data.get("mana_cost", {})
                _type_line = data.get("type_line", {})
                _bad_ids = set(data.get("bad_ids", []))
                for s in data.get("preloaded_sets", []):
                    _preloaded_sets.add(s)
        except Exception:
            _cache = {}


def _save_cache():
    with _save_lock:
        try:
            with open(_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump({
                    "cards": _cache,
                    "oracle": _oracle,
                    "cmc": _cmc,
                    "mana_cost": _mana_cost,
                    "type_line": _type_line,
                    "bad_ids": list(_bad_ids),
                    "preloaded_sets": list(_preloaded_sets),
                }, f)
        except Exception:
            pass


def get_oracle(card_name: str) -> str:
    """Return oracle text for a card name (lowercased lookup). Empty string if unknown."""
    if not _oracle:
        _load_cache()
    return _oracle.get(card_name.strip().lower(), "")


def get_cmc(card_name: str) -> int:
    """Return converted mana cost from Scryfall cache. 0 if unknown."""
    if not _cmc:
        _load_cache()
    return _cmc.get(card_name.strip().lower(), 0)


def get_subtypes(card_name: str) -> list[str]:
    """
    Return creature subtypes from the Scryfall type line.
    e.g. "Legendary Creature — Angel Warrior" → ["Angel", "Warrior"]
    Returns empty list if type line is unknown or has no subtypes.
    """
    if not _type_line:
        _load_cache()
    tl = _type_line.get(card_name.strip().lower(), "")
    if not tl or "—" not in tl:
        return []
    return tl.split("—", 1)[1].strip().split()


def get_mana_cost(card_name: str) -> str:
    """Return mana cost string e.g. '{2}{B}{B}' from Scryfall cache. Empty if unknown."""
    if not _mana_cost:
        _load_cache()
    return _mana_cost.get(card_name.strip().lower(), "")


def get_type_line(card_name: str) -> str:
    """Return full type line e.g. 'Creature — Angel Warrior'. Empty string if unknown."""
    if not _type_line:
        _load_cache()
    return _type_line.get(card_name.strip().lower(), "")


def preload_set(set_code: str):
    """
    Fetch every card in the set from Scryfall and cache arena_id -> name.
    Call this when a draft starts so ID lookups are instant during the draft.
    Skips sets already loaded this session.
    """
    if not _cache:
        _load_cache()

    key = set_code.upper()
    if key in _preloaded_sets:
        print(f"[card_db] Set {key} already preloaded ({len(_cache)} cards in cache).")
        return

    print(f"[card_db] Preloading card names for set {key} from Scryfall...")
    count = 0

    try:
        url = "https://api.scryfall.com/cards/search"
        # game:arena ensures we get MTGA-specific printings with arena_id populated
        params: dict = {"q": f"set:{set_code.lower()} game:arena", "unique": "cards"}

        while url:
            resp = requests.get(url, params=params, timeout=10)
            if resp.status_code != 200:
                print(f"[card_db] Scryfall search returned {resp.status_code} for {key}")
                break

            data = resp.json()
            for card in data.get("data", []):
                arena_id = card.get("arena_id")
                name = card.get("name", "")
                if arena_id and name:
                    _cache[str(arena_id)] = name
                    count += 1
                # Store oracle text and CMC keyed by lowercase name
                oracle = card.get("oracle_text", "")
                if name and oracle:
                    _oracle[name.lower()] = oracle
                raw_cmc = card.get("cmc")
                if name and raw_cmc is not None:
                    _cmc[name.lower()] = int(raw_cmc)
                mc = card.get("mana_cost", "")
                if name and mc:
                    _mana_cost[name.lower()] = mc
                tl = card.get("type_line", "")
                if name and tl:
                    _type_line[name.lower()] = tl

            if data.get("has_more") and data.get("next_page"):
                url = data["next_page"]
                params = {}
                time.sleep(0.1)
            else:
                break

        _preloaded_sets.add(key)
        _save_cache()
        print(f"[card_db] Preloaded {count} cards for {key}. "
              f"Total cache size: {len(_cache)}.")

    except Exception as e:
        print(f"[card_db] Failed to preload {key}: {e}")


def resolve(arena_ids: list[str | int]) -> dict[str, str]:
    """
    Resolve a list of Arena card IDs to card names.
    Returns {str(arena_id): card_name}.
    Falls back to Scryfall /cards/collection for IDs not in cache.
    """
    if not _cache:
        _load_cache()

    ids = [str(i) for i in arena_ids]
    missing = [i for i in ids if i not in _cache and i not in _bad_ids]

    if missing:
        _fetch_collection(missing)
        _save_cache()

    result = {}
    for i in ids:
        found = _cache.get(i)
        if found and not found.startswith("Unknown("):
            result[i] = found
        elif i in _bad_ids:
            # Confirmed 404 from Scryfall — new set whose arena IDs aren't mapped yet
            result[i] = f"NewCard({i})"
        else:
            result[i] = f"Unknown({i})"
            # Queue for background resolution attempt
            if i not in _queued_unknowns:
                _queued_unknowns.add(i)
                pending_unknowns.put(i)

    return result


def learn_name(arena_id: str, card_name: str):
    """
    Store a user-supplied arena_id → card_name mapping permanently.
    Also fetches oracle text / mana cost from Scryfall for the resolved name.
    """
    arena_id = str(arena_id)
    _cache[arena_id] = card_name
    _save_cache()
    print(f"[card_db] Learned: arena_id {arena_id} = '{card_name}'")

    # Best-effort: fetch card data from Scryfall to get oracle/CMC/mana cost
    try:
        resp = requests.get(
            "https://api.scryfall.com/cards/named",
            params={"exact": card_name},
            timeout=10,
        )
        if resp.status_code == 200:
            data = resp.json()
            key = card_name.lower()
            oracle = data.get("oracle_text", "")
            if oracle:
                _oracle[key] = oracle
            raw_cmc = data.get("cmc")
            if raw_cmc is not None:
                _cmc[key] = int(raw_cmc)
            mc = data.get("mana_cost", "")
            if mc:
                _mana_cost[key] = mc
            tl = data.get("type_line", "")
            if tl:
                _type_line[key] = tl
            _save_cache()
            print(f"[card_db] Fetched Scryfall data for '{card_name}': {mc}, CMC={raw_cmc}")
    except Exception as e:
        print(f"[card_db] Scryfall lookup for '{card_name}' failed: {e}")


def _try_arena_endpoint(arena_id: str) -> bool:
    """Fallback: fetch a single card via GET /cards/arena/{id}.
    Returns True and populates _cache if found.
    Returns False for transient failures (don't blacklist — retry next session).
    Only adds to _bad_ids on confirmed HTTP 404 (card truly doesn't exist).
    """
    try:
        resp = requests.get(
            f"https://api.scryfall.com/cards/arena/{arena_id}",
            timeout=10,
        )
        if resp.status_code == 404:
            _bad_ids.add(arena_id)   # confirmed non-existent
            return False
        if resp.status_code != 200:
            print(f"[card_db] arena endpoint returned {resp.status_code} for {arena_id} (will retry next session)")
            return False
        data = resp.json()
        name = data.get("name", "")
        if not name:
            return False
        _cache[arena_id] = name
        key = name.lower()
        oracle = data.get("oracle_text", "")
        if oracle:
            _oracle[key] = oracle
        raw_cmc = data.get("cmc")
        if raw_cmc is not None:
            _cmc[key] = int(raw_cmc)
        mc = data.get("mana_cost", "")
        if mc:
            _mana_cost[key] = mc
        tl = data.get("type_line", "")
        if tl:
            _type_line[key] = tl
        return True
    except Exception:
        return False


def _fetch_collection(arena_ids: list[str]):
    """
    Batch-fetch from Scryfall /cards/collection for missing IDs.
    On HTTP 400 (invalid ID in batch), splits the chunk in half and retries
    each half recursively, isolating and skipping the bad ID(s).
    """
    _fetch_collection_chunk(arena_ids, chunk_size=75)


def _fetch_collection_chunk(arena_ids: list[str], chunk_size: int):
    """Recursive helper that halves chunk size on 400 errors to isolate bad IDs."""
    for start in range(0, len(arena_ids), chunk_size):
        chunk = arena_ids[start: start + chunk_size]
        identifiers = [{"arena_id": int(i)} for i in chunk]
        try:
            resp = requests.post(
                "https://api.scryfall.com/cards/collection",
                json={"identifiers": identifiers},
                timeout=20,
            )
            if resp.status_code == 400:
                if len(chunk) == 1:
                    # Collection endpoint rejected this ID — try the direct arena endpoint.
                    # _try_arena_endpoint handles blacklisting (only on HTTP 404).
                    if not _try_arena_endpoint(chunk[0]):
                        if chunk[0] not in _bad_ids:
                            print(f"[card_db] Could not resolve arena_id {chunk[0]} this session")
                    continue
                # Split and retry each half separately with a small delay
                mid = len(chunk) // 2
                time.sleep(0.3)
                _fetch_collection_chunk(chunk[:mid], chunk_size=mid)
                time.sleep(0.3)
                _fetch_collection_chunk(chunk[mid:], chunk_size=len(chunk) - mid)
                continue
            if resp.status_code != 200:
                print(f"[card_db] Collection API returned {resp.status_code}")
                continue

            data = resp.json()
            for card in data.get("data", []):
                aid = card.get("arena_id")
                name = card.get("name", "")
                if aid and name:
                    _cache[str(aid)] = name
                oracle = card.get("oracle_text", "")
                if name and oracle:
                    _oracle[name.lower()] = oracle
                raw_cmc = card.get("cmc")
                if name and raw_cmc is not None:
                    _cmc[name.lower()] = int(raw_cmc)
                mc = card.get("mana_cost", "")
                if name and mc:
                    _mana_cost[name.lower()] = mc
                tl = card.get("type_line", "")
                if name and tl:
                    _type_line[name.lower()] = tl

            not_found = data.get("not_found", [])
            if not_found:
                print(f"[card_db] {len(not_found)} IDs not found via collection, trying arena endpoint: "
                      f"{[x.get('arena_id') for x in not_found[:5]]}")
                # Collection endpoint misses many MTGA-specific printings.
                # Fall through immediately to the direct /cards/arena/{id} endpoint
                # rather than waiting for the background resolver, so the calling
                # thread gets correct card names before firing on_state_change.
                for identifier in not_found:
                    arena_id_int = identifier.get("arena_id")
                    if arena_id_int is not None:
                        _try_arena_endpoint(str(arena_id_int))

            time.sleep(0.1)

        except Exception as e:
            print(f"[card_db] Collection fetch failed: {e}")


def name(arena_id: str | int) -> str:
    """Resolve a single Arena ID to a card name."""
    return resolve([arena_id])[str(arena_id)]


def rehabilitate(arena_ids: list[str | int]) -> None:
    """Remove IDs from _bad_ids so they will be retried on the next resolve().

    Call this whenever MTGA's own log contains a grpId — that is proof the
    card exists in the game, even if a previous Scryfall request failed or
    was incorrectly blacklisted by an old code path.  Saves the updated
    cache so the rehabilitation persists across restarts.
    """
    if not _bad_ids:
        return
    ids = {str(i) for i in arena_ids}
    removed = _bad_ids & ids
    if removed:
        _bad_ids.difference_update(removed)  # mutate in-place — no global declaration needed
        _save_cache()
        print(f"[card_db] Rehabilitated {len(removed)} previously-blacklisted IDs: "
              f"{sorted(removed)[:10]}")


def start_background_resolver() -> None:
    """Start a daemon thread that retries unresolved arena IDs via the direct endpoint.

    Consumes items from the pending_unknowns queue.  Rate-limited to one request
    per 0.5 s so we stay well under Scryfall's rate limit.
    """
    def _resolver_loop():
        while True:
            try:
                arena_id = pending_unknowns.get(timeout=5)
            except Exception:
                continue  # queue.Empty or other — keep looping
            if arena_id in _cache or arena_id in _bad_ids:
                continue
            if _try_arena_endpoint(arena_id):
                print(f"[card_db] Background resolver found: {arena_id} = '{_cache.get(arena_id)}'")
                _save_cache()
            time.sleep(0.5)

    t = threading.Thread(target=_resolver_loop, daemon=True, name="card_db-resolver")
    t.start()

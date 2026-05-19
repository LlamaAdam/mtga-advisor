"""Top-level tests for card_db.py — the legacy draft-helper card database.

This file fills a gap noted in FUTURE_PLANS.md FP-D: the legacy
draft-helper code at the project root has no test coverage. Tests focus
on pure-logic functions (no network) that are easy to validate.

The shared-store integration is already tested under
`game_advisor/tests/test_card_db_shared_store.py` (16 tests). This file
covers the rest of `card_db.py`.
"""
from __future__ import annotations

import json
import pathlib
import pytest

import card_db


_REAL_SAVE_CACHE = card_db._save_cache  # Captured before any test stubs it.


@pytest.fixture(autouse=True)
def isolate_card_db(monkeypatch, request):
    """Isolate each test from on-disk cache and shared store.

    Each test gets:
    - Empty in-memory caches (snapshot + restore).
    - Shared-store lookup disabled (so synthetic data takes effect).
    - `_save_cache` and `_load_cache` no-ops (no real file I/O), unless
      the test is marked ``real_save`` (used to exercise the atomic
      write path itself).
    """
    monkeypatch.setattr("card_db._resolve_shared_cards_dir", lambda: None)
    if "real_save" not in request.keywords:
        monkeypatch.setattr("card_db._save_cache", lambda: None)
    monkeypatch.setattr("card_db._load_cache", lambda: None)
    orig_cache = card_db._cache.copy()
    orig_oracle = card_db._oracle.copy()
    orig_cmc = card_db._cmc.copy()
    orig_mana = card_db._mana_cost.copy()
    orig_type_line = card_db._type_line.copy()
    orig_bad_ids = card_db._bad_ids.copy()
    card_db._cache.clear()
    card_db._oracle.clear()
    card_db._cmc.clear()
    card_db._mana_cost.clear()
    card_db._type_line.clear()
    card_db._bad_ids.clear()
    yield
    card_db._cache.clear()
    card_db._cache.update(orig_cache)
    card_db._oracle.clear()
    card_db._oracle.update(orig_oracle)
    card_db._cmc.clear()
    card_db._cmc.update(orig_cmc)
    card_db._mana_cost.clear()
    card_db._mana_cost.update(orig_mana)
    card_db._type_line.clear()
    card_db._type_line.update(orig_type_line)
    card_db._bad_ids.clear()
    card_db._bad_ids.update(orig_bad_ids)


# ---------------------------------------------------------------------------
# get_oracle / get_cmc / get_type_line / get_mana_cost (local-cache path)
# ---------------------------------------------------------------------------

def test_get_oracle_returns_local_value_when_shared_disabled():
    card_db._oracle["lightning bolt"] = "Deals 3 damage to any target."
    assert card_db.get_oracle("Lightning Bolt") == "Deals 3 damage to any target."


def test_get_oracle_strips_whitespace_and_lowercases():
    card_db._oracle["sol ring"] = "Tap: add CC."
    assert card_db.get_oracle("  Sol Ring  ") == "Tap: add CC."
    assert card_db.get_oracle("SOL RING") == "Tap: add CC."


def test_get_oracle_returns_empty_string_for_unknown():
    assert card_db.get_oracle("Definitely Not A Real Card") == ""


def test_get_cmc_returns_zero_for_unknown():
    assert card_db.get_cmc("Unknown Card") == 0


def test_get_cmc_returns_local_value():
    card_db._cmc["sol ring"] = 1
    assert card_db.get_cmc("Sol Ring") == 1


def test_get_mana_cost_returns_empty_for_unknown():
    assert card_db.get_mana_cost("Unknown Card") == ""


def test_get_mana_cost_returns_local_value():
    card_db._mana_cost["counterspell"] = "{U}{U}"
    assert card_db.get_mana_cost("Counterspell") == "{U}{U}"


def test_get_type_line_returns_local_value():
    card_db._type_line["sol ring"] = "Artifact"
    assert card_db.get_type_line("Sol Ring") == "Artifact"


def test_get_type_line_returns_empty_for_unknown():
    assert card_db.get_type_line("Unknown") == ""


# ---------------------------------------------------------------------------
# get_subtypes — parses the type line
# ---------------------------------------------------------------------------

def test_get_subtypes_parses_creature_subtypes():
    card_db._type_line["serra angel"] = "Creature — Angel"
    assert card_db.get_subtypes("Serra Angel") == ["Angel"]


def test_get_subtypes_handles_multiple_subtypes():
    card_db._type_line["atraxa"] = "Legendary Creature — Phyrexian Angel Horror"
    assert card_db.get_subtypes("Atraxa") == ["Phyrexian", "Angel", "Horror"]


def test_get_subtypes_returns_empty_for_no_subtype():
    card_db._type_line["sol ring"] = "Artifact"
    assert card_db.get_subtypes("Sol Ring") == []


def test_get_subtypes_returns_empty_for_unknown():
    assert card_db.get_subtypes("Definitely Unknown") == []


def test_get_subtypes_handles_basic_land():
    card_db._type_line["forest"] = "Basic Land — Forest"
    assert card_db.get_subtypes("Forest") == ["Forest"]


# ---------------------------------------------------------------------------
# rehabilitate — un-blacklists arena IDs
# ---------------------------------------------------------------------------

def test_rehabilitate_removes_bad_ids():
    card_db._bad_ids.update({"100", "200", "300"})
    card_db.rehabilitate(["100", "300"])
    assert card_db._bad_ids == {"200"}


def test_rehabilitate_handles_int_ids():
    card_db._bad_ids.update({"100"})
    card_db.rehabilitate([100])
    assert card_db._bad_ids == set()


def test_rehabilitate_no_op_when_no_bad_ids():
    """rehabilitate should bail early when _bad_ids is empty."""
    card_db.rehabilitate(["100", "200"])
    assert card_db._bad_ids == set()


def test_rehabilitate_ignores_ids_not_in_bad_set():
    card_db._bad_ids.update({"100"})
    card_db.rehabilitate(["999"])
    # 100 still bad, 999 wasn't in the set so it's a no-op
    assert card_db._bad_ids == {"100"}


# ---------------------------------------------------------------------------
# name() — single-ID resolution wrapper
# ---------------------------------------------------------------------------

def test_name_returns_cached_value(monkeypatch):
    """name() returns whatever resolve() puts at the requested key."""
    card_db._cache["123"] = "Lightning Bolt"
    monkeypatch.setattr(
        "card_db.resolve", lambda ids: {str(ids[0]): card_db._cache[str(ids[0])]},
    )
    assert card_db.name("123") == "Lightning Bolt"
    assert card_db.name(123) == "Lightning Bolt"  # int input also works


# ---------------------------------------------------------------------------
# preload_set — short-circuits on already-loaded sets
# ---------------------------------------------------------------------------

def test_preload_set_skips_already_loaded(monkeypatch, capsys):
    """If the set was already preloaded this session, don't re-fetch."""
    card_db._preloaded_sets.add("DSK")
    # Make any HTTP call fail loudly so we know we DIDN'T hit the network.
    def fail(*args, **kwargs):
        raise AssertionError(f"Should not have called HTTP: {args}")
    monkeypatch.setattr("card_db.requests.get", fail)
    card_db.preload_set("DSK")
    captured = capsys.readouterr()
    assert "already preloaded" in captured.out


def test_preload_set_uppercases_set_code(monkeypatch):
    """Lowercase / mixed-case input should normalize to uppercase."""
    card_db._preloaded_sets.add("DSK")
    def fail(*args, **kwargs):
        raise AssertionError("Should not call HTTP for already-loaded set.")
    monkeypatch.setattr("card_db.requests.get", fail)
    # All three should be a no-op since DSK is in _preloaded_sets.
    card_db.preload_set("dsk")
    card_db.preload_set("Dsk")
    card_db.preload_set("DSK")


# ---------------------------------------------------------------------------
# learn_name — records a user-supplied mapping
# ---------------------------------------------------------------------------

def test_learn_name_records_mapping(monkeypatch):
    """learn_name should write the arena_id → name mapping into _cache.
    HTTP fetch failure shouldn't lose the mapping."""
    def fake_get(*args, **kwargs):
        class FakeResp:
            status_code = 500  # force the Scryfall path to no-op
        return FakeResp()
    monkeypatch.setattr("card_db.requests.get", fake_get)
    card_db.learn_name("999", "My Custom Card")
    assert card_db._cache["999"] == "My Custom Card"


def test_learn_name_normalizes_int_id_to_string(monkeypatch):
    monkeypatch.setattr(
        "card_db.requests.get",
        lambda *a, **k: type("R", (), {"status_code": 500})(),
    )
    card_db.learn_name(12345, "Foo")
    assert card_db._cache["12345"] == "Foo"


# ---------------------------------------------------------------------------
# _save_cache atomic-rename behavior (FP-E defensive fix)
# ---------------------------------------------------------------------------

@pytest.mark.real_save
def test_save_cache_uses_atomic_rename(tmp_path, monkeypatch):
    """Save should write to .tmp then os.replace into the canonical
    path. A crash mid-write must not leave the canonical file
    truncated."""
    cache_file = tmp_path / "arena_id_cache.json"
    monkeypatch.setattr("card_db._CACHE_FILE", str(cache_file))
    card_db._cache["1"] = "Lightning Bolt"
    card_db._save_cache()

    assert cache_file.exists()
    assert not (tmp_path / "arena_id_cache.json.tmp").exists()
    body = json.loads(cache_file.read_text(encoding="utf-8"))
    assert body["cards"]["1"] == "Lightning Bolt"


@pytest.mark.real_save
def test_save_cache_failure_is_swallowed(tmp_path, monkeypatch):
    """Cache writes are best-effort; an OS error from a missing
    parent dir must not propagate."""
    monkeypatch.setattr(
        "card_db._CACHE_FILE",
        str(tmp_path / "nonexistent_dir" / "cache.json"),
    )
    # Should not raise — parent dir doesn't exist.
    card_db._save_cache()

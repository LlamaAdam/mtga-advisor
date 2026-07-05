from __future__ import annotations

import pytest

from draft_helper import ratings as ratings_mod
from draft_helper import deck as deck_mod
from draft_helper.benchmark.models import PickEvent, DraftRecord
from draft_helper.benchmark import runner


def test_run_benchmark_loads_ratings_then_scores(monkeypatch):
    calls = {"loaded": False}

    def fake_load(set_code, draft_format):
        calls["loaded"] = (set_code, draft_format)

    monkeypatch.setattr(runner, "_ensure_ratings_loaded", fake_load)
    table = {"Bomb": 62.0, "Filler": 51.0}
    monkeypatch.setattr(ratings_mod, "is_loaded", lambda: True)
    monkeypatch.setattr(ratings_mod, "get_winrate",
                        lambda name, color_filter="All Decks": table.get(name))
    monkeypatch.setattr(deck_mod.DeckTracker, "adjusted_rating",
                        lambda self, name: (table.get(name), "?"))

    rec = DraftRecord(set_code="MSH", source="t", picks=(
        PickEvent(1, 1, ("Filler", "Bomb"), "Bomb"),
    ))
    report = runner.run_benchmark(rec, draft_format="PremierDraft")
    assert calls["loaded"] == ("MSH", "PremierDraft")
    assert report.agreement_rate == 1.0


def test_ensure_ratings_reloads_when_a_different_set_is_loaded(monkeypatch):
    """Benchmarking set B after set A in one process must reload ratings —
    is_loaded() alone can't tell WHICH set is in the module."""
    loads: list[tuple[str, str]] = []
    monkeypatch.setattr(runner.api, "load_cache",
                        lambda s, f: (loads.append((s, f)) or {"some card": {}}))
    # Simulate: module already holds ratings, but for set "AAA".
    monkeypatch.setattr(ratings_mod, "is_loaded", lambda: True)

    real_load = ratings_mod.load
    monkeypatch.setattr(ratings_mod, "load",
                        lambda data, set_key=None: real_load(data, set_key=set_key))
    ratings_mod.load({"old card": {}}, set_key="AAA_PremierDraft")
    try:
        runner._ensure_ratings_loaded("BBB", "PremierDraft")
        assert loads == [("BBB", "PremierDraft")]        # cache consulted for BBB
        assert ratings_mod.loaded_key() == "BBB_PremierDraft"
    finally:
        ratings_mod.load({}, set_key=None)               # reset module state


def test_ensure_ratings_skips_reload_when_same_set_loaded(monkeypatch):
    loads: list[tuple[str, str]] = []
    monkeypatch.setattr(runner.api, "load_cache",
                        lambda s, f: (loads.append((s, f)) or {"some card": {}}))
    ratings_mod.load({"a card": {}}, set_key="MSH_PremierDraft")
    try:
        runner._ensure_ratings_loaded("MSH", "PremierDraft")
        assert loads == []                               # no reload needed
    finally:
        ratings_mod.load({}, set_key=None)

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

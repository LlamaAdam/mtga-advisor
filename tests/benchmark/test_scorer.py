from __future__ import annotations

import pytest

from draft_helper import deck as deck_mod
from draft_helper import ratings as ratings_mod
from draft_helper.benchmark.models import PickEvent, DraftRecord
from draft_helper.benchmark import scorer


@pytest.fixture(autouse=True)
def stub_engine(monkeypatch):
    """Control the pick engine deterministically: each card's adjusted rating
    and raw win rate come from a fixed table, so tests exercise the scorer's
    ranking/agreement/mirroring logic, not the rating internals."""
    table = {"Bomb": 62.0, "Good": 57.0, "Filler": 51.0, "Splash": 55.0}
    monkeypatch.setattr(ratings_mod, "is_loaded", lambda: True)
    monkeypatch.setattr(ratings_mod, "get_winrate",
                        lambda name, color_filter="All Decks": table.get(name))
    monkeypatch.setattr(deck_mod.DeckTracker, "adjusted_rating",
                        lambda self, name: (table.get(name), "?"))
    return table


def _one_pick(pack, taken, pack_no=1, pick_no=1):
    return DraftRecord(
        set_code="MSH", source="t",
        picks=(PickEvent(pack_number=pack_no, pick_number=pick_no,
                         pack_cards=tuple(pack), human_pick=taken),),
    )


def test_tool_pick_is_highest_rated_card():
    report = scorer.score_draft(_one_pick(["Filler", "Bomb", "Good"], "Bomb"))
    r = report.results[0]
    assert r.tool_pick == "Bomb"
    assert r.agree is True
    assert r.human_rank == 1
    assert r.scored is True


def test_human_rank_reflects_ordering_on_disagreement():
    # Human took Filler (worst of three) -> tool picks Bomb, human ranks 3rd.
    report = scorer.score_draft(_one_pick(["Filler", "Bomb", "Good"], "Filler"))
    r = report.results[0]
    assert r.tool_pick == "Bomb"
    assert r.agree is False
    assert r.human_rank == 3


def test_pick_skipped_when_human_pick_not_in_pack():
    report = scorer.score_draft(_one_pick(["Bomb", "Good"], "Missing"))
    r = report.results[0]
    assert r.scored is False


def test_pack_opener_uses_raw_winrate(monkeypatch):
    # For pick 1 of pack 2+, ranking must use get_winrate, not adjusted_rating.
    # Make adjusted_rating rank differently so we can tell which was used.
    monkeypatch.setattr(deck_mod.DeckTracker, "adjusted_rating",
                        lambda self, name: (0.0, "?"))  # would rank all equal
    report = scorer.score_draft(
        _one_pick(["Filler", "Bomb"], "Bomb", pack_no=2, pick_no=1))
    assert report.results[0].tool_pick == "Bomb"  # from raw win rate


def test_deck_state_mirrors_human_prior_picks(monkeypatch):
    # Two picks: verify the tracker records the human's first pick before
    # scoring the second (the fairness rule). Assert via a spy on add_pick.
    seen: list[str] = []
    original = deck_mod.DeckTracker.add_pick

    def spy(self, name):
        seen.append(name)
        return original(self, name)

    monkeypatch.setattr(deck_mod.DeckTracker, "add_pick", spy)
    rec = DraftRecord(set_code="MSH", source="t", picks=(
        PickEvent(1, 1, ("Bomb", "Good"), "Good"),
        PickEvent(1, 2, ("Filler", "Splash"), "Splash"),
    ))
    scorer.score_draft(rec)
    # The human's first pick ("Good") must have been added before pick 2.
    assert seen == ["Good", "Splash"]

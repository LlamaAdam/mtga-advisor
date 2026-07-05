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


def test_mid_draft_skip_excluded_from_metrics_but_still_mirrored(monkeypatch):
    # A skipped pick (human pick not in the recognized pack) must be excluded
    # from agreement_rate, yet the human's card must still enter the tracker
    # so every later pick is judged from the human's true deck.
    seen: list[str] = []
    original = deck_mod.DeckTracker.add_pick

    def spy(self, name):
        seen.append(name)
        return original(self, name)

    monkeypatch.setattr(deck_mod.DeckTracker, "add_pick", spy)
    rec = DraftRecord(set_code="MSH", source="t", picks=(
        PickEvent(1, 1, ("Bomb", "Good"), "Bomb"),          # agree
        PickEvent(1, 2, ("Filler", "Good"), "Mystery Card"), # skip: not in pack
        PickEvent(1, 3, ("Filler", "Splash"), "Filler"),     # disagree
    ))
    report = scorer.score_draft(rec)

    assert seen == ["Bomb", "Mystery Card", "Filler"]  # mirroring advanced
    assert report.scored_count == 2
    assert report.skipped_count == 1
    assert report.agreement_rate == 0.5  # 1 agree of 2 scored — skip excluded
    assert report.results[1].scored is False


def test_tied_ratings_rank_deterministically_in_pack_order(stub_engine):
    # Stable sort: equal ratings keep pack order, so the tool pick and the
    # human rank are deterministic run-to-run.
    stub_engine["TieB"] = 55.0
    stub_engine["TieA"] = 55.0

    report = scorer.score_draft(_one_pick(["TieB", "TieA"], "TieA"))
    r = report.results[0]
    assert r.tool_pick == "TieB"   # first in pack order wins the tie
    assert r.human_rank == 2       # the other tied card ranks second
    assert r.agree is False

    # Same tie, human takes the pack-order leader -> agreement.
    report2 = scorer.score_draft(_one_pick(["TieB", "TieA"], "TieB"))
    assert report2.results[0].agree is True


def test_fully_unrated_pack_is_skipped_not_scored():
    # No card in the pack has any rating -> the tool has no opinion.
    # Production best_pick returns None here; the scorer must not fabricate
    # a tool_pick from pack order and register a spurious agreement.
    report = scorer.score_draft(_one_pick(["Mystery A", "Mystery B"], "Mystery A"))
    r = report.results[0]
    assert r.scored is False
    assert r.tool_pick == ""
    assert report.agreement_rate == 0.0


def test_partially_unrated_pack_ranks_rated_cards_first(stub_engine):
    # One rated card among unknowns: it must win, and the unknown human
    # pick still gets a real (last) rank.
    report = scorer.score_draft(_one_pick(["Mystery A", "Good"], "Mystery A"))
    r = report.results[0]
    assert r.scored is True
    assert r.tool_pick == "Good"
    assert r.human_rank == 2


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

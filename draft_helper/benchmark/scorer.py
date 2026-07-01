"""Score a recorded draft against the tool's pick engine.

Pure: drives the existing DeckTracker and assumes ratings are already loaded
for the record's set. No network, no video.
"""
from __future__ import annotations

from draft_helper import ratings
from draft_helper.deck import DeckTracker
from .models import DraftRecord, PickResult, BenchmarkReport

_MISS = -999.0


def _rank_pack(tracker: DeckTracker, pack_cards: tuple[str, ...],
               is_pack_opener: bool) -> list[str]:
    """Return pack card names ordered best-first, mirroring best_pick's
    criterion: raw 'All Decks' win rate for a pack-opener, otherwise the
    tracker's colour/synergy-adjusted rating."""
    scored: list[tuple[str, float]] = []
    for name in pack_cards:
        if is_pack_opener:
            wr = ratings.get_winrate(name, "All Decks")
        else:
            wr, _ = tracker.adjusted_rating(name)
        scored.append((name, wr if wr is not None else _MISS))
    scored.sort(key=lambda pair: pair[1], reverse=True)
    return [name for name, _ in scored]


def score_draft(record: DraftRecord) -> BenchmarkReport:
    """Replay the pick engine over a recorded draft and score agreement."""
    tracker = DeckTracker()
    tracker.clear()
    results: list[PickResult] = []

    for pe in record.picks:
        is_opener = pe.pick_number == 1 and pe.pack_number >= 2
        ordering = _rank_pack(tracker, pe.pack_cards, is_opener)

        if pe.human_pick not in ordering:
            # Recognition gave a pick that isn't in the recognized pack — skip
            # rather than fabricate a rank, and let coverage reflect it.
            results.append(PickResult(
                pack_number=pe.pack_number, pick_number=pe.pick_number,
                human_pick=pe.human_pick, tool_pick=ordering[0] if ordering else "",
                agree=False, human_rank=0, pack_size=len(pe.pack_cards),
                scored=False,
            ))
        else:
            tool_pick = ordering[0]
            results.append(PickResult(
                pack_number=pe.pack_number, pick_number=pe.pick_number,
                human_pick=pe.human_pick, tool_pick=tool_pick,
                agree=(tool_pick == pe.human_pick),
                human_rank=ordering.index(pe.human_pick) + 1,
                pack_size=len(pe.pack_cards), scored=True,
            ))

        # Fairness rule: mirror the human's deck for the next pick.
        tracker.add_pick(pe.human_pick)

    return BenchmarkReport(set_code=record.set_code, source=record.source,
                           results=tuple(results))

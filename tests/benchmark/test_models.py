from __future__ import annotations

from draft_helper.benchmark.models import (
    PickEvent, DraftRecord, PickResult, BenchmarkReport,
)


def _result(agree: bool, rank: int, scored: bool = True) -> PickResult:
    return PickResult(
        pack_number=1, pick_number=1, human_pick="X", tool_pick="Y",
        agree=agree, human_rank=rank, pack_size=15, scored=scored,
    )


def test_pick_event_holds_pack_and_pick():
    pe = PickEvent(pack_number=2, pick_number=3,
                   pack_cards=("A", "B"), human_pick="A")
    assert pe.pack_number == 2
    assert pe.pick_number == 3
    assert pe.pack_cards == ("A", "B")
    assert pe.human_pick == "A"
    assert pe.confidence == 1.0  # default


def test_draft_record_holds_picks():
    rec = DraftRecord(set_code="MSH", source="v.mp4", picks=())
    assert rec.set_code == "MSH"
    assert rec.picks == ()


def test_agreement_rate_counts_only_scored_picks():
    report = BenchmarkReport(
        set_code="MSH", source="v.mp4",
        results=(_result(True, 1), _result(False, 4),
                 _result(True, 1), _result(False, 2, scored=False)),
    )
    # 3 scored (2 agree), 1 skipped
    assert report.scored_count == 3
    assert report.skipped_count == 1
    assert report.agreement_rate == 2 / 3


def test_mean_human_rank_over_scored_only():
    report = BenchmarkReport(
        set_code="MSH", source="v.mp4",
        results=(_result(True, 1), _result(False, 3)),
    )
    assert report.mean_human_rank == 2.0


def test_metrics_safe_when_no_scored_picks():
    report = BenchmarkReport(set_code="MSH", source="v.mp4",
                             results=(_result(True, 1, scored=False),))
    assert report.scored_count == 0
    assert report.agreement_rate == 0.0
    assert report.mean_human_rank == 0.0

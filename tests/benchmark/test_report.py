from __future__ import annotations

import json

from draft_helper.benchmark.models import PickResult, BenchmarkReport
from draft_helper.benchmark import report as report_mod


def _report() -> BenchmarkReport:
    return BenchmarkReport(
        set_code="MSH", source="draft.mp4",
        results=(
            PickResult(1, 1, "Bomb", "Bomb", True, 1, 15, True),
            PickResult(1, 2, "Filler", "Good", False, 4, 14, True),
            PickResult(1, 3, "Missing", "Good", False, 0, 13, False),
        ),
    )


def test_markdown_shows_headline_metrics_and_coverage():
    md = report_mod.render_markdown(_report())
    assert "MSH" in md
    assert "50%" in md            # agreement rate: 1 of 2 scored
    assert "2/3" in md            # coverage: scored 2 of 3
    assert "Bomb" in md and "Good" in md


def test_markdown_lists_biggest_disagreements():
    md = report_mod.render_markdown(_report())
    # The disagreement (human took Filler, tool took Good) must appear.
    assert "Filler" in md
    assert "Disagreement" in md or "disagreement" in md


def test_zero_scored_picks_render_without_dividing_by_zero():
    report = BenchmarkReport(
        set_code="MSH", source="bad-recognition.mp4",
        results=(
            PickResult(1, 1, "Ghost A", "Bomb", False, 0, 15, False),
            PickResult(1, 2, "Ghost B", "Good", False, 0, 14, False),
        ),
    )
    assert report.agreement_rate == 0.0
    assert report.mean_human_rank == 0.0
    md = report_mod.render_markdown(report)
    assert "0/2" in md                       # coverage line reflects reality
    assert "Biggest disagreements" not in md  # skips are not disagreements
    data = json.loads(report_mod.render_json(report))
    assert data["scored_count"] == 0
    assert data["skipped_count"] == 2


def test_json_roundtrips_metrics():
    data = json.loads(report_mod.render_json(_report()))
    assert data["set_code"] == "MSH"
    assert data["agreement_rate"] == 0.5
    assert data["scored_count"] == 2
    assert data["skipped_count"] == 1
    assert len(data["results"]) == 3

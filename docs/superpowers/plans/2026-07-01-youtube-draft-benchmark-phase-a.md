# YouTube Draft Benchmark — Phase A Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the benchmark engine that scores the draft helper's pick recommendations against a human draft, reporting agreement rate and how the human's pick ranked in the tool's ordering.

**Architecture:** A new `draft_helper/benchmark/` package with four focused modules: `models` (data contracts), `scorer` (replays the existing pick engine against the human's prior picks), `report` (markdown + JSON rendering), and `runner` (loads ratings, then scores). The scorer is pure — it drives the existing `DeckTracker` and assumes ratings are already loaded — so it is fully unit-testable with no network or video. This is Phase A of the design in `docs/superpowers/specs/2026-07-01-youtube-draft-benchmark-design.md`; the video-ingestion phases (B1–B3) get their own plans after a recognition spike.

**Tech Stack:** Python 3.14, pytest, existing `draft_helper` modules (`deck.DeckTracker`, `ratings`, `api`). No new dependencies in Phase A.

---

## File Structure

- Create: `draft_helper/benchmark/__init__.py` — package marker + public re-exports.
- Create: `draft_helper/benchmark/models.py` — `PickEvent`, `DraftRecord`, `PickResult`, `BenchmarkReport` dataclasses.
- Create: `draft_helper/benchmark/scorer.py` — `score_draft(record)` and the `_rank_pack` helper.
- Create: `draft_helper/benchmark/report.py` — `render_markdown(report)`, `render_json(report)`.
- Create: `draft_helper/benchmark/runner.py` — `run_benchmark(record, draft_format)` (loads ratings, calls `score_draft`).
- Create: `tests/benchmark/__init__.py` — empty test package marker.
- Create: `tests/benchmark/test_models.py`
- Create: `tests/benchmark/test_scorer.py`
- Create: `tests/benchmark/test_report.py`
- Create: `tests/benchmark/test_runner.py`

---

## Task 1: Data models

**Files:**
- Create: `draft_helper/benchmark/__init__.py`
- Create: `draft_helper/benchmark/models.py`
- Create: `tests/benchmark/__init__.py`
- Test: `tests/benchmark/test_models.py`

- [ ] **Step 1: Create the empty package markers**

Create `draft_helper/benchmark/__init__.py`:

```python
"""Benchmark the draft helper's picks against recorded human drafts."""
from .models import PickEvent, DraftRecord, PickResult, BenchmarkReport

__all__ = ["PickEvent", "DraftRecord", "PickResult", "BenchmarkReport"]
```

Create `tests/benchmark/__init__.py` as an empty file (no content).

- [ ] **Step 2: Write the failing test for the models + report metrics**

Create `tests/benchmark/test_models.py`:

```python
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
```

- [ ] **Step 3: Run the test to verify it fails**

Run: `python -m pytest tests/benchmark/test_models.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'draft_helper.benchmark.models'`

- [ ] **Step 4: Implement the models**

Create `draft_helper/benchmark/models.py`:

```python
"""Data contracts for the draft benchmark.

DraftRecord / PickEvent are the seam the video pipeline (Project B) produces
and the scorer (Project A) consumes. PickResult / BenchmarkReport are the
scorer's output.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class PickEvent:
    """One pick in a recorded draft: the pack shown and the card taken."""
    pack_number: int
    pick_number: int
    pack_cards: tuple[str, ...]
    human_pick: str
    confidence: float = 1.0  # recognition confidence; 1.0 when hand-verified


@dataclass(frozen=True)
class DraftRecord:
    """A full recorded draft, in pick order."""
    set_code: str
    source: str
    picks: tuple[PickEvent, ...]


@dataclass(frozen=True)
class PickResult:
    """The scorer's verdict for a single pick."""
    pack_number: int
    pick_number: int
    human_pick: str
    tool_pick: str
    agree: bool
    human_rank: int   # 1-based rank of the human's pick in the tool's ordering
    pack_size: int
    scored: bool      # False when the pick was skipped (see scorer)


@dataclass(frozen=True)
class BenchmarkReport:
    """Aggregate result over a whole draft."""
    set_code: str
    source: str
    results: tuple[PickResult, ...] = field(default_factory=tuple)

    @property
    def _scored(self) -> list[PickResult]:
        return [r for r in self.results if r.scored]

    @property
    def scored_count(self) -> int:
        return len(self._scored)

    @property
    def skipped_count(self) -> int:
        return len(self.results) - self.scored_count

    @property
    def agreement_rate(self) -> float:
        scored = self._scored
        if not scored:
            return 0.0
        return sum(1 for r in scored if r.agree) / len(scored)

    @property
    def mean_human_rank(self) -> float:
        scored = self._scored
        if not scored:
            return 0.0
        return sum(r.human_rank for r in scored) / len(scored)
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `python -m pytest tests/benchmark/test_models.py -q`
Expected: PASS (5 passed)

- [ ] **Step 6: Commit**

```bash
git add draft_helper/benchmark/__init__.py draft_helper/benchmark/models.py tests/benchmark/__init__.py tests/benchmark/test_models.py
git commit -m "feat: benchmark data models (DraftRecord seam + report metrics)"
```

---

## Task 2: Scorer

**Files:**
- Create: `draft_helper/benchmark/scorer.py`
- Test: `tests/benchmark/test_scorer.py`

**Behavior:** For each pick in order, score the pack against a `DeckTracker`
holding the human's *prior* picks (the fairness rule), then add the human's
pick so the next pick sees the same deck. Rank the pack by `adjusted_rating`
(or raw "All Decks" win rate for a pack-opener: pick 1 of packs 2+). The tool's
pick is the top of that ranking; the human's rank is its position. Skip a pick
(`scored=False`) when the human's pick is not among the recognized pack cards.

- [ ] **Step 1: Write the failing test**

Create `tests/benchmark/test_scorer.py`:

```python
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
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python -m pytest tests/benchmark/test_scorer.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'draft_helper.benchmark.scorer'`

- [ ] **Step 3: Implement the scorer**

Create `draft_helper/benchmark/scorer.py`:

```python
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
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `python -m pytest tests/benchmark/test_scorer.py -q`
Expected: PASS (5 passed)

- [ ] **Step 5: Commit**

```bash
git add draft_helper/benchmark/scorer.py tests/benchmark/test_scorer.py
git commit -m "feat: benchmark scorer (deck-mirroring, tool pick, human rank)"
```

---

## Task 3: Report rendering

**Files:**
- Create: `draft_helper/benchmark/report.py`
- Test: `tests/benchmark/test_report.py`

- [ ] **Step 1: Write the failing test**

Create `tests/benchmark/test_report.py`:

```python
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


def test_json_roundtrips_metrics():
    data = json.loads(report_mod.render_json(_report()))
    assert data["set_code"] == "MSH"
    assert data["agreement_rate"] == 0.5
    assert data["scored_count"] == 2
    assert data["skipped_count"] == 1
    assert len(data["results"]) == 3
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python -m pytest tests/benchmark/test_report.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'draft_helper.benchmark.report'`

- [ ] **Step 3: Implement the report renderer**

Create `draft_helper/benchmark/report.py`:

```python
"""Render a BenchmarkReport as markdown (for reading) or JSON (for storage)."""
from __future__ import annotations

import json

from .models import BenchmarkReport


def render_markdown(report: BenchmarkReport) -> str:
    lines: list[str] = []
    lines.append(f"# Draft benchmark — {report.set_code}")
    lines.append(f"Source: `{report.source}`")
    lines.append("")
    lines.append(f"- **Agreement rate:** {report.agreement_rate:.0%}")
    lines.append(f"- **Mean rank of human's pick:** {report.mean_human_rank:.2f}")
    lines.append(f"- **Coverage:** scored {report.scored_count}/"
                 f"{len(report.results)} picks "
                 f"({report.skipped_count} skipped as unrecognized)")
    lines.append("")

    lines.append("| Pack | Pick | Tool pick | Human pick | Agree | Human rank |")
    lines.append("|-----:|-----:|-----------|------------|:-----:|-----------:|")
    for r in report.results:
        agree = "—" if not r.scored else ("✓" if r.agree else "✗")
        rank = "—" if not r.scored else str(r.human_rank)
        lines.append(f"| {r.pack_number} | {r.pick_number} | {r.tool_pick} | "
                     f"{r.human_pick} | {agree} | {rank} |")
    lines.append("")

    disagreements = [r for r in report.results if r.scored and not r.agree]
    disagreements.sort(key=lambda r: r.human_rank, reverse=True)
    if disagreements:
        lines.append("## Biggest disagreements")
        for r in disagreements:
            lines.append(f"- P{r.pack_number}P{r.pick_number}: tool took "
                         f"`{r.tool_pick}`, human took `{r.human_pick}` "
                         f"(human's pick ranked #{r.human_rank})")
    return "\n".join(lines)


def render_json(report: BenchmarkReport) -> str:
    payload = {
        "set_code": report.set_code,
        "source": report.source,
        "agreement_rate": report.agreement_rate,
        "mean_human_rank": report.mean_human_rank,
        "scored_count": report.scored_count,
        "skipped_count": report.skipped_count,
        "results": [
            {
                "pack_number": r.pack_number,
                "pick_number": r.pick_number,
                "tool_pick": r.tool_pick,
                "human_pick": r.human_pick,
                "agree": r.agree,
                "human_rank": r.human_rank,
                "pack_size": r.pack_size,
                "scored": r.scored,
            }
            for r in report.results
        ],
    }
    return json.dumps(payload, indent=2)
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `python -m pytest tests/benchmark/test_report.py -q`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add draft_helper/benchmark/report.py tests/benchmark/test_report.py
git commit -m "feat: benchmark report rendering (markdown + json)"
```

---

## Task 4: Runner (ratings loading + end-to-end)

**Files:**
- Create: `draft_helper/benchmark/runner.py`
- Test: `tests/benchmark/test_runner.py`

**Behavior:** `run_benchmark` ensures ratings for the record's set are loaded
(fetching via `api` only if not already loaded), then calls `score_draft`. This
keeps network I/O out of the scorer. The test stubs the ratings load so it stays
offline.

- [ ] **Step 1: Write the failing test**

Create `tests/benchmark/test_runner.py`:

```python
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
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python -m pytest tests/benchmark/test_runner.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'draft_helper.benchmark.runner'`

- [ ] **Step 3: Implement the runner**

Create `draft_helper/benchmark/runner.py`:

```python
"""Top-level benchmark entry: load ratings for the set, then score."""
from __future__ import annotations

from draft_helper import api, ratings
from .models import DraftRecord, BenchmarkReport
from .scorer import score_draft


def _ensure_ratings_loaded(set_code: str, draft_format: str) -> None:
    """Load 17Lands ratings for the set into the ratings module if needed.

    Prefers the on-disk cache; falls back to a live fetch. Isolated in its own
    function so tests can stub the network entirely.
    """
    if ratings.is_loaded():
        return
    cached = api.load_cache(set_code, draft_format)
    if cached:
        ratings.load(cached)
        return
    data = api.fetch_all_ratings(set_code, draft_format)
    api.save_cache(set_code, draft_format, data)
    ratings.load(data)


def run_benchmark(record: DraftRecord,
                  draft_format: str = "PremierDraft") -> BenchmarkReport:
    """Load ratings for the record's set, then score the draft."""
    _ensure_ratings_loaded(record.set_code, draft_format)
    return score_draft(record)
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `python -m pytest tests/benchmark/test_runner.py -q`
Expected: PASS (1 passed)

- [ ] **Step 5: Run the whole benchmark suite + full project suite**

Run: `python -m pytest tests/benchmark/ -q`
Expected: PASS (all benchmark tests)

Run: `python -m pytest tests/ game_advisor/tests/ -q`
Expected: PASS (existing 356 + new benchmark tests, no regressions)

- [ ] **Step 6: Commit**

```bash
git add draft_helper/benchmark/runner.py tests/benchmark/test_runner.py
git commit -m "feat: benchmark runner (ratings load + end-to-end scoring)"
```

---

## Self-Review Notes

- **Spec coverage:** Phase A of the spec is fully covered — the `DraftRecord`/`PickEvent` seam (Task 1), the scorer with the deck-mirroring fairness rule + pack-opener handling (Task 2), agreement rate + mean human rank + coverage line (Tasks 1, 3), and markdown/JSON report with a biggest-disagreements list (Task 3). Ratings loading is isolated in the runner (Task 4). Phases B1–B3 are intentionally out of this plan — they get their own plans after a recognition spike, per the design's phasing.
- **Not yet wired to real data:** this plan produces a working, tested engine that runs on hand-written `DraftRecord`s. Feeding it real MSH picks (read from video frames via vision, or the future B pipeline) is a follow-on step, not part of Phase A.
- **No new dependencies.**

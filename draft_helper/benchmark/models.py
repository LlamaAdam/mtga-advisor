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

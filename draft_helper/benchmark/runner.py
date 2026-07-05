"""Top-level benchmark entry: load ratings for the set, then score."""
from __future__ import annotations

from draft_helper import api, ratings
from .models import DraftRecord, BenchmarkReport
from .scorer import score_draft


def _ensure_ratings_loaded(set_code: str, draft_format: str) -> None:
    """Load 17Lands ratings for the set into the ratings module if needed.

    Prefers the on-disk cache; falls back to a live fetch. Isolated in its own
    function so tests can stub the network entirely. Reloads whenever the
    module holds ratings for a DIFFERENT (or unknown) set/format — otherwise
    back-to-back benchmarks of two sets would silently share one set's data.
    """
    set_key = f"{set_code}_{draft_format}"
    if ratings.is_loaded() and ratings.loaded_key() == set_key:
        return
    cached = api.load_cache(set_code, draft_format)
    if cached:
        ratings.load(cached, set_key=set_key)
        return
    data = api.fetch_all_ratings(set_code, draft_format)
    api.save_cache(set_code, draft_format, data)
    ratings.load(data, set_key=set_key)


def run_benchmark(record: DraftRecord,
                  draft_format: str = "PremierDraft") -> BenchmarkReport:
    """Load ratings for the record's set, then score the draft."""
    _ensure_ratings_loaded(record.set_code, draft_format)
    return score_draft(record)

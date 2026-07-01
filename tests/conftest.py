"""Pytest config: ensure the draft_helper package is importable.

The legacy draft-helper code lives in the `draft_helper/` package (FP-C).
Add the repo root to sys.path so `from draft_helper import card_db`,
`from draft_helper.deck import DeckTracker`, etc. work from the test
files. `draft_helper.*` and `game_advisor.*` no longer share bare
module names, so `pytest tests/ game_advisor/tests/` can run together
in one invocation.
"""
import sys
import pathlib

_REPO = pathlib.Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))


def pytest_configure(config):
    """Register custom markers used by tests."""
    config.addinivalue_line(
        "markers",
        "real_save: opt out of the test_card_db autouse stub of "
        "_save_cache (used by tests that exercise the real atomic "
        "write path)",
    )

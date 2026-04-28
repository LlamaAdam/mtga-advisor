"""Pytest config: ensure top-level project modules are importable.

The legacy draft-helper code lives at the repo root (no `src/` layout).
Add the repo root to sys.path so `import card_db`, `import deck`, etc.
work from the test files.

NOTE: The `game_advisor/` subdirectory ships its own `config.py` and
`log_scanner.py`. When pytest is invoked from the repo root with no
scope, game_advisor's tests inject `game_advisor/` onto sys.path[0],
which then shadows the top-level modules during collection of
`tests/test_api.py` and `tests/test_log_scanner.py`. Both top-level
and subpackage suites pass when run separately:

    pytest tests/                 # top-level (this file's tests)
    pytest game_advisor/tests/    # game_advisor subpackage

Mixing them in one invocation is a pre-existing limitation.
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

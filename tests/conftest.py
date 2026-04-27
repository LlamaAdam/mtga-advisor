"""Pytest config: ensure top-level project modules are importable.

The legacy draft-helper code lives at the repo root (no `src/` layout).
Add the repo root to sys.path so `import card_db`, `import deck`, etc.
work from the test files.
"""
import sys
import pathlib

_REPO = pathlib.Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

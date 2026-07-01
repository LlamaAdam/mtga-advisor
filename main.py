"""Thin entry-point shim — the draft helper now lives in draft_helper/.

Kept at the repo root so existing launchers (Launch Draft Helper.bat,
Launch Draft Helper (no console).vbs) and the `python main.py` command
in the docs keep working unchanged.
"""
from draft_helper.main import main

if __name__ == "__main__":
    main()

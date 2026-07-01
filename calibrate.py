"""Thin entry-point shim — the calibrator now lives in draft_helper/.

Kept at the repo root so `python calibrate.py` (per setup.bat and the
README) keeps working unchanged.
"""
from draft_helper.calibrate import Calibrator

if __name__ == "__main__":
    app = Calibrator()
    app.run()

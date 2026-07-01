"""
Screen capture fallback for detecting opponent cards not visible in the log.
Uses mss for screenshot and pytesseract for OCR.
Fuzzy-matches OCR text against known card names from card_db.

Falls back gracefully if tesseract is not installed.
"""
import difflib
import importlib.util
import sys
import pathlib
from typing import Optional

# Load game_advisor/config.py explicitly to avoid shadowing by root config.py
_config_path = pathlib.Path(__file__).parent / "config.py"
_spec = importlib.util.spec_from_file_location("game_advisor_config", _config_path)
config = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(config)

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
from draft_helper import card_db

try:
    import mss
    import pytesseract
    from PIL import Image, ImageFilter
    pytesseract.pytesseract.tesseract_cmd = config.TESSERACT_CMD
    pytesseract.get_tesseract_version()  # raises TesseractNotFoundError if binary missing
    _CAPTURE_AVAILABLE = True
except Exception:
    _CAPTURE_AVAILABLE = False
    print("[capture] OCR disabled — install Tesseract to enable screen capture fallback.")


def capture_opponent_cards() -> list[str]:
    """
    Capture the MTGA window, OCR visible card names on the opponent's side.
    Returns a list of matched card names. Returns [] if OCR is unavailable.
    """
    if not _CAPTURE_AVAILABLE:
        return []
    try:
        return _do_capture()
    except Exception as e:
        print(f"[capture] Error during capture: {e}")
        return []


def _do_capture() -> list[str]:
    region = config.CAPTURE_REGION
    with mss.mss() as sct:
        screenshot = sct.grab(region)

    img = Image.frombytes("RGB", screenshot.size, screenshot.rgb)
    img = img.convert("L")  # grayscale
    img = img.point(lambda p: 255 if p > 128 else 0)  # threshold

    raw_text = pytesseract.image_to_string(img, config="--psm 11")
    lines = [line.strip() for line in raw_text.splitlines() if len(line.strip()) > 3]

    known_names = list(card_db._cache.values())
    matched: list[str] = []
    for line in lines:
        hits = difflib.get_close_matches(
            line, known_names, n=1,
            cutoff=config.OCR_CONFIDENCE_THRESHOLD,
        )
        if hits:
            matched.append(hits[0])

    return list(set(matched))

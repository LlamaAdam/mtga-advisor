"""
Screen capture utilities.
Uses mss for fast multi-monitor screenshot support.
"""

import mss
import numpy as np
from PIL import Image


def capture_region(x: int, y: int, w: int, h: int) -> Image.Image:
    """Capture a specific screen region and return a PIL Image."""
    with mss.mss() as sct:
        monitor = {"left": x, "top": y, "width": w, "height": h}
        raw = sct.grab(monitor)
        return Image.frombytes("RGB", raw.size, raw.bgra, "raw", "BGRX")


def capture_fullscreen() -> Image.Image:
    """Capture the entire primary monitor."""
    with mss.mss() as sct:
        monitor = sct.monitors[1]  # monitors[0] is all monitors combined
        raw = sct.grab(monitor)
        return Image.frombytes("RGB", raw.size, raw.bgra, "raw", "BGRX")


def preprocess_for_ocr(img: Image.Image) -> Image.Image:
    """
    Enhance image for better Tesseract OCR accuracy on card names.
    MTGA uses white/gold text on dark backgrounds.
    """
    # Scale up for better OCR
    w, h = img.size
    img = img.resize((w * 3, h * 3), Image.LANCZOS)

    # Convert to grayscale
    gray = img.convert("L")

    # Apply threshold to isolate light text on dark bg
    threshold = 160
    bw = gray.point(lambda p: 255 if p > threshold else 0)

    return bw

"""
Detects MTGA draft card bounding boxes from a live screenshot.

Strategy: MTGA cards have a bright metallic frame border. By scanning
horizontal slices of the screen for these bright pixels we can find the
top edge of each card row, then scan vertical columns to find left edges.
Card centers are returned for badge placement.

Falls back gracefully: if we can't detect the right number of cards,
we return None and the overlay uses the calibration-based grid instead.
"""

import numpy as np
import mss
from PIL import Image
import config

# -----------------------------------------------------------------------
# Tuning parameters
# -----------------------------------------------------------------------

# A pixel is "border-bright" if its grayscale value exceeds this
BORDER_BRIGHT = 170

# Minimum number of bright pixels in a single row for it to count
# as a "card top border" row
ROW_BRIGHT_MIN = 55

# Minimum pixels between two separate card row detections
ROW_MIN_GAP = 90

# Minimum pixels between two separate card column detections
COL_MIN_GAP = 70

# Estimated half-card height: badge Y is placed this far below the top border
HALF_CARD_H = 95

# Estimated half-card width: badge X is offset this far right from the left border
HALF_CARD_W = 80

# Skip the very top of the screen (nav bar) and very bottom (buttons)
SCAN_TOP_FRAC    = 0.10
SCAN_BOTTOM_FRAC = 0.90

# Exclude the right-side deck list panel
GAME_RIGHT_FRAC  = 0.72


def detect_card_centers(expected_count: int) -> list[tuple[int, int]] | None:
    """
    Detect MTGA draft card center positions from the live screen.

    Returns list of (cx, cy) in left-to-right, top-to-bottom order.
    Returns None if detection confidence is too low (falls back to grid).
    """
    try:
        gray, x_off, y_off = _capture_game_area()
        centers = _find_centers(gray, x_off, y_off)

        if not centers:
            return None

        # Accept if within ±2 of expected (accounts for partially off-screen cards)
        if abs(len(centers) - expected_count) > 2:
            return None

        return centers[:expected_count]

    except Exception as e:
        print(f"[detector] Detection failed: {e}")
        return None


def _capture_game_area() -> tuple[np.ndarray, int, int]:
    """Capture the MTGA game area (excluding deck list). Returns (gray, x_offset, y_offset)."""
    x_off = 0
    y_off = 0
    game_w = int(config.SCREEN_WIDTH  * GAME_RIGHT_FRAC)
    game_h = config.SCREEN_HEIGHT

    with mss.mss() as sct:
        region = {"left": x_off, "top": y_off, "width": game_w, "height": game_h}
        raw = sct.grab(region)
        img = Image.frombytes("RGB", raw.size, raw.bgra, "raw", "BGRX")

    return np.array(img.convert("L")), x_off, y_off


def _find_centers(gray: np.ndarray, x_off: int, y_off: int) -> list[tuple[int, int]]:
    """Find card centers in a grayscale image. Returns [(cx, cy), ...]."""
    h, w = gray.shape

    scan_top = int(h * SCAN_TOP_FRAC)
    scan_bot = int(h * SCAN_BOTTOM_FRAC)

    bright = (gray > BORDER_BRIGHT).astype(np.int32)

    # ------------------------------------------------------------------
    # Step 1: Horizontal projection — find card top border rows
    # ------------------------------------------------------------------
    row_proj = bright[scan_top:scan_bot, :].sum(axis=1)
    border_rows = _find_peaks(row_proj, threshold=ROW_BRIGHT_MIN, min_gap=ROW_MIN_GAP)
    border_rows = [r + scan_top for r in border_rows]

    if not border_rows:
        return []

    # ------------------------------------------------------------------
    # Step 2: For each border row, find card left border columns
    # ------------------------------------------------------------------
    all_centers: list[tuple[int, int]] = []

    for border_y in border_rows:
        # Sample a thin strip right at this border line
        strip = bright[max(0, border_y - 4): min(h, border_y + 8), :]
        col_proj = strip.sum(axis=0)

        col_lefts = _find_peaks(col_proj, threshold=2, min_gap=COL_MIN_GAP)
        if not col_lefts:
            continue

        # Card center: left-border + half card width, top-border + half card height
        cy = border_y + HALF_CARD_H + y_off
        for col_x in col_lefts:
            cx = col_x + HALF_CARD_W + x_off
            all_centers.append((cx, cy))

    # Sort top-to-bottom, left-to-right (group rows with 80px tolerance)
    all_centers.sort(key=lambda p: (p[1] // 80, p[0]))
    return all_centers


def _find_peaks(arr: np.ndarray, threshold: int, min_gap: int) -> list[int]:
    """
    Find peaks in a 1-D array where values exceed threshold.
    Within each contiguous above-threshold region, return the position of the maximum.
    Enforces a minimum distance of min_gap between returned peaks.
    """
    peaks: list[int] = []
    last_peak = -min_gap - 1

    in_region = False
    region_max = 0
    region_max_pos = 0

    for i, v in enumerate(arr):
        if v >= threshold:
            if not in_region:
                in_region = True
                region_max = int(v)
                region_max_pos = i
            elif int(v) > region_max:
                region_max = int(v)
                region_max_pos = i
        else:
            if in_region:
                in_region = False
                if region_max_pos - last_peak >= min_gap:
                    peaks.append(region_max_pos)
                    last_peak = region_max_pos

    if in_region and region_max_pos - last_peak >= min_gap:
        peaks.append(region_max_pos)

    return peaks

"""Tests for card_detector.py — pure-function unit tests.

Mocks `mss` screen capture for the public ``detect_card_centers`` API
and exercises the inner helpers (``_find_peaks``, ``_find_centers``)
directly against synthetic numpy arrays.
"""
from __future__ import annotations

import numpy as np
import pytest

import card_detector
from card_detector import (
    _find_centers,
    _find_peaks,
    detect_card_centers,
)


# ---------------------------------------------------------------------------
# _find_peaks
# ---------------------------------------------------------------------------

def test_find_peaks_returns_position_of_maximum_in_region():
    arr = np.array([0, 0, 5, 8, 10, 7, 0, 0, 0, 0])
    peaks = _find_peaks(arr, threshold=4, min_gap=3)
    # Region is indices 2..5; max is 10 at index 4.
    assert peaks == [4]


def test_find_peaks_enforces_min_gap():
    arr = np.array([0, 9, 0, 9, 0, 0, 0, 9, 0])
    peaks = _find_peaks(arr, threshold=5, min_gap=4)
    # Indices 1, 3, 7 all peak. min_gap=4 → keep 1, drop 3 (gap=2),
    # keep 7 (gap from 1 = 6).
    assert peaks == [1, 7]


def test_find_peaks_handles_empty_array():
    assert _find_peaks(np.array([]), threshold=5, min_gap=2) == []


def test_find_peaks_returns_empty_when_nothing_above_threshold():
    arr = np.array([1, 2, 3, 2, 1])
    assert _find_peaks(arr, threshold=10, min_gap=2) == []


def test_find_peaks_handles_in_region_at_end_of_array():
    """A region that runs to the last element shouldn't be silently
    dropped."""
    arr = np.array([0, 0, 0, 0, 5, 9, 7])
    peaks = _find_peaks(arr, threshold=4, min_gap=3)
    assert peaks == [5]


def test_find_peaks_separates_two_distinct_regions():
    arr = np.array([0, 0, 8, 9, 7, 0, 0, 0, 0, 0, 6, 9, 8, 0])
    peaks = _find_peaks(arr, threshold=5, min_gap=4)
    assert peaks == [3, 11]


def test_find_peaks_min_gap_zero_keeps_all():
    """min_gap=0 should still enforce regional dedup, but not skip any."""
    arr = np.array([0, 9, 0, 9, 0])
    peaks = _find_peaks(arr, threshold=5, min_gap=0)
    assert peaks == [1, 3]


# ---------------------------------------------------------------------------
# _find_centers — synthetic grayscale grids
# ---------------------------------------------------------------------------

def _make_grid_image(rows: int, cols: int,
                     card_w: int = 200, card_h: int = 280,
                     gap_x: int = 40, gap_y: int = 60,
                     border_thickness: int = 6) -> np.ndarray:
    """Build a synthetic grayscale screenshot containing a grid of
    "cards" — bright rectangles on a dark background."""
    margin = 100
    h = margin + rows * (card_h + gap_y)
    w = margin + cols * (card_w + gap_x)
    img = np.zeros((h, w), dtype=np.uint8)
    for r in range(rows):
        for c in range(cols):
            top = margin + r * (card_h + gap_y)
            left = margin + c * (card_w + gap_x)
            # Top border: horizontal bright stripe.
            img[top:top + border_thickness, left:left + card_w] = 255
            # Left border: vertical bright stripe.
            img[top:top + card_h, left:left + border_thickness] = 255
    return img


def test_find_centers_detects_2x3_grid():
    """6 cards in a 2x3 grid should produce 6 centers."""
    img = _make_grid_image(rows=2, cols=3)
    centers = _find_centers(img, x_off=0, y_off=0)
    assert len(centers) == 6, f"expected 6 centers, got {len(centers)}"


def test_find_centers_returns_top_to_bottom_left_to_right_ordering():
    img = _make_grid_image(rows=2, cols=3)
    centers = _find_centers(img, x_off=0, y_off=0)
    # First three should be roughly the same y (top row), increasing x.
    ys = [y for _, y in centers]
    xs = [x for x, _ in centers]
    # First row centers should have lower y than second row centers.
    assert max(ys[:3]) < min(ys[3:])
    # Within each row, x should be increasing.
    assert xs[0] < xs[1] < xs[2]
    assert xs[3] < xs[4] < xs[5]


def test_find_centers_applies_x_y_offsets():
    img = _make_grid_image(rows=1, cols=2)
    no_off = _find_centers(img, x_off=0, y_off=0)
    with_off = _find_centers(img, x_off=50, y_off=30)
    assert len(no_off) == len(with_off)
    for (x0, y0), (x1, y1) in zip(no_off, with_off):
        assert x1 == x0 + 50
        assert y1 == y0 + 30


def test_find_centers_returns_empty_for_blank_image():
    img = np.zeros((600, 800), dtype=np.uint8)
    assert _find_centers(img, 0, 0) == []


# ---------------------------------------------------------------------------
# detect_card_centers — public API with mocked capture
# ---------------------------------------------------------------------------

def test_detect_card_centers_returns_centers_when_count_matches(monkeypatch):
    img = _make_grid_image(rows=2, cols=3)
    monkeypatch.setattr(
        card_detector, "_capture_game_area",
        lambda: (img, 0, 0),
    )
    centers = detect_card_centers(expected_count=6)
    assert centers is not None
    assert len(centers) == 6


def test_detect_card_centers_returns_none_when_count_far_off(monkeypatch):
    """If detection finds way more or fewer cards than expected,
    return None to fall back to grid."""
    img = _make_grid_image(rows=2, cols=3)  # 6 cards
    monkeypatch.setattr(
        card_detector, "_capture_game_area",
        lambda: (img, 0, 0),
    )
    # Expecting 12 — should reject (gap > 2).
    assert detect_card_centers(expected_count=12) is None


def test_detect_card_centers_truncates_to_expected_count(monkeypatch):
    """If detection finds slightly more cards than expected (within 2),
    truncate to expected_count."""
    img = _make_grid_image(rows=2, cols=3)  # 6 cards
    monkeypatch.setattr(
        card_detector, "_capture_game_area",
        lambda: (img, 0, 0),
    )
    centers = detect_card_centers(expected_count=5)
    assert centers is not None
    assert len(centers) == 5


def test_detect_card_centers_returns_none_on_capture_error(monkeypatch):
    def _raise():
        raise RuntimeError("simulated capture failure")
    monkeypatch.setattr(card_detector, "_capture_game_area", _raise)
    assert detect_card_centers(expected_count=6) is None


def test_detect_card_centers_returns_none_on_blank_screen(monkeypatch):
    blank = np.zeros((600, 800), dtype=np.uint8)
    monkeypatch.setattr(
        card_detector, "_capture_game_area",
        lambda: (blank, 0, 0),
    )
    assert detect_card_centers(expected_count=6) is None

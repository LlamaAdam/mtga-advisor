"""Tests for overlay.py — pure-function unit tests.

Only `OverlayApp.grid_centers` (a staticmethod) is tested here, since
the rest of the module is Tkinter UI that can't run without a display.
"""
from __future__ import annotations

import math

import pytest

# We can't import overlay at module top because it imports tkinter,
# which initializes a display in some environments. Defer the import
# to inside each test so we can monkeypatch config first.


def test_grid_centers_single_row(monkeypatch):
    from draft_helper import config
    monkeypatch.setattr(config, "DRAFT_ORIGIN", (100, 200), raising=False)
    monkeypatch.setattr(config, "CARD_STEP_X", 250, raising=False)
    monkeypatch.setattr(config, "CARD_STEP_Y", 400, raising=False)
    monkeypatch.setattr(config, "SCREEN_WIDTH", 2560, raising=False)
    monkeypatch.setattr(config, "SCREEN_HEIGHT", 1440, raising=False)
    monkeypatch.setattr(config, "OVERLAY_BADGE_SIZE", 60, raising=False)
    monkeypatch.setattr(config, "BADGE_Y_OFFSET", 50, raising=False)

    from draft_helper.overlay import OverlayApp
    centers = OverlayApp.grid_centers(3)
    assert len(centers) == 3
    # All in the same row → same y.
    ys = [y for _, y in centers]
    assert len(set(ys)) == 1
    # X increments by CARD_STEP_X.
    xs = [x for x, _ in centers]
    assert xs[1] - xs[0] == 250
    assert xs[2] - xs[1] == 250


def test_grid_centers_wraps_to_second_row(monkeypatch):
    """When card_count exceeds per_row, second row wraps below the first."""
    from draft_helper import config
    monkeypatch.setattr(config, "DRAFT_ORIGIN", (100, 200), raising=False)
    # CARD_STEP_X=400 → game_right(1843) - 100 = 1743 // 400 = 4 per row.
    monkeypatch.setattr(config, "CARD_STEP_X", 400, raising=False)
    monkeypatch.setattr(config, "CARD_STEP_Y", 400, raising=False)
    monkeypatch.setattr(config, "SCREEN_WIDTH", 2560, raising=False)
    monkeypatch.setattr(config, "SCREEN_HEIGHT", 1440, raising=False)
    monkeypatch.setattr(config, "OVERLAY_BADGE_SIZE", 60, raising=False)
    monkeypatch.setattr(config, "BADGE_Y_OFFSET", 50, raising=False)

    from draft_helper.overlay import OverlayApp
    centers = OverlayApp.grid_centers(6)  # 4 + 2
    assert len(centers) == 6
    # First four are top row, last two are second row.
    top_ys = {y for _, y in centers[:4]}
    bot_ys = {y for _, y in centers[4:]}
    assert len(top_ys) == 1
    assert len(bot_ys) == 1
    assert max(top_ys) < min(bot_ys)


def test_grid_centers_returns_empty_for_zero_cards(monkeypatch):
    from draft_helper import config
    monkeypatch.setattr(config, "DRAFT_ORIGIN", (100, 200), raising=False)
    monkeypatch.setattr(config, "CARD_STEP_X", 250, raising=False)
    monkeypatch.setattr(config, "CARD_STEP_Y", 400, raising=False)
    monkeypatch.setattr(config, "SCREEN_WIDTH", 2560, raising=False)
    monkeypatch.setattr(config, "SCREEN_HEIGHT", 1440, raising=False)
    monkeypatch.setattr(config, "OVERLAY_BADGE_SIZE", 60, raising=False)
    monkeypatch.setattr(config, "BADGE_Y_OFFSET", 50, raising=False)

    from draft_helper.overlay import OverlayApp
    assert OverlayApp.grid_centers(0) == []


def test_grid_centers_compresses_vertical_step_for_many_rows(monkeypatch):
    """When 3+ rows are needed, step_y should compress to keep all
    rows on-screen above the bottom margin."""
    from draft_helper import config
    monkeypatch.setattr(config, "DRAFT_ORIGIN", (100, 100), raising=False)
    # 400px step → game_right(1843) - 100 = 1743 // 400 = 4 per row.
    monkeypatch.setattr(config, "CARD_STEP_X", 400, raising=False)
    monkeypatch.setattr(config, "CARD_STEP_Y", 800, raising=False)  # too tall
    monkeypatch.setattr(config, "SCREEN_WIDTH", 2560, raising=False)
    monkeypatch.setattr(config, "SCREEN_HEIGHT", 1440, raising=False)
    monkeypatch.setattr(config, "OVERLAY_BADGE_SIZE", 60, raising=False)
    monkeypatch.setattr(config, "BADGE_Y_OFFSET", 50, raising=False)

    from draft_helper.overlay import OverlayApp
    # 12 cards / 4 per row → 3 rows.
    centers = OverlayApp.grid_centers(12)
    assert len(centers) == 12
    # Vertical step must be ≤ CARD_STEP_Y (800) because of compression.
    ys = sorted({y for _, y in centers})
    assert len(ys) == 3
    step = ys[1] - ys[0]
    assert step < 800


def test_grid_centers_per_row_clamped_to_at_least_one(monkeypatch):
    """If CARD_STEP_X is huge, per_row must clamp to 1 (not zero)."""
    from draft_helper import config
    monkeypatch.setattr(config, "DRAFT_ORIGIN", (100, 200), raising=False)
    # Huge step that exceeds the game-area width.
    monkeypatch.setattr(config, "CARD_STEP_X", 10000, raising=False)
    monkeypatch.setattr(config, "CARD_STEP_Y", 400, raising=False)
    monkeypatch.setattr(config, "SCREEN_WIDTH", 2560, raising=False)
    monkeypatch.setattr(config, "SCREEN_HEIGHT", 1440, raising=False)
    monkeypatch.setattr(config, "OVERLAY_BADGE_SIZE", 60, raising=False)
    monkeypatch.setattr(config, "BADGE_Y_OFFSET", 50, raising=False)

    from draft_helper.overlay import OverlayApp
    centers = OverlayApp.grid_centers(3)
    assert len(centers) == 3
    # 1-per-row → all 3 in different rows (different y).
    ys = sorted({y for _, y in centers})
    assert len(ys) == 3


def test_grid_centers_x_uses_step_plus_half_badge(monkeypatch):
    """The first card's x should be DRAFT_ORIGIN.x + badge_size//2."""
    from draft_helper import config
    monkeypatch.setattr(config, "DRAFT_ORIGIN", (200, 300), raising=False)
    monkeypatch.setattr(config, "CARD_STEP_X", 250, raising=False)
    monkeypatch.setattr(config, "CARD_STEP_Y", 400, raising=False)
    monkeypatch.setattr(config, "SCREEN_WIDTH", 2560, raising=False)
    monkeypatch.setattr(config, "SCREEN_HEIGHT", 1440, raising=False)
    monkeypatch.setattr(config, "OVERLAY_BADGE_SIZE", 80, raising=False)
    monkeypatch.setattr(config, "BADGE_Y_OFFSET", 50, raising=False)

    from draft_helper.overlay import OverlayApp
    centers = OverlayApp.grid_centers(1)
    assert centers == [(200 + 80 // 2, 300 + 50)]

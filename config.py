"""
MTGA Draft Helper - Configuration
"""

import os
import pathlib

# Absolute path to the directory containing this config file.
# All relative cache paths are resolved from here so the program works
# regardless of which directory the user launches it from.
_BASE_DIR = pathlib.Path(__file__).parent

# --- Arena Player Log ---
# Where MTGA writes its log file (used to detect draft events)
ARENA_LOG_PATH = os.path.join(
    os.environ.get("USERPROFILE", "C:/Users/Default"),
    "AppData", "LocalLow", "Wizards Of The Coast", "MTGA", "Player.log"
)

# --- 17Lands API ---
# Date range for fetching ratings (broader = more data, slower)
RATINGS_START_DATE = "2024-01-01"   # Adjust to current set's start date
# End date is always today (fetched dynamically in api.py)

# Minimum sample count for a rating to be considered reliable
MIN_GAME_COUNT = 200

# Use Bayesian smoothing for low-sample cards (recommended)
BAYESIAN_ENABLED = True

# --- Overlay Settings ---
SCREEN_WIDTH  = 2560
SCREEN_HEIGHT = 1600
OVERLAY_REFRESH_SECONDS = 1.5
OVERLAY_BADGE_SIZE = 64
OVERLAY_OPACITY = 0.90

# --- Grid-based card position system ---
# Instead of fixed positions, we store 3 reference points and derive the full
# grid dynamically. Run calibrate.py to set these for your screen.
#
# DRAFT_ORIGIN   = top-left corner of the FIRST card's badge area
# CARD_STEP_X    = horizontal distance (px) from one card to the next
# CARD_STEP_Y    = vertical distance (px) from row 1 to row 2
# MAX_PER_ROW    = cards per row when the pack is at its largest
#                  (e.g. 7 for a 14-card pack, 4 for an 8-card pack)
#
# At runtime, badge positions are computed from these values based on
# how many cards are actually in the current pack.
DRAFT_ORIGIN  = (274, 273)   # (x, y) of first card's TOP-LEFT corner
# How far down from the card's top-left to place the badge center.
# Moves the badge to the bottom-left of each card to avoid covering card text.
# Roughly: card height - badge size - small margin.
BADGE_Y_OFFSET = 310         # px below card top to center the badge
CARD_STEP_X   = 288          # px between cards horizontally
CARD_STEP_Y   = 396          # px between rows
# MAX_PER_ROW is derived at runtime from SCREEN_WIDTH and CARD_STEP_X —
# do not set it manually. See overlay.py card_positions().

# --- Grading (standard deviations from set mean GIHWR) ---
# Matches the grading system used by 17Lands / bstaple1's tool
GRADE_THRESHOLDS = [
    ("A+",  2.00),
    ("A",   1.50),
    ("A-",  1.00),
    ("B+",  0.50),
    ("B",   0.17),
    ("B-", -0.17),
    ("C+", -0.33),
    ("C",  -0.50),
    ("C-", -0.83),
    ("D+", -1.00),
    ("D",  -1.33),
    ("D-", -1.67),
    ("F",  -9999),
]

GRADE_COLORS = {
    "A+": "#00cc44",
    "A":  "#00cc44",
    "A-": "#44dd66",
    "B+": "#88ee44",
    "B":  "#aadd00",
    "B-": "#cccc00",
    "C+": "#ddaa00",
    "C":  "#ee8800",
    "C-": "#ee6600",
    "D+": "#ee4400",
    "D":  "#ee3300",
    "D-": "#cc1100",
    "F":  "#aa0000",
    "?":  "#555555",
}

# Local cache file for fetched ratings (avoids re-fetching every run)
RATINGS_CACHE_FILE = str(_BASE_DIR / "ratings_cache.json")

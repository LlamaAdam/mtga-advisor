import os
import sys
import pathlib
from dotenv import load_dotenv

# Load .env from the game_advisor directory
load_dotenv(pathlib.Path(__file__).parent / ".env")

# Add parent folder to path so we can import card_db
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

# LLM backend — supports OpenAI, OpenRouter, or Ollama (local)
#
# For Ollama (local, free):
#   LLM_BACKEND=ollama
#   LLM_MODEL=llama3  (or mistral, phi3, gemma2, etc.)
#
# For OpenAI:
#   LLM_BACKEND=openai
#   OPENAI_API_KEY=sk-...
#   LLM_MODEL=gpt-4o
#
# For OpenRouter:
#   LLM_BACKEND=openrouter
#   OPENAI_API_KEY=sk-or-v1-...
#   LLM_MODEL=openai/gpt-4o  (or any OpenRouter model slug)

LLM_BACKEND: str = os.environ.get("LLM_BACKEND", "ollama").lower()
OPENAI_API_KEY: str = os.environ.get("OPENAI_API_KEY", "")

_default_model = {
    "ollama": "llama3",
    "openrouter": "openai/gpt-4o",
    "openai": "gpt-4o",
}.get(LLM_BACKEND, "llama3")
OPENAI_MODEL: str = os.environ.get("LLM_MODEL", _default_model)

LLM_TIMEOUT_SECONDS: int = int(os.environ.get("LLM_TIMEOUT_SECONDS", "30"))
LLM_MIN_INTERVAL_SECONDS: int = int(os.environ.get("LLM_MIN_INTERVAL_SECONDS", "8"))

# MTGA log path (same as draft helper)
ARENA_LOG_PATH: str = os.path.join(
    os.environ.get("USERPROFILE", "C:/Users/Default"),
    "AppData", "LocalLow", "Wizards Of The Coast", "MTGA", "Player.log"
)

# Dashboard: position and size for second monitor
# Set ADVISOR_MONITOR_X to your second monitor's x offset (e.g. 1920 for right-side monitor)
ADVISOR_MONITOR_X: int = int(os.environ.get("ADVISOR_MONITOR_X", "1920"))
ADVISOR_MONITOR_Y: int = int(os.environ.get("ADVISOR_MONITOR_Y", "0"))
ADVISOR_WIDTH: int = 800
ADVISOR_HEIGHT: int = 950

# Your seat ID in the game. Almost always 1 for the local player.
PLAYER_SEAT_ID: int = 1

# Poll intervals
LOG_POLL_SECONDS: float = 0.5
CAPTURE_POLL_SECONDS: float = 3.0

# Screen capture region (set by calibrate_capture.py, saved to config.py)
CAPTURE_REGION: dict = {"top": 0, "left": 0, "width": 1920, "height": 1080}
OCR_CONFIDENCE_THRESHOLD: float = 0.80

# Tesseract binary path (Windows default; override via TESSERACT_CMD env var)
TESSERACT_CMD: str = os.environ.get(
    "TESSERACT_CMD",
    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
)

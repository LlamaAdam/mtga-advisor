"""
MTGA Game Advisor — entry point.

Wires together: log scanner, rule engine, LLM advisor, dashboard.

Usage:
  cd game_advisor
  python main.py

Controls:
  Space  = force LLM advice refresh
  R      = resync from log
  ESC    = quit
"""
import sys
import pathlib
import time
import threading

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
sys.path.insert(0, str(pathlib.Path(__file__).parent))

import config
import rule_engine

# Each imported submodule calls sys.path.insert(0, root), displacing game_advisor/.
# The root also has log_scanner.py and capture.py that shadow ours.
# Re-assert game_advisor/ at [0] before each conflicting import.
_here = str(pathlib.Path(__file__).parent)

if sys.path[0] != _here:
    sys.path.insert(0, _here)
from log_scanner import GameLogScanner  # root has log_scanner.py (ArenaLogScanner)

from llm_advisor import LLMAdvisor      # no root conflict
from dashboard import AdvisorDashboard  # no root conflict

if sys.path[0] != _here:               # log_scanner.py re-inserted root at [0]
    sys.path.insert(0, _here)
from capture import capture_opponent_cards, _CAPTURE_AVAILABLE  # root has capture.py

from game_state import GameState        # no root conflict


def main() -> None:
    print("=" * 55)
    print("  MTGA Game Advisor  |  Powered by GPT-4o")
    print("=" * 55)
    print(f"\n  Arena log: {config.ARENA_LOG_PATH}")
    if not config.OPENAI_API_KEY:
        print("  WARNING: OPENAI_API_KEY not set — LLM advice disabled.")
    print()

    dashboard = AdvisorDashboard()
    scanner = GameLogScanner()
    advisor = LLMAdvisor()

    _current_state: list[GameState] = [None]  # mutable container for thread sharing
    _current_advice: list[str] = ["Waiting for game..."]

    def on_state_change(state: GameState) -> None:
        _current_state[0] = state
        alerts = rule_engine.run_all(state)
        dashboard.schedule_update(state, alerts, _current_advice[0])
        print(
            f"[main] Turn {state.turn} | {state.phase} | "
            f"You {state.you.life} vs Opp {state.opponent.life} | "
            f"{len(alerts)} alerts"
        )

        def on_advice(text: str) -> None:
            _current_advice[0] = text
            dashboard.schedule_llm_update(text)

        dashboard.set_status("Thinking...")
        advisor.request_advice_async(state, on_complete=on_advice)

    def force_refresh() -> None:
        if _current_state[0]:
            on_state_change(_current_state[0])

    def resync() -> None:
        print("[main] Resyncing log...")
        scanner._file_pos = 0
        scanner._last_mtime = 0
        scanner.poll()

    scanner.on_state_change = on_state_change
    dashboard.on_force_refresh = force_refresh
    dashboard.on_resync = resync

    # Background log polling thread
    def poll_loop() -> None:
        while dashboard._running:
            try:
                scanner.poll()
            except Exception as e:
                print(f"[poll] Error: {e}")
            time.sleep(config.LOG_POLL_SECONDS)

    poll_thread = threading.Thread(target=poll_loop, daemon=True)
    poll_thread.start()

    # Background OCR capture thread
    def capture_loop() -> None:
        while dashboard._running:
            try:
                names = capture_opponent_cards()
                if names:
                    print(f"[capture] OCR detected: {names}")
            except Exception as e:
                print(f"[capture] Error: {e}")
            time.sleep(config.CAPTURE_POLL_SECONDS)

    capture_thread = threading.Thread(target=capture_loop, daemon=True)
    capture_thread.start()

    dashboard.set_status("Waiting for MTGA game...")

    ocr_line = "OCR: Ready (screen capture active)" if _CAPTURE_AVAILABLE else \
               "OCR: Disabled — install Tesseract to enable screen capture fallback"
    llm_line = "LLM: Ready (GPT-4o connected)" if config.OPENAI_API_KEY else \
               "LLM: Disabled — set OPENAI_API_KEY in game_advisor/.env to enable advice"
    log_line = f"Log: Watching {config.ARENA_LOG_PATH}"
    dashboard.set_startup_message(
        f"{ocr_line}\n{llm_line}\n{log_line}\n\n"
        "Open MTGA and start a game — advice will appear here automatically.\n\n"
        "  Space  = force advice refresh\n"
        "  R      = resync log\n"
        "  ESC    = quit"
    )
    print("[main] Advisor started. Open MTGA and start a game!\n")
    dashboard.run()
    print("\nGoodbye!")


if __name__ == "__main__":
    main()

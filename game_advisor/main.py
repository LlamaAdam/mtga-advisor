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
import decklist
import card_db
from decision_log import DecisionLog

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
    _backend_label = {"ollama": "Ollama (local)", "openrouter": "OpenRouter",
                      "openai": "GPT-4o"}.get(config.LLM_BACKEND, config.LLM_BACKEND)
    print("=" * 55)
    print(f"  MTGA Game Advisor  |  {_backend_label} / {config.OPENAI_MODEL}")
    print("=" * 55)
    print(f"\n  Arena log: {config.ARENA_LOG_PATH}")
    if config.LLM_BACKEND != "ollama" and not config.OPENAI_API_KEY:
        print("  WARNING: OPENAI_API_KEY not set — LLM advice disabled.")
    print()

    # Start background card resolver so unknown arena IDs get resolved after initial lookup
    card_db.start_background_resolver()

    # Optional: load decklist for LLM context and hand quality hints
    _load_decklist_interactive()

    decision_log = DecisionLog()
    dashboard = AdvisorDashboard()
    scanner = GameLogScanner()
    advisor = LLMAdvisor()

    _current_state: list[GameState] = [None]  # mutable container for thread sharing
    _current_advice: list[str] = ["Waiting for game..."]

    def on_state_change(state: GameState) -> None:
        nonlocal decision_log
        _current_state[0] = state
        alerts = rule_engine.run_all(state)
        decision_log.record(state, alerts)
        # Flush decision log when game_id changes (new game started)
        if state.game_id and state.game_id != getattr(on_state_change, "_last_game_id", ""):
            if getattr(on_state_change, "_last_game_id", ""):
                path = decision_log.flush(on_state_change._last_game_id)
                if path:
                    print(f"[main] Decision log saved: {path}")
            on_state_change._last_game_id = state.game_id
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
    if config.LLM_BACKEND == "ollama":
        llm_line = f"LLM: Ready (Ollama / {config.OPENAI_MODEL})"
    elif config.OPENAI_API_KEY:
        llm_line = f"LLM: Ready ({_backend_label} / {config.OPENAI_MODEL})"
    else:
        llm_line = "LLM: Disabled — set OPENAI_API_KEY in game_advisor/.env to enable advice"
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


def _load_decklist_interactive() -> None:
    """Prompt the user to paste their MTGA decklist. Press Enter twice to finish."""
    print("  Paste your MTGA decklist below (press Enter twice when done, or just Enter to skip):")
    lines: list[str] = []
    try:
        while True:
            line = input()
            if line == "" and lines and lines[-1] == "":
                break
            if line == "" and not lines:
                # Immediate empty = skip
                break
            lines.append(line)
    except (EOFError, KeyboardInterrupt):
        pass

    text = "\n".join(lines).strip()
    if not text:
        print("  [Advisor] No decklist loaded — LLM advice will be generic.\n")
        return

    parsed = decklist.parse_decklist(text)
    decklist.active_deck = parsed
    card_count = sum(parsed.values())
    print(f"  [Advisor] Loaded {len(parsed)} unique cards ({card_count} total) from decklist.\n")


if __name__ == "__main__":
    main()

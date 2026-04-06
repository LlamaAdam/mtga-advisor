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
import deck_manager
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

    # Pre-populate card name cache from the local MTGA database so new sets that
    # Scryfall hasn't mapped yet (e.g. Edge of Eternities) resolve correctly.
    try:
        import mtga_local_db
        mtga_local_db.preload_into_card_db()
    except Exception as _e:
        print(f"  [mtga_local_db] Preload skipped: {_e}")

    # Start background card resolver so unknown arena IDs get resolved after initial lookup
    card_db.start_background_resolver()

    # Optional: load decklist for LLM context and hand quality hints
    _load_decklist_interactive()

    decision_log = DecisionLog()
    dashboard = AdvisorDashboard()
    # Wire 'D' key to snapshot the current in-memory log so the viewer always
    # shows data even before the game ends / a new game starts.
    dashboard.set_pre_log_callback(
        lambda: decision_log.write_snapshot(
            getattr(on_state_change, "_last_game_id", "current")
        )
    )
    scanner = GameLogScanner()
    advisor = LLMAdvisor()

    _current_state: list[GameState] = [None]  # mutable container for thread sharing
    _current_advice: list[str] = ["Waiting for game..."]

    def on_state_change(state: GameState) -> None:
        _current_state[0] = state
        alerts = rule_engine.run_all(state)
        decision_log.record(state, alerts)
        dashboard.schedule_update(state, alerts, _current_advice[0])
        print(
            f"[main] Turn {state.turn} | {state.phase} | "
            f"You {state.you.life} vs Opp {state.opponent.life} | "
            f"{len(alerts)} alerts | "
            f"board {len(state.you.board)}v{len(state.opponent.board)} | "
            f"hand {len(state.you.hand)}"
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

    def on_new_game(game_id: str) -> None:
        """Fired when MTGA sends a GameStateType_Full (new game started)."""
        print(f"[main] New game detected — id: {game_id}")
        # Flush any leftover decisions from the previous game
        old_path = decision_log.flush(game_id)
        if old_path:
            print(f"[main] Previous game log saved: {old_path}")
        # Reset current advice so the old game's text doesn't bleed into the new game
        _current_advice[0] = "New game — waiting for first state..."
        dashboard.set_status(f"New game started")
        dashboard.set_startup_message("New game detected — analysing opening hand...\n")

    def on_game_over(outcome: str) -> None:
        """Fired when MTGA reports a game result. Triggers post-loss analysis."""
        print(f"[main] Game over — outcome: {outcome}")
        # Always flush the decision log so it's saved regardless of outcome
        path = decision_log.flush(scanner._current_game_id)
        if path:
            print(f"[main] Decision log saved: {path}")

        if outcome != "loss":
            # Win or draw — just update the status bar
            msg = "🏆 You won!" if outcome == "win" else "🤝 Draw."
            dashboard.set_status(msg)
            return

        # Loss — request a post-game analysis paragraph from the LLM
        dashboard.set_status("📋 Analysing your game...")
        entries = decision_log._entries  # entries cleared by flush; re-read from file if needed
        # If flush already cleared entries, reload from the saved file
        if not entries and path:
            try:
                import json as _json
                with open(path, encoding="utf-8") as _f:
                    _data = _json.load(_f)
                from decision_log import Decision
                entries = [
                    Decision(
                        turn=d["turn"],
                        phase=d["phase"],
                        recommendations=d["recommendations"],
                        inferred_action=d.get("inferred_action", "unknown"),
                    )
                    for d in _data.get("decisions", [])
                ]
            except Exception as _e:
                print(f"[main] Could not reload decision log: {_e}")

        def on_analysis(text: str) -> None:
            _current_advice[0] = text
            dashboard.schedule_llm_update(text)
            dashboard.set_status("📋 Post-game review ready")

        advisor.request_post_game_analysis_async(
            entries, outcome, on_complete=on_analysis
        )

    scanner.on_state_change = on_state_change
    scanner.on_game_over = on_game_over
    scanner.on_new_game = on_new_game
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
    """Show the deck selection menu. Load a saved deck or paste a new one."""
    saved = deck_manager.list_decks()

    print("  ┌─────────────────────────────────────────┐")
    print("  │           Deck Selection                 │")
    print("  └─────────────────────────────────────────┘")

    if saved:
        for i, name in enumerate(saved, 1):
            total = deck_manager.deck_card_count(name)
            print(f"    {i:>2}.  {name}  ({total} cards)")
        print()
        print("     n.  Paste new deck from MTGA")
        print("     d.  Delete a saved deck")
        print("     s.  Skip (no decklist this game)")
    else:
        print("    No saved decks yet.")
        print()
        print("     n.  Paste new deck from MTGA")
        print("     s.  Skip (no decklist this game)")

    print()

    try:
        choice = input("  Pick a number, n, d, or s (Enter = skip): ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        choice = ""

    # --- Skip ---
    if choice in ("", "s"):
        print("  [Advisor] No decklist loaded — LLM advice will be generic.\n")
        return

    # --- Delete ---
    if choice == "d":
        if not saved:
            print("  [Advisor] No saved decks to delete.\n")
            return
        try:
            target = input("  Enter deck name or number to delete: ").strip()
            # Allow number reference
            if target.isdigit():
                idx = int(target) - 1
                if 0 <= idx < len(saved):
                    target = saved[idx]
            if deck_manager.delete_deck(target):
                print(f"  [Advisor] Deleted '{target}'.\n")
            else:
                print(f"  [Advisor] Deck '{target}' not found.\n")
        except (EOFError, KeyboardInterrupt):
            pass
        return

    # --- Load saved deck by number ---
    if choice.isdigit():
        idx = int(choice) - 1
        if 0 <= idx < len(saved):
            name = saved[idx]
            loaded = deck_manager.load_deck(name)
            if loaded:
                decklist.active_deck = loaded
                total = sum(loaded.values())
                print(f"  [Advisor] Loaded '{name}' ({len(loaded)} unique, {total} total cards).\n")
                return
        print("  [Advisor] Invalid choice — no decklist loaded.\n")
        return

    # --- Paste new deck ---
    if choice == "n":
        print("  Paste your MTGA decklist (press Enter twice when done):")
        lines: list[str] = []
        try:
            while True:
                line = input()
                if line == "" and lines and lines[-1] == "":
                    break
                if line == "" and not lines:
                    break
                lines.append(line)
        except (EOFError, KeyboardInterrupt):
            pass

        text = "\n".join(lines).strip()
        if not text:
            print("  [Advisor] No decklist entered — LLM advice will be generic.\n")
            return

        parsed = decklist.parse_decklist(text)
        if not parsed:
            print("  [Advisor] Could not parse decklist — check format and try again.\n")
            return

        decklist.active_deck = parsed
        total = sum(parsed.values())
        print(f"  [Advisor] Loaded {len(parsed)} unique cards ({total} total).")

        # Offer to save for next time
        try:
            save_name = input("  Save this deck? Enter a name (or Enter to skip saving): ").strip()
        except (EOFError, KeyboardInterrupt):
            save_name = ""

        if save_name:
            deck_manager.save_deck(save_name, parsed)
            print(f"  [Advisor] Deck saved as '{save_name}'.")
        print()
        return

    print("  [Advisor] Unrecognised choice — no decklist loaded.\n")


if __name__ == "__main__":
    main()

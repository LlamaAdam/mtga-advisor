"""
Full-dashboard tkinter window for the second monitor.

Layout:
  [Status bar]           turn, life totals, phase
  [Your Board | Opp Board]  creatures side-by-side
  [Your Hand]            hand cards with castability indicator
  [Advice]               rule alerts + GPT-4o advice
"""
import queue
import threading
import tkinter as tk
from tkinter import font as tkfont
from typing import Optional

import sys
import pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
import config
import card_db as _cdb
from game_state import GameState, RuleAlert

_BG = "#1a1a2e"
_BG2 = "#16213e"
_ACCENT = "#0f3460"
_TEXT = "#e0e0e0"
_GREEN = "#4caf50"
_RED = "#f44336"
_YELLOW = "#ff9800"
_BLUE = "#2196f3"
_GRAY = "#757575"

_SEVERITY_COLOR = {
    "DANGER": _RED,
    "WARNING": _YELLOW,
    "INFO": _BLUE,
}


class AdvisorDashboard:
    def __init__(self):
        self._update_queue: queue.Queue = queue.Queue()
        self._running = True

        self.root = tk.Tk()
        self._setup_window()
        self._build_ui()
        self._bind_keys()

        # Callbacks assigned by main.py
        self.on_force_refresh: Optional[callable] = None
        self.on_resync: Optional[callable] = None

    # ------------------------------------------------------------------
    # Setup
    # ------------------------------------------------------------------

    def _setup_window(self) -> None:
        r = self.root
        r.title("MTGA Game Advisor")
        r.geometry(
            f"{config.ADVISOR_WIDTH}x{config.ADVISOR_HEIGHT}"
            f"+{config.ADVISOR_MONITOR_X}+{config.ADVISOR_MONITOR_Y}"
        )
        r.configure(bg=_BG)
        r.attributes("-topmost", False)

    def _build_ui(self) -> None:
        self._build_status_bar()
        self._build_boards_section()
        self._build_hand_section()
        self._build_advice_section()

    def _build_status_bar(self) -> None:
        frame = tk.Frame(self.root, bg=_ACCENT, height=40)
        frame.pack(fill=tk.X, padx=0, pady=0)
        frame.pack_propagate(False)

        self._status_var = tk.StringVar(value="Waiting for MTGA game...")
        lbl = tk.Label(frame, textvariable=self._status_var,
                       bg=_ACCENT, fg=_TEXT, font=("Consolas", 12, "bold"))
        lbl.pack(expand=True)

    def _build_boards_section(self) -> None:
        outer = tk.Frame(self.root, bg=_BG2, height=200)
        outer.pack(fill=tk.X, padx=4, pady=4)
        outer.pack_propagate(False)

        # Your board (left half)
        your_frame = tk.LabelFrame(outer, text=" YOUR BOARD ",
                                   bg=_BG2, fg=_GREEN, font=("Consolas", 10, "bold"),
                                   bd=1, relief=tk.RIDGE)
        your_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=4, pady=4)

        self._your_board_list = tk.Listbox(
            your_frame, bg=_BG2, fg=_TEXT, font=("Consolas", 10),
            selectbackground=_ACCENT, bd=0, highlightthickness=0,
        )
        self._your_board_list.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)

        # Opponent board (right half)
        opp_frame = tk.LabelFrame(outer, text=" OPPONENT BOARD ",
                                  bg=_BG2, fg=_RED, font=("Consolas", 10, "bold"),
                                  bd=1, relief=tk.RIDGE)
        opp_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=4, pady=4)

        self._opp_board_list = tk.Listbox(
            opp_frame, bg=_BG2, fg=_TEXT, font=("Consolas", 10),
            selectbackground=_ACCENT, bd=0, highlightthickness=0,
        )
        self._opp_board_list.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)

    def _build_hand_section(self) -> None:
        frame = tk.LabelFrame(self.root, text=" YOUR HAND ",
                              bg=_BG, fg=_GREEN, font=("Consolas", 10, "bold"),
                              bd=1, relief=tk.RIDGE)
        frame.pack(fill=tk.X, padx=4, pady=2)

        self._hand_text = tk.Text(
            frame, bg=_BG, fg=_TEXT, font=("Consolas", 10),
            height=6, bd=0, highlightthickness=0, state=tk.DISABLED,
        )
        self._hand_text.pack(fill=tk.X, padx=4, pady=4)
        self._hand_text.tag_config("castable", foreground=_GREEN)
        self._hand_text.tag_config("not_castable", foreground=_GRAY)
        self._hand_text.tag_config("land", foreground=_YELLOW)

    def _build_advice_section(self) -> None:
        frame = tk.LabelFrame(self.root, text=" ADVICE ",
                              bg=_BG, fg=_YELLOW, font=("Consolas", 10, "bold"),
                              bd=1, relief=tk.RIDGE)
        frame.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        self._advice_text = tk.Text(
            frame, bg=_BG, fg=_TEXT, font=("Consolas", 10),
            bd=0, highlightthickness=0, state=tk.DISABLED, wrap=tk.WORD,
        )
        self._advice_text.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
        self._advice_text.tag_config("DANGER", foreground=_RED)
        self._advice_text.tag_config("WARNING", foreground=_YELLOW)
        self._advice_text.tag_config("INFO", foreground=_BLUE)
        self._advice_text.tag_config("llm", foreground=_TEXT)
        self._advice_text.tag_config("separator", foreground=_GRAY)

    def _bind_keys(self) -> None:
        self.root.bind("<Escape>", lambda _: self.quit())
        self.root.bind("<space>", lambda _: self._on_force_refresh())
        self.root.bind("r", lambda _: self._on_resync())
        self.root.bind("R", lambda _: self._on_resync())

    # ------------------------------------------------------------------
    # Public API — thread-safe via queue
    # ------------------------------------------------------------------

    def schedule_update(
        self,
        state: GameState,
        alerts: list[RuleAlert],
        llm_advice: str,
    ) -> None:
        """Queue a full dashboard update from any thread."""
        self._update_queue.put(("full", state, alerts, llm_advice))

    def schedule_llm_update(self, advice: str) -> None:
        """Queue a partial update to refresh only the LLM advice text."""
        self._update_queue.put(("llm", advice))

    def set_status(self, text: str) -> None:
        self._update_queue.put(("status", text))

    def run(self) -> None:
        """Start the tkinter mainloop. Blocks until window is closed."""
        self._poll_queue()
        self.root.mainloop()

    def quit(self) -> None:
        self._running = False
        self.root.quit()

    # ------------------------------------------------------------------
    # Internal rendering — runs on main thread via after()
    # ------------------------------------------------------------------

    def _poll_queue(self) -> None:
        try:
            while True:
                item = self._update_queue.get_nowait()
                if item[0] == "full":
                    _, state, alerts, advice = item
                    self._render_full(state, alerts, advice)
                elif item[0] == "llm":
                    _, advice = item
                    self._render_llm_advice(advice)
                elif item[0] == "status":
                    _, text = item
                    self._status_var.set(text)
        except queue.Empty:
            pass
        if self._running:
            self.root.after(100, self._poll_queue)

    def _render_full(self, state: GameState, alerts: list[RuleAlert], advice: str) -> None:
        # Status bar
        self._status_var.set(
            f"Turn {state.turn}  |  You: {state.you.life} ♥  Opp: {state.opponent.life} ♥"
            f"  |  {state.phase}"
        )

        # Your board
        self._your_board_list.delete(0, tk.END)
        for card in state.you.board:
            tap = "[T]" if card.tapped else "   "
            kw = " ".join(card.keywords[:2]) if card.keywords else ""
            self._your_board_list.insert(
                tk.END, f"{tap} {card.name}  {card.power}/{card.toughness}  {kw}"
            )

        # Opponent board
        self._opp_board_list.delete(0, tk.END)
        if state.opponent.board:
            scored = sorted(state.opponent.board,
                            key=lambda c: sum(1.5 if k == "flying" else 1.0 for k in c.keywords) * c.power,
                            reverse=True)
            for i, card in enumerate(scored):
                kw = " ".join(card.keywords[:2]) if card.keywords else ""
                entry = f"{'⚠ ' if i == 0 else '  '}{card.name}  {card.power}/{card.toughness}  {kw}"
                self._opp_board_list.insert(tk.END, entry)
                if i == 0:
                    self._opp_board_list.itemconfig(tk.END, fg=_RED)

        # Hand
        self._hand_text.config(state=tk.NORMAL)
        self._hand_text.delete("1.0", tk.END)
        for card in state.you.hand:
            type_line = _cdb.get_type_line(card.name).lower()
            is_land = "land" in type_line

            if is_land:
                marker, tag = "[L]", "land"
            elif card.castable:
                marker, tag = "[✓]", "castable"
            else:
                marker, tag = "[✗]", "not_castable"

            cost_display = card.mana_cost if card.mana_cost else "—"
            if not card.castable and not is_land and card.colors:
                need = f"  (need more mana)"
            else:
                need = ""
            self._hand_text.insert(tk.END, f"{marker} {card.name:<28} {cost_display}{need}\n", tag)
        self._hand_text.config(state=tk.DISABLED)

        # Advice
        self._render_alerts_and_advice(alerts, advice)

    def _render_alerts_and_advice(self, alerts: list[RuleAlert], advice: str) -> None:
        self._advice_text.config(state=tk.NORMAL)
        self._advice_text.delete("1.0", tk.END)
        for alert in alerts:
            icon = {"DANGER": "⚡", "WARNING": "⚠", "INFO": "ℹ"}.get(alert.severity, "•")
            self._advice_text.insert(tk.END, f"{icon} {alert.message}\n", alert.severity)
        if alerts:
            self._advice_text.insert(tk.END, "─" * 60 + "\n", "separator")
        self._advice_text.insert(tk.END, advice or "Waiting for advice...\n", "llm")
        self._advice_text.config(state=tk.DISABLED)

    def _render_llm_advice(self, advice: str) -> None:
        # Find separator and replace everything after it
        self._advice_text.config(state=tk.NORMAL)
        sep_idx = self._advice_text.search("─" * 10, "1.0", tk.END)
        if sep_idx:
            line = int(sep_idx.split(".")[0])
            self._advice_text.delete(f"{line + 1}.0", tk.END)
            self._advice_text.insert(tk.END, advice + "\n", "llm")
        self._advice_text.config(state=tk.DISABLED)

    def _on_force_refresh(self) -> None:
        if self.on_force_refresh:
            threading.Thread(target=self.on_force_refresh, daemon=True).start()

    def _on_resync(self) -> None:
        if self.on_resync:
            threading.Thread(target=self.on_resync, daemon=True).start()

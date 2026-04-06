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
from typing import Callable, Optional

import sys
import pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
import config
import card_db as _cdb
from game_state import GameState, RuleAlert

_BG = "#1a1a2e"
_ROLE_COLORS = {
    "Aggressor": "#f44336",   # red — press damage
    "Defender":  "#2196f3",   # blue — hold back
    "Flexible":  "#ff9800",   # orange — adapt
}
_BG2 = "#16213e"
_ACCENT = "#0f3460"
_TEXT = "#e0e0e0"
_GREEN = "#4caf50"
_RED = "#f44336"
_YELLOW = "#ff9800"
_BLUE = "#2196f3"
_GRAY = "#757575"

def _extract_role(alerts: "list[RuleAlert]") -> "tuple[str, str]":
    """Return (role_name, color) from alerts. Empty string if no role alert."""
    for a in alerts:
        if a.message.startswith("Role: "):
            for role in ("Aggressor", "Defender", "Flexible"):
                if role in a.message:
                    return role, _ROLE_COLORS.get(role, _TEXT)
    return "", _TEXT


def _extract_clock(alerts: "list[RuleAlert]") -> str:
    """Return compact lethal clock string from alerts, or empty string."""
    for a in alerts:
        if a.message.startswith("Lethal clock: "):
            # Shorten: "you kill in 2 attack(s), opponent kills you in 4 attack(s)"
            # → "⚔ kill T2  🛡 T4"
            msg = a.message[len("Lethal clock: "):]
            parts = msg.split(", ")
            short_parts = []
            for p in parts:
                if "you kill" in p:
                    n = "".join(c for c in p if c.isdigit())
                    short_parts.append(f"⚔ kill T{n}")
                elif "opponent kills" in p:
                    n = "".join(c for c in p if c.isdigit())
                    short_parts.append(f"🛡 opp T{n}")
            return "  ".join(short_parts)
    return ""


def _extract_draw_odds(alerts: "list[RuleAlert]") -> str:
    """Return the draw odds string from alerts, or empty string."""
    for a in alerts:
        if a.message.startswith("Draw odds"):
            # Strip the leading "Draw odds (library N): " prefix for compact display
            return a.message
    return ""


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
        self._build_role_clock_bar()
        self._build_boards_section()
        self._build_stats_strip()
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

    def _build_role_clock_bar(self) -> None:
        """Thin bar below status showing role badge and lethal clock."""
        frame = tk.Frame(self.root, bg=_BG2, height=24)
        frame.pack(fill=tk.X, padx=0, pady=0)
        frame.pack_propagate(False)

        self._role_var = tk.StringVar(value="")
        self._clock_var = tk.StringVar(value="")

        self._role_lbl = tk.Label(frame, textvariable=self._role_var,
                                  bg=_BG2, font=("Consolas", 10, "bold"), width=18)
        self._role_lbl.pack(side=tk.LEFT, padx=8)

        self._clock_lbl = tk.Label(frame, textvariable=self._clock_var,
                                   bg=_BG2, fg=_TEXT, font=("Consolas", 10))
        self._clock_lbl.pack(side=tk.LEFT, padx=4)

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

    def _build_stats_strip(self) -> None:
        """Compact strip showing library size and live draw odds (visible when data available)."""
        frame = tk.Frame(self.root, bg=_ACCENT, height=22)
        frame.pack(fill=tk.X, padx=0, pady=0)
        frame.pack_propagate(False)

        self._stats_var = tk.StringVar(value="")
        lbl = tk.Label(frame, textvariable=self._stats_var,
                       bg=_ACCENT, fg=_TEXT, font=("Consolas", 9))
        lbl.pack(side=tk.LEFT, padx=8)

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
        self.root.bind("d", lambda _: self._show_decision_log())
        self.root.bind("D", lambda _: self._show_decision_log())
        self._pre_log_callback: Optional[Callable[[], None]] = None

    def set_pre_log_callback(self, fn: "Callable[[], None]") -> None:
        """Register a callable that is invoked before the decision log viewer opens.

        Use this to flush/snapshot the current in-memory decision log to disk
        so the viewer always shows the latest game data.
        """
        self._pre_log_callback = fn

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

    def set_startup_message(self, text: str) -> None:
        """Display a plain message in the advice panel before any game starts."""
        self._update_queue.put(("startup", text))

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
                elif item[0] == "startup":
                    _, text = item
                    self._advice_text.config(state=tk.NORMAL)
                    self._advice_text.delete("1.0", tk.END)
                    self._advice_text.insert(tk.END, text, "llm")
                    self._advice_text.config(state=tk.DISABLED)
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

        # Role badge + lethal clock bar
        role, role_color = _extract_role(alerts)
        self._role_var.set(f"[ {role} ]" if role else "")
        self._role_lbl.config(fg=role_color)
        clock = _extract_clock(alerts)
        self._clock_var.set(clock)

        # Stats strip — library size + draw odds
        lib = getattr(state.you, "library_size", 0)
        odds = _extract_draw_odds(alerts)
        if lib > 0 or odds:
            parts = []
            if lib > 0:
                parts.append(f"Library: {lib}")
            if odds:
                parts.append(odds)
            self._stats_var.set("  ".join(parts))
        else:
            self._stats_var.set("")

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

    def _show_decision_log(self) -> None:
        """Load and display the most recent decision log JSON in the advice panel."""
        import json, os, pathlib, glob as _glob
        # Snapshot current in-memory log so we always see the latest game data
        if self._pre_log_callback is not None:
            try:
                self._pre_log_callback()
            except Exception:
                pass
        logs_dir = pathlib.Path(__file__).parent / "logs"
        files = sorted(_glob.glob(str(logs_dir / "*.json")))
        if not files:
            self._advice_text.config(state=tk.NORMAL)
            self._advice_text.delete("1.0", tk.END)
            self._advice_text.insert(tk.END, "No decision logs found yet.\nPlay a game first!\n", "INFO")
            self._advice_text.config(state=tk.DISABLED)
            return

        latest = files[-1]
        try:
            with open(latest, encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            return

        self._advice_text.config(state=tk.NORMAL)
        self._advice_text.delete("1.0", tk.END)
        fname = os.path.basename(latest)
        self._advice_text.insert(tk.END, f"📋 Decision Log: {fname}\n", "INFO")
        self._advice_text.insert(tk.END, "─" * 60 + "\n", "separator")

        decisions = data.get("decisions", [])
        for d in decisions[-20:]:   # show last 20 turns
            turn = d.get("turn", "?")
            phase = d.get("phase", "")
            action = d.get("inferred_action", "unknown")
            recs = d.get("recommendations", [])

            self._advice_text.insert(tk.END, f"\nT{turn} {phase} — {action}\n", "llm")
            for r in recs[:3]:   # top 3 alerts per turn
                sev = "DANGER" if r.startswith("[DANGER]") else "WARNING" if r.startswith("[WARNING]") else "INFO"
                self._advice_text.insert(tk.END, f"  {r}\n", sev)

        self._advice_text.insert(tk.END, "\n─── Press Space to return to live view ───\n", "separator")
        self._advice_text.config(state=tk.DISABLED)

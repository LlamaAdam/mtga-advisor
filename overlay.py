"""
Transparent overlay window using tkinter.

Draws rating badges over each card position on screen and shows a sidebar
with deck stats. Positions correspond to config.CARD_OVERLAY_POSITIONS.

Keyboard shortcuts:
  ESC / click X  = quit
  R              = force refresh badges
  U              = undo last pick
  C              = clear deck / new draft
"""

import queue
import threading
import tkinter as tk

import config
import ratings as ratings_engine
from deck import DeckTracker

_TRANSPARENT = "#010101"   # Color key made invisible on Windows


class OverlayApp:
    def __init__(self, tracker: DeckTracker):
        self.tracker = tracker
        self._running = True
        self._lock = threading.Lock()
        self.on_resync = None   # Set by main.py after construction
        self._status_queue: queue.Queue = queue.Queue()
        # (card_names, best_pick, original_pack_size) tuples queued from threads
        self._update_queue: queue.Queue = queue.Queue()

        self.root = tk.Tk()
        self._setup_window()
        self._build_canvas()
        self._build_sidebar()
        self._build_close_button()
        self._bind_keys()

    # ------------------------------------------------------------------
    # Window setup
    # ------------------------------------------------------------------

    def _setup_window(self):
        r = self.root
        r.title("MTGA Draft Helper")
        r.geometry(f"{config.SCREEN_WIDTH}x{config.SCREEN_HEIGHT}+0+0")
        r.configure(bg=_TRANSPARENT)
        r.attributes("-transparentcolor", _TRANSPARENT)
        r.attributes("-topmost", True)
        r.attributes("-alpha", config.OVERLAY_OPACITY)
        r.overrideredirect(True)

    def _build_canvas(self):
        self.canvas = tk.Canvas(
            self.root,
            width=config.SCREEN_WIDTH,
            height=config.SCREEN_HEIGHT,
            bg=_TRANSPARENT,
            highlightthickness=0,
        )
        self.canvas.place(x=0, y=0)

    def _build_close_button(self):
        tk.Button(
            self.root,
            text="✕",
            bg="#cc0000", fg="white",
            font=("Helvetica", 10, "bold"),
            relief=tk.FLAT,
            command=self.quit,
            cursor="hand2",
        ).place(x=config.SCREEN_WIDTH - 32, y=4, width=28, height=28)

    def _bind_keys(self):
        self.root.bind("<Escape>", lambda e: self.quit())
        self.root.bind("<r>",      lambda e: self._resync())
        self.root.bind("<R>",      lambda e: self._resync())
        self.root.bind("<u>",      lambda e: self._undo())
        self.root.bind("<U>",      lambda e: self._undo())
        self.root.bind("<c>",      lambda e: self._clear())
        self.root.bind("<C>",      lambda e: self._clear())

    # ------------------------------------------------------------------
    # Sidebar
    # ------------------------------------------------------------------

    def _build_sidebar(self):
        W = 210
        X = config.SCREEN_WIDTH - W - 38
        Y = 40

        frame = tk.Frame(self.root, bg="#12122a", bd=2, relief=tk.RIDGE)
        frame.place(x=X, y=Y, width=W, height=520)

        def lbl(text, size=9, bold=False, color="#ddddff"):
            font = ("Helvetica", size, "bold" if bold else "normal")
            return tk.Label(frame, text=text, bg="#12122a", fg=color,
                            font=font, wraplength=W - 16)

        def sep():
            tk.Frame(frame, bg="#334466", height=1).pack(fill=tk.X, padx=8, pady=3)

        lbl("MTGA DRAFT HELPER", 12, bold=True, color="#e8c96a").pack(pady=(10, 1))
        lbl("Powered by 17Lands", 8, color="#667788").pack()
        sep()

        self._lbl_pack   = lbl("Pack 1 | Pick 1", 10, bold=True)
        self._lbl_pack.pack(pady=2)
        self._lbl_colors = lbl("Colors: Undecided")
        self._lbl_colors.pack(pady=1)
        self._lbl_total  = lbl("Cards picked: 0")
        self._lbl_total.pack(pady=1)
        sep()

        lbl("Mana Curve", 9, bold=True, color="#aaaacc").pack()
        self._lbl_curve = lbl("—", color="#ccccff")
        self._lbl_curve.pack(pady=1)
        sep()

        lbl("Color Counts", 9, bold=True, color="#aaaacc").pack()
        self._lbl_color_detail = lbl("—", color="#ccccff")
        self._lbl_color_detail.pack(pady=1)
        sep()

        lbl("R=Resync picks  U=Undo  C=Clear  ESC=Quit",
            7, color="#556677").pack(pady=6)

        sep()
        self._lbl_status = lbl("Waiting for draft…", 8, color="#aaaaaa")
        self._lbl_status.pack(pady=4)

    # ------------------------------------------------------------------
    # Badge drawing
    # ------------------------------------------------------------------

    @staticmethod
    def grid_centers(card_count: int) -> list[tuple[int, int]]:
        """
        Fallback: compute card CENTER positions from the calibration grid.
        Returns list of (cx, cy) — the center point of each card.
        """
        import math
        ox, oy = config.DRAFT_ORIGIN
        S = config.OVERLAY_BADGE_SIZE

        # MTGA's draft card area only spans ~72% of the screen width
        # (the right portion is the deck list panel). Using full screen width
        # would compute too many cards per row and misplace badges for rows 2+.
        game_right = int(config.SCREEN_WIDTH * 0.72)
        per_row = max(1, (game_right - ox) // config.CARD_STEP_X)
        num_rows = math.ceil(card_count / per_row) if card_count > 0 else 1

        # Compress vertical step when 3+ rows so all fit on screen
        bottom_margin = 120
        available_h = config.SCREEN_HEIGHT - bottom_margin - oy
        step_y = min(config.CARD_STEP_Y,
                     available_h // (num_rows - 1)) if num_rows > 1 else config.CARD_STEP_Y

        centers = []
        for i in range(card_count):
            row = i // per_row
            col = i % per_row
            # Badge placed at bottom-left of each card to avoid covering card text
            cx = ox + col * config.CARD_STEP_X + S // 2
            cy = oy + row * step_y + config.BADGE_Y_OFFSET
            centers.append((cx, cy))
        return centers

    def update_cards(self, card_names: list[str], best_pick: str | None = None,
                     original_pack_size: int = 0):
        """
        Redraw all rating badges.
        Tries screen-based card detection first; falls back to calibration grid.
        """
        import card_detector

        self.canvas.delete("badge")
        card_names = [n for n in card_names if n]
        count = len(card_names)
        if count == 0:
            self._update_sidebar()
            return

        # Try visual detection — returns card centers directly
        centers = card_detector.detect_card_centers(count)
        source = "detector"

        if centers is None:
            # Fall back to calibration-based grid
            centers = self.grid_centers(count)
            source = "grid"

        if len(centers) < count:
            centers = centers + self.grid_centers(count)[len(centers):]

        for i, name in enumerate(card_names):
            cx, cy = centers[i]
            wr, grade = self.tracker.adjusted_rating(name)
            color = ratings_engine.grade_color(grade)
            self._draw_badge(cx, cy, name, grade, wr, color, name == best_pick)

        self._update_sidebar()

    def _draw_badge(self, cx, cy, name, grade, winrate, color, is_best):
        """Draw a rating badge CENTERED at (cx, cy)."""
        S = config.OVERLAY_BADGE_SIZE
        r = S // 2
        pad = 6

        if is_best and winrate is not None:
            self.canvas.create_oval(
                cx - r - pad, cy - r - pad,
                cx + r + pad, cy + r + pad,
                fill="", outline="#ffffff", width=3, tags="badge",
            )

        self.canvas.create_oval(
            cx - r, cy - r, cx + r, cy + r,
            fill=color, outline="#000000", width=1, tags="badge",
        )

        self.canvas.create_text(
            cx, cy - 9, text=grade,
            fill="white", font=("Helvetica", 15, "bold"), tags="badge",
        )

        wr_text = f"{winrate:.1f}%" if winrate is not None else "N/A"
        self.canvas.create_text(
            cx, cy + 10, text=wr_text,
            fill="white", font=("Helvetica", 8), tags="badge",
        )

        # Only show "PICK THIS" when we actually have a win rate to base it on
        if is_best and winrate is not None:
            self.canvas.create_text(
                cx, cy + r + 13, text="▲ PICK THIS",
                fill="#ffffff", font=("Helvetica", 9, "bold"), tags="badge",
            )

    def _update_sidebar(self):
        s = self.tracker.summary()
        self._lbl_pack.config(text=f"Pack {s['pack']} | Pick {s['pick']}")
        colors = s["main_colors"]
        self._lbl_colors.config(
            text=f"Colors: {'/' .join(colors) if colors else 'Undecided'}"
        )
        self._lbl_total.config(text=f"Cards picked: {s['total_cards']}")
        self._lbl_curve.config(text=s["curve"])
        bd = s["color_breakdown"]
        self._lbl_color_detail.config(
            text="  ".join(f"{k}:{v}" for k, v in bd.items()) if bd else "—"
        )

    # ------------------------------------------------------------------
    # Thread-safe update + controls
    # ------------------------------------------------------------------

    def schedule_update(self, card_names: list[str], best_pick: str | None,
                        original_pack_size: int = 0):
        """Call from any thread to update badges safely."""
        self._update_queue.put((card_names, best_pick, original_pack_size))

    def set_status(self, text: str):
        """Update the status line in the sidebar from any thread (thread-safe)."""
        self._status_queue.put(text)

    def _poll_queues(self):
        """
        Drain both the status and card-update queues on the main thread.
        Scheduled to run every 100 ms once the mainloop is up.
        Only the last card update in the queue is applied (discard stale ones).
        """
        # Status updates — apply all, last one wins
        try:
            while True:
                text = self._status_queue.get_nowait()
                self._lbl_status.config(text=text)
        except queue.Empty:
            pass

        # Card updates — discard all but the most recent
        latest = None
        try:
            while True:
                latest = self._update_queue.get_nowait()
        except queue.Empty:
            pass
        if latest is not None:
            card_names, best_pick, orig = latest
            self.update_cards(card_names, best_pick, orig)

        if self._running:
            self.root.after(100, self._poll_queues)

    def _resync(self):
        """Trigger a full log resync from the R key."""
        if self.on_resync:
            import threading
            threading.Thread(target=self.on_resync, daemon=True).start()

    def quit(self):
        self._running = False
        self.root.quit()

    def _undo(self):
        self.tracker.remove_last_pick()
        self._update_sidebar()

    def _clear(self):
        self.tracker.clear()
        self.canvas.delete("badge")
        self._update_sidebar()

    def run(self):
        self._poll_queues()   # Start draining queues once mainloop is up
        self.root.mainloop()

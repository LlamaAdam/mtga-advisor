"""
Calibration tool — click 3 reference points to define the card grid.

Run this WHILE MTGA is open on a draft pick screen with a FULL pack showing.

You will click:
  [1] Top-left corner of the FIRST card (top-left of the grid)
  [2] Top-left corner of the SECOND card (one step to the right)
  [3] Top-left corner of the first card in the SECOND ROW

From these 3 points the tool derives:
  - DRAFT_ORIGIN  (where the first badge goes)
  - CARD_STEP_X   (horizontal spacing between cards)
  - CARD_STEP_Y   (vertical spacing between rows)

It also asks you how many cards are visible so it can set MAX_PER_ROW.

Usage:
    python calibrate.py
"""

import pathlib
import tkinter as tk
from tkinter import messagebox, simpledialog
import re
import mss
from PIL import Image, ImageTk

import config


def capture_screen() -> Image.Image:
    with mss.mss() as sct:
        monitor = sct.monitors[1]
        raw = sct.grab(monitor)
        return Image.frombytes("RGB", raw.size, raw.bgra, "raw", "BGRX")


class Calibrator:
    STEPS = [
        "Click the TOP-LEFT corner of card #1 (first card, top row)",
        "Click the TOP-LEFT corner of card #2 (second card, same row)",
        "Click the TOP-LEFT corner of card #1 in the SECOND ROW",
    ]

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("MTGA Draft Helper — Calibration")
        self.clicks: list[tuple[int, int]] = []
        self.scale = 1.0

        screen = capture_screen()
        sw, sh = screen.size
        max_w, max_h = 2560,1600
        self.scale = min(max_w / sw, max_h / sh)
        dw = int(sw * self.scale)
        dh = int(sh * self.scale)

        self.display = screen.resize((dw, dh), Image.LANCZOS)
        self.tk_img  = ImageTk.PhotoImage(self.display)

        self.root.geometry(f"{dw}x{dh + 70}")
        self.lbl = tk.Label(
            self.root,
            text=f"Step 1 of 3: {self.STEPS[0]}",
            font=("Helvetica", 11),
            wraplength=dw - 20,
        )
        self.lbl.pack(pady=6)

        self.canvas = tk.Canvas(self.root, width=dw, height=dh)
        self.canvas.pack()
        self.canvas.create_image(0, 0, anchor=tk.NW, image=self.tk_img)
        self.canvas.bind("<Button-1>", self._on_click)
        self.root.bind("<Escape>", lambda e: self.root.destroy())

    def _on_click(self, event):
        sx = int(event.x / self.scale)
        sy = int(event.y / self.scale)
        self.clicks.append((sx, sy))

        r = 8
        n = len(self.clicks)
        self.canvas.create_oval(
            event.x - r, event.y - r, event.x + r, event.y + r,
            fill="red", outline="white", width=2,
        )
        self.canvas.create_text(
            event.x + 14, event.y, text=str(n),
            fill="red", font=("Helvetica", 12, "bold"),
        )

        if n < 3:
            self.lbl.config(text=f"Step {n + 1} of 3: {self.STEPS[n]}")
        else:
            self._finish()

    def _finish(self):
        p1, p2, p3 = self.clicks

        origin   = p1
        step_x   = p2[0] - p1[0]
        step_y   = p3[1] - p1[1]

        # Per-row is computed at runtime from screen width — no need to ask.
        # Just preview what the layout will look like.
        import math
        per_row_preview = max(1, (config.SCREEN_WIDTH - origin[0]) // step_x)

        snippet = f"""
# --- Set by calibrate.py ---
DRAFT_ORIGIN  = ({origin[0]}, {origin[1]})
CARD_STEP_X   = {step_x}
CARD_STEP_Y   = {step_y}
"""
        print("\nCalibration result — written to config.py:\n")
        print(snippet)
        print(f"  Per-row at runtime: {per_row_preview} cards "
              f"(from ({config.SCREEN_WIDTH} - {origin[0]}) / {step_x})")

        # Write directly into config.py by replacing the existing values
        config_path = str(pathlib.Path(__file__).parent / "config.py")
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                src = f.read()

            src = re.sub(r"DRAFT_ORIGIN\s*=\s*\(.*?\)",
                         f"DRAFT_ORIGIN  = ({origin[0]}, {origin[1]})", src)
            src = re.sub(r"CARD_STEP_X\s*=\s*\d+",
                         f"CARD_STEP_X   = {step_x}", src)
            src = re.sub(r"CARD_STEP_Y\s*=\s*\d+",
                         f"CARD_STEP_Y   = {step_y}", src)

            with open(config_path, "w", encoding="utf-8") as f:
                f.write(src)

            messagebox.showinfo(
                "Done",
                f"config.py updated!\n\n"
                f"Origin:  {origin}\n"
                f"Step X:  {step_x} px\n"
                f"Step Y:  {step_y} px\n\n"
                f"Cards per row will be calculated automatically\n"
                f"from your screen width ({config.SCREEN_WIDTH}px):\n"
                f"  → {per_row_preview} cards per row with these settings\n\n"
                f"If this looks wrong, adjust SCREEN_WIDTH in config.py\n"
                f"to match your actual MTGA window width.",
            )
        except Exception as e:
            messagebox.showerror("Error", f"Could not update config.py:\n{e}\n\nCopy the output from the terminal manually.")

        self.root.destroy()

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    app = Calibrator()
    app.run()

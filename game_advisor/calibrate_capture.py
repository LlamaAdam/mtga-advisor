"""
Interactive helper to set the MTGA window capture region.
Run once: python calibrate_capture.py
Follow prompts to click two corners of the area containing opponent cards.
Saves CAPTURE_REGION to config.py.
"""
import sys
import pathlib
import re

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

try:
    import mss
    import mss.tools
    from PIL import Image
    from pynput import mouse
except ImportError:
    print("Install pynput: pip install pynput")
    sys.exit(1)

_CONFIG_PATH = pathlib.Path(__file__).parent / "config.py"
_clicks: list[tuple[int, int]] = []


def on_click(x: int, y: int, button, pressed: bool) -> bool | None:
    if pressed:
        _clicks.append((x, y))
        print(f"  Point {len(_clicks)}: ({x}, {y})")
        if len(_clicks) == 2:
            return False  # Stop listener


def main() -> None:
    print("MTGA Capture Calibration")
    print("========================")
    print("1. Make sure MTGA is open and showing a game.")
    print("2. Click the TOP-LEFT corner of the opponent's card area.")
    print("3. Click the BOTTOM-RIGHT corner of the opponent's card area.")
    print()

    with mouse.Listener(on_click=on_click) as listener:
        listener.join()

    (x1, y1), (x2, y2) = _clicks[0], _clicks[1]
    region = {
        "top": min(y1, y2),
        "left": min(x1, x2),
        "width": abs(x2 - x1),
        "height": abs(y2 - y1),
    }
    print(f"\nCapture region: {region}")

    # Update CAPTURE_REGION in config.py
    config_text = _CONFIG_PATH.read_text(encoding="utf-8")
    new_line = f'CAPTURE_REGION: dict = {region}'
    config_text = re.sub(
        r'CAPTURE_REGION: dict = \{[^}]+\}',
        new_line,
        config_text,
    )
    _CONFIG_PATH.write_text(config_text, encoding="utf-8")
    print(f"Saved to {_CONFIG_PATH}")

    # Take a test screenshot
    with mss.mss() as sct:
        shot = sct.grab(region)
    img = Image.frombytes("RGB", shot.size, shot.rgb)
    out = pathlib.Path(__file__).parent / "capture_test.png"
    img.save(out)
    print(f"Test screenshot saved to {out}")


if __name__ == "__main__":
    main()

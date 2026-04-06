# MTG Arena Game Advisor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a second-screen Python dashboard (`game_advisor/`) that monitors MTGA in real time, runs instant rule-based alerts (combat math, lethal, threat ranking), and calls GPT-4o for strategic advice during games.

**Architecture:** Standalone `game_advisor/` app alongside the existing draft helper. Tails `Player.log` for `GREMessageType_GameStateMessage` payloads to extract game state. Rule engine runs synchronously on each state update; GPT-4o advisor fires async in a background thread with state-hash caching. `mss` + `pytesseract` screen capture fills in unrevealed opponent cards. Tkinter dashboard renders on second monitor.

**Tech Stack:** Python 3.11+, tkinter, openai, mss, pytesseract, Pillow, python-dotenv, pytest

---

## File Map

**Created (new):**
- `game_advisor/__init__.py` — empty package marker
- `game_advisor/config.py` — all settings: API key, monitor position, poll intervals, seat ID
- `game_advisor/game_state.py` — dataclasses: `BoardCard`, `HandCard`, `Player`, `RuleAlert`, `GameState`
- `game_advisor/card_helpers.py` — `get_keywords()`, `get_colors()` wrappers around parent `card_db`
- `game_advisor/log_scanner.py` — tails Player.log, parses GRE messages, fires callbacks
- `game_advisor/rule_engine.py` — synchronous checks: lethal, combat, threats, castability, removal
- `game_advisor/llm_advisor.py` — GPT-4o async client with state-hash cache and rate limiting
- `game_advisor/dashboard.py` — tkinter full-dashboard window for second monitor
- `game_advisor/capture.py` — mss screen capture + pytesseract OCR fallback
- `game_advisor/calibrate_capture.py` — interactive helper to set capture region
- `game_advisor/main.py` — entry point wiring all components
- `game_advisor/.env.example` — `OPENAI_API_KEY=sk-...` template
- `game_advisor/requirements.txt` — new dependencies
- `game_advisor/tests/__init__.py` — empty
- `game_advisor/tests/test_game_state.py`
- `game_advisor/tests/test_card_helpers.py`
- `game_advisor/tests/test_log_scanner.py`
- `game_advisor/tests/test_rule_engine.py`
- `game_advisor/tests/test_llm_advisor.py`

**Modified (parent folder):**
- `card_db.py` — add `get_type_line(card_name)` public function (one-liner, safe addition)

---

## Task 1: Project Scaffold

**Files:**
- Create: `game_advisor/__init__.py`
- Create: `game_advisor/requirements.txt`
- Create: `game_advisor/.env.example`
- Create: `game_advisor/config.py`
- Create: `game_advisor/tests/__init__.py`

- [ ] **Step 1: Create the game_advisor directory structure**

```bash
cd "C:/Users/pilot/OneDrive/Documents/Python Scripts/mtga_draft_helper"
mkdir -p game_advisor/tests
```

- [ ] **Step 2: Create `game_advisor/__init__.py` and `game_advisor/tests/__init__.py`**

Both files are empty — just package markers.

```bash
touch game_advisor/__init__.py game_advisor/tests/__init__.py
```

- [ ] **Step 3: Create `game_advisor/requirements.txt`**

```
openai>=1.0.0
python-dotenv>=1.0.0
mss>=9.0.0
pytesseract>=0.3.10
Pillow>=10.0.0
pytest>=8.0.0
```

- [ ] **Step 4: Create `game_advisor/.env.example`**

```
OPENAI_API_KEY=sk-your-key-here
```

- [ ] **Step 5: Create `game_advisor/config.py`**

```python
import os
import sys
import pathlib
from dotenv import load_dotenv

# Load .env from the game_advisor directory
load_dotenv(pathlib.Path(__file__).parent / ".env")

# Add parent folder to path so we can import card_db
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

# OpenAI
OPENAI_API_KEY: str = os.environ.get("OPENAI_API_KEY", "")
OPENAI_MODEL: str = "gpt-4o"
LLM_TIMEOUT_SECONDS: int = 10
LLM_MIN_INTERVAL_SECONDS: int = 8

# MTGA log path (same as draft helper)
ARENA_LOG_PATH: str = os.path.expandvars(
    r"%LOCALAPPDATA%\..\LocalLow\Wizards Of The Coast\MTGA\Player.log"
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
```

- [ ] **Step 6: Install dependencies**

```bash
cd game_advisor
pip install -r requirements.txt
```

Expected: all packages install without error.

- [ ] **Step 7: Commit scaffold**

```bash
git add game_advisor/
git commit -m "feat: scaffold game_advisor app structure"
```

---

## Task 2: Add `get_type_line` to card_db

**Files:**
- Modify: `card_db.py` (add one function after `get_mana_cost`)

`card_db.py` already has `_type_line` populated but no public `get_type_line()`. The `get_subtypes()` function uses it internally. We add the public accessor.

- [ ] **Step 1: Write the failing test**

Create `game_advisor/tests/test_card_helpers_card_db.py`:

```python
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent.parent))
import card_db


def test_get_type_line_returns_cached_value():
    card_db._type_line["lightning bolt"] = "Instant"
    result = card_db.get_type_line("Lightning Bolt")
    assert result == "Instant"


def test_get_type_line_returns_empty_for_unknown():
    result = card_db.get_type_line("Nonexistent Card XYZZY")
    assert result == ""
```

- [ ] **Step 2: Run to verify it fails**

```bash
cd "C:/Users/pilot/OneDrive/Documents/Python Scripts/mtga_draft_helper"
python -m pytest game_advisor/tests/test_card_helpers_card_db.py -v
```

Expected: `AttributeError: module 'card_db' has no attribute 'get_type_line'`

- [ ] **Step 3: Add `get_type_line` to `card_db.py`**

Insert after the `get_mana_cost` function (after line 99):

```python
def get_type_line(card_name: str) -> str:
    """Return full type line e.g. 'Creature — Angel Warrior'. Empty string if unknown."""
    if not _type_line:
        _load_cache()
    return _type_line.get(card_name.strip().lower(), "")
```

- [ ] **Step 4: Run to verify it passes**

```bash
python -m pytest game_advisor/tests/test_card_helpers_card_db.py -v
```

Expected: 2 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add card_db.py game_advisor/tests/test_card_helpers_card_db.py
git commit -m "feat: add get_type_line to card_db"
```

---

## Task 3: GameState Dataclasses

**Files:**
- Create: `game_advisor/game_state.py`
- Create: `game_advisor/tests/test_game_state.py`

- [ ] **Step 1: Write failing tests**

```python
# game_advisor/tests/test_game_state.py
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
from game_state import BoardCard, HandCard, Player, RuleAlert, GameState


def test_board_card_defaults():
    card = BoardCard(
        name="Goblin Blast-Runner",
        arena_id="93913",
        instance_id=101,
        power=2,
        toughness=1,
        keywords=["haste"],
    )
    assert card.tapped is False
    assert card.attacking is False


def test_hand_card_defaults():
    card = HandCard(
        name="Lightning Strike",
        arena_id="67890",
        instance_id=201,
        mana_cost="{1}{R}",
        cmc=2,
        colors=["R"],
    )
    assert card.castable is False


def test_player_defaults():
    player = Player(seat_id=1, life=20)
    assert player.board == []
    assert player.hand == []
    assert player.mana_available == 0
    assert player.mana_colors == []


def test_rule_alert_fields():
    alert = RuleAlert(severity="DANGER", message="You have lethal!")
    assert alert.severity == "DANGER"
    assert alert.message == "You have lethal!"


def test_game_state_construction():
    you = Player(seat_id=1, life=18)
    opp = Player(seat_id=2, life=14)
    state = GameState(turn=4, phase="Main 1", active_seat=1, you=you, opponent=opp)
    assert state.turn == 4
    assert state.recent_events == []
    assert state.game_id == ""
```

- [ ] **Step 2: Run to verify it fails**

```bash
python -m pytest game_advisor/tests/test_game_state.py -v
```

Expected: `ModuleNotFoundError: No module named 'game_state'`

- [ ] **Step 3: Create `game_advisor/game_state.py`**

```python
from __future__ import annotations
from dataclasses import dataclass, field


@dataclass
class BoardCard:
    name: str
    arena_id: str
    instance_id: int
    power: int
    toughness: int
    keywords: list[str]
    tapped: bool = False
    attacking: bool = False


@dataclass
class HandCard:
    name: str
    arena_id: str
    instance_id: int
    mana_cost: str     # e.g. "{1}{R}"
    cmc: int
    colors: list[str]  # e.g. ["R"]
    castable: bool = False


@dataclass
class Player:
    seat_id: int
    life: int
    board: list[BoardCard] = field(default_factory=list)
    hand: list[HandCard] = field(default_factory=list)
    mana_available: int = 0
    mana_colors: list[str] = field(default_factory=list)


@dataclass
class RuleAlert:
    severity: str   # "DANGER", "WARNING", "INFO"
    message: str


@dataclass
class GameState:
    turn: int
    phase: str
    active_seat: int
    you: Player
    opponent: Player
    recent_events: list[str] = field(default_factory=list)
    game_id: str = ""
```

- [ ] **Step 4: Run to verify it passes**

```bash
python -m pytest game_advisor/tests/test_game_state.py -v
```

Expected: 5 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add game_advisor/game_state.py game_advisor/tests/test_game_state.py
git commit -m "feat: add GameState dataclasses"
```

---

## Task 4: Card Helpers (keywords and colors)

**Files:**
- Create: `game_advisor/card_helpers.py`
- Create: `game_advisor/tests/test_card_helpers.py`

- [ ] **Step 1: Write failing tests**

```python
# game_advisor/tests/test_card_helpers.py
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent.parent))
import card_db
import card_helpers


def test_get_colors_red_card():
    card_db._mana_cost["lightning strike"] = "{1}{R}"
    result = card_helpers.get_colors("Lightning Strike")
    assert result == ["R"]


def test_get_colors_multicolor():
    card_db._mana_cost["dreadbore"] = "{B}{R}"
    result = card_helpers.get_colors("Dreadbore")
    assert sorted(result) == ["B", "R"]


def test_get_colors_colorless():
    card_db._mana_cost["sol ring"] = "{1}"
    result = card_helpers.get_colors("Sol Ring")
    assert result == []


def test_get_keywords_flying():
    card_db._oracle["warden of the inner sky"] = "Flying\nWard {1}"
    result = card_helpers.get_keywords("Warden of the Inner Sky")
    assert "flying" in result


def test_get_keywords_deathtouch_and_lifelink():
    card_db._oracle["vampire nighthawk"] = "Flying, Deathtouch, Lifelink"
    result = card_helpers.get_keywords("Vampire Nighthawk")
    assert "deathtouch" in result
    assert "lifelink" in result


def test_get_keywords_empty_for_unknown():
    result = card_helpers.get_keywords("Nonexistent Card XYZZY")
    assert result == []
```

- [ ] **Step 2: Run to verify it fails**

```bash
python -m pytest game_advisor/tests/test_card_helpers.py -v
```

Expected: `ModuleNotFoundError: No module named 'card_helpers'`

- [ ] **Step 3: Create `game_advisor/card_helpers.py`**

```python
"""
Wrappers around parent card_db that provide keyword and color extraction.
card_db stores oracle text and mana cost but doesn't parse them into
structured keyword lists or color lists — that's done here.
"""
import re
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
import card_db

_COLOR_SYMBOLS = {"W", "U", "B", "R", "G"}

_KEYWORDS = [
    "flying", "trample", "lifelink", "deathtouch", "haste",
    "first strike", "double strike", "menace", "vigilance",
    "reach", "indestructible", "hexproof", "ward", "flash",
    "protection", "persist", "undying", "landfall",
]


def get_colors(card_name: str) -> list[str]:
    """Return sorted list of color symbols from a card's mana cost. e.g. ['R'] for {1}{R}."""
    mc = card_db.get_mana_cost(card_name)
    pips = re.findall(r'\{([A-Z])\}', mc)
    return sorted(set(p for p in pips if p in _COLOR_SYMBOLS))


def get_keywords(card_name: str) -> list[str]:
    """Return list of keyword abilities found in oracle text (lowercase)."""
    oracle = card_db.get_oracle(card_name).lower()
    if not oracle:
        return []
    return [kw for kw in _KEYWORDS if kw in oracle]
```

- [ ] **Step 4: Run to verify it passes**

```bash
python -m pytest game_advisor/tests/test_card_helpers.py -v
```

Expected: 6 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add game_advisor/card_helpers.py game_advisor/tests/test_card_helpers.py
git commit -m "feat: add card_helpers with get_colors and get_keywords"
```

---

## Task 5: Log Scanner

**Files:**
- Create: `game_advisor/log_scanner.py`
- Create: `game_advisor/tests/test_log_scanner.py`

- [ ] **Step 1: Write failing tests**

```python
# game_advisor/tests/test_log_scanner.py
import json
import sys
import pathlib
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent.parent))

import card_db
from log_scanner import GameLogScanner
from game_state import GameState


# --- Fixture: minimal valid GRE game state message ---
def _make_gre_log_line(turn: int = 3, your_life: int = 18, opp_life: int = 20) -> str:
    payload = {
        "greToClientEvent": {
            "greToClientMessages": [
                {
                    "type": "GREMessageType_GameStateMessage",
                    "msgId": 5,
                    "gameStateMessage": {
                        "type": "GameStateType_Full",
                        "gameStateId": 12,
                        "gameState": {
                            "turnInfo": {
                                "phase": "Phase_Main",
                                "step": "Step_Main",
                                "turnNumber": turn,
                                "activePlayer": 1,
                                "decisionPlayer": 1,
                            },
                            "zones": [
                                {
                                    "zoneId": 28,
                                    "type": "ZoneType_Hand",
                                    "playerIds": [1],
                                    "objectInstanceIds": [101],
                                },
                                {
                                    "zoneId": 29,
                                    "type": "ZoneType_Battlefield",
                                    "playerIds": [2],
                                    "objectInstanceIds": [105],
                                },
                            ],
                            "gameObjects": [
                                {
                                    "instanceId": 101,
                                    "grpId": 12345,
                                    "type": "GameObjectType_Card",
                                    "zoneId": 28,
                                    "controllerSeatId": 1,
                                    "ownerSeatId": 1,
                                    "power": {"value": 0},
                                    "toughness": {"value": 0},
                                    "isTapped": False,
                                },
                                {
                                    "instanceId": 105,
                                    "grpId": 33333,
                                    "type": "GameObjectType_Card",
                                    "zoneId": 29,
                                    "controllerSeatId": 2,
                                    "ownerSeatId": 2,
                                    "power": {"value": 2},
                                    "toughness": {"value": 2},
                                    "isTapped": False,
                                },
                            ],
                            "players": [
                                {"systemSeatNumber": 1, "lifeTotal": your_life},
                                {"systemSeatNumber": 2, "lifeTotal": opp_life},
                            ],
                        }
                    },
                }
            ]
        }
    }
    return json.dumps(payload)


def test_scanner_fires_on_state_change(tmp_path):
    # Teach card_db the test IDs
    card_db._cache["12345"] = "Lightning Strike"
    card_db._cache["33333"] = "Goblin Guide"
    card_db._mana_cost["lightning strike"] = "{1}{R}"
    card_db._cmc["lightning strike"] = 2
    card_db._oracle["lightning strike"] = "Lightning Strike deals 3 damage to any target."
    card_db._type_line["goblin guide"] = "Creature — Goblin Scout"
    card_db._oracle["goblin guide"] = "Haste"

    log_file = tmp_path / "Player.log"
    log_file.write_text(_make_gre_log_line(turn=3, your_life=18, opp_life=20))

    received: list[GameState] = []
    scanner = GameLogScanner(log_path=str(log_file))
    scanner.on_state_change = lambda s: received.append(s)
    scanner.poll()

    assert len(received) == 1
    state = received[0]
    assert state.turn == 3
    assert state.you.life == 18
    assert state.opponent.life == 20


def test_scanner_parses_opponent_board(tmp_path):
    card_db._cache["33333"] = "Goblin Guide"
    card_db._type_line["goblin guide"] = "Creature — Goblin Scout"
    card_db._oracle["goblin guide"] = "Haste"

    log_file = tmp_path / "Player.log"
    log_file.write_text(_make_gre_log_line())

    received: list[GameState] = []
    scanner = GameLogScanner(log_path=str(log_file))
    scanner.on_state_change = lambda s: received.append(s)
    scanner.poll()

    opp_board = received[0].opponent.board
    assert len(opp_board) == 1
    assert opp_board[0].name == "Goblin Guide"
    assert opp_board[0].power == 2
    assert opp_board[0].toughness == 2


def test_scanner_skips_malformed_json(tmp_path):
    log_file = tmp_path / "Player.log"
    log_file.write_text('{"greToClientEvent": INVALID JSON HERE}')

    received: list[GameState] = []
    scanner = GameLogScanner(log_path=str(log_file))
    scanner.on_state_change = lambda s: received.append(s)
    scanner.poll()  # should not raise

    assert received == []


def test_scanner_skips_missing_file():
    scanner = GameLogScanner(log_path="/nonexistent/Player.log")
    scanner.on_state_change = lambda s: None
    scanner.poll()  # should not raise
```

- [ ] **Step 2: Run to verify it fails**

```bash
python -m pytest game_advisor/tests/test_log_scanner.py -v
```

Expected: `ModuleNotFoundError: No module named 'log_scanner'`

- [ ] **Step 3: Create `game_advisor/log_scanner.py`**

```python
"""
Tails Player.log for GREMessageType_GameStateMessage payloads and fires
on_state_change(GameState) whenever the game state updates.

MTGA writes GRE events as JSON on lines containing 'greToClientEvent'.
Example line:
  [Client GRE] 4/5/2026 ... {"greToClientEvent":{"greToClientMessages":[...]}}
"""
from __future__ import annotations

import json
import os
import sys
import pathlib
from typing import Callable, Optional

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
import card_db
import config
from game_state import BoardCard, GameState, HandCard, Player
from card_helpers import get_colors, get_keywords


_BASIC_LAND_TYPES = {
    "plains": ["W"], "island": ["U"], "swamp": ["B"],
    "mountain": ["R"], "forest": ["G"],
}


class GameLogScanner:
    def __init__(self, log_path: str = config.ARENA_LOG_PATH):
        self.log_path = log_path
        self._file_pos: int = 0
        self._last_mtime: float = 0

        # Callbacks — assign before calling poll()
        self.on_state_change: Optional[Callable[[GameState], None]] = None

    def poll(self) -> None:
        """Read new log content since last poll and process any game state messages."""
        try:
            mtime = os.path.getmtime(self.log_path)
        except FileNotFoundError:
            return
        if mtime == self._last_mtime:
            return
        self._last_mtime = mtime

        try:
            with open(self.log_path, "r", encoding="utf-8", errors="replace") as f:
                f.seek(self._file_pos)
                new_content = f.read()
                self._file_pos = f.tell()
        except OSError:
            return

        self._process_content(new_content)

    def _process_content(self, content: str) -> None:
        for line in content.splitlines():
            if "greToClientEvent" not in line:
                continue
            json_str = _extract_json(line)
            if json_str:
                self._handle_gre_json(json_str)

    def _handle_gre_json(self, json_str: str) -> None:
        try:
            data = json.loads(json_str)
        except json.JSONDecodeError:
            return

        messages = data.get("greToClientEvent", {}).get("greToClientMessages", [])
        for msg in messages:
            if msg.get("type") != "GREMessageType_GameStateMessage":
                continue
            gs_raw = msg.get("gameStateMessage", {}).get("gameState", {})
            if not gs_raw:
                continue
            state = _parse_game_state(gs_raw)
            if state and self.on_state_change:
                self.on_state_change(state)


def _extract_json(line: str) -> Optional[str]:
    """Find the first '{' in a log line and return the JSON substring."""
    idx = line.find("{")
    if idx == -1:
        return None
    candidate = line[idx:]
    try:
        json.loads(candidate)
        return candidate
    except json.JSONDecodeError:
        return None


def _parse_game_state(gs: dict) -> Optional[GameState]:
    turn_info = gs.get("turnInfo", {})
    turn = turn_info.get("turnNumber", 0)
    phase = _normalize_phase(turn_info.get("phase", ""), turn_info.get("step", ""))
    active_seat = turn_info.get("activePlayer", config.PLAYER_SEAT_ID)

    players_raw = gs.get("players", [])
    if len(players_raw) < 2:
        return None

    seat = config.PLAYER_SEAT_ID
    you_raw = next((p for p in players_raw if p.get("systemSeatNumber") == seat), players_raw[0])
    opp_raw = next((p for p in players_raw if p.get("systemSeatNumber") != seat), players_raw[1])

    zones = {z["zoneId"]: z for z in gs.get("zones", [])}
    objects = {o["instanceId"]: o for o in gs.get("gameObjects", [])}

    you = _build_player(you_raw, zones, objects, is_you=True)
    opp = _build_player(opp_raw, zones, objects, is_you=False)

    return GameState(turn=turn, phase=phase, active_seat=active_seat, you=you, opponent=opp)


def _build_player(raw: dict, zones: dict, objects: dict, is_you: bool) -> Player:
    seat_id = raw.get("systemSeatNumber", 1)
    life = raw.get("lifeTotal", 20)
    board_cards: list[BoardCard] = []
    hand_cards: list[HandCard] = []

    for zone in zones.values():
        if seat_id not in zone.get("playerIds", []):
            continue
        zone_type = zone.get("type", "")
        for iid in zone.get("objectInstanceIds", []):
            obj = objects.get(iid)
            if not obj:
                continue
            arena_id = str(obj.get("grpId", ""))
            name = card_db._cache.get(arena_id) or f"Unknown({arena_id})"
            power = obj.get("power", {}).get("value", 0)
            toughness = obj.get("toughness", {}).get("value", 0)
            keywords = get_keywords(name)
            tapped = obj.get("isTapped", False)
            attacking = obj.get("attackState", "") == "AttackState_Attacking"

            if zone_type == "ZoneType_Battlefield":
                board_cards.append(BoardCard(
                    name=name, arena_id=arena_id, instance_id=iid,
                    power=power, toughness=toughness, keywords=keywords,
                    tapped=tapped, attacking=attacking,
                ))
            elif zone_type == "ZoneType_Hand" and is_you:
                mana_cost = card_db.get_mana_cost(name)
                cmc = card_db.get_cmc(name)
                colors = get_colors(name)
                hand_cards.append(HandCard(
                    name=name, arena_id=arena_id, instance_id=iid,
                    mana_cost=mana_cost, cmc=cmc, colors=colors,
                ))

    # Compute available mana from untapped lands on your board
    mana_colors: list[str] = []
    untapped_land_count = 0
    for card in board_cards:
        type_line = card_db.get_type_line(card.name).lower()
        if "land" not in type_line or card.tapped:
            continue
        untapped_land_count += 1
        # Basic land colors from name
        base = card.name.lower().replace("snow-covered ", "")
        if base in _BASIC_LAND_TYPES:
            mana_colors.extend(_BASIC_LAND_TYPES[base])
        else:
            # Non-basic: use color identity from mana cost of the card itself
            mana_colors.extend(get_colors(card.name))

    # Mark castable hand cards
    available_color_set = set(mana_colors)
    for hc in hand_cards:
        can_afford = hc.cmc <= untapped_land_count
        has_colors = all(c in available_color_set for c in hc.colors)
        hc.castable = can_afford and has_colors

    return Player(
        seat_id=seat_id,
        life=life,
        board=board_cards,
        hand=hand_cards,
        mana_available=untapped_land_count,
        mana_colors=mana_colors,
    )


def _normalize_phase(phase: str, step: str) -> str:
    if phase == "Phase_Beginning":
        return "Beginning"
    if phase == "Phase_Main":
        return "Main 2" if "Post" in step else "Main 1"
    if phase == "Phase_Combat":
        return "Combat"
    if phase == "Phase_Ending":
        return "End"
    return phase.replace("Phase_", "")
```

- [ ] **Step 4: Run to verify it passes**

```bash
python -m pytest game_advisor/tests/test_log_scanner.py -v
```

Expected: 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add game_advisor/log_scanner.py game_advisor/tests/test_log_scanner.py
git commit -m "feat: add game log scanner for GRE game state messages"
```

---

## Task 6: Rule Engine

**Files:**
- Create: `game_advisor/rule_engine.py`
- Create: `game_advisor/tests/test_rule_engine.py`

- [ ] **Step 1: Write failing tests**

```python
# game_advisor/tests/test_rule_engine.py
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
from game_state import BoardCard, GameState, HandCard, Player, RuleAlert
import rule_engine


def _make_creature(name: str, power: int, toughness: int, keywords=None,
                   tapped=False, attacking=False) -> BoardCard:
    return BoardCard(
        name=name, arena_id="0", instance_id=1,
        power=power, toughness=toughness,
        keywords=keywords or [],
        tapped=tapped, attacking=attacking,
    )


def _make_hand_card(name: str, cmc: int, colors: list[str],
                    castable: bool = True) -> HandCard:
    return HandCard(
        name=name, arena_id="0", instance_id=2,
        mana_cost="", cmc=cmc, colors=colors, castable=castable,
    )


def _make_state(your_board=None, opp_board=None, your_hand=None,
                your_life=20, opp_life=20, mana_available=3,
                mana_colors=None) -> GameState:
    you = Player(
        seat_id=1, life=your_life,
        board=your_board or [],
        hand=your_hand or [],
        mana_available=mana_available,
        mana_colors=mana_colors or ["R", "R", "W"],
    )
    opp = Player(seat_id=2, life=opp_life, board=opp_board or [], hand=[])
    return GameState(turn=4, phase="Main 1", active_seat=1, you=you, opponent=opp)


# --- Lethal detection ---

def test_lethal_when_total_power_equals_life():
    your_board = [_make_creature("A", 3, 3), _make_creature("B", 2, 2)]
    state = _make_state(your_board=your_board, opp_life=5)
    alerts = rule_engine.check_lethal(state)
    dangers = [a for a in alerts if a.severity == "DANGER"]
    assert any("lethal" in a.message.lower() for a in dangers)


def test_no_lethal_when_power_less_than_life():
    your_board = [_make_creature("A", 2, 2)]
    state = _make_state(your_board=your_board, opp_life=20)
    alerts = rule_engine.check_lethal(state)
    dangers = [a for a in alerts if a.severity == "DANGER" and "lethal" in a.message.lower()]
    assert dangers == []


def test_tapped_creatures_dont_count_for_lethal():
    your_board = [_make_creature("A", 10, 10, tapped=True)]
    state = _make_state(your_board=your_board, opp_life=5)
    alerts = rule_engine.check_lethal(state)
    dangers = [a for a in alerts if a.severity == "DANGER" and "lethal" in a.message.lower()]
    assert dangers == []


# --- Threat ranking ---

def test_flying_creature_ranked_as_top_threat():
    opp_board = [
        _make_creature("Warden", 2, 2, keywords=["flying"]),
        _make_creature("Goblin", 1, 1),
    ]
    state = _make_state(opp_board=opp_board)
    alerts = rule_engine.check_threats(state)
    threat_alert = next((a for a in alerts if "Warden" in a.message), None)
    assert threat_alert is not None
    assert threat_alert.severity in ("WARNING", "DANGER")


def test_empty_opp_board_no_threat_alerts():
    state = _make_state(opp_board=[])
    alerts = rule_engine.check_threats(state)
    assert alerts == []


# --- Combat math ---

def test_suicidal_attack_flagged():
    your_board = [_make_creature("My 1/1", 1, 1)]
    opp_board = [_make_creature("Opp 3/3", 3, 3)]
    state = _make_state(your_board=your_board, opp_board=opp_board)
    alerts = rule_engine.check_combat(state)
    warnings = [a for a in alerts if "1/1" in a.message or "suicidal" in a.message.lower()
                or "don't attack" in a.message.lower()]
    assert warnings != []


def test_favorable_attack_flagged():
    your_board = [_make_creature("My 3/3", 3, 3)]
    opp_board = [_make_creature("Opp 1/1", 1, 1)]
    state = _make_state(your_board=your_board, opp_board=opp_board)
    alerts = rule_engine.check_combat(state)
    infos = [a for a in alerts if a.severity == "INFO"]
    assert infos != []


# --- Removal targeting ---

def test_removal_target_flagged_when_castable():
    your_hand = [
        _make_hand_card("Lightning Strike", cmc=2, colors=["R"], castable=True)
    ]
    opp_board = [_make_creature("Warden", 2, 2, keywords=["flying"])]
    state = _make_state(your_hand=your_hand, opp_board=opp_board)

    import card_db
    card_db._oracle["lightning strike"] = "Lightning Strike deals 3 damage to any target."

    alerts = rule_engine.check_removal(state)
    assert any("Lightning Strike" in a.message for a in alerts)


def test_no_removal_alert_when_hand_is_empty():
    state = _make_state(your_hand=[], opp_board=[_make_creature("X", 3, 3)])
    alerts = rule_engine.check_removal(state)
    assert alerts == []
```

- [ ] **Step 2: Run to verify it fails**

```bash
python -m pytest game_advisor/tests/test_rule_engine.py -v
```

Expected: `ModuleNotFoundError: No module named 'rule_engine'`

- [ ] **Step 3: Create `game_advisor/rule_engine.py`**

```python
"""
Synchronous rule-based checks that run on every game state update.
Returns a list of RuleAlert objects for immediate display in the dashboard.
"""
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
import card_db
from game_state import BoardCard, GameState, HandCard, RuleAlert

_KEYWORD_MULTIPLIERS: dict[str, float] = {
    "flying": 1.5,
    "trample": 1.2,
    "lifelink": 1.3,
    "deathtouch": 1.4,
    "haste": 1.3,
    "first strike": 1.2,
    "double strike": 1.6,
    "menace": 1.2,
    "indestructible": 1.5,
    "vigilance": 1.1,
}

_REMOVAL_ORACLE_MARKERS = [
    "deals", "damage to any target", "damage to target creature",
    "destroy target", "exile target",
]


def check_lethal(state: GameState) -> list[RuleAlert]:
    """Fire DANGER if your untapped creatures can deal >= opponent life total."""
    untapped = [c for c in state.you.board if not c.tapped]
    total_power = sum(c.power for c in untapped)
    if untapped and total_power >= state.opponent.life:
        names = ", ".join(c.name for c in untapped)
        return [RuleAlert(
            severity="DANGER",
            message=f"You have lethal — attack with: {names} ({total_power} power vs {state.opponent.life} life)",
        )]
    return []


def check_threats(state: GameState) -> list[RuleAlert]:
    """Rank opponent creatures by threat score and flag the top threat."""
    if not state.opponent.board:
        return []
    scored = [(c, _threat_score(c)) for c in state.opponent.board]
    scored.sort(key=lambda x: x[1], reverse=True)
    top, score = scored[0]
    severity = "DANGER" if score >= 4.0 else "WARNING"
    kw_str = (", ".join(top.keywords)) if top.keywords else "no keywords"
    return [RuleAlert(
        severity=severity,
        message=f"Top threat: {top.name} ({top.power}/{top.toughness}, {kw_str}) — score {score:.1f}",
    )]


def check_combat(state: GameState) -> list[RuleAlert]:
    """Flag suicidal attacks and favorable attack opportunities."""
    alerts: list[RuleAlert] = []
    your_attackers = [c for c in state.you.board if not c.tapped]
    opp_blockers = state.opponent.board

    for attacker in your_attackers:
        best_block = _find_best_blocker(attacker, opp_blockers)
        if best_block is None:
            continue
        attacker_survives = attacker.toughness > best_block.power or "indestructible" in attacker.keywords
        blocker_dies = best_block.toughness <= attacker.power or "deathtouch" in attacker.keywords

        if not attacker_survives and not blocker_dies:
            alerts.append(RuleAlert(
                severity="WARNING",
                message=f"Don't attack with {attacker.name} ({attacker.power}/{attacker.toughness}) — loses to {best_block.name} ({best_block.power}/{best_block.toughness})",
            ))
        elif blocker_dies and attacker_survives:
            alerts.append(RuleAlert(
                severity="INFO",
                message=f"Favorable attack: {attacker.name} kills {best_block.name} and survives",
            ))

    return alerts


def check_removal(state: GameState) -> list[RuleAlert]:
    """Flag when a castable removal spell can kill the top threat."""
    if not state.opponent.board or not state.you.hand:
        return []

    top_threat = max(state.opponent.board, key=_threat_score)
    alerts: list[RuleAlert] = []

    for card in state.you.hand:
        if not card.castable:
            continue
        oracle = card_db.get_oracle(card.name).lower()
        if not oracle:
            continue
        is_removal = any(marker in oracle for marker in _REMOVAL_ORACLE_MARKERS)
        if is_removal:
            alerts.append(RuleAlert(
                severity="INFO",
                message=f"{card.name} can remove top threat {top_threat.name} ({top_threat.power}/{top_threat.toughness})",
            ))
            break  # Only flag once

    return alerts


def run_all(state: GameState) -> list[RuleAlert]:
    """Run all checks and return combined alerts, most severe first."""
    alerts: list[RuleAlert] = []
    alerts.extend(check_lethal(state))
    alerts.extend(check_threats(state))
    alerts.extend(check_removal(state))
    alerts.extend(check_combat(state))
    return alerts


def _threat_score(card: BoardCard) -> float:
    score = float(card.power)
    for kw in card.keywords:
        score *= _KEYWORD_MULTIPLIERS.get(kw, 1.0)
    return score


def _find_best_blocker(attacker: BoardCard, blockers: list[BoardCard]) -> BoardCard | None:
    """Find the blocker most likely to be assigned — highest power blocker that can legally block."""
    # Flying attackers can only be blocked by flying/reach creatures
    if "flying" in attacker.keywords:
        valid = [b for b in blockers if "flying" in b.keywords or "reach" in b.keywords]
    else:
        valid = [b for b in blockers if "flying" not in b.keywords]
    if not valid:
        return None
    return max(valid, key=lambda b: b.power)
```

- [ ] **Step 4: Run to verify it passes**

```bash
python -m pytest game_advisor/tests/test_rule_engine.py -v
```

Expected: 9 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add game_advisor/rule_engine.py game_advisor/tests/test_rule_engine.py
git commit -m "feat: add rule engine with lethal, threats, combat, and removal checks"
```

---

## Task 7: LLM Advisor

**Files:**
- Create: `game_advisor/llm_advisor.py`
- Create: `game_advisor/tests/test_llm_advisor.py`

- [ ] **Step 1: Write failing tests**

```python
# game_advisor/tests/test_llm_advisor.py
import sys, pathlib, time
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
from unittest.mock import MagicMock, patch
from game_state import BoardCard, GameState, HandCard, Player
from llm_advisor import LLMAdvisor


def _make_state() -> GameState:
    attacker = BoardCard(
        name="Goblin Blast-Runner", arena_id="0", instance_id=1,
        power=2, toughness=1, keywords=["haste"],
    )
    spell = HandCard(
        name="Lightning Strike", arena_id="1", instance_id=2,
        mana_cost="{1}{R}", cmc=2, colors=["R"], castable=True,
    )
    you = Player(seat_id=1, life=18, board=[attacker], hand=[spell],
                 mana_available=2, mana_colors=["R", "R"])
    opp_creature = BoardCard(
        name="Warden of the Inner Sky", arena_id="2", instance_id=3,
        power=2, toughness=2, keywords=["flying"],
    )
    opp = Player(seat_id=2, life=20, board=[opp_creature], hand=[])
    return GameState(turn=3, phase="Main 1", active_seat=1, you=you, opponent=opp)


def _mock_openai_response(text: str) -> MagicMock:
    msg = MagicMock()
    msg.content = text
    choice = MagicMock()
    choice.message = msg
    response = MagicMock()
    response.choices = [choice]
    return response


def test_request_advice_sync_returns_text():
    state = _make_state()
    with patch("llm_advisor.openai.OpenAI") as mock_cls:
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        mock_client.chat.completions.create.return_value = (
            _mock_openai_response("Kill the Warden with Lightning Strike.")
        )
        advisor = LLMAdvisor(api_key="test-key")
        result = advisor._call_api(state)
        assert "Warden" in result or "Lightning" in result or len(result) > 0


def test_caching_skips_duplicate_api_call():
    state = _make_state()
    with patch("llm_advisor.openai.OpenAI") as mock_cls:
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        mock_client.chat.completions.create.return_value = (
            _mock_openai_response("Attack with Blast-Runner.")
        )
        advisor = LLMAdvisor(api_key="test-key")
        result1 = advisor._call_api(state)
        result2 = advisor._call_api(state)  # same state — should use cache
        assert mock_client.chat.completions.create.call_count == 1
        assert result1 == result2


def test_rate_limit_blocks_rapid_calls():
    state1 = _make_state()
    # Slightly different state (different life total) to bypass state-hash cache
    you2 = Player(seat_id=1, life=15, board=[], hand=[], mana_available=0, mana_colors=[])
    opp2 = Player(seat_id=2, life=20, board=[], hand=[])
    state2 = GameState(turn=3, phase="Main 1", active_seat=1, you=you2, opponent=opp2)

    with patch("llm_advisor.openai.OpenAI") as mock_cls:
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        mock_client.chat.completions.create.return_value = (
            _mock_openai_response("Hold your spells.")
        )
        advisor = LLMAdvisor(api_key="test-key", min_interval_seconds=60)
        advisor._call_api(state1)
        result2 = advisor._call_api(state2)  # rate-limited — same cached result
        assert mock_client.chat.completions.create.call_count == 1
        assert result2 is not None


def test_api_timeout_returns_fallback():
    state = _make_state()
    with patch("llm_advisor.openai.OpenAI") as mock_cls:
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        mock_client.chat.completions.create.side_effect = Exception("timeout")
        advisor = LLMAdvisor(api_key="test-key")
        result = advisor._call_api(state)
        assert result == LLMAdvisor.OFFLINE_MESSAGE


def test_build_prompt_contains_key_info():
    state = _make_state()
    advisor = LLMAdvisor(api_key="test-key")
    prompt = advisor._build_prompt(state)
    assert "Turn 3" in prompt
    assert "18" in prompt           # your life
    assert "Goblin Blast-Runner" in prompt
    assert "Lightning Strike" in prompt
    assert "Warden of the Inner Sky" in prompt
```

- [ ] **Step 2: Run to verify it fails**

```bash
python -m pytest game_advisor/tests/test_llm_advisor.py -v
```

Expected: `ModuleNotFoundError: No module named 'llm_advisor'`

- [ ] **Step 3: Create `game_advisor/llm_advisor.py`**

```python
"""
Async GPT-4o advisor. Fires in a background thread on significant state
changes. Caches responses by state hash to avoid redundant API calls.
Rate-limited to at most one call per min_interval_seconds.
"""
from __future__ import annotations

import hashlib
import sys
import pathlib
import threading
import time
from typing import Callable, Optional

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
import config
import openai

from game_state import GameState


class LLMAdvisor:
    OFFLINE_MESSAGE = "Advisor offline — rule alerts active."

    def __init__(
        self,
        api_key: str = config.OPENAI_API_KEY,
        model: str = config.OPENAI_MODEL,
        timeout: int = config.LLM_TIMEOUT_SECONDS,
        min_interval_seconds: int = config.LLM_MIN_INTERVAL_SECONDS,
    ):
        self._client = openai.OpenAI(api_key=api_key)
        self._model = model
        self._timeout = timeout
        self._min_interval = min_interval_seconds
        self._cache: dict[str, str] = {}     # state_hash -> advice text
        self._last_call_time: float = 0.0
        self._last_advice: str = ""
        self._lock = threading.Lock()

    def request_advice_async(
        self,
        state: GameState,
        on_complete: Callable[[str], None],
    ) -> None:
        """Fire an async advice request. Calls on_complete(text) when done."""
        def run():
            result = self._call_api(state)
            on_complete(result)

        threading.Thread(target=run, daemon=True).start()

    def _call_api(self, state: GameState) -> str:
        """Call GPT-4o synchronously. Returns cached or rate-limited result when applicable."""
        with self._lock:
            state_hash = _state_hash(state)

            # Return cached response for identical state
            if state_hash in self._cache:
                return self._cache[state_hash]

            # Rate limit: return last advice if called too soon
            now = time.monotonic()
            if now - self._last_call_time < self._min_interval and self._last_advice:
                return self._last_advice

            prompt = self._build_prompt(state)
            try:
                response = self._client.chat.completions.create(
                    model=self._model,
                    messages=[
                        {"role": "system", "content": (
                            "You are an expert Magic: The Gathering advisor. "
                            "Give concise, actionable advice in 3 numbered points. "
                            "Be specific about card names and combat math."
                        )},
                        {"role": "user", "content": prompt},
                    ],
                    timeout=self._timeout,
                    max_tokens=300,
                )
                advice = response.choices[0].message.content.strip()
            except Exception:
                advice = self.OFFLINE_MESSAGE

            self._cache[state_hash] = advice
            self._last_call_time = time.monotonic()
            self._last_advice = advice
            return advice

    def _build_prompt(self, state: GameState) -> str:
        your_hand = ", ".join(
            f"{c.name} ({c.mana_cost}){' [castable]' if c.castable else ''}"
            for c in state.you.hand
        ) or "Empty"
        your_board = ", ".join(
            f"{c.name} ({c.power}/{c.toughness}{(' ' + ' '.join(c.keywords)) if c.keywords else ''})"
            for c in state.you.board
        ) or "Empty"
        opp_board = ", ".join(
            f"{c.name} ({c.power}/{c.toughness}{(' ' + ' '.join(c.keywords)) if c.keywords else ''})"
            for c in state.opponent.board
        ) or "Empty"
        recent = "; ".join(state.recent_events[-3:]) if state.recent_events else "None"

        return (
            f"Turn {state.turn} | You: {state.you.life} life | "
            f"Opponent: {state.opponent.life} life | Phase: {state.phase}\n\n"
            f"YOUR HAND: {your_hand}\n"
            f"YOUR BOARD: {your_board}\n"
            f"OPPONENT BOARD: {opp_board}\n"
            f"Recent events: {recent}\n\n"
            "Answer briefly:\n"
            "1. Best play this turn?\n"
            "2. Combat recommendation?\n"
            "3. Highest priority threat to address?"
        )


def _state_hash(state: GameState) -> str:
    key = (
        state.turn,
        state.phase,
        state.you.life,
        state.opponent.life,
        tuple(sorted(c.name for c in state.you.hand)),
        tuple(sorted(c.name for c in state.you.board)),
        tuple(sorted(c.name for c in state.opponent.board)),
    )
    return hashlib.md5(str(key).encode()).hexdigest()
```

- [ ] **Step 4: Run to verify it passes**

```bash
python -m pytest game_advisor/tests/test_llm_advisor.py -v
```

Expected: 5 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add game_advisor/llm_advisor.py game_advisor/tests/test_llm_advisor.py
git commit -m "feat: add GPT-4o LLM advisor with async calls and state-hash caching"
```

---

## Task 8: Dashboard UI

**Files:**
- Create: `game_advisor/dashboard.py`

No unit tests — this is a GUI component. Verify visually by running `python main.py` in Task 10.

- [ ] **Step 1: Create `game_advisor/dashboard.py`**

```python
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
```

- [ ] **Step 2: Commit**

```bash
git add game_advisor/dashboard.py
git commit -m "feat: add tkinter full-dashboard for second monitor"
```

---

## Task 9: Screen Capture Fallback

**Files:**
- Create: `game_advisor/capture.py`
- Create: `game_advisor/calibrate_capture.py`

- [ ] **Step 1: Create `game_advisor/capture.py`**

```python
"""
Screen capture fallback for detecting opponent cards not visible in the log.
Uses mss for screenshot and pytesseract for OCR.
Fuzzy-matches OCR text against known card names from card_db.

Falls back gracefully if tesseract is not installed.
"""
import difflib
import sys
import pathlib
from typing import Optional

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
import config
import card_db

try:
    import mss
    import pytesseract
    from PIL import Image, ImageFilter
    _CAPTURE_AVAILABLE = True
except ImportError:
    _CAPTURE_AVAILABLE = False
    print("[capture] mss/pytesseract/Pillow not available — OCR disabled.")


def capture_opponent_cards() -> list[str]:
    """
    Capture the MTGA window, OCR visible card names on the opponent's side.
    Returns a list of matched card names. Returns [] if OCR is unavailable.
    """
    if not _CAPTURE_AVAILABLE:
        return []
    try:
        return _do_capture()
    except Exception as e:
        print(f"[capture] Error during capture: {e}")
        return []


def _do_capture() -> list[str]:
    region = config.CAPTURE_REGION
    with mss.mss() as sct:
        screenshot = sct.grab(region)

    img = Image.frombytes("RGB", screenshot.size, screenshot.rgb)
    img = img.convert("L")  # grayscale
    img = img.point(lambda p: 255 if p > 128 else 0)  # threshold

    raw_text = pytesseract.image_to_string(img, config="--psm 11")
    lines = [line.strip() for line in raw_text.splitlines() if len(line.strip()) > 3]

    known_names = list(card_db._cache.values())
    matched: list[str] = []
    for line in lines:
        hits = difflib.get_close_matches(
            line, known_names, n=1,
            cutoff=config.OCR_CONFIDENCE_THRESHOLD,
        )
        if hits:
            matched.append(hits[0])

    return list(set(matched))
```

- [ ] **Step 2: Create `game_advisor/calibrate_capture.py`**

```python
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
```

- [ ] **Step 3: Commit**

```bash
git add game_advisor/capture.py game_advisor/calibrate_capture.py
git commit -m "feat: add screen capture OCR fallback for opponent cards"
```

---

## Task 10: Main Entry Point

**Files:**
- Create: `game_advisor/main.py`

- [ ] **Step 1: Create `game_advisor/main.py`**

```python
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

import config
import rule_engine
from log_scanner import GameLogScanner
from llm_advisor import LLMAdvisor
from dashboard import AdvisorDashboard
from capture import capture_opponent_cards
from game_state import GameState


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
    print("[main] Advisor started. Open MTGA and start a game!\n")
    dashboard.run()
    print("\nGoodbye!")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Verify all tests still pass**

```bash
cd "C:/Users/pilot/OneDrive/Documents/Python Scripts/mtga_draft_helper"
python -m pytest game_advisor/tests/ -v
```

Expected: All tests PASS.

- [ ] **Step 3: Run a quick smoke test (manual)**

```bash
cd game_advisor
python main.py
```

Expected: Dashboard window opens on second monitor. Console prints "Waiting for MTGA game...". No import errors. ESC closes the window.

- [ ] **Step 4: Commit**

```bash
git add game_advisor/main.py
git commit -m "feat: add game advisor main entry point"
```

---

## Setup Instructions (for reference)

```bash
cd "C:/Users/pilot/OneDrive/Documents/Python Scripts/mtga_draft_helper/game_advisor"
pip install -r requirements.txt
cp .env.example .env
# Edit .env and add your OpenAI API key

python calibrate_capture.py    # one-time: set MTGA window region
python main.py                 # start the advisor
```

Open MTGA on monitor 1. The advisor dashboard appears on monitor 2 (configured via `ADVISOR_MONITOR_X` in `config.py`). Press `Space` to force a GPT-4o refresh, `R` to resync the log, `ESC` to quit.

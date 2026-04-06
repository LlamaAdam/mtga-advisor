# MTG Arena Game Advisor — Design Spec

**Date:** 2026-04-05
**Status:** Approved

---

## Overview

A standalone Python app (`game_advisor/`) that runs on a second screen during MTGA draft or practice games. It monitors the game in real time, runs instant rule-based checks, and calls GPT-4o for higher-level strategic advice. The existing `mtga_draft_helper` codebase is untouched; the advisor reuses only `card_db.py` for oracle data.

---

## 1. Architecture & File Structure

```
game_advisor/
  main.py              — entry point, wires all components, starts dashboard
  log_scanner.py       — tails Player.log for GRE game state messages
  game_state.py        — dataclasses: GameState, Player, BoardCard, HandCard, RuleAlert
  rule_engine.py       — fast synchronous rule checks (combat, lethal, castability, threats)
  llm_advisor.py       — GPT-4o client, prompt builder, async advice with state-hash caching
  dashboard.py         — tkinter full-dashboard second-screen window
  config.py            — OPENAI_API_KEY from env, monitor position/size, poll intervals
  capture.py           — mss screen capture + pytesseract OCR fallback for unrevealed cards
  calibrate_capture.py — interactive helper to set the MTGA window capture region
```

**Shared from parent folder** (imported via `sys.path` insertion):
- `card_db.py` — Scryfall oracle data: card names, type lines, power/toughness, keywords, mana costs

**New dependencies** (added to `requirements.txt`):
- `openai` — GPT-4o API client
- `python-dotenv` — loads `OPENAI_API_KEY` from `.env` file
- `mss` — fast cross-platform screen capture
- `pytesseract` — OCR for screen capture fallback
- `Pillow` — image processing for OCR pipeline

---

## 2. Game State Tracking

### Log Source

MTGA writes `[Client GRE]` blocks to `Player.log` containing JSON `GREMessageType_GameStateMessage` payloads. These use the same Arena numeric card IDs as the draft system, resolved through `card_db.py`.

### Parsed Data

Each message contains:
- **zones** — `HAND`, `BATTLEFIELD`, `GRAVEYARD`, `EXILE` per player with card instance IDs
- **gameObjects** — card instances: Arena ID, controller seat ID, current power/toughness (post-buff), tapped/attacking/blocking status
- **players** — life totals, mana pools, system seat IDs
- **annotations** — damage events, triggered abilities, +1/+1 counters, combat damage

### GameState Dataclasses

```python
@dataclass
class BoardCard:
    name: str
    arena_id: str
    power: int
    toughness: int
    keywords: list[str]   # flying, trample, etc. from card_db
    tapped: bool
    attacking: bool

@dataclass
class HandCard:
    name: str
    arena_id: str
    mana_cost: str        # e.g. "2R"
    castable: bool        # computed by rule engine vs. available mana

@dataclass
class Player:
    life: int
    mana_available: int
    board: list[BoardCard]
    hand: list[HandCard]  # empty for opponent (populated by OCR when available)

@dataclass
class GameState:
    turn: int
    phase: str            # "Main 1", "Combat", "Main 2", etc.
    active_player: int    # seat ID
    you: Player
    opponent: Player
    recent_events: list[str]   # last 3 game actions as text
```

### Event Detection

The scanner diffs each new `GameState` against the previous one and fires callbacks:
- `on_turn_change(turn, phase)`
- `on_card_played(player, card_name)`
- `on_attack_declared(attackers)`
- `on_state_change(new_state)` — catch-all for dashboard refresh

Unknown Arena IDs are queued to `card_db.pending_unknowns` (same pattern as draft helper).

---

## 3. Rule Engine

All checks are synchronous and run on every `on_state_change` callback. Returns `list[RuleAlert]`.

```python
@dataclass
class RuleAlert:
    severity: str    # "DANGER", "WARNING", "INFO"
    message: str
```

### Checks

**Mana castability**
Count untapped lands on your board → mark each `HandCard.castable`. Considers basic land types for color requirements. Updates the hand display (green = castable, gray = not).

**Combat math**
For each of your untapped creatures, simulate attacks against opponent blockers:
- Trade: both die → flag as "risky trade"
- Favorable: opponent creature dies, yours survives → flag as "good attack"
- Suicidal: your creature dies, opponent's survives → flag as "don't attack with X"

**Lethal detection**
Sum power of all your untapped creatures vs. opponent life total. If ≥ opponent life (accounting for potential blocks), fire `DANGER: You have lethal — attack with all`.

**Threat ranking**
Score each opponent creature:
```
score = power * keyword_multipliers
# flying: ×1.5, trample: ×1.2, lifelink: ×1.3, deathtouch: ×1.4, haste: ×1.3
```
Top threat highlighted red in dashboard.

**Removal targeting**
Cross-reference removal spells in hand (identified by oracle text keywords: "destroy", "exile", "deals X damage") against opponent board. Flag: "Lightning Strike kills [top threat] right now."

---

## 4. LLM Advisor (GPT-4o)

### Trigger Conditions

LLM advice is requested on:
- Turn change
- Opponent plays a spell
- Attack step begins
- User presses `Space` (manual refresh)
- Minimum 8 seconds between calls (rate limit guard)

### Prompt Format

```
Turn {N} | You: {life} life | Opponent: {life} life | Phase: {phase}

YOUR HAND: {card} ({cost}), ...
YOUR BOARD: {card} ({P/T} {keywords}), ...
OPPONENT BOARD: {card} ({P/T} {keywords}), ...

Recent events: {last 3 events}

Answer briefly:
1. Best play this turn?
2. Combat recommendation?
3. Highest priority threat to address?
```

### Async Behavior

- Fires in a background thread via `threading.Thread`
- Dashboard shows "Thinking..." in the advice panel while waiting
- 10-second timeout; on timeout or API error → "Advisor offline — rule alerts active"

### Caching

State hash = `hash((turn, phase, frozenset(your_hand_names), frozenset(your_board), frozenset(opp_board)))`. If hash matches last call, reuse cached response — no new API call.

### Configuration

`OPENAI_API_KEY` read from environment variable (`.env` file supported via `python-dotenv`). Model defaults to `gpt-4o` but configurable in `config.py`.

---

## 5. Dashboard UI

Standard (non-transparent) `tkinter` window on the second monitor. Position and size set in `config.py` via `ADVISOR_MONITOR_X`, `ADVISOR_MONITOR_Y`, `ADVISOR_WIDTH`, `ADVISOR_HEIGHT`.

### Layout

```
┌─────────────────────────────────────────────────┐
│  Turn 4  |  You: 14 ❤  Opp: 12 ❤  |  Main 1   │  ← status bar
├────────────────────┬────────────────────────────┤
│  YOUR BOARD        │  OPPONENT BOARD             │
│  Blast-Runner 2/1  │  ⚠ Warden 2/2 flying [!]  │
│  (haste)           │  Boros Recruit 1/1          │
├────────────────────┴────────────────────────────┤
│  YOUR HAND                                       │
│  [✓] Lightning Strike   2R                       │
│  [✓] Giant Growth       G                        │
│  [✗] Charging Ursari    4G  (need 1 more green)  │
│  [✓] Mountain           —   (land, play it)      │
├─────────────────────────────────────────────────┤
│  ADVICE                                          │
│  ⚡ DANGER: Warden has flying — you can't block  │
│  ⚡ INFO: Lightning Strike kills Warden now      │
│  ────────────────────────────────────────        │
│  GPT-4o: Kill the Warden before it grows out of  │
│  range. Play Mountain first, then Strike. Hold   │
│  Giant Growth as a combat trick next turn.       │
└─────────────────────────────────────────────────┘
```

### Color Coding

- Rule alerts: red = DANGER, yellow = WARNING, blue = INFO
- Hand cards: green text = castable, gray = not castable
- Opponent board: red highlight on top threat

### Keyboard Shortcuts

| Key   | Action                        |
|-------|-------------------------------|
| Space | Force LLM advice refresh      |
| R     | Resync from log               |
| ESC   | Quit                          |

---

## 6. Screen Capture Fallback

Used to detect opponent cards that haven't been played/revealed (not visible in the log).

**Capture:** `mss` screenshots a configurable region of the MTGA window (monitor 1). Region set by running `calibrate_capture.py`, which saves coordinates to `config.py`.

**OCR pipeline:**
1. Capture region → Pillow image → grayscale + threshold
2. `pytesseract` extracts text strings
3. Each string fuzzy-matched against Scryfall card names via `difflib.get_close_matches(n=1, cutoff=0.8)`
4. Matches below 80% confidence discarded

**Poll rate:** Every 3 seconds (vs. 0.5s for log polling) — OCR is expensive.

**Degradation:** If Tesseract is not installed, capture falls back gracefully to log-only mode with a console warning.

---

## 7. Error Handling

| Scenario | Handling |
|----------|----------|
| Malformed GRE JSON in log | Skip block, log warning, continue |
| Unknown Arena card ID | Queue to `card_db.pending_unknowns`, display "Unknown card" placeholder |
| GPT-4o timeout (>10s) | Show "Advisor offline — rule alerts active", retry on next trigger |
| GPT-4o API error | Same as timeout |
| Tesseract not installed | Log warning, disable OCR, run log-only |
| Log file not found | Show "Waiting for MTGA..." in status bar, retry every 5s |

---

## 8. Setup & Usage

```bash
cd game_advisor
pip install -r requirements.txt   # adds openai, mss, pytesseract, Pillow
cp .env.example .env
# edit .env: OPENAI_API_KEY=sk-...

python calibrate_capture.py       # set MTGA window region (one-time)
python main.py                    # start the advisor
```

Open MTGA on monitor 1, the advisor dashboard on monitor 2. Works for draft games and constructed practice matches.

---

## 9. Testing

- **Unit tests** for `rule_engine.py` — combat math with known P/T scenarios, lethal detection, castability
- **Unit tests** for `log_scanner.py` — mock log fixtures with sample GRE messages
- **Unit tests** for `llm_advisor.py` — mocked OpenAI client verifying prompt format and cache behavior
- Test files in `game_advisor/tests/`

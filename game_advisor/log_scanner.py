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

_GAME_ADVISOR_DIR = str(pathlib.Path(__file__).parent)
_REPO_ROOT = str(pathlib.Path(__file__).parent.parent)
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)
if _GAME_ADVISOR_DIR not in sys.path:
    sys.path.insert(0, _GAME_ADVISOR_DIR)
import card_db
import config
from game_state import BoardCard, GameState, HandCard, Player
from card_helpers import get_colors, get_keywords

# Eagerly warm all card_db lazy caches so that _load_cache() never fires
# mid-processing and replaces the module-level dict references via `global`.
card_db.get_mana_cost("")
card_db.get_cmc("")
card_db.get_oracle("")
card_db.get_type_line("")

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

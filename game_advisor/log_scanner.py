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

_BASIC_LAND_TYPES = {
    "plains": ["W"], "island": ["U"], "swamp": ["B"],
    "mountain": ["R"], "forest": ["G"],
}


class GameLogScanner:
    def __init__(self, log_path: str = config.ARENA_LOG_PATH):
        self.log_path = log_path
        self._last_mtime: float = 0
        self.on_state_change: Optional[Callable[[GameState], None]] = None
        self._gs_cache: dict = {}   # accumulated game state — Full replaces, Diff merges
        # Start at end of existing log so we only pick up new events, not history.
        # The resync() action in main.py resets _file_pos to 0 for replaying history.
        try:
            self._file_pos: int = os.path.getsize(log_path)
        except OSError:
            self._file_pos = 0
        # Eagerly warm card_db caches so _load_cache() doesn't fire and replace
        # test-injected dict values mid-processing.
        card_db.get_mana_cost("")
        card_db.get_cmc("")
        card_db.get_oracle("")
        card_db.get_type_line("")

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
            # Real MTGA format: fields sit directly in gameStateMessage (no nested
            # "gameState" key).  GameStateType_Full replaces our cache entirely;
            # GameStateType_Diff is a partial update that we merge in.
            gsm = msg.get("gameStateMessage", {})
            if not gsm:
                continue
            msg_type = gsm.get("type", "")
            if msg_type == "GameStateType_Full":
                self._gs_cache = dict(gsm)
            elif msg_type == "GameStateType_Diff":
                _merge_diff(self._gs_cache, gsm)
            else:
                continue
            state = _parse_game_state(self._gs_cache)
            if state and self.on_state_change:
                self.on_state_change(state)


def _merge_diff(base: dict, diff: dict) -> None:
    """Merge a GameStateType_Diff into the base state dict in-place.
    Lists (players, zones, gameObjects) are merged by their ID key so that
    partial updates don't wipe entries that weren't included in the diff.
    """
    _LIST_ID_KEYS = {
        "players": "systemSeatNumber",
        "zones": "zoneId",
        "gameObjects": "instanceId",
    }
    for key, value in diff.items():
        if key in _LIST_ID_KEYS and isinstance(value, list):
            id_key = _LIST_ID_KEYS[key]
            existing = {item[id_key]: item for item in base.get(key, []) if id_key in item}
            for item in value:
                item_id = item.get(id_key)
                if item_id is not None:
                    existing[item_id] = {**existing.get(item_id, {}), **item}
            base[key] = list(existing.values())
        else:
            base[key] = value


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


def _detect_local_seat(zones: dict, objects: dict) -> Optional[int]:
    """Detect local player seat by finding the hand zone whose cards appear in gameObjects.

    In MTGA logs the opponent's hand cards are hidden — their instance IDs do not
    appear in gameObjects.  The local player's hand cards ARE present.  Whichever
    hand zone has at least one object instance ID that appears in gameObjects
    belongs to the local player.
    """
    for zone in zones.values():
        if zone.get("type") != "ZoneType_Hand":
            continue
        player_ids = zone.get("playerIds", [])
        if not player_ids:
            continue
        iids = set(zone.get("objectInstanceIds", []))
        if iids & set(objects.keys()):
            return player_ids[0]
    return None


def _parse_game_state(gs: dict) -> Optional[GameState]:
    turn_info = gs.get("turnInfo", {})
    turn = turn_info.get("turnNumber", 0)
    phase = _normalize_phase(turn_info.get("phase", ""), turn_info.get("step", ""))
    active_seat = turn_info.get("activePlayer", config.PLAYER_SEAT_ID)

    players_raw = gs.get("players", [])
    if len(players_raw) < 2:
        return None

    zones = {z["zoneId"]: z for z in gs.get("zones", [])}
    objects = {o["instanceId"]: o for o in gs.get("gameObjects", [])}

    # Dynamically detect local seat so boards stay correct regardless of seat assignment.
    seat = _detect_local_seat(zones, objects) or config.PLAYER_SEAT_ID
    you_raw = next((p for p in players_raw if p.get("systemSeatNumber") == seat), players_raw[0])
    opp_raw = next((p for p in players_raw if p.get("systemSeatNumber") != seat), players_raw[1])

    you = _build_player(you_raw, zones, objects, is_you=True)
    opp = _build_player(opp_raw, zones, objects, is_you=False)

    return GameState(turn=turn, phase=phase, active_seat=active_seat, you=you, opponent=opp)


def _build_player(raw: dict, zones: dict, objects: dict, is_you: bool) -> Player:
    seat_id = raw.get("systemSeatNumber", 1)
    life = raw.get("lifeTotal", 20)
    board_cards: list[BoardCard] = []
    hand_cards: list[HandCard] = []

    # Build lookup: instance_id -> zone_type
    # Used to know which zone each game object is in.
    obj_zone_type: dict[int, str] = {}
    for zone in zones.values():
        zone_type = zone.get("type", "")
        for iid in zone.get("objectInstanceIds", []):
            obj_zone_type[iid] = zone_type

    # Build hand zone lookup: instance_ids in hand zones owned by this player
    # Hand zones DO carry playerIds, so we can filter by seat ownership.
    hand_instance_ids: set[int] = set()
    for zone in zones.values():
        if zone.get("type") == "ZoneType_Hand" and seat_id in zone.get("playerIds", []):
            hand_instance_ids.update(zone.get("objectInstanceIds", []))

    # Iterate all game objects — only resolve names for cards in Hand or Battlefield.
    # Skipping library/graveyard/exile objects avoids wasting Scryfall quota on hidden cards.
    for obj in objects.values():
        # Only process real card objects; skip abilities, tokens without arena IDs, etc.
        if obj.get("type") != "GameObjectType_Card":
            continue
        grp_id = obj.get("grpId", 0)
        if not grp_id:
            continue

        iid = obj.get("instanceId")
        zone_type = obj_zone_type.get(iid, "")

        is_my_battlefield = (zone_type == "ZoneType_Battlefield"
                             and obj.get("controllerSeatId") == seat_id)
        is_my_hand = (zone_type == "ZoneType_Hand" and is_you and iid in hand_instance_ids)

        if not is_my_battlefield and not is_my_hand:
            continue

        arena_id = str(grp_id)
        name = card_db.name(arena_id)
        power = obj.get("power", {}).get("value", 0)
        toughness = obj.get("toughness", {}).get("value", 0)
        keywords = get_keywords(name)

        if is_my_battlefield:
            tapped = obj.get("isTapped", False)
            attacking = obj.get("attackState", "") == "AttackState_Attacking"
            board_cards.append(BoardCard(
                name=name, arena_id=arena_id, instance_id=iid,
                power=power, toughness=toughness, keywords=keywords,
                tapped=tapped, attacking=attacking,
            ))
        else:  # is_my_hand
            mana_cost = card_db.get_mana_cost(name)
            cmc = card_db.get_cmc(name)
            colors = get_colors(name)
            hand_cards.append(HandCard(
                name=name, arena_id=arena_id, instance_id=iid,
                mana_cost=mana_cost, cmc=cmc, colors=colors,
            ))

    # Compute available mana from untapped lands on this player's board
    mana_colors: list[str] = []
    untapped_land_count = 0
    for card in board_cards:
        type_line = card_db.get_type_line(card.name).lower()
        if "land" not in type_line or card.tapped:
            continue
        untapped_land_count += 1
        base = card.name.lower().replace("snow-covered ", "")
        if base in _BASIC_LAND_TYPES:
            mana_colors.extend(_BASIC_LAND_TYPES[base])
        else:
            # Non-basic land: infer colors from mana cost field
            # Note: hybrid/Phyrexian pips are not captured (known limitation)
            mana_colors.extend(get_colors(card.name))

    # Mark castable hand cards
    # Note: hybrid-cost cards may be incorrectly marked castable (known limitation in get_colors)
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

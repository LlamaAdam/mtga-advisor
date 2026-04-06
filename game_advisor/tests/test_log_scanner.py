import json
import sys
import pathlib
import pytest
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent.parent))
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

import card_db
from log_scanner import GameLogScanner
from game_state import GameState


@pytest.fixture(autouse=True)
def clean_card_db_state():
    orig_cache = card_db._cache.copy()
    orig_mana = card_db._mana_cost.copy()
    orig_cmc = card_db._cmc.copy()
    orig_oracle = card_db._oracle.copy()
    orig_type_line = card_db._type_line.copy()
    orig_bad_ids = card_db._bad_ids.copy()  # prevent test IDs leaking into real cache
    yield
    for d, orig in [
        (card_db._cache, orig_cache),
        (card_db._mana_cost, orig_mana),
        (card_db._cmc, orig_cmc),
        (card_db._oracle, orig_oracle),
        (card_db._type_line, orig_type_line),
    ]:
        d.clear()
        d.update(orig)
    card_db._bad_ids.clear()
    card_db._bad_ids.update(orig_bad_ids)


# --- Fixture: minimal valid GRE game state message ---
def _make_gre_log_line(turn: int = 3, your_life: int = 18, opp_life: int = 20) -> str:
    payload = {
        "greToClientEvent": {
            "greToClientMessages": [
                {
                    "type": "GREMessageType_GameStateMessage",
                    "msgId": 5,
                    # Real MTGA format: fields sit directly in gameStateMessage,
                    # NOT nested under a "gameState" key.
                    "gameStateMessage": {
                        "type": "GameStateType_Full",
                        "gameStateId": 12,
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
                                # Hand zones DO carry playerIds
                                "playerIds": [1],
                                "objectInstanceIds": [101],
                            },
                            {
                                "zoneId": 29,
                                "type": "ZoneType_Battlefield",
                                # Battlefield is a shared zone — no playerIds
                                "playerIds": [],
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
                                    # controllerSeatId indicates ownership on shared zones
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

    # Create scanner before writing content so it starts at position 0 (empty file).
    log_file = tmp_path / "Player.log"
    log_file.write_text("")
    received: list[GameState] = []
    scanner = GameLogScanner(log_path=str(log_file))
    scanner.on_state_change = lambda s: received.append(s)
    log_file.write_text(_make_gre_log_line(turn=3, your_life=18, opp_life=20))
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
    log_file.write_text("")
    received: list[GameState] = []
    scanner = GameLogScanner(log_path=str(log_file))
    scanner.on_state_change = lambda s: received.append(s)
    log_file.write_text(_make_gre_log_line())
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


def _make_gre_log_line_with_land(tapped: bool) -> str:
    """Build a log line where player 1 has a Forest (possibly tapped) on the battlefield
    and a hand card (Lightning Strike, cmc=2, color=R)."""
    payload = {
        "greToClientEvent": {
            "greToClientMessages": [
                {
                    "type": "GREMessageType_GameStateMessage",
                    "msgId": 10,
                    "gameStateMessage": {
                        "type": "GameStateType_Full",
                        "gameStateId": 20,
                        "turnInfo": {
                            "phase": "Phase_Main",
                            "step": "Step_Main",
                            "turnNumber": 3,
                            "activePlayer": 1,
                            "decisionPlayer": 1,
                        },
                        "zones": [
                            {
                                "zoneId": 30,
                                "type": "ZoneType_Hand",
                                "playerIds": [1],
                                "objectInstanceIds": [201],
                            },
                            {
                                "zoneId": 31,
                                "type": "ZoneType_Battlefield",
                                "playerIds": [],
                                "objectInstanceIds": [202, 203],
                            },
                        ],
                        "gameObjects": [
                                {
                                    # Hand card: Lightning Strike (R spell)
                                    "instanceId": 201,
                                    "grpId": 11111,
                                    "type": "GameObjectType_Card",
                                    "zoneId": 30,
                                    "controllerSeatId": 1,
                                    "ownerSeatId": 1,
                                    "power": {"value": 0},
                                    "toughness": {"value": 0},
                                    "isTapped": False,
                                },
                                {
                                    # Battlefield: Mountain (untapped, always)
                                    "instanceId": 202,
                                    "grpId": 22222,
                                    "type": "GameObjectType_Card",
                                    "zoneId": 31,
                                    "controllerSeatId": 1,
                                    "ownerSeatId": 1,
                                    "power": {"value": 0},
                                    "toughness": {"value": 0},
                                    "isTapped": False,
                                },
                                {
                                    # Battlefield: a second land, tapped state is configurable
                                    "instanceId": 203,
                                    "grpId": 22223,
                                    "type": "GameObjectType_Card",
                                    "zoneId": 31,
                                    "controllerSeatId": 1,
                                    "ownerSeatId": 1,
                                    "power": {"value": 0},
                                    "toughness": {"value": 0},
                                    "isTapped": tapped,
                                },
                            ],
                        "players": [
                            {"systemSeatNumber": 1, "lifeTotal": 20},
                            {"systemSeatNumber": 2, "lifeTotal": 20},
                        ],
                    },
                }
            ]
        }
    }
    return json.dumps(payload)


def test_tapped_land_does_not_contribute_to_mana(tmp_path):
    """A tapped land on the battlefield must not be counted as available mana."""
    # Create scanner against an empty file so _file_pos starts at 0, then write content.
    # Scanner must be created first so __init__ warm-up fires _load_cache() before
    # we inject test data (otherwise _load_cache overwrites our injected values).
    log_file = tmp_path / "Player.log"
    log_file.write_text("")
    received: list[GameState] = []
    scanner = GameLogScanner(log_path=str(log_file))
    log_file.write_text(_make_gre_log_line_with_land(tapped=True))

    card_db._cache["11111"] = "Lightning Strike"
    card_db._mana_cost["lightning strike"] = "{1}{R}"
    card_db._cmc["lightning strike"] = 2
    # Mountain (untapped) contributes 1 R mana
    card_db._cache["22222"] = "Mountain"
    card_db._type_line["mountain"] = "Basic Land — Mountain"
    # Plains (tapped) must NOT contribute
    card_db._cache["22223"] = "Plains"
    card_db._type_line["plains"] = "Basic Land — Plains"
    scanner.on_state_change = lambda s: received.append(s)
    scanner.poll()

    assert len(received) == 1
    # Only the untapped Mountain counts
    assert received[0].you.mana_available == 1
    assert received[0].you.mana_colors == ["R"]


def _make_gre_mulligan_line() -> str:
    """Build a log line that mimics the MTGA mulligan phase:
    - turnNumber=0, no phase
    - Hand zone has NO playerIds (MTGA omits them during mulligan)
    - Card objects DO have ownerSeatId set
    """
    payload = {
        "greToClientEvent": {
            "greToClientMessages": [
                {
                    "type": "GREMessageType_GameStateMessage",
                    "gameStateMessage": {
                        "type": "GameStateType_Full",
                        "turnInfo": {"turnNumber": 0},
                        "zones": [
                            {
                                "zoneId": 40,
                                "type": "ZoneType_Hand",
                                # playerIds intentionally absent / empty — mulligan phase
                                "playerIds": [],
                                "objectInstanceIds": [301, 302],
                            },
                        ],
                        "gameObjects": [
                            {
                                "instanceId": 301,
                                "grpId": 55555,
                                "type": "GameObjectType_Card",
                                "zoneId": 40,
                                "ownerSeatId": 1,
                                "controllerSeatId": 1,
                                "power": {"value": 0},
                                "toughness": {"value": 0},
                                "isTapped": False,
                            },
                            {
                                "instanceId": 302,
                                "grpId": 66666,
                                "type": "GameObjectType_Card",
                                "zoneId": 40,
                                "ownerSeatId": 1,
                                "controllerSeatId": 1,
                                "power": {"value": 0},
                                "toughness": {"value": 0},
                                "isTapped": False,
                            },
                        ],
                        "players": [
                            {"systemSeatNumber": 1, "lifeTotal": 20},
                            {"systemSeatNumber": 2, "lifeTotal": 20},
                        ],
                    },
                }
            ]
        }
    }
    return json.dumps(payload)


def test_mulligan_hand_parsed_without_player_ids(tmp_path):
    """During the mulligan phase MTGA omits playerIds from hand zones.
    The scanner must still detect the local player's hand via ownerSeatId fallback."""
    log_file = tmp_path / "Player.log"
    log_file.write_text("")
    received: list[GameState] = []
    # Create scanner first so __init__ warm-up fires _load_cache() before we inject
    scanner = GameLogScanner(log_path=str(log_file))
    # Inject AFTER scanner creation so warm-up doesn't overwrite our test values
    card_db._cache["55555"] = "Plains"
    card_db._type_line["plains"] = "Basic Land — Plains"
    card_db._cache["66666"] = "Shock"
    card_db._mana_cost["shock"] = "{R}"
    card_db._cmc["shock"] = 1
    scanner.on_state_change = lambda s: received.append(s)
    log_file.write_text(_make_gre_mulligan_line())
    scanner.poll()

    assert len(received) == 1
    state = received[0]
    assert state.turn == 0
    hand = state.you.hand
    assert len(hand) == 2, f"Expected 2 hand cards, got {len(hand)}: {[c.name for c in hand]}"
    names = {c.name for c in hand}
    assert "Plains" in names
    assert "Shock" in names


def test_castable_hand_card_marked_castable(tmp_path):
    """A hand card whose CMC and colors are satisfied by available mana is marked castable."""
    # Create scanner against an empty file so _file_pos starts at 0, then write content.
    # Scanner must be created first so __init__ warm-up fires _load_cache() before
    # we inject test data.
    log_file = tmp_path / "Player.log"
    log_file.write_text("")
    received: list[GameState] = []
    scanner = GameLogScanner(log_path=str(log_file))
    log_file.write_text(_make_gre_log_line_with_land(tapped=False))

    card_db._cache["11111"] = "Lightning Strike"
    card_db._mana_cost["lightning strike"] = "{1}{R}"
    card_db._cmc["lightning strike"] = 2
    # Two untapped Mountains provide {R}{R} and 2 generic mana
    card_db._cache["22222"] = "Mountain"
    card_db._type_line["mountain"] = "Basic Land — Mountain"
    card_db._cache["22223"] = "Mountain"
    scanner.on_state_change = lambda s: received.append(s)
    scanner.poll()

    assert len(received) == 1
    hand = received[0].you.hand
    assert len(hand) == 1
    assert hand[0].name == "Lightning Strike"
    assert hand[0].castable is True

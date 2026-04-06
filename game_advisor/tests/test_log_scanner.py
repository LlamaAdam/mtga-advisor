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

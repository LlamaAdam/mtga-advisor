import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
from game_state import BoardCard, GameState, Player, HandCard
import rule_engine


def _creature(name: str, power: int, toughness: int) -> BoardCard:
    return BoardCard(name=name, arena_id="0", instance_id=1,
                     power=power, toughness=toughness, keywords=[])


def _state(your_board=None, opp_board=None, your_life=20, opp_life=20, turn=4):
    you = Player(seat_id=1, life=your_life, board=your_board or [], hand=[])
    opp = Player(seat_id=2, life=opp_life, board=opp_board or [], hand=[])
    return GameState(turn=turn, phase="Main 1", active_seat=1, you=you, opponent=opp)


def test_role_aggressor_big_board_life_lead():
    state = _state(
        your_board=[_creature("A", 5, 5), _creature("B", 4, 4)],
        opp_board=[_creature("C", 1, 1)],
        your_life=20, opp_life=12,
    )
    alerts = rule_engine.check_role(state)
    assert any("aggressor" in a.message.lower() for a in alerts)


def test_role_defender_behind_board_and_life():
    state = _state(
        your_board=[_creature("A", 1, 1)],
        opp_board=[_creature("B", 5, 5), _creature("C", 4, 4)],
        your_life=8, opp_life=20,
    )
    alerts = rule_engine.check_role(state)
    assert any("defender" in a.message.lower() for a in alerts)


def test_role_flexible_even_board():
    state = _state(
        your_board=[_creature("A", 3, 3)],
        opp_board=[_creature("B", 3, 3)],
        your_life=20, opp_life=20,
    )
    alerts = rule_engine.check_role(state)
    assert any("flexible" in a.message.lower() for a in alerts)


def test_role_empty_boards_no_alert():
    state = _state(your_board=[], opp_board=[])
    alerts = rule_engine.check_role(state)
    assert alerts == []

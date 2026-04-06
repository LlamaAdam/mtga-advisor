import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
from game_state import BoardCard, GameState, Player, RuleAlert
import rule_engine


def _make_creature(name: str, power: int, toughness: int,
                   tapped: bool = False, keywords=None) -> BoardCard:
    return BoardCard(
        name=name, arena_id="0", instance_id=1,
        power=power, toughness=toughness,
        keywords=keywords or [], tapped=tapped,
    )


def _make_state(your_board=None, opp_board=None, your_life=20, opp_life=20, turn=4):
    you = Player(seat_id=1, life=your_life, board=your_board or [], hand=[])
    opp = Player(seat_id=2, life=opp_life, board=opp_board or [], hand=[])
    return GameState(turn=turn, phase="Main 1", active_seat=1, you=you, opponent=opp)


def test_lethal_clock_you_faster():
    # 5 untapped power vs 10 life = 2 attacks
    state = _make_state(
        your_board=[_make_creature("A", 5, 5)],
        opp_board=[_make_creature("B", 2, 2)],
        opp_life=10, your_life=20,
    )
    alerts = rule_engine.check_lethal_clock(state)
    msgs = [a.message for a in alerts]
    assert any("2" in m and "kill" in m.lower() for m in msgs)


def test_lethal_clock_opponent_faster_gives_warning():
    # Opponent has 6 power vs your 8 life — dies in 2; you have 2 power vs 20 life — 10 turns
    state = _make_state(
        your_board=[_make_creature("A", 2, 2)],
        opp_board=[_make_creature("B", 6, 6)],
        your_life=8, opp_life=20,
    )
    alerts = rule_engine.check_lethal_clock(state)
    severities = [a.severity for a in alerts]
    assert "WARNING" in severities


def test_lethal_clock_no_creatures_no_alert():
    state = _make_state(your_board=[], opp_board=[])
    alerts = rule_engine.check_lethal_clock(state)
    assert alerts == []


def test_lethal_clock_tapped_excluded_from_your_clock():
    # Your only creature is tapped — no clock for you
    state = _make_state(
        your_board=[_make_creature("A", 10, 10, tapped=True)],
        opp_board=[_make_creature("B", 2, 2)],
        opp_life=5, your_life=20,
    )
    alerts = rule_engine.check_lethal_clock(state)
    # Should not show you threatening lethal via clock
    assert not any("1 attack" in a.message.lower() for a in alerts)


def test_lethal_clock_exact_one_turn():
    state = _make_state(
        your_board=[_make_creature("A", 20, 20)],
        opp_board=[],
        opp_life=5, your_life=20,
    )
    alerts = rule_engine.check_lethal_clock(state)
    assert any("1" in a.message for a in alerts)

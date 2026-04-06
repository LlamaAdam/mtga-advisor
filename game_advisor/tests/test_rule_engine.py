import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent.parent))
from game_state import BoardCard, GameState, HandCard, Player, RuleAlert
import rule_engine
import card_db
import pytest


@pytest.fixture(autouse=True)
def clean_card_db():
    orig_oracle = card_db._oracle.copy()
    yield
    card_db._oracle.clear()
    card_db._oracle.update(orig_oracle)


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


def test_trade_attack_flagged_as_warning():
    your_board = [_make_creature("My 2/2", 2, 2)]
    opp_board = [_make_creature("Opp 2/2", 2, 2)]
    state = _make_state(your_board=your_board, opp_board=opp_board)
    alerts = rule_engine.check_combat(state)
    trade_warnings = [a for a in alerts if a.severity == "WARNING" and "trade" in a.message.lower()]
    assert trade_warnings != []


# --- Removal targeting ---

def test_removal_target_flagged_when_castable():
    your_hand = [
        _make_hand_card("Lightning Strike", cmc=2, colors=["R"], castable=True)
    ]
    opp_board = [_make_creature("Warden", 2, 2, keywords=["flying"])]
    state = _make_state(your_hand=your_hand, opp_board=opp_board)
    card_db._oracle["lightning strike"] = "Lightning Strike deals 3 damage to any target."
    alerts = rule_engine.check_removal(state)
    assert any("Lightning Strike" in a.message for a in alerts)


def test_no_removal_alert_when_hand_is_empty():
    state = _make_state(your_hand=[], opp_board=[_make_creature("X", 3, 3)])
    alerts = rule_engine.check_removal(state)
    assert alerts == []

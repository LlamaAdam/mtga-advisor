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

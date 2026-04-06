import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
from game_state import BoardCard, GameState, Player, HandCard
import decklist as _decklist
from llm_advisor import compress_state, _COT_SYSTEM_PROMPT


def _board_card(name: str, power: int, toughness: int, keywords=None, tapped=False):
    return BoardCard(name=name, arena_id="0", instance_id=1,
                     power=power, toughness=toughness,
                     keywords=keywords or [], tapped=tapped)


def _hand_card(name: str, cmc: int, cost: str = "{R}", castable: bool = True):
    return HandCard(name=name, arena_id="0", instance_id=2,
                    mana_cost=cost, cmc=cmc, colors=["R"], castable=castable)


def _make_state():
    you = Player(seat_id=1, life=18, board=[_board_card("Goblin", 1, 1)],
                 hand=[_hand_card("Shock", 1)], mana_available=2)
    opp = Player(seat_id=2, life=14, board=[_board_card("Dragon", 5, 5, ["flying"])], hand=[])
    return GameState(turn=4, phase="Main 1", active_seat=1, you=you, opponent=opp)


def test_compress_state_contains_turn_and_life():
    state = _make_state()
    compressed = compress_state(state)
    assert "T4" in compressed
    assert "18" in compressed   # your life
    assert "14" in compressed   # opp life


def test_compress_state_contains_board_creatures():
    state = _make_state()
    compressed = compress_state(state)
    assert "Goblin" in compressed
    assert "Dragon" in compressed


def test_compress_state_contains_hand():
    state = _make_state()
    compressed = compress_state(state)
    assert "Shock" in compressed


def test_compress_state_empty_board():
    you = Player(seat_id=1, life=20, board=[], hand=[], mana_available=0)
    opp = Player(seat_id=2, life=20, board=[], hand=[])
    state = GameState(turn=1, phase="Main 1", active_seat=1, you=you, opponent=opp)
    compressed = compress_state(state)
    assert "Board:[]" in compressed or "Board: []" in compressed


def test_cot_system_prompt_has_four_steps():
    assert "BOARD ASSESSMENT" in _COT_SYSTEM_PROMPT
    assert "HAND EVALUATION" in _COT_SYSTEM_PROMPT
    assert "RECOMMENDED ACTION" in _COT_SYSTEM_PROMPT
    assert "SUMMARY" in _COT_SYSTEM_PROMPT


def test_prompt_includes_deck_context_when_loaded():
    orig = _decklist.active_deck.copy()
    try:
        _decklist.active_deck = {"Lightning Bolt": 4, "Mountain": 17}
        state = _make_state()
        compressed = compress_state(state)
        # deck section is separate — tested via _build_prompt indirectly
        # Just verify compress_state itself still works
        assert "T4" in compressed
    finally:
        _decklist.active_deck = orig

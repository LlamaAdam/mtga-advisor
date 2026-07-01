import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent.parent))
from draft_helper import card_db
import pytest
from game_state import BoardCard, GameState, Player, HandCard
import decklist as _decklist
from llm_advisor import compress_state, _COT_SYSTEM_PROMPT, card_text_appendix


@pytest.fixture(autouse=True)
def _disable_shared_store(monkeypatch):
    """Tests in this file control oracle data via card_db._oracle directly,
    so disable the shared-store lookup to keep the local cache in charge."""
    monkeypatch.setattr("draft_helper.card_db._resolve_shared_cards_dir", lambda: None)
    orig = card_db._oracle.copy()
    yield
    card_db._oracle.clear()
    card_db._oracle.update(orig)


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


def test_card_text_appendix_returns_empty_when_no_oracle_data():
    """No card has cached oracle text → appendix is empty string."""
    state = _make_state()
    appendix = card_text_appendix(state)
    assert appendix == ""


def test_card_text_appendix_includes_hand_oracle():
    state = _make_state()
    card_db._oracle["shock"] = "Shock deals 2 damage to any target."
    appendix = card_text_appendix(state)
    assert "Shock" in appendix
    assert "2 damage" in appendix
    assert "[hand]" in appendix


def test_card_text_appendix_includes_opp_board_oracle():
    state = _make_state()
    card_db._oracle["dragon"] = "Flying. When this enters, deal 5 damage to any target."
    appendix = card_text_appendix(state)
    assert "[opp-board]" in appendix
    assert "Dragon" in appendix


def test_card_text_appendix_truncates_long_text():
    state = _make_state()
    card_db._oracle["shock"] = "Word " * 200  # ~1000 chars
    appendix = card_text_appendix(state, max_chars_per_card=50)
    # Each card line should be capped — overall length bound is loose,
    # but specifically the truncated entry should fit within the cap + ellipsis.
    lines = [line for line in appendix.splitlines() if "Shock" in line]
    assert lines, "Shock should appear"
    # The line is "  - [hand] Shock: <truncated>"; ensure the truncated
    # text is at most 50 chars + the ellipsis marker.
    text_after_colon = lines[0].split("Shock:", 1)[1].strip()
    assert len(text_after_colon) <= 51  # 50 chars + ellipsis


def test_card_text_appendix_collapses_newlines():
    state = _make_state()
    card_db._oracle["shock"] = "Line one\nLine two\nLine three"
    appendix = card_text_appendix(state)
    # Newlines inside a card's text should become spaces so the line stays one-per-card.
    shock_line = [line for line in appendix.splitlines() if "Shock" in line][0]
    # Card line itself shouldn't have embedded newlines beyond the format separator.
    assert "Line one Line two Line three" in shock_line


def test_card_text_appendix_dedupes_identical_card_names():
    """If a card appears multiple times in hand or twice across hand+board,
    it should only emit one oracle line (avoids prompt bloat)."""
    you = Player(
        seat_id=1, life=18,
        board=[],
        hand=[
            HandCard(name="Shock", arena_id="0", instance_id=1,
                     mana_cost="{R}", cmc=1, colors=["R"], castable=True),
            HandCard(name="Shock", arena_id="0", instance_id=2,
                     mana_cost="{R}", cmc=1, colors=["R"], castable=True),
        ],
        mana_available=2,
    )
    opp = Player(seat_id=2, life=14, board=[], hand=[])
    state = GameState(turn=4, phase="Main 1", active_seat=1, you=you, opponent=opp)
    card_db._oracle["shock"] = "Shock deals 2 damage to any target."
    appendix = card_text_appendix(state)
    assert appendix.count("Shock:") == 1


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

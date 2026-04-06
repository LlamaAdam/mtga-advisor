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
    orig_type_line = card_db._type_line.copy()
    orig_bad_ids = card_db._bad_ids.copy()
    yield
    card_db._oracle.clear()
    card_db._oracle.update(orig_oracle)
    card_db._type_line.clear()
    card_db._type_line.update(orig_type_line)
    card_db._bad_ids.clear()
    card_db._bad_ids.update(orig_bad_ids)


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


def _make_hand_land(name: str) -> HandCard:
    return HandCard(
        name=name, arena_id="0", instance_id=3,
        mana_cost="", cmc=0, colors=[], castable=False,
    )


def _make_state(your_board=None, opp_board=None, your_hand=None,
                your_life=20, opp_life=20, mana_available=3,
                mana_colors=None, turn=4) -> GameState:
    you = Player(
        seat_id=1, life=your_life,
        board=your_board or [],
        hand=your_hand or [],
        mana_available=mana_available,
        mana_colors=mana_colors or ["R", "R", "W"],
    )
    opp = Player(seat_id=2, life=opp_life, board=opp_board or [], hand=[])
    return GameState(turn=turn, phase="Main 1", active_seat=1, you=you, opponent=opp)


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


def test_deathtouch_blocker_is_risky_trade():
    your_board = [_make_creature("Big 4/4", 4, 4)]
    opp_board = [_make_creature("DT 1/1", 1, 1, keywords=["deathtouch"])]
    state = _make_state(your_board=your_board, opp_board=opp_board)
    alerts = rule_engine.check_combat(state)
    # 4/4 kills the 1/1 (blocker dies), but 1/1 deathtouch kills the 4/4 (attacker dies) → trade
    warnings = [a for a in alerts if a.severity == "WARNING" and "trade" in a.message.lower()]
    assert warnings != []


def test_flying_creature_can_block_ground_attacker():
    # Opponent has only a flying blocker; your ground creature should still get a combat warning
    your_board = [_make_creature("Ground 2/2", 2, 2)]
    opp_board = [_make_creature("Dragon 5/5", 5, 5, keywords=["flying"])]
    state = _make_state(your_board=your_board, opp_board=opp_board)
    alerts = rule_engine.check_combat(state)
    # Dragon can block Ground 2/2 and kills it → suicidal or trade
    assert any("Ground 2/2" in a.message for a in alerts)


def test_no_removal_alert_when_hand_is_empty():
    state = _make_state(your_hand=[], opp_board=[_make_creature("X", 3, 3)])
    alerts = rule_engine.check_removal(state)
    assert alerts == []


# --- Mulligan detection ---

def _setup_lands(*names):
    """Inject type_line entries so rule_engine recognises these as lands."""
    for name in names:
        card_db._type_line[name.lower()] = f"Basic Land — {name}"


def test_mulligan_no_lands_danger():
    # MTGA reports turnNumber=0 during the mulligan screen
    _setup_lands("Mountain")
    hand = [_make_hand_card("Shock", 1, ["R"]) for _ in range(7)]
    state = _make_state(your_hand=hand, turn=0)
    alerts = rule_engine.check_mulligan(state)
    assert any(a.severity == "DANGER" and "no land" in a.message.lower() for a in alerts)


def test_mulligan_no_lands_danger_turn1():
    # Also fires at turn 1 (just after mulligan decision / start of first real turn)
    _setup_lands("Mountain")
    hand = [_make_hand_card("Shock", 1, ["R"]) for _ in range(7)]
    state = _make_state(your_hand=hand, turn=1)
    alerts = rule_engine.check_mulligan(state)
    assert any(a.severity == "DANGER" and "no land" in a.message.lower() for a in alerts)


def test_mulligan_one_land_warning():
    _setup_lands("Mountain")
    hand = [_make_hand_land("Mountain")] + [_make_hand_card("Shock", 1, ["R"]) for _ in range(6)]
    state = _make_state(your_hand=hand, turn=1)
    alerts = rule_engine.check_mulligan(state)
    assert any(a.severity == "WARNING" and "1 land" in a.message.lower() for a in alerts)


def test_mulligan_flood_warning():
    _setup_lands("Mountain")
    hand = [_make_hand_land("Mountain") for _ in range(6)] + [_make_hand_card("Shock", 1, ["R"])]
    state = _make_state(your_hand=hand, turn=1)
    alerts = rule_engine.check_mulligan(state)
    assert any(a.severity == "WARNING" and "flood" in a.message.lower() for a in alerts)


def test_mulligan_good_hand_keep_recommendation():
    _setup_lands("Mountain")
    lands = [_make_hand_land("Mountain") for _ in range(3)]
    spells = [_make_hand_card("Shock", 1, ["R"]) for _ in range(4)]
    state = _make_state(your_hand=lands + spells, turn=1)
    alerts = rule_engine.check_mulligan(state)
    assert any(a.severity == "INFO" and "keepable" in a.message.lower() for a in alerts)


def test_mulligan_color_screw_warning():
    card_db._type_line["island"] = "Basic Land — Island"
    hand = [_make_hand_land("Island"), _make_hand_land("Island"),
            _make_hand_card("Shock", 1, ["R"]),
            _make_hand_card("Lightning Strike", 2, ["R"]),
            _make_hand_card("Goblin", 2, ["R"]),
            _make_hand_card("Fireball", 3, ["R"]),
            _make_hand_card("Dragon", 5, ["R"])]
    state = _make_state(your_hand=hand, turn=1)
    alerts = rule_engine.check_mulligan(state)
    assert any(a.severity == "WARNING" and "red" in a.message.lower() for a in alerts)


def test_mulligan_ignored_after_turn_3():
    """Turn 3+ with a full hand = game in progress, no mulligan advice."""
    _setup_lands("Mountain")
    hand = [_make_hand_card("Shock", 1, ["R"]) for _ in range(7)]
    state = _make_state(your_hand=hand, turn=3)
    alerts = rule_engine.check_mulligan(state)
    assert alerts == []


def test_mulligan_fires_at_turn0_mulligan_screen():
    """turn=0 is the actual MTGA mulligan screen — advice must fire here."""
    _setup_lands("Mountain")
    lands = [_make_hand_land("Mountain") for _ in range(3)]
    spells = [_make_hand_card("Shock", 1, ["R"]) for _ in range(4)]
    state = _make_state(your_hand=lands + spells, turn=0)
    alerts = rule_engine.check_mulligan(state)
    assert any(a.severity == "INFO" and "keepable" in a.message.lower() for a in alerts)


def test_mulligan_unknown_cards_defers_to_resolver():
    """If >half the hand is still Unknown, report 'resolving' instead of wrong land count."""
    hand = [HandCard(name=f"Unknown({i})", arena_id=str(i), instance_id=i,
                     mana_cost="", cmc=0, colors=[]) for i in range(7)]
    state = _make_state(your_hand=hand, turn=0)
    alerts = rule_engine.check_mulligan(state)
    assert len(alerts) == 1
    assert alerts[0].severity == "INFO"
    assert "resolving" in alerts[0].message.lower()


def test_mulligan_turn2_fires_on_mulliganed_hand_no_lands():
    """At turn 2 with fewer than 7 cards (took a mulligan), still warn if no lands."""
    _setup_lands("Mountain")
    hand = [_make_hand_card("Shock", 1, ["R"]) for _ in range(6)]
    state = _make_state(your_hand=hand, turn=2)
    alerts = rule_engine.check_mulligan(state)
    assert any(a.severity == "DANGER" and "no land" in a.message.lower() for a in alerts)


def test_mulligan_turn2_ignored_for_full_hand():
    """Turn 2 with a full 7-card hand = no mulligan was taken, don't re-analyse."""
    _setup_lands("Mountain")
    hand = [_make_hand_land("Mountain")] + [_make_hand_card("Shock", 1, ["R"]) for _ in range(6)]
    state = _make_state(your_hand=hand, turn=2)
    alerts = rule_engine.check_mulligan(state)
    assert alerts == []


# --- Surveil recommendation ---

def test_surveil_alert_when_castable_surveil_card():
    opp_board = [_make_creature("Goblin", 1, 1)]
    your_hand = [_make_hand_card("Grim Wanderer", cmc=2, colors=["B"], castable=True)]
    card_db._oracle["grim wanderer"] = "Surveil 2. Draw a card."
    state = _make_state(your_hand=your_hand, opp_board=opp_board)
    alerts = rule_engine.check_surveil(state)
    assert any("surveil" in a.message.lower() and "Grim Wanderer" in a.message for a in alerts)


def test_surveil_no_alert_when_not_castable():
    your_hand = [_make_hand_card("Grim Wanderer", cmc=2, colors=["B"], castable=False)]
    card_db._oracle["grim wanderer"] = "Surveil 2. Draw a card."
    state = _make_state(your_hand=your_hand)
    alerts = rule_engine.check_surveil(state)
    assert alerts == []


def test_surveil_no_alert_when_no_surveil_card():
    your_hand = [_make_hand_card("Lightning Bolt", cmc=1, colors=["R"], castable=True)]
    card_db._oracle["lightning bolt"] = "Lightning Bolt deals 3 damage to any target."
    state = _make_state(your_hand=your_hand)
    alerts = rule_engine.check_surveil(state)
    assert alerts == []

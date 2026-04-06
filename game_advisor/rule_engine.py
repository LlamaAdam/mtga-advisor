"""
Synchronous rule-based checks that run on every game state update.
Returns a list of RuleAlert objects for immediate display in the dashboard.
"""
import math
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
import card_db
import decklist as _decklist
from game_state import BoardCard, GameState, HandCard, RuleAlert
from math_utils import hypergeometric_cdf_at_least, prob_draw_at_least_one

_KEYWORD_MULTIPLIERS: dict[str, float] = {
    "flying": 1.5,
    "trample": 1.2,
    "lifelink": 1.3,
    "deathtouch": 1.4,
    "haste": 1.3,
    "first strike": 1.2,
    "double strike": 1.6,
    "menace": 1.2,
    "indestructible": 1.5,
    "vigilance": 1.1,
}

_REMOVAL_ORACLE_MARKERS = [
    "deals damage", "damage to any target", "damage to target creature",
    "destroy target", "exile target",
]

_BASIC_LAND_COLORS: dict[str, list[str]] = {
    "plains": ["W"], "island": ["U"], "swamp": ["B"],
    "mountain": ["R"], "forest": ["G"],
}

_COLOR_NAMES: dict[str, str] = {
    "W": "White", "U": "Blue", "B": "Black", "R": "Red", "G": "Green",
}


def _display_name(card) -> str:
    """Return card name, or power/toughness for still-unresolved cards."""
    if card.name.startswith("Unknown("):
        return f"({card.power}/{card.toughness})"
    return card.name


def check_lethal(state: GameState) -> list[RuleAlert]:
    """Fire DANGER if your untapped creatures can deal >= opponent life total."""
    untapped = [c for c in state.you.board if not c.tapped]
    total_power = sum(c.power for c in untapped)
    if untapped and total_power >= state.opponent.life:
        names = ", ".join(_display_name(c) for c in untapped)
        return [RuleAlert(
            severity="DANGER",
            message=f"You have lethal — attack with: {names} ({total_power} power vs {state.opponent.life} life)",
        )]
    return []


def check_threats(state: GameState) -> list[RuleAlert]:
    """Rank opponent creatures by threat score and flag the top threat."""
    if not state.opponent.board:
        return []
    scored = [(c, _threat_score(c)) for c in state.opponent.board]
    scored.sort(key=lambda x: x[1], reverse=True)
    top, score = scored[0]
    severity = "DANGER" if score >= 4.0 else "WARNING"
    kw_str = (", ".join(top.keywords)) if top.keywords else "no keywords"
    return [RuleAlert(
        severity=severity,
        message=f"Top threat: {_display_name(top)} ({top.power}/{top.toughness}, {kw_str}) — score {score:.1f}",
    )]


def check_combat(state: GameState) -> list[RuleAlert]:
    """Flag suicidal attacks and favorable attack opportunities."""
    alerts: list[RuleAlert] = []
    your_attackers = [c for c in state.you.board if not c.tapped]
    opp_blockers = state.opponent.board

    for attacker in your_attackers:
        best_block = _find_best_blocker(attacker, opp_blockers)
        if best_block is None:
            continue
        attacker_survives = (
            attacker.toughness > best_block.power
            and "deathtouch" not in best_block.keywords
        ) or "indestructible" in attacker.keywords
        blocker_dies = best_block.toughness <= attacker.power or "deathtouch" in attacker.keywords

        if not attacker_survives and not blocker_dies:
            alerts.append(RuleAlert(
                severity="WARNING",
                message=f"Don't attack with {_display_name(attacker)} ({attacker.power}/{attacker.toughness}) — loses to {_display_name(best_block)} ({best_block.power}/{best_block.toughness})",
            ))
        elif not attacker_survives and blocker_dies:
            alerts.append(RuleAlert(
                severity="WARNING",
                message=f"Risky trade: {_display_name(attacker)} trades with {_display_name(best_block)}",
            ))
        elif blocker_dies and attacker_survives:
            alerts.append(RuleAlert(
                severity="INFO",
                message=f"Favorable attack: {_display_name(attacker)} kills {_display_name(best_block)} and survives",
            ))

    return alerts


def check_removal(state: GameState) -> list[RuleAlert]:
    """Flag when a castable removal spell can kill the top threat."""
    if not state.opponent.board or not state.you.hand:
        return []

    top_threat = max(state.opponent.board, key=_threat_score)
    alerts: list[RuleAlert] = []

    for card in state.you.hand:
        if not card.castable:
            continue
        oracle = card_db.get_oracle(card.name).lower()
        if not oracle:
            continue
        is_removal = any(marker in oracle for marker in _REMOVAL_ORACLE_MARKERS)
        if is_removal:
            alerts.append(RuleAlert(
                severity="INFO",
                message=f"{card.name} can remove top threat {top_threat.name} ({top_threat.power}/{top_threat.toughness})",
            ))
            break  # Only flag once

    return alerts


def check_surveil(state: GameState) -> list[RuleAlert]:
    """Flag castable cards in hand that have surveil, suggesting library manipulation."""
    alerts: list[RuleAlert] = []
    for card in state.you.hand:
        if not card.castable:
            continue
        oracle = card_db.get_oracle(card.name).lower()
        if "surveil" in oracle:
            alerts.append(RuleAlert(
                severity="INFO",
                message=f"Surveil available: cast {card.name} to look at top of library",
            ))
    return alerts


def check_mulligan(state: GameState) -> list[RuleAlert]:
    """Analyse the opening hand at turn 1 (MTGA's first turnNumber).

    MTGA starts with turnNumber=1, so turn 0 never occurs in practice.

    Fires:
      turn == 1, any hand size  → opening hand (before or just after keep decision)
      turn == 2, hand_size < 7 → player mulliganed and game is now turn 2
    """
    hand = state.you.hand
    if not hand:
        return []
    hand_size = len(hand)

    if state.turn == 1:
        pass  # opening hand — always analyse
    elif state.turn == 2 and hand_size < 7:
        pass  # mulliganed hand carried into turn 2
    else:
        return []

    lands = [c for c in hand if "land" in card_db.get_type_line(c.name).lower()]
    spells = [c for c in hand if c not in lands]
    land_count = len(lands)

    # No lands at all
    if land_count == 0:
        return [RuleAlert(
            severity="DANGER",
            message=f"No lands in {hand_size}-card hand — mulligan strongly recommended",
        )]

    # Only 1 land in a large hand
    if land_count == 1 and hand_size >= 6:
        return [RuleAlert(
            severity="WARNING",
            message=f"Only 1 land in {hand_size}-card hand — mulligan recommended",
        )]

    # Flooded (one fewer spell than lands)
    if land_count >= hand_size - 1 and hand_size >= 6:
        return [RuleAlert(
            severity="WARNING",
            message=f"{land_count}/{hand_size} lands in hand — flood risk, consider mulligan",
        )]

    # Colour mismatch: spells need colours the hand's lands can't produce
    needed: set[str] = set()
    for card in spells:
        needed.update(card.colors)

    if needed:
        available: set[str] = set()
        for card in lands:
            base = card.name.lower().replace("snow-covered ", "")
            if base in _BASIC_LAND_COLORS:
                available.update(_BASIC_LAND_COLORS[base])
            else:
                # Non-basic: infer from type line subtypes (e.g. "Land — Forest Mountain")
                tl = card_db.get_type_line(card.name).lower()
                for basic, colors in _BASIC_LAND_COLORS.items():
                    if basic in tl:
                        available.update(colors)

        missing = needed - available
        if missing:
            missing_str = "/".join(_COLOR_NAMES.get(c, c) for c in sorted(missing))
            return [RuleAlert(
                severity="WARNING",
                message=f"Missing {missing_str} mana source in hand — colour screw risk",
            )]

    # Hand passes all checks — recommend keeping, add probability context if decklist loaded
    prob_note = ""
    if _decklist.active_deck:
        deck = _decklist.active_deck
        deck_size = sum(deck.values())
        total_lands_in_deck = sum(
            count for name, count in deck.items()
            if "land" in card_db.get_type_line(name).lower()
        )
        if deck_size > hand_size and total_lands_in_deck > land_count:
            remaining_deck = deck_size - hand_size
            remaining_lands = total_lands_in_deck - land_count
            lands_needed = max(0, 3 - land_count)  # target ≥3 by turn 4
            draws_available = 4  # turns 1-4
            if lands_needed > 0:
                p = hypergeometric_cdf_at_least(
                    lands_needed, remaining_deck, remaining_lands, draws_available
                )
                prob_note = f" | {p:.0%} to hit 3 lands by T4"
            else:
                prob_note = " | already at 3+ lands"

    return [RuleAlert(
        severity="INFO",
        message=f"Hand looks keepable: {land_count} lands, {len(spells)} spells in {hand_size} cards{prob_note}",
    )]


def check_lethal_clock(state: GameState) -> list[RuleAlert]:
    """Calculate how many attack steps each player needs to win at current board power.

    Tapped creatures are excluded from your offensive clock (they can't attack).
    Returns INFO with clock numbers and WARNING if the opponent's clock is faster.
    """
    your_power = sum(c.power for c in state.you.board if not c.tapped)
    opp_power = sum(c.power for c in state.opponent.board)

    if your_power == 0 and opp_power == 0:
        return []

    your_turns = math.ceil(state.opponent.life / your_power) if your_power > 0 else 999
    opp_turns = math.ceil(state.you.life / opp_power) if opp_power > 0 else 999

    parts: list[str] = []
    if your_power > 0:
        parts.append(f"you kill in {your_turns} attack(s)")
    if opp_power > 0:
        parts.append(f"opponent kills you in {opp_turns} attack(s)")

    severity = "WARNING" if opp_turns < your_turns else "INFO"
    return [RuleAlert(
        severity=severity,
        message="Lethal clock: " + ", ".join(parts),
    )]


def check_role(state: GameState) -> list[RuleAlert]:
    """Classify the player's role as Aggressor, Defender, or Flexible.

    Score combines board power advantage and life differential.
    Returns INFO with role and a brief reason.
    """
    your_power = sum(c.power for c in state.you.board)
    opp_power = sum(c.power for c in state.opponent.board)

    if your_power == 0 and opp_power == 0:
        return []

    life_diff = state.you.life - state.opponent.life
    power_diff = your_power - opp_power
    score = power_diff + (life_diff / 5.0)

    if score >= 3:
        role = "Aggressor"
        reason = "board and life lead — press for damage"
    elif score <= -3:
        role = "Defender"
        reason = "behind on board or life — prioritise blocking and answers"
    else:
        role = "Flexible"
        reason = "even game — adapt to opponent's next move"

    return [RuleAlert(
        severity="INFO",
        message=f"Role: {role} — {reason}",
    )]


def check_outs(state: GameState) -> list[RuleAlert]:
    """Show draw probabilities for lands and win-cons given the known library size.

    Requires decklist.active_deck to be populated and state.you.library_size > 0.
    Win-cons are defined as non-land cards with CMC >= 5 in the deck.
    """
    if not _decklist.active_deck:
        return []
    library_size = getattr(state.you, "library_size", 0)
    if library_size <= 0:
        return []

    # Count remaining lands in deck (total deck lands minus seen cards rough estimate)
    cards_seen: set[str] = getattr(state, "cards_seen", set())
    deck = _decklist.active_deck

    land_outs = 0
    wincon_outs = 0
    for name, count in deck.items():
        is_land = "land" in card_db.get_type_line(name).lower()
        seen_count = min(count, sum(1 for s in cards_seen if s == name))
        remaining = max(0, count - seen_count)
        if is_land:
            land_outs += remaining
        elif card_db.get_cmc(name) >= 5:
            wincon_outs += remaining

    p_land = prob_draw_at_least_one(library_size, land_outs, 1)
    p_wincon = prob_draw_at_least_one(library_size, wincon_outs, 1) if wincon_outs > 0 else 0.0

    return [RuleAlert(
        severity="INFO",
        message=(
            f"Draw odds (library {library_size}): "
            f"{p_land:.0%} land, {p_wincon:.0%} win-con"
        ),
    )]


def run_all(state: GameState) -> list[RuleAlert]:
    """Run all checks and return combined alerts, most severe first."""
    alerts: list[RuleAlert] = []
    alerts.extend(check_mulligan(state))
    alerts.extend(check_lethal(state))
    alerts.extend(check_lethal_clock(state))
    alerts.extend(check_role(state))
    alerts.extend(check_threats(state))
    alerts.extend(check_combat(state))
    alerts.extend(check_removal(state))
    alerts.extend(check_surveil(state))
    alerts.extend(check_outs(state))
    return alerts


def _threat_score(card: BoardCard) -> float:
    score = float(card.power)
    for kw in card.keywords:
        score *= _KEYWORD_MULTIPLIERS.get(kw, 1.0)
    return score


def _find_best_blocker(attacker: BoardCard, blockers: list[BoardCard]) -> BoardCard | None:
    """Find the blocker most likely to be assigned — highest power blocker that can legally block."""
    # Flying attackers can only be blocked by flying/reach creatures
    if "flying" in attacker.keywords:
        valid = [b for b in blockers if "flying" in b.keywords or "reach" in b.keywords]
    else:
        valid = list(blockers)  # all creatures can block a non-flying attacker
    if not valid:
        return None
    return max(valid, key=lambda b: b.power)

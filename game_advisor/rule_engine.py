"""
Synchronous rule-based checks that run on every game state update.
Returns a list of RuleAlert objects for immediate display in the dashboard.
"""
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
import card_db
from game_state import BoardCard, GameState, HandCard, RuleAlert

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


def check_lethal(state: GameState) -> list[RuleAlert]:
    """Fire DANGER if your untapped creatures can deal >= opponent life total."""
    untapped = [c for c in state.you.board if not c.tapped]
    total_power = sum(c.power for c in untapped)
    if untapped and total_power >= state.opponent.life:
        names = ", ".join(c.name for c in untapped)
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
        message=f"Top threat: {top.name} ({top.power}/{top.toughness}, {kw_str}) — score {score:.1f}",
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
                message=f"Don't attack with {attacker.name} ({attacker.power}/{attacker.toughness}) — loses to {best_block.name} ({best_block.power}/{best_block.toughness})",
            ))
        elif not attacker_survives and blocker_dies:
            alerts.append(RuleAlert(
                severity="WARNING",
                message=f"Risky trade: {attacker.name} trades with {best_block.name}",
            ))
        elif blocker_dies and attacker_survives:
            alerts.append(RuleAlert(
                severity="INFO",
                message=f"Favorable attack: {attacker.name} kills {best_block.name} and survives",
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


def run_all(state: GameState) -> list[RuleAlert]:
    """Run all checks and return combined alerts, most severe first."""
    alerts: list[RuleAlert] = []
    alerts.extend(check_lethal(state))
    alerts.extend(check_threats(state))
    alerts.extend(check_combat(state))
    alerts.extend(check_removal(state))
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

"""
Post-game decision logger.

Records rule engine recommendations and infers what the player actually did
by comparing consecutive game states.  Writes one JSON file per game to
game_advisor/logs/.
"""
from __future__ import annotations
import json
import os
import pathlib
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional

from game_state import GameState, RuleAlert


@dataclass
class Decision:
    turn: int
    phase: str
    recommendations: list[str]          # rule alerts at the time
    inferred_action: str = "unknown"    # what we think the player did
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


class DecisionLog:
    def __init__(self, log_dir: str = ""):
        if not log_dir:
            log_dir = str(pathlib.Path(__file__).parent / "logs")
        self._log_dir = log_dir
        os.makedirs(log_dir, exist_ok=True)
        self._entries: list[Decision] = []
        self._prev_state: Optional[GameState] = None

    def record(self, state: GameState, alerts: list[RuleAlert]) -> None:
        """Record recommendations for the current state. Must be called before
        infer_action so the previous state is captured correctly."""
        recs = [f"[{a.severity}] {a.message}" for a in alerts]
        action = "unknown"
        if self._prev_state is not None:
            action = self._infer_action(self._prev_state, state)
        self._entries.append(Decision(
            turn=state.turn,
            phase=state.phase,
            recommendations=recs,
            inferred_action=action,
        ))
        self._prev_state = state

    def flush(self, game_id: str = "") -> str:
        """Write the accumulated log to disk and reset.  Returns the file path."""
        path = self._write_to_disk(game_id)
        if path:
            self._entries = []
            self._prev_state = None
        return path

    def write_snapshot(self, game_id: str = "") -> str:
        """Write current entries to disk WITHOUT clearing them.

        Used when the user wants to view the log for the current in-progress
        game (e.g. pressing D). Overwrites any existing snapshot for the same
        game so the viewer always sees the latest state.
        """
        return self._write_to_disk(game_id, snapshot=True)

    def _write_to_disk(self, game_id: str = "", snapshot: bool = False) -> str:
        """Internal: serialise entries to a JSON file. Returns the file path or ''."""
        if not self._entries:
            return ""
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_id = game_id.replace("/", "_").replace(":", "_")[:32] if game_id else "game"
        if snapshot:
            filename = f"snapshot_{safe_id}.json"
        else:
            filename = f"{ts}_{safe_id}.json"
        path = os.path.join(self._log_dir, filename)
        data = {
            "game_id": game_id,
            "recorded_at": ts,
            "decisions": [asdict(e) for e in self._entries],
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        return path

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _infer_action(self, prev: GameState, curr: GameState) -> str:
        """Heuristically infer the player's action from state differences."""
        actions: list[str] = []

        # Life total changes
        if curr.opponent.life < prev.opponent.life:
            dmg = prev.opponent.life - curr.opponent.life
            actions.append(f"dealt {dmg} damage to opponent")
        if curr.you.life < prev.you.life:
            dmg = prev.you.life - curr.you.life
            actions.append(f"took {dmg} damage")

        # Cards played from hand (hand shrinks, board/graveyard grows)
        prev_hand_names = {c.name for c in prev.you.hand}
        curr_hand_names = {c.name for c in curr.you.hand}
        played = prev_hand_names - curr_hand_names
        for name in played:
            actions.append(f"cast {name}")

        # New creatures on board
        prev_board_names = {c.name for c in prev.you.board}
        curr_board_names = {c.name for c in curr.you.board}
        entered = curr_board_names - prev_board_names
        for name in entered:
            if name not in played:
                actions.append(f"{name} entered play")

        # Opponent creatures removed
        prev_opp_names = {c.name for c in prev.opponent.board}
        curr_opp_names = {c.name for c in curr.opponent.board}
        removed = prev_opp_names - curr_opp_names
        for name in removed:
            actions.append(f"opponent lost {name}")

        return "; ".join(actions) if actions else "passed / no visible change"

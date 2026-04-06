"""
Async GPT-4o advisor. Fires in a background thread on significant state
changes. Caches responses by state hash to avoid redundant API calls.
Rate-limited to at most one call per min_interval_seconds.
"""
from __future__ import annotations

import hashlib
import sys
import pathlib
import threading
import time
from typing import Callable, Optional

import importlib.util as _ilu

# Import game_advisor/config.py explicitly by path to avoid shadowing by the
# root-level config.py when the parent directory is on sys.path.
_config_path = pathlib.Path(__file__).parent / "config.py"
_spec = _ilu.spec_from_file_location("game_advisor_config", _config_path)
config = _ilu.module_from_spec(_spec)  # type: ignore[arg-type]
_spec.loader.exec_module(config)  # type: ignore[union-attr]

import openai

from game_state import GameState


class LLMAdvisor:
    OFFLINE_MESSAGE = "Advisor offline — rule alerts active."

    def __init__(
        self,
        api_key: str = config.OPENAI_API_KEY,
        model: str = config.OPENAI_MODEL,
        timeout: int = config.LLM_TIMEOUT_SECONDS,
        min_interval_seconds: int = config.LLM_MIN_INTERVAL_SECONDS,
    ):
        self._client = openai.OpenAI(api_key=api_key)
        self._model = model
        self._timeout = timeout
        self._min_interval = min_interval_seconds
        self._cache: dict[str, str] = {}     # state_hash -> advice text
        self._last_call_time: float = 0.0
        self._last_advice: str = ""
        self._lock = threading.Lock()

    def request_advice_async(
        self,
        state: GameState,
        on_complete: Callable[[str], None],
    ) -> None:
        """Fire an async advice request. Calls on_complete(text) when done."""
        def run():
            result = self._call_api(state)
            on_complete(result)

        threading.Thread(target=run, daemon=True).start()

    def _call_api(self, state: GameState) -> str:
        """Call GPT-4o synchronously. Returns cached or rate-limited result when applicable."""
        with self._lock:
            state_hash = _state_hash(state)

            # Return cached response for identical state
            if state_hash in self._cache:
                return self._cache[state_hash]

            # Rate limit: return last advice if called too soon
            now = time.monotonic()
            if now - self._last_call_time < self._min_interval and self._last_advice:
                return self._last_advice

            prompt = self._build_prompt(state)
            try:
                response = self._client.chat.completions.create(
                    model=self._model,
                    messages=[
                        {"role": "system", "content": (
                            "You are an expert Magic: The Gathering advisor. "
                            "Give concise, actionable advice in 3 numbered points. "
                            "Be specific about card names and combat math."
                        )},
                        {"role": "user", "content": prompt},
                    ],
                    timeout=self._timeout,
                    max_tokens=300,
                )
                advice = response.choices[0].message.content.strip()
            except Exception:
                advice = self.OFFLINE_MESSAGE

            self._cache[state_hash] = advice
            self._last_call_time = time.monotonic()
            self._last_advice = advice
            return advice

    def _build_prompt(self, state: GameState) -> str:
        your_hand = ", ".join(
            f"{c.name} ({c.mana_cost}){' [castable]' if c.castable else ''}"
            for c in state.you.hand
        ) or "Empty"
        your_board = ", ".join(
            f"{c.name} ({c.power}/{c.toughness}{(' ' + ' '.join(c.keywords)) if c.keywords else ''})"
            for c in state.you.board
        ) or "Empty"
        opp_board = ", ".join(
            f"{c.name} ({c.power}/{c.toughness}{(' ' + ' '.join(c.keywords)) if c.keywords else ''})"
            for c in state.opponent.board
        ) or "Empty"
        recent = "; ".join(state.recent_events[-3:]) if state.recent_events else "None"

        return (
            f"Turn {state.turn} | You: {state.you.life} life | "
            f"Opponent: {state.opponent.life} life | Phase: {state.phase}\n\n"
            f"YOUR HAND: {your_hand}\n"
            f"YOUR BOARD: {your_board}\n"
            f"OPPONENT BOARD: {opp_board}\n"
            f"Recent events: {recent}\n\n"
            "Answer briefly:\n"
            "1. Best play this turn?\n"
            "2. Combat recommendation?\n"
            "3. Highest priority threat to address?"
        )


def _state_hash(state: GameState) -> str:
    key = (
        state.turn,
        state.phase,
        state.you.life,
        state.opponent.life,
        tuple(sorted(c.name for c in state.you.hand)),
        tuple(sorted(c.name for c in state.you.board)),
        tuple(sorted(c.name for c in state.opponent.board)),
    )
    return hashlib.md5(str(key).encode()).hexdigest()

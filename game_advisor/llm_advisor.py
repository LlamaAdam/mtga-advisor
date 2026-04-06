"""
Async LLM advisor. Supports OpenAI, OpenRouter, and Ollama backends.
Fires in a background thread on significant state changes. Caches
responses by state hash to avoid redundant API calls. Rate-limited
to at most one call per min_interval_seconds.
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
import decklist as _decklist

_COT_SYSTEM_PROMPT = (
    "You are an expert Magic: The Gathering advisor. Think step by step:\n"
    "1. BOARD ASSESSMENT: Who is ahead? List key threats and advantages.\n"
    "2. HAND EVALUATION: What plays are available this turn? What is the best card to cast?\n"
    "3. RECOMMENDED ACTION: Give a specific, concrete recommendation (card name + target).\n"
    "4. SUMMARY: One sentence — the single most important thing to do right now.\n\n"
    "Keep the total response under 200 words. Use card names. Include combat math when relevant."
)


class LLMAdvisor:
    OFFLINE_MESSAGE = "Advisor offline — rule alerts active."

    def __init__(
        self,
        api_key: str = config.OPENAI_API_KEY,
        model: str = config.OPENAI_MODEL,
        timeout: int = config.LLM_TIMEOUT_SECONDS,
        min_interval_seconds: int = config.LLM_MIN_INTERVAL_SECONDS,
        backend: str = config.LLM_BACKEND,
    ):
        _BASE_URLS = {
            "ollama": "http://localhost:11434/v1",
            "openrouter": "https://openrouter.ai/api/v1",
            "openai": None,  # default
        }
        base_url = _BASE_URLS.get(backend)
        # Ollama doesn't require a real key; use a placeholder if none set
        if backend == "ollama" and not api_key:
            api_key = "ollama"
        self._client = openai.OpenAI(
            api_key=api_key,
            **({"base_url": base_url} if base_url else {}),
        )
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
                        {"role": "system", "content": _COT_SYSTEM_PROMPT},
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
        compressed = compress_state(state)
        deck_line = ""
        if _decklist.active_deck:
            deck_line = "\n" + _decklist.deck_composition(_decklist.active_deck)
            hand_ctx = _decklist.hand_overlap_summary(
                _decklist.active_deck,
                [c.name for c in state.you.hand],
            )
            if hand_ctx:
                deck_line += " | " + hand_ctx
        return compressed + deck_line


def compress_state(state: GameState) -> str:
    """Return a compact single-line board state string for the LLM prompt.

    Format:
      T{turn} {phase} | You {life}hp | Opp {life}hp | Board:[...] | Opp:[...] | Hand:[...] | Mana:{n}
    """
    def fmt_board(cards) -> str:
        if not cards:
            return "[]"
        parts = []
        for c in cards:
            kw = (" " + ",".join(c.keywords)) if c.keywords else ""
            tap = "~" if c.tapped else ""
            parts.append(f"{c.name}{tap}({c.power}/{c.toughness}{kw})")
        return "[" + ", ".join(parts) + "]"

    def fmt_hand(cards) -> str:
        if not cards:
            return "[]"
        return "[" + ", ".join(
            f"{c.name}({c.mana_cost})" + ("*" if c.castable else "")
            for c in cards
        ) + "]"

    return (
        f"T{state.turn} {state.phase} | "
        f"You {state.you.life}hp | Opp {state.opponent.life}hp | "
        f"Board:{fmt_board(state.you.board)} | "
        f"Opp:{fmt_board(state.opponent.board)} | "
        f"Hand:{fmt_hand(state.you.hand)} | "
        f"Mana:{state.you.mana_available}"
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

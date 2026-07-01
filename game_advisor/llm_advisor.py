"""
Async LLM advisor. Supports OpenAI, OpenRouter, Ollama, and the
subscription `claude` CLI as backends. Fires in a background thread on
significant state changes. Caches responses by state hash to avoid
redundant API calls. Rate-limited to at most one call per
min_interval_seconds.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import threading
import time
from typing import Callable, Optional

import config
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

# Env vars that could redirect the subscription `claude` CLI to a BILLED
# endpoint or inject an API key. Scrubbed from the child process so
# LLM_BACKEND=claude always uses the logged-in subscription, never
# per-token billing — even if a key is set for other tooling (e.g. the
# openrouter backend's OPENAI_API_KEY, which shares this process's env).
_CLAUDE_CLI_BILLING_REDIRECT_VARS = {"CLAUDE_CODE_USE_BEDROCK", "CLAUDE_CODE_USE_VERTEX"}


def _claude_cli_available() -> bool:
    return shutil.which("claude") is not None


def _complete_via_claude_cli(system: str, user_msg: str, *, timeout: int = 60) -> str:
    """Run a completion through the subscription `claude` CLI instead of an
    API-billed backend. Mirrors commander_builder's _curator_complete_via_cli.

    system + user are sent on STDIN (not argv) to avoid command-line length
    limits. Raises RuntimeError on failure — callers should catch and fall
    back to LLMAdvisor.OFFLINE_MESSAGE.
    """
    claude = shutil.which("claude")
    if not claude:
        raise RuntimeError("`claude` CLI not found on PATH (needed for "
                            "LLM_BACKEND=claude)")

    prompt = f"{system}\n\n---\n\n{user_msg}"
    env = {k: v for k, v in os.environ.items()
           if not k.startswith("ANTHROPIC_")
           and k not in _CLAUDE_CLI_BILLING_REDIRECT_VARS}
    cmd = [claude, "-p", "--output-format", "json"]

    last_err = ""
    for attempt in range(2):
        try:
            proc = subprocess.run(
                cmd, input=prompt, env=env, capture_output=True, text=True,
                encoding="utf-8", errors="replace", timeout=timeout,
            )
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(f"claude CLI timed out after {timeout}s") from exc

        if proc.returncode != 0:
            last_err = (f"claude CLI failed rc={proc.returncode}: "
                        f"{(proc.stderr or proc.stdout or '')[-300:]}")
        else:
            try:
                data = json.loads(proc.stdout)
            except json.JSONDecodeError:
                text = proc.stdout.strip()
                if text:
                    return text
                last_err = "claude CLI returned empty non-JSON output"
                data = None
            if isinstance(data, dict):
                if data.get("is_error"):
                    last_err = f"claude CLI reported error: {data.get('result')}"
                else:
                    result = str(data.get("result") or "")
                    if result.strip():
                        return result
                    last_err = "claude CLI returned empty result"

        if attempt == 0:
            time.sleep(3)  # brief backoff before the single retry

    raise RuntimeError(f"claude CLI failed after retry: {last_err}")


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
        self._backend = backend
        if backend == "claude":
            # Subscription CLI backend — no OpenAI-compatible client needed.
            self._client = None
        else:
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

    def _complete(self, system: str, user: str, *, max_tokens: int) -> str:
        """Dispatch a completion to the configured backend. Returns
        OFFLINE_MESSAGE on any failure (network, auth, CLI missing, etc.)."""
        if self._backend == "claude":
            try:
                return _complete_via_claude_cli(system, user, timeout=self._timeout)
            except Exception:
                return self.OFFLINE_MESSAGE
        try:
            response = self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                timeout=self._timeout,
                max_tokens=max_tokens,
            )
            return response.choices[0].message.content.strip()
        except Exception:
            return self.OFFLINE_MESSAGE

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

    def request_post_game_analysis_async(
        self,
        decisions: list,
        outcome: str,
        on_complete: Callable[[str], None],
    ) -> None:
        """Analyse the game's decision log after a loss and call on_complete(text).

        decisions — list of Decision dataclass instances from DecisionLog
        outcome   — "loss" | "win" | "draw"
        """
        def run():
            result = self._call_post_game_api(decisions, outcome)
            on_complete(result)

        threading.Thread(target=run, daemon=True).start()

    def _call_post_game_api(self, decisions: list, outcome: str) -> str:
        """Build a post-game analysis prompt and call the LLM."""
        if not decisions:
            return "No game data recorded to analyse."

        # Summarise the game turn-by-turn (cap at 30 turns to stay within token limits)
        turn_lines: list[str] = []
        for d in decisions[-30:]:
            warnings = [r for r in d.recommendations if "[DANGER]" in r or "[WARNING]" in r]
            action = d.inferred_action
            if warnings:
                warn_str = "; ".join(w.replace("[DANGER] ", "").replace("[WARNING] ", "") for w in warnings[:2])
                turn_lines.append(f"T{d.turn} {d.phase}: action='{action}' | warnings='{warn_str}'")
            elif action and action != "passed / no visible change":
                turn_lines.append(f"T{d.turn} {d.phase}: action='{action}'")

        game_summary = "\n".join(turn_lines) if turn_lines else "(no significant events logged)"

        system = (
            "You are an expert Magic: The Gathering coach reviewing a game replay. "
            "Be concise, specific, and constructive. Focus on the 2-3 biggest mistakes "
            "or missed opportunities. Reference actual turn numbers and card names where available."
        )
        user = (
            f"I just lost a game of MTG Arena. Here is a turn-by-turn log of key actions "
            f"and any warnings the advisor flagged:\n\n"
            f"{game_summary}\n\n"
            f"In 2-3 short paragraphs, explain: (1) the biggest mistake(s) or missed opportunities, "
            f"(2) what I should have done differently, and (3) one key lesson to take away."
        )

        return self._complete(system, user, max_tokens=400)

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
            advice = self._complete(_COT_SYSTEM_PROMPT, prompt, max_tokens=300)

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
        appendix = card_text_appendix(state)
        return compressed + deck_line + appendix


def card_text_appendix(
    state: GameState, max_chars_per_card: int = 200, max_cards: int = 12,
) -> str:
    """Render an oracle-text appendix for the LLM prompt.

    Includes oracle text for cards the LLM is most likely to reason about:
    your hand (the playable choices) plus opponent's board (the threats
    you're responding to). Each entry is truncated to ``max_chars_per_card``
    so a 7-card hand + 3 opponent threats stays around ~2000 prompt chars
    instead of ballooning to 5k+.

    Card text is sourced via ``card_db.get_oracle`` which prefers the
    shared `mtg_cards/oracle_snapshots/` store (current Oracle text,
    post-errata) over the local cache. This is the FP-B change: the
    LLM advisor reads authoritative card text rather than relying on
    its training-data memory of cards (which lags errata).

    Returns "" when no oracle text is available for any card — keeps
    the prompt tight when running with an empty cache.
    """
    from draft_helper import card_db

    cards: list[tuple[str, str]] = []  # (label, name) pairs
    seen: set[str] = set()
    for c in state.you.hand:
        if c.name in seen:
            continue
        cards.append(("hand", c.name))
        seen.add(c.name)
    for c in state.opponent.board:
        if c.name in seen:
            continue
        cards.append(("opp-board", c.name))
        seen.add(c.name)
        if len(cards) >= max_cards:
            break

    lines: list[str] = []
    for label, name in cards[:max_cards]:
        oracle = card_db.get_oracle(name)
        if not oracle:
            continue
        # Collapse newlines, truncate.
        oracle_compact = " ".join(oracle.split())
        if len(oracle_compact) > max_chars_per_card:
            oracle_compact = oracle_compact[: max_chars_per_card - 1] + "…"
        lines.append(f"  - [{label}] {name}: {oracle_compact}")

    if not lines:
        return ""
    return "\nCard text reference (current Oracle):\n" + "\n".join(lines)


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

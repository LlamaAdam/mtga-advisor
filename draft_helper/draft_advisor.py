"""
Draft pick LLM advisor.

Uses the same Ollama/OpenAI backend as game_advisor to explain close picks
and provide strategic context. Fires asynchronously so it never blocks the
overlay or pack output.

Configuration via environment variables (same .env as game_advisor):
  LLM_BACKEND  = ollama | openai | openrouter  (default: ollama)
  LLM_MODEL    = llama3 | gpt-4o | ...         (default: llama3)

If Ollama is not running the advisor prints nothing — it degrades silently.
"""
from __future__ import annotations

import os
import pathlib
import threading
from typing import Callable

# ---------------------------------------------------------------------------
# LLM client setup (mirrors game_advisor/llm_advisor.py backend logic)
# ---------------------------------------------------------------------------

_env_file = pathlib.Path(__file__).parent.parent / "game_advisor" / ".env"
if _env_file.exists():
    try:
        from dotenv import load_dotenv
        load_dotenv(_env_file)
    except ImportError:
        pass

_BACKEND: str = os.environ.get("LLM_BACKEND", "ollama").lower()
_MODEL:   str = os.environ.get("LLM_MODEL", {
    "ollama":      "llama3",
    "openrouter":  "openai/gpt-4o",
    "openai":      "gpt-4o",
}.get(_BACKEND, "llama3"))
_API_KEY: str = os.environ.get("OPENAI_API_KEY", "") or ("ollama" if _BACKEND == "ollama" else "")
_TIMEOUT: int = int(os.environ.get("LLM_TIMEOUT_SECONDS", "30"))

_BASE_URLS = {
    "ollama":      "http://localhost:11434/v1",
    "openrouter":  "https://openrouter.ai/api/v1",
    "openai":      None,
}

_client = None

def _get_client():
    global _client
    if _client is not None:
        return _client
    try:
        import openai
        base_url = _BASE_URLS.get(_BACKEND)
        _client = openai.OpenAI(
            api_key=_API_KEY,
            **({"base_url": base_url} if base_url else {}),
        )
    except ImportError:
        pass
    return _client


# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

_DRAFT_SYSTEM_PROMPT = (
    "You are an expert Magic: The Gathering limited (draft) advisor. "
    "You give concise, specific pick advice. "
    "Focus on draft theory: card quality, mana curve, synergy, and signals. "
    "Keep responses under 120 words. Use card names. Be direct."
)

_REVIEW_SYSTEM_PROMPT = (
    "You are an expert Magic: The Gathering limited (draft) coach doing a mid-draft check-in. "
    "Analyse the picks made so far and give strategic guidance. "
    "Be direct and specific. Mention card names. Keep total response under 200 words. "
    "Structure your response as:\n"
    "DIRECTION: one sentence on whether the color/archetype is correct.\n"
    "CURVE: one sentence on mana curve health (2-drops, late-game balance).\n"
    "SYNERGY: one sentence on synergies forming or missing.\n"
    "WATCH FOR: one sentence on what to prioritize in upcoming picks."
)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def explain_pick_async(
    pack_number: int,
    pick_number: int,
    top_cards: list[tuple[str, float | None, str]],   # (name, wr, grade)
    picks_so_far: list[str],
    main_colors: list[str],
    on_complete: Callable[[str], None],
) -> None:
    """
    Fire an async LLM explanation for the current pick situation.
    Calls on_complete(text) from a background thread when done.

    Only fires when the decision is genuinely close (top-2 within 2pp)
    or when there are no clearly dominant on-color options.
    """
    client = _get_client()
    if client is None:
        return

    prompt = _build_prompt(pack_number, pick_number, top_cards, picks_so_far, main_colors)

    def run():
        try:
            response = client.chat.completions.create(
                model=_MODEL,
                messages=[
                    {"role": "system", "content": _DRAFT_SYSTEM_PROMPT},
                    {"role": "user",   "content": prompt},
                ],
                timeout=_TIMEOUT,
                max_tokens=180,
            )
            text = response.choices[0].message.content.strip()
            on_complete(text)
        except Exception:
            pass  # Degrade silently if LLM is unavailable

    threading.Thread(target=run, daemon=True, name="draft-advisor").start()


def should_explain(
    top_cards: list[tuple[str, float | None, str]],
    main_colors: list[str],
    pack_number: int,
    pick_number: int,
) -> bool:
    """
    Return True when an LLM explanation adds value:
      - First pick of pack 2 or 3 (always useful — new pack strategy)
      - Top-2 cards within 2.0pp of each other (genuinely close decision)
      - No card grades B or better AND deck has established colors (no clear bomb)
    """
    # Always explain the first pick of packs 2 and 3
    if pick_number == 1 and pack_number >= 2:
        return True

    if len(top_cards) < 2:
        return False

    wr1 = top_cards[0][1]
    wr2 = top_cards[1][1]
    if wr1 is not None and wr2 is not None and (wr1 - wr2) <= 2.0:
        return True

    # No clear bomb (all cards below B = 57%) and colors are established
    if main_colors and all(wr is None or wr < 57.0 for _, wr, _ in top_cards[:3]):
        return True

    return False


def review_draft_async(
    pack_number: int,
    pick_number: int,
    picks: list[tuple[str, str, str]],   # (card_name, grade, color_identity)
    main_colors: list[str],
    curve: dict[int, int],               # cmc → count of cards at that cmc
    on_complete: Callable[[str], None],
) -> None:
    """
    Fire an async mid-draft review every N picks.
    Assesses direction, curve health, synergies, and what to look for next.
    Calls on_complete(text) from a background thread when done.
    """
    client = _get_client()
    if client is None:
        return

    prompt = _build_review_prompt(pack_number, pick_number, picks, main_colors, curve)

    def run() -> None:
        try:
            response = client.chat.completions.create(
                model=_MODEL,
                messages=[
                    {"role": "system", "content": _REVIEW_SYSTEM_PROMPT},
                    {"role": "user",   "content": prompt},
                ],
                timeout=_TIMEOUT,
                max_tokens=250,
            )
            text = response.choices[0].message.content.strip()
            on_complete(text)
        except Exception:
            pass

    threading.Thread(target=run, daemon=True, name="draft-reviewer").start()


def _build_review_prompt(
    pack_number: int,
    pick_number: int,
    picks: list[tuple[str, str, str]],
    main_colors: list[str],
    curve: dict[int, int],
) -> str:
    color_str  = "/".join(main_colors) if main_colors else "undecided"
    total      = len(picks)

    # Full pick list with grade and color
    pick_lines = [f"  {grade:<4} {colors or 'C':>4}  {name}"
                  for name, grade, colors in picks]
    picks_block = "\n".join(pick_lines) if pick_lines else "  (none)"

    # Curve summary: 1-drop through 6+
    curve_parts = []
    for cmc in range(1, 7):
        label = f"{cmc}+" if cmc == 6 else str(cmc)
        count = sum(v for k, v in curve.items() if (k >= 6 if cmc == 6 else k == cmc))
        curve_parts.append(f"{label}-drop:{count}")
    curve_str = "  ".join(curve_parts)

    return (
        f"Mid-draft check-in after pick {total} "
        f"(Pack {pack_number} Pick {pick_number})\n"
        f"Current colors: {color_str}\n\n"
        f"Picks so far (grade | color | name):\n{picks_block}\n\n"
        f"Mana curve: {curve_str}\n\n"
        "Give a structured review: DIRECTION, CURVE, SYNERGY, WATCH FOR."
    )


def _build_prompt(
    pack_number: int,
    pick_number: int,
    top_cards: list[tuple[str, float | None, str]],
    picks_so_far: list[str],
    main_colors: list[str],
) -> str:
    color_str = "/".join(main_colors) if main_colors else "undecided"
    picks_str = ", ".join(picks_so_far[-8:]) if picks_so_far else "none yet"

    card_lines = []
    for name, wr, grade in top_cards[:5]:
        wr_s = f"{wr:.1f}%" if wr is not None else "N/A"
        card_lines.append(f"  {grade} {wr_s}  {name}")
    cards_block = "\n".join(card_lines)

    context = ""
    if pick_number == 1 and pack_number >= 2:
        context = (
            f"\nThis is the FIRST pick of Pack {pack_number}. "
            "Prioritize the objectively strongest card available — "
            "taking the best card in the pack is often correct even if it pushes "
            "into a new color, because signals and flexibility matter early in a new pack."
        )

    return (
        f"Pack {pack_number} Pick {pick_number} | Deck colors: {color_str}\n"
        f"Recent picks: {picks_str}\n\n"
        f"Cards in pack (sorted best to worst by adjusted win rate):\n{cards_block}\n"
        f"{context}\n\n"
        "Which card should I pick and why? Give a 2-3 sentence explanation."
    )

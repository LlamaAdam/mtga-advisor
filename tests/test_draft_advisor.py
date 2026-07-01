"""Tests for draft_advisor.py — pure-function logic.

LLM client construction and async fire-and-forget calls are not
exercised here (they need the openai client + a network or local
Ollama). What IS testable is the should_explain decision and the
prompt-building helpers.
"""
from __future__ import annotations

import pytest

from draft_helper import draft_advisor


# ---------------------------------------------------------------------------
# should_explain
# ---------------------------------------------------------------------------

def test_should_explain_first_pick_of_pack_2():
    """Pack 2 pick 1 always gets an explanation — new-pack strategy."""
    top = [("Bear", 60.0, "B"), ("Goblin", 55.0, "C")]
    assert draft_advisor.should_explain(top, ["R"], pack_number=2, pick_number=1)


def test_should_explain_first_pick_of_pack_3():
    top = [("Bear", 60.0, "B"), ("Goblin", 55.0, "C")]
    assert draft_advisor.should_explain(top, ["R"], pack_number=3, pick_number=1)


def test_should_explain_close_top_two():
    """When top-2 win rates are within 2pp, explain the pick."""
    top = [("Bear", 60.0, "B"), ("Goblin", 58.5, "B")]
    assert draft_advisor.should_explain(top, ["R"], pack_number=1, pick_number=5)


def test_should_explain_no_clear_bomb_with_colors():
    """No grade-B-or-better card and colors set → explain."""
    top = [("Card1", 56.0, "C"), ("Card2", 54.0, "C"), ("Card3", 53.0, "C")]
    assert draft_advisor.should_explain(top, ["W", "U"], pack_number=1, pick_number=4)


def test_should_not_explain_clear_pick_with_colors():
    """Clear top card (>2pp lead, B-grade or higher) → skip explanation."""
    top = [("Bomb", 62.0, "A"), ("OK", 55.0, "C"), ("Worse", 53.0, "C")]
    assert not draft_advisor.should_explain(
        top, ["W", "U"], pack_number=1, pick_number=5,
    )


def test_should_not_explain_when_only_one_card():
    """Final pick (1 card left in pack) — no choice to explain."""
    top = [("Last", 55.0, "C")]
    assert not draft_advisor.should_explain(
        top, ["W"], pack_number=1, pick_number=14,
    )


def test_should_not_explain_when_colors_unset_and_no_close_call():
    """Pack 1 pick 1 with a clear best card — no need for advice."""
    top = [("Bomb", 62.0, "A"), ("OK", 55.0, "C")]
    assert not draft_advisor.should_explain(
        top, [], pack_number=1, pick_number=1,
    )


def test_should_explain_when_winrates_are_none():
    """Defensive: missing win-rate data shouldn't crash should_explain."""
    top = [("Card1", None, "?"), ("Card2", None, "?")]
    # No close-call comparison possible, no clear bomb (None < 57 by code path
    # since the iterator skips None checks); colors set → triggers branch.
    result = draft_advisor.should_explain(
        top, ["W"], pack_number=1, pick_number=5,
    )
    assert isinstance(result, bool)


# ---------------------------------------------------------------------------
# _build_prompt
# ---------------------------------------------------------------------------

def test_build_prompt_includes_pack_pick_and_colors():
    prompt = draft_advisor._build_prompt(
        pack_number=2, pick_number=1,
        top_cards=[("Lightning Bolt", 60.0, "A"), ("Bear", 55.0, "C")],
        picks_so_far=["Mountain", "Goblin"],
        main_colors=["R"],
    )
    assert "Pack 2 Pick 1" in prompt
    assert "R" in prompt
    assert "Lightning Bolt" in prompt
    assert "Mountain" in prompt or "Goblin" in prompt


def test_build_prompt_first_pick_of_new_pack_adds_context():
    """Pack 2/3 pick 1 should include the new-pack context paragraph."""
    prompt = draft_advisor._build_prompt(
        pack_number=2, pick_number=1,
        top_cards=[("Best", 65.0, "A")],
        picks_so_far=[],
        main_colors=["W"],
    )
    assert "FIRST pick" in prompt or "Prioritize" in prompt


def test_build_prompt_handles_missing_winrates():
    """Cards without win rates render as N/A, not crash."""
    prompt = draft_advisor._build_prompt(
        pack_number=1, pick_number=5,
        top_cards=[("Mystery", None, "?")],
        picks_so_far=[],
        main_colors=[],
    )
    assert "N/A" in prompt
    assert "Mystery" in prompt


def test_build_prompt_undecided_colors_renders():
    prompt = draft_advisor._build_prompt(
        pack_number=1, pick_number=2,
        top_cards=[("Card", 50.0, "C")],
        picks_so_far=[],
        main_colors=[],
    )
    assert "undecided" in prompt


# ---------------------------------------------------------------------------
# _build_review_prompt
# ---------------------------------------------------------------------------

def test_build_review_prompt_renders_picks_and_curve():
    prompt = draft_advisor._build_review_prompt(
        pack_number=2, pick_number=4,
        picks=[
            ("Lightning Bolt", "A", "R"),
            ("Mountain", "C", ""),
            ("Bear", "C", "G"),
        ],
        main_colors=["R"],
        curve={1: 1, 2: 1, 3: 0, 4: 0, 5: 0, 6: 0},
    )
    assert "Pack 2 Pick 4" in prompt
    assert "Lightning Bolt" in prompt
    assert "Bear" in prompt
    # Curve summary should mention drops.
    assert "1-drop" in prompt
    assert "6+-drop" in prompt or "6+" in prompt


def test_build_review_prompt_handles_no_picks():
    prompt = draft_advisor._build_review_prompt(
        pack_number=1, pick_number=1,
        picks=[],
        main_colors=[],
        curve={},
    )
    assert "(none)" in prompt
    assert "undecided" in prompt


def test_build_review_prompt_curve_buckets_six_plus():
    """7+ CMC cards count toward the 6+ bucket."""
    prompt = draft_advisor._build_review_prompt(
        pack_number=1, pick_number=10,
        picks=[("Big", "A", "G")],
        main_colors=["G"],
        curve={6: 1, 7: 1, 8: 1},  # all in 6+ bucket
    )
    # 6+-drop:3 should appear.
    assert "6+" in prompt
    assert ":3" in prompt

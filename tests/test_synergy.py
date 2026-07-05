"""Tests for synergy.py — pure-logic synergy bonus calculator.

Coverage:
- DeckMetrics initialization
- build_metrics scanning
- bonus() rule firing per oracle text + metric
- bread_bonus() evasion + removal grading

All tests run offline; card data is injected via card_db._oracle/_type_line
fixtures (shared-store lookup disabled).
"""
from __future__ import annotations

import pytest

from draft_helper import card_db
from draft_helper import synergy


@pytest.fixture(autouse=True)
def isolate(monkeypatch):
    """Disable shared-store lookups; restore card_db state per-test."""
    monkeypatch.setattr("draft_helper.card_db._resolve_shared_cards_dir", lambda: None)
    monkeypatch.setattr("draft_helper.card_db._save_cache", lambda: None)
    monkeypatch.setattr("draft_helper.card_db._load_cache", lambda: None)
    orig_oracle = card_db._oracle.copy()
    orig_type_line = card_db._type_line.copy()
    yield
    card_db._oracle.clear()
    card_db._oracle.update(orig_oracle)
    card_db._type_line.clear()
    card_db._type_line.update(orig_type_line)


# ---------------------------------------------------------------------------
# DeckMetrics
# ---------------------------------------------------------------------------

def test_deck_metrics_initializes_to_zero():
    m = synergy.DeckMetrics()
    assert m.instants_sorceries == 0
    assert m.creatures == 0
    assert m.plus_one_counters == 0
    assert m.tribes == {}


def test_deck_metrics_slots_present():
    """Sanity check — all documented slots exist on instances."""
    m = synergy.DeckMetrics()
    expected = (
        "instants_sorceries", "creatures", "plus_one_counters",
        "kicker_spells", "sacrifice_outlets", "artifacts",
        "lifegain_sources", "flyers",
        "two_drops", "four_drops", "five_drops", "six_plus_drops",
        "mana_fixing", "enabler_count", "payoff_count",
        "removal_count", "tribes",
    )
    for slot in expected:
        assert hasattr(m, slot), f"DeckMetrics missing slot {slot}"


# ---------------------------------------------------------------------------
# bonus() — rule firing
# ---------------------------------------------------------------------------

def test_bonus_returns_zero_for_unknown_card():
    """No oracle text → no bonus."""
    metrics = synergy.DeckMetrics()
    metrics.creatures = 5
    assert synergy.bonus("Unknown Card", metrics) == 0.0


def test_bonus_fires_on_spell_cost_reducer_pattern():
    """A 'costs {1} less for each instant or sorcery' card with 5 spells in
    deck should fire the matching rule."""
    card_db._oracle["tolarian terror"] = (
        "This spell costs {1} less to cast for each instant and sorcery "
        "card in your graveyard. Ward {2}."
    )
    metrics = synergy.DeckMetrics()
    metrics.instants_sorceries = 5
    bonus = synergy.bonus("Tolarian Terror", metrics)
    # Rule: 0.6 per spell, cap 4.0. 5 × 0.6 = 3.0 (under cap).
    assert bonus >= 3.0


def test_bonus_caps_at_rule_max():
    """A spell-cost-reducer with 20 spells in deck shouldn't keep scaling."""
    card_db._oracle["spell rebate"] = "costs {1} less for each instant or sorcery in your graveyard."
    metrics = synergy.DeckMetrics()
    metrics.instants_sorceries = 20
    bonus = synergy.bonus("Spell Rebate", metrics)
    # 20 × 0.6 = 12.0 → capped at 4.0
    assert bonus <= 4.5  # cap ~4.0; allow tiny float wiggle


def test_bonus_zero_when_metric_count_is_zero():
    """A spell-payoff card in a creature deck → no bonus from this rule."""
    card_db._oracle["spell mage"] = "Whenever you cast an instant or sorcery, draw a card."
    metrics = synergy.DeckMetrics()
    metrics.instants_sorceries = 0
    bonus = synergy.bonus("Spell Mage", metrics)
    assert bonus == 0.0


def test_bonus_prowess_card_with_spells_present():
    """Prowess fires the instants_sorceries rule at a smaller per-count weight."""
    card_db._oracle["mocking sprite"] = "Flying. Prowess (this creature gets +1/+1 until end of turn whenever you cast a noncreature spell.)"
    metrics = synergy.DeckMetrics()
    metrics.instants_sorceries = 6
    bonus = synergy.bonus("Mocking Sprite", metrics)
    # Prowess rule: 0.35/spell, cap 2.0
    # Plus the "whenever you cast a noncreature spell" rule: 0.4/spell, cap 2.5.
    assert bonus > 0.0


# ---------------------------------------------------------------------------
# bread_bonus
# ---------------------------------------------------------------------------

def test_bread_bonus_zero_for_empty_oracle():
    assert synergy.bread_bonus("") == 0.0
    assert synergy.bread_bonus(None) == 0.0  # type: ignore[arg-type]


def test_bread_bonus_fires_on_flying_keyword():
    """Flying creature should get an evasion bonus."""
    bonus = synergy.bread_bonus("Flying. When this enters, scry 1.")
    assert bonus > 0.0


def test_bread_bonus_fires_on_destroy_target():
    """Removal text should grade up."""
    bonus = synergy.bread_bonus("Destroy target creature.")
    assert bonus > 0.0


def test_bread_bonus_capped_overall():
    """Combining many evasion + removal effects shouldn't blow past the cap."""
    text = (
        "Flying, deathtouch, menace, haste, trample, hexproof, indestructible. "
        "Destroy target creature. Exile target permanent. Counter target spell."
    )
    bonus = synergy.bread_bonus(text)
    # Cap is 1.5 per the docstring.
    assert bonus <= 1.5


def test_bread_bonus_first_removal_pattern_only():
    """Removal patterns shouldn't all stack — only first match counts."""
    # destroy target (1.5) + exile target (1.5) → only 1.5 since first wins.
    bonus_destroy = synergy.bread_bonus("Destroy target creature.")
    bonus_both = synergy.bread_bonus("Destroy target creature. Exile target.")
    # The two should be similar — second pattern doesn't add on top.
    assert abs(bonus_both - bonus_destroy) < 0.5


# ---------------------------------------------------------------------------
# build_metrics — full integration
# ---------------------------------------------------------------------------

def test_build_metrics_counts_creatures(monkeypatch):
    monkeypatch.setattr("draft_helper.ratings.get_types", lambda name: {
        "goblin warrior": ["Creature"],
        "lightning bolt": ["Instant"],
    }.get(name.lower(), []))
    monkeypatch.setattr("draft_helper.ratings.get_cmc", lambda name: 1)
    monkeypatch.setattr("draft_helper.ratings.get_colors", lambda name: ["R"])
    card_db._oracle["goblin warrior"] = "Haste."
    card_db._oracle["lightning bolt"] = "Lightning Bolt deals 3 damage."

    m = synergy.build_metrics(["Goblin Warrior", "Lightning Bolt"])
    assert m.creatures == 1
    assert m.instants_sorceries == 1


def test_build_metrics_counts_curve_buckets(monkeypatch):
    """Cards by cmc should land in the right bucket."""
    cmc_map = {"two-drop": 2, "four-drop": 4, "five-drop": 5, "six-drop": 7}
    monkeypatch.setattr("draft_helper.ratings.get_types", lambda name: ["Creature"])
    monkeypatch.setattr("draft_helper.ratings.get_cmc", lambda name: cmc_map.get(name.lower(), 0))
    monkeypatch.setattr("draft_helper.ratings.get_colors", lambda name: [])
    for n in cmc_map:
        card_db._oracle[n] = "x"
    m = synergy.build_metrics(["two-drop", "four-drop", "five-drop", "six-drop"])
    assert m.two_drops == 1
    assert m.four_drops == 1
    assert m.five_drops == 1
    assert m.six_plus_drops == 1


def test_build_metrics_counts_lifegain(monkeypatch):
    monkeypatch.setattr("draft_helper.ratings.get_types", lambda name: ["Creature"])
    monkeypatch.setattr("draft_helper.ratings.get_cmc", lambda name: 2)
    monkeypatch.setattr("draft_helper.ratings.get_colors", lambda name: [])
    card_db._oracle["soul sister"] = (
        "Whenever another creature enters under your control, you gain 1 life."
    )
    m = synergy.build_metrics(["Soul Sister"])
    assert m.lifegain_sources == 1


def test_build_metrics_counts_artifacts(monkeypatch):
    monkeypatch.setattr("draft_helper.ratings.get_types", lambda name: ["Artifact"])
    monkeypatch.setattr("draft_helper.ratings.get_cmc", lambda name: 2)
    monkeypatch.setattr("draft_helper.ratings.get_colors", lambda name: [])
    card_db._oracle["mind stone"] = "{T}: Add {C}."
    m = synergy.build_metrics(["Mind Stone"])
    assert m.artifacts == 1


# ---------------------------------------------------------------------------
# deck_skeleton_penalty — curve / creature-density nudges
# ---------------------------------------------------------------------------

def test_deck_skeleton_penalty_no_op_in_first_5_picks(monkeypatch):
    """Below 6 picks, the heuristic doesn't fire (too noisy to judge)."""
    monkeypatch.setattr("draft_helper.ratings.get_cmc", lambda name: 5)
    monkeypatch.setattr("draft_helper.ratings.get_types", lambda name: ["Creature"])
    m = synergy.DeckMetrics()
    m.two_drops = 0
    assert synergy.deck_skeleton_penalty("Big Threat", m, total_picks=3) == 0.0


def test_deck_skeleton_penalty_rewards_two_drop_when_slot_empty(monkeypatch):
    """A two-drop creature gets a positive nudge when 2-drops is empty."""
    monkeypatch.setattr("draft_helper.ratings.get_cmc", lambda name: 2)
    monkeypatch.setattr("draft_helper.ratings.get_types", lambda name: ["Creature"])
    m = synergy.DeckMetrics()
    m.two_drops = 0
    nudge = synergy.deck_skeleton_penalty("Bear", m, total_picks=10)
    assert nudge > 0  # rewarded


def test_deck_skeleton_penalty_penalizes_high_cmc_when_two_drops_thin(monkeypatch):
    """A 4-drop is penalized when 2-drops is below 2."""
    monkeypatch.setattr("draft_helper.ratings.get_cmc", lambda name: 4)
    monkeypatch.setattr("draft_helper.ratings.get_types", lambda name: ["Creature"])
    m = synergy.DeckMetrics()
    m.two_drops = 1
    penalty = synergy.deck_skeleton_penalty("Big Beast", m, total_picks=10)
    assert penalty < 0  # negative = penalty


def test_deck_skeleton_penalty_penalizes_six_plus_overload(monkeypatch):
    """A 6+ drop when there are already 2 in the deck → penalty."""
    monkeypatch.setattr("draft_helper.ratings.get_cmc", lambda name: 7)
    monkeypatch.setattr("draft_helper.ratings.get_types", lambda name: ["Creature"])
    m = synergy.DeckMetrics()
    m.six_plus_drops = 2
    m.two_drops = 4  # healthy 2-drop count to isolate the 6+ penalty
    penalty = synergy.deck_skeleton_penalty("Dragon", m, total_picks=15)
    assert penalty < 0


def test_deck_skeleton_penalty_penalizes_noncreature_when_creature_starved(monkeypatch):
    """Picking yet another non-creature when creature density is far below
    target → penalty."""
    monkeypatch.setattr("draft_helper.ratings.get_cmc", lambda name: 3)
    monkeypatch.setattr("draft_helper.ratings.get_types", lambda name: ["Sorcery"])
    m = synergy.DeckMetrics()
    m.two_drops = 4  # healthy
    m.creatures = 1  # very low — total_picks=20 → target 8, deficit 7
    penalty = synergy.deck_skeleton_penalty("Some Sorcery", m, total_picks=20)
    assert penalty < 0


# ---------------------------------------------------------------------------
# enabler_payoff_gap_bonus
# ---------------------------------------------------------------------------

def test_enabler_payoff_gap_zero_for_balanced_deck(monkeypatch):
    """When enablers ≈ payoffs, no bonus."""
    monkeypatch.setattr("draft_helper.ratings.get_types", lambda name: ["Creature"])
    monkeypatch.setattr("draft_helper.ratings.get_cmc", lambda name: 4)
    card_db._oracle["card a"] = "Whenever you cast an instant or sorcery, draw a card."
    m = synergy.DeckMetrics()
    m.enabler_count = 5
    m.payoff_count = 4  # gap = 1, below threshold
    bonus = synergy.enabler_payoff_gap_bonus("Card A", m)
    assert bonus == 0.0


def test_enabler_payoff_gap_rewards_payoff_when_enabler_heavy(monkeypatch):
    """Many enablers, no payoffs → reward picking a payoff."""
    monkeypatch.setattr("draft_helper.ratings.get_types", lambda name: ["Creature"])
    monkeypatch.setattr("draft_helper.ratings.get_cmc", lambda name: 4)
    card_db._oracle["spell mage"] = "Whenever you cast an instant or sorcery, draw a card."
    m = synergy.DeckMetrics()
    m.enabler_count = 6
    m.payoff_count = 1
    # gap = 5 → bonus 1.5 (capped)
    bonus = synergy.enabler_payoff_gap_bonus("Spell Mage", m)
    assert bonus > 0


def test_enabler_payoff_gap_zero_for_unrelated_card(monkeypatch):
    """A vanilla creature in an enabler-heavy deck gets nothing — it's
    not a payoff."""
    monkeypatch.setattr("draft_helper.ratings.get_types", lambda name: ["Creature"])
    monkeypatch.setattr("draft_helper.ratings.get_cmc", lambda name: 4)
    card_db._oracle["bear"] = "Vanilla 2/2."
    m = synergy.DeckMetrics()
    m.enabler_count = 6
    m.payoff_count = 1
    assert synergy.enabler_payoff_gap_bonus("Bear", m) == 0.0


# ---------------------------------------------------------------------------
# removal_scarcity_bonus
# ---------------------------------------------------------------------------

def test_removal_scarcity_zero_when_three_or_more_already(monkeypatch):
    """Deck has plenty of removal → no scarcity bonus."""
    card_db._oracle["bolt"] = "Lightning Bolt deals 3 damage to any target."
    m = synergy.DeckMetrics()
    m.removal_count = 4
    assert synergy.removal_scarcity_bonus("Bolt", m) == 0.0


def test_removal_scarcity_max_bonus_when_zero_removal():
    """0 removal → +2.0 pp on a removal spell."""
    card_db._oracle["doom blade"] = "Destroy target nonblack creature."
    m = synergy.DeckMetrics()
    m.removal_count = 0
    bonus = synergy.removal_scarcity_bonus("Doom Blade", m)
    assert bonus == 2.0


def test_removal_scarcity_partial_bonus_for_one_removal():
    card_db._oracle["doom blade"] = "Destroy target creature."
    m = synergy.DeckMetrics()
    m.removal_count = 1
    bonus = synergy.removal_scarcity_bonus("Doom Blade", m)
    assert bonus == 1.25


def test_removal_scarcity_zero_for_non_removal_card():
    """Non-removal card → no scarcity bonus, even when deck is starved."""
    card_db._oracle["bear"] = "Vanilla 2/2 creature."
    m = synergy.DeckMetrics()
    m.removal_count = 0
    assert synergy.removal_scarcity_bonus("Bear", m) == 0.0


def test_removal_scarcity_zero_for_unknown_card():
    m = synergy.DeckMetrics()
    m.removal_count = 0
    assert synergy.removal_scarcity_bonus("Unknown Card", m) == 0.0


# ---------------------------------------------------------------------------
# card_themes — per-card synergy tagger
# ---------------------------------------------------------------------------

def _register(monkeypatch, cards: dict):
    """cards: name -> (oracle, types, cmc, subtypes). Stub the lookups."""
    types = {n.lower(): c[1] for n, c in cards.items()}
    cmcs = {n.lower(): c[2] for n, c in cards.items()}
    subs = {n.lower(): c[3] for n, c in cards.items()}
    for n, c in cards.items():
        card_db._oracle[n.lower()] = c[0]
    monkeypatch.setattr("draft_helper.ratings.get_types",
                        lambda name: types.get(name.lower(), []))
    monkeypatch.setattr("draft_helper.ratings.get_cmc",
                        lambda name: cmcs.get(name.lower(), 0))
    monkeypatch.setattr("draft_helper.card_db.get_subtypes",
                        lambda name: subs.get(name.lower(), []))


def test_card_themes_detects_counters(monkeypatch):
    _register(monkeypatch, {"Grower": ("Put a +1/+1 counter on target creature.",
                                        ["Instant"], 2, [])})
    assert "+1/+1 counters" in synergy.card_themes("Grower")


def test_card_themes_detects_enabler_and_not_payoff(monkeypatch):
    _register(monkeypatch, {"Cantrip": ("Draw a card.", ["Instant"], 1, [])})
    tags = synergy.card_themes("Cantrip")
    assert "enabler" in tags
    assert "payoff" not in tags


def test_card_themes_detects_payoff(monkeypatch):
    _register(monkeypatch, {"Engine": ("Whenever you cast an instant, draw a card.",
                                       ["Enchantment"], 3, [])})
    assert "payoff" in synergy.card_themes("Engine")


def test_card_themes_detects_tribe(monkeypatch):
    _register(monkeypatch, {"Merlord": ("Other Merfolk you control get +1/+1.",
                                        ["Creature"], 3, ["Merfolk"])})
    assert "merfolk tribal" in synergy.card_themes("Merlord")


def test_card_themes_cheap_removal_is_not_an_enabler(monkeypatch):
    """The enabler tag is for cheap fuel spells — a card that is already
    removal (or a payoff) must not double-tag as 'enabler' and pollute the
    deck's significant-theme detection."""
    _register(monkeypatch, {"Bolt": ("Bolt deals 3 damage to any target.",
                                     ["Instant"], 1, [])})
    tags = synergy.card_themes("Bolt")
    assert "removal" in tags
    assert "enabler" not in tags


def test_card_themes_cheap_payoff_is_not_an_enabler(monkeypatch):
    _register(monkeypatch, {"Cheap Engine":
                            ("Whenever you cast an instant, draw a card.",
                             ["Instant"], 2, [])})
    tags = synergy.card_themes("Cheap Engine")
    assert "payoff" in tags
    assert "enabler" not in tags


def test_card_themes_counter_removal_cost_is_not_counters_theme(monkeypatch):
    """A card that only REMOVES +1/+1 counters (an upkeep cost/downside)
    doesn't advance a counters gameplan."""
    _register(monkeypatch, {"Shrinking Hydra":
                            ("At the beginning of your upkeep, remove a "
                             "+1/+1 counter from Shrinking Hydra.",
                             ["Creature"], 3, ["Hydra"])})
    assert "+1/+1 counters" not in synergy.card_themes("Shrinking Hydra")


def test_card_themes_counter_placer_still_detected(monkeypatch):
    """Cards that PLACE counters (even alongside a remove clause) keep the
    theme tag."""
    _register(monkeypatch, {"Grower Hydra":
                            ("Grower Hydra enters with two +1/+1 counters. "
                             "At the beginning of your upkeep, remove a "
                             "+1/+1 counter from it.",
                             ["Creature"], 3, ["Hydra"])})
    assert "+1/+1 counters" in synergy.card_themes("Grower Hydra")


def test_card_themes_vanilla_card_has_no_tags(monkeypatch):
    _register(monkeypatch, {"Bear": ("", ["Creature"], 2, ["Bear"])})
    assert synergy.card_themes("Bear") == set()


# ---------------------------------------------------------------------------
# assess_hand_synergy — opening-hand vs deck plan
# ---------------------------------------------------------------------------

def test_assess_hand_synergistic_when_hand_hits_payoff_theme(monkeypatch):
    # Deck: 3+ counter cards -> counters is significant. Hand has one.
    _register(monkeypatch, {
        "A": ("Put a +1/+1 counter on it.", ["Instant"], 2, []),
        "B": ("Put a +1/+1 counter on it.", ["Sorcery"], 3, []),
        "C": ("Put a +1/+1 counter on it.", ["Creature"], 4, []),
        "Land": ("", ["Land"], 0, []),
    })
    deck = ["A", "B", "C", "Land", "Land", "Land"]
    result = synergy.assess_hand_synergy(deck, ["A", "Land", "Land"])
    assert "+1/+1 counters" in result.deck_themes
    assert result.verdict == "synergistic"


def test_assess_hand_off_plan_when_no_theme_cards(monkeypatch):
    _register(monkeypatch, {
        "A": ("Put a +1/+1 counter on it.", ["Instant"], 2, []),
        "B": ("Put a +1/+1 counter on it.", ["Sorcery"], 3, []),
        "C": ("Put a +1/+1 counter on it.", ["Creature"], 4, []),
        "Vanilla": ("", ["Creature"], 3, []),
        "Land": ("", ["Land"], 0, []),
    })
    deck = ["A", "B", "C", "Vanilla", "Land", "Land"]
    result = synergy.assess_hand_synergy(deck, ["Vanilla", "Land", "Land"])
    assert result.verdict == "off-plan"


def test_assess_hand_removal_deck_hand_full_of_removal_is_on_plan(monkeypatch):
    # A deck whose PLAN is utility (removal — no payoff/engine theme at all):
    # a hand advancing that plan is genuinely on-plan and reads
    # "synergistic". The deck can't be penalized for not having an engine
    # it was never drafted to have.
    _register(monkeypatch, {
        "Murder": ("Destroy target creature.", ["Sorcery"], 3, []),
        "Zap": ("Destroy target creature.", ["Sorcery"], 3, []),
        "Smite": ("Destroy target creature.", ["Sorcery"], 3, []),
        "Land": ("", ["Land"], 0, []),
    })
    deck = ["Murder", "Zap", "Smite", "Land", "Land", "Land"]
    result = synergy.assess_hand_synergy(deck, ["Murder", "Zap", "Land"])
    assert "removal" in result.deck_themes
    assert result.verdict == "synergistic"


def test_assess_hand_functional_when_deck_has_payoff_but_hand_misses_it(monkeypatch):
    # Deck has a real payoff plan (counters) AND heavy removal; a hand that
    # only touches removal is playable but misses the engine → "functional".
    _register(monkeypatch, {
        "A": ("Put a +1/+1 counter on it.", ["Instant"], 2, []),
        "B": ("Put a +1/+1 counter on it.", ["Sorcery"], 3, []),
        "C": ("Put a +1/+1 counter on it.", ["Creature"], 4, []),
        "Murder": ("Destroy target creature.", ["Sorcery"], 3, []),
        "Zap": ("Destroy target creature.", ["Sorcery"], 3, []),
        "Smite": ("Destroy target creature.", ["Sorcery"], 3, []),
        "Land": ("", ["Land"], 0, []),
    })
    deck = ["A", "B", "C", "Murder", "Zap", "Smite", "Land", "Land"]
    result = synergy.assess_hand_synergy(deck, ["Murder", "Zap", "Land"])
    assert result.verdict == "functional"
    assert "lacks a payoff" in result.reason


def test_assess_hand_unknown_when_no_significant_theme(monkeypatch):
    _register(monkeypatch, {"Vanilla": ("", ["Creature"], 3, []),
                            "Land": ("", ["Land"], 0, [])})
    result = synergy.assess_hand_synergy(["Vanilla", "Land"], ["Vanilla", "Land"])
    assert result.verdict == "unknown"

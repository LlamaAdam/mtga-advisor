"""
Synergy bonus calculator for draft card recommendations.

Detects synergy conditions from oracle text and deck composition,
then returns a win-rate bonus (in percentage points) to add to a
card's adjusted rating.

Design:
  - Each synergy rule is a (pattern, metric, bonus_per_count, cap) tuple.
  - 'pattern' matches oracle text to identify a card as a synergy payoff.
  - 'metric' names a DeckMetrics counter (e.g. "instants_sorceries").
  - 'bonus_per_count' is added per matching card already in the deck.
  - 'cap' limits the total bonus so one synergy can't dominate everything.

Example:
  Tolarian Terror: "costs {1} less for each instant and sorcery"
    → metric="instants_sorceries", bonus=0.6/spell, cap=4.0
    → deck has 5 spells → +3.0 pts (capped at 4.0)

Additional scoring layers (BREAD/KHEBA framework):
  bread_bonus()            — evasion keywords + removal text (BREAD: R + E)
  deck_skeleton_penalty()  — curve integrity + creature density checks
  enabler_payoff_gap_bonus() — rewards cards that fill the missing half of
                               your synergy engine (enablers vs. payoffs)
"""

import re
from . import card_db


# ---------------------------------------------------------------------------
# Synergy rule definitions
# (oracle_text_pattern, deck_metric, bonus_per_count, max_bonus)
# ---------------------------------------------------------------------------

_RULES: list[tuple[str, str, float, float]] = [
    # Spell-cost reducers (Tolarian Terror etc.)
    (r"costs? \{1\} less.*instant.*sorcery",    "instants_sorceries", 0.6, 4.0),
    (r"costs? \{1\} less.*sorcery.*instant",    "instants_sorceries", 0.6, 4.0),
    # Spell-matters payoffs ("whenever you cast an instant or sorcery")
    (r"whenever you cast an instant or sorcery", "instants_sorceries", 0.4, 3.0),
    # Creature-count reducers
    (r"costs? \{1\} less.*each creature",        "creatures",          0.5, 3.0),
    # +1/+1 counter synergies — payoffs that reward counters already on creatures
    (r"counter on it has trample",               "plus_one_counters",  0.5, 2.5),
    (r"with a \+1/\+1 counter",                  "plus_one_counters",  0.4, 2.0),
    (r"whenever.*\+1/\+1 counter",               "plus_one_counters",  0.4, 2.0),
    # Counter draw/protection payoffs (Jubilant Call style)
    (r"for each creature you control with a \+1/\+1 counter",
                                                 "plus_one_counters",  0.6, 3.0),
    # Attack-trigger counter engines (Ranging Guide style) — reward having
    # many counter payoffs already in the deck
    (r"whenever you attack.*\+1/\+1 counter",    "plus_one_counters",  0.45, 2.5),
    (r"whenever.*attack.*with.*creature.*\+1/\+1 counter",
                                                 "plus_one_counters",  0.45, 2.5),
    # ETB counter engines (place counters when entering)
    (r"enters.*\+1/\+1 counter",                 "plus_one_counters",  0.4, 2.0),
    # Kicker payoffs
    (r"whenever a kicked",                       "kicker_spells",      0.5, 2.5),
    # Sacrifice synergies
    (r"whenever.*creature.*dies",                "sacrifice_outlets",  0.4, 2.0),
    # Artifact synergies
    (r"costs? \{1\} less.*each artifact",        "artifacts",          0.5, 3.0),
    (r"whenever.*artifact.*enter",               "artifacts",          0.4, 2.0),
    # Life-gain payoffs (e.g. Marauding Blight-Priest style)
    (r"whenever you gain life",                  "lifegain_sources",   0.4, 2.5),
    # Flying matters
    (r"whenever a creature.*flying.*enter",      "flyers",             0.4, 2.0),
    # Prowess and spell-cost reduction (Mocking Sprite style)
    (r"\bprowess\b",                             "instants_sorceries", 0.35, 2.0),
    (r"instant and sorcery spells you cast cost \{1\} less",
                                                 "instants_sorceries", 0.5, 3.0),
    (r"whenever you cast a noncreature spell",   "instants_sorceries", 0.4, 2.5),
]

# Pre-compile patterns for speed
_COMPILED: list[tuple[re.Pattern, str, float, float]] = [
    (re.compile(pat, re.IGNORECASE), metric, bpc, cap)
    for pat, metric, bpc, cap in _RULES
]


# ---------------------------------------------------------------------------
# Tribal synergy rules
# (oracle_text_pattern, tribe_name, bonus_per_member_in_deck, max_bonus)
# ---------------------------------------------------------------------------

_TRIBAL_RULES: list[tuple[str, str, float, float]] = [
    # Lords / "other X creatures you control" payoffs
    (r"\bother angels?\b",          "Angel",   0.5, 2.5),
    (r"\bother humans?\b",          "Human",   0.4, 2.0),
    (r"\bother zombies?\b",         "Zombie",  0.4, 2.0),
    (r"\bother vampires?\b",        "Vampire", 0.4, 2.0),
    (r"\bother elves?\b",           "Elf",     0.4, 2.0),
    (r"\bother goblins?\b",         "Goblin",  0.4, 2.0),
    (r"\bother merfolk\b",          "Merfolk", 0.4, 2.0),
    (r"\bother knights?\b",         "Knight",  0.4, 2.0),
    (r"\bother dragons?\b",         "Dragon",  0.5, 2.5),
    (r"\bother wolves?\b",          "Wolf",    0.4, 2.0),
    (r"\bother soldiers?\b",        "Soldier", 0.4, 2.0),
    (r"\bother warriors?\b",        "Warrior", 0.4, 2.0),
    (r"\bother cats?\b",            "Cat",     0.4, 2.0),
    (r"\bother birds?\b",           "Bird",    0.4, 2.0),
    (r"\bother wizards?\b",         "Wizard",  0.4, 2.0),
    # "X you control" payoffs
    (r"\bangels? you control\b",    "Angel",   0.4, 2.0),
    (r"\bhumans? you control\b",    "Human",   0.35, 1.5),
    (r"\bzombies? you control\b",   "Zombie",  0.35, 1.5),
    (r"\bvampires? you control\b",  "Vampire", 0.35, 1.5),
    (r"\belves? you control\b",     "Elf",     0.35, 1.5),
    (r"\bgoblins? you control\b",   "Goblin",  0.35, 1.5),
    (r"\bmerfolk you control\b",    "Merfolk", 0.35, 1.5),
    (r"\bknights? you control\b",   "Knight",  0.35, 1.5),
    (r"\bdragons? you control\b",   "Dragon",  0.45, 2.0),
    (r"\bwolves? you control\b",    "Wolf",    0.35, 1.5),
    (r"\bsoldiers? you control\b",  "Soldier", 0.35, 1.5),
    (r"\bwarriors? you control\b",  "Warrior", 0.35, 1.5),
    (r"\bcats? you control\b",      "Cat",     0.35, 1.5),
    (r"\bbirds? you control\b",     "Bird",    0.35, 1.5),
    (r"\bwizards? you control\b",   "Wizard",  0.35, 1.5),
    # "Whenever a/an X" triggers
    (r"\bwhenever (?:an? )?angel\b",   "Angel",   0.45, 2.0),
    (r"\bwhenever (?:an? )?zombie\b",  "Zombie",  0.4,  2.0),
    (r"\bwhenever (?:an? )?vampire\b", "Vampire", 0.4,  2.0),
    (r"\bwhenever (?:an? )?elf\b",     "Elf",     0.4,  2.0),
    (r"\bwhenever (?:an? )?goblin\b",  "Goblin",  0.4,  2.0),
    (r"\bwhenever (?:an? )?knight\b",  "Knight",  0.4,  2.0),
    (r"\bwhenever (?:an? )?dragon\b",  "Dragon",  0.45, 2.0),
    (r"\bwhenever (?:an? )?wolf\b",    "Wolf",    0.4,  2.0),
    (r"\bwhenever (?:an? )?soldier\b", "Soldier", 0.4,  2.0),
    (r"\bwhenever (?:an? )?warrior\b", "Warrior", 0.4,  2.0),
    (r"\bwhenever (?:an? )?wizard\b",  "Wizard",  0.4,  2.0),
]

# Tribes tracked in DeckMetrics.tribes
TRACKED_TRIBES: frozenset[str] = frozenset({
    "Angel", "Human", "Zombie", "Vampire", "Elf", "Goblin", "Merfolk",
    "Knight", "Dragon", "Wolf", "Werewolf", "Soldier", "Warrior",
    "Cat", "Bird", "Wizard", "Cleric", "Scout", "Rogue", "Pirate",
})

_COMPILED_TRIBAL: list[tuple[re.Pattern, str, float, float]] = [
    (re.compile(pat, re.IGNORECASE), tribe, bpc, cap)
    for pat, tribe, bpc, cap in _TRIBAL_RULES
]


# ---------------------------------------------------------------------------
# Deck metrics
# ---------------------------------------------------------------------------

class DeckMetrics:
    """
    Counts of synergy-relevant card categories already in the deck.
    Passed to bonus() so it doesn't need to re-count every call.

    Slots:
      instants_sorceries  — spells for cost-reducer / spell-matters payoffs
      creatures           — creature count (cost-reducer + density check)
      plus_one_counters   — cards that place or care about +1/+1 counters
      kicker_spells       — kicked spells for kicker-payoff synergies
      sacrifice_outlets   — sacrifice-able creatures/artifacts
      artifacts           — artifacts for artifact-matters payoffs
      lifegain_sources    — cards that gain life
      flyers              — creatures with flying
      two_drops           — 2-CMC cards (curve integrity check)
      mana_fixing         — dual lands, treasures, any-color mana
      enabler_count       — cheap non-creature spells (fuel for synergy engines)
      payoff_count        — cards that reward accumulated fuel
    """
    __slots__ = ("instants_sorceries", "creatures", "plus_one_counters",
                 "kicker_spells", "sacrifice_outlets", "artifacts",
                 "lifegain_sources", "flyers",
                 "two_drops", "four_drops", "five_drops", "six_plus_drops",
                 "mana_fixing", "enabler_count", "payoff_count",
                 "removal_count", "tribes")

    def __init__(self):
        for slot in self.__slots__:
            if slot == "tribes":
                setattr(self, slot, {})
            else:
                setattr(self, slot, 0)


def build_metrics(card_names: list[str]) -> DeckMetrics:
    """
    Build DeckMetrics by scanning oracle text of all cards already picked.
    Call once per resync/pack-update, not per card evaluation.
    """
    from . import ratings as r
    m = DeckMetrics()
    for name in card_names:
        text = card_db.get_oracle(name).lower()
        types = r.get_types(name)
        cmc   = r.get_cmc(name)
        colors = r.get_colors(name)

        # --- Existing synergy counters ---
        if "Instant" in types or "Sorcery" in types:
            m.instants_sorceries += 1
        if "Creature" in types:
            m.creatures += 1
        if "Artifact" in types:
            m.artifacts += 1

        if _mentions_counters_synergy(text):
            m.plus_one_counters += 1
        if "kicker" in text:
            m.kicker_spells += 1
        if "sacrifice" in text and ("creature" in text or "artifact" in text):
            m.sacrifice_outlets += 1
        if "you gain" in text and "life" in text:
            m.lifegain_sources += 1
        if "flying" in text and ("creature" in text or "Bird" in str(types)):
            m.flyers += 1

        # --- Deck-skeleton metrics ---
        if cmc == 2:
            m.two_drops += 1
        elif cmc == 4:
            m.four_drops += 1
        elif cmc == 5:
            m.five_drops += 1
        elif cmc >= 6:
            m.six_plus_drops += 1

        # Mana fixing: multi-color lands, treasures, or any-color mana sources
        if "Land" in types and len(colors) >= 2:
            m.mana_fixing += 1
        if "treasure" in text or ("add" in text and "any color" in text):
            m.mana_fixing += 1

        # Enablers: cheap non-creature spells that fuel synergy engines
        if (cmc <= 2
                and "Creature" not in types
                and ("Instant" in types or "Sorcery" in types)):
            m.enabler_count += 1

        # Payoffs: cards that reward accumulated fuel
        if ("whenever you cast" in text
                or ("for each" in text
                    and ("instant" in text or "sorcery" in text
                         or "creature" in text or "artifact" in text))):
            m.payoff_count += 1

        # Removal count: cards that answer opposing threats
        for pattern, _ in _COMPILED_REMOVAL:
            if pattern.search(card_db.get_oracle(name)):
                m.removal_count += 1
                break  # count each card at most once

        # Tribal counts: track creature subtypes present in the deck
        for subtype in card_db.get_subtypes(name):
            if subtype in TRACKED_TRIBES:
                m.tribes[subtype] = m.tribes.get(subtype, 0) + 1

    return m


# ---------------------------------------------------------------------------
# Bonus calculation
# ---------------------------------------------------------------------------

def bonus(card_name: str, metrics: DeckMetrics) -> float:
    """
    Return total synergy bonus (in win-rate percentage points) for a card
    given the current deck composition.
    """
    oracle = card_db.get_oracle(card_name)
    if not oracle:
        return 0.0

    total = 0.0
    for pattern, metric, bpc, cap in _COMPILED:
        if pattern.search(oracle):
            count = getattr(metrics, metric, 0)
            total += min(count * bpc, cap)

    # Tribal rules: bonus based on how many tribe members are already in the deck
    for pattern, tribe, bpc, cap in _COMPILED_TRIBAL:
        if pattern.search(oracle):
            count = metrics.tribes.get(tribe, 0)
            total += min(count * bpc, cap)

    return round(total, 2)


# ---------------------------------------------------------------------------
# BREAD / Evasion-Removal bonus
# ---------------------------------------------------------------------------

# (keyword, pts) — keywords are matched as substrings in lowercased oracle text
_EVASION_BONUSES: list[tuple[str, float]] = [
    ("flying",         0.7),
    ("double strike",  0.6),
    ("deathtouch",     0.5),
    ("menace",         0.5),
    ("haste",          0.4),
    ("trample",        0.4),
    ("hexproof",       0.4),
    ("indestructible", 0.4),
    ("first strike",   0.3),
    ("lifelink",       0.3),
    ("ward",           0.3),
]

# (pattern, pts) — first match wins (removal effects don't stack)
_REMOVAL_PATTERNS: list[tuple[str, float]] = [
    (r"\bdestroy target\b",                           1.5),
    (r"\bexile target\b",                             1.5),
    (r"\bcounter target\b",                           1.0),
    (r"\bdeals? \d+ damage to (target|any target)\b", 1.0),
    (r"-\d+/-\d+",                                    1.0),
    (r"\breturn target.*to.*hand\b",                  0.5),
    (r"\btap target.*doesn't untap\b",                0.5),
]

_COMPILED_REMOVAL: list[tuple[re.Pattern, float]] = [
    (re.compile(pat, re.IGNORECASE), pts)
    for pat, pts in _REMOVAL_PATTERNS
]

# "remove a +1/+1 counter …" is a cost/downside, not counters synergy.
_REMOVE_COUNTER_RE = re.compile(r"remove[^.]*\+1/\+1 counter", re.IGNORECASE)


def is_removal_text(oracle: str) -> bool:
    """True when the oracle text reads as removal/interaction.

    THE shared removal definition: used by the draft-side theme tags,
    removal counting, and the in-game advisor's check_removal — keep them
    on one list so draft assist and game assist never disagree about
    whether a card answers a threat.
    """
    if not oracle:
        return False
    return any(pat.search(oracle) for pat, _ in _COMPILED_REMOVAL)


def _mentions_counters_synergy(text: str) -> bool:
    """'+1/+1' counts as counters synergy only outside 'remove a +1/+1
    counter' clauses — a card that only pays counters away isn't advancing
    a counters gameplan."""
    return "+1/+1" in _REMOVE_COUNTER_RE.sub("", text)


def bread_bonus(oracle: str) -> float:
    """
    Return a win-rate bonus (in pp) for evasion keywords and removal text.

    Represents the BREAD efficiency factors — Removal (R) and Evasion (E) —
    that stand-alone card value before considering synergy. Capped at 1.5 pts
    to nudge the recommendation without overriding 17Lands win-rate data.
    """
    if not oracle:
        return 0.0
    oracle_lower = oracle.lower()
    total = 0.0

    for keyword, pts in _EVASION_BONUSES:
        if keyword in oracle_lower:
            total += pts

    for pattern, pts in _COMPILED_REMOVAL:
        if pattern.search(oracle):
            total += pts
            break  # Count removal once — don't stack multiple removal clauses

    return min(round(total, 2), 1.5)


# ---------------------------------------------------------------------------
# Deck skeleton penalty (Mana Curve + Creature Density)
# ---------------------------------------------------------------------------

def deck_skeleton_penalty(card_name: str, metrics: DeckMetrics,
                          total_picks: int) -> float:
    """
    Return a win-rate penalty (negative, in pp) for cards that worsen the
    deck's foundational structure.

    Targets based on "How to Build a Mana Curve" (Gavin Verhey, 2017):
      2-drops: 4–6  (most important slot)
      3-drops: 3–5
      4-drops: 2–4  (don't overload)
      5-drops: 1–3
      6+:      0–2  (bombs only)

    Also checks creature density (≈38% of deck = ~15 in 40 cards).
    No penalty applied in the first 5 picks (too little data to judge).
    """
    if total_picks < 6:
        return 0.0

    from . import ratings as r
    penalty = 0.0
    cmc         = r.get_cmc(card_name)
    types       = r.get_types(card_name)
    is_creature = "Creature" in types
    is_land     = "Land" in types

    # --- 2-drop scarcity (target: 4–6) ---
    # The single most important slot. Penalise high-CMC cards when it's empty,
    # and bonus 2-drops when the slot is critically underfilled.
    if cmc == 2 and is_creature:
        # Reward two-drop creatures when we're well below the 4-drop target.
        # +1.5pp when empty (0), +0.75pp when thin (1-2), no bonus at 3+.
        if metrics.two_drops == 0:
            penalty += 1.5
        elif metrics.two_drops <= 2:
            penalty += 0.75
    elif cmc >= 4 and metrics.two_drops < 2:
        penalty -= 1.5
    elif cmc >= 3 and metrics.two_drops == 0:
        penalty -= 0.75

    # --- 4-drop overload (target: max 4) ---
    # "Opening hands with 2–3 four-drops can make your draw very slow."
    if cmc == 4 and metrics.four_drops >= 4:
        penalty -= 1.0

    # --- 5-drop overload (target: max 3) ---
    if cmc == 5 and metrics.five_drops >= 3:
        penalty -= 1.0

    # --- 6+ overload (target: max 2, bombs only) ---
    if cmc >= 6 and metrics.six_plus_drops >= 2:
        penalty -= 1.5

    # --- Creature density ---
    # Target: roughly 38% of picks should be creatures (≈15 in a 40-card deck).
    # Penalise non-creatures when we are well below that target.
    if not is_creature and not is_land:
        target  = max(8, int(total_picks * 0.38))
        deficit = target - metrics.creatures
        if deficit >= 4:
            penalty -= 1.5
        elif deficit >= 2:
            penalty -= 0.75

    return round(penalty, 2)


# ---------------------------------------------------------------------------
# Enabler / Payoff gap bonus
# ---------------------------------------------------------------------------

def enabler_payoff_gap_bonus(card_name: str, metrics: DeckMetrics) -> float:
    """
    Return a bonus for cards that fill the missing half of the synergy engine.

    If enablers >> payoffs by 3+, payoff cards gain a bonus.
    If payoffs >> enablers by 3+, enabler cards gain a bonus.
    Capped at 1.5 pts.
    """
    oracle = card_db.get_oracle(card_name)
    if not oracle:
        return 0.0
    text = oracle.lower()

    from . import ratings as r
    types = r.get_types(card_name)
    cmc   = r.get_cmc(card_name)

    # Classify this card
    is_payoff = (
        "whenever you cast" in text
        or ("for each" in text
            and ("instant" in text or "sorcery" in text
                 or "creature" in text or "artifact" in text))
        or any(pat.search(oracle) for pat, _, _, _ in _COMPILED)
    )
    is_enabler = (
        cmc <= 2
        and "Creature" not in types
        and ("Instant" in types or "Sorcery" in types)
    )

    gap = metrics.enabler_count - metrics.payoff_count  # positive = too many enablers

    bonus_val = 0.0
    if gap >= 3 and is_payoff:
        bonus_val = min(gap * 0.3, 1.5)   # Many enablers, need payoffs
    elif gap <= -3 and is_enabler:
        bonus_val = min((-gap) * 0.3, 1.5)  # Many payoffs, need enablers

    return round(bonus_val, 2)


# ---------------------------------------------------------------------------
# Removal scarcity bonus
# ---------------------------------------------------------------------------

def removal_scarcity_bonus(card_name: str, metrics: DeckMetrics) -> float:
    """
    Bonus for removal spells when the deck is starved of interaction.

    Removal is the highest-priority draft resource after bombs. When a deck
    has fewer than 3 removal spells the bonus scales with scarcity:
      0 removal → +2.0 pp
      1 removal → +1.25 pp
      2 removal → +0.5 pp
      3+        → no bonus

    Only awarded to cards that actually match a removal pattern.
    """
    if metrics.removal_count >= 3:
        return 0.0

    oracle = card_db.get_oracle(card_name)
    if not oracle:
        return 0.0

    is_removal = any(pat.search(oracle) for pat, _ in _COMPILED_REMOVAL)
    if not is_removal:
        return 0.0

    bonus_table = {0: 2.0, 1: 1.25, 2: 0.5}
    return bonus_table.get(metrics.removal_count, 0.0)


# ---------------------------------------------------------------------------
# Per-card theme tagger + opening-hand synergy assessment
#
# card_themes() is the reusable "keyword grouping" primitive: it maps one
# card to the set of synergy themes it participates in. assess_hand_synergy()
# uses it to decide whether an opening hand actually advances the deck's plan
# — consumed by the in-game advisor's mulligan check.
# ---------------------------------------------------------------------------

# A theme is "significant" for a deck once at least this many cards feed it.
_SIGNIFICANT_THEME_MIN = 3
# Themes that represent an actual gameplan/engine (vs. incidental keywords).
# A hand hitting one of these reads as genuinely on-plan.
_PAYOFF_THEMES = frozenset({"+1/+1 counters", "payoff", "artifacts", "lifegain"})


def card_themes(card_name: str) -> set[str]:
    """Return the set of synergy theme tags a single card participates in.

    The per-card primitive behind both draft-pick synergy and the mulligan
    hand-fit check. Themes: '+1/+1 counters', 'artifacts', 'lifegain',
    'enabler', 'payoff', 'removal', and '<tribe> tribal'. Detection mirrors
    build_metrics() so the deck profile and the hand read use the same rules.
    """
    oracle = card_db.get_oracle(card_name)
    if not oracle:
        return set()
    text = oracle.lower()

    from . import ratings as r
    types = r.get_types(card_name)
    cmc = r.get_cmc(card_name)

    tags: set[str] = set()
    if _mentions_counters_synergy(text):
        tags.add("+1/+1 counters")
    if "Artifact" in types:
        tags.add("artifacts")
    if "you gain" in text and "life" in text:
        tags.add("lifegain")
    if ("whenever you cast" in text
            or ("for each" in text
                and any(w in text for w in ("instant", "sorcery", "creature", "artifact")))):
        tags.add("payoff")
    if is_removal_text(oracle):
        tags.add("removal")
    # Enabler = cheap fuel spell. A card that is already removal or a payoff
    # has a real role — double-tagging it as 'enabler' would let any cheap
    # removal shell read as an "enabler deck".
    if (cmc <= 2 and "Creature" not in types
            and ("Instant" in types or "Sorcery" in types)
            and "removal" not in tags and "payoff" not in tags):
        tags.add("enabler")
    for subtype in card_db.get_subtypes(card_name):
        if subtype in TRACKED_TRIBES:
            tags.add(f"{subtype.lower()} tribal")
    return tags


class HandSynergy:
    """Result of assessing an opening hand against its deck's synergy plan.

    verdict is one of:
      'synergistic' — hand hits a core payoff/engine theme of the deck
      'functional'  — hand touches the deck's themes but not a payoff
      'off-plan'    — hand advances none of the deck's significant themes
      'unknown'     — deck too small / no themes detected (no signal)
    """
    __slots__ = ("deck_themes", "hand_hits", "verdict", "reason")

    def __init__(self, deck_themes, hand_hits, verdict, reason):
        self.deck_themes = deck_themes    # list[str] significant deck themes
        self.hand_hits = hand_hits        # list[tuple[str, str]] (card, theme)
        self.verdict = verdict            # str
        self.reason = reason              # str, human-facing


def assess_hand_synergy(deck_names: list[str], hand_names: list[str]) -> HandSynergy:
    """Judge whether an opening hand advances the deck's synergy plan.

    deck_names — every card in the deck (a flat list; duplicates included).
    hand_names — the cards in the opening hand.

    Detects the deck's *significant* themes (fed by >= _SIGNIFICANT_THEME_MIN
    cards), then reports which of those themes the hand actually contains.
    Purely additive context for the mulligan call — it never turns a
    land-screwed hand into a keep; it explains whether a keepable hand is
    on-plan.
    """
    from collections import Counter

    theme_counts: Counter = Counter()
    for name in deck_names:
        for theme in card_themes(name):
            theme_counts[theme] += 1

    significant = sorted(t for t, c in theme_counts.items()
                         if c >= _SIGNIFICANT_THEME_MIN)
    if not significant:
        return HandSynergy([], [], "unknown",
                           "No dominant synergy theme detected in the deck.")

    hand_hits = []
    for name in hand_names:
        for theme in card_themes(name):
            if theme in significant:
                hand_hits.append((name, theme))

    hit_themes = {t for _, t in hand_hits}
    if not hand_hits:
        verdict = "off-plan"
        reason = ("Hand advances none of your deck's themes "
                  f"({', '.join(significant)}) — plays like a generic hand.")
    elif hit_themes & _PAYOFF_THEMES or any("tribal" in t for t in hit_themes):
        verdict = "synergistic"
        cards = ", ".join(sorted({c for c, _ in hand_hits}))
        reason = (f"Hand is on-plan: {cards} feed your "
                  f"{', '.join(sorted(hit_themes))} gameplan.")
    else:
        verdict = "functional"
        reason = (f"Hand touches your {', '.join(sorted(hit_themes))} theme "
                  "but lacks a payoff — playable, not explosive.")

    return HandSynergy(significant, hand_hits, verdict, reason)

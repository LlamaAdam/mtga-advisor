"""
Deck tracker - tracks cards picked so far and recommends the best pick.
"""

import re
from collections import Counter, defaultdict
import card_db
import ratings
import synergy


# Color symbol → WUBRG letter
_PIP_RE = re.compile(r'\{([WUBRG])\}')


_ADD_RE = re.compile(r'add\b[^.]*', re.IGNORECASE)

_BASIC_LAND_NAMES: frozenset[str] = frozenset({
    "Plains", "Island", "Swamp", "Mountain", "Forest",
    "Snow-Covered Plains", "Snow-Covered Island",
    "Snow-Covered Swamp", "Snow-Covered Mountain", "Snow-Covered Forest",
})


def _land_produced_colors(card_name: str) -> list[str]:
    """
    Parse a land's oracle text for mana symbols in 'Add ...' sentences.
    Returns list of WUBRG color letters the land can produce.
    e.g. Dismal Backwater → ['U', 'B']
    """
    oracle = card_db.get_oracle(card_name)
    if not oracle:
        return []
    colors: list[str] = []
    for match in _ADD_RE.finditer(oracle):
        for pip in _PIP_RE.findall(match.group()):
            if pip not in colors:
                colors.append(pip)
    return colors


def _count_off_color_pips(card_name: str, main_colors: set) -> int:
    """
    Count how many colored mana pips in the card's mana cost are NOT in main_colors.
    e.g. {2}{B}{B} with main_colors={'U','G'} → 2 off-color pips.
    Falls back to 1 if mana cost is unavailable (treats it as a single splash).
    """
    mc = card_db.get_mana_cost(card_name)
    if not mc:
        return 1
    return sum(1 for pip in _PIP_RE.findall(mc) if pip not in main_colors)


class DeckTracker:
    def __init__(self):
        self.picks: list[str] = []
        self.pack_number: int = 1
        self.pick_number: int = 1
        self._metrics_cache: synergy.DeckMetrics | None = None
        self._metrics_picks_snapshot: list[str] = []

    # ------------------------------------------------------------------
    # Picks
    # ------------------------------------------------------------------

    def add_pick(self, card_name: str):
        if not card_name:
            return
        self.picks.append(card_name)
        self.pick_number += 1
        if self.pick_number > 15:
            self.pick_number = 1
            self.pack_number += 1

    def remove_last_pick(self):
        if self.picks:
            self.picks.pop()
            if self.pick_number > 1:
                self.pick_number -= 1
            else:
                self.pick_number = 15
                self.pack_number = max(1, self.pack_number - 1)

    def sync_from_log(self, log_state):
        """Sync picks and pack/pick numbers from the log scanner's DraftState."""
        self.picks = list(log_state.picked_cards)
        self.pack_number = log_state.pack_number
        self.pick_number = log_state.pick_number

    def clear(self):
        self.__init__()

    # ------------------------------------------------------------------
    # Color analysis
    # ------------------------------------------------------------------

    def color_counts(self) -> Counter:
        c = Counter()
        for name in self.picks:
            for color in ratings.get_colors(name):
                c[color] += 1
        return c

    def main_colors(self) -> list[str]:
        """Top 1-2 colors by card count."""
        counts = self.color_counts()
        if not counts:
            return []
        top = counts.most_common(2)
        # Only include a second color if it has a meaningful count
        if len(top) == 2 and top[1][1] >= 3:
            return [top[0][0], top[1][0]]
        return [top[0][0]] if top else []

    def color_filter_for_ratings(self) -> str:
        """
        Return the 17Lands color filter string to use for adjusted ratings.
        Single color (e.g. "U") is used once we have 1 main color established.
        Color pair (e.g. "WU") is used once a second color reaches >= 3 cards.
        Empty string means undecided (no meaningful color lean yet).
        """
        main = self.main_colors()
        if len(main) == 2:
            return "".join(sorted(main))   # "WU", "UB", etc.
        if len(main) == 1:
            return main[0]                 # "U", "W", etc. — single color lean
        return ""

    # ------------------------------------------------------------------
    # Mana curve
    # ------------------------------------------------------------------

    def curve(self) -> dict[int, int]:
        counts: defaultdict = defaultdict(int)
        for name in self.picks:
            cmc = ratings.get_cmc(name)
            counts[cmc] += 1
        return dict(sorted(counts.items()))

    def curve_string(self) -> str:
        """
        Show creature curve (top row) separately from spell curve (bottom row).
        Based on Verhey's advice: reactive spells don't count as curve fillers.
        Format: "2:2c 3:3c 4:1c | 2:1s 3:2s" (c=creature, s=spell)
        """
        creature_curve: defaultdict = defaultdict(int)
        spell_curve: defaultdict = defaultdict(int)
        for name in self.picks:
            cmc = ratings.get_cmc(name)
            types = ratings.get_types(name)
            if "Land" in types:
                continue
            if "Creature" in types:
                creature_curve[cmc] += 1
            else:
                spell_curve[cmc] += 1

        c_str = " ".join(f"{c}:{n}c" for c, n in sorted(creature_curve.items())) or "—"
        s_str = " ".join(f"{c}:{n}s" for c, n in sorted(spell_curve.items()))
        return f"{c_str}" + (f"  |  {s_str}" if s_str else "")

    # ------------------------------------------------------------------
    # Pick recommendation
    # ------------------------------------------------------------------

    def _deck_metrics(self) -> synergy.DeckMetrics:
        """
        Build synergy metrics from current picks.
        Memoized: rebuilds only when the picks list changes.
        This avoids 14x redundant oracle scans per pack display.
        """
        if self.picks != self._metrics_picks_snapshot:
            self._metrics_cache = synergy.build_metrics(self.picks)
            self._metrics_picks_snapshot = list(self.picks)
        return self._metrics_cache  # type: ignore[return-value]

    def adjusted_rating(self, card_name: str) -> tuple[float | None, str]:
        """
        Win rate + grade adjusted for current deck colors and synergies.
          1. Start with color-filtered 17Lands GIH win rate.
          2. Apply off-color penalty for unestablished splash colors.
          3. Add synergy bonus based on deck composition.
        """
        # Basic lands: no 17Lands data, but give a synthetic rating based on
        # how many lands the deck currently has. Target is 17 lands in 40 cards.
        # A free basic land is worth taking over most chaff late in the draft.
        #
        # Basic land names are hardcoded as a fast path because Arena IDs for
        # basics are resolved to names without fetching full oracle/type data,
        # so ratings.get_types() may return [] and the type-check would miss them.
        types = ratings.get_types(card_name)
        if card_name in _BASIC_LAND_NAMES or ("Land" in types and not ratings.get_colors(card_name)):
            oracle = card_db.get_oracle(card_name).lower()
            # Only apply synthetic rating to true basic lands.
            # A basic land's oracle is just a parenthetical mana ability e.g. "({T}: Add {W}.)"
            # Utility lands like Rogue's Passage have additional non-mana abilities.
            _is_basic = (
                "whenever" not in oracle
                and "enters" not in oracle
                and oracle.count("{t}") == 1          # exactly one tap ability
                and "," not in oracle                  # no activated abilities (cost, ability)
                and oracle.count(":") == 1             # only one colon (one ability)
            )
            if _is_basic:
                land_count = sum(1 for p in self.picks if "Land" in ratings.get_types(p))
                if land_count < 15:
                    synthetic_wr = 57.0 - (land_count * 1.0)  # Decreases as lands accumulate
                elif land_count < 17:
                    synthetic_wr = 54.0
                else:
                    synthetic_wr = 50.0  # Already have enough lands
                grade = ratings.winrate_to_grade(synthetic_wr)
                return synthetic_wr, grade

        cf = self.color_filter_for_ratings()
        wr = ratings.get_winrate(card_name, color_filter=cf if cf else "All Decks")
        if wr is None:
            wr = ratings.get_winrate(card_name, "All Decks")

        # Off-color penalty — scaled by pip count in the mana cost.
        # A card with {B}{B} in an GU deck is far worse than a splash {B}.
        # Base penalty: 4.0 pp. Each additional off-color pip beyond the first
        # adds 1.5 pp, capped at 9.0 pp total.
        #
        # Flexibility factor: penalties are reduced when the draft is young (<20 picks).
        # Pack 2 signals about open colors should still be readable — full rigidity
        # only locks in once the deck is well-established (20+ picks).
        #   0 picks  → 50% penalty (maximum flexibility)
        #   10 picks → 75% penalty
        #   20+ picks → 100% penalty (locked in)
        n_picks = len(self.picks)
        _flex = min(1.0, 0.5 + n_picks / 40.0)  # reaches 1.0 at 20 picks

        if wr is not None and cf:
            card_colors = ratings.get_colors(card_name)
            # Lands have no color identity in 17Lands data — infer from oracle text
            if not card_colors and "Land" in ratings.get_types(card_name):
                card_colors = _land_produced_colors(card_name)
            main_set = set(self.main_colors())
            # Emerging colors: 1–2 cards picked of a color = soft commitment.
            # Treat these at 50% penalty so we can keep picking into them
            # without the full off-color discount burying those cards.
            counts = self.color_counts()
            emerging_set = {c for c, n in counts.items() if 1 <= n < 3}
            if card_colors and not any(c in main_set for c in card_colors):
                off_pips = _count_off_color_pips(card_name, main_set)
                penalty = min(4.0 + max(0, off_pips - 1) * 1.5, 9.0)
                # Halve the penalty if this card's color matches an emerging direction
                if any(c in emerging_set for c in card_colors):
                    penalty *= 0.5
                wr = max(0.0, wr - penalty * _flex)

                # Zero-source penalty: if the deck has no land that produces
                # any of this card's colors, it's effectively uncastable.
                # Add -2pp on top of the standard off-color penalty.
                # Also scaled by flexibility so early pivots remain visible.
                picked_colors: set[str] = set()
                for p in self.picks:
                    if "Land" in ratings.get_types(p):
                        picked_colors.update(_land_produced_colors(p))
                if not any(c in picked_colors for c in card_colors):
                    wr = max(0.0, wr - 2.0 * _flex)

        # Partial off-color penalty for dual lands: a land that produces one
        # on-color and one off-color mana passes the full off-color block above,
        # but the unused color pip still represents wasted fixing slots.
        # Apply -1.5pp per off-color mana the land produces (scaled by flex).
        if wr is not None and cf:
            types = ratings.get_types(card_name)
            if "Land" in types:
                produced = _land_produced_colors(card_name)
                main_set = set(self.main_colors())
                off_colors = [c for c in produced if c not in main_set]
                if off_colors and any(c in main_set for c in produced):
                    # Mixed land: some on-color, some wasted — partial penalty
                    wr = max(0.0, wr - len(off_colors) * 1.5 * _flex)

        # Tapland penalty: dual lands that ETB tapped have inflated 17Lands rates
        # because good players in 2-color decks take fixing, skewing the data.
        if wr is not None:
            oracle = card_db.get_oracle(card_name).lower()
            if ("land" in ratings.get_types(card_name) and
                    ("enters tapped" in oracle or
                     "enters the battlefield tapped" in oracle)):
                wr = max(0.0, wr - 1.5)

        # Synergy bonus: cards whose text synergizes with current deck composition
        if wr is not None:
            metrics = self._deck_metrics()
            syn = synergy.bonus(card_name, metrics)
            if syn > 0:
                # A card you can't cast provides zero synergy. Apply the bonus only
                # when the card is on-color or colorless. For emerging colors (1–2
                # cards), apply at 50% — the direction isn't locked yet.
                syn_colors = ratings.get_colors(card_name)
                _main_set  = set(self.main_colors())
                _counts    = self.color_counts()
                _emerging  = {c for c, n in _counts.items() if 1 <= n < 3}
                if not syn_colors:
                    wr += syn                    # colorless — always applies
                elif any(c in _main_set for c in syn_colors):
                    wr += syn                    # on-color — full bonus
                elif any(c in _emerging for c in syn_colors):
                    wr += syn * 0.5             # emerging — half bonus
                # else: fully off-color — no synergy bonus

            # BREAD bonus: evasion keywords + removal text
            oracle = card_db.get_oracle(card_name)
            wr += synergy.bread_bonus(oracle)

            # Deck skeleton penalty: curve integrity + creature density
            penalty = synergy.deck_skeleton_penalty(card_name, metrics, len(self.picks))
            wr = max(0.0, wr + penalty)

            # Enabler/payoff gap: reward cards that fill the missing half
            wr += synergy.enabler_payoff_gap_bonus(card_name, metrics)

            # Colorless flexibility bonus: cards with no color identity are always
            # castable regardless of deck direction. +0.75pp reflects that a colorless
            # card is a free pick that never constrains or conflicts with your colors.
            # Lands excluded (they're handled by the synthetic rating path above).
            if not ratings.get_colors(card_name) and "Land" not in ratings.get_types(card_name):
                wr += 0.75

            # Removal scarcity: premium for interaction when deck has fewer than 3.
            # Only award the bonus if the removal is on-color — off-color removal
            # you can't cast is not actually a solution to scarcity.
            scarcity = synergy.removal_scarcity_bonus(card_name, metrics)
            if scarcity > 0:
                rem_colors = ratings.get_colors(card_name)
                if not rem_colors or any(c in set(self.main_colors()) for c in rem_colors):
                    wr += scarcity
                # else: off-color removal — scarcity bonus withheld

            # Duplicate penalty: diminishing returns for extra copies of the same card.
            # Basic lands are exempt. Each copy beyond the first costs 1.5 pp,
            # beyond the second costs 3.0 pp (another 1.5), capped at -4.5 pp.
            copies = self.picks.count(card_name)
            if copies > 0 and "Land" not in ratings.get_types(card_name):
                dup_penalty = min(copies * 1.5, 4.5)
                wr = max(0.0, wr - dup_penalty)

        grade = ratings.winrate_to_grade(wr)
        return wr, grade

    def best_pick(self, card_names: list[str]) -> str | None:
        """
        Return the card with the highest adjusted win rate.
        Returns None if ratings are not loaded — never guess when we have no data.
        """
        if not ratings.is_loaded():
            return None

        best_name, best_wr = None, -999.0
        for name in card_names:
            if not name:
                continue
            wr, _ = self.adjusted_rating(name)
            # Only consider cards that have actual 17Lands data
            if wr is not None and wr > best_wr:
                best_wr, best_name = wr, name
        return best_name

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------

    def summary(self) -> dict:
        return {
            "total_cards":      len(self.picks),
            "pack":             self.pack_number,
            "pick":             self.pick_number,
            "main_colors":      self.main_colors(),
            "color_breakdown":  dict(self.color_counts()),
            "curve":            self.curve_string(),
        }

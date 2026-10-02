# FP-020 (proposed) — Win routes: every deck needs a way to win, and the tool must know which

Scoping note, 2026-09-26. Written for owner review **before** any code
lands, the way FP-016 (`LLM_DECK_JUDGE_SCOPE.md`) was. Research behind
it: `WINCON_RESEARCH.md` (58 decks, real oracle text, Spellbook
top-1500). Owner premise, verbatim: *"Every deck needs a win on either
an infinite combo or some other way."*

---

## 1. The question, and what answers it today

"Can this deck win, and how?" is answered in commander-builder by one
number: `ROLE_TARGETS["finisher"] = 3`, counted over cards whose oracle
text matches a finisher/win-condition pattern. The research shows that
number is a drain-and-infect detector: 45 of the 58 most-liked decks
fail it, 19 with zero — Vivi, Elsha, Kefka, Krenko, The Ur-Dragon among
them — while a route reading finds a win in 53 of 58 and agrees with
the pilots' own primers in 28 of 29 cases.

The premise is right and the instrument is wrong. Decks win by
**routes**; only two of nine routes leave a "win" in oracle text.

## 2. What a win route is

A `WinRoute` is `{kind, pieces, outlets, strength, thin}`:

- `kind` — one of nine: `combo`, `alt_win`, `drain`, `burn`, `poison`,
  `mill`, `combat_wide`, `combat_voltron`, `combat_big`. These are the
  words primers already use (research finding 6), so a stated route
  and a detected route share a vocabulary.
- `pieces` — the cards that make the route exist (the combo's cards;
  the drain triggers; the overrun and the token makers).
- `outlets` — for `combo` only: the cards that turn a *resource* loop
  into a kill (Impact Tremors for an ETB loop, Blood Artist for a
  death loop, an overrun for a token loop, an X-damage spell for mana).
- `strength` — redundancy count: how many independent pieces could be
  removed before the route disappears. A route with `strength == 1`
  is `thin` (Yuriko with one Thassa's Oracle and no Consultation).

The deck-level result is `WinRoutes = {routes, primary, verdict}` with
`verdict ∈ {present, thin, none, unknown}`; `unknown` is the outage
contract (oracle coverage below `MIN_ORACLE_COVERAGE`, the same rule
`archetype.py` uses) and never masquerades as `none`.

**Kill vs resource combos — the one change to combo detection.**
`combo_detection.is_game_ending` treats any "infinite" as game-ending.
That is right for bracket pressure (an infinite-mana deck *is* a B4
deck) and wrong for "can it win". FP-020 adds `combo_outcome(combo)
-> kill | resource(needs) | value` beside it, leaving
`is_game_ending` and the bracket floor untouched. A resource combo
counts toward the `combo` route only when the deck holds an outlet for
what it produces. Outlets are matched one step only — "infinite
landfall → land tokens → needs haste" is reported as *engine present,
kill not recognised*, not chased.

## 3. Where it is factored in — the seams

| Seam | Today | With FP-020 |
|---|---|---|
| `staples.role_target_report` (`finisher` target) | counts finisher-pattern cards, target 3 | the `finisher` deficit is **satisfied by any non-thin route**; the pattern count stays as a sub-signal, no longer a deficit on its own |
| `deck_health.compute_deck_health` | no win signal; `wincon_protection` counts Silence-class cards | new `win_routes` tile: present (≥1 route, strength ≥2) · thin · none · unavailable. `compute_health_grade` gets it as a `construction_signals` sub-score with the outage exclusion the other tiles have |
| `intent.learn_intent` → `Intent.key_wincons` | finisher/win_condition-pattern cards | **route pieces and outlets** of the primary route. This is the protection seam: `improve` appends `key_wincons` to the protected list, so the improver stops cutting Impact Tremors out of a Krenko deck or the second half of Sanguine Bond |
| `Intent.stated` (FP-018.2) | free text steering attention only | a stated route is parsed from the primer with the nine words (same negation-aware matcher as preferences); `adopt` reports **stated vs detected** — "primer says combo; no combo found in the 99" is the highest-value line adopt can print |
| `_deck_judge_prompt.plan_coherence` gloss | "does the deck have one plan its cards execute" | "…and a named win route — combo, combat, drain, alt-win — that the plan actually reaches" plus the detected route list in the intent block. The judge still never invents card facts: routes come with their pieces |
| `improve` / `_proposer_cli` proposals | can propose cutting a route piece; cannot propose a route | when `verdict == none`: the round's first proposal is a **route add**, chosen by archetype/themes and bracket (`combo` adds only where `combo_bracket_floor` allows; a B2 deck gets combat or alt-win suggestions); when `thin`: a redundancy add for the primary route |
| `adopt` (FP-018.3) | polish-tier suggestions, cuts guarded by `Protect=` | route pieces join the auto-protected set alongside primer card-links; a `none` verdict is reported, never "fixed" (adopt stays read-only) |
| `bracket_estimator` | combo-aware via `combo_bracket_floor` | unchanged; `combo_outcome` is additive |
| knowledge log | `verdict` rows carry no route | `win_routes` JSON on `save_iteration` so the agreement study (FP-016 phase 2) can split by route kind — the politics-blind dimension is expected to concentrate in combat routes |

## 4. Rules that must hold (from the research)

1. **Presence is not enough; redundancy is the bar.** Every pilot deck
   with a stated plan carried a backup (finding 4). `thin` is a real
   verdict, distinct from `none`.
2. **The outlet is part of the win.** Protecting combo pieces without
   their outlet breaks the kill (finding 3).
3. **`one_piece_away` is not a route.** 55/58 decks are one card from
   *some* top-1500 kill combo (finding 7). It stays a bracket-aware
   suggestion list.
4. **The commander counts double, as it does for roles.** Vivi and
   Azula win *through* the commander; a route whose piece is the
   commander is never `thin` on that piece alone
   (`COMMANDER_ROLE_CREDIT` precedent in `staples`).
5. **Unknown is not none.** Under the oracle-outage contract the tile
   reads "unavailable", the target stays satisfied, and no route-add
   is proposed.
6. **Stated beats detected for attention, never for facts.** A primer
   that says "combo" makes adopt *look* for one; it does not make one
   exist.

## 5. Phases

**Phase 1 — measure only.** `win_routes.py` (pure: oracle lookup
injected, combos injected; ~500 lines) with the nine detectors,
`combo_outcome`, and the deck-level verdict. Tests pinned on the
research corpus: the 862-card oracle subset and the combo capture
become fixtures with provenance (real data, captured through the lane
— never synthesized). `commander-health` and the dashboard show the
tile. `role_target_report` learns the route satisfaction rule.
Nothing proposes anything yet.

**Phase 2 — protect.** `Intent.key_wincons` from route pieces +
outlets; `adopt` reports stated vs detected; the judge gloss.

**Phase 3 — propose.** Route-add / redundancy-add proposals in
`improve`, bracket-gated. Gated on Phase 1 shipping and the owner
having seen the tile on their own decks for a while.

## 6. Pre-registered kill criteria

Declared before any code exists, per the FP-015/FP-016 discipline:

- **G1 — corpus agreement.** On the 29 stated-route decks the shipped
  detector must keep ≥ 25 full-or-partial agreements and 0
  contradictions (a detected route the pilot explicitly disclaims,
  e.g. "no infinite combos" → `combo`). Below that, the taxonomy is
  wrong, not the thresholds.
- **G2 — owner's decks.** On the owner's own deck directory the tile
  must read `none` on no deck the owner considers finished. One
  false `none` on a tuned deck parks Phase 3.
- **G3 — the finisher-target regression.** After Phase 1, `commander
  audit` on the research corpus must stop reporting a finisher deficit
  for the 40 decks that have a non-thin route. If the deficit count
  does not fall below 10, the satisfaction rule is miswired.

## 7. Honest risks

- **In-sample thresholds.** The prototype's numbers were tuned on the
  corpus they are measured on; G1 must be re-read on the next harvest
  batch (batch 3 rules are standing).
- **Combo coverage is the top-1,500 by popularity**, and `data/` is
  gitignored: the sandbox and CI have only the 20-entry fallback. Phase
  1 needs a decision on shipping a trimmed combos file (D4).
- **Combat routes are the weakest detectors** (power-only `combat_big`,
  Arcades' toughness plan, Zimone's X-spell tokens). The `unknown` and
  `thin` verdicts exist so those read as uncertainty, not absence.
- **Precons will read `none`** — correctly, per the research — and a
  new user importing a precon will meet the tile first. The wording
  must say "no closer detected" and name what would count, not "bad
  deck".

## 8. Decisions — put to the owner (see `DECISIONS_FOR_REVIEW.md`, FP20-D1…D5)

- **D1.** Does a resource loop with no recognised outlet count as a
  route (`thin`), or as none?
- **D2.** Redundancy bar: `strength ≥ 2` for `present`, or per-route
  bars (e.g. voltron ≥ 8 gear pieces but combo ≥ 1 kill + 1 backup)?
- **D3.** Should `improve` ever *add* a route on its own (Phase 3), or
  only flag and let the owner choose?
- **D4.** Ship a trimmed `data/combos.json` (top-N by popularity, with
  provenance) so the sandbox, CI and a fresh install detect combos, or
  keep combos owner-machine-only behind `--refresh`?
- **D5.** Is "stax lock" (Heliod's "silence is a valid win condition")
  a route, or a plan that still needs one of the nine?

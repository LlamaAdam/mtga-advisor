# Two-AI review of commander-builder (2026-08-13)

Two independent AI analysts reviewed the
[commander-builder](https://github.com/LlamaAdam/commander-builder) repo:
a **code reviewer** focused on the LLM/Ollama integration and core loop,
and an **MTG domain analyst** who checked the game logic against the
official August 2026 Commander format state (with web sources). Each then
cross-examined the other's findings; the joint verdict is at the end.

> Note on methodology: the plan was to run this conversation through a
> local Ollama model in-session, but the cloud environment's network
> policy blocks every model-weight source (see MODEL_GUIDE.md). The two
> analysts here are independent Claude subagents with different lenses;
> `run_local_review.py` reproduces the same loop against a local Ollama
> model on your own machine.

---

## Part 1 — Code review findings (ranked)

### High severity

1. **`--auto-propose` never applies the LLM's proposal to disk**
   (`iteration_loop.py:91-125`). `propose_then_iterate()` proposes
   against the *new* deck file and then sims the two pre-existing files —
   there is no `apply_proposal_to_deck` step. The knowledge log records a
   manifest describing changes that were never made, poisoning exactly
   the training data the project exists to accumulate. Fix: propose
   against the OLD deck, materialize the new one (as
   `_proposer_cli.auto_curate_main` already does), then sim.

2. **Web `save_iteration` writes the absolute margin into the signed
   `margin` column** (`web/routes_sim.py:902-905` via `_execute_swap`;
   `ComparisonReport.margin` is `abs(...)` per `compare_versions.py:187-189`,
   while `knowledge_log.py:23` documents the column as `new_wins - old_wins`
   and the CLI paths write signed). Web-recorded regressions look like
   improvements in any pooled analysis. Fix: always compute
   `new_w - old_w` in `save_iteration`; ignore the payload's `margin`.

3. **Ollama HTTP errors are misclassified as "daemon not reachable" and
   silently swallowed** (`analyst.py:410-413`, same shape in
   `proposer.py:334-337`). `HTTPError` is a subclass of `URLError`, so a
   404 for a not-pulled model becomes `NotImplementedError` → the
   router's *quiet* fall-through. Every verdict degrades to the
   low-confidence heuristic with zero output — violating the module's own
   "wired-but-misbehaving must be LOUD" contract (`analyst.py:99-111`).
   Fix: catch `HTTPError` first and re-raise as `RuntimeError`.

4. **API/local proposers are fed a browser-workflow prompt they cannot
   execute** (`proposer.py:201-249`, `:293-320`). `claude_propose` and
   `ollama_propose` send the 706-line `prompts/moxfield_audit_v3.md` —
   which opens with "STEP 0 — ASK ME FIRST" and drives `javascript_tool`
   fetches — to tool-less API calls. The model either fails JSON parsing
   or fabricates a manifest from zero reference data. Fix: dedicated
   API-mode prompts with pre-fetched EDHREC/peer data in the user message
   (the machinery already exists in `_advisor_claude.py` /
   `_AUTO_PROPOSE_SYSTEM_PROMPT`).

### Medium severity

5. **Empty LLM responses raise `NotImplementedError`** → silent
   fall-through on a *paid* call (`analyst.py:347-348`, `:416-417`).
   The proposer paths already correctly use `RuntimeError`.
6. **Analyst heuristic's "decisive games" counts filler-won games**
   (`analyst.py:144-158`: `decisive = total - draws`), contradicting the
   repo's own convention (`knowledge_log.py:27-32`:
   `decisive = old_wins + new_wins`). With 20 pod games the
   `min_decisive_games=8` gate effectively always passes even when the
   head-to-head pair won 2-3 games. `margin_strong_threshold=4` is also
   game-count-invariant. Fix: head-to-head decisive + sample-size-aware
   threshold.
7. **The Claude/Ollama analyst backends are unreachable dead code** —
   no CLI flag, config key, or web parameter ever sets
   `use_claude`/`use_ollama` (only tests do). Docs oversell this
   ("available with API key / running daemon"). Fix: add
   `--analyst {heuristic,claude,ollama}` to `commander-iterate`, or
   delete the backends and the claims.
8. **Sim summaries handed to the LLM carry the absolute margin, and the
   Ollama summary omits `winner`** (`compare_versions.py:328-333`,
   `analyst.py:313`, `:385`) — a small model can read `margin: 6` as an
   improvement on a regression. Fix: pass signed margin + winner.
9. **Four Claude call sites resolve API keys four different ways**
   (header→config→env in `routes_audit.py`; env *membership* in
   `analyst.py:292` / `proposer.py:221` — which treats the deliberately
   empty `""` never-bill key as wired; truthiness+CLI in
   `auto_propose`). Fix: one `resolve_anthropic_key()` helper.
10. **No Host-header validation on the localhost Flask server** — a
    DNS-rebinding page becomes same-origin and can read decks and
    `PUT /api/config`. Cheap fix in the existing `before_request` hook.

### Low severity

11. Proposer WARN lines drop the exception message (`proposer.py:151-163`).
12. Malformed BYO-key header silently skips config-key fallback
    (`routes_audit.py:91-103`).
13. `_is_decisive` docstring example arithmetic is wrong
    (`compare_versions.py:369-374`) — behavior correct, comment not.
14. Backend ladder order is inverted between analyst (Ollama→Claude) and
    proposer (Claude→Ollama), undocumented; garbage JSON kills one
    pipeline and quietly degrades the other.
15. Retry policy exists only on the subscription-CLI curator path; SDK
    and Ollama calls get none.

### Ollama-path gap analysis

The "local Ollama (cost saving)" tier the docs advertise is, today, two
dead functions with mis-tuned prompts and silent failure handling:

- **No entry point reaches it** — no CLI flag, no web parameter, no
  config key sets `use_ollama` anywhere in `src/`.
- **No `_advisor_ollama.py`** counterpart to `_advisor_claude.py` despite
  the module docstring promising one.
- **Prompts are Claude prompts, unadapted** — nothing is sized for a 3B
  model, and the tasks the architecture doc marks "✅ strong fit for
  local" (archetype classification, card role tagging) are
  `NotImplementedError` stubs (`archetype.py:225-233`) with no caller.
- **Failure modes are quieter than Claude's** (HTTPError bug, no retry,
  no preflight that `config.ollama_model` is actually pulled — doctor
  lists models but never checks the configured one).
- **No config plumbing** for `ollama_url`/`ollama_model` beyond dataclass
  defaults.

### Code reviewer's top 5 app improvements

1. Close the auto-propose loop for real (propose → apply → snapshot →
   compare → analyze as one honest path).
2. One credentials resolver + one failure taxonomy (`BackendUnavailable`
   vs `BackendMisbehaved`) for all LLM call sites.
3. Statistical hygiene: head-to-head decisive everywhere, signed margins
   everywhere, sample-size-aware thresholds.
4. Prompt/provenance registry: versioned API-mode prompts per backend
   capability class, recorded in the existing `audit_version` column.
5. Enforce the 800-line module ceiling on `card_score.py` (1,820),
   `moxfield_import.py` (1,699), `deck_builder.py` (1,561).

---

## Part 2 — MTG domain findings

### Bracket system vs. official Aug 2026 state

**Current and correct:** the bundled 53-card Game Changers fallback
matches the live official list (post-Feb 9 2026 update — includes
Farewell and Biorhythm, excludes all ten Oct 2025 removals); GC caps per
bracket (0/0/≤3/∞/∞) are right; there is still no official points
system, and the app's weighted score is honestly labeled as its own.

**Outdated — the estimator encodes pre-Oct-2025 beta rules:**

- **Two-card-combo floor is wrong.** `bracket_estimator.py:548-566`
  hard-floors *any* game-ending two-card combo at B4, overriding
  `combo_detection.combo_bracket_floor`'s speed rule — but since the
  [Oct 21 2025 update](https://magic.wizards.com/en/news/announcements/commander-brackets-beta-update-october-21-2025),
  late-assembling (~turn 6+) two-card combos are explicitly Bracket-3
  legal. The repo's own combo_detection module matches the official rule
  better than the code that overrides it. Net effect: legal B3 decks get
  over-bracketed, which poisons pool curation and build steering.
- **The 4+-tutor auto-bump cites a repealed rule** (`:119-131, :604-610`)
  — Oct 2025 removed tutor restrictions from the brackets entirely. Fine
  as a labeled power heuristic; false as "official rules transcription."
- **Extra-turn floor misaligned**: B4 floor at count ≥ 2, but official
  language is about *chaining*; and `_EXTRA_TURN_CARDS` has only 6 names
  (missing Alrund's Epiphany, Temporal Mastery, Part the Waterveil, …),
  so it over-fires on semantics and under-fires on coverage. `_MLD_CARDS`
  (8 names) is similarly thin.
- **The official "expected game length" framing is unused** even though
  `game_analyzer` end-turn telemetry — the perfect raw signal — is
  already in-tree.

### Deck-quality heuristics

**Sound:** the Command-Zone-style `ROLE_TARGETS` (ramp 10 / draw 10 /
removal 8 / wipe 3 / protection 4 / finisher 3) with the
commander-absorbs-2 rule; the correctly-transcribed Karsten 99-card
manabase table; the 38±2 land model; the honest
`MIN_DECISIVE_GAMES_FOR_VERDICT = 20` inconclusive gate.

**Divergent or buggy:**

- **Free-mulligan bug** (`consistency.py:98-100`): claims Commander
  grants no free mulligan — it does (CR 103.4c), and
  `deck_builder_manabase.py:163-165` in the same repo *depends* on it.
  Every mulligan-rate and commander-on-curve stat shown to users is
  systematically pessimistic, and the health grade consumes them.
- **Draw ceiling == floor deadlock**: `ROLE_SATURATION_THRESHOLDS["draw"]
  = 10` equals the target 10, so the advisor can never recommend an 11th
  draw spell — below current consensus (~12 card-advantage pieces for
  most B3+ decks). Targets also don't scale with bracket/archetype.
- **Land-band contradiction**: builder clamps 33-40 (seed-trust to 42)
  while `deck_health._LAND_BAND=(33,38)` docks ~12 pts/land — the app
  penalizes its own builds.
- **Manabase tiers are stale**: no triomes for 3+ color, no surveil
  duals on the budget path, while budget mode keeps City of Brass/Mana
  Confluence and the default path pushes $200+ ABU duals at every
  bracket. `UNIVERSAL_STAPLES_LC` claims 50-80% ubiquity for Evolving
  Wilds-class lands that tuned 2026 decks cut.
- **Archetype classifier is name-regex only** yet its combo/stax labels
  carry ±1.0/±0.5 bracket weight, and it can disagree with the real
  `combo_detection` module in the same pipeline.
- `card_score.py` is well-designed **and honestly gated off** after
  failing its pre-registered validation twice — the right call.

### Simulation validity

Good as a *falsifier* (mana/curve/threat-density regressions show up).
Blind spots: no politics (Rhystic-style tax and goad/monarch/vote cards
are systematically mis-valued and may get "empirically" cut), Forge AI
can't pilot combo/stax/storm (B5 sims least valid exactly where human
data is best), ~±15pp CI on a 40-game A/B (no CI reported), no RNG seed,
and the vendored Forge 2.0.12 is two sets behind (current 2.0.14) so the
loop structurally can't validate the newest staples.

### Meta-data sourcing

- EDHREC: `json.edhrec.com` remains the standard keyless route; moving
  commander pages + salt there would de-brittle the `__NEXT_DATA__`
  scrape and likely unblock the bot-challenge-blocked salt backfill
  (STATUS.md:293-296).
- Moxfield: still no official public API in 2026; single point of
  failure, partial Archidekt hedge exists.
- edhtop16: current and correctly scoped B5-only;
  [topdeck.gg's documented Tournaments V2 API](https://topdeck.gg/docs/tournaments-v2)
  is a sturdier upstream not yet used.
- Format cadence: WotC moved to **seven B&R windows in 2026**, but
  Scryfall oracle snapshots have **no TTL** — a ban can be invisible for
  months on a cold box. (Aug 10 2026 B&R: no Commander changes; next
  window Oct 12 2026.)

### Domain analyst's top 10 improvements (ranked by player value)

1. Re-base `bracket_estimator` on the Oct 2025 / Feb 2026 official rules
   (combo floor defers to speed rule; tutor bump demoted to labeled
   heuristic; extra-turn floor keyed on chainability).
2. Fix the free-mulligan bug in `consistency.py`.
3. Ban-window-aware data freshness (TTL / announcement-date-triggered
   re-pull of `legalities.commander` + GC refresh).
4. Upgrade vendored Forge 2.0.12 → 2.0.14; surface "N cards unsupported
   by your Forge build" in the dashboard.
5. Generate the hard-rule card lists (extra-turn / MLD / tutors) from
   oracle text at refresh time with human-reviewed diffs.
6. "Sim-invisible" guard: exempt politics/taxing cards from
   sim-margin-driven cuts (like `Protect=` already does for categories
   the pipeline can't judge).
7. Wilson/bootstrap CIs on A/B verdicts + goldfish-clock secondary
   endpoint (aligns with the official expected-game-length framing and
   could feed the estimator).
8. Bracket/archetype-scaled `ROLE_TARGETS`; break the draw
   ceiling==floor deadlock.
9. Modernize manabase tiers (triomes, surveil duals, MDFC-aware counts;
   reconcile the 33-40/42 vs 33-38 land-band contradiction).
10. Move EDHREC ingestion to `json.edhrec.com`; add topdeck.gg V2.

---

## Part 3 — Cross-examination and joint verdict

*(filled in after each analyst reviewed the other's findings)*

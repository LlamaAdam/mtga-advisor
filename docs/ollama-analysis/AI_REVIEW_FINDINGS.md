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

### The domain analyst on the code findings

**Impact ranking.** The three findings that most corrupt Magic-facing
output: the auto-propose apply gap (A — knowledge-log rows pair a
manifest with a sim of an unrelated diff), the unsigned web margin (B —
signed margin is the exact regressand FP-002 pivoted to; web rows flip
every regression's sign), and the decisive-games definition (E — in
4-player pods the A/B pair wins only ~half the non-draw games, so
verdicts issue off ~2-5 pair-relevant games while the gate always
passes).

**Contested / refined:**

- **The verdict threshold is statistically indefensible even after the
  proposed fix.** Under the null, pair-decisive wins split
  ~Binomial(n, 0.5): with 20 decisive games, P(|new−old| ≥ 4) ≈ 0.50 —
  **half of all neutral swaps get a confident kept/reverted verdict.**
  This is the likeliest domain explanation for FP-002's own observation
  that "significant" features collapsed as n grew. The fix is a binomial
  test / CI (at 20 decisive, p<0.05 two-sided needs ~15-5), not a bigger
  constant.
- **A is recoverable, not fatal**: `compare_versions` computes its own
  diff from the `.dck` files and snapshots are stored, so poisoned rows
  can be *re-derived* post-hoc rather than discarded.
- **C is latent, not active** — since nothing ever sets `use_ollama`
  (F), the silent-degrade bug can't fire yet. F outranks C.
- **G's real failure is evidential, not legality** — post-filters
  enforce color identity/GC caps/singleton, so hallucinated proposals
  are *legal-but-unevidenced*, which is subtler and worse.

**New failure modes the code findings imply:**

1. **B × EDHREC-seeded builds recreates the "no negative class"
   pathology**: fresh builds are where early iterations genuinely
   regress most; flipping those margins positive erases exactly the
   negative examples FP-002 said the dataset lacked.
2. **E × pool hygiene compounds**: a mislabeled strong filler farms pod
   wins, inflates "decisive," and pushes pair verdicts through the gate
   on even fewer relevant games — two hygiene mechanisms fail open on
   the same path.
3. **A × `revert_to` lineage**: "revert to the iteration that won" can
   restore a deck state that never produced the recorded result — a
   direct player-facing wrong action.
4. **F means FP-013 is banking nothing**: with both LLM analyst backends
   dead, every `lessons` field is template text; the intended fine-tune
   corpus doesn't exist despite appearing to accumulate.
5. **G + name-validation → staple-soup drift**: hallucination filtering
   passes exactly the famous cards a model can name from memory, so
   unevidenced proposals survive *only when generic* — systematically
   ratcheting synergy decks toward EDHREC-average goodstuff while the
   underpowered verdict statistics can't catch the quality loss.
6. **H is missing draws, not just winner**: an LLM summary without draw
   counts can't distinguish "even matchup" from "deck can't close" —
   opposite lessons, and the latter is precisely the official
   expected-game-length signal.

### The code reviewer on the domain proposals

**Feasibility highlights** (effort in S/M/L, verified against source):

- Bracket re-base (#1): **M**, mechanical — the weights/frozensets are
  already a single tuning surface; defer the 2-card floor to
  `combo_detection.assess_deck_brackets`.
- Free-mulligan (#2): **S**, isolated; display-only signal, low blast
  radius.
- Oracle TTL (#3): **M**, verified — `lookup_card` serves the disk cache
  forever. Caution: scope the TTL to legality fields / bulk-date check,
  or ~32k snapshots refetch-storm at once.
- Forge upgrade (#4): **split it.** Surfacing unsupported-card counts is
  ~free (`log_parser` already extracts them; the web never shows them);
  the 2.0.12→2.0.14 engine upgrade is **L** and touches the most
  regex-brittle surfaces (`log_parser`, `_PER_GAME_WIN_RE` salvage
  paths, the FP-001 frozen-fork plan) — needs a 2.0.14 stdout regression
  corpus first.
- Generated card lists (#5): **S/M** via the existing
  `_card_list_refresh.py` diff-and-review pattern — but only MLD and
  extra-turns are cleanly derivable from oracle text; tutors are not
  ("search your library" matches fetches/ramp), keep those curated.
- CIs (#7): **S/M** and the *same edit site* as the code reviewer's
  decisive-denominator finding — merge into one change; the signed-margin
  web fix is a prerequisite for any CI math over stored rows.
- EDHREC migration (#10): **half-done already** — `EDHREC_JSON_BASE`,
  `fetch_top_cards`, `fetch_top_commanders` are live; only
  commander/average-deck/tag pages still scrape `__NEXT_DATA__`.

**Contested / corrected:**

- **The free-mulligan issue is a documented assumption with a false
  justification, not an accidental bug** — `consistency.py` lists it
  under "MODELLING ASSUMPTIONS (all deliberate)". Fix the sim *and* both
  contradictory docstrings.
- **The draw "ceiling==floor deadlock" is overstated**: `is_role_saturated`
  fires at `count >= threshold` while a deficit needs `count < target`,
  so demand stops exactly where the guard starts — there's no
  contradiction state. The legitimate residue: zero headroom above the
  floor (no path to 12 draw) and no bracket/archetype scaling.
- Land clamp is 33-40, not "/42"; band mismatch vs (33,38) still real.

### Joint top-5 roadmap (player value per engineering hour)

1. **Close the auto-propose loop + fix the signed-margin web writer**
   (`iteration_loop.py`, `web/routes_sim.py`). The closed loop is the
   product's core promise; its flagship unattended path records
   manifests unrelated to the simmed diff, and the web writer corrupts
   the margin column. Everything downstream is only as good as these
   rows — and per the domain analyst, poisoned rows are *re-derivable*
   from snapshots once fixed.
2. **Verdict statistics package**: head-to-head decisive everywhere +
   Wilson/binomial CI + sample-scaled thresholds (`analyst.py`,
   `_proposer_sim.py`, `compare_versions.py`). One edit site; ends the
   situation where ~half of neutral swaps get a confident verdict.
3. **Legality/rules freshness**: bracket_estimator re-base on the
   Oct 2025/Feb 2026 rules + generated MLD/extra-turn lists +
   legality-scoped oracle TTL. Wrong bracket/ban verdicts are
   user-visible wrongness in every audit.
4. **Two S-sized correctness wins**: surface unsupported-card counts in
   the dashboard (stops silent sim-validity erosion) + the free-mulligan
   fix (unpessimizes every mulligan stat). Defer the Forge engine
   upgrade until a 2.0.14 stdout regression corpus exists.
5. **Finish the EDHREC JSON migration + modernize manabase tiers**
   (triomes, surveil duals, band reconciliation) — likely unblocks the
   bot-challenge-blocked salt backfill and stops recommending a
   2019-era land list.

Deliberately deferred: the sim-invisible politics guard (needs 1-2
landed first so cut decisions are trustworthy at all), ROLE_TARGETS
scaling (pursue via the existing `corpus_themes` norms flag),
topdeck.gg (new integration), the Forge engine upgrade (worst
risk/reward until the regression corpus exists), and the
**Ollama path itself — a delete-or-build product decision**: either
build the thin local-model router the architecture doc sketches (route
the *small* tasks — archetype classification, role tagging — to a local
model with purpose-written schema-first prompts and a model-pulled
preflight), or delete the stubs and the docs' claims. If building:
see MODEL_GUIDE.md — `qwen3:14b` / `gpt-oss:20b` class models for
verdict/proposal, not `llama3.2:3b`, and never the 706-line browser
prompt.

---

# Round 2 (2026-08-16)

Round 1's five roadmap fixes landed on `commander-builder` PR #82
(CI green). Round 2 aimed two fresh analysts at what round 1 skipped,
plus an adversarial verification of the round-1 fixes themselves.

## Part 4 — Round-2 code review

**Round-1 fix verification: all five commits core-sound.** The binomial
math, temp-dir/Name= handling, land-band import, EDHREC cache guards,
free-mulligan model, and path-traversal/SQLite concerns were each
checked and held up. Secondary issues found:

### Medium

1. **`_sim_coverage` rebuilds the ~32k-card Forge DFC index on every
   dashboard request** (`routes_dashboard.py:185-238` +
   `forge_cards_loader.py:222-253`): the `CardsLoader` is constructed
   per request, and any MDFC front-face or unsupported card misses the
   direct slug and triggers a full corpus scan — 1-2s+ stall per
   dashboard load on exactly the decks the feature flags. Fix: memoize
   a supported-slug set at blueprint level, keyed on corpus mtime.
2. **`PUT /api/deck_text` skips the `Name=` restamp every other writer
   applies, and writes non-atomically** (`routes_decks.py:198-214`):
   pasting deck A's text into deck B's editor makes future sims
   misattribute wins — the exact bug class `dck_meta.py` exists to
   prevent. Fix: `rewrite_name(text, path.stem)` + temp-file +
   `os.replace`.

### Low

3. Web `save_iteration` stores `margin=0` (not NULL) for payloads with
   no head-to-head wins — fabricated ties; and pre-fix web rows still
   carry absolute margins (no backfill shipped).
4. `_materialize_proposed_deck` doesn't copy basic-land padding
   (`padded_count`/`dropped_*`) into the manifest on short source
   decks — the manifest↔diff invariant breaks exactly where the fix
   promised it.
5. `propose_then_iterate` sims a no-op (deck vs itself, 10+ games) when
   the applier drops every proposed pair.
6. EDHREC JSON-first double-sleeps on fallback and probes JSON twins
   for arbitrary pasted average-deck URLs.
7. `_EXTRA_TURN_CHAIN_ENABLERS` includes generic recursion (Eternal
   Witness, Regrowth) — 2 extra turns + Eternal Witness hard-floors a
   deck to B4, arguably the over-flagging class round 1 fixed for
   combos.

## Part 5 — Round-2 MTG domain analysis

**Round-1 fix domain verification:** chainability rule defensible
(errs conservative), triome/surveil tiers match 2026 consensus, free
mulligan correct, Game Changers fallback verified current through the
June 29 2026 B&R (no Commander changes; next window Oct 12 2026).
**One real bug found in round-1's own area**: the combo speed rule
prices two-card combos by summed mana value, so reanimator pairs
(Worldgorger Dragon 9 + Animate Dead 2 = 11) read as "late-game
B3-legal" when the real assembly cost is ~3 mana. Fix: use the
reanimation spell's cost when one half is a reanimation effect.

### New findings

1. **HIGH — the archetype classifier is a de facto no-op**: the
   name-regex content scan needs ≥3 hits against tiny keyword lists,
   so ~70-85% of real decks default to "midrange". Consequences: pool
   archetype-diversity always "violates" and ships the default
   arrangement, and the bracket estimator's combo/stax weights almost
   never fire. The fix needs no LLM: derive archetype from oracle
   signals the pipeline already computes (`_detect_game_ending_combos`
   + tutor density → combo; `interaction.classify_interaction` →
   control; a new ~10-pattern stax table — zero stax-text detection
   exists today; `detect_tribal_type` + curve → aggro).
2. **MED-HIGH — `meta_test` is significance-blind**: it prints "the
   references BEAT your deck" on any losing record including 1-2, with
   a CLI default of 2 games per reference — violating the repo's own
   new binomial standard.
3. **MED-HIGH — the role classifier misses evergreen shapes**:
   restricted counterspells (Negate, Swan Song), impulse draw,
   fight/bite removal, edicts, X-damage wipes, Treasure plurals, ward
   — all feeding wrong role deficits/saturation and health grades.
4. **MED — stats-honesty gaps**: web tooltips compute noise on total
   pod games instead of decisive games (real ±0.11 at 40 games, not
   ±0.08); two verdict floors coexist (8 vs 20 decisive); the
   `_proposer_sim` docstring says 26-14 clears at n=40 but the true
   boundary is 27-13; no minimum-detectable-effect display anywhere.
5. **MED — popularity-bias contradiction**: `[PREMADE]` decks are
   excluded from pools/fillers for popularity bias while `[REF]`
   (Moxfield top-likes — the same bias) are deliberately kept and
   filler-eligible.
6. **MED — pool "tournament" ranks on ~9 games/deck** (SE ±0.17);
   `INFLATED_WIN_RATE_THRESHOLD` tags but never acts. Rank on Wilson
   lower bound.
7. **MED — the Game Changers live scrape is known-broken** (the code
   says so itself); Scryfall now publishes an official `game_changer`
   boolean in bulk data the repo already snapshots. Replace the scrape
   with a bulk-field read; keep the fallback and trust gate.
8. Promotions now that prerequisites landed: the **sim-invisible
   politics guard** (goad/monarch/vote/tempting-offer/Rhystic-tax
   oracle tag, `Protect=`-equivalent in every margin-driven cut path)
   and **corpus-scaled ROLE_TARGETS** (via `corpus_themes` medians;
   raise draw saturation to 12). Keep topdeck.gg deferred; gate the
   Forge 2.0.14 upgrade on a stdout regression corpus plus the new
   coverage metric crossing ~2%.

## Part 6 — Round-2 cross-examination and joint verdict

### Corrections that survived the crossfire

- **The chain-enabler fix splits on the wrong axis** (domain analyst
  correcting the code reviewer): calibrate by *repeatability*, not
  genericness. Time Warp → Eternal Witness → rebuy is the textbook
  casual chain, so a one-shot rebuy genuinely chains — but official B3
  language targets what breaks the ~6-turn game-length expectation:
  hard-floor loop-capable enablers (buyback, Mystic Sanctuary +
  fetches, blink-Archaeomancer), weight one-shot rebuys (Regrowth,
  Eternal Witness, Twincast). The reviewer's proposed
  "dedicated-copy-pieces → floor" bucket would floor Twincast
  (one-shot) while weighting Mystic Sanctuary (repeatable) — backwards.
- **The reanimator mis-pricing amends round 1's own verdict** (code
  reviewer, after checking): the pre-fix count-only B4 floor *masked*
  the summed-MV error; the round-1 speed-rule deferral made the
  estimator inherit it — more permissive for reanimator decks. "Sound
  in structure, but the deferred floor inherits a speed-rule error the
  old strict floor masked."
- **Empirical verification of the role gaps**: executing
  `classify_role` against near-verbatim oracle text confirmed Negate,
  Swan Song, Light Up the Stage, Prey Upon, Diabolic Edict, and
  Earthquake all classify `other` today — while disproving two claims
  (Blasphemous Act already → wipe; Big Score already → draw).
- **Exact tails computed**: p(26-14 of 40) = 0.081 (not significant);
  the true n=40 boundary is 27-13 — the new code's own docstring is
  wrong by one game.
- **Any margin backfill must fence at knowledge-log id ≥ 314** (the
  seat-attribution fix): recomputing signed margins for older rows
  would launder pre-fix measurement artifacts into clean-looking data.

### New failure modes surfaced by the crossfire

1. **Structural anti-new-card bias**: unsupported cards are mostly
   *new* cards (vendored Forge trails by two sets); a proposal adding
   a new staple sims as a 98-card deck, loses the A/B, and the loop
   "learns" to cut new cards. The coverage gate must also filter the
   advisor's add-candidates, not just warn before sims.
2. **Web deck edits can poison bracket-tagged pools**: pasting a
   stronger list into a `[B3]`-named file keeps the filename bracket
   tag the pool curator keys on — a hand-edit seats a de facto B4 deck
   as a B3 filler with no estimator check.
3. **No-op sims corrupt the bandit**: in `--search-budget` runs, a
   never-applied arm books a genuine-looking null reward, deflating its
   estimate and misdirecting budget.

### Contested and resolved

- [REF]-vs-[PREMADE] popularity asymmetry: severity lowered — a
  documented policy call at 10× scale difference, not a bug.
- Wilson-bound pool ranking: correct but only changes outcomes where
  per-deck game counts diverge; the material win is finally *acting*
  on `suspected_inflated`.
- "GC scrape known-broken" was overstated (it's trust-gated, not
  dead); the Scryfall `game_changer` bulk-field migration is still the
  right move, with field-absent → "unknown, fall back", never "not a
  GC".
- Corpus-scaled ROLE_TARGETS: **not promoted** — the repo's own
  backlog gates corpus-norms steering behind an unrun A/B; building on
  it now would invert the project's own discipline.

### Joint round-2 top-5 roadmap (player value per engineering hour)

1. **Statistical-honesty batch** (S): significance-gate meta_test's
   "references BEAT your deck" copy; decisive-basis tooltips
   (±0.22/±0.11/±0.07); align the 8-vs-20 decisive floors; fix the
   26-14→27-13 docstring; NULL margin when decisive==0 plus the legacy
   web-row backfill (fenced at id ≥ 314).
2. **Web-layer integrity batch** (S): cache the Forge supported-card
   index (kills the per-click 1-2s corpus rescan) + `Name=` restamp
   and atomic write on `PUT /api/deck_text` (closes the last
   win-misattribution hole; consider a bracket-estimate check on web
   edits to protect pool tags).
3. **Bracket-floor correctness pass** (S-M): reanimation-aware combo
   speed costing + chainability calibration over the on-disk B3/B4
   pools, splitting enablers by repeatability; demote one-shot rebuys
   to a weight if the calibration shows non-trivial false floors.
4. **Archetype v2 from oracle signals** (M): combo := game-ending
   combos + tutor density; control := interaction report; stax := new
   ~10-pattern oracle table; aggro := tribal + curve. Un-no-ops pool
   diversity and the estimator's archetype weights; fold in Wilson
   ranking + acting on `suspected_inflated` in the same pool_curator
   pass. Cache-only, no LLM.
5. **Role-classifier evergreen gaps** (S-M): the six confirmed misses
   (restricted counterspells, impulse draw, fight/bite, edicts,
   X-wipes, ward) with verbatim-oracle fixtures and one calibration
   pass over the library.

Below the line: GC bulk-field migration (next `game_changers` touch),
auto-propose polish (no-op guard + padding in manifest — with the
bandit-integrity note), politics guard (real gap, opt-in value),
[REF] policy call (coordinator decision), corpus-scaled targets
(blocked on the repo's own pending A/B).

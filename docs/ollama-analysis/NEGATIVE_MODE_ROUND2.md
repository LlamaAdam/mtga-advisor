# Negative-mode review, round 2 (2026-08-20)

Target: branch `claude/ollama-code-analysis-ak77i1` @ `b384b1c`, as of
2026-08-20 — i.e. the branch *after* the 2026-08-14/16/17 fix batch
landed.

Method: the same three-agent pass as round 1, run fresh. One agent
explained the program end to end from source; a second, hostile agent
attacked the explanation with source verification and executed code
where a number was in dispute; a third agent cross-examined every
attack from the defense side, re-reading each claim in context,
tracing call graphs, and re-running the arithmetic.

Exclusion rule: every prior finding was treated as known and
off-limits. `AI_REVIEW_FINDINGS`, `NEGATIVE_MODE_REPORT` (P01–P23),
`DECISIONS_FOR_REVIEW` and `LLM_DECK_JUDGE_SCOPE` were read first, and
nothing already filed there is re-filed here. Round 2 therefore
targets two things only: what round 1 missed, and whether the fixes
shipped since round 1 actually hold.

**Headline tally: 25 problems raised → 20 CONFIRMED · 4 PARTIAL ·
0 REFUTED.** Severity after cross-examination: **critical 0 · major 7
· minor 18.**

The critic was unusually accurate this round — no claim collapsed
under a misread call graph. What the cross-examination did find was
wrong arithmetic and missed mitigations inside otherwise-valid claims:
three of the four partials change the *fix*, and the flagship
statistical claim (P21) had its numbers wrong in both directions.
Where the cross-examiner corrected the critic, this report states the
cross-examiner's version and nothing else.

Problems marked **[USER-DECISION]** are product/policy calls, collected
in `DECISIONS_FOR_REVIEW.md` under "Round-2 decisions"; the rest are
engineering fixes.

---

## The reconciled top 3

As the cross-examiner ranked them after correction — note that these
are pairings, not single findings:

1. **P09 + P10 — the politics guard fails its own primary mission,
   twice.** (a) The unattended curation stage (`auto_propose`) has no
   politics post-filter on cuts. The candidate pool it is fed *is*
   filtered and the prompt constrains Claude to that pool, so this is
   an enforcement gap rather than an open door — but the repo's own
   safety-net standard (nets exist for adds precisely because Claude
   deviates) is unmet for the one cut class decision C2 exists to
   protect, and the changelog's "all three cut paths" sentence is
   false as written. (b) Even where the guard does run, its tax
   pattern misses Smothering Tithe — proven by execution — along with
   the entire "may pay … If the player doesn't" punisher template and
   the initiative. Both are small, safe fixes.
2. **P19 + P20 — the era system leaks at both consumer ends.**
   `commander-history`'s win-rate trajectory baselines on era-1/2
   rows; `/api/verdict_breakdown` pools all-era verdicts; and the web
   save default writes any-lead-at-20-decisive labels into
   era-4-stamped, FP-013-eligible rows. "Rates AND verdicts pool
   cleanly" currently holds only as long as nobody uses the report CLI
   or accepts a web default.
3. **P01 + P02 — `--strategy bandit` escaped the branch's
   disciplines.** It lacks the no-op guard both sibling paths got (and
   its cut-cycling arm construction makes no-op pulls routine after
   any accepted pull; ~1.2% of those no-op sims still reach 'kept'),
   and it writes zero knowledge-log rows while permanently advancing
   decks on disk — no snapshot, no lineage, no revert path, invisible
   to FP-013, with CLI copy claiming the opposite.

Ranked fourth and worth reading alongside them: **P21 (as corrected)
— the replication gate's honest number is the wrong one.**
True-positive throughput at shipped power is ~1.3% per 10-round
overnight run (worse than the critic claimed); the
composition-of-advances argument survives only under a corrected
threshold — advances are majority-noise iff the true-hit prior is
below ~10%, not 17% — which is plausible given FP-002 but no longer
arithmetic-certain. The docstring sells 1-in-1,600 without stating
either consequence.

---

## Full reconciled problem list

Severity is as corrected by cross-examination. Where the critic's
scope or numbers were wrong, the claim below is the corrected one.

| # | Sev | Verdict | Area | Problem |
|---|-----|---------|------|---------|
| R2-P01 | maj | CONFIRMED | bug (fix hole) | Bandit evaluator has no no-op guard; base-vs-identical-copy sims |
| R2-P02 | maj | CONFIRMED | data/premise | `--strategy bandit` writes zero knowledge_log rows |
| R2-P03 | min | CONFIRMED | stats | Replication discards run 2's measurement from the arm mean |
| R2-P04 | min | CONFIRMED | data honesty | Replication note overwrites run 1's note; run 2 unstructured |
| R2-P05 | min | CONFIRMED | semantics | Failed-to-run confirmation rewrites a completed row to 'pending' |
| R2-P06 | min | CONFIRMED | stats/schema | `--sim-margin` changes 'neutral' semantics; margin unrecorded |
| R2-P07 | min | CONFIRMED | latent bug | `accept_threshold=args.sim_margin` mixes units with [-1,1] rewards |
| R2-P08 | min | PARTIAL | stats | Skip-retirement is deliberate, but its stated premise is false |
| R2-P09 | maj | CONFIRMED | bug (fix hole) | No politics enforcement net on the auto-curate curator's cuts |
| R2-P10 | maj | CONFIRMED | bug (data) | Tax pattern misses Smothering Tithe and the punisher template |
| R2-P11 | min | CONFIRMED | domain gap | Protection role misses phasing and shield counters |
| R2-P12 | min | CONFIRMED | arch | Archetype v2 cold-cache fallback degrades silently to v1 behavior |
| R2-P13 | min | CONFIRMED | stats/data | Era-3/4 boundary is a hard date cut where others got NULL |
| R2-P14 | min | PARTIAL | stats honesty | "Would promote them" overstates; printed count is an upper bound |
| R2-P15 | min | CONFIRMED | concurrency | Stale-lock reclaim TOCTOU + unverified `release()` unlink |
| R2-P16 | min | CONFIRMED | ux | `bracket_tag_unverified` computed, tested, returned, never rendered |
| R2-P17 | min | PARTIAL | process/docs | `local_model.main` has no console script (but `python -m` is documented) |
| R2-P18 | min | CONFIRMED | tests | Archidekt adapter has no MDFC/split-card fixture |
| R2-P19 | maj | CONFIRMED | stats honesty | History trajectory + verdict breakdown pool across all four eras |
| R2-P20 | maj | CONFIRMED | stats honesty | Web save default still implements the retired era-3 verdict rule |
| R2-P21 | maj | PARTIAL | premise | Replication gate collapses true-positive throughput; numbers corrected |
| R2-P22 | min | CONFIRMED | ux | `[REF]` filler exclusion can zero the pool; skip message names no remedy |
| R2-P23 | min | CONFIRMED | desktop | `wait_until_up`'s result discarded; docstring wrong; lockfile truncates |
| R2-P24 | min | CONFIRMED | web hygiene | Five `innerHTML` template literals contradict the no-innerHTML rule |
| R2-P25 | min | CONFIRMED | docs | Three comment/doc drifts introduced by the fix batch |

### Majors

**[R2-P01] major · CONFIRMED — the no-op-sim fix missed the third
site.**
Claim: `--strategy bandit`'s evaluator sims base-vs-identical-copy
whenever the swap pair drops for legality, spending a full 45-game
Forge budget to measure base-vs-base noise and booking it as that
arm's real reward.
Evidence: `improve.py:678-713` — `evaluate()` builds the Proposal,
calls `apply_proposal_to_deck`, and goes straight to
`run_ab_simulation` with no check of `proposal.applied_adds` /
`applied_cuts`. The cross-exam traced the drop path:
`apply_proposal_to_deck` (`proposer.py:952-1153`) drops the whole pair
on an unmatched cut, an all-dropped proposal still clears the
mainboard hard guard (99 == 99), and it writes a content-identical
(`Name=`-restamped) copy without raising — so the `apply_failed` skip
never fires. Both sibling paths *do* guard:
`improve_search.py:567-574` and `iteration_loop.py:199-202`. Arm
construction makes this routine, not rare: `improve.py:599` cycles
cuts (`cut = cuts[i % len(cuts)]`), so once one arm's cut is accepted
every sibling sharing that cut is a guaranteed no-op. Replication is
default-OFF on this path (`resolve_replicate_default`,
`improve.py:823-826`).
Corrected number: a base-vs-identical-copy sim reaches 'kept' about
**1.2%** of the time, not ~5% — the exact two-sided binomial over the
decisive-count distribution at 45 games gives `P(kept | null) = 0.012`.
The 0.05 alpha is a loose bound; the exact test plus the decisive gate
is far more conservative. Also "byte-identical" → content-identical.
Fix: after apply, `PullOutcome.skip("swap_dropped_by_legality")` when
both applied lists are empty — the same three lines `improve_search`
already has. Test: an arm whose cut card is absent.

**[R2-P02] major · CONFIRMED — the bandit strategy is off-log
entirely.**
Claim: `--strategy bandit` runs full 45-game A/B sims and permanently
advances the base deck while writing zero knowledge_log rows — no
iteration row, no snapshot, no lineage, no revert path, invisible to
FP-013.
Evidence: in `improve.py`, `update_iteration_sim` appears only in
`_default_replicate_fn` (`366-368`) and the `--health` import
(`1037`); `_make_swap_evaluator` and `_run_bandit_strategy`
(`633-797`) never touch knowledge_log, and `bandit.py` is pure by
design. Greedy rounds get rows only because they subprocess
`auto_curate_main` (comment at `improve.py:214`); the bandit path
calls `advise()` + `apply_proposal_to_deck` + `run_ab_simulation`
directly. Deck files still advance on disk (`state["deck"] =
candidate`, written at `proposer.py:1152`). The `--strategy` help
(`improve.py:957-959`) discloses none of this, and the counter comment
"Every improve run grows this number" (`improve.py:1033-1035`) is
flatly false for this strategy — as is the README's "every cycle is
one row in knowledge_log.sqlite" for one of the three shipped
strategies.
Needs: **[USER-DECISION]** — record an iteration row per accepted pull
(manifest = the single swap, snapshot = candidate text), or loudly
document `--strategy bandit` as off-log. The choice affects schema
semantics and FP-013 counting.

**[R2-P09] major · CONFIRMED, with a scope correction — the politics
guard has no enforcement net on the unattended curator.**
Claim (corrected scope): the auto-curate curation stage has no
politics post-filter on cuts. This is an *enforcement gap*, not a
total bypass — the critic's "bypasses all politics filtering"
overstates it.
Evidence: the cross-exam traced all four cut paths. The heuristic
loop and `card_score` rails are covered in-path; the orchestrator is
covered — `improvement_advisor.py:934-938` runs `recs,
skipped_for_politics = _filter_for_politics(recs, deck_text)` over
every source's recommendations, disclosed at `:1047`. The fourth path,
`auto_propose` (`proposer.py:813-904`) — the one
`commander-auto-curate` / `commander-improve` actually traverse —
post-filters `raw_cuts` for protection only (`:884-891`), while adds
get bracket, color-identity and ownership nets; `grep -rn politic
proposer.py _proposer_filters.py _proposer_cli.py iteration_loop.py`
returns zero hits, and `apply_proposal_to_deck`'s defense-in-depth
(`:1037-1046`) re-checks `Protect=` only.
What the critic under-stated: the candidate cuts fed to the curator
*are* politics-filtered (they come from `advise()`'s post-filter
output), and the curator system prompt (`proposer.py:475-517`)
instructs it to "pick a small, applicable subset of those
candidates". So the exposure is Claude-deviation-only. But the repo
built the color-identity net because Claude "occasionally hallucinates
off-color picks" (`:831-836`) and the ownership net because "Claude
can propose cards outside the candidate pool" (`:869-871`) — by its
own standard, the missing net is a real hole on exactly the loop C2
was written for.
Fix: in `auto_propose`, filter `raw_cuts` through the politics
predicate when the deck's guard is on, into a `dropped_for_politics`
bucket (mirror the protection filter at `proposer.py:884-891`); and
correct `docs/CHANGELOG.md:37-40`, whose "the orchestrator (the only
path Claude's … cuts traverse)" is false for the curation-stage Claude
call.

**[R2-P10] major · CONFIRMED — the tax pattern misses the card its own
comment names.**
Claim: `politics_tags` does not tag Smothering Tithe, because the
modern punisher-tax template ("that player may pay {2}. If the player
doesn't, …") contains no "unless".
Evidence: `staples.py:1048` — the only tax pattern is `\bunless that
player pays\b` — while the comment two lines up (`:1041-1042`) names
Smothering Tithe as a covered example. Executed:
`politics_tags(<Smothering Tithe text>) -> ()`, against
`politics_tags(<Rhystic Study>) -> ('tax',)` and
`politics_tags(<Mystic Remora>) -> ('tax',)`. No Smothering Tithe
politics fixture exists (`grep Smothering tests/` hits only
game-changer tests), so the repo's real-oracle fixture discipline —
adopted after synthetic fixtures hid nine bugs — was not applied to
the guard's flagship example. The whole "may pay … If the player
doesn't" template is unshielded, and the initiative has zero patterns
(same sim-invisible class as monarch).
Fix: add a second tax pattern for the punisher template, e.g.
`\bthat player may pay\b[^.]{0,60}?\bif (?:the player|they)
(?:doesn't|don't)\b`, pinned with real Smothering Tithe oracle text in
the fixture module; decide cover-or-scope-out for the initiative in
the same commit's comment.

**[R2-P19] major · CONFIRMED — the era system's two user-visible
pooled surfaces were never routed through it.**
Claim: `commander-history`'s win-rate trajectory and the web verdict
breakdown both pool across all four measurement eras — the exact
analysis the schema docstring forbids.
Evidence: `grep measurement_era src/commander_builder/web/
src/commander_builder/report.py` → **zero hits**.
`report.py:174-185` takes the first non-null `win_rate_new` in the
full history as the trajectory baseline — possibly era 1 ("archive
only, never training data", `knowledge_log.py:170-175`) or era 2
("rates are not comparable", `:177-184`) — subtracts it from the
latest rate, and headlines the delta.
`verdict_breakdown_for_deck` (`knowledge_log.py:930-964`) counts every
row's verdict without so much as SELECTing the era column, and
`/api/verdict_breakdown` (`routes_dashboard.py:706-707`) serves it.
Both violate `knowledge_log.py:37` ("Any pooled analysis must bucket
rows by measurement_era").
Fix: era-bucket `report.py`'s trajectory (baseline from era ≥ 3 rows
only, since era-3 rates pool cleanly) and add era annotation/split to
`verdict_breakdown_for_deck` plus its route.

**[R2-P20] major · CONFIRMED — the web save default still writes the
retired rule.**
Claim: the web save-iteration verdict default is any-lead-at-20-
decisive, with no significance test, and those rows are stamped era 4
and are FP-013-eligible.
Evidence: `app.js:876-881` — `defaultVerdict = _decisive < 20 ?
"inconclusive" : body.winner === "new" ? "kept" : …`; and
`ComparisonReport.winner` (`compare_versions.py:190-191`) is any-lead
("Reports 'tie' on equal wins"). So a 21-20 over 41 decisive
(p ≈ 1.0) pre-selects "Kept (apply changes)". The CLI path requires
`binomial_two_sided_p(wins_b, decisive) < alpha`
(`_proposer_sim.py:153`). The server stores the radio verbatim — the
whitelist at `routes_sim.py:818-827` is the only validation — and
`Iteration.to_row` (`knowledge_log.py:407-415`) stamps the live write
with the current era (4). Row shape (manifest + decided verdict +
≥40-game report) qualifies for FP-013. The user can override, but a
default is the label most saves get: this is the one remaining writer
on the old rule, and the era-4 pooling claim quietly depends on the
web user never accepting a default.
Fix: have the server return a `suggested_verdict` computed with
`analyst.binomial_two_sided_p` (it already imports analyst) and have
`app.js` default the radio to it. Keep the user override.

**[R2-P21] major · PARTIAL — thesis holds, every quoted number was
wrong.**
Claim (corrected): the replication gate (decision A2) cuts the
false-advance rate as advertised but does not fix P02's actual problem
— most advances are still noise — and it collapses true-positive
throughput to the point where the default unattended loop is
structurally inert at shipped power.
Evidence: `improve.py:17-31` states the false-positive half honestly
(kept-at-null ≈ 1/40 per run → 1/1,600 replicated) and states neither
consequence. The cross-exam re-ran the exact computation (decisive ~
Binomial(45, 0.5), 20-decisive gate, exact two-sided binomial at
α = 0.05, margin 1, true swap = 55% decisive win rate):

```
P(kept | true 55% swap, one 45-game run)  = 0.0365   (critic said 5.5%)
P(advance | replication)                  = 0.00133  (critic: ~0.3%)
P(>=1 true advance in 10 rounds)          = 0.0133   (critic: ~3%)
P(kept | null) = 0.012  ->  replicated 0.000145
LR single = 3.0;  LR replicated = 9.2     (critic: 2.2 -> 4.8)
```

So the structural-inertness half is confirmed and is roughly **2×
worse** than the critic said: a 10-round overnight run advances a
genuine +5pp swap with ~1.3% probability, at 45 pod games per round
plus 2× on any gate trigger. The "majority of advances are still false
positives" half is **weaker** than claimed: at LR ≈ 9.2 the prior
true-hit rate needed for majority-true advances is ~10%, not ~17%.
Given FP-002 measured curation net-neutral, a sub-10% prior remains
plausible, so the conclusion likely survives — but the stated Bayesian
numbers should not be quoted. In fairness to the defense, the
docstring's "1 in 40" is itself the loose alpha bound; the exact
per-run null-kept rate is ~1/83.
Needs: **[USER-DECISION]** — no fix exists inside the gate. This is
A1's repositioning applied to A2: state true-positive throughput next
to the false-positive rate, and decide whether the unattended loop
should keep defaulting ON as if replication makes its advances
trustworthy.

### Minors

**[R2-P03] minor · CONFIRMED — replication discards the unbiased
draw.** On the bandit path, replication keeps only run 1's
measurement in the arm mean. `improve.py:715-738`: on disagreement,
`PullOutcome(reward=reward, …)` books run 1's reward; on confirmation
the return at `:738` also carries only run 1's. Run 1 is the
selection-biased draw — it triggered the gate by being extreme — so
UCB1/Thompson keeps favoring an arm whose only recorded evidence is
the split a second sim failed to reproduce. The rationale at
`:662-666` ("folding a second sim into the mean would silently
double-weight exactly the arms that reached the gate") is a documented
deliberate choice, but backwards statistically: run 2 is the unbiased
draw, and averaging both reduces winner's-curse inflation rather than
compounding it. Non-default path (`--replicate` on bandit).
Needs: **[USER-DECISION]** — the owner wrote the current rationale
deliberately; overriding it is a judgment call.

**[R2-P04] minor · CONFIRMED — the confirming sim is invisible as
data.** `knowledge_log.update_iteration_sim` (`knowledge_log.py:
620-622`) does `verdict_notes = ?` (overwrite) whenever notes is not
None, and `_default_replicate_fn` passes a fresh string
(`improve.py:352-363, 368-376`), destroying run 1's "(N games,
margin=M)" note. The docstring at `improve.py:313-314` says notes
"gain a ``replication_confirmed`` line" — append semantics the code
does not have. Run 1's split survives only inside sim_report JSON;
run 2's games are structured nowhere, so total Forge games backing a
replicated 'kept' are 2× what sim_report says.
Fix: read-modify-append the note (or add append semantics to
`update_iteration_sim`); persist run 2's split structurally, e.g.
`sim_report["replication"]`. Fix the docstring either way.

**[R2-P05] minor · CONFIRMED — a failed-to-RUN confirmation makes a
completed row self-contradictory.** `improve.py:337-342` produces
`Replication(verdict="pending", …)` when the confirm sim cannot run,
written over a row whose sim_report says 'done' with win rates. The
vocabulary defines 'pending' as "the sim didn't complete"
(`_proposer_sim.py:123`). Any consumer that re-derives state from
verdict alone misreads it, and a re-scoring pass over sim_reports
would resurrect 'kept' on a row the gate refused. (Mitigation: the
note text does explain itself to a human.)
Needs: **[USER-DECISION]** — label policy.

**[R2-P06] minor · CONFIRMED — a raised `--sim-margin` changes
'neutral' semantics inside era 4, unrecorded.** `_verdict_from_ab`
(`_proposer_sim.py:151-152`) returns 'neutral' whenever
|delta| < margin, *before* the significance test, so at
`--sim-margin 15` a significant 27-13 is labeled 'neutral' — a
different quantity from a margin-1 'neutral'. The margin used is
recorded only in free text ("(N games, margin=M)",
`_proposer_sim.py:436-439`); sim_report is `ab_result.to_dict()` with
no verdict params. All such rows still stamp era 4 and pool as if
label semantics were uniform. Conditional on the operator raising the
flag.
Fix: store the margin/alpha/min_decisive used inside sim_report at
write time.

**[R2-P07] minor · CONFIRMED — live wrong-units plumbing on a CLI
flag.** `improve.py:785-788` passes `accept_threshold=args.sim_margin`
(raw-margin units, default 1) while `bandit._coerce_outcome`
(`bandit.py:216`) accepts a bare-float reward iff
`reward >= accept_threshold` on the normalized [-1,1] scale — only a
perfect sweep can pass, and any raised `--sim-margin` makes acceptance
impossible. The real evaluator returns `PullOutcome`, so this fires
only on back-compat/test float evaluators, and the restriction is
documented at `improve.py:781-784` — but it is a CLI flag wired in the
wrong units, the exact error class the module lectures about.
Fix: stop plumbing `args.sim_margin` into `accept_threshold`; pass a
normalized constant or drop the parameter.

**[R2-P08] minor · PARTIAL — restated: deliberate policy, false
premise.** Behavior confirmed: `bandit.py:393`
(`eligible = [a for a in arms if a.skips == 0]`) retires an arm
forever on one skip, and the evaluator's skip reasons include
transient classes — `sim_failed` (a JVM crash, retried nowhere) and
`zero_decisive_games` (sampling luck) — at `improve.py:703-710`. But
this is an explicitly argued design choice (`bandit.py:370-376`,
citing the same choice in `improve_search.SearchArm`), not an
oversight. The genuine kernel is narrower than the critic's "bug":
*the retirement policy is deliberate, but its stated premise
("failures … are typically structural") is false for two of the four
skip classes; differentiating them is a small improvement, not a fix
of broken code.*
Needs: **[USER-DECISION]** — changing it alters run behavior.

**[R2-P11] minor · CONFIRMED — protection role misses two evergreen
families.** `staples.py:812-836` has exactly hexproof /
indestructible / protection-from / shroud / can't-be-target /
granted-ward; `grep -i "phas\|shield counter" staples.py` finds no
pattern-table hits. Decks leaning on phasing (Slip Out the Back,
Teferi's Time Twist, Guardian of Faith) or shield counters read as
protection-deficient against the ROLE_TARGETS quota and get offered
redundant Swiftfoot-Boots-class adds.
Fix: `phases? out` + `put (?:a|N)? shield counter` patterns with
real-oracle fixtures.

**[R2-P12] minor · CONFIRMED — archetype v2 degrades silently to the
v1 no-op.** `derive_archetype_signals` computes `oracle_available`
(`archetype.py:666, 687`) but `classify` (`:760-795`) returns only the
label, and the flag's only consumer is `local_model`. On a cold
snapshot cache (fresh machine, CI, misconfigured `MTG_CARDS_DIR`) the
stax/control/aggro rungs abstain, most decks fall through the name
scan to "midrange", and `pool_curator`'s archetype-diversity check
returns to the WARN-and-ship-every-time state v2 claims to have
fixed. No caller can distinguish measured midrange from blind
midrange and nothing prints a degradation notice — against the repo's
own no-silent-failures principle.
Fix: one stderr warning when rung 2 abstained for coverage, or expose
`oracle_available` so pool_curator can abstain instead of thrash.

**[R2-P13] minor · CONFIRMED — the era-3/4 boundary is handled
inconsistently.** `knowledge_log.py:212` sets `_SIGNIFICANCE_START =
"2026-08-14"` and `measurement_era_for` (`:255-256`) grants era 4 on
the bare date, while the same function NULLs the 2026-05-21/22 session
(`:263-268`) and the 2026-07-19 window (`:259-260`) for exactly the
mid-session-mix reason. The 08-14 fixes were commits, not midnight
cutovers, so rows written that day before the commit are stamped era 4
and admitted to the FP-013 training floor (`FP013_MIN_TRAINING_ERA =
4`) with margin-threshold labels. Impact is bounded to rows the owner
wrote that day — possibly zero, unverifiable from the repo.
Needs: **[USER-DECISION]** — reclassifying relabels live owner data.

**[R2-P14] minor · PARTIAL — restated: the copy overstates, but less
than the critic said.** The copy claims are verified:
`knowledge_log.py:837-838` ("Re-scoring … promotes them; they are a
backlog, not a loss"), `improve.py:1058-1066` ("would promote them"),
and no re-scoring tool exists. Two corrections to the critic: (1) the
gate counts kept/reverted/**neutral** (`knowledge_log.py:849`), so
era-3 rows that re-score to 'neutral' at ≥20 decisive *do* promote —
only sub-20-decisive re-scores drop out, which the critic's own aside
conceded but the "~44% not promotable" headline over-attributes; and
(2) the 44% figure holds only at exactly 40 total games, while the
filter is ≥40, so larger runs fall short less often. Correct
statement: *"would promote them" should read "most would survive
re-scoring, some (those under 20 decisive) would not; the printed
count is an upper bound, and no re-scorer exists yet."*
Fix: have `fp013_gate_progress` re-score each era-3 sim_report it
already loads and report the honest count; soften both copy sites.

**[R2-P15] minor · CONFIRMED — stale-lock reclaim has a TOCTOU and
`release()` unlinks blind.** `forge_batch.py:746-766`: reclaim is stat
→ unconditional `os.unlink(lock_path)` → O_EXCL create. The
interleaving A:stat, B:stat, A:unlink, A:create, B:unlink (deleting
A's *fresh* lock), B:create leaves both holding "the" lock, so the
docstring's "exactly one of them wins" (`:730-731`) is false.
Separately, `ProfileLock.release` (`:638-652`) unlinks by path with no
payload/pid ownership check: a run that outlives the 6h stale window
(reachable at `--sim-games` ≳ 130 serial, or a wedged JVM) has its
lock reclaimed, keeps running, and its finally-release deletes the
reclaimer's live lock, admitting a third run. Both windows are narrow
— but they are the crash-recovery scenario the mechanism exists for.
Fix: reclaim via rename-to-unique-name (atomic arbitration) instead of
unlink; have `release()` verify its own payload before unlinking.

**[R2-P16] minor · CONFIRMED — the bracket-tag mitigation is
server-side only.** `routes_decks.py:332-353` computes and returns
`bracket_tag_unverified` and `tests/test_web_app.py` pins it five
times, but `grep -rn bracket_tag_unverified web/static/*.js` returns
zero hits; the save handler (`app.js:632-655`) reads only
`body.error`. The docstring's "the UI gets a hint to offer
re-validation" (`routes_decks.py:281-285`) describes a UI that does
not exist, so the hand-edited-B4-under-a-`[B3]`-filename
pool-poisoning path is as invisible to the user as before the fix.
Fix: render the flag in the save-status line.

**[R2-P17] minor · PARTIAL — restated: packaging gap only.**
`pyproject.toml` `[project.scripts]` has 27 entries and none for
`local_model`, though `local_model.py:980` defines a full argparse CLI
including the agreement harness the env flag is gated on, and the
repo's own checklist (`architecture.md:583-594`) ends with "register
the console script". But the critic's "no documented invocation" is
**false**: `local_model.py` documents `python -m
commander_builder.local_model` in its module docstring (`:67`), its
CLI section header (`:954`), and its `argparse prog=` (`:995`) — a
deliberate-looking choice for an off-by-default, unmeasured tier.
Fix: register `commander-local-model =
"commander_builder.local_model:main"` and add one docs-level usage
line.

**[R2-P18] minor · CONFIRMED — the Archidekt lane has no multi-face
fixture.** `archidekt_client._entry_name` (`:184-186`) trusts
`card.oracleCard.name` verbatim, and `grep '//'
tests/test_archidekt_client.py` finds only URLs — no MDFC or split
card among its two `oracleCard` fixtures. Name parity with the
Moxfield lane (months of empirical validation) is therefore unpinned
on the one drift — front-face vs "A // B" — that silently produces
.dck files the sim-coverage probe and Forge resolve differently.
Nobody has shown the drift exists, but by the repo's own real-oracle
discipline the gap is real.
Fix: pin one real MDFC entry from a live probe. Do not synthesize it
— synthesizing is the failure mode.

**[R2-P22] minor · CONFIRMED — the `[REF]` exclusion can zero the
filler pool with no explanation.** `_proposer_sim.py:253-256` now
excludes `[USER]`/`[CONTROL]`/`[PREMADE]`/`[REF]`; a deck directory
populated only by imports and meta-test references — a realistic
non-harvest setup — yields "found 0 … Sim skipped" (`:345-349`) where
the pre-2026-08-17 behavior ran the sim. The message names the count
but not the exclusion rule, so an operator staring at a directory full
of .dck files gets no path forward.
Fix: when candidates existed but were all prefix-excluded, say so and
name the remedy (`commander-curate --harvest`, or `--sim-fillers`).

**[R2-P23] minor · CONFIRMED — desktop launch ignores its own
readiness check.** `desktop.py:337` calls `wait_until_up(host, port)`
and discards the bool with no branch, so on a slow or failed server
start the window opens on a refused page — the exact case the helper
exists to prevent. The launch docstring (`:298-299`) says the icon is
"passed to ``webview.create_window``" while the code (`:351-356`)
passes it to `webview.start()`, with a comment 40 lines below noting
that `create_window` raises TypeError. Cosmetically,
`_acquire_instance_lock` opens the lock file `"w+b"`/`"w"`
(`:133, :141`), truncating away the first instance's pid diagnostics
before the lock attempt fails.
Fix: branch on `wait_until_up`; fix the docstring; open the instance
lock non-truncating.

**[R2-P24] minor · CONFIRMED — five `innerHTML` sites contradict the
stated discipline.** `app.js:532, 3206, 3326, 3518, 3559` all
interpolate `e.message` into template literals, against `app.js:58-61`
("server data flows through textContent"). Current exploitability is
~nil given fetchJSON's error shape (`app.js:50`), but the repo treated
DNS-rebinding as real enough to land the D2 host gate, and these are
the only sites where a future error-shape change — e.g. surfacing
`body.error`, which contains card names — becomes markup.
Fix: five `textContent`/`el()` conversions.

**[R2-P25] minor · CONFIRMED — three doc drifts from the fix batch.**
(a) `MEASUREMENT_ERAS[2]` says era 2 starts 2026-05-22
(`knowledge_log.py:178`) while date-only classification grants era 2
from 05-23 (`:261-262`; 05-22 needs id ≥ 314). (b)
`local_model.py:205-208` says "the three the classifier produces
without a pattern table" then parenthesizes two (threat, other) — the
other two are called extended buckets. (c) `improve.py:313-314`
"notes gain a line" vs the overwrite semantics in R2-P04.
Fix: three comment/doc corrections.

---

## What genuinely survived criticism

The critic's survived-list was itself audited by the cross-examiner,
who spot-checked four entries in full; nothing on it was found broken.

- **`_verdict_from_ab`** — read end to end
  (`_proposer_sim.py:105-155`): pending gate, decisive gate, the
  margin pre-filter (a genuine no-op at margin 1) and the exact
  binomial via `analyst.binomial_two_sided_p` are all correct as
  coded. The residual issues are the label semantics of a *raised*
  margin and the unrecorded parameter (R2-P06).
- **Era classification core** (`measurement_era_for`,
  `knowledge_log.py:215-269`) — date-decides / id-tiebreaks is right,
  the three NULL-not-guess windows are right, `Iteration.to_row`
  derives era from the row's own timestamp so imports and backdates
  classify honestly, and export/import round-trips the stamp with a
  NULL fail-safe. The leaks are at the consumers (R2-P19) and one
  boundary (R2-P13).
- **Profile-lock lifecycle** — every acquire is paired with a
  finally-release, including the mid-construction failure path
  (`compare_versions.py:1090-1100`), and the no-op-lock degrade for
  missing or read-only dirs round-trips cleanly. Residual: the
  stale-reclaim TOCTOU (R2-P15).
- **The politics guard's opt-out parsing and fail-safe direction** —
  `POLITICS_GUARD_META_KEY` plus a six-value `_POLITICS_GUARD_OFF_
  VALUES` frozenset, positive-switch rationale documented; the
  vote/devotion boundary, the "unless its controller pays" exclusion
  and deterrent's sentence-bounded window are all pinned by tests. The
  misses are template coverage (R2-P10), not mechanism.
- **The deck_text PUT hardening** (`c6714ce`) — the restamp choice is
  argued correctly, `_atomic_write_text` does temp-in-same-dir + fsync
  + `os.replace` + mode preservation, and the `[Main]` shape check
  closes the garbage-paste hole. Only the unused hint is dead
  (R2-P16).
- **The corpus-loader memoization (M1)** — the signature tracks the
  right sources, the in-lock `warm()` eliminates the mid-request scan,
  eviction semantics (no `close()` on a shared instance) are correctly
  reasoned, and a cold corpus falls back to exactly the old behavior.
- **The reanimation-aware combo pricing** — patterns are
  clause-bounded, the `min()` direction is strictly conservative,
  "permanent card" templates (Sun Titan) correctly don't match,
  unknown types reprice toward the strict direction, and Victimize is
  hard-tagged where the regex can't reach.
- **The chain-enabler repeatability split** — the frozensets implement
  the earlier crossfire's correction exactly (Mystic
  Sanctuary/Reiterate/mass-rebuy floor; Twincast/Eternal Witness/bare
  ETB creatures one-shot, with the blink-engine caveat stated).
- **`local_model`'s structure** — HTTPError-before-URLError at both
  sites, two failure classes, imported taxonomies verified complete
  against `classify_role_extended`'s actual range, temperature-0 with
  a 30s timeout, and agreement-not-accuracy framing with
  None-not-0.0 rates. Residuals are packaging and docs (R2-P17,
  R2-P25b).
- **The Archidekt lane's refusal semantics** — 404 never falls back,
  no id translation, namespaced provenance, `MOXFIELD_ONLY_NOTE` — all
  as documented.
- **`export.py`** — natural-key dedupe, id remapping, parent remapping
  to NULL over dangling FKs.
- **meta_test significance gating, the analyst decisive convention,
  the web signed margin and NULL-margin-at-zero-decisive, manifest
  padding, `_advisor_manabase` dedup** — all round-1 and round-2 fixes
  verified still in place; 294 tests in the touched files pass.

---

## Corrections ledger

Round 2's critic was accurate on substance and repeatedly wrong on
detail. Future rounds should inherit these corrections rather than
re-deriving them:

1. **P21's arithmetic was wrong in every quoted figure.** At 45 games
   with a 20-decisive gate and an exact two-sided test at α = 0.05:
   `P(kept | true +5pp)` = 3.65% per run (critic said 5.5%);
   replicated advance 0.13% (not 0.3%); ≥1 advance in 10 rounds 1.3%
   (not 3%); likelihood ratio rises 3.0 → 9.2 (not 2.2 → 4.8);
   majority-noise threshold ≈ 10% prior (not 17%). Direction
   unchanged, every number off — and off in both directions, which is
   why the rerun mattered.
2. **P01's no-op kept rate is ~1.2%, not ~5%.** The exact test at the
   null, integrated over the decisive-count distribution, is far more
   conservative than the 0.05 alpha bound. Also: the produced copy is
   *content*-identical, not byte-identical (`Name=` is restamped and
   the filename version-bumped).
3. **P09 is an enforcement gap, not a total bypass.** The candidate
   cut pool the curator is prompted from *is* politics-filtered, and
   the prompt constrains Claude to that pool. What is missing is the
   post-response enforcement net. Severity and fix are unchanged;
   the wording is not.
4. **P17's "no documented invocation" is false.** `local_model.py`
   documents the `python -m commander_builder.local_model` form in
   three places and even sets `prog=` to it. The real gap is
   console-script registration plus a docs-level mention.
5. **P14's "not promotable" over-attributes.** Re-scored era-3 rows
   that land on 'neutral' still count toward the FP-013 gate
   (kept/reverted/neutral all qualify); only sub-20-decisive re-scores
   are lost, and the 44% shortfall applies only at exactly the 40-game
   floor.
6. **The survived-list and the explainer corrections checked out
   clean.** All seven explainer corrections were verified (27 console
   scripts, not 30; the changelog's cut-path claim; replace-not-append
   notes; the era-2 boundary; `commander-improve`'s 45-game default vs
   auto-curate's 40 floor; the bandit log hole; ROLE_TAXONOMY's
   hand-appended snapshot). Future rounds can treat both lists as
   reliable.

---

## On the exercise itself

Round 2 found **zero critical problems**, against round 1's crop of
three criticals and five majors in the top five. That is a real
signal, and it should be read narrowly.

**What it says.** The codebase hardened. The fixes that landed between
2026-08-14 and 2026-08-17 are, mechanism for mechanism, correct: the
era classifier, the verdict math, the politics guard's opt-out logic,
the profile-lock lifecycle, the atomic deck write, the corpus
memoization all survived direct attack. Twelve of the survived-list
entries are code written in the last week. A hostile pass that has to
reach for `verdict_notes` overwrite semantics and a desktop docstring
is a pass that could not find anything structural — and this pass was
executing code, not reading it charitably.

**What it does not say.** Three things, plainly:

- *Several of those fixes shipped with holes, in the same week they
  shipped.* Four of the seven majors are fix holes, not old bugs: the
  no-op guard landed at two of three sites (P01); the politics guard
  covers three of four cut paths and misses the unattended one it was
  written for (P09), while its flagship example card is untagged
  (P10); the era stamp landed but neither pooled consumer was routed
  through it (P19) and the web writer still uses the retired rule
  (P20). The pattern is consistent: correct mechanism, incomplete
  application. A fix is not done when the core lands.
- *`app.js` still has zero tests.* Round 1's P13 filed it; B3 is
  queued and unbuilt. Two of this round's majors (P20) and two minors
  (P16, P24) live in that file, and every one of them was found by
  reading, because nothing else can find them. The single largest
  untested surface in the repo produced findings again this round and
  will again next round.
- *Zero criticals is not zero risk.* Round 1's criticals were about
  the product premise — statistical power, the noise ratchet, the
  value of the JVM spend. Those were answered by *decisions* (A1, A2,
  A3), and P21 shows the answer is incomplete: the replication gate
  fixes the false-positive rate the decision named, and leaves the
  loop advancing a genuine improvement about 1.3% of the time per
  overnight run. Round 2 did not find new criticals partly because the
  old ones are still open as product questions rather than closed as
  code.

Round 3, if there is one, should probably start where the tests
aren't.

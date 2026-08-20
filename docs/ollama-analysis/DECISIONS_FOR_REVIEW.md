# Product decisions — DECIDED 2026-08-17

Sixteen decisions collected from three review rounds plus negative mode,
reviewed with the owner on 2026-08-17. Every one is now settled; this
file is the record of what was chosen and why, and the work queue that
follows from it.

Status key: **[done]** landed · **[queued]** agreed, not yet built ·
**[parked]** deliberately not doing now.

---

## A. Product thesis

### A1. The Forge sim is a deep-dive instrument, not the per-swap arbiter — [queued]

The verdict gate detects a true +5pp improvement ~5% of the time at
shipped settings, and FP-002 measured curation as net-neutral over
37,120 games. Rather than pretend otherwise, the fast deterministic
tools — legality, Karsten manabase math, consistency, the advisor,
the dashboard — become the headline product; the sim stays available
for questions worth real game counts.

Follows: reposition README and STATUS framing; keep the honest
inconclusive/neutral machinery; stop implying per-swap proof.

### A2. Unattended runs require replication before advancing a deck — [queued]

A second independent A/B must confirm direction before the improve
loop permanently advances the base. Doubles sim cost per accepted
swap and kills the noise-ratchet (~5% of single-A/B accepts are false
positives against a ~0 true effect rate). Interactive runs stay
single-shot so the user isn't left waiting.

### A3. `--run-sim` defaults to the verdict floor — [queued]

Default rises from 5 games (which can only ever record "inconclusive")
to 40, printing the estimated time before it runs. `--smoke 5` keeps
the cheap sanity check.

### A4. Build the local-model router for small tasks — [queued]

The Ollama path — where this whole investigation started — becomes
real for the tasks local models are actually good at: archetype and
role tagging, cheap classification. Purpose-written schema-first
prompts (never the 706-line browser prompt), a preflight that the
configured model is actually pulled, and the hardware tiers from
MODEL_GUIDE.md. Verdicts and proposals stay on Claude.

### A5. Knowledge log: era-stamp rows, park the ML harness — [queued]

Every row gets a measurement-era/schema stamp so future analysis can
tell the three incompatible eras apart (pre-attribution-fix,
pre-decisive-convention, pre-significance-verdicts). The FP-013 eval
harness and the 0/1,000 gate line are parked until 100 gate-quality
rows exist.

### A6. Document the bot-meta caveat — [queued]

README states plainly where it makes the ground-truth claim: a "kept"
verdict certifies "better against Forge's AI, which loops ~25% of
games", not "better at your table."

---

## B. UX — all four approved

- **B1. `commander` umbrella command** — [queued] one multiplexer with
  subcommands, aliasing the 27 existing entry points so nothing breaks.
- **B2. Guided `commander-init`** — [queued] sequences bootstrap →
  oracle bulk → harvest → pool curation with cost/time warnings.
- **B3. JS smoke tests (Playwright)** — [queued] cover the
  verdict/save/SSE paths in the 4,308-line `app.js` that currently has
  zero automated tests.
- **B4. Weekly real-Forge canary** — [queued] a scheduled one-pod real
  JVM run so Forge-side regressions surface on their own.

---

## C. Policy

- **C1. `[REF]` decks excluded from filler seats** — [queued] they stay
  pool *candidates* (real playable builds worth ranking), but stop
  being seeded as fillers, matching the `[PREMADE]` popularity rule.
- **C2. Politics guard on by default** — [queued] goad / monarch /
  vote / tempting-offer / Rhystic-style tax cards are tagged and
  shielded from margin-driven cuts (same mechanism as `Protect=`),
  with an annotation that the sim can't judge them. Per-deck opt-out.
- **C3. Archidekt promoted to a fallback lane** — [queued] plus a
  documented risk tier per source, so a Moxfield ToS/CDN change
  doesn't strand imports, harvest, peers and meta-test refs at once.
- **C4. Rebuild tier is manual-only until validated** — [queued] the
  30+30 escalation is a 6× cost multiplier gated on the never-validated
  health score; it now requires explicit opt-in.
- **C5. Corpus-norms A/B** — [parked] not funded now; corpus-scaled
  ROLE_TARGETS stays blocked behind it, as the repo's own discipline
  requires.
- **C6. Pre-registered change-budget check** — [parked] not funded now;
  superseded in practice by C4 making the tier opt-in.

---

## D. Small approvals

- **D1. Margin backfill: dry-run only** — [queued] I run
  `scripts/backfill_web_margins.py` in dry-run and show the
  before/after table; the owner runs `--apply` themselves after
  reviewing, since the knowledge log is the only copy of that history.
- **D2. Host-header validation** — [queued] reject requests whose Host
  isn't `127.0.0.1`/`localhost` in the existing `before_request` hook,
  closing the DNS-rebinding path to deck reads and `PUT /api/config`.

---

## Implementation order

Cheap correctness and honesty first, then the structural UX work:

1. D2 host check, C1 `[REF]` fillers, A6 README caveat, C4 rebuild
   opt-in, A5 era stamp (all small, no new surface).
2. A3 sim default + A2 replication (same code path).
3. C2 politics guard, C3 Archidekt lane.
4. A4 local-model router.
5. B1 umbrella CLI + B2 `commander-init` (docs-heavy, touches every
   workflow).
6. B3 Playwright smokes + B4 Forge canary (new tooling in the repo).
7. D1 backfill dry-run report for the owner.

---

# Round-2 decisions (2026-08-20) — open

Six decisions surfaced by the round-2 negative-mode pass over branch
`claude/ollama-code-analysis-ak77i1` (see `NEGATIVE_MODE_ROUND2.md`).
The other nineteen findings from that round are engineering fixes and
need no call. Nothing below is settled; each is a product, policy or
owner-data judgment that the cross-examination explicitly declined to
make on the owner's behalf.

Status: all **[open]** — awaiting review.

### R2-D1. What is `--strategy bandit`'s relationship to the knowledge log? — [open]

`--strategy bandit` writes zero knowledge_log rows while running full
45-game A/B sims and permanently advancing the deck on disk: no
iteration row, no snapshot, no lineage, no revert path, invisible to
FP-013 — and the CLI copy claims "every improve run grows this number"
(R2-P02, major). The README's "every cycle is one row in
knowledge_log.sqlite" is currently false for one of three shipped
strategies.

The decision is what "one iteration" means for a bandit pull:

- **Log it** — record a row per accepted pull, with manifest = the
  single swap and snapshot = the candidate deck text. Restores revert,
  lineage and FP-013 counting, but commits the schema to treating a
  single-swap pull as an iteration alongside full curate cycles.
- **Declare it off-log** — leave the path as-is and state loudly in
  `--strategy` help and the README that bandit runs are unlogged and
  unrevertable, correcting the "every run" copy.

Either way the false CLI comment gets fixed. Affects schema semantics
and the FP-013 denominator.

### R2-D2. Does the unattended loop stay default-ON at its shipped power? — [open]

The A2 replication gate works as designed on false positives, but the
corrected arithmetic (45 games, 20-decisive gate, exact two-sided
α = 0.05) says a genuine +5pp swap advances with probability 0.13% per
round — **~1.3% over a 10-round overnight run** — while each round
spends 45 pod games, doubled on any gate trigger. The likelihood ratio
of an advance rises only 3.0 → 9.2, so advances remain majority-noise
unless the curator's true-hit rate exceeds ~10%; FP-002 measured
curation net-neutral (R2-P21, major). The docstring sells 1-in-1,600
false advances without stating either consequence.

The decision is spend and positioning, not code:

- **Ship as-is**, accepting that the expected outcome of an overnight
  unattended run is "nothing happened".
- **Raise per-round games** to buy power, at proportional JVM cost.
- **Reposition the flag** — the same move A1 made for the sim overall,
  applied to A2: an instrument for questions worth real game counts,
  not a background improver.

Separately, and independently of the above: should the docs be required
to state true-positive throughput beside the 1-in-1,600 figure wherever
that number appears?

### R2-D3. Label policy for a confirmation that could not run — [open]

When the replication sim fails to *run*, the writer rewrites a COMPLETED
run-1 row to `verdict='pending'` — but the vocabulary defines 'pending'
as "the sim didn't complete", and the row carries a done sim_report with
win rates. The row contradicts itself, and any consumer re-deriving
state from the verdict alone misreads it (R2-P05, minor).

Options:

- **`'pending'`** — current behavior; self-contradictory but signals
  "not confirmed" to the advance logic.
- **`'inconclusive'`** — consistent with the row's own sim_report, and
  already means "measured, not decided".
- **Leave run 1's verdict alone** and record the non-advance in notes
  only, keeping the verdict a statement about the sim that actually ran.

Whichever is chosen, the vocabulary doc should say so explicitly.

### R2-D4. Replication reward policy on the bandit path — [open]

On the bandit path, replication keeps run 1's reward in the arm mean and
discards run 2's — on both the confirming and the disagreeing branch.
The written rationale is that folding in a second sim would double-weight
the arms that reached the gate. Statistically this preserves rather than
corrects the winner's curse: run 1 triggered the gate by being extreme,
so run 2 is the unbiased draw (R2-P03, minor; non-default path).

Options:

- **Keep run-1-only** — the owner wrote the current rationale
  deliberately; overriding it is a judgment call, not a bug fix.
- **Fold run 2 in as a second observation** (`update_arm` twice), or
  replace the reward with the pooled estimate, and count the pull budget
  honestly.

### R2-D5. Should the 2026-08-14 era boundary be a hard date cut? — [open]

Era boundaries are handled asymmetrically: the 2026-05-21/22 session and
the 2026-07-19 window are NULLed because the fix landed mid-session, but
the era-3/4 boundary is a bare date cut, so rows written on 2026-08-14
*before* the significance commit are stamped era 4 and admitted to the
FP-013 training floor with margin-threshold labels (R2-P13, minor).

This one needs owner data, not a code opinion: **are there any rows in
the log written on 2026-08-14 before that commit?**

- If none, document that the window is empty and leave the constant.
- If some exist, NULL (or era-3) the date and start era 4 on 2026-08-15
  — which relabels live rows in the only copy of that history, so it
  follows the D1 precedent: dry-run report first, owner applies.

### R2-D6. Should skip-retirement distinguish transient from structural failures? — [open]

`run_bandit` retires an arm permanently after a single skip. The policy
is deliberate and documented — but its stated premise, that failures are
"typically structural", is false for two of the four skip classes:
`sim_failed` is a transient JVM crash and `zero_decisive_games` is
sampling luck. One transient event permanently removes an arm from a run
whose whole purpose is repeated measurement, on an event uncorrelated
with swap quality (R2-P08, minor, restated by cross-exam as a false
premise rather than broken code).

Options:

- **Keep the policy**, and correct the docstring's premise.
- **Split the classes** — retire on `apply_failed` / `swap_dropped`
  only, allow N retries for the `sim_*` classes. Changes run behavior
  and run length, so it is a policy change rather than a fix.

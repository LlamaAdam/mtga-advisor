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

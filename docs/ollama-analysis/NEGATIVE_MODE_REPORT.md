# Negative-mode review of commander-builder (2026-08-16)

Method: one agent explained every part of the program faithfully
(product concept, all four layers, web/desktop, process); a second,
hostile agent attacked every aspect of that explanation with source
verification. 23 problems survived verification. Problems marked
**[USER-DECISION]** are product/policy calls collected in
`DECISIONS_FOR_REVIEW.md`; the rest are engineering fixes.

## The five most consequential attacks

1. **P01 — The verdict gate has ~5% statistical power for realistic
   effects.** At the shipped 20-decisive minimum with alpha 0.05, a
   true +5pp improvement is detected 5.5% of the time (vs 2.1% false
   positives at the null). A properly powered +5pp test needs ~1,570
   pod games per swap. The README's "empirically validates whether
   swaps actually improve win rate" is not deliverable at shipped
   settings, and no power statement exists anywhere in the docs.
2. **P03 — The bandit/search evaluator bypasses the significance
   discipline entirely** (`improve.py:415-419`): it advances the base
   deck on a raw ±1-win margin (the exact game-count-invariant rule
   the 2026-08-14 work repudiated), and records crashed sims as
   0-reward ties.
3. **P02 — Given the project's own FP-002 null result, kept-verdicts
   are mostly false positives, and the greedy improve loop ratchets
   noise into permanent deck state** logged as "empirically validated."
4. **P04 — The knowledge log is not accumulating a trainable asset**:
   the FP-013 gate reads 0/1,000 after ~6 months, and the log spans
   three mutually incompatible measurement eras (pre-attribution-fix,
   pre-decisive-convention, pre-significance-verdicts).
5. **P05 — The economics are inverted**: tens of thousands of JVM games
   validate an intervention layer the project itself measured as
   net-neutral, while the demonstrably valuable features (legality,
   manabase math, consistency, imports, dashboard) need no JVM at all.

## Full problem list (compressed; each verified against source)

| # | Sev | Area | Problem | Disposition |
|---|-----|------|---------|-------------|
| P01 | crit | premise | Verdict gate ~5% power at shipped settings; no power statement in docs | Fix: power table + CI display; **[USER-DECISION]** on JVM spend |
| P02 | crit | premise | Greedy loop ratchets coin-flip winners given ~0 true effect rate | **[USER-DECISION]**: replication-before-advance policy |
| P03 | crit | bug | `improve.py` advances on raw margin ≥1, no significance, failures = 0-reward | Fix: route through `_verdict_from_ab`; failures = skipped pulls |
| P04 | maj | premise | Knowledge log: 0/1,000 gate rows, three incompatible eras, no era stamp | Fix: era/schema stamp; **[USER-DECISION]** on ML premise |
| P05 | maj | premise | JVM-heavy loop validates a net-neutral layer; cheap features carry the value | **[USER-DECISION]**: product thesis |
| P06 | maj | premise | "Ground truth" = looping-bot meta; transfer assumption unstated in README | Fix: state caveat; **[USER-DECISION]** on acceptability |
| P07 | maj | arch | Layering invariant false: diagram inverted; status/doctor/deck_dashboard import upward | Fix: redraw + declare reporting surface |
| P08 | maj | arch | No arbitration across recommendation surfaces; "7 sources" is actually 3 | Fix: aggregation + conflict view; fix docs |
| P09 | maj | bug | No cross-invocation Forge-profile locking; concurrent web+CLI sims collide | Fix: per-profile lockfile |
| P10 | maj | ux | 27 CLI entry points, overlapping verbs, comment cites nonexistent docs | **[USER-DECISION]**: umbrella `commander` command |
| P11 | maj | ux | First-run wall: hours of unsequenced setup behind a pip-install quickstart | **[USER-DECISION]**: guided `commander-init` |
| P12 | maj | process | `--run-sim` default 5 games can only record inconclusive rows | **[USER-DECISION]**: cost/consent default |
| P13 | maj | process | 0 JS tests for 4,308-line app.js; user is the test suite; no Forge canary | Fix (M): smoke tests + weekly canary |
| P14 | min | premise | Change-budget escalation gated on never-validated health score | **[USER-DECISION]**: validation spend |
| P15 | min | arch | FP-013 eval infra built while gate reads 0/1,000 | **[USER-DECISION]**: park it |
| P16 | min | bug | UCB1 exploration term mis-scaled for O(±20) win-margin rewards | Fix: normalize rewards |
| P17 | min | docs | Doc drift: 7-vs-3 sources, inverted diagram, dead doc refs, stale docstring, hand-pinned test counts | Fix: doc sweep |
| P18 | min | premise | Data spine on unsanctioned endpoints (Moxfield private API, scrapes) | **[USER-DECISION]**: risk tier / Archidekt promotion |
| P19 | min | ux | Pricing rendered from undated snapshots; legality got a staleness warning, pricing didn't | Fix: thread snapshot age |
| P20 | min | data | ~8 caches, 6 lifetime policies, doctor audits 2 | Fix: cache registry |
| P21 | min | ux | JS error log path lands inside vendor/ by default | Fix: `~/.commander-builder/` |
| P22 | min | docs | ~15 env flags undocumented; author's personal path baked into source | Fix: config reference + OS default |
| P23 | min | process | Offline-only tests structurally can't catch live-service drift (proven by the EDHREC breakage) | Fix: opt-in weekly live-contract lane |

## What genuinely survived the criticism

- **Epistemic honesty as practiced**: null results recorded as null,
  a wrong conclusion retracted in 16 minutes with both timestamps
  kept, real pre-registration ("COMMITTED BLIND"). Better hygiene than
  most industrial ML teams — the gap is acting on the conclusions.
- **The verdict-honesty machinery itself** (decisive-vs-total units,
  filler exclusion, inconclusive gates) — the attacks are about power
  and one bypassing path, not correctness.
- **Web hardening** unusual for a personal tool (error-log caps, image
  cache quotas, job-store restart recovery).
- **Forge quirk archaeology** (broken flags, buffered-stdout loss,
  seat-1 bias — all pinned with tests and rationale).
- **Test-suite engineering** (3,200+ offline tests, ~30s fast lane,
  byte-exact real-oracle fixtures).
- **`deck_builder_manabase` and `consistency`** — the load-bearing MTG
  math, isolated and citable; notably the modules that need no JVM.
- **Secrets discipline** end to end.

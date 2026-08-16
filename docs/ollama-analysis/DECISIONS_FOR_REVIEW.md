# Decisions that need your call (joint review list)

Collected from three review rounds + negative mode. Everything
engineering-only is being fixed without you; these change product
behavior, cost, or scope, so they wait for you. Each has a
recommendation to react to.

## A. The big product-thesis questions (negative mode P01/P02/P04/P05/P06)

1. **What is the Forge sim for?** The shipped verdict gate detects a
   true +5pp swap ~5% of the time; a real answer costs ~1,570 pod games
   per swap; and the project's own FP-002 experiment measured curation
   as net-neutral. Options: (a) keep sim as the per-swap arbiter and
   accept screening-level evidence (rename verdicts "screen-positive"),
   (b) reposition sim as an occasional deep-dive instrument and make
   the deterministic advisor+consistency+legality path the headline
   product, (c) fund real power for a few decisions you care about.
   **Recommendation: (b), with (c) on demand.**
2. **Replication before advancing?** Should the improve loop require a
   second independent A/B confirming direction before it permanently
   advances the base deck? Costs 2x sim time per accepted swap; kills
   the noise-ratchet. **Recommendation: yes for unattended runs, off
   for interactive ones.**
3. **The ML moonshot (FP-013)**: the 1,000-row gate reads 0 after ~6
   months and the log spans three incompatible measurement eras. Keep
   the infra and start era-stamping rows (cheap), or park the whole
   premise? **Recommendation: era-stamp (landing regardless), park the
   eval harness, revisit at 100 gate-quality rows.**
4. **Bot-meta caveat**: a "kept" verdict certifies "better against
   Forge's AI (which loops ~25% of games)", not "better at your
   table." Accept and document, or is this a dealbreaker for how you
   use verdicts? **Recommendation: accept + document in README.**
5. **`--run-sim` default (5 games)** can only ever record inconclusive
   rows. Raise the default to 40 (real cost per audit) with `--smoke 5`
   opt-out, or keep cheap-by-default? **Recommendation: raise, with
   the cost printed before running.**

## B. UX restructuring (negative mode P10/P11/P13)

6. **One `commander` umbrella command** replacing/aliasing the 27
   entry points? Additive and safe, but touches every doc/workflow.
   **Recommendation: yes.**
7. **A guided `commander-init`** sequencing bootstrap → oracle bulk →
   harvest → pool curation with cost warnings (the current first-run
   is hours of unsequenced steps)? **Recommendation: yes.**
8. **Invest in JS smoke tests + a weekly real-Forge canary?** The
   4,308-line app.js has zero automated tests; the compensating
   control is the production error sink. Needs adding node/Playwright
   tooling to the repo. **Recommendation: yes, minimal Playwright
   smoke of verdict/save/SSE paths.**

## C. Policy calls from rounds 1-2

9. **[REF] vs [PREMADE] popularity policy**: top-liked Moxfield
   reference decks are eligible sim fillers while premades are
   excluded for exactly that popularity bias. Exclude [REF] too, or
   document the asymmetry? **Recommendation: exclude from fillers,
   keep as pool candidates.**
10. **Sim-invisible politics guard**: exempt goad/monarch/vote/
    Rhystic-tax cards from sim-driven cuts (Forge's AI can't value
    them). Changes what the loop is allowed to cut — playstyle call.
    **Recommendation: on by default, per-deck opt-out.**
11. **Ollama path: build or delete?** Round 1 found it dead code with
    misfit prompts. Build the thin local-model router (archetype/role
    tagging first, per MODEL_GUIDE.md hardware tiers), or delete the
    stubs and doc claims? **Recommendation: build the small-task
    router only if you actually run Ollama locally; otherwise delete.**
12. **Data-source risk appetite**: most acquisition rides Moxfield's
    private API + scrapes (one ToS change strands it). Promote
    Archidekt (public API) to co-primary where substitutable?
    **Recommendation: yes, as fallback lane.**
13. **Change-budget validation**: the 30+30 rebuild escalation is
    gated on the unvalidated health score. Fund a small pre-registered
    check, accept as-is, or make rebuild-tier manual-only?
    **Recommendation: manual-only until validated.**
14. **Corpus-scaled ROLE_TARGETS** stays blocked on the corpus-norms
    A/B the repo itself queued. Run that A/B (sim cost), or leave the
    static template? **Recommendation: run it once, decide on data.**

## D. Small approvals

15. **Margin backfill script** (`scripts/backfill_web_margins.py`,
    landing in the current fix wave): recomputes legacy web-saved
    margins from stored sim reports, fenced to id ≥ 314, dry-run by
    default. OK to run `--apply` on your live knowledge log?
16. **Web `PUT /api/config` etc. Host-header check** (round-1 finding,
    unfixed): add localhost-only Host validation? Tiny change,
    recommended, but it touches how you access the UI if you ever use
    a non-localhost hostname.

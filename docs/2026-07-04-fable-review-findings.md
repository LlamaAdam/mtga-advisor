# Fable Review — Benchmark + Session Changes

**Date:** 2026-07-04
**Reviewing:** `master` tip `a8a0e60` per `docs/2026-07-04-benchmark-and-session-review-handoff.md`
**Verdict:** Benchmark engine (the primary deliverable) is **sound** — every §6 checklist item passes and the four suggested adversarial tests were added and pass (suite now 374). But the review surfaced **one urgent security item** and a set of real bugs in the log scanner and synergy tagger that should be triaged before further feature work.

---

## 0. Checklist results (§6)

| Check | Result |
|---|---|
| `pytest tests/ game_advisor/tests/ -q` | ✅ 370 passed before my changes; **374 passed** with the 4 new adversarial tests |
| `pytest tests/benchmark/ -q` | ✅ 14 → 17 passed |
| Manual §3 snippet | ✅ prints `Agreement rate: 100%`, coverage 1/1 (cache hit for MSH) |
| `git log --oneline 04780b9..HEAD` | ✅ matches §2 (plus the handoff doc commit) |
| Scryfall `_SCRYFALL_HEADERS` | ✅ all four call sites in `card_db.py` (lines 257, 351, 386, 466) send headers; `api.py`'s three `requests.get` are 17Lands, not Scryfall |

## 1. URGENT — the "scrubbed" OpenRouter key is still in public history

The handoff states the history rewrite scrubbed the fake-but-real-shaped key and a full-history scan came back clean. **That is not the case.** Commit `2de3774` — on `master`, **`origin/master` (public)**, and both local benchmark branches — still contains the full `sk-or-v1-7c84…dda0` string in `game_advisor/.env.example`. The placeholder fix only landed in the *next* commit (`214cb3b`); the rewrite missed the commit where the key first appeared.

Verified with: `git grep -l <key> $(git rev-list origin/master)` → 1 commit (`2de3774`).

**Recommended actions (operator decision — I did not rewrite public history):**
1. If that key was ever real, revoke it at openrouter.ai now — treat it as burned either way.
2. Rewrite history again (`git filter-repo`/BFG targeting `2de3774`'s blob of `game_advisor/.env.example`) and force-push **all** branches, or accept the exposure if the key is confirmed fabricated.

## 2. Benchmark engine (primary deliverable) — findings

The §5 attack surface held up well:

- **Fairness rule — correct.** The tracker holds only *prior* picks when scoring pick N; the human's pick is added after scoring, and it is added even for skipped picks so deck-mirroring never desyncs. New test `test_mid_draft_skip_excluded_from_metrics_but_still_mirrored` locks this in.
- **Pack-opener branch — consistent with production.** `pick_number == 1 and pack_number >= 2` mirrors exactly when the overlay calls `best_pick(ignore_colors=True)` (raw "All Decks" win rate). Treating P1P1 as non-opener also matches production.
- **Tie behavior — deterministic.** Stable sort preserves pack order among equal ratings, matching `best_pick`'s strict `>` (first tied card wins). New test `test_tied_ratings_rank_deterministically_in_pack_order`.
- **Zero-scored reports — safe.** Metrics return 0.0, coverage renders "0/N", no division by zero. New test `test_zero_scored_picks_render_without_dividing_by_zero`.

Two genuine (non-blocking) issues found:

- **MEDIUM — cross-set ratings staleness in `runner.py`.** `_ensure_ratings_loaded` early-returns on `ratings.is_loaded()`, which only checks that *some* ratings dict is non-empty — it does not know which set is loaded. Benchmarking set A then set B in one process silently scores B against A's ratings. Fix: have `ratings` remember its loaded set code (or track it in the runner) and reload on mismatch.
- **LOW — unrated-card divergence from production.** `_rank_pack` includes unrated cards at −999 (they rank last), while `best_pick` skips `None`-rated cards entirely and returns `None` when nothing is rated. For a fully-unrated pack the scorer emits an arbitrary `tool_pick` (first pack card) and can register a spurious "agreement". Consider `scored=False` when the top rating is the −999 sentinel.
- **Handoff §5.4 (name near-misses):** confirmed a typo'd `human_pick` silently skips. Given `ratings._lookup` already does fuzzy matching, a reasonable Phase B improvement is fuzzy-matching `human_pick` against `pack_cards` before declaring a skip, and surfacing skipped names in the report (they currently appear in the table, which is adequate for hand-checking).

## 3. Log scanner (`draft_helper/log_scanner.py`) — needs a hardening pass

Reviewer verified each of these by execution:

- **CRITICAL:** `_get_payload` (~line 271): a present-but-non-string `Payload` (e.g. `{"Payload":123}`) raises `TypeError` — not in the caught `(JSONDecodeError, KeyError)` — and kills the poll loop permanently. Add `isinstance(payload_str, str)` or catch `TypeError`.
- **CRITICAL:** widened set-detection (`"InternalEventName" in line and "Draft" in line`, ~line 225): a *stale* course name appearing in a state dump mid-stream resets the active draft (wipes `current_pack`, re-fires `on_draft_start`, loads the wrong set's ratings). Don't let the fallback signal override a draft already established by `EventJoin` in the same parse pass.
- **HIGH:** no monotonicity guard — a duplicated/late `Draft.Notify` rewinds `pick_number` and restores a stale pack.
- **HIGH:** `GrpIds` regex (~line 470) is unanchored (a decoy `GrpIds\":[999]` substring earlier in the line wins) and only matches single-id arrays (`[105119,200000]` → pick silently dropped). Parse the `request` JSON properly, regex as fallback.
- **MEDIUM:** `PackCards` tokens aren't validated as numeric; a JSON-array-valued `PackCards` becomes mangled names like `C[105009`. Greedy `Draft\.Notify\s+(\{.*\})` is fragile to future trailing brace content.
- Verified robust: no regex backtracking blowups, truncated lines degrade gracefully, `picked_ids` dedup works, empty CSV tokens filtered.

## 4. Synergy tagger / mulligan verdicts — mostly design questions

- **Design decision needed:** `removal` is excluded from `_PAYOFF_THEMES`, so a removal-shell deck's best possible hand verdict is "functional", never "synergistic". The handoff implies this is intended ("removal is not a payoff theme") — my new test `test_assess_hand_removal_deck_is_functional_not_synergistic` pins the current behavior; flip it deliberately if you decide removal-on-plan should read as synergistic.
- **HIGH:** the `enabler` tag is purely mechanical (CMC ≤ 2 instant/sorcery) with no exclusion, so cheap removal and cheap payoffs double-tag as `enabler`, polluting significant-theme detection.
- **MEDIUM:** `"+1/+1" in text` counts counter-*removal* costs ("remove a +1/+1 counter…") as counters-theme cards.
- **MEDIUM (drift bug):** `rule_engine._REMOVAL_ORACLE_MARKERS` is a second, narrower removal list that misses counterspells and −X/−X effects which `synergy._REMOVAL_PATTERNS` catches — in-game `check_removal` disagrees with draft-side removal detection for the same card. Share one definition.
- Verified safe: the handoff's "counter target spell" vs "+1/+1 counter" worry — the two pattern families cannot cross-trigger.

## 5. Claude CLI backend (`game_advisor/llm_advisor.py`)

- **MEDIUM:** env scrub is case-sensitive; on Windows (case-insensitive env) a `anthropic_api_key` in the parent leaks to the child. Compare on `k.upper()`, and consider an allowlist over the current denylist.
- **LOW:** `config.CLAUDE_CLI_TIMEOUT_SECONDS` is dead — the claude path actually uses `LLM_TIMEOUT_SECONDS` (30s). Wire it or delete it.
- Verified clean: list-form argv (no `shell=True`), prompt via stdin, timeout handled, `.env` properly ignored, no secret content in error paths, existing scrub test covers the uppercase happy path.

## 6. Tests added this review (all passing)

| Test | File | Pins |
|---|---|---|
| `test_mid_draft_skip_excluded_from_metrics_but_still_mirrored` | `tests/benchmark/test_scorer.py` | skip excluded from metrics; mirroring still advances |
| `test_tied_ratings_rank_deterministically_in_pack_order` | `tests/benchmark/test_scorer.py` | stable-sort tie behavior |
| `test_zero_scored_picks_render_without_dividing_by_zero` | `tests/benchmark/test_report.py` | zero-scored safety, coverage line |
| `test_assess_hand_removal_deck_is_functional_not_synergistic` | `tests/test_synergy.py` | removal verdict boundary (current behavior) |

## 7. Suggested triage order

1. Resolve the key exposure (revoke and/or rewrite history) — before anything else touches the public repo.
2. Log scanner CRITICALs (crash + stale-course reset) — they take down the live overlay.
3. Runner cross-set staleness (matters as soon as Phase B benchmarks multiple sets).
4. Env-scrub case-insensitivity (one-line fix + regression test).
5. Synergy tagger refinements + removal-list unification (behavioral tuning, needs your call on the removal-verdict design question).

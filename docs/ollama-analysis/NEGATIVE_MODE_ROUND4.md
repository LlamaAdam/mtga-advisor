# Negative-mode review, round 4 (2026-09-16)

Target: **PR #86 at head `d554270`, reviewed as it would land** — master `0b944ef` plus the 44 round-3 FIX-MASTER items (C-01…C-14, F-01…F-18, W-01…W-10, W-12, W-13, with
S-1…S-4 riding along) and the three audit open bugs of 2026-09-09 (Game Changers scraper, unpriced cards, network-blocking fixture). Nine commits, 103 files, +6,738/−637.
The two pull requests by a different AI assistant — #85 `feat/fp-019-primer-heuristics` @ `e4ca395` and #84 (the Windows desktop lock-diagnostics PR) @ `d8207d0` — are
unchanged since round 3 and were examined only for how they merge with #86.

Method: a four-agent maximum-effort pass, run one agent at a time. One agent explained the PR fix by fix from source (`EXPLANATION.md`, 1,335 lines: a 47-entry "asked →
done → pinned → deviation" ledger, a claims ledger against the PR body and CHANGELOG, and a merge- interaction section). Two hostile critics attacked in parallel lanes —
core statistics, knowledge log, the C-11 UI and audit bug 2 (critic A); FP-018, web/CLI/desktop, audit bug 1 and the #85/#84 interactions (critic B) — each executing code
where a number or behaviour was in dispute, every probe pinned to the target tree by path. One cross-examiner then re-tried every attack from the defense side, re-ran
every probe (including both critics' scripts verbatim), re-ran the merge-tree in a throwaway clone, and ranked on the corrected evidence. Where the cross-examiner
corrected a critic, this report states the cross-examiner's version and nothing else.

Exclusion rule: every round-3 id is treated as known. It is re-filed here only as **FIX-INCOMPLETE** (the round-3 `Fix:` line was not fully done) or **REGRESSION**
(master behaved correctly and the PR does not), each with new evidence; everything else is **NEW**, meaning the fix's completeness is not impugned and the residue is
adjacent to the ask. The contract for "inside the ask" is the `Fix:` line (or the finding's stated remedy) in `NEGATIVE_MODE_ROUND3.md` §2–§4, quoted per entry by the
explainer and the cross-examiner.

**Headline tally: 28 raised → 12 CONFIRMED · 16 PARTIAL · 0 REFUTED** (plus 8 suspected items checked, one promoted: the proposer's `Protect=` cut guard, B-18). Severity
after cross-examination: **critical 0 · major 0 · minor 28.** Scope split after examination: **FIX-INCOMPLETE 3** (B-02 advisor sites, B-09 `deck_source`, B-15),
**REGRESSION 1** (A-01), **NEW 24** — ten of which the critics had filed as FIX-INCOMPLETE or REGRESSION (A-02, A-03, A-04, A-06, A-08, A-09, A-12, B-03, B-08, B-11) and
the cross-examiner re-labelled because the round-3 ask was met and the residue sits beside it.

The critics had filed **6 major**. Every one became minor, and each downgrade is calibrated against round 3's own ratings rather than a fresh scale. Round 3 rated W-04 —
one cp1252 `.dck` 500-ing `/api/library` and every per-deck route — *minor*, because it needs an external editor; B-01 (a cp1252 sidecar crashes `adopt`) and B-02
(`/api/audit` 503s on a cp1252 deck) need the same editor on one file and reach less, so major would re-grade W-04. Round 3 rated C-08 — `deck_id` fragmenting on every
surface, the CLI and `parent_id` — *major*; A-02 is two view-only web widgets going empty after the backfill, rows intact, reversible, and A-03 is a docstring overclaim
whose concrete harm is one parent lookup on versioned files. A-08's missing floor gate is on an LLM verdict rung that no production path constructs (the flag defaults
`False`; the tree's own comment says the only production construction is the default). B-03's `--preferences` on the bandit is a no-op flag on an opt-in explorer, not a
wrong steer. No severity was raised. The one candidate for raising — B-04, the fence id being a 48-bit fixed point — stays minor on the achievable-effect reasoning round
3 applied to F-05: the only verifier is the model, which computes no hash, so a wrong id already "reads as a closing line"; both presentation orders carry the same
primer, so a seat-level payload is an order flip and returns `inconclusive`; a content-keyed payload still needs 5 of 6 and reaches observe-only statistics.

Routing: **FIX-NOW 18 · FOLLOW-UP 11 · USER-DECISION 0.** The fixer works from the FIX-NOW list in §4. R3-D1 (auto-Protect) and B-16's "POST-only" alternative remain the
owner's from round 3; nothing new was added to that queue.

---

## The reconciled top 5

Merged from the cross-examiner's ranking. All five are minor; they are ranked by how much they change what a user or the next round sees.

1. **A-02 + A-03 — the web lane's deck key vs the C-08 backfill.** After the CHANGELOG-instructed `backfill_deck_ids.py --apply`, the verdict pills and the price
   sparkline render empty for every Moxfield-, Archidekt- and version-keyed deck with web A/B history — broader than filed, since `_FILENAME_SHAPED` matches every `[USER]
   … [B3]` stem and the backfill then prefers the provenance id. Rows are intact; two of the four per-deck readers already merge both ids and two do not; the web writer
   still stores the raw stem while `deck_identity.py` claims "every writer AND reader". NEW, FIX-NOW as one patch, readers first (the writer change alone blanks the same
   two widgets immediately, with no backfill involved).
2. **B-01 + B-02 — cp1252 tolerance stops at the `.dck`.** The primer sidecar this PR turned into a production input is read strictly by all three sidecar readers, so a
   cp1252 sidecar tracebacks `adopt` and makes `judge`/`improve` print "judging without it" — where "it" silently includes the `--preferences` typed on the command line.
   Beneath the migrated `/api/audit` route, `advise()` re-reads the deck strictly, so the route migration is hollow for the advisor. Both minor by the W-04 calibration;
   both FIX-NOW (one helper, four one-liners, two tests).
3. **A-01 + A-07 — a regression and an asymmetry in the core batch.** `collect_deck_status` now raises on a missing deck path, against its own docstring ("fields go
   empty/None rather than crashing"); the C-12 branch is one-sided, so `intent + both` is `mixed` with a reason that is false while the mirror `staple + both` is
   `staple_ward`, enlarging one G3 arm. Both one-liners, FIX-NOW.
4. **B-03 + B-12 — two dead lanes on the F-01/F-06 wiring.** `commander improve --strategy bandit --preferences …` is accepted, printed as `preferences=N words` and
   consumed by nothing (the bandit was already blind to `Intent` on master); the desktop Import button still writes no sidecar, so every UI-imported deck answers `adopt`
   with the "no primer — common (~75 %)" misattribution F-06 named. NEW, FIX-NOW (two lines and five lines).
5. **B-15 + B-09 + B-08 — three one-line near-misses.** No `workflow_dispatch` (F-17's ask verbatim; it must land before merge because dispatch is registered only from
   the default branch); `PUT /api/deck_source` still writes a bare-LF `Moxfield=` line into a CRLF deck (W-10 said "any PUT"); the header-less-sidecar re-pull overwrites
   hand notes under "upstream changed", and the critic's own fix would not have saved them either. All FIX-NOW.

Honourable mention: **A-08** is the largest latent item — the LLM verdict rung has no decisive-games floor — but nothing in the tree reaches it; a three-line clamp now is
the round-3 F-05 pattern of hardening before the rung is wired.

---

## 1. How well PR #86 answered round 3

The 44 round-3 items plus the three audit bugs, from the explainer's §1 ledger and the cross-examiner's consolidated "verified holding". **Fixed as asked 42 · fixed with
a narrower scope 2 · incomplete 3.** "As asked" means the `Fix:` line was done and every pin executed; a trailing id names the adjacent NEW finding that bounds it.

| Id | Verdict | Note (bounds → round-4 id) |
|---|---|---|
| C-01 | as asked | `inconclusive` on the heuristic floor; `next_action` map and LLM labels widened; four pins re-pinned → A-08 (no gate on the LLM rung), A-09 (`stats_summary`) |
| C-02 | as asked | `status != "done"` → `inconclusive`, `ran: False`, `None` counts; `skipped` covered too |
| C-03 | as asked | `filler_policy` module on both auto-pick paths; loud on every `compare()` caller → A-13 (explicit `--sim-fillers` override) |
| C-04 | as asked | `check_compare_name_alignment` before any pod; nameless deck warns (documented) |
| C-05 | as asked | `--apply-era-shift` idempotent, survives `init_db`; `--era-boundary-report --apply` refused |
| C-06 | as asked | id lane / `None` / bare date at 4 boundaries executed |
| C-07 | as asked | `commit_instant_utc`, `side` column in UTC → A-04 (row selection still by string) |
| C-08 | **narrower** | `Source=` not read (harmless: `Archidekt=` is always written beside it); `parent_id` not re-threaded (declined) → A-01 (REGRESSION), A-02, A-03 |
| C-09 | as asked | `verdict_params` on both writers |
| C-10 | as asked | suggestion recomputed server-side; client copy parked |
| C-11 | **narrower** | labels/tooltips only; games semantics unchanged (still per pod); no JS test executes `describeGamesOption` → A-05, A-06 |
| C-12 | as asked | all-staple + `both` → `staple_ward` → A-07 (mirror) |
| C-13 | as asked | agreement over decided rows only |
| C-14 | as asked | `decisive_margin` on every writer; readers tolerate NULL; history not rewritten → A-12 |
| S-1, S-3, S-4 | as asked | pins executed; S-2 is a comment rewrite |
| F-01 | as asked | `learn_intent` → fence → `--free-text-themes` traced end to end on greedy → B-03 (bandit), B-01 (encoding) |
| F-02 | as asked | `match_key` both sides (superset of the asked `name_key`) → B-14 (back face) |
| F-03 | as asked | tribe slot reserved by construction; real `advise` pinned |
| F-04 | as asked | word boundaries + negation window; 0 affirmative drops on the real corpus → B-06 (four over-broad cues) |
| F-05 | as asked | sentinel fence + system-prompt rule + `prompt_version` on the only constructor → B-04 (wording), B-05 (pooled gates) |
| F-06 | as asked | both CLI lanes write → B-12 (UI lane) |
| F-07 | as asked | header first; refusal in both consumers |
| F-08 | as asked | minimum (import line) printed → B-08 (attribution; docstring promise) |
| F-09 | as asked | unresolved → protected; init text not pinned |
| F-10 | as asked | `match_key` in adopt → B-18 (proposer cut guard still `lower()`) |
| F-11, F-13, F-14, F-15, F-16, F-18 | as asked | pins executed; F-11 still prints the names under the honest label |
| F-12 | as asked | independent rewrite of master's function, PR-03 case pinned → B-07 (heading shape); conflicts with #85 |
| F-17 | **incomplete** | `workflow_dispatch` absent; trigger byte-identical to master → B-15 |
| W-01, W-02, W-03 | as asked | executed on a loopback server; B-16 residual is inside W-02's stated contract |
| W-04 | **incomplete** | routes migrated, but `advise()` re-reads strictly beneath `/api/audit` → B-02; no cp1252 second pass (U+FFFD replacement); CLI readers not migrated |
| W-05, W-06 | as asked | newline in a name is sanitised to `_` rather than refused (noted narrowing) |
| W-07 | as asked | validated at PUT; the FIX-PR85 consumer half is still owed by #85 |
| W-08 | as asked | `mkstemp` 0600 + `os.replace` → B-11 (symlink) |
| W-09 | as asked | all five sites; other writers outside the ask |
| W-10 | **incomplete** | `deck_text` PUT round-trips CRLF; `deck_source` PUT does not → B-09 |
| W-12, W-13 | as asked | fake lock + env; SSE spec asserts the rendered state |
| Bug 1 | as asked | 53/53 on the recovered 421,488-byte capture, trusted → B-10 (completeness) |
| Bug 2 | as asked | partial marker through pricing → audit → `save_iteration` → status → A-10, A-11 |
| Bug 3 | as asked | TCP/DNS blocked, proxy vars absent, child processes traced; UDP `sendto` uncovered (S-C, no caller) |

The PR body's quantitative claims held where the tree can show them (explainer §6): `--run-slow` → **4,588 passed, 0 skipped in 49.9 s** and the fast lane → **4,420
passed, 168 skipped in 44.0 s**, exactly as stated; the `live` marker hunks are byte-identical to #85's; the capture files were consumed and deleted. Two body claims are
not verifiable in the tree (the 23 posted reviews; the "310 tests that tripped" count) and one is over-stated: "one `.dck` reader replaces the strict reads" is true for
the web routes and the adopt/intent/ judge readers, not for the ~18 the round-3 finding counted.

---

## 2. The round-4 findings by area

Severity is as corrected by cross-examination; each block gives the corrected claim, the corrected fix and the routing, with the scope tag.

### 2a. Core, knowledge log and the web lane's deck identity

**[A-01] minor · CONFIRMED · REGRESSION(C-08) — `collect_deck_status` raises on a missing deck path.** Executed: target → `ValueError: deck not found and no fallback`;
master → `OK`. `status.py:482` now calls `resolve_deck_id(deck_path, fallback=mox_id)` and `mox_id` is `None` for a missing file (`:330-333`), so
`deck_identity.py:126-129` raises. Only the library entry point regressed: `:655` sits inside a glob and the CLI guards the path first (`:756-758`); no in-tree caller
passes a missing path, but the docstring (`:463-465`) promises no crash. Fix: `fallback=mox_id or stable_deck_stem(deck_path.name)` at `:482`, mirroring
`_proposer_sim.py:606-607`; pin the missing-path case. Routing: FIX-NOW.

**[A-02] minor · PARTIAL · NEW — `backfill_deck_ids.py --apply` empties `/api/verdict_breakdown` and `/api/pricing_series`.** Executed end to end with the real app and
script: after `--apply`, the ids the UI sends (`[USER] Foo v2 [B3]`, `[USER] Mox [B3]`, `[USER] Arch [B3]`) show `iterations` and `graph` intact but `verdict_total 0` and
`pricing_pts 0`. Broader than filed: `_FILENAME_SHAPED` (`deck_identity.py:69-71`) matches every ` [B\d]` stem, so every Moxfield- and Archidekt-imported deck with web
history is re-keyed, not only versioned ones. Nothing is lost — `/api/iterations` (`routes_dashboard.py:587-606`) and `/api/iteration_graph` (`:674-690`) resolve and
merge both ids; only `verdict_breakdown_route` (`:808-813`) and `pricing_series_route` (`:633-636`) query the raw stem. `parent_id` is untouched. C-08's ask named the
writers and the backfill, not the web readers, and the gap was latent on master for Moxfield decks. Fix: factor the `/api/iterations` merge into `_ids_for_stem(deck_id)`
and apply it to both routes (sum breakdowns, concatenate-and-sort points). Routing: FIX-NOW — the CHANGELOG tells the owner to run `--apply`.

**[A-03] minor · PARTIAL · NEW — the web writer stores the raw filename stem.** `POST /api/save_iteration` for `[USER] Foo v2 [B3]` stores that stem verbatim
(`routes_sim.py:821` → `:1013`); the CLI writer for the same file stores `[USER] Foo [B3]`. The web lane has always been stem-keyed by design (the `/api/iterations`
comment describes the dual-key arrangement on master) and the round-3 text scoped C-08 to "the two unattended writers"; what is false is the new `deck_identity.py:24-25`
claim of "one identity function every writer AND reader routes through". Concrete harm is bounded: the auto-curate parent lookup (`_proposer_sim.py:614`) cannot see web
rows on a versioned file. Fix: `resolve_deck_id(path, fallback=stable_deck_stem (deck_id))` in `save_iteration` — **after** A-02's reader merge, never before it. Routing:
FIX-NOW as one patch with A-02; FOLLOW-UP if split.

**[A-04] minor · PARTIAL · NEW — era-boundary report and `measurement_era_for` still select by the raw date string.** `era_boundary_report` selects `WHERE created_at LIKE
'2026-08-14%'` (`backfill_web_margins.py:365-369`) and `apply_era_shift` relabels that set; only `_side_of_landing` converts both instants (`:336-344`).
`measurement_era_for` compares the prefix lexically (`knowledge_log.py:388-396`). C-07's premise was UTC rows vs a local commit time, and the PR compares the commit in
UTC as asked; rows carrying a non-UTC offset come only from `export.py` import or a hand edit. Fix: filter in Python on `_row_instant_utc(created_at).date()` and print
the UTC instant (script-only, safe); touch the classifier only with a pinned table of offset cases. Routing: FOLLOW-UP.

**[A-07] minor · CONFIRMED · NEW — the C-12 branch is one-sided.** Executed with the test module's helpers: `{staple 0, intent 1, both 2}` → `mixed` "evidence for neither
side"; `{staple 1, intent 0, both 2}` → `staple_ward`. The new branch (`_deck_judge_prompt.py:546-560`) has no `intent and both and not staple` twin, so the mirror falls
through to `:567-573` with a reason that is false when every added card matches the intent. C-12 asked about the all-staple case only. Fix: add the symmetric
`intent_ward` branch (or treat `both` as neutral on both sides); pin the mirror. Routing: FIX-NOW — it changes what G3 measures.

**[A-08] minor (latent) · PARTIAL · NEW — the decisive floor is enforced on the heuristic rung only.** `analyze()` returns the heuristic only at confidence ≥ 0.75
(`analyst.py:199-202`); the floor branch returns `inconclusive` at 0.3 (`:294-296`); with the analyst's LLM flag set the router calls the model rung (`:237-247`), which
accepts any label in the four-word set verbatim (`:531-537`). True — and unreachable: the flag defaults `False` (`:170`), the only production constructions are the
defaults (`iteration_loop.py:322`, `analyst.py:197`, stated at `:586-590`), and `--auto-propose` sets the *proposer's* flag, not the analyst's. No CHANGELOG text
describes the configuration the critic named. The "missing/unknown label → `neutral`" coercions are master's lines verbatim. C-01 asked that the rung accept the label,
which it does; a gate was not asked. Fix: in `analyze()`, if the heuristic is `inconclusive` and `decisive < min_decisive_games`, return it without escalating; treat a
missing or unknown label as a parse failure. Routing: FOLLOW-UP (acceptable as FIX-NOW at three lines).

**[A-09] minor · PARTIAL · NEW — `stats_summary` has no `inconclusive` bucket.** `knowledge_log.py:1087-1102` returns `total, kept, reverted, neutral, pending,
unique_decks`; `status.py:279-284` prints those five. `inconclusive` rows predate the PR (web and auto-curate writers since 2026-08-20; master's `app.js:3112-3114`
already comments on the gap); C-01 adds `commander-iterate` to the writers. Fix: one `COUNT(*)` plus the `status.py` line; `app.js` reads only `total`. Routing: FIX-NOW —
the CHANGELOG's "readers migrated" should be true.

**[A-12] minor/low · PARTIAL · NEW — legacy era-4 `margin = 0` rows are neither backfilled nor distinguishable.** True for stored rows (`recompute_margin` skips reports
without `old_wins`/`new_wins`, `backfill_web_margins.py:159-178`; the PR says "history not rewritten"). The reader half is refuted: `scripts/margin_analysis.py` reads
soak JSONL, not the knowledge log, and no in-tree reader pools `iterations.margin`. The shape is distinguishable by `margin = 0 AND win_rate_old IS NULL AND win_rate_new
IS NULL`. Fix: one `UPDATE … SET margin = NULL` under that predicate in the dry-run script, or document the shape test. Routing: FOLLOW-UP.

**[A-13] minor · CONFIRMED · NEW — explicit `--sim-fillers` seats `[REF]`/`[CONTROL]` decks with no note.** `improve.py:339-340` and `_proposer_cli.py:323-328` hand the
operator's list straight to `run_ab_simulation`; `filler_policy` is consulted only on the auto-pick branches C-03 named. An operator override is a legitimate escape
hatch; the defect is that the row does not say so, while the CHANGELOG says "every filler path". Fix: one `NOTE:` line naming the excluded prefixes seated and
`sim_report["fillers_overridden"] = True`. Routing: FOLLOW-UP.

**[B-18] minor · promoted from suspected · NEW — the proposer's cut guard still keys `Protect=` on `lower()`.** Executed: `read_protected_cards("Protect=Jeska’s Will")` →
`"jeska's will" in {x.lower()}` is `False`; `match_key` → `True`. `proposer.py:725, 906, 1103-1106` compare `lower()`, so a curly-apostrophe `Protect=` is unprotected on
`commander improve` and auto-curate — the path that actually cuts. F-10 was scoped to adopt and its ask ("one key") was done there. Fix: two call sites → `match_key`. Not
executed through a sim (no Forge). Routing: FOLLOW-UP.

### 2b. Test suite and the network block

No numbered finding landed here. Audit bug 3 held under direct attack: `requests`, `http.client`, `socket.create_connection` and `asyncio.open_connection` all raise
`NetworkBlockedError` under the conftest; the proxy variables are absent inside a test; the three tests that spawn real children (`--help`, a child `pytest`, `git`) reach
no socket; no `urlopen`-level patch remains beneath the new seams, so no test silently changed subject; no `live`-marked test exists. Residuals, notes only: UDP `sendto`
and `gethostbyname` are not covered (S-C; no repo code uses them), and the module-level `pytestmark` that #84/#85's appended tests will inherit is in
`tests/test_web_app.py:23` and `tests/test_deck_dashboard.py:35` only — `test_bracket_estimator.py` marks per test and `test_desktop.py` not at all — though all four run
under the autouse `network_block`, which is the consequence that matters (§3, item 8).

### 2c. FP-018 — intent, sidecar, fence

**[B-01] minor · PARTIAL · NEW — a cp1252 sidecar crashes `adopt` and strips primer + `--preferences` from `judge`/`improve`.** Executed: every sidecar reader raises
`UnicodeDecodeError`; `commander adopt --json` rc 1 with a traceback naming the byte, not the file; `commander judge --preferences tokens` rc 0 with `WARN: could not
learn intent … judging without it` and `report.intent: None`. Readers: `primer.py:369, :382, :443` read strictly inside `except OSError` (`UnicodeDecodeError` is a
`ValueError`); `deck_judge.py:777-782` and `improve.py:1791-1798` catch the `learn_intent` failure wholesale, and the preferences ride on it. W-04 counted `.dck` readers;
the sidecar is a file class this PR made a production input, so NEW of the same class, minor by W-04's calibration. Fix: one tolerant sidecar reader (strict UTF-8 →
`errors="replace"` + one WARN naming the file) at the three sites; `(OSError, ValueError)` in the readers; `:419` → `read_deck_text`; on `learn_intent` failure keep the
preferences on a bare `Intent(pilot_preferences=…)`. Routing: FIX-NOW.

**[B-03] minor · PARTIAL · NEW — `--strategy bandit --preferences …` is accepted, printed and has no effect.** `_run_bandit_strategy` (`improve.py:1312-1330`) never reads
`args.intent`; `_build_arms_from_advice` calls `advise()` without themes (`:856`, identical to master). The greedy default strategy consumes the flag end to end, so
F-01's ask is met; the bandit was already blind to `Intent` on master (`--intent-themes` was dead there too). Fix: pass `intent_themes` and
`free_text_bias_slugs(args.intent)` into `advise()` from `_build_arms_from_advice`, the same split `_default_round_fn:216- 229` makes; pin the call. Routing: FIX-NOW.

**[B-04] minor · PARTIAL · NEW — the fence id is a 48-bit fixed point, not "unforgeable"; the reader never checks it.** Arithmetic reproduced (16/20/24-bit widths forged
in 259/4,754/32,107 trials). Beside the point: the only verifier is the model reading `_FREE_TEXT_RULE` (`_deck_judge_prompt.py:133-143`), which computes no hash, so a
wrong id already reads as a closing line and a keyed 256-bit id would change nothing. The hash's real job — distinguishing the two lines from any line the author wrote
without knowing the text's own hash — holds against anyone unwilling to spend GPU-minutes. Achievable effect is unchanged from round 3's F-05 ruling. Fix: reword `:711,
:714-720`; in `_fence_free_text`, prefix any in-band line starting with `<<<FREE-TEXT` or `>>>END-FREE-TEXT` so no payload line is fence-shaped; extend the pin. Routing:
FIX-NOW.

**[B-05] minor · CONFIRMED · NEW — `judge_agreement` still pools G1/G2/G3 across prompt versions.** `analyze` (`scripts/judge_agreement. py:298-336`) computes every gate
over all paired rows; `by_prompt_version` is a `Counter` and `_render` appends "(MIXED — read the gates per version)" with nothing per version to read. The requirement is
the PR's own (`_deck_judge_prompt.py:125-130`). Fix: `{version: analyze(rows_of_that_version)}`; mark the pooled block informational when more than one version is
present. Routing: FOLLOW-UP.

**[B-06] minor · PARTIAL · NEW — the negation window drops affirmative prose on four cues.** The six synthetic false negatives reproduce (`against` as a POST cue eats
"great against control"; `drop\w*`, `skip\w*`, `nothing` as PRE cues eat "I drop tokens", "nothing but make tokens"). Quantified on the real corpus (Appendices A, B, C;
22.7k chars; 39 theme mentions): **0 affirmative mentions dropped**, 4 genuine negations dropped, and the one slug master emitted that the target does not (`enchantress`)
was wrong on master. Dropping is not the inversion's class of harm: a dropped mention contributes nothing to ≤ 2 additive soft-bias pages, whereas the inversion steered
toward the negated theme. Fix: remove `against`/`nothing` from the POST cues and `drop\w*`/`skip\w*`/`nothing` from the PRE cues (keep `against` as PRE); treat
`but`/`only`/`except` as scope breakers; add the six sentences and the three appendix slug lists as pins. Routing: FOLLOW-UP.

**[B-07] minor · CONFIRMED · NEW — a short first line starting with a win word is a "heading" and the paragraph under it is quoted.** Reproduced: `'Combo pieces I
cut\nFood Chain, … removed for budget.'` quotes the REMOVED list as "how it wins". `_is_heading_line` is shape-only (`primer.py:476-487`), `_WIN_HEADING_RE` matches a
leading win word (`:467-472`), the body is quoted whole (`:520-527`). The critic's first example is 8 words, fails the shape and is quoted by the keyword path — arguably
legitimately. Fix: require a `fullmatch` short title (≤ 4 words) or a markdown marker before quoting a body; pin both sentences. Routing: FOLLOW-UP.

**[B-08] minor · PARTIAL · NEW — a pre-R3 header-less sidecar with hand notes is overwritten on the first unchanged re-pull, under "upstream changed".** Reproduced: first
re-pull `refreshed`, notes gone; second `unchanged`. `store_primer_sidecar` (`primer.py:313-328`) compares the hash only when a header exists, and the import prints
"(overwrote the previous sidecar — upstream changed)" (`moxfield_import.py:1281-1282`). F-08's minimum (the import line) is printed; the docstring's own promise
(`:291-295`) is not implemented. The critic's fix — compare the stripped existing text with the new render — would not have saved the notes either (`"Original… \n\nMY
NOTES"` ≠ `"Original…"`). Population: Archidekt-lane imports between 2026-08-27 and this PR, hand-annotated, re-pulled once. Fix: in the header-less branch, if the
stripped old text equals or starts with the new render, write the header and keep the old text verbatim, reporting "unchanged (identity header added)"; otherwise replace
and say so honestly. Routing: FIX-NOW.

**[B-12] minor · CONFIRMED · NEW — the web/desktop import lane writes no primer sidecar.** `routes_decks.py:462-470` fetches the deck and never reads
`deck_json["description"]`; the exclusive create at `:544-545` writes the `.dck` only. F-06's fix line meant the CLI importer's two lanes (both done); `/api/import_deck`
is a third path the round-3 text did not name — but F-06's rationale applies to it verbatim, and these are exactly the decks a desktop user owns. Fix: after the create,
`store_primer_sidecar(target, deck_json.get( "description"), source_id=public_id)` with the CLI's WARN-on-`refused` handling and a `primer` field in the reply; pin with
Appendix C. Routing: FIX-NOW.

**[B-13] minor · CONFIRMED · NEW — terminal escape sequences in a description reach the terminal via `commander adopt`.** Reproduced: a "How it wins" paragraph carrying
`ESC[2J`, `ESC]0;… BEL`, `ESC[31m` → `render_adoption` output contains 5 ESC bytes and a BEL (`primer.py:184-185` passes non-Delta text untouched; `:533-535` quotes it;
`adopt.py:582-585` prints it). Author is the upstream deck owner; effect is a screen clear, title or colour. Fix: strip `[\x00-\x08\x0b-\x1f\x7f-\x9f]` in `parse_primer`
on both branches. Routing: FIX-NOW.

**[B-14] minor · CONFIRMED · NEW — a back-face `Protect=` protects nothing; the comment says either face works.** Executed: front face in both directions → equal; back
face → not equal; curly apostrophes → equal (F-10 holds); `Lim-Dûl's` vs `Lim-Dul's`, `Æther` vs `Aether` → not equal (pre-existing property of `name_key`; the tool's own
`.dck` matches itself). `match_key` (`collection.py:101-118`) keeps `split("//", 1)[0]`; `adopt.py:367-368` overclaims. Fix: fold both faces into the key set when
building `protected_keys`/`all_keys`, or correct the comment. Routing: FIX-NOW for the faces/comment; FOLLOW-UP for diacritic folding (a matching-semantics change).

### 2d. Web, import, config and the UI labels

**[B-02] minor · PARTIAL · FIX-INCOMPLETE(W-04) for the advisor sites, NEW for the CLI readers — `/api/audit` 503s and `/api/audit/stream` emits an error frame on a
cp1252 deck.** Reproduced (every other per-deck route → 200, including `/api/deck_audit`, which the critic conflated with `/api/audit`). `routes_audit.py:578, 719` read
tolerantly and then call `advise()`, which re-reads strictly at `improvement_advisor.py:567` and `:881` — so for the audit path the route migration is hollow. The CLI
readers the critic lists (`_proposer_cli.py`, `improve_search.py`, `archetype.py:388,868`, `meta_test.py`, …) are outside W-04's web scope. Fix: the two one-liners
(`dck_utils.read_deck_text`) plus a test that GETs `/api/audit?source=heuristic` on the W-04 fixture; sweep the CLI readers as a follow-up, `archetype.py` first (its
failure is swallowed into a silent "midrange"). Routing: FIX-NOW for the advisor sites; FOLLOW-UP for the sweep.

**[B-09] minor · PARTIAL · FIX-INCOMPLETE(W-10) — `PUT /api/deck_source` writes a bare-LF `Moxfield=` line into a CRLF deck.** Reproduced: endings `{CRLF: 8, bare LF: 1}`
after the PUT; the clear regex `^Moxfield=.+\n?` eats the CR and restores the original byte-for-byte. `routes_decks.py:863-877` uses `"\n"` literals and `^Moxfield=.+$`
(the `.` matches CR — the defect `_NAME_LINE` was rewritten to avoid). The mixed-file half is not a defect: LF metadata over CRLF cards is what master's `rewrite_name`
bug produced, and `set_bracket_unverified` collapsing it on the next mainboard save is repair; an unchanged PUT round-trips byte-identically. Fix:
`dck_meta.line_ending(text)` for the inserted line and `^Moxfield=[^\r\n]*\r?\n?` for replace/clear; pin through `/api/deck_source` with the W-10 CRLF deck. Routing:
FIX-NOW.

**[B-11] minor/low · PARTIAL · NEW — atomic writers replace a symlink with a regular file.** `os.replace(tmp, path)` swaps the link (`atomic_io.py:53-63`); master's
`write_text` followed it. W-08's fix line asked for `os.replace`, and nothing in the repo's docs suggests symlinking `config.json` — the one dotfiles mention argues the
opposite for the file holding the key. Parent mode: `mkdir(mode= 0o700)` applies at creation; not narrowing a pre-existing directory is the conservative choice. Fix:
`path = Path(os.path.realpath(path))` at the top of `atomic_write_text`; document the parent-mode choice. Routing: FOLLOW-UP.

**[A-05] minor · PARTIAL · NEW — "verdict floor" lands on the 10/pod option on a 4-pod host; tooltip says "cleared".** Re-run under node: `10/pod × 4 = 40 games (~20
decisive) — verdict floor | clears=true`; `P(Bin(40,½) ≥ 20) = 0.5627`. The rule `expected decisive ≥ floor` is the repo-wide convention the CLI applies to the same run
(`min_sim_games_for_verdict()` = 40; `_proposer_cli.py:104-111`). What the PR introduces is the wording "Verdict floor is 20 decisive: cleared." (`app.js:626`) — an
expectation stated as a fact — and the static placeholder at `index.html:366` says the opposite until `/api/sim_settings` answers. Fix: `clears = decisive > floor` (or a
one-sigma margin) and "expected to reach the 20-decisive floor (≈56 % of runs do)"; keep CLI and web on one rule. Routing: FIX-NOW.

**[A-06] minor · PARTIAL · NEW — the run-status line prints the per-pod count; the rewritten label is wrong in 1v1 mode.** The status line (`app.js:819-820, :894-895`,
"Running ${games} pod games") is byte-identical to master and outside C-11's ask. The 1v1 half is the PR's: `compare()` builds one pod in 1v1 mode (`compare_versions.py:
876-878`), `routes_sim.py:471` says `filler_pairs` is ignored there, and `applySimSettings` (`app.js:631-647`) never reads the mode radio, so a 40-game 1v1 run is
labelled `40/pod × 4 = 160 games`. Fix: recompute labels on mode change with `pods = 1` for 1v1; derive the status line from `describeGamesOption(games, settings).total`.
Routing: FIX-NOW for the 1v1 label; the status line rides along.

**[A-10] minor · CONFIRMED · NEW — `save_iteration` drops `price_partial` when the caller supplies its own `pricing` block.** `routes_sim.py:882-899` validates the flag
but writes the marker only inside `if "pricing" not in audit_manifest:`; a caller supplying both gets 200 and a row `status.py:428-435` renders as a whole total. The
shipped UI never sends a `pricing` key, so only API/CLI callers hit it. Fix: set `pricing["partial"] = True` on the caller's block too (a bool marker, nothing to lose),
or 400 the combination. Routing: FIX-NOW.

**[A-11] minor · CONFIRMED (bounded) · NEW — the dashboard tile's `price_partial: False` excludes lands by construction.** `deck_dashboard.py:370-374` skips lands before
the price step (pre-existing); `price_deck_text` prices every card including lands and the commander. Two surfaces now give two `partial` answers, and the subtitle says
"N priced cards", not "non-land cards". A land with no snapshot has an empty `type_line` and IS counted unpriced; only a trimmed-schema land is silently skipped. Fix: the
label ("N priced non-land cards") and counting trimmed lands in `n_unpriced_cards`; pricing lands on the tile is a product change. Routing: FOLLOW-UP.

### 2e. Scraper and capture lane

**[B-10] minor · CONFIRMED, numbers corrected · NEW — the payload parser has no completeness check.** On the checked-in fixture the seven colour entries carry W 7 · U 10
· B 10 · R 3 · G 7 · Multi 4 · Colorless 12 = 53 names. Losing any one entry except Colorless (43–50 names, overlap 0.811–0.943) still passes the 80 % gate, is cached for
7 days and served; only the Colorless loss fails closed (41 names, 0.774). The gate is master's pre-registered bar (round 3's F-15 recorded the same property) and audit
bug 1 asked the parser to read the payload, not the gate to change; the critic's two layout drifts are plausible CMS changes. Fix: trust the payload only when all seven
`Game Changer Wiki <colour>` entries matched with ≥ 1 name each; never harvest the Info entry; keep the 80 % gate as the second line. `CACHE_PATH` at `v2` is fine — only
trusted results are cached. Routing: FOLLOW-UP.

**[B-15] minor · CONFIRMED · FIX-INCOMPLETE(F-17) — no `workflow_dispatch`; the capture lane is push-triggered on this PR's branch.**
`.github/workflows/fetch-archidekt-capture.yml:16-19` is byte-identical to master; the default branch is `master`, so after merge the branch named in `on.push.branches`
disappears and a `request.txt` push to master triggers nothing — F-17's exact condition. The header comment (`:12-15`) explains why dispatch is registered only from the
default branch, which is precisely why it must be added before merge. Fix: add `workflow_dispatch:` with a `request` input (or a `push` on `master` with the same `paths:`
filter), keeping the push trigger that produced `010edd7`. Routing: FIX-NOW.

---

## 3. Merge interactions with #85 and #84

Verified by `git merge-tree --write-tree` in a throwaway clone (never the real checkout), merge base `0b944ef` for both:

- **#86 × #85: 12 content conflicts** — `docs/CHANGELOG.md`, `docs/architecture.md`, `docs/future-plans.md`, `_deck_judge_prompt.py`, `adopt.py`, `deck_dashboard.py`,
  `improvement_advisor.py`, `primer.py`, `web/routes_decks.py`, `tests/test_adopt.py`, `tests/test_desktop.py`, `tests/test_primer.py` (auto-merged: `config_store.py`,
  `staples.py`, `web/app.py`, `app.js`, `index.html`, `tests/conftest.py`).
- **#86 × #84: 1 conflict** — `docs/CHANGELOG.md` (auto-merged: `routes_decks.py`, `app.js`, `index.html`, the four shared test files).

What breaks in each order:

1. **adopt auto-Protect (R3-D1).** #86 keeps and extends it — DFC links now match via `match_key` and are unioned into `protected` (`adopt.py:492-494`, pinned); #85
   removes it ("references only", `cb-pr85 adopt.py:68-73`, still `casefold()` at `:164-165`). #86 first: #85's rebase conflicts in `adopt.py`/`test_adopt.py`, and
   resolving toward "references only" fails #86's DFC pin and the "belongs to another deck" protection pin. #85 first: #86's rebase re-introduces auto-Protect and #85's
   reference-only tests fail. Neither order is mechanical; **R3-D1 must be decided before either rebase** — unchanged from round 3, still USER-DECISION.
2. **`quoted_win_lines`.** Two independent rewrites of one function (`primer.py` conflict): #85's `_primer_tokens`/`_heading_kind` with excluded sections; #86's
   word-bounded keyword plus shape-only heading (B-07), pinning the PR-03 over-exclusion against #85's design. The merge must pick one and port the other's pins; stacking
   them is what F-12 forbade.
3. **BOM.** #86 strips it in `read_deck_text` (`dck_utils.py:52-58,100`); #85's `normalize_dck_cards` raises `ImportFormatError` on a BOM'd first line. #86 first: on-disk
   BOMs never reach #85's normaliser, so its 400 fires only for a BOM pasted into the editor — coherent. #85 first: a BOM'd deck 400s on every PUT until #86 lands. The
   FIX-PR85 half ("accept the BOM rather than 400") is owed by #85 in both orders.
4. **`deck_dir` consumer.** #86 validates at PUT; #85's `create_app` calls `get_deck_dir(...)` (`cb-pr85 web/app.py:211-216`) with no `deck_dir_problem` check. A value
   stored before the fix crashes startup in both orders (`ValueError: embedded null byte`, executed by critic B). No file conflict — the gap is silent. The FIX-PR85 half
   of W-07 is owed by #85.
5. **Instance-lock fixture.** #86's autouse env var + `_FakeLock` vs #85's conftest `instance_lock` (a real lock in `tmp_path`); `test_desktop.py` conflicts. Both satisfy
   W-12; whichever lands second drops its duplicate rather than merging both into one test.
6. **`/api/deck_commander` (#84, R3-D3).** No source conflict, but #84's route reads `path.read_text(encoding="utf-8")` (`cb-pr84 routes_decks.py:563`, and `:457, 515,
   996, 1094, 1230`), so a cp1252 deck 500s the new editor in either order until it is switched to `read_deck_text` — B-02's class lands in #84's editor. Its PUT imports
   `atomic_write_text` from `_helpers`, which #86 re-exports (`web/_helpers.py:410`) — compatible; #86's request gate and 8 MiB cap apply to it automatically.
7. **`live` marker / `--run-live`.** Byte-identical hunks; clean.
8. **Shared test files.** Append-only, auto-merge. #86's module-level `pytestmark` governs #84/#85's appended tests in `test_web_app.py` and `test_deck_dashboard.py` (two
   of the four, corrected from the critic's four); in all four the autouse `network_block` applies, so any appended test expecting a real socket fails loudly after
   rebase.

R3-D1 is the dependency: items 1 and 2 cannot be resolved by either PR author, and the `adopt.py`/`primer.py`/`test_adopt.py` conflicts do not have a mechanical
resolution until it is decided.

---

## 4. Routing summary

| Routing | Count | Items |
|---|---|---|
| FIX-NOW | 18 | A-01, A-02, A-03, A-05, A-06, A-07, A-09, A-10, B-01, B-02, B-03, B-04, B-08, B-09, B-12, B-13, B-14, B-15 |
| FOLLOW-UP | 11 | A-04, A-08, A-11, A-12, A-13, B-05, B-06, B-07, B-10, B-11, B-18 |
| USER-DECISION | 0 | (R3-D1 and B-16's POST-only alternative remain open from round 3) |

**FIX-NOW, in the order the fixer should take them** (ordering constraints are marked):

1. B-15 — `workflow_dispatch:` on the capture workflow (must land before merge).
2. A-01 — `fallback=mox_id or stable_deck_stem(...)` at `status.py:482`; pin the missing path.
3. A-02 **then** A-03, one patch — `_ids_for_stem` merge in `verdict_breakdown_route` and `pricing_series_route` first, then the writer resolves the stable id. Never the
   writer alone.
4. A-07 — symmetric `intent_ward` branch; pin the mirror.
5. A-09 — `inconclusive` bucket in `stats_summary` + the `status.py` line.
6. A-10 — `pricing["partial"] = True` on a caller-supplied block (or 400).
7. A-05 + A-06 — `decisive > floor`, "expected to reach" wording, 1v1 `pods = 1`, status line from `describeGamesOption(...).total`.
8. B-01 — tolerant sidecar reader at `primer.py:369/:382/:443`, `(OSError, ValueError)`, `:419` → `read_deck_text`; keep `--preferences` on a bare `Intent` when
   `learn_intent` fails.
9. B-02 — `read_deck_text` at `improvement_advisor.py:567` and `:881`; test `/api/audit?source=heuristic` on the W-04 fixture.
10. B-03 — thread `intent_themes`/`free_text_themes` into the bandit's `advise()`; pin the call.
11. B-04 — reword the fence docstring; neutralise in-band fence-shaped lines in `_fence_free_text`; extend the pin.
12. B-08 — header-less branch keeps hand notes when the old text equals or starts with the new render; honest message otherwise; pin E29.
13. B-09 — `line_ending(text)` and `[^\r\n]` regexes in `deck_source`; pin through the route with the W-10 CRLF deck.
14. B-12 — `store_primer_sidecar` after the exclusive create in `/api/import_deck`; `primer` field in the reply; pin with Appendix C.
15. B-13 — control-character strip in `parse_primer`, both branches.
16. B-14 — both DFC faces in the adopt key set (or correct the comment).

**FOLLOW-UP:** A-04 (UTC-date filtering in the era report; classifier only with a pinned offset table), A-08 (floor gate before the LLM rung; unknown label → parse
failure), A-11 (tile label; count trimmed lands as unpriced), A-12 (`margin = NULL` on the legacy shape, or document the shape test), A-13 (`NOTE:` +
`fillers_overridden`), B-05 (per-version gates), B-06 (four cues + scope breakers + corpus pins), B-07 (heading `fullmatch`/markers), B-10 (seven-entry completeness
check), B-11 (`realpath` in `atomic_write_text`), B-18 (`match_key` at the proposer's two cut-guard sites), plus the B-02 CLI reader sweep and B-14's diacritic folding.

---

## 5. What held

No round-3 fix was found un-done except the three FIX-INCOMPLETE entries above, and no holding entry from either critic was overturned by the cross-examiner.
Consolidated:

- **Core (critic A):** C-01 heuristic rung, C-02, C-03 auto-pick paths, C-04, C-05, C-06, C-07 `side` column, C-08 CLI writers + backfill (dry-run writes nothing; second
  `--apply` is a no-op), C-09, C-10, C-12 as asked, C-13, C-14 writers and readers (mixed 0/NULL db renders without error), S-1, S-3, S-4, audit bug 3 for TCP/DNS, audit
  bug 2 on the non-land path (3 priced / 2 trimmed / 1 missing through the real `lookup_card` → total 15.10, `n_unpriced 4`, `partial True` carried to the audit payload,
  the stored row and `commander-status`).
- **FP-018 (critic B):** F-01 greedy plumbing end to end (`learn_intent` → fence → `--free-text-themes` → `advise(free_text_themes=)` → extra pages), F-02 front face,
  F-03 tribe slot with the real `advise`, F-04 boundaries and genuine negations (0 affirmative drops on 22.7k chars of real primer prose), F-05 fence + version stamp at
  the only `JudgeReport(` constructor, F-06 both CLI lanes, F-07, F-08 headered sidecars, F-09 (cold cache → `skipped` with the remedy), F-10 in adopt, F-11, F-13 (now
  load-bearing: 8 candidates, `== 5`), F-14, F-15 with `staple_list_source`, F-16, F-18.
- **Web/CLI/desktop (critic B):** W-01, W-02 on a loopback server (no headers → 200; `same-site`/`cross-site`/foreign `Origin` → 403; loopback `Origin` in any case/port →
  200; `/` and `/static/*` never gated), W-03, W-04 for every route it named, W-05 (U+202E, U+0085, U+200B, `..`, NUL → 400, 300 chars → 400, 8.1 MB → 413), W-06, W-07 at
  PUT, W-08, W-09 all five sites, W-10 `deck_text` PUT, W-12, W-13, audit bug 1 on the real 421,488-byte page (53/53, trusted; legacy `<li>` scan → 5 chrome strings;
  cache written only when trusted).
- **Interactions:** the merge-tree conflict sets and items 1–7 hold as filed; item 8 holds for two of the four shared test files.

### Tests run (all offline, Linux, fast lane unless noted)

| Lane | Scope | Result |
|---|---|---|
| Explainer, full suite | `pytest --run-slow -q` on `d554270` | **4,588 passed, 0 skipped** in 49.9 s |
| Explainer, fast lane | `pytest -q` | **4,420 passed, 168 skipped** in 44.0 s |
| Critic B baseline | `test_intent`, `test_primer`, `test_adopt`, `test_game_changers`, `test_dck_meta`, `test_config_store`, `test_deck_identity` | **209 passed, 2 slow-skipped**; judge/moxfield/agreement/web subsets **21 + 51 passed** |
| Critic A | per-id subsets (`-k confirmation`, `-k filler`, `-k alignment or refuses`, `-k provenance`, `-k mutual or agreement`, `-k non_integer or whole_number`, `test_backfill_deck_ids`) | all passed; every A-* finding is outside the PR's own pins |
| Probes | 5 cross-examiner scripts + 3 critic-B scripts re-executed verbatim; `a02.py` runs the real app and the real backfill | outputs quoted in §2 |
| Merge test | throwaway clone, `merge-tree --write-tree` against #85 and #84 | 12 / 1 conflicts (§3) |

Not run: any JVM/Forge path (B-18 is source + unit-executed only), any live-model path, Playwright (no Chromium in the sandbox), mutation testing of "every fix carries a
test that fails without it".

---

## 6. Corrections ledger

Where the cross-examiner corrected a critic. As in rounds 2 and 3 the critics were right on mechanism and repeatedly wrong on reach; this round adds a new category — a
critic's *fix* being wrong.

1. **A-03's fix is mis-ordered.** Storing the stable id in `save_iteration` before the readers merge blanks the verdict pills and the price sparkline for every deck
   immediately, with no backfill involved. Readers first.
2. **B-08's fix does not save the notes it demonstrates.** Text equality between the stripped old sidecar and the new render fails the moment a note is appended; only
   "equals or starts with" keeps them.
3. **B-04's hash width is irrelevant.** The only verifier computes no hash; neutralising fence-shaped lines inside the payload is the fix, and a per-panel nonce is
   optional.
4. **A-02 is broader than filed and less harmful than filed.** Every Moxfield/Archidekt-imported deck with web history is re-keyed, not only versioned ones; nothing is
   lost, two of four readers already merge, `parent_id` is untouched.
5. **A-08 has no referent in production.** No CHANGELOG text describes a product configuration with the analyst's LLM rung enabled; the analyst's LLM flag defaults off
   and every caller leaves it there. The "coercions" are master's lines verbatim.
6. **A-12's reader half does not exist.** `margin_analysis.py` reads soak JSONL, never the knowledge log; no in-tree reader pools `iterations.margin`.
7. **B-02 conflated `/api/deck_audit` with `/api/audit`.** The former (legality scan) returns 200; the latter (advisor) 503s because of two strict reads beneath the
   migrated route.
8. **B-06's rate is synthetic.** Six crafted sentences reproduce; on the real corpus 0 of 39 mentions were wrongly dropped, and the one slug master emitted that the
   target does not was master's error.
9. **B-10's numbers were off by one** (43–50 names, not 42–49) and the Colorless loss fails closed, which the critic did not test.
10. **B-01/B-02 and A-02/A-03 were majors only on a fresh scale.** Held to round 3's W-04 (minor, external editor) and C-08 (major, every surface) ratings, both pairs are
    minor.
11. **Interaction item 8 counts two files, not four.** The module-level `pytestmark` is in `test_web_app.py` and `test_deck_dashboard.py`; the autouse `network_block` is
    what governs all four.
12. **B-18 was under-filed, not over-filed.** The one promotion of the round: a suspected note turned out to be the proposer's cut guard — the path that actually cuts —
    still keyed on `lower()`.

---

## 7. On the exercise itself

Round 4 is the first round that reviewed the reviewer's own fixes: the 44 items and three bugs under attack were written in response to round 3's report, by the same
process that wrote the report. Three things it showed.

**The fixes held.** 42 of 47 were done as asked and pinned; the two narrower ones (C-08's unread `Source=`, C-11's labels-only scope) were reasonable readings; the three
incomplete ones are one YAML line, two one-line reads and one regex. No critical, no major, no refuted claim, and — for the first time in four rounds — zero USER-DECISION
items, because the fixes implemented decisions rather than making new ones. The PR body's numbers matched the tree exactly wherever the tree could be asked.

**The residue is the same shape one layer down.** Round 2's majors were fixes at two of three sites; round 3's were decisions on one of four paths. Round 4's minors are
asks met on the named path and missed on the unnamed one beside it: the `.dck` read migrated but not the sidecar read (B-01) or the advisor beneath the route (B-02); the
importer's two lanes but not the UI's third (B-12); the greedy strategy but not the bandit (B-03); adopt's key but not the proposer's (B-18); one PUT's line endings but
not the other's (B-09); the C-12 case but not its mirror (A-07). Every one of these was findable by asking "where else does this same read/write/compare happen?" — the
question the fix author did not ask after answering the finding. The one true regression (A-01) came from routing a call through a new shared function without checking
the function's raise branch against the caller's documented contract.

**What it says about reviewing your own work.** The self-review found nothing structural because there was nothing structural to find, and it found 28 minors because a
hostile pass with a fixed contract ("was the `Fix:` line done, and what sits beside it?") is a different instrument from the pass that wrote the fixes. The critics'
over-grading (6 majors, all downgraded against round 3's own scale) is the cost of that instrument; the calibration rule — rate against the prior round's ratings, not a
fresh scale — is what kept the severity honest, and it should be stated up front in round 5's brief. The cross-examiner's three fix corrections (A-03, B-08, B-04) are the
new lesson: a critic who executes the bug does not necessarily execute the fix, and the round should require both.

Round 5, if there is one, should start after R3-D1 is decided and #86 is merged with the FIX-NOW list applied — then review the merged tree with #85 rebased, where items
1–2 of §3 will have been resolved by a human and can be attacked as decisions rather than as conflicts.
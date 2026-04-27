# STATUS.md — mtga_draft_helper

> Operational state of the project. Read this file first to find out
> "what's the project up to right now?" without scrolling chat history.
>
> **Three sections** — *Now* (active work), *Recent* (last few days),
> *Blocked* (paused on something external). For roadmap items see
> [FUTURE_PLANS.md](FUTURE_PLANS.md). For one-time data hygiene see
> [DATA_CLEANUP.md](DATA_CLEANUP.md).

**Last updated**: 2026-04-27 (autonomous-improvement session)
**Project shape**: dual-codebase — legacy draft helper (top-level)
+ in-game advisor (`game_advisor/`)

---

## Now

### Working on
Nothing actively in flight. The 2026-04-27 session landed:

- **`FUTURE_PLANS.md`** — strategic roadmap (FP-A through FP-G) with
  current take and unblock conditions on each.
- **`DATA_CLEANUP.md`** — prioritized cleanup options with status
  checkboxes. Option 1 (gitignore tightening) applied; Options 2 and
  3 (`git rm --cached` and tracking launchers) await user approval.
- **FP-A: shared `mtg_cards/` oracle store integration** — `card_db.py`
  now consults `C:\dev\mtg_cards\oracle_snapshots\` first for oracle
  text, cmc, type line, and mana cost. Falls back to local cache on
  miss. 16 new tests in `game_advisor/tests/test_card_db_shared_store.py`.
- **FP-B: oracle-text in LLM prompt** — `llm_advisor.card_text_appendix()`
  adds current Oracle text for cards in hand + opponent's board to the
  LLM prompt. The LLM now reads authoritative card text, not its
  training-data memory of cards. 6 new tests.
- **FP-D: legacy code test coverage** — **132 new tests** at top level
  for `card_db.py` (23), `deck.py` (20), `ratings.py` (25),
  `synergy.py` (29), `log_scanner.py` (17), and `mtga_local_db.py` (18).
  Was 0 before. First-ever automated regression coverage for the
  draft-helper code, including: Bayesian smoothing, fuzzy lookup,
  grade-threshold arithmetic, mulligan/curve/colors scoring,
  synergy-bonus rule firing, BREAD evasion+removal grading,
  deck-skeleton penalties (curve-target deviation), enabler/payoff
  gap rewards, removal-scarcity scaling, EventJoin /
  InternalEventName parsing for resumed drafts, double-encoded JSON
  payload extraction, MTGA-internal mana cost decoding (`o2oWoW` →
  `{2}{W}{W}`), CMC arithmetic with X-as-zero, and type-line assembly.
- **Bug fix in `card_db.get_subtypes`** — was reading `_type_line`
  directly, bypassing the new shared-store fallback. Now goes through
  `get_type_line()` so errata'd subtypes (Phyrexian / Demon-Devil
  rebrandings) reach the result.

### Up next
Highest-leverage next work, ranked:

1. **DATA_CLEANUP Option 2 + 3** — Need user approval to:
   - `git rm --cached` the 10 `__pycache__/*.pyc` files, the two large
     cache JSONs, the 4MB screenshot, and the per-user
     `settings.local.json`.
   - `git add` the launcher .vbs/.bat files and `draft_advisor.py`
     (which is live code never committed — see DATA_CLEANUP.md).
2. **More legacy tests (FP-D continuation)** — `log_scanner.py`,
   `synergy.py`, `ratings.py` still have no top-level tests. Each is
   ~3–5h to cover meaningfully.
3. **FP-C (consolidate dual codebase)** — biggest architectural lift,
   ~12–20h. Defer until concrete duplication-pain bites.
4. **FP-E (SQLite for `arena_id_cache.json`)** — corruption-safety
   refactor. Pre-emptive; defer until a corruption actually happens.

### Cross-project context
This project is one of three sibling MTG projects under `C:\dev\` (and
this folder under `C:\Users\pilot\OneDrive\Documents\Python Scripts\`):

- `commander_builder` — Forge JVM driver for Commander deck testing
- `forge_py` — Python goldfish + (incoming) turn-by-turn engine
- `mtg_cards/` — **shared card-data folder** (data substrate)

This project's `card_db.py` now reads from `mtg_cards/oracle_snapshots/`
via the same `MTG_CARDS_DIR` env var the sister projects use. See
[FUTURE_PLANS.md](FUTURE_PLANS.md) FP-G for the long-term unified
application vision.

---

## Recent (last 7 days)

### 2026-04-27 (autonomous-improvement session)
- Adopted shared `mtg_cards/` data folder (FP-A) — card_db's oracle
  lookups now hit the shared store first for current Scryfall data.
- Added oracle-text appendix to LLM prompt (FP-B) so the in-game
  advisor reads authoritative card text post-errata.
- Wrote first-ever top-level tests (FP-D) — 43 tests covering
  `card_db.py` and `deck.py` (was 0 tests at top level before).
- Tightened `.gitignore` to exclude cache JSONs, screenshots, runtime
  logs, and per-user lockfiles. Option 2 (`git rm --cached`) deferred
  for user approval.
- Wrote FUTURE_PLANS.md (FP-A through FP-G) and DATA_CLEANUP.md so
  future sessions can pick up state cold.

### Earlier (recent commits)
- Concede / quit detection via dual-source fallback (commits 07237dd, 36583da)
- Post-loss LLM game analysis (72f2961)
- Board count + empty placeholder in dashboard (b85a381)
- SQLite thread-safety fix for read-only path (2b34098)

---

## Blocked

Nothing currently blocked.

DATA_CLEANUP Options 2 and 3 are *waiting on user sign-off*, not
externally blocked — they're destructive enough to want explicit
approval.

---

## Stats

| Project area | Modules | Tests | Notes |
|---|---|---|---|
| Top-level (legacy draft helper) | ~13 | **132 (NEW)** | Was 0; covers `card_db` (23) + `deck` (20) + `ratings` (25) + `synergy` (29) + `log_scanner` (17) + `mtga_local_db` (18) |
| `game_advisor/` (in-game advisor) | ~13 | **122** | +22 this session |
| **Total** | **~26** | **254** | |

- Wall time: ~0.1s top-level + ~2s game_advisor.
- CLI entry points: `python main.py` (draft helper),
  `python game_advisor/main.py` (game advisor).
- Launchers: 2× tracked, 2× untracked (per DATA_CLEANUP.md Option 3).
- Shared data: `C:\dev\mtg_cards\oracle_snapshots\` (~32k Scryfall
  card snapshots) via `MTG_CARDS_DIR` env var.

---

## How to update this file

- Move items between *Now* / *Recent* / *Blocked* as state changes.
- *Now* should always have ≤ 3 active items. If more, prune to the
  truly active ones.
- *Recent* is rolling — keep ~7 days, archive older into a date-stamped
  archive when the section gets unwieldy.
- *Blocked* is for things waiting on external events (API access,
  decisions from the user, sample-size accumulation). If nothing is
  blocked, the section should literally say so.

Don't make this file a duplicate of `FUTURE_PLANS.md`. FUTURE_PLANS is
the strategic roadmap; STATUS is the operational snapshot.

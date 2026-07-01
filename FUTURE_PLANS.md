# FUTURE_PLANS.md — mtga_draft_helper

> Strategic roadmap for the MTGA draft helper + game advisor. Items here
> are deliberately **out of the active queue** — bigger bets, blocked
> items, and architectural forks. Move things from here into a `BACKLOG.md`
> when an unblock condition fires.
>
> Each entry: **What** (proposal), **Why it might matter**, **Cost**
> (honest scope), **What would unblock it**, **Current take**.
>
> Living doc, written 2026-04-27. Update as state changes.

---

## Project shape (updated 2026-06-30 — FP-C landed)

The codebase has **two halves living in separate packages**
(`draft_helper/` and `game_advisor/`) that share one module
(`card_db.py`) and coexist as two entry points of one Arena program:

### Half 1: Draft-pick overlay (`draft_helper/` package)

- Files: `draft_helper/main.py`, `api.py`, `card_db.py`, `deck.py`,
  `draft_advisor.py`, `log_scanner.py`, `mtga_local_db.py`,
  `overlay.py`, `ratings.py`, `synergy.py`, `calibrate.py`,
  `capture.py`, `card_detector.py`, `config.py`
- Entry: `python main.py` (thin repo-root shim over
  `draft_helper.main.main()`) — reads Arena Player.log, fetches
  17lands GIH ratings, shows letter-grade overlay on draft picks
- Caches (repo root, gitignored): `arena_id_cache.json`,
  `ratings_cache.json`
- **196 tests** in `tests/` (was 0 before FP-D).

### Half 2: In-game advisor (`game_advisor/` package)

- Files: `game_advisor/main.py`, `dashboard.py`, `decision_log.py`,
  `deck_manager.py`, `decklist.py`, `game_state.py`, `llm_advisor.py`,
  `log_scanner.py`, `math_utils.py`, `rule_engine.py`, plus capture
  helpers
- Entry: `game_advisor/main.py` — reads Arena Player.log during matches,
  builds game state, LLM-driven decision advice (Ollama backend,
  Claude API optional)
- **122 tests passing** across `game_advisor/tests/`
- Persistence: `game_advisor/saved_decks.json` (user decks),
  `game_advisor/logs/` (decision logs per game, currently empty)
- Imports the shared `card_db.py` as `from draft_helper import card_db`
  (FP-C) — no more sys.path-shadowing workarounds.

`pytest tests/ game_advisor/tests/` runs both suites together
(318 tests) in one invocation since FP-C.

### Sister projects (and how this project relates to them)

- This project's two halves — top-level draft helper + `game_advisor/`
  in-game advisor — **work together as one Arena program**. Treat them
  as a single product from a planning perspective; they happen to live
  in two directories for historical reasons. FP-C below tracks their
  eventual code-level consolidation.
- `C:\dev\commander_builder\` — Forge JVM driver for Commander deck testing.
  **Separate from this project today.**
- `C:\dev\forge_py\` — Python goldfish + (incoming) turn-by-turn engine.
  **User intent (2026-04-27):** "when forge_py works well I do want it
  in commander_builder." So forge_py is a spike that's expected to fold
  into commander_builder once Phase 1 (turn-by-turn) is producing useful
  signal. Tracked symmetrically in `commander_builder/FUTURE_PLANS.md`
  FP-001.
- `C:\dev\mtg_cards\` — **shared card-data folder** (Scryfall bulk +
  per-card oracle snapshots + Magic Comp Rules). Created 2026-04-27 to
  consolidate card caches across all three project trees.

---

## FP-A — Adopt the shared `mtg_cards/` folder for oracle text ✅ DONE 2026-04-27

**What landed.** `card_db.py` now consults the shared
`C:\dev\mtg_cards\oracle_snapshots\` store **first** for oracle text,
cmc, type line, and mana cost. Falls back to the legacy local cache
when the shared store has no entry, when the shared dir is unset
(`MTG_CARDS_DIR` env var override), or when the snapshot is corrupt.

New helpers in `card_db.py`:
- `_resolve_shared_cards_dir()` — env var → canonical `C:\dev\mtg_cards`
  → None.
- `_shared_snapshot_path(card_name)` — slugifies the name,
  returns the snapshot file path.
- `_load_shared_snapshot(card_name)` — returns the projected card
  dict or None on miss/corruption.

The four public lookup functions (`get_oracle`, `get_cmc`,
`get_type_line`, `get_mana_cost`) all check shared store first then
fall through to local cache. **No changes needed in callers** — the
behavior is transparent.

**16 new tests** in `tests/test_card_db_shared_store.py` covering
env-var resolution, slug computation, shared-store priority, fallback
paths, corrupt-snapshot handling, missing-field handling, and CMC
float→int coercion.

**Test isolation.** Three existing test fixtures
(`test_card_helpers.py`, `test_card_helpers_card_db.py`,
`test_log_scanner.py`, `test_rule_engine.py`) updated to monkeypatch
`_resolve_shared_cards_dir` to None, so synthetic test data stays in
charge of `_oracle`/`_type_line`/etc. dicts.

**Smoke validation (2026-04-27).** Sol Ring, Lightning Bolt, Forest,
Cultivate all return current Scryfall oracle text, cmc, mana cost,
and type line. The shared store has ~32,000 card snapshots covering
basically every Standard / Pioneer / Modern / Commander card.

---

## FP-B — Oracle-text-first card reference ✅ DONE 2026-04-27

**What landed.** New `card_text_appendix(state)` in `llm_advisor.py`
adds an oracle-text reference block to the LLM prompt. Includes
oracle text for cards in your hand (the playable choices) plus
opponent's board (the threats you're responding to). Each entry
truncated to 200 chars; whole-state capped at 12 cards.

```
T4 Main 1 | You 18hp | Opp 14hp | Board:[Goblin~(1/1)] | Opp:[Dragon(5/5 flying)] | Hand:[Shock({R})*] | Mana:2

Card text reference (current Oracle):
  - [hand] Shock: Shock deals 2 damage to any target.
  - [opp-board] Dragon: Flying. When this enters, deal 5 damage…
```

Source via `card_db.get_oracle()`, which now uses the shared
store (FP-A). So the LLM sees **post-errata oracle text** rather
than relying on its training-data memory of what cards "used to" do.

**6 new tests** for the appendix: empty state, hand-card inclusion,
opponent-board-card inclusion, truncation, newline collapsing,
deduplication.

**Cost.** Each appendix entry is ~50–250 prompt chars. A typical
turn (7-card hand, 3 opp threats with oracle data) adds ~1.5k chars
to the prompt — a noticeable but acceptable token overhead given
the accuracy gain on errata'd cards.

---

## FP-C — Merge legacy draft helper into `game_advisor/` package ✅ DONE 2026-06-30

**What landed.** The 14 top-level files (`main.py`, `api.py`,
`card_db.py`, `card_detector.py`, `config.py`, `deck.py`,
`draft_advisor.py`, `log_scanner.py`, `mtga_local_db.py`,
`overlay.py`, `ratings.py`, `synergy.py`, `calibrate.py`,
`capture.py`) moved into a proper `draft_helper/` package
(`__init__.py` + relative imports between siblings). This turned out
to be a much smaller lift than the original estimate — the
"namespace collision" was never a real Python packaging problem
(`game_advisor/` already ran as its own script directory with its
own `config.py`/`log_scanner.py`/`capture.py`); it only became a
*pytest* collision when both suites were collected in one invocation,
because both used bare, unqualified imports. Once `draft_helper/` is
a real package, `from draft_helper import card_db` is unambiguous
and the collision disappears structurally — no file renames needed.

**What did NOT land (correctly deferred).** The "extract shared
`mtga_common/` infrastructure" and "single `pyproject.toml`" parts of
the original proposal were skipped — the two log scanners parse
genuinely different log content for different purposes (draft-pick
detection vs. live game state), so merging them would be speculative
work, not real deduplication. `card_db.py` was already the one
genuinely shared module and needed no extraction, just a cleaner
import path.

**Concrete changes:**
- Root `main.py` and `calibrate.py` are now thin shims
  (`from draft_helper.main import main`) so `python main.py` /
  `python calibrate.py` and the existing `.bat`/`.vbs` launchers work
  unchanged.
- `game_advisor/main.py`, `card_helpers.py`, `capture.py`,
  `dashboard.py`, `decklist.py`, `log_scanner.py`, `rule_engine.py`,
  `llm_advisor.py` now import the shared module as
  `from draft_helper import card_db` instead of a fragile
  sys.path-reinsertion dance that re-asserted `game_advisor/` at
  `sys.path[0]` before every import that might get shadowed.
  `llm_advisor.py`'s manual `importlib.util` load of its own
  `config.py` (to dodge the same shadowing) was simplified back to a
  plain `import config`.
- **Real bug fix found along the way:** `card_db._CACHE_FILE` and
  `config.RATINGS_CACHE_FILE` derived their paths from
  `pathlib.Path(__file__).parent`, which — once the file moved into
  `draft_helper/` — would have silently pointed cache reads/writes at
  `draft_helper/arena_id_cache.json` instead of the existing
  repo-root cache, orphaning the user's warm cache on next run. Fixed
  to `.parent.parent` (repo root). Same class of bug in
  `draft_advisor.py`'s `.env` file lookup (was resolving to
  `draft_helper/game_advisor/.env` instead of `game_advisor/.env`).
- All test imports (`tests/*.py` and 6 files in `game_advisor/tests/`
  that reached into the shared `card_db`) updated to
  `from draft_helper import ...` / `monkeypatch.setattr("draft_helper.card_db...")`.
- **The doc'd blocker is resolved:** `pytest tests/ game_advisor/tests/`
  now runs both suites together in one invocation — 318 tests pass.
  Previously this required two separate invocations
  (`pytest tests/` then `pytest game_advisor/tests/`) due to the
  bare-import shadowing.

---

## FP-D — Test coverage for legacy draft helper ✅ DONE 2026-04-28

**Resolution.** 50+ test target met and exceeded. Top-level
`tests/` directory now ships **196 tests** across nine files:

- `test_api.py` — 25 tests for the 17Lands client (mocked HTTP)
- `test_card_db.py` — 26 tests for card-name caching, oracle lookup,
  ID resolution + atomic-rename save path
- `test_card_detector.py` — 16 tests for peak finding + grid
  detection (with synthetic numpy images)
- `test_deck.py` — deck object ops + color counting
- `test_draft_advisor.py` — 15 tests for `should_explain` decision
  logic + LLM prompt builders
- `test_log_scanner.py` — 17 tests for Arena Player.log parsing
- `test_mtga_local_db.py` — local card DB
- `test_overlay.py` — 6 tests for `OverlayApp.grid_centers`
- `test_ratings.py` — 25 tests for grading + Bayesian smoothing
- `test_synergy.py` — pick recommendation logic

Real bug found along the way: `card_db._save_cache` had no atomic
rename, so a crash mid-write left the 1.6MB arena_id_cache.json
truncated and unreadable on next startup. Fixed via .tmp +
os.replace pattern with regression tests.

Run via `pytest tests/`, or together with `game_advisor/tests/` in one
invocation now that FP-C resolved the import-shadowing collision.

---

## FP-E — Replace legacy `arena_id_cache.json` with SQLite

**What.** The 1.6MB `arena_id_cache.json` is loaded fully into memory
on every startup. SQLite would let us:

- Index by Arena ID (currently a linear-ish dict scan for some queries)
- Atomically add/update single entries instead of rewriting the whole
  file (which currently risks corruption on crash mid-write — there's
  no atomic-rename in the save path)
- Share across processes (the in-memory dict can't be shared between
  draft helper and game advisor today)

**Why it might matter.** The atomic-rewrite risk is real — if Arena
crashes (or this program is killed) mid-write, the cache becomes
truncated JSON and the next startup fails to load. We've had this
happen at least once based on the truncated bulk-data file we saw on
the forge_py side.

**Cost.** ~5h. Schema design + migration script + test.

**What would unblock it.** A corruption incident, or a desire to
share the cache between draft helper and game advisor.

**Current take.** Pre-emptive. Low ROI until a corruption actually
happens. `mtga_local_db.py` already uses SQLite for its own purposes;
extending that DB is the natural shape if we do this.

---

## FP-F — Decision log → ML training set

**What.** `game_advisor/decision_log.py` records every advisor decision
+ outcome (win/loss). With enough rows, these become a training
dataset for a "predict best play" model that doesn't need an LLM.

**Why it might matter.** The LLM advisor costs tokens per call (Claude)
or local-GPU time (Ollama). A trained model is free at inference time.
Mirrors the `commander_builder/ml_dataset.py` Phase 3 plan — same
shape of "log human/LLM decisions, train predictor on outcomes."

**Cost.** Significant. Need:
- Decision-log schema stable enough to use as features (today it's a
  free-form JSON blob)
- 200+ logged games minimum to attempt training
- Feature engineering: game state → fixed-size vector

**What would unblock it.** Volume. Today's logs are sparse — running
the advisor in real games for a couple months would build a
meaningful dataset.

**Current take.** Premature. Like commander_builder's Phase 3 ML, this
sits behind months of accumulated real usage. Triggered automatically
when log row count crosses ~200.

---

## FP-G — Unified MTG application (cross-project)

**What.** Same FP-007 from `commander_builder/FUTURE_PLANS.md` —
consolidate all three MTG projects into one unified app. From this
project's perspective:

- Draft helper becomes a "Draft" tab
- Game advisor becomes a "Live game" tab
- Card reference (oracle text) is a sidebar
- Saved decks library is a tab
- Match history (decision logs from this project + iteration logs from
  commander_builder) is a tab

**Cost.** Months. Smart approach: ship piece-by-piece via FP-006
(Flask single-page) in commander_builder, then *add* draft / game
panels as Flask blueprints.

**What would unblock it.** FP-006 ships first. Then this becomes "add
two more views to the existing Flask app."

**Current take.** Right shape long-term. Lots of prerequisite work.
Status: PARKED, watching FP-006 progress.

---

## How this file relates to the codebase

- **`FUTURE_PLANS.md`** (this file): bigger bets, blocked items,
  strategic forks. Things we want to remember without committing.
- No `BACKLOG.md` exists for this project yet — when an item moves
  out of here into actionable work, create one.
- See [DATA_CLEANUP.md](DATA_CLEANUP.md) for one-time cleanup actions
  (gitignore tightening, untracked-large-file handling) that should
  precede most of these plans.

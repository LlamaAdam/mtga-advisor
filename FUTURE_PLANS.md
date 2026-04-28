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

## Project shape (snapshot 2026-04-27)

The codebase has **two independent halves** that share a working
directory but very little code:

### Half 1: Draft-pick overlay (legacy, top-level files)

- Files: `main.py`, `api.py`, `card_db.py`, `deck.py`, `draft_advisor.py`,
  `log_scanner.py`, `mtga_local_db.py`, `overlay.py`, `ratings.py`,
  `synergy.py`, `calibrate.py`, `capture.py`, `card_detector.py`,
  `config.py`
- Entry: `main.py` — reads Arena Player.log, fetches 17lands GIH ratings,
  shows letter-grade overlay on draft picks
- Caches: `arena_id_cache.json` (1.6MB), `ratings_cache.json` (820KB)
- **No automated tests** at the top level. Stable but untested.

### Half 2: In-game advisor (newer, `game_advisor/` subpackage)

- Files: `game_advisor/main.py`, `dashboard.py`, `decision_log.py`,
  `deck_manager.py`, `decklist.py`, `game_state.py`, `llm_advisor.py`,
  `log_scanner.py`, `math_utils.py`, `rule_engine.py`, plus capture
  helpers
- Entry: `game_advisor/main.py` — reads Arena Player.log during matches,
  builds game state, LLM-driven decision advice (Ollama backend,
  Claude API optional)
- **100 tests passing** across `game_advisor/tests/`
- Persistence: `game_advisor/saved_decks.json` (user decks),
  `game_advisor/logs/` (decision logs per game, currently empty)

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

## FP-C — Merge legacy draft helper into `game_advisor/` package

**What.** The two halves of the codebase share concepts (Arena log
scanning, deck objects, card lookups) but duplicate logic. Consolidate:

- Move top-level `main.py` (draft helper) under `draft_helper/` as a
  sibling of `game_advisor/`
- Extract shared infrastructure (log scanning, MTGA DB, Scryfall
  lookups) into `mtga_common/` or similar
- Single `pyproject.toml` so both halves can be `pip install -e .`
- Rename top-level `card_db.py` etc. to avoid the namespace collision
  with `game_advisor/`'s files of the same name

**Why it might matter.**

- Tests today only cover `game_advisor/`. The top-level code is stable
  but untested. Consolidating gives a clear path to add tests for the
  draft helper too.
- The two log scanners (top-level `log_scanner.py` and
  `game_advisor/log_scanner.py`) are *different* implementations with
  some shared parsing logic. One canonical scanner reduces drift.
- Onboarding: the dual-package structure is confusing — every file
  exists twice with different content.

**Cost.** ~12–20h depending on how much shared code we want to
extract. The naming-collision rename alone is ~3h; the extraction
of `mtga_common` is the bulk.

**What would unblock it.** A user willingness to take a regression-
risk hit on the legacy code while it gets restructured. The draft
helper has been stable for months; touching it carries risk.

**Current take.** Tempting but risky. Defer until either (a) a real
duplication-pain bug bites, or (b) the user is doing draft helper
work AND game advisor work in the same session and feels the seam.
For now the two halves coexist fine.

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

Run via `pytest tests/` (scope-locally; mixing with `game_advisor/
tests/` triggers the documented `config.py` collision).

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

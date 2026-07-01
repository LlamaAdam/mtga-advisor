# STATUS.md — mtga_draft_helper

> Operational state of the project. Read this file first to find out
> "what's the project up to right now?" without scrolling chat history.
>
> **Three sections** — *Now* (active work), *Recent* (last few days),
> *Blocked* (paused on something external). For roadmap items see
> [FUTURE_PLANS.md](FUTURE_PLANS.md). For one-time data hygiene see
> [DATA_CLEANUP.md](DATA_CLEANUP.md).

**Last updated**: 2026-06-30
**Project shape**: two packages, one shared module — `draft_helper/`
(draft-pick overlay) + `game_advisor/` (in-game advisor), sharing
`draft_helper/card_db.py`

---

## Now

### Working on
Nothing actively in flight. The 2026-06-30 session landed:

- **FP-C: merged the legacy draft helper into a proper `draft_helper/`
  package** — the 14 top-level files (`main.py`, `api.py`, `card_db.py`,
  `deck.py`, `draft_advisor.py`, `log_scanner.py`, `mtga_local_db.py`,
  `overlay.py`, `ratings.py`, `synergy.py`, `calibrate.py`, `capture.py`,
  `card_detector.py`, `config.py`) now live under `draft_helper/` with
  relative imports. Root `main.py`/`calibrate.py` are thin shims so
  `python main.py` and the existing launchers work unchanged.
  `game_advisor/` now imports the shared card_db as
  `from draft_helper import card_db` instead of the old
  sys.path-shadowing workaround. **`pytest tests/ game_advisor/tests/`
  now runs both suites together (318 tests)** — previously blocked by
  a bare-import collision. Full writeup in FUTURE_PLANS.md FP-C.
- **Found + fixed a real cache-path bug during the move** —
  `card_db._CACHE_FILE`, `config.RATINGS_CACHE_FILE`, and
  `draft_advisor.py`'s `.env` lookup all derived from
  `pathlib.Path(__file__).parent`, which would have silently pointed
  them at `draft_helper/` instead of the repo root once the files
  moved, orphaning the user's existing cache. Fixed to resolve from
  the repo root.
- **Refreshed FUTURE_PLANS.md's stale "Up next" list** — it claimed
  `log_scanner.py`/`synergy.py`/`ratings.py` still needed tests; they
  already had them (FP-D shipped 2026-04-28). Doc now matches reality.

### Up next
Nothing urgent. Remaining roadmap items are correctly parked:

1. **FP-F (decision-log → ML)** — blocked on data volume (200+ logged
   games), not effort. Revisit once that volume accumulates.
2. **FP-G (unified MTG app across the 3 sibling projects)** — blocked
   on `commander_builder` shipping its Flask single-page app (FP-006)
   first. Revisit once that lands.

### Cross-project context
This project is one of three sibling MTG projects under `C:\dev\` (and
this folder under `C:\Users\pilot\OneDrive\Documents\Python Scripts\`):

- `commander_builder` — Forge JVM driver for Commander deck testing
- `forge_py` — Python goldfish + (incoming) turn-by-turn engine
- `mtg_cards/` — **shared card-data folder** (data substrate)

This project's `card_db.py` reads from `mtg_cards/oracle_snapshots/`
via the same `MTG_CARDS_DIR` env var the sister projects use. See
[FUTURE_PLANS.md](FUTURE_PLANS.md) FP-G for the long-term unified
application vision.

---

## Recent (last 7 days)

### 2026-06-30
- FP-C: consolidated `draft_helper/` package, fixed the cache-path
  bug the move would have introduced, refreshed stale roadmap docs.

### Earlier
- FP-E (partial): `card_db._save_cache` uses atomic rename
  (`.tmp` + `os.replace`) so a crash mid-write can't truncate
  `arena_id_cache.json`.
- FP-D: 196 tests across nine files at top level (now `tests/`),
  covering `api`, `card_db`, `card_detector`, `deck`, `draft_advisor`,
  `log_scanner`, `mtga_local_db`, `overlay`, `ratings`, `synergy`.
- FP-A / FP-B (2026-04-27): shared `mtg_cards/` oracle store adopted;
  oracle-text appendix added to the LLM prompt.
- Concede / quit detection via dual-source fallback (commits 07237dd,
  36583da); post-loss LLM game analysis (72f2961); board count +
  empty placeholder in dashboard (b85a381); SQLite thread-safety fix
  for read-only path (2b34098).

---

## Blocked

Nothing currently blocked. FP-F and FP-G (see *Up next*) are parked on
external conditions, not actively worked.

---

## Stats

| Project area | Modules | Tests | Notes |
|---|---|---|---|
| `draft_helper/` (draft-pick overlay) | 14 | **196** | `api`, `card_db`, `card_detector`, `deck`, `draft_advisor`, `log_scanner`, `mtga_local_db`, `overlay`, `ratings`, `synergy` |
| `game_advisor/` (in-game advisor) | ~13 | **122** | |
| **Total** | **~27** | **318** | Runs together in one `pytest` invocation since FP-C |

- Wall time: ~1–3s for the combined suite.
- CLI entry points: `python main.py` (draft helper, shim over
  `draft_helper.main`), `python calibrate.py` (calibration, shim over
  `draft_helper.calibrate`), `python game_advisor/main.py` (game
  advisor).
- Caches (repo root, gitignored): `arena_id_cache.json`,
  `ratings_cache.json`.
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

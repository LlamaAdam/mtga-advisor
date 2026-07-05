# Review & Test Handoff — Draft Benchmark + Session Changes

**Date:** 2026-07-04
**Branch under review:** `master` (tip `cb00542`, pushed to `LlamaAdam/mtga-advisor`)
**Full suite:** `370 passed` (`pytest tests/ game_advisor/tests/`)
**Purpose:** Hand this session's work to an independent reviewer (Fable) to test and scrutinize. It covers what changed, where, how to run it, and specific areas to attack.

---

## 1. How to run everything

```bash
# from repo root: C:\Users\pilot\OneDrive\Documents\Python Scripts\mtga_draft_helper
# Use the SYSTEM python (Python 3.14), not a venv.

# Full suite (both halves run together — this is intentional and load-bearing, see FP-C):
python -m pytest tests/ game_advisor/tests/ -q          # expect: 370 passed

# Just the new benchmark package:
python -m pytest tests/benchmark/ -q                    # expect: 14 passed
```

Note: reports use non-ASCII glyphs (`✓ ✗ —`). Writing to a UTF-8 file is fine; if a caller `print()`s a report to a Windows console, set `PYTHONIOENCODING=utf-8`.

---

## 2. Session changes on `master` (7 commits, oldest→newest)

| Commit | What | Primary files | Tests |
|---|---|---|---|
| `2de3774` | **FP-C:** merge legacy top-level modules into a `draft_helper/` package; root `main.py`/`calibrate.py` become thin shims. **Also fixes** (a) cache-path bug the move would introduce (`__file__.parent` → repo root) and (b) **Scryfall User-Agent 400** that was silently breaking *all* Scryfall calls. | `draft_helper/*`, root `main.py`/`calibrate.py` | `tests/` + `game_advisor/tests/` now co-run; Scryfall header regression tests in `tests/test_card_db.py` |
| `214cb3b` | **Claude CLI backend** for the in-game advisor: `LLM_BACKEND=claude` shells to the subscription `claude` CLI (no API key), scrubbing `ANTHROPIC_*`/billing env. Also swapped a fake-but-real-shaped OpenRouter key in `.env.example` for a placeholder. | `game_advisor/llm_advisor.py`, `config.py`, `.env.example` | `game_advisor/tests/test_llm_advisor.py` (8 new, subprocess mocked) |
| `092f787` | **Scanner fix:** parse the modern MTGA `Draft.Notify` pick format (inline JSON, CSV `PackCards`) + `EventPlayerDraftMakePick`; widen set-detection beyond `BotDraft` so resumed Premier drafts load ratings. | `draft_helper/log_scanner.py` | `tests/test_log_scanner.py` (11 new: unit + `_parse` routing) |
| `76cf71c` | **Crash fix:** `DeckTracker._deck_metrics` returned `None` on a pack-opener (0 picks), crashing every synergy fn. Sentinel-init the memo snapshot. Surfaced only once the scanner fix let packs reach the overlay. | `draft_helper/deck.py` | `tests/test_deck.py` (2 new) |
| `c3f9d22` | **Mulligan synergy:** `check_mulligan` now pulls the active deck, detects its themes, and judges whether the hand is on-plan. New reusable `synergy.card_themes()` (per-card tagger) + `synergy.assess_hand_synergy()`. | `draft_helper/synergy.py`, `game_advisor/rule_engine.py` | `tests/test_synergy.py` (8), `game_advisor/tests/test_rule_engine.py` (3) |
| `8b4f2b5`, `6887717` | **Benchmark design spec + Phase A plan.** | `docs/superpowers/specs/2026-07-01-*.md`, `docs/superpowers/plans/2026-07-01-*.md` | — |
| `7d124f9`, `a98d704`, `b71c4dd`, `cb00542` | **Benchmark Phase A engine** (see §3). | `draft_helper/benchmark/*` | `tests/benchmark/*` (14) |

A security note for the reviewer: the repo history was rewritten this session to scrub a fake-but-real-shaped OpenRouter key from `game_advisor/.env.example` (all pre-existing SHAs changed). A full-history secret scan across all branches came back otherwise clean.

---

## 3. The benchmark (primary deliverable)

**What it does.** Scores the draft helper's pick recommendations against a recorded human draft, pick by pick. Headline metric: **agreement rate** (how often the tool's #1 == the human's pick), plus **mean rank** of the human's pick in the tool's ordering.

**Design docs:** `docs/superpowers/specs/2026-07-01-youtube-draft-benchmark-design.md` (spec, incl. the un-built Phase B video pipeline), `docs/superpowers/plans/2026-07-01-youtube-draft-benchmark-phase-a.md` (the plan this code implements).

**Architecture — a clean seam so the (future) video pipeline and the scorer are independent:**

```
DraftRecord{ set_code, source, picks: [PickEvent...] }
PickEvent{ pack_number, pick_number, pack_cards, human_pick, confidence }
   │  (Project B — video ingestion — produces these; NOT built)
   ▼
score_draft(record) → BenchmarkReport{ results: [PickResult...], agreement_rate, mean_human_rank, scored_count, skipped_count }
```

**Files (`draft_helper/benchmark/`):**
- `models.py` — the four frozen dataclasses; `BenchmarkReport` metrics count only `scored=True` picks and are safe at zero.
- `scorer.py` — `score_draft`. **The one non-obvious correctness rule:** for each pick it feeds a `DeckTracker` the human's *prior* picks (the "fairness rule") so the tool judges the pack from the same deck the human was building; then adds the human's pick. Ranks by `adjusted_rating`, EXCEPT a pack-opener (pick 1 of packs 2–3) ranks by raw `ratings.get_winrate(..., "All Decks")`. Human pick not in the pack → `scored=False` (excluded from metrics).
- `report.py` — `render_markdown` / `render_json`.
- `runner.py` — `run_benchmark` loads MSH ratings (cache-first) then calls `score_draft`; keeps network out of the scorer.

**Run it manually (works today — MSH ratings are cached):**

```python
from draft_helper.benchmark.models import PickEvent, DraftRecord
from draft_helper.benchmark.runner import run_benchmark
from draft_helper.benchmark import report as rpt

rec = DraftRecord(set_code="MSH", source="demo", picks=(
    PickEvent(1, 1, ("Justice, Vance Astrovik", "Powerful Broker", "Plains"), "Justice, Vance Astrovik"),
))
print(rpt.render_markdown(run_benchmark(rec)))
```

**Empirically validated (2026-07-04).** Ran on NumotTheNummy's MSH draft (real 720p video, read via vision, picks cross-checked against the on-screen deck pool). First three picks: **67% agreement** — tool agreed on P1P1 (Justice) and P1P2 (Trickster's Stratagem), disagreed on P1P3 (tool: Hydraulic Helper on-color; human splashed red for Hawkeye, which the tool ranked #9). The disagreement is the intended signal: pure win-rate + color-lane heuristic doesn't model an expert's off-lane splash.

---

## 4. What is NOT built — Phase B (video ingestion)

The full "point at a video, get a benchmark" pipeline is designed but not built. The intended path (revised after a spike): a **Claude Code skill** (`/benchmark-draft <local video>`) where ffmpeg extracts pick frames, Claude reads them in-session (montage several packs per pass), and the Phase A engine scores. A standalone-program + local-VLM approach was ruled out — a `minicpm-v` spike hit 108s/frame with hallucinated card names. Tooling is installed (ffmpeg via winget, yt-dlp). See the memory note `project_youtube_draft_benchmark` and the spec's Project B section.

---

## 5. Review focus areas (where to attack)

**Benchmark scorer (`scorer.py`) — highest-value scrutiny:**
1. **Fairness rule:** confirm the tracker holds only *prior* picks when scoring pick N (human's pick added after). Off-by-one here silently biases every result.
2. **Pack-opener branch:** `pick_number == 1 and pack_number >= 2` uses raw win rate; everything else uses `adjusted_rating`. Is that the right definition of "opener"? (Pack 1 Pick 1 is NOT treated as an opener — deck is empty anyway.)
3. **Human rank vs tool pick:** both derive from the same ordering, so `tool_pick == ordering[0]` and `human_rank = ordering.index(...) + 1`. Check tie behavior (stable sort → pack order) — untested.
4. **Skipped picks:** `human_pick not in pack` → `scored=False`, excluded from metrics. Also worth probing: card-name mismatches (recognition typos, punctuation/apostrophes, "//" cards) → silent skip. How should near-misses be handled?

**Other changes worth a second look:**
- `synergy.card_themes()` / `assess_hand_synergy()` — theme detection is substring/regex on oracle text; check false positives (e.g. "counter target spell" vs "+1/+1 counter"). `_SIGNIFICANT_THEME_MIN = 3` threshold is a judgment call.
- `log_scanner._handle_draft_notify` / `_handle_make_pick` — regex parsing of escaped JSON in the raw log line; adversarial/malformed lines.
- `card_db` Scryfall calls — all now send `_SCRYFALL_HEADERS`; confirm no call site was missed (grep `requests.(get|post)`).
- `llm_advisor` claude backend — env scrubbing correctness (no `ANTHROPIC_*` leaks to the child).

**Suggested adversarial tests for Fable to add:**
- Scorer: a multi-pick `DraftRecord` with a mid-draft skip, asserting the skip is excluded from `agreement_rate` *and* the deck-mirroring still advances (the skipped human pick is still added to the tracker).
- Scorer: two packs with tied ratings, asserting deterministic ordering.
- `assess_hand_synergy`: a deck whose dominant theme is *removal* (not a payoff theme) → verify "functional" vs "synergistic" verdict boundary.
- Report: a report with 0 scored picks → metrics are 0.0, no divide-by-zero, coverage line reads "0/N".

---

## 6. Quick verification checklist

- [ ] `python -m pytest tests/ game_advisor/tests/ -q` → 370 passed
- [ ] `python -m pytest tests/benchmark/ -q` → 14 passed
- [ ] Manual benchmark snippet (§3) prints a report with `Agreement rate: 100%`
- [ ] `git log --oneline 04780b9..HEAD` matches the 7 commits in §2
- [ ] No `requests.get`/`requests.post` to `api.scryfall.com` missing `_SCRYFALL_HEADERS`

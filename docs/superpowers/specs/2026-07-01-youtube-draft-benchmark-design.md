# YouTube Draft Benchmark — Design

**Date:** 2026-07-01
**Status:** Approved (design); pending implementation plan
**Reference video:** "Marvel Super Heroes Premier Draft | MTG Arena"
(`https://www.youtube.com/watch?v=R4bqbX8IaWY`) — MSH, PremierDraft, MTGA UI.

## Goal

Benchmark the draft helper's pick recommendations against expert human play by
comparing, pick-by-pick, what the tool would take vs. what a skilled streamer
actually took in a recorded Arena draft. The headline metric is **agreement
rate** (how often the tool's top pick equals the human's pick). The purpose is
to find where the tool's pure-win-rate heuristic diverges from good drafting.

## Scope

One spec, built in phases. Two logical projects joined by a clean data seam:

- **Project A — benchmark engine.** Small, deterministic, high value. Consumes
  draft data, runs the existing pick engine, scores agreement, produces a
  report. Does not care how the data was obtained.
- **Project B — video ingestion.** Larger, riskier computer-vision pipeline.
  Turns a local Arena-draft `.mp4` into the draft data Project A consumes.

All benchmark value lives in A. B is a hard data-delivery problem in front of
it. Phasing guarantees A ships and delivers value even if B needs heavy
iteration.

## The seam (interface between B and A)

B produces `DraftRecord`s; A consumes them. This lets A be built and tested with
hand-written records (no video), and lets B be swapped/improved without touching
scoring.

```
DraftRecord:
  set_code: str                 # e.g. "MSH"
  source: str                   # video filename / label
  picks: list[PickEvent]

PickEvent:
  pack_number: int
  pick_number: int
  pack_cards: list[str]         # card names available in the pack
  human_pick: str               # the card the streamer took
  confidence: float             # recognition confidence; 1.0 when hand-verified
```

## Project A — benchmark engine

For each `PickEvent`, in draft order:

1. Feed a `DeckTracker` the **human's actual prior picks** (the cards the
   streamer took up to this point). **Fairness rule:** the tool must judge the
   pack from the same deck the human was building — otherwise the tool's colors
   diverge after pick 1 and every later comparison is polluted by compounding
   divergence, not pick-quality difference.
2. `tracker.best_pick(pack_cards)` → **tool_pick**. Rank every card in the pack
   by `tracker.adjusted_rating` → find **where `human_pick` ranked** (1st, 2nd,
   …).
3. Record: `agree = (tool_pick == human_pick)`, the human-pick rank, both
   grades/win-rates.

**Report** (markdown + JSON):

- Headline: **agreement rate** = matches / scored picks.
- Cheap extra: **mean rank of the human's pick** in the tool's ordering. A 40%
  agreement rate reads very differently if the human's pick was usually the
  tool's #2 vs. its #8.
- Per-pick table and a "biggest disagreements" list (tool #1 vs. human pick,
  with both grades) so divergences can be eyeballed.
- **Coverage line**: "scored 42/45 picks; 3 skipped as unrecognized" — so a low
  agreement rate is never secretly a recognition failure.

Reuses existing code: `DeckTracker.best_pick` / `adjusted_rating`,
`ratings.get_winrate` / `winrate_to_grade`, `api.fetch_all_ratings`. No Arena
log or arena_ids needed — the engine works purely by card name.

## Project B — video ingestion pipeline

Linear chain of small, independently-testable stages, for a local Arena-draft
`.mp4`:

1. **Frame sampling** (`ffmpeg`) — extract frames every ~1–2s (picks take
   several seconds; this won't miss any).
2. **Pick-screen filter** — keep only frames showing the draft pick screen
   (card grid present); discard menus / deckbuild / gameplay.
3. **Region calibration** — MTGA lays cards in a fixed grid and shows the
   player's already-picked cards in a separate pool region. Derive both the
   pack-card bounding boxes and the pool region from the video's resolution
   once per video (can adapt `card_detector.py`'s bright-frame detection).
4. **Recognition (perceptual hash)** — crop each pack-card region *and* the
   pool cards, hash each, match to the nearest MSH card art → `pack_cards` +
   `pool_cards` + per-card confidence (hash distance).
5. **Pick detection** — pack size decreasing by one across successive pick
   screens tracks pick progression, and a reset to ~15 marks a new pack
   (pack 1 → 2 → 3). Note that consecutive screens show *different* packs
   (each passed from a neighbor, one card smaller), so the pick cannot be
   inferred by diffing packs. Instead the human's pick for a screen is the
   card that newly appears in the **picked-pool** on the following screen (the
   pool grows by exactly one each pick). A pick-confirmation highlight frame,
   if reliably detectable, is a secondary signal. Emit a `PickEvent` with that
   screen's `pack_cards` and the newly-pooled `human_pick`.
6. **Assemble `DraftRecord`** → hand to Project A.

**Known risk:** stages 3 and 5 are where arbitrary-video variability bites —
different streamers/resolutions or a UI update can shift the grid or add
animation frames that confuse the "pack shrank by one" logic. Mitigated by
confidence gating + manual review (below), but B is the part most likely to
need iteration on real footage. The reference video being **MTG Arena** (fixed,
crisp, programmatic UI) is the best case and meaningfully de-risks recognition
vs. paper/webcam footage.

## MSH card-image database (one-time setup)

Recognition needs a match target; the shared store has zero MSH images.

- Fetch all MSH card images (Scryfall) into `C:\dev\mtg_cards\images\` using the
  existing store and the User-Agent-fixed Scryfall client.
- Precompute a perceptual hash per card → a `hash → card_name` index saved to
  disk.
- Run once per set; cached forever after.

## Error handling — don't let misreads fake the score

Recognition is **confidence-gated** so a silent misread can't invisibly corrupt
the agreement rate:

- Each recognized card carries a hash-distance confidence. Below threshold →
  marked **uncertain**, not guessed.
- Any pick with an uncertain card, or an ambiguous pack transition (size didn't
  cleanly drop by 1), is **flagged for review**, not scored blindly.
- The pipeline writes a **review file** (`pack N pick M: [cards] → took X,
  confidence …`). The user corrects any misreads and re-runs scoring — instant,
  because Project A is pure/deterministic.
- The report always states coverage (scored vs. skipped).

## Testing

- **Project A** — fully unit-tested with hand-written `DraftRecord`s: agreement
  math, human-pick rank, the deck-state-mirroring fairness rule, report
  generation. No video needed.
- **Project B** — unit-test the pure logic: pick-transition detection from
  synthetic pack-size sequences, pack-boundary detection, hash-matching against
  a tiny fixture image set. `ffmpeg` extraction + real recognition get one
  integration smoke test on a few sample frames.
- **Golden test** — hand-label ~one pack of the MSH reference video (frames read
  via vision) and assert the pipeline recovers those picks end-to-end.

## Dependencies

- **New:** `ffmpeg` (system), `cv2` + `imagehash` (pip).
- **Present already:** `PIL`, `numpy`, `pytesseract`, `requests`.
- **Reuses:** `DeckTracker`, `ratings`, `card_db`, `api`, `card_detector`.

## Phased build order

Each phase is independently shippable and testable:

- **Phase A** — benchmark engine + report. Works immediately on hand-written
  `DraftRecord`s. **Where the value lands.**
- **Phase B1** — MSH card-image DB + perceptual-hash index.
- **Phase B2** — frame extraction + region calibration + recognition
  (frame → `pack_cards`).
- **Phase B3** — pick-transition detection → `DraftRecord`, wired to A.
  End-to-end on the real video.

If B2/B3 (the risky CV) need heavy iteration, Phase A still delivers a working
benchmark — fed by draft data read from frames via vision in the meantime.

## Explicitly out of scope (YAGNI)

- YouTube URL download (`yt-dlp`) — local `.mp4` only, to avoid YouTube ToS and
  a brittle dependency.
- OCR-based card reading — image-matching chosen instead (more robust on card
  art).
- "Why they diverged" analysis, close-call grade-gap scoring, and multi-metric
  dashboards — agreement rate (+ human-pick rank) only, for v1.

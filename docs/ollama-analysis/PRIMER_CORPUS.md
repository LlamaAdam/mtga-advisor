# FP-018.4 — Primer corpus, batch 1 (2026-08-27)

Supporting study for FP-018 "Adopt a deck": what Archidekt primers
actually contain, harvested with the commander-builder capture lane's
new `primer-batch` mode (Actions run 33040726815; sandbox egress is
blocked, CI runners are not). Method: for each of 12 requested
commanders — sampled across brackets, weighted toward B3/B4 per the
default weighting (owner has not overridden it) — walk the most-viewed
public decks and keep the first whose Quill-Delta `description` renders
to ≥ 200 chars. Captures were trimmed in-runner (description kept
byte-verbatim; card list reduced to name/qty/categories/layout),
consumed into this study, then deleted per the lane discipline.

## The batch

| Deck | Name | Views | Delta ops | card-links | Chars |
|---|---|---|---|---|---|
| 3949764 | Upping the Average — Atraxa Infect | 61,265 | 4 | 0 | 400 |
| 2073351 | Upping the Average — Edgar Markov Redux | 60,919 | 4 | 0 | 210 |
| 1173110 | Upping the Average — Lathril | 59,635 | 4 | 0 | 222 |
| 1017047 | Upping the Average — Meren | 46,824 | 4 | 0 | 288 |
| 2223923 | Upping the Average — Muldrotha | 43,679 | 5 | 0 | 270 |
| 639285 | Upping the Average — Yuriko | 42,227 | 4 | 0 | 315 |
| 5984805 | Upping the Average — Pantlaza | 39,962 | 7 | 0 | 347 |
| 2425068 | Upping the Average — Isshin | 34,424 | 4 | 0 | 329 |
| 854121 | Upping the Average — The Ur-Dragon | 29,599 | 4 | 0 | 270 |
| 696285 | Upping the Average — Kaalia of the Vast | 80,340 | 4 | 0 | 403 |
| 60036 | Gobs of Goblins (Krenko) | 18,693 | 13 | 6 | 543 |
| 86888 | Sisay, Onion Queen | 14,745 | 59 | 19 | 4,076 |

12/12 requested commanders hit; a further 9 candidate decks were
rejected for descriptions under 200 chars.

## Findings

**1. viewCount sorting collapses diversity.** 10 of 12 hits are one
series ("Upping the Average", an EDHRECast segment): a YouTube link
plus a plain-text "Cards Added" changelog. These are *upgrade diffs*,
not primers — no strategy, no lines, no packages. The ≥ 200-char
threshold cannot tell a changelog from a primer; future batches should
sort or filter differently (see finding 3) rather than harder by views.

**2. Card mentions are `card-link` EMBEDS, not prose.** In real
primers, card names appear as non-string Delta inserts of the shape
`{"insert": {"card-link": "Laboratory Maniac"}}`. A naive renderer
that concatenates string inserts silently loses *every card name the
primer mentions* — the single most load-bearing content for the adopt
flow (cross-checking primer claims against the list, auto-Protecting
primer-named cards). Pinned in commander-builder by a fixture built
from deck 86888's verbatim description (59 ops: 29 plain strings, 10
attributed strings, 19 card-links, 1 image embed). Conversely, the
changelog-style descriptions name cards only as plain text lines — so
card-name extraction must treat embeds as exact (no NLP) and must NOT
guess at prose mentions (the hazel primer's "Zulaport CUttrhotoat"
stands as the warning).

**3. card-link density is the honest "is this a primer?" signal in
this batch.** Real primers: 19 and 6 card-links. All ten
changelog-blurbs: 0, each with a YouTube link instead. Char-count
ranks the 400-char Atraxa changelog above the 288-char Meren one; it
cannot rank either against a primer. A future batch filter of
"≥ N card-links" (or ops-count ≥ ~10) would have kept 2/12 and
correctly discarded the rest — the corpus needs more batches with that
filter, not more views-sorted batches.

**4. What a real primer contains** (the FP-018 payload, from the two
genuine ones):

- *Stated intent and meta position*: "take a commander like Sisay and
  bring her to a game with some of the biggest baddies", "isn't trying
  to be tier 1" — bracket/power claims in the player's own words, the
  `stated` intent field's exact use case.
- *Named packages/archetypes with per-package rationale*: Consultation
  / Opus Thief / Flash-Hulk / Vigean Grafting, each with a paragraph
  of WHY (card-advantage gaps, threat density, testing the table).
- *Step-by-step win lines* with exact card sequences ("Have Sisay be a
  5/5 → Activate → Get Jace → Cast Demonic Consultation → Win") —
  machine-checkable against the list via the card-link embeds.
- *Swap guides*: Krenko's sideboard maps a like-for-like conversion
  ("Umbral Mantle > Muxus", …) — literally the small-modification
  format `commander adopt` wants to emit.
- *Degenerate/secondary lines flagged as such*: "The deck isn't
  intended to go off this way, it just happens to come up sometimes."

**5. Bracket spread survived the series bias.** The requested spread
(B4-leaning through B2-leaning) was hit 12/12, but the primer *depth*
did not correlate with bracket — the two real primers are a cEDH-adjacent
combo deck and a casual Krenko list. Depth tracks the author, not the
bracket.

## Implications carried back into FP-018

- 018.1 renderer: card-link embeds render as the card name; image
  embeds render as nothing; done against the deck-86888 fixture
  (in commander-builder, alongside the hazel single-op fixture).
- 018.3 auto-Protect: source card names from embeds only.
- 018.4 next batch: filter by card-link count, not description length;
  consider Archidekt search ordering other than `-viewCount`.

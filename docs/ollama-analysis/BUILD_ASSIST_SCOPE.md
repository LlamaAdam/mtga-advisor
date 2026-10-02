# FP-021 (proposed) — Build assist: recommendations conditioned on the cards you have already picked

Scoping note, 2026-10-02. Written for owner review before any code
lands (the FP-016 / FP-020 pattern). Owner prompt, 2026-10-02, after a
Discord thread explaining EDHREC's "Recs" feature: *"This sounds like a
good idea to recommend cards. It might be more useful. Tracking the
list, perhaps downloading once the commander is selected so you can
select cards you want in the deck and the percentage cards appear in
that deck."*

The Discord explanation of EDHREC Recs (user keattz, 2026-01-07),
paraphrased: normal EDHREC pages show the most popular cards per
commander; Recs goes a step further — for every card in your deck it
counts every card ever run alongside it in EDHREC's data, sums those
counts and flattens them to a single score. "Bigger number = more
popular."

---

## 1. What exists today, and the bug found on the way

commander-builder already pulls the commander-conditional numbers:

| Seam | What it gives | Conditioned on |
|---|---|---|
| `edhrec_client.fetch_commander_page` | ~220 cards in 12 sections, each with `num_decks`, `potential_decks`, `synergy`, `lift`, `trend_zscore` | the commander only |
| `_advisor_heuristic` ("edhrec.top_cards" / "edhrec.high_synergy" evidence) | add/cut recommendations gated on inclusion ≥ 30% | the commander only |
| `deck_builder` (FP-014) | assembles a 99 from the commander page, then personalization passes | the commander only |
| `lift_analysis` | pairwise lift over the locally harvested pool decks | your other cards — but a corpus of dozens of decks, not EDHREC's |
| `_advisor_bracket_peers` | top-liked Moxfield decks for commander + bracket | commander + bracket |

Nothing re-ranks as the deck changes. That is the whole gap.

**Found while scoping (fixed the same day, PR #86 `68228d9`):** live
`json.edhrec.com` card entries carry no `inclusion` key at all — 0 of
221 on the captured Krenko page — so every `inclusion_pct` parsed to
0.0 and the heuristic advisor's "≥ 30% inclusion" add gate had been
silently empty. Inclusion is now derived as `num_decks /
potential_decks`, which is the number EDHREC itself displays, and the
page's `lift` is kept on `CardEntry`. So the "percentage cards appear
in that deck" the owner asked for *was* in the product and was showing
zero.

## 2. The data, captured (nothing in this note is from memory)

Three captures through the lane on 2026-10-02 (scratch record; the
trimmed commander page is a repo fixture):

**Commander page** `json.edhrec.com/pages/commanders/<slug>.json` —
220 cards. Per card: `num_decks` (decks with this commander running
the card), `potential_decks` (decks with this commander where the card
is legal), `synergy`, `lift`, `trend_zscore`. Krenko: Goblin Warchief
87.5% inclusion, lift 5.8; Umbral Mantle 20% inclusion, lift 7.6 (the
"High Lift Cards" list is EDHREC's own pairwise statistic against the
commander).

**Card page** `json.edhrec.com/pages/cards/<slug>.json` — the pairwise
data. For Krenko *as a card* (98,971 decks, commander or 99): 16 lists,
512 co-played cards, each with `num_decks` (decks holding both) and
`potential_decks` (decks holding Krenko where the co-card is legal —
it varies per co-card: Swords to Plowshares 12,547 / 21,757 = 57.7%
among the white-legal Krenko decks; Impact Tremors 52,673 / 98,971 =
53.2%). No `synergy`/`lift` on this page; "High Lift Cards" and
"Top Commanders" are included as lists. Overlap with the commander
page's vocabulary: 108 of 220.

**Recs API** — the Recs page is client-rendered; its JS chunk
(`recs-d87dc4ad181f70ac.js`) posts to `/api/recs` with
`{cards: [names], commanders: [{name, …}], name, options:
{excludeLands, offset}}` and renders `inRecs` / `outRecs` items by
`name` with a 0–100 `score` bar, paging by `offset` and `more`. The
response was **not** captured (POST; no lane form for it yet) and the
endpoint is undocumented — see D1.

## 3. The design — compute Recs from the public card pages

Let `C` be the commander and `S` the set of cards the user has picked
(commander page vocabulary, growing as they tick). For every candidate
`X`:

- **prior** `P(X | C)` — the commander page inclusion (what the owner
  called "the percentage cards appear in that deck");
- **fit** — the Recs idea, computed from card pages:
  `fit(X) = mean over s ∈ S of P(X | s)` where `P(X | s) = num_decks /
  potential_decks` on s's card page (0 when X is not in s's lists);
- **lift** — EDHREC's commander-page lift, shown as-is;
- display: `inclusion% · fit% · lift`, sortable; the fit column is the
  one that moves when you tick a card.

Properties worth stating: `fit` is a mean of conditional inclusions,
so it stays a percentage ("across the cards you picked, X shows up in
N% of the decks that run them"), unlike Recs' flattened score, and it
is bounded, so a single very popular pick cannot dominate. Cuts are
the same statistic over cards already in the deck: a card with low
fit against everything else you chose is the "outRecs" list.

Cost: one card-page fetch per picked card, cached 24 h like every
EDHREC fetch (`CACHE_DIR`, `REQUEST_SLEEP_SEC = 0.5`). Picking 40
cards costs 40 fetches ≈ 20 s on a cold cache, 0 on warm. Lands and
basics are excluded from `S` (they condition nothing).

## 4. Where it plugs in

| Seam | Change |
|---|---|
| `edhrec_client` | `fetch_card_page(name) -> CardPage` (same JSON-first fetch + cache + retry as the commander page; walker shared); `conditional_inclusion(page, other) -> float` |
| new `build_assist.py` | pure: `score_candidates(commander_page, card_pages_for(S), deck) -> rows` with `inclusion`, `fit`, `lift`, `role` (`staples.role_bucket`), `support` (how many of S had X in their lists) |
| CLI `commander recs <deck.dck>` | the Phase-1 surface: top-N adds and cuts with the three numbers and the supporting picks named; offline tests on the captured pages |
| web: Build panel | commander picker → commander page → table with tick boxes; each tick re-scores (card pages fetched lazily); running `ROLE_TARGETS` counters; FP-020 win-route verdict live once that ships; "Export .dck" through `deck_builder`'s renderer |
| `deck_builder` | gains an include list so a hand-picked `S` becomes the seed the assembler fills around (today it has none) |
| `_advisor_heuristic` | `fit` becomes a fourth evidence pill beside inclusion / synergy / lift — the advisor's adds get deck-conditional for free |
| `lift_analysis` | stays as the offline fallback when EDHREC is unreachable; its lift and EDHREC's are both shown as "lift", labeled by source |

## 5. Rules

1. **Real data only.** Every number shown has a source pill (commander
   page / card page / local corpus). Tests use captured pages; the
   lane's `url:` form captures any card page in one push.
2. **Fit is a percentage, not a rank.** No flattened "bigger = better"
   number without the unit — the Discord thread shows exactly the
   confusion that produces.
3. **Politeness is the budget.** 0.5 s between fetches, 24 h cache,
   never more than one card page per pick; a cold-cache build session
   is bounded by the number of picks, never by the candidate count.
4. **Inclusion must stay honest** — the parser now derives it; if
   EDHREC ever ships `inclusion` again it is honoured first (pinned).

## 6. Phases

**Phase 1 — `commander recs` (CLI, read-only).** `fetch_card_page`,
`build_assist.score_candidates`, the command. Tests on the captured
Krenko commander + card pages. Ships with the inclusion fix already
in.

**Phase 2 — Build panel.** The dashboard surface the owner described:
pick a commander, tick cards, watch inclusion / fit / lift, export.
Needs `deck_builder`'s include list.

**Phase 3 — advisor integration.** `fit` as advisor evidence;
`improve` proposals ranked with it.

## 7. Kill criteria

- **G1 — it must say something the commander page does not.** On the
  58-deck primer corpus (real lists, real commanders), the top-10 by
  `fit` against each deck's actual 99 must differ from the top-10 by
  commander inclusion in ≥ 50% of decks. If they coincide, the
  conditioning adds nothing and Phase 2 is not built.
- **G2 — it must agree with the pilots.** For the 29 primers that name
  their win route (FP-020 research), the top-10 fit adds must not
  contradict the stated route in more than 3 decks (e.g. combo pieces
  recommended to a "no infinite combos" deck).

## 8. Decisions for the owner (`DECISIONS_FOR_REVIEW.md`, FP21-D1…D4)

- **D1.** Use EDHREC's undocumented `POST /api/recs` directly, or
  compute from the public per-card JSON pages? *Recommended: the
  pages* — documented shape (captured), cacheable, and no dependency
  on an endpoint EDHREC can change or gate without notice. The API can
  be probed later with a lane `post:` form if you want a comparison.
- **D2.** Phase 1 as CLI first, or straight to the Build panel?
  *Recommended: CLI first* — it is testable offline and the panel
  needs the builder's include list anyway.
- **D3.** Fetch budget: cap picks that trigger card-page fetches at 40
  per session (cold cache ≈ 20 s), or no cap? *Recommended: 40, with
  the count shown.*
- **D4.** Should `fit` feed the heuristic advisor (Phase 3) or stay a
  build-time tool? *Recommended: build-time until G1 passes.*

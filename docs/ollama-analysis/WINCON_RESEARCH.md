# Win-condition research — how the 58 most-liked primer decks actually win (2026-09-26)

Owner ask, 2026-09-26: *"Every deck needs a win on either an infinite
combo or some other way. Can you research the wincons for various decks
and figure out a way to factor that in?"*

This is the research half. The design half is `WIN_ROUTES_SCOPE.md`
(FP-020, proposed). Nothing in commander-builder changed for this note
except the capture lane (two new request forms, §2).

**Headline.** Every one of the 58 harvested decks has a way to win,
and the pilots who wrote a plan down agree with a card-level reading of
it in 28 of 29 cases. But commander-builder's only "can this deck win?"
measure — the `finisher` role target of 3 oracle-pattern cards — says
**45 of the 58 are short and 19 have zero finishers**, including every
cEDH combo list in the corpus, Krenko, The Ur-Dragon and Vivi. The
advisor is currently built to tell the format's most-liked decks to
"add finishers". The measure counts the wrong thing: it counts
*cards that say "win"*, when decks win by *routes* — a combo, a combat
plan, a drain engine, an alt-win card — and most routes have no card
whose oracle text says "win".

---

## 1. Corpus

The FP-018.4 harvest (`PRIMER_CORPUS.md`): batch 1 (12 owner-agnostic
commanders, most-viewed Archidekt deck each) + batch 2 (top-25 by
views on Archidekt, top-25 by likes on Moxfield, two-per-commander cap,
exact-duplicate rejection). 62 captures, **58 unique decks** after the
4 batch-1/batch-2 overlaps (33 Archidekt, 25 Moxfield), 3,150 unique
card names. The captures were trimmed to names + description in the
runner; they live in git history (`61f7282`, `ee41e4b`) and were
re-extracted for this study.

Composition matters for reading the numbers (batch-2 finding 2 stands):
9 "Upping the Average" changelog blurbs, 5 Strixhaven and 4 set-preview
precon writeups, 1 reference list (Atogatog, "All Free EDH Sac
Outlets" — not a deck), ~14 explicitly [cEDH]/[PRIMER] Moxfield lists,
and ~25 real player decks with a stated plan.

## 2. Method — real oracle text, real combo data, nothing invented

The sandbox cannot reach Scryfall or Commander Spellbook (both 403 at
the egress proxy), and the harvest captures carry names only. Rather
than reason from remembered card text, the capture lane
(`.github/workflows/fetch-archidekt-capture.yml`) learned two forms:

- `oracle-names: <file>` — trims Scryfall's bulk `oracle_cards`
  export to a name list in the runner. 3,150 / 3,150 names found (DFC
  names match on the front face). *Drift caught on the way:* the
  bulk-data endpoint no longer serves `download_uri` at all, only a
  gzipped JSONL `jsonl_download_uri` (24 MB compressed). The repo's
  `oracle_store` already moved to that form in July; the lane's first
  two runs pinned it again.
- `combos: 1500` — runs the repo's own
  `combo_detection.refresh_combos` (Commander Spellbook,
  `ordering=-popularity`) with the output redirected into the capture
  directory, so the combo data is the production code path's output,
  not a copy of it. 1,500 combos: 752 two-card, 619 three-card, 124
  four-card, 5 five-card. `data/` is gitignored, which is why the
  sandbox never has this file and the offline floor is the 20-entry
  hand-curated fallback.

A prototype classifier (`wincon_corpus/win_routes_proto.py`, **not**
repo code) read every deck's cards against that oracle text and combo
list. Its outputs, the 862-card oracle subset it used and the combo
capture are checked in under `wincon_corpus/` so every number below is
reproducible offline. The pilot-stated routes were read by hand from
the rendered primers (`primer.parse_primer`, the shipped parser) and
recorded in `routes.json` as `pilot_stated_routes`.

## 3. The taxonomy — nine win routes

A **win route** is a way a deck ends the game, evidenced by the cards
it runs. The prototype's definitions and thresholds (all of these are
the research question, not settled numbers — see FP-020 D2):

| Route | What it means | Prototype evidence rule |
|---|---|---|
| `combo` | a combo in the deck that ends the game | ≥1 **kill combo** present (below) |
| `alt_win` | a card whose text wins or makes an opponent lose | ≥1 card: "you win the game" / "loses the game" |
| `drain` | life-loss engine (aristocrats, extort, Exsanguinate-class) | ≥3 drain triggers or "each opponent loses X" |
| `burn` | direct damage to each opponent / X-damage finishers | ≥3 such cards |
| `poison` | infect / toxic / poison | ≥5 cards |
| `mill` | milling opponents out | ≥4 opponent-mill cards |
| `combat_wide` | tokens + overrun or anthems | ≥1 overrun & ≥4 token makers, or ≥3 anthems & ≥4 token makers |
| `combat_voltron` | one big evasive/commander-damage threat | ≥8 auras/equipment |
| `combat_big` | many large bodies, extra combats | ≥10 creatures with power ≥5, or ≥7 with an extra-combat / overrun piece |

**Combos are not all wins.** Commander Spellbook's `produces` field has
290 distinct features in the top 1,500. The repo's `is_game_ending`
treats anything containing "infinite" as game-ending — correct for
bracket pressure, wrong for "can this deck win": *Infinite colorless
mana* (128 combos) and *Infinite creature ETB* (641) end nothing on
their own. The prototype splits them:

- **kill** — the combo itself wins: *Win the game* (37), *Target /
  Each opponent loses the game* (51), *Infinite / Near-infinite damage*
  (128), *Infinite / Near-infinite lifeloss* (89), *Infinite mill*
  (48), *Infinite creature tokens with haste* (56), *Infinite combat
  phases* (72), *Infinite turns* (25), *Infinite combat damage* (17).
- **resource** — infinite ETB / LTB / death / sacrifice / tokens /
  storm / draw / mana / lifegain / landfall / magecraft / counters. A
  resource loop becomes a kill only if the deck also runs an **outlet**
  that converts it: Impact Tremors for ETB, Blood Artist for deaths,
  an overrun or haste anthem for tokens, an X-damage spell for mana,
  and so on (`OUTLET` table in the prototype).
- **value** — everything else (blink, scry, Food).

Krenko is the clean example: its 16 kill combos are all
*Infinite creature tokens* or *Infinite ETB* loops that count as kills
**only because** the deck runs Impact Tremors, Purphoros and Goblin
Bombardment — which is exactly what its primer says ("sac them to
Goblin Bombardment or have Impact Tremors or Purphoros deal damage").

## 4. Results

### 4a. Routes per deck

| Routes detected | Decks |
|---|---|
| 0 | 5 |
| 1 | 19 |
| 2 | 23 |
| 3 | 10 |
| 5 | 1 (the Atogatog reference list) |

Route frequency across the 58: combo 31 · combat_wide 17 · drain 12 ·
combat_big 11 · alt_win 11 · burn 9 · combat_voltron 6 · mill 2 ·
poison 1. Kill combos present in 31 decks; 12 decks carry resource
loops with **no recognised outlet**; 55 of 58 are one card away from
at least one kill combo in the top 1,500 (a fact about the combo
database's density more than about the decks — see §5).

### 4b. Agreement with what the pilots wrote

29 primers state how the deck wins. Against the card-level reading:
**19 full agreement, 9 partial, 1 miss.**

The partials are instructive because every one is the *tool* being
narrower than the pilot, never contradicting them:

| Deck | Pilot says | Detected | Why the gap |
|---|---|---|---|
| Vivi Ornitier | combo, burn (Vivi grows to lethal) | combo | commander-as-damage-source is not a "burn card" |
| The Master, Transcendent | mill, drain, beatdown | mill | Syr Konrad + Mindcrank is 2 drain pieces (threshold 3); 7 fatties (threshold 10) |
| Krenko | go-wide, burn | combat_wide, combo | Impact Tremors + Purphoros = 2 burn cards; the tool credited them as combo outlets instead |
| Jin Sakai | voltron, infect swings | combat_voltron | 4 infect pieces (threshold 5) |
| Magda (Clockside) | combo, dragon beatdown | combo | dragons below the fatties threshold |
| Henzie | beatdown, Protean Hulk line | combat_big, drain | the Hulk pile is a resource loop whose outlet the prototype does not recognise |
| Necrobloom | combo, dredge finisher | combo, combat_wide | "dredge finisher" has no card-level signature |
| Marneus Calgar | drain, go-wide | drain, alt_win | 25 token makers but no anthem/overrun — go-wide without a finisher card |
| Fire Lord Azula (Cold-Blooded Flame) | scary threat each turn, combo | combo, burn | voltron-by-commander, not by gear |

The one miss: **Zimone, Infinite Analyst** (Quandrix precon, "massive
X-spells and huge numbers") — X-spells that make Fractal tokens are a
route with no signature in this taxonomy.

### 4c. The five decks with no detected route

Arcades, the Strategist (walls attack with toughness — the `fatties`
rule reads power); Heroes in a Half Shell, Rootha and Zimone (three
precon writeups — WotC's own blurbs promise "shock and awe", not a
kill); Ms. Bumbleflower (budget draw-matters midrange). Four of the
five are the "value pile with no closer" the owner's premise is about;
Arcades is a taxonomy hole.

### 4d. What the repo says today about the same decks

`staples.classify_role_extended` over the same oracle text, counting
`finisher` + `win_condition` against `ROLE_TARGETS["finisher"] = 3`
(the rule `role_target_report` applies):

- **19 / 58 decks have zero finisher-pattern cards.** Among them:
  Vivi, Elsha, Kefka, both Fire Lord Azula lists, Kinnan, Necrobloom,
  Shorikai (all combo decks with detected kill combos), Krenko, The
  Ur-Dragon, Isshin, Killian (combat decks), The Master (mill),
  Muldrotha (mill).
- **45 / 58 are below the target of 3**, so the advisor would ask 45
  of the format's most-liked decks for more finishers.
- The 13 that satisfy it are the drain/aristocrats decks (Meren,
  Lathril, Baba, Wilhelt, Dina, Sephiroth, both Edgars, Henzie —
  Zulaport Cutthroat-class cards match "each opponent loses N life"),
  Atraxa infect (43 matches — `infect` is in the pattern list), Jin
  Sakai (its infect package), Marneus, Sisay (Lab Man + Jace) and the
  Atogatog reference list.
  In other words the pattern list is a **drain-and-infect detector**
  wearing a "finisher" label.

Cross-tabulated: of the 53 decks with a detected route, 40 fail the
finisher target (15 with zero finisher cards). All 5 decks with no
route fail it too — so the target does flag the no-route decks, but
only because it flags almost everything: 45 of 58 overall. It cannot
tell a Vivi from a Rootha.

## 5. Findings

1. **"Can it win?" is a question about routes, not cards.** Seven of
   the nine routes have no oracle-text "win" signature at all; combo
   (31 decks) and combat (34 route-hits across the three combat
   routes) are the two most common ways to win and the current
   measure sees neither.
2. **The combo database already in the repo is the right instrument,
   with one split missing.** `combo_detection` + Spellbook top-1500
   found the stated combo in every combo deck that named one (Sisay,
   Vivi, Heliod, RogSi, both Magdas, K'rrik, Sephiroth, Yawgmoth,
   Kefka, both Azulas, Elsha, Kinnan, Necrobloom). The one change
   needed is *kill* vs *resource* + outlet; without it a mono-green
   lands deck (Lumra: 31 loops, all *Infinite landfall triggers;
   Infinite tapped land tokens*) reads as 31 wins.
3. **Outlets are how most "combo" decks actually kill.** Of the 31
   decks with kill combos, a large share of their kills are resource
   loops made lethal by an outlet in the 99 (Krenko 16/16, Wilhelt,
   Dina, Sephiroth). An advisor that protects combo pieces but not the
   outlet — or cuts Impact Tremors as "low impact" — breaks the win
   while leaving the loop intact.
4. **Thresholds want redundancy, not presence.** Every pilot deck with
   a clear plan carries redundancy in it (Heliod: Ballista *and*
   Triskelion, "a clunkier backup plan"; Light-Paws: 39 aura/equipment
   pieces; Atraxa: 43 infect cards). Single-piece routes (Yuriko with
   one Thassa's Oracle and no Consultation; Kilo with one Darksteel
   Reactor) are the ones a route check should call *thin*, not
   *present*.
5. **Precons and value piles are exactly the "no route" population.**
   The owner's premise holds in the data: the decks without a
   detectable closer are the set-preview writeups and the draw-matters
   budget deck, not anyone's tuned list.
6. **Pilots state routes in the same vocabulary.** "combo", "go wide",
   "voltron", "drain", "mill", "infect", "beatdown/beats" — the nine
   route names above are the words primers already use, which is what
   makes a primer-stated route matchable against a detected one
   (FP-018's `Intent.stated` is the seam).
7. **One-card-away is too dense to be a signal by itself.** 55/58 decks
   are one card from *some* top-1500 kill combo. `one_piece_away`
   stays what it is — a bracket-aware suggestion list — and is not a
   route.
8. **The finisher saturation ceiling of 3 is also wrong for the same
   reason.** It never fires on Craterhoof-class cards by design
   ("wincon cards are too heterogeneous"), so the target and the
   ceiling disagree about what a finisher is; a route model gives both
   the same object to reason about.

## 6. Limits of this study

- **Prototype rules, not shipped code.** The regexes are first drafts;
  the `tokens` outlet rule matches any "haste" (Lightning Greaves
  counts as a token outlet) and `combat_big` reads power only. They
  were tuned on this corpus, so the 28/29 agreement is in-sample.
- **Spellbook top-1500 by popularity** is a coverage floor, not the
  database; a deck's actual combo may be an unpopular variant. The
  full export is ~89k variants.
- **cEDH skew** in the Moxfield half (batch-2 finding 2) inflates the
  combo share; a bracket-2/3 corpus would show more combat routes.
- **Stated routes are hand-read** from 29 primers by one reader; the
  reading is recorded in `routes.json` so it can be disputed.
- **Commander as the win route** (Vivi as damage source, Azula as the
  threat) is under-detected — the commander's own text needs a
  separate weighting, as `ROLE_TARGETS` already does for roles.

## 7. Where this goes

`WIN_ROUTES_SCOPE.md` turns the taxonomy into FP-020: a `win_routes`
module, a deck-health tile that replaces the finisher target's
question, route pieces feeding `Intent.key_wincons` so the improver
never cuts the only route, a stated-vs-detected cross-check on adopt,
and the judge's plan-coherence gloss asking about the route by name.
Five owner decisions are queued in `DECISIONS_FOR_REVIEW.md`
(FP20-D1…D5).

## Appendix — per-deck table

Columns: commander · site · pilot-stated routes (— = primer states no
plan) · detected routes · kill combos / resource loops without outlet
(top-1500) · finisher-pattern cards the repo counts today (target 3).

| Commander | Site | Pilot states | Detected | Kill / res | Finisher today |
|---|---|---|---|---|---|
| Meren of Clan Nel Toth | arch | — | combo, drain | 5 / 0 | 3 |
| Lathril, Blade of the Elves | arch | — | drain, combat_wide | 0 / 0 | 5 |
| Edgar Markov | arch | — | combo, drain, combat_wide | 1 / 0 | 2 |
| Muldrotha, the Gravetide | arch | — | mill | 0 / 0 | 0 |
| Isshin, Two Heavens as One | arch | — | combat_big | 0 / 0 | 0 |
| Atraxa, Praetors' Voice | arch | poison | combo, poison | 1 / 0 | 43 |
| Pantlaza, Sun-Favored | arch | — | combo, combat_big | 2 / 0 | 1 |
| Krenko, Mob Boss | arch | combat_wide, burn | combo, combat_wide | 16 / 0 | 0 |
| Yuriko, the Tiger's Shadow | arch | — | alt_win | 0 / 0 | 1 |
| Kaalia of the Vast | arch | — | combo, alt_win, combat_big | 1 / 0 | 1 |
| The Ur-Dragon | arch | — | burn, combat_wide, combat_big | 0 / 0 | 0 |
| Sisay, Weatherlight Captain | arch | combo, alt_win | combo, alt_win | 4 / 0 | 3 |
| Brudiclad, Telchor Engineer | arch | — | combo, alt_win | 2 / 0 | 2 |
| Arcades, the Strategist | arch | — | **none** | 0 / 1 | 0 |
| Vivi Ornitier | arch | combo, burn | combo | 11 / 1 | 0 |
| Szarel, Genesis Shepherd | arch | — | combat_big | 0 / 0 | 1 |
| Kilo, Apogee Mind | arch | alt_win | alt_win, burn | 0 / 0 | 1 |
| Baba Lysaga, Night Witch | arch | drain, combat_wide | drain, combat_wide, combat_voltron | 0 / 0 | 3 |
| Atogatog | arch | — | drain, burn, combat_wide, combat_voltron, combat_big | 0 / 0 | 6 |
| Heliod, Sun-Crowned | arch | combo | combo | 2 / 0 | 1 |
| Auntie Ool, Cursewretch | arch | — | combo, burn | 2 / 0 | 2 |
| Ashling, the Limitless | arch | — | combat_wide, combat_big | 0 / 0 | 1 |
| Wilhelt, the Rotcleaver | arch | — | combo, drain, combat_wide | 5 / 0 | 3 |
| Heroes in a Half Shell | arch | — | **none** | 0 / 0 | 1 |
| Killian, Decisive Mentor | arch | — | combat_wide, combat_voltron | 0 / 0 | 0 |
| Rootha, Mastering the Moment | arch | — | **none** | 0 / 0 | 0 |
| Dina, Essence Brewer | arch | — | combo, drain, combat_wide | 4 / 0 | 3 |
| Quintorius, History Chaser | arch | — | combat_wide | 0 / 0 | 1 |
| Zimone, Infinite Analyst | arch | x_spells | **none** | 0 / 0 | 0 |
| The Master, Transcendent | arch | mill, drain, combat_big | mill | 0 / 0 | 0 |
| Shorikai, Genesis Engine | arch | — | combo | 1 / 0 | 0 |
| Reki, the History of Kamigawa | arch | combat_big | combat_big | 0 / 0 | 1 |
| Niv-Mizzet, Parun | arch | — | combo, alt_win, burn | 7 / 1 | 2 |
| Y'shtola, Night's Blessed | mox | — | burn, combat_wide | 0 / 0 | 1 |
| Marneus Calgar | mox | drain, combat_wide | alt_win, drain | 0 / 0 | 8 |
| Lumra, Bellow of the Woods | mox | — | combat_wide | 0 / 31 | 0 |
| Jin Sakai, Ghost of Tsushima | mox | combat_voltron, poison | combat_voltron | 0 / 0 | 3 |
| Rograkh, Son of Rohgahh | mox | combo | combo, alt_win | 6 / 0 | 1 |
| Magda, Brazen Outlaw | mox | combo | combo, alt_win | 4 / 6 | 1 |
| Henzie "Toolbox" Torre | mox | combat_big, combo | drain, combat_big | 0 / 1 | 3 |
| K'rrik, Son of Yawgmoth | mox | combo | combo, alt_win | 1 / 0 | 2 |
| Sephiroth, Fabled SOLDIER | mox | combo, drain | combo, drain | 17 / 1 | 5 |
| Sauron, the Dark Lord | mox | combat_voltron | combat_voltron | 0 / 0 | 1 |
| Kinnan, Bonder Prodigy | mox | combo | combo, combat_big | 8 / 3 | 0 |
| Teval, the Balanced Scale | mox | — | combo, alt_win, combat_big | 2 / 0 | 2 |
| Yawgmoth, Thran Physician | mox | combo | combo, drain | 9 / 0 | 1 |
| Ms. Bumbleflower | mox | — | **none** | 0 / 0 | 0 |
| Edgar Markov | mox | combat_wide, drain | combo, drain, combat_wide | 4 / 0 | 3 |
| Fire Lord Azula | mox | combat_big, combo | combo, burn | 1 / 0 | 0 |
| Light-Paws, Emperor's Voice | mox | combat_voltron | combat_voltron | 0 / 0 | 1 |
| Fire Lord Azula | mox | combo | combo | 7 / 0 | 0 |
| Rocco, Street Chef | mox | combo, combat_wide | combo, burn, combat_wide | 1 / 0 | 1 |
| Hearthhull, the Worldseed | mox | — | combo, burn | 22 / 0 | 1 |
| The Necrobloom | mox | combo, combat_big | combo, combat_wide | 3 / 25 | 0 |
| Kefka, Court Mage | mox | combo | combo | 3 / 3 | 0 |
| Alela, Cunning Conqueror | mox | — | combat_wide | 0 / 0 | 1 |
| Elsha of the Infinite | mox | combo | combo | 6 / 1 | 0 |
| Magda, Brazen Outlaw | mox | combo, combat_big | combo | 4 / 5 | 1 |

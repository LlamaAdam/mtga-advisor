# Owner checklist — things only your PC can run (2026-08-27)

Everything below needs your machine (knowledge_log.sqlite, Forge,
Ollama) or your accounts. In rough order:

## commander-builder

1. **Merge the open PRs when you're happy with them**: commander-builder
   #83 (DFC fix + FP-018 adopt-a-deck + bug sweep) and mtga-advisor #4
   (G3 numbers + primer corpus study). Then `git pull` master on both.
2. **Backfill, dry-run first** (D1 — writes knowledge_log.sqlite, which
   exists only on your PC):
   `python scripts/backfill_web_margins.py` → review the report →
   rerun with `--apply`.
3. **Era boundary call** (D5):
   `python scripts/backfill_web_margins.py --era-boundary-report`
   lists the 2026-08-14 rows; decide which side of the boundary they
   belong to. Zero writes until you say so.
4. **First deck-judge run**: set `COMMANDER_BUILDER_DECK_JUDGE=1` on
   your next real compare (needs `ANTHROPIC_API_KEY`). Observe-only.
   After ~50 pairings: `python scripts/judge_agreement.py` — G1/G2/G3
   print with their pre-registered rules; G3 needs ≥10 labeled
   pairings per arm before it reads anything.
5. **Try `commander adopt`**: import a primer'd deck
   (`commander import <archidekt url>` — you'll see
   `primer captured (N words) -> <deck>.primer.md`), then
   `commander adopt <deck.dck>` — optionally with
   `--preferences "I like sacrificing creatures"` in your own words.
   Read-only; suggestions capped at the polish tier; rebuild is
   unreachable from this command.
6. **Doctor**: `commander doctor` — the local-model check now tells
   the truth: flag off is green; flag on needs Ollama running AND the
   model pulled (`ollama pull llama3.2:3b`).

## mtgdeals (whenever you revisit deals)

7. PR #1 stays parked per your "leave it for now" (draft, conflicts
   with your newer main). When you do want it: resolve the classify.py
   + score.py conflicts, then activate the Opus review gate with
   `pip install anthropic` + `ANTHROPIC_API_KEY` in the bot's
   environment. The sellout-factor and foreign-language gates need no
   setup beyond the merge.

## Standing decisions on record

- C5/C6 stay parked; sealed-price alerts remain an idea doc
  (docs/ideas/SEALED_PRICE_ALERTS.md), not built.
- Primer-corpus batch 3, if wanted: the capture lane's rules (2 per
  commander, exact-duplicate skip) are standing; the study recommends
  filtering by card-link count instead of description length next
  time.

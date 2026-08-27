# FP-016 (proposed) — LLM deck judge

Scoping note, 2026-08-17. Written for owner review **before** any code
lands. Nothing here is built yet.

Companion to decision A4 (local-model router) but a different job at a
different model tier — see "Relationship to A4" below.

---

## 1. The question it answers, and the one it must not

`forge_py_screen.py` already states this repo's contract:

> forge_py decides which candidates DESERVE Forge games.
> Forge decides which deck is BETTER. Only Forge.

The judge does **not** get to overrule that, and this note is not an
argument for replacing the sim. It is an argument that "better" was
always two questions, and Forge only answers one:

| Question | Instrument | Status |
|---|---|---|
| Which deck wins more games against Forge's AI? | Forge A/B | Built; ~5% power at shipped settings; ~67 min/verdict |
| Which deck is better built **for its stated intent, at a real table**? | *nothing* | The gap |

The second question is not a softer version of the first. It covers
everything the guard we shipped on 2026-08-17 exists to protect:
politics, threat assessment, the incentive to pay a tax, whether a deck
can actually execute its plan through interaction. Forge's AI does not
negotiate and loops ~25% of soak games, so on those dimensions its
margin is not weak evidence — it is *no* evidence.

**The judge must never be allowed to answer question 1.** No "the LLM
thinks deck B wins more games." It has no access to game outcomes and
would be inventing them.

## 2. Why it is worth building

1. **It covers a real blind spot**, not a redundant one. Everything in
   the politics guard is currently protected by *refusing to measure*
   it. A judge is the first instrument that could actually evaluate it.
2. **The cost asymmetry is extreme.** A 40-game verdict costs ~67
   minutes of JVM. A six-judgment panel costs seconds and cents. The judge
   can run on *every* swap, including the many that will never be worth
   sim time.
3. **It produces the validation study this repo has been waiting for.**
   Log both verdicts side by side and after N swaps you have an
   agreement table between two instruments with different blind spots.
   That is learnable at ~50 rows, not the 1,000 FP-013 needs — and
   unlike FP-013 it does not require a fine-tune.
4. **Frontier models genuinely know Commander.** Not card *recall* —
   that must be retrieved, see §4 — but archetype convention, synergy
   reasoning, and multiplayer dynamics.

## 3. Design — borrowing the sim's discipline, not skipping it

The failure mode to avoid is a confident single opinion dressed as a
measurement. The sim earns its verdicts with a significance test; the
judge needs an analogue, or it is just vibes with a JSON schema.

- **Panel of 6, three per presentation order.** Six independent
  judgments, no shared context. *Revised from this note's first draft
  (N=5): five cannot be split evenly across two orders, which confounds
  position bias with ordinary judge variance — the one thing this design
  exists to keep separate.* Three judgments see the pairing as A/B,
  three as B/A.
- **Order bias is a detector, not a tiebreak.** Position bias is the
  best-documented LLM-judge failure mode. Agreement is counted on the
  *deck*, never the position; if the two triads systematically prefer
  whichever deck was shown first, that pairing is `inconclusive` **by
  definition**.
- **Blinded.** The judge is never told which deck is the incumbent.
  Status-quo bias is otherwise free to masquerade as judgment.
- **Supermajority gate.** A verdict requires ≥5 of 6 agreeing on the
  same deck. Anything less is `inconclusive`.
- **Reuse the verdict vocabulary.** `kept` / `reverted` / `neutral` /
  `inconclusive`. No new labels — the same discipline the replication
  work followed on 2026-08-17.
- **Per-dimension scoring**, so disagreement is diagnosable rather than
  a single opaque number: plan coherence, interaction density,
  resilience, mana/curve realism, and the politics/table dimension the
  sim cannot see.

## 4. Grounding — retrieval, never recall

Every card named in a judge prompt carries its oracle text and type
line from the existing Scryfall snapshots. The model reasons over text
it is *handed*, never text it remembers. This is the whole
anti-hallucination measure and the machinery already exists
(`scryfall_client`, the `real_oracles` fixture discipline).

**Prompt budget — diff-focused, not deck-dump.** Full oracle text for
~200 cards across two decks would run tens of thousands of tokens *per
judgment*, and six judgments per pairing makes that a real recurring
cost. It is also worse judging: the changed cards are what matter and
they drown in 190 lines of unchanged context. So the prompt carries
full oracle text for the **changed** cards only, plus a compact
role-tagged name list for the rest of each deck (role tags come free
from `staples`). Cheaper and sharper for the same reason.

**Judged against intent, not against generic power.** `intent.py`
already produces archetype, themes, and key win-cons per deck. The
judge is asked "is this better *at what this deck is trying to do*",
with the intent supplied. Without that anchor an LLM panel will chase
consensus and converge every deck toward the EDHREC average — which is
the single most likely way this feature makes the app worse.

## 5. Seams it plugs into

| Seam | Use |
|---|---|
| `intent.learn_intent` | supplies the standard the deck is judged against |
| `scryfall_client` snapshots | oracle text for the changed cards (see the prompt budget in §4) |
| `staples.politics_tags` | flags the dimension Forge is blind to, so the judge is asked about it explicitly |
| `knowledge_log` | new `judge_verdict` + `judge_report` alongside `verdict` / `sim_report`; stamped with the current `measurement_era` |
| `_proposer_sim` verdict vocabulary | reused verbatim |
| `forge_py_screen` | the precedent for a screen that never becomes a judge |

## 6. Phases

**Phase 1 — observe only.** `deck_judge.py`: blinded order-swapped
panel, per-dimension scores, `inconclusive` on disagreement. Writes
`judge_verdict` beside the sim verdict. **It does not advance decks and
does not gate anything.** Ships behind `COMMANDER_BUILDER_DECK_JUDGE`,
matching the repo's convention for unvalidated machinery.

**Phase 2 — agreement analysis.** A script producing the instrument
agreement table: where judge and sim agree, where they diverge, and
whether divergence concentrates in the dimensions we predicted (decks
heavy in politics tags). This is the deliverable that decides Phase 3.

**Phase 3 — only if Phase 2 earns it.** Two options, in preference
order:
1. **Judge as screen** (the `forge_py_screen` pattern, already
   precedented): the panel eliminates weak swaps so the 67-minute sim
   is spent on candidates worth testing. Screening does not require
   the judge to be *right*, only better than random — a much lower bar
   than judging.
2. **Judge as second verdict** on politics-heavy decks where the sim is
   known blind. Higher bar; needs Phase 2 to show stable, explicable
   behavior.

## 7. Pre-registered kill criteria

In the spirit of FP-015 (CardScore was killed by three pre-registered
gates it failed). Declared **now**, before any results exist:

The judge is abandoned if, over the first 50 pairings:

- **G1 — self-consistency.** Order-swap flips the verdict on >25% of
  pairings. A judge that disagrees with itself cannot judge.
- **G2 — discrimination.** It returns `kept` on >80% of pairings. An
  instrument that approves nearly everything is measuring agreeableness,
  not quality.
- **G3 — consensus bias.** Its preferences track "cards with high
  EDHREC inclusion" more strongly than deck-specific fit, tested by
  scoring swaps that are staple-ward vs. intent-ward. If it just
  recommends Rhystic Study to everyone, it has added nothing that
  EDHREC inclusion% did not already provide for free.

Failing any of the three parks it, and the note gets an honest
postmortem the way FP-002 and FP-015 did.

## 8. Honest risks

- **No ground truth.** Agreement with the sim is not truth; both
  instruments can be wrong together. The agreement table is
  informative, not confirmatory — it must never be written up as
  "validated."
- **Consensus bias** is the likeliest failure (mitigated by §4, not
  eliminated).
- **Non-determinism.** Same input, different output — which is exactly
  why the panel and the supermajority gate exist rather than a single
  call.
- **It is an opinion.** The strongest honest claim available is "two
  instruments with different blind spots agree", which is genuinely
  worth more than either alone, and still is not proof.

## 9. Relationship to A4 (local-model router)

Different jobs, different tiers, and they should not be conflated:

- **A4 / local small model** — narrow tagging with the oracle text
  supplied (role, archetype). A 3B model can do this. It cannot judge.
- **This / frontier model** — comparative judgment needing real
  Commander knowledge and multi-step reasoning.

Pointing a local 3B model at the judging task would reproduce exactly
the mistake negative mode found in the existing Ollama stubs: a
706-line prompt written for Claude, handed to a model that cannot
execute it.

## 10. Decisions — settled 2026-08-17

Settled by argument where an argument exists; the two that turn on the
owner's spending appetite are marked and were put to them directly.

**D1. Unit of judgment: whole-deck pairings, not individual swaps.**
The agreement table in Phase 2 is the entire point of Phase 1, and it is
only meaningful if both instruments answer about the *same object*. The
sim's unit is a deck pairing, so the judge's must be too. Judging
individual swaps would produce a column that cannot be joined against
the sim's.

**D2. Panel of 6, three per presentation order** — revised up from the
draft's 5, because 5 cannot split evenly across two orders and would
confound position bias with judge variance. See §3.

**D3. Phase 1 runs automatically whenever it is enabled.** Not a
separate on-demand invocation. The value of Phase 1 is an *unbiased*
sample of paired verdicts; running it on demand would sample exactly
the pairings the owner was already curious about, which is the one
sampling rule guaranteed to poison the agreement table. Cost is
controlled by the env flag being off by default —
`COMMANDER_BUILDER_DECK_JUDGE=1` opts in, and while it is off nothing
is spent.

**D4. Model tier: the strongest tier available, not a larger cheap
panel.** *(Owner decision — a spending call, not a derivable one.)*
The reasoning that framed it: panel size buys down
*variance*, not *bias*. The failure modes that would sink this feature
— consensus-chasing, shallow Commander reasoning — are systematic, so
they are correlated across panel members; adding cheap judges measures
the same bias more precisely rather than removing it. If cost needs to
come down, the honest lever is running the judge on fewer pairings, not
on more, weaker judges.

**D5. Prompt is diff-focused** (§4) — full oracle text for changed
cards, role-tagged names for the rest. Settled on judgment quality
grounds as much as cost: the changed cards are the question, and they
drown in 190 lines of unchanged context.

**D6. Build Phase 1 after the existing queue.** *(Owner decision.)*
FP-016 was net-new scope against the sixteen decisions reviewed on
2026-08-17, so it queues behind them: local-model router, umbrella CLI,
`commander-init`, Playwright smokes, Forge canary, backfill report. The
agreement table wants paired verdicts accumulating early, but not at
the cost of work already approved.

### Still open

Nothing blocking. Phase 3 remains explicitly gated on Phase 2's
results, and the §7 kill criteria stand as declared.

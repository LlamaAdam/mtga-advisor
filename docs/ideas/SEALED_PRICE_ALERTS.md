# Idea — sealed product price alerts

Captured 2026-08-17 from a live example: a Wilds of Eldraine set booster
box (30 packs) listed at Best Buy near MSRP, years after the set went
out of print.

Not scoped, not scheduled, not committed. This note exists so the idea
is not lost and so the traps are recorded while the example is fresh.

## The proposed rule, and why it needs adjusting

As stated: *"if a new play booster is less than $200 and it isn't that
price on the market, ping."*

Two corrections before this becomes a spec:

**1. Do not key on "play booster."** Play Boosters began with Murders at
Karlov Manor (early 2024). Wilds of Eldraine (Sept 2023) shipped Set,
Draft and Collector boosters — so the rule as written would have missed
the exact listing that prompted it. The trigger should cover sealed
booster boxes generally (draft / set / play / collector), plus bundles
and precons, keyed on **product category**, not on the current
generation's name. This matters more over time, not less: the set most
likely to be mispriced at retail is an old one, and old sets are exactly
the ones whose booster type has since been discontinued.

**2. The absolute price is a proxy; the spread is the signal.** "Under
$200" is a decent heuristic for *this year's* boxes, but it silently
encodes today's MSRP and will rot. The real condition is
`retail_price < market_price` by some margin — which is also what makes
the alert actionable, since it says how much the gap is worth. Absolute
price is better used as a sanity floor (ignore anything implausibly
cheap — that is a listing error or a scam, not a deal).

## Why age is a strong prior

Sealed product generally appreciates once a set leaves print, because
supply is fixed and draft/cube demand continues. So a big-box retailer
still holding old stock at the original MSRP is systematically
underpriced against the secondary market — they price on shelf age,
the market prices on scarcity. The owner's instinct ("maybe a set being
2 years old even") is the right shape:

- **Age is a prior, not the rule.** ~18-24 months post-release is a
  reasonable threshold for "out of print, market has moved."
- It should raise the alert's priority, not be its trigger. A brand-new
  box at a genuine discount is still worth knowing about.

## The hard part is data, not logic

The rule is a few lines. The feasibility question is entirely about
where the two numbers come from:

| Need | Candidate source | Reality |
|---|---|---|
| Retail price | Best Buy / Amazon / Target / LGS | Big-box scraping is ToS-hostile and bot-detected. Official APIs exist but generally need an affiliate or developer account. |
| Market price | TCGPlayer sealed, eBay sold listings | TCGPlayer has an API behind approval. eBay *sold* listings are the better truth signal but harder to get cleanly. |

This should be settled **before** any code: a watcher built on scraping
retail pages will break constantly and may violate terms. An
API-and-affiliate-account route is slower to start and far more durable.

## Where it belongs — open question

It shares almost nothing with `commander-builder`: no oracle data, no
simulation, no advisor, no deck. The only overlap is the word "prices",
and even that is a different market — `deck_pricing.py` tracks *singles*,
this tracks *sealed*. Bolting a retail-arbitrage watcher onto a deck
optimizer would add a whole fragile network surface to a tool whose
tests are deliberately offline.

Recommendation: a **separate small service**, with its own schedule and
its own notification path, rather than a module inside the deck pipeline.

## If it gets built

- Watchlist of products (set + booster type), not a whole-catalogue crawl
- Poll on a schedule; alert on spread crossing a threshold
- De-duplicate alerts so one listing does not ping repeatedly
- Record price history, so "near MSRP" is measured rather than eyeballed
- Alert must include the spread and the source link, so it is actionable
  without a second lookup

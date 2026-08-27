# FP-018.4 — Primer corpus (batches 1–2, 2026-08-27)

Supporting study for FP-018 "Adopt a deck": what deck primers actually
contain, harvested with the commander-builder capture lane (sandbox
egress is blocked; CI runners are not). Captures are trimmed in-runner
(description byte-verbatim, card lists reduced), consumed into this
study, then deleted per the lane discipline. Three exemplar primers are
preserved verbatim in the appendices; everything else survives as the
tables and findings here.

## Method

- **Batch 1** (Actions run 33040726815): 12 owner-agnostic commanders
  sampled across brackets weighted toward B3/B4; per commander, the
  most-viewed public Archidekt deck whose description renders ≥ 200
  chars. 12/12 hit.
- **Batch 2** (Actions run 33078277486, owner-directed): walk the
  TOP-RANKED public commander decks on both sites and keep 25 per site,
  with the owner's rules: most-liked ordering where the API offers it
  (Moxfield; **Archidekt's API exposes no like count** — pinned in
  `archidekt_client.py` — so views stay its proxy), exact-duplicate
  lists rejected by a card-name fingerprint shared across sites, and at
  most **two decks per commander** — a third is skipped and the walk
  continues down the ranking.

Batch-2 outcome: **25/25 kept on each site.**
Archidekt: 107 candidates walked — 77 thin-primer, 3 no-commander,
2 fetch errors (429s). Moxfield: 119 walked — 94 thin-primer.
Duplicate-fingerprint and commander-cap skips: 0 each — the top
rankings happened to contain no exact-list repost and no third
primer-bearing deck of one commander within reach; both rules are
offline-tested, and the cap-2 allowance is visibly exercised (Magda
and Fire Lord Azula each kept exactly twice on Moxfield).

## Batch 2 — Archidekt (top-viewed)

| Deck | Name | Views | Ops | card-links | Chars |
|---|---|---|---|---|---|
| 1585124 | Baby Lasagna (Baba Lysaga) | 267,205 | 290 | 71 | 17,541 |
| 18520785 | Praise the Sun, Fire the Gun (Heliod) | 207,781 | 80 | 0 | 4,915 |
| 3887 | Reki, the History of Kamigawa | 69,264 | 285 | 92 | 4,888 |
| 13765265 | Vivi Ornitier, semi-budget EDH | 57,331 | 237 | 74 | 4,231 |
| 24364891 | The Unity (The Master, Transcendent) | 91,397 | 101 | 0 | 3,107 |
| 14397447 | World Shaper (Szarel, preview deck) | 124,140 | 31 | 12 | 930 |
| 14420275 | Counter Intelligence (Kilo, preview deck) | 116,690 | 33 | 13 | 871 |
| 20105223 | Turtle Power! (TMNT) | 77,968 | 8 | 2 | 577 |
| 18744843 | Dance of the Elements (Ashling, preview) | 82,277 | 5 | 0 | 532 |
| 1794593 | All Free EDH Sac Outlets (Atogatog) | 57,322 | 1 | 0 | 458 |
| 18744715 | Blight Curse (Auntie Ool, preview) | 86,804 | 1 | 0 | 434 |
| 1221862 | Upping the Average — Brudiclad | 121,283 | 6 | 0 | 406 |
| 696285 | Upping the Average — Kaalia | 80,357 | 4 | 0 | 403 |
| 3949764 | Upping the Average — Atraxa Infect | 61,282 | 4 | 0 | 400 |
| 582352 | Upping the Average — Niv-Mizzet | 60,313 | 4 | 0 | 337 |
| 21319610 | Lorehold Spirit (Strixhaven series) | 60,680 | 5 | 2 | 323 |
| 21319304 | Silverquill Influence (Strixhaven) | 64,969 | 5 | 2 | 299 |
| 21319521 | Witherbloom Pestilence (Strixhaven) | 76,028 | 5 | 2 | 286 |
| 21319431 | Prismari Artistry (Strixhaven) | 57,860 | 5 | 2 | 281 |
| 21319716 | Quandrix Unlimited (Strixhaven) | 64,735 | 5 | 2 | 268 |
| 1234196 | Upping the Average — Arcades | 57,941 | 6 | 0 | 263 |
| 1904544 | Upping the Average — Wilhelt | 88,711 | 4 | 0 | 235 |
| 1173110 | Upping the Average — Lathril | 59,643 | 4 | 0 | 222 |
| 2073351 | Upping the Average — Edgar Markov | 60,935 | 4 | 0 | 210 |
| 2498709 | Upping the Average — Shorikai | 69,649 | 4 | 0 | 202 |

## Batch 2 — Moxfield (top-liked; the API has real like ordering)

| Likes | Name | Commander(s) | Chars |
|---|---|---|---|
| 2,463 | [Cabal] A Faster K'rrik Storm (cEDH) | K'rrik | 269 |
| 1,434 | Henzie — High Power (non-cEDH) | Henzie | 261 |
| 1,385 | Kefka budget Competitive High Power | Kefka (MDFC) | 599 |
| 1,376 | Edgar Markov Aggro | Edgar Markov | 212 |
| 1,198 | Earn Your 9th Tail [PRIMER] | Light-Paws | 295 |
| 956 | Ms. Bumbleflower: Keep calm and draw | Ms. Bumbleflower | 241 |
| 910 | Grind Them Into Dust — Kinnan Midrange | Kinnan | 220 |
| 895 | Sauron, the Dark Lord | Sauron | 262 |
| 885 | [cEDH] Rograkh Silas Storm Combo | Rograkh + Silas (partners) | 257 |
| 834 | The Magdanomicon — Magda cEDH Primer | Magda | 790 |
| 826 | The Necrobloom [Primer] | The Necrobloom | 249 |
| 754 | The Cold-Blooded Flame | Fire Lord Azula | 405 |
| 738 | Cocaine Bear (Lumra) | Lumra | 224 |
| 699 | [CABLE] Clockside Outlawed | Magda (2nd — cap allows two) | 867 |
| 677 | Lotuslight Gardens | Teval | 295 |
| 609 | Jin's Vengeance | Jin Sakai | 903 |
| 587 | Of Tricks and Temptations | Alela, Cunning Conqueror | 416 |
| 581 | Hearthhull, Land Shuffle | Hearthhull | 503 |
| 564 | Sephiroth's Singularity | Sephiroth (MDFC) | 545 |
| 564 | Disciple of Matoya | Y'shtola | 216 |
| 556 | [cEDH] To Infinity & Beyond | Elsha | 237 |
| 536 | Yawgmoth Xerox [cEDH Primer] | Yawgmoth | 364 |
| 513 | [PRIMER] Nutritional Beats | Rocco, Street Chef | 301 |
| 507 | $100 Fire Lord Azula (2nd — cap allows two) | Fire Lord Azula | 230 |
| 488 | Marneus Calgar: Travel/Souvenir Deck | Marneus Calgar | 217 |

## Batch 1 (superseded detail, kept for the record)

12 commander-targeted Archidekt captures: 10 were "Upping the Average"
changelog blurbs (0 card-links, a YouTube link each); the two real
primers were Sisay, Onion Queen (86888 — 4,076 chars, 59 ops, 19
card-links; now the formatted-Delta renderer fixture in
commander-builder) and Gobs of Goblins (60036 — 543 chars, 6
card-links, with a like-for-like Muxus swap guide). Four batch-1 decks
resurfaced in batch 2's views ranking (Kaalia, Atraxa, Edgar, Lathril).

## Findings

**1. Card mentions are `card-link` embeds — but only on Archidekt, and
not always.** Archidekt primers embed card names as non-string Quill
Delta inserts (`{"insert": {"card-link": name}}`); a renderer that
drops non-string inserts loses every one (batch-1 finding, now
re-confirmed at scale: 71/92/74 card-links in the three big batch-2
primers). BUT long prose primers with zero embeds exist (Heliod,
4,915 chars, 0 card-links — cards named as plain text), so embed
extraction is *precise but not complete*: exact names when present,
never a guarantee the primer names nothing else. Moxfield descriptions
are **markdown/plain text, not Quill Delta** — zero bracket-links or
markdown links in all 25 — so on Moxfield there is no reliable exact
card extraction at all. Site shapes differ; the parser must branch on
provenance, and auto-Protect can only trust Archidekt embeds.

**2. Each site's ranking has its own bias.** Archidekt top-views:
series content again — 9 "Upping the Average" changelogs, 5 Strixhaven
commander-deck writeups, 4 set-preview decks; real player primers are
5 of 25. Moxfield top-likes is the richer primer vein per capita —
most kept decks are explicitly titled [PRIMER]/[cEDH] — but the
description field itself is short (216–903 chars): Moxfield primer
culture evidently lives in short mission statements plus external
links/updates, or text beyond the API's description field. cEDH skews
heavily here (likes concentrate on competitive lists), which is a
bracket-composition fact future batches must weigh.

**3. Thin-primer rejection dominates the walk.** 77/107 Archidekt and
94/119 Moxfield candidates fell to the < 200-char filter: even at the
very top of both rankings, roughly three quarters of decks carry no
usable stated intent. `hasPrimer`-style presence is the exception, not
the rule — the adopt flow must treat "no primer" as the common case
and degrade gracefully.

**4. What the deep primers add** (beyond batch 1's list): update logs
with dates ("Last Update: 8/09/26 — Blood Moon Variant Moved…"),
variant/budget sub-lists, per-package card counts, playstyle-steering
advice aimed at exactly FP-018's user ("aimed to help players make
their own changes based on playstyle preferences or meta
requirements" — the Magdanomicon's own words), and community-primer
conventions (a "front-facing test list" maintained for a whole
archetype community).

**5. Rate limits are real at scale.** Two Archidekt 429s mid-walk
(absorbed by the retry/skip path). Politeness delays stay mandatory;
bigger batches should expect and log them.

## Implications carried into FP-018

- 018.1 parser branches by site: Archidekt = Quill Delta (string ops +
  card-link embeds + image embeds); Moxfield = markdown passthrough.
- 018.3 auto-Protect: Archidekt card-link embeds only; a prose-only
  primer yields explanation without auto-protection, stated as such.
- 018.4 batch 3, if wanted: keep the two-per-commander and
  exact-duplicate rules (now standing owner policy), add a
  series-blurb filter (card-links = 0 AND a lone URL ⇒ changelog, not
  primer), and consider Moxfield bracket filters to rebalance the
  cEDH skew.

---

## Appendix A — Baba Lysaga, Night Witch (Archidekt 1585124, 267k views)

The deepest primer captured. `[[name]]` marks a card-link embed;
rendered from the verbatim Delta, image embeds elided.

> My signature deck, Baba Lysaga, AKA Baby Lasagna! A mix of aristocrats, landfall, and reanimator strategies, where you have to solve a puzzle every turn.
>  
> As a fun detail of this deck, every time I cast Baba from the Command Zone, I use a different edition of her, as a funny new way of tracking command tax. 
> 
> Shuffle Up & Play video and Budget Baba list
> 200-card Extra Turns video and 200-card version of the deck
> Hijinks gameplay
> Goldfish With Me video
> 
> 
> General Strategy
> I've opted for an extremely greedy version of Baba, attempting to activate her ASAP and to activate her every round, if possible. Rather than building long-term engines, this deck is basically living paycheck-to-paycheck. Solving her 3-type potion puzzle is extremely fun to me, since it keeps me on my toes every turn, making for high variance not just every game but in every single round. 
> 
> However, this means sacrificing long-term planning for short-term bursts of value. In this version of a Baba deck, we can't afford to be precious about our game pieces, not even our resources; Baba's regularly eating away at her own mana base to fill in the gaps. Multi-type lands like [[Darksteel Citadel]] and [[Urza's Saga]] aren't just helpful, they're crucial. That means you're banking on drawing some form of land recursion spell with Baba's card velocity. If you lose that bet, then we get to turn 8 with 4 lands while everyone else has built enormous empires. Figuring out how to survive moment-to-moment and get to next turn, while also trying to figure out how you can win  even when you've sacrificed your long-term plans for short-term gain, is one of the most thrilling parts of playing this list.
> 
> You shouldn't play this deck if...
> You like to keep your stuff around and protect it.
> You prefer secure, safe bets rather than risky gambles. 
> You like casting big spells
> You enjoy politicking & deal-making
> 
> You SHOULD play this deck if...
> You enjoy puzzle-solving every single turn
> You're okay with being public enemy number 1
> You enjoy adapting/improvising on the spot
> 
> 
> MVP Cards
> [[Mishra's Factory]], [[Blinkmoth Nexus]], and other cheap self-animating lands. Baba doesn't need to sacrifice exactly 3 things, just any number of permanents, and if they include at least 3 card types among them, then she'll draw 3 and drain 3. These cards turn into artifact creature lands, satisfying 3 types all on their own!
> [[Liquimetal Coating]] and [[Liquimetal Torque]] are my all-star favorite cards. Giving an enchantment creature a 3rd type is cool enough, but these can also help out a [[Marionette Master]] or turn an enemy permanent into an artifact so that it's eligible to be hit by [[Tear Asunder]] or [[Reclamation Sage]] effects. 
> [[Kaya's Ghostform]] and other pop-back Auras. I see some confusion about this, but yes, if you enchant Baba with one of these, then use Baba's ability to all at once sacrifice herself, the aura, and some other 3rd bonus thing to satisfy her 3-type requirements, then yes, cards like Kaya's Ghostform or [[Changing Loyalty]] will see the death and trigger even though they're on the way out themselves, too. These can be hand to put onto an artifact creature, so that sacrificing them means you get your 3 types and immediately get 2 of them back. However, I think it's always wiser to put these effects on Baba herself. That way, if people try to remove her, you can just sac her and the enchantment (plus some other 3rd thing to proc her draw effect) and the Aura will pop her back to play, which will fizzle their removal spell. That line of play makes it so extremely difficult for opponents to actually kill her that I think it's usually the right move to put those on her instead of onto your fodder pieces.
> [[Ugin's Nexus]] is super easy to proc in this deck. It's not loop-able here, but it doesn't need to be. Just getting that 1 extra turn can be a big life swing, and I notice it tends to draw less ire than blue extra turn effects. 
> [[Glimmerlight]] and [[Invasion of Ikoria // Zilortha, Apex of Ikoria]] set the bar for the ratio of mana-cost-to-card-types. Ikoria is a late-game tutor, sure, but it's useful early on just to search for a 0-drop [[Ornithopter]]. 2 mana for 3 types is an incredible rate, satisfying Baba all on their own, and almost everything else pales in comparison.
> Earthbending is ludicrous in this deck. Animate a land, giving it 2 types for Baba, and then when you eat that land, it comes right back? Absurdly good.
> 
> 
> Win Conditions
> This is a tough plane to land; chunking opponents for 3 life at a time doesn't win a game, and you're eating a lot of your own cards to get anywhere, which does draw a lot of cards, but can make it hard to face off against an opponent who's been accruing value more exponentially over time. 
> In general, I opt to keep the win conditions as cards that can focus-fire a single player, rather than using cards that function similar to Baba and ping all opponents (such as [[Bastion of Remembrance]]). As the game winds toward a close, especially if it's down to a 1-on-1, cards that offer the chance for a final burst of damage are the most valuable way to close a game. 
> [[Jolrael, Mwonvuli Recluse]] is cheap to cast and regularly supplies you with Cat tokens as Baba draws extra cards. Once you're in a position to try attacking for lethal, Baba can often get you hand of 6 or 7 or even more cards, so Jolrael will make even a ton of little tokens into worrisome attackers.
> [[Blossoming Bogbeast]] is wild; activate Baba once, and when Bogbeast attacks, the team gets +5/+5 and trample. With an untapper, 2 Baba acitvations means Bogbeast grants +8/+8. It can be hard to assemble a LOT of tokens, but that big of a buff is often enough to clinch the finalBlossoming Bogbeast
> [[Zuran Orb]] is listed under 'Win Cons' because of how drastically it amplifies/expedites potential win condition opportunities. It turns [[Titania, Protector of Argoth]] and [[Baloth Prime]] into enormous threats by sacrificing lands on the end step before your turn, so as to untap with tons of tokens for a final lethal swing. It makes [[Mazirek, Kraul Death Priest]] and [[Blossoming Bogbeast]] able to pump for tons more damage in combat. It could also just gain you tons of life and proc tons of Landfall triggers like [[Tireless Provisioner]] after you recur lands with a [[Will of the Sultai]], which is of course an absurdly powerful maneuver, but here, it's just a nice extra bonus compared to how much of a late-game threat it poses. Deploy this card only when you're ready to push for an endgame, because opponents will be correct to snipe it.
> [[Starscream, Power Hungry // Starscream, Seeker Leader]] - cast this on the back half, haste-flying-menacing through to hit an opponent and give them the Monarch. On the next turn, hit them again to steal the crown, flipping Starscream over, and granting you the ability to deal 2 damage and gain 2 life every time you draw a card... which Baba does a whole lot of. Even though it's a little convoluted, 
> [[Marionette Master]] is an oldie but a goodie. Sac a few artifacts to target someone for several chunks at a time, whether you're sacrificing Treasure tokens, artifact creatures with Baba, or using [[Zuran Orb]] to pitch your artifact lands.
> [[Deadly Tempest]] and [[Villainous Wrath]] - might seem weird to have board wipes in the win conditions category, but these straight-up win me games in this deck. Baba kicks off the game by lowering life totals, and through other combat during the game, opponents naturally drift down to the 10s of life points. If they make a bunch of tokens to try and win via some huge combat, losing life for each of those creatures turns their own late-game momentum against them. 
> 
> 
> Coolest Plays:
> Sac 3 creatures with Baba, including herself, and then cast [[Living Death]] to get her & her friends right back. Voila, a one-sided board wipe.
> Baba doesn't need to sac exactly 3 types; sometimes I've used her just to sacrifice 3 lands on the end step, so that [[Titania, Protector of Argoth]] will have 3 new tokens to attack with on my turn.
> When someone comes at ya with a big creature, activate Baba. She'll gain ya life, and you probably sacrifice a creature too, so your [[Mortality Spear]] and your [[Tragic Slip]] are now active!
> Activate Baba multiple times in 1 turn with minimal casualties: [[Thousand-Year Elixir]] grants ability haste, and [[Lightning Greaves]] could grant regular haste. Give her a [[Kaya's Ghostform]] type of enchantment, activate her by sacrificing that enchantment and herself, then she'll pop right back. Giver her haste, and she can get another go. This also works if you let her go to the graveyard and bring her back with [[Animate Dead]] or [[Necromancy]]. Ability haste will let you activate her sometimes up to 3 or 4 times in a single turn, though it requires you to lose a few other pieces along the way and often eats up your mana and your future resources. I don't recommend deploying this maneuver early on, but it can sometimes be the last-minute hail mary you need to drain your final opponent's remaining life points. 
> [[Ordeal of Nylea]] doesn't care how it gets sacrificed, just that it gets sacrificed. Eat it with Baba and you'll ramp 2 lands. 
> 
> 
> Weak Points & What to Watch For
> Public enemy number 1: After 2 Baba activations, you're at 46 and everyone else is at 34. Also, you've eaten a bunch of your own board to make this occur. It is impossible not to get focused at that point.
> Baba deals AOE (area of effect) damage. Singling out a single player to target, without also accidentally hurting a temporary ally, is a political liability that makes it very hard to properly join forces with other players against a mutual archenemy. This is one of the reasons I prioritize win conditions that also me to focus-fire a single opponent, rather than dealing even more AOE damage. 
> Lifegain is brutal against this deck. Someone doubling their life is very, very hard to chew through when your commander is chunking for 3 at a time, especially when several of the other good win conditions require combat to make up for the shortfall. I'm sometimes more afraid of lifegain players than I am of combo players, because they can absolutely put themselves beyond my deck's reach, at a damage threshold that is nearly impossible for this deck to achieve before that player can get their own win conditions together. 
> Mana base: this deck relies upon a lot of utility lands and multi-type lands to grease the wheels. That eats away at the number of basic lands you can search for, as well as how many color-fixing lands you have room for.
> If you don't manage to find a land recursion helper (such as [[World Shaper]]) then you'll have eaten multiple lands and be several mana resources behind everyone else at the exact moment they've all decided to start attacking your larger life total and picking apart your already-sparse board.
> Your mana curve is TINY. I think the highest mana cost in the whole deck is 5, or maybe there's 1 card at mana value 6 in there. With the number of lands I feel comfortable eating, casting something for 5 mana could mean that's the only spell I'm playing, not just that turn, but that round. 
> Related to the tiny mana curve: yes, Baba will draw you a butt-ton of cards. However, sometimes the cards you're drawing are, like, [[Ornithopter]]s. You'll look threatening by drawing 3 at a time, but that doesn't always mean you'll have actually drawn answers & threats, just that you've drawn enough to get your commander 1 more activation.
> 
> Common Rules Errors
> Baba sometimes trips people up, so here are some common rules clarifications to answer some questions that may still be puzzling for any folks out there:
> Using Baba to sacrifice cards with 2 total types (for instance, just an artifact and a creature) does not mean she draws 2 and drains for 2. 
> Baba sacrifices up to 3 permanents, not exactly 3 permanents. 
> Baba can indeed sacrifice herself, and yes, she can sacrifice herself and any Auras she's wearing, like [[Kaya's Ghostform]], and that Ghostform ability will still see the death and proc to bring her back. 
> "Snow" is a supertype, not a card type. Sacrificing Snow or Legendary cards doesn't give Baba anything extra. 
> Ironically, "Kindred" actually is a card type, not a supertype like Legendary or Snow. There are weird and annoying rules reasons for this, take it up with Wizards. But yes, if you sacrificed a [[Lignify]], that counts for 2 types.
> 
> Notable Exclusions:
> Anything that costs 4 or more mana to achieve multiple card types is just too high of a mana cost. Baba is a high-profile target and the linchpin for the whole deck, she can't really wait for us to get our bearings or set up a value engine. I barely feel comfortable with things that cost 3 mana for all 3 card types, even.
> [[Sting, the Glinting Dagger]]: I like the idea here, untapping your commander each round to activate her multiple times. The problem is, you need 3 things to eat every time you activate her. The supply of fuel will drain much faster than you can refill it, so I personally caution against this line of play unless you have a much 
> "Kindred" card types - I'm still tinkering with these, but as of right now, I haven't found many Kindred cards that I'm compelled to put into this list. The most likely candidates would be [[Lignify]] or [[Bitterblossom]]. A lot of folks have suggested [[Thornbite Staff]] too, which could be a good final "activate-Baba-multiple-times-for-a-final-burst-of-damage" play, I suppose, but I don't own one and haven't tested it yet, and for now, Bogbeast and other win cons have been more fun for me anyway.
> [[Gloomshrieker]] it has 2 types, but I don't like exiling it, personally. Could still be worth it.
> [[Fungal Fortitude]] and [[Not Dead After All]] and other pop-back effects: I want to play more and more of these, though I prefer the ones that bring things back untapped whenever possible, given how strong that interaction can be with ability haste (like [[Thousand-Year Elixir]]).
> [[Silversmote Ghoul]] and [[Sméagol, Helpful Guide]] - these are super good in theory, and the new [[Moseo, Vein's New Dean]] is also very compelling. However, I try to activate Baba on other peoples' turns rather than on my own, if I can help it, so as to activate cards like [[Tragic Slip]] and mitigate potential aggression when people move to combat and start looking at high life totals. 
> [[Ulvenwald Mysteries]] - I respect the crap out of these types of cards, and I think there's a very reasonable case to play a different version of Baba that makes amazing use of them. I've opted for a version of Baba that starts activations right away and tries to activate her every single round.  This means I'm sacrificing the long-term for the short-term, most regularly by devouring my own lands, in the hope that I'll draw into some recursion spell to get them all back. That's an extremely risky proposition that some Baba players may prefer not to go for. Instead, steady engines like [[Ulvenwald Mysteries]] that supply fodder every turn without compromising your long-term prospects or permanently reducing your resources, and which convert the loss of 1 item into the creation of another item, could be a very cool way to build this deck. I respect the crap out of those players, I just went with a greedier and riskier version. 
> [[Ashaya, Soul of the Wild]] and [[Biotransference]] - mass type-changing cards are rad, but Biotransference turned out to be a huge liability (making everything vulnerable to get [[Vandalblast]]ed, for instance) and Ashaya is a very high-mana card for this deck's curve. I think these would also be good candidates for a more long-term-minded version of Baba. 
> [[Bastion of Remembrance]] and other AOE damage effects: I want my win conditions to be able to point in 1 direction. Plus, some cards, like Bastion, are the kinds of things you end up not wanting to ever eat. I'm trying to be more careful with how many cards I play that I'm truly unwilling to sacrifice.
> Lifegain payoffs - I'm strongly considering a few more of these, like [[Enduring Tenacity]] or the new [[Defiling Daemogoth]], as some alternative win con options. I'm not sold on them here just yet, but there's strong potential.
> [[The Gitrog Monster]] is a strong card advantage engine, but it's 5 mana and I'm unwilling to sacrifice it. I'm trying to save my 5+ mana cards that I don't want to eat for my win con slots. I think it's relevant, though, that card advantage is rarely a thing Baba will struggle with (hence why I'm also not running eatable enchantments like [[Treacherous Blessing]] or [[Demonic Lore]]). There's definitely more to explore here for longer-term versions of the deck, but in general, any backup draw I use, I'd rather be a little cheaper, and be able to work even if Baba can't stick in play (such as [[Braids, Arisen Nightmare]]). 
> Other Game Changers: I currently only have [[Field of the Dead]] in here, though if I were to include more, [[Glacial Chasm]] and [[Crop Rotation]] are probably the only others I'd consider. They'd be ludicrously strong here, though, and I already worry I'm punching harder than I should be at this bracket to begin with. I haven't felt the need to play more Game Changers, and this deck is very clearly Bracket 3 even without those other Game Changer signals in the 99. 
> 
> One Final Note:
> This version of the deck doesn't 100% reflect what I'm currently experimenting with IRL at the moment. After the 200-card Extra Turns episode, I've actually kept Baba in a 200-card paper version, just for kicks. I'm keeping this version up to date with changes I would make if I wasn't tinkering and experimenting with this 
> 
> 
> 
> 

## Appendix B — Vivi Ornitier, semi-budget EDH (Archidekt 13765265)

Kept whole partly for the tie-in: this is the same commander the
owner's own Vivi deck work targeted earlier in this campaign.

> Core Concept
>  The deck functions as a linear Izzit spellslinger–storm shell. Your plan is to ramp and reduce spell costs early, ensure that [[Vivi Ornitier]]  can safely enter the battlefield and survive one turn, and then untap and combo off. You run a very high density of replacement spells, cantrips, and pseudo-draw, which continuously grow [[Vivi Ornitier]] while keeping your hand full. Once your engines are online, every spell you cast essentially replaces itself or generates additional value.
> 1. Early Game: Ramp, Setup, Cost Reduction
> Goal: Assemble mana engines and cost reducers. Do not cast [[Vivi Ornitier]] yet.
> Key pieces:
> 
> Cost Reduction: [[Ruby Medallion]], [[Helm of Awakening]], [[Stormcatch Mentor]], [[Artist's Talent]], [[Case of the Ransacked Lab]], [[Ral, Monsoon Mage // Ral, Leyline Prodigy]].
> Mana Engines: [[Runaway Steam-Kin]], [[Storm-Kiln Artist]], [[Brass's Bounty]], [[Mana Geyser]], [[Seething Song]].
> Card Advantage Engines: [[Rhystic Study]], [[Archmage of Runes]], [[Niv-Mizzet, Visionary]], [[Niv-Mizzet, Parun]].
> Use counters to stop real threats, not to protect value engines. Save protection for [[Vivi Ornitier]].
> 2. [[Vivi Ornitier]] Enters: “Stick Turn”
> Cast [[Vivi Ornitier]] only when you can leave meaningful interaction open.
> Typical sequence:
> Cost reducers + mana engines in place.
> Cast [[Vivi Ornitier]].
> Keep up protection: [[Fierce Guardianship]], [[Deflecting Swat]], [[Dispel]], [[Negate]], [[Counterspell]], [[Shore Up]], [[Magic Damper]], [[Swiftfoot Boots]] Fierce Guardianship, Deflecting Swat, Dispel, Negate, Counterspell, Shore Up, Magic Damper, Swiftfoot Boots.
> If Vivi survives a full rotation, the setup is complete.
>  Once Vivi untaps, you usually win.
> 3. Combo Turn: Draw Chain, Storm Line, Pump Line
> Start chaining your massive number of cheap spells.
> 
> Replacement / Draw Spells
> [[Crimson Wisps]], [[Expedite]], [[Opt]], [[Preordain]], [[Gitaxian Probe]], [[Brainstorm]], [[Frantic Search]], etc.
>  → They replace themselves.
>  → Vivi triggers and grows.
>  → With cost reduction, many of them cost 0 mana during the combo turn.
> Copy Effects
> [[Reiterate]], [[Bonus Round]], [[Display of Power]], [[Flare of Duplication]], [[Harmonic Prodigy]], [[Marvin, Murderous Mimic]], [[Veyran, Voice of Duality]]
>  → Multiply value, triggers, and mana.
> 
> Mana Explosion
> [[Storm-Kiln Artist]], [[Runaway Steam-Kin]], [[Seething Song]], [[Mana Geyser]], 
>  → Practical unlimited mana during the combo turn.
> 
> Convergence Points: Actual Win Paths
> A. Storm Finish
> 
> [[Mind's Desire]]
> [[Bonus Round]] + [[Reiterate]] loops
> [[Mizzix's Mastery]] as pseudo-storm
> B. Draw Loops → Direct Damage
> 
> [[Niv-Mizzet, Parun]] kills the table once loops start
> [[Curiosity]] / [[Ophidian Eye]] / [[Tandem Takedown]]  = infinite triggers
> C. [[Vivi Ornitier]]  Becomes the Wincon
>  Dozens of spell triggers → Vivi grows to lethal damage output.
> D. [[Ojer Axonil, Deepest Might // Temple of Power]] Shortcut
>  All [[Vivi Ornitier]]  damage becomes minimum 4.
>  20+ [[Vivi Ornitier]]  triggers = lethal for the entire table.
> E. Omniscience
>  Once resolved, you simply unload your entire hand/library.
> 4. Concrete Win Lines
> 1. [[Bonus Round]]  → cantrip chain → exponential Vivi scaling.
> 2. [[Reiterate]]  + [[Seething Song]] = Infinite Mana
>  → Infinite spells for [[Vivi Ornitier]] 
>  → Infinite [[Storm-Kiln Artist]]  triggers
>  → Infinite [[Vivi Ornitier]]  or [[Niv-Mizzet, Parun]]  damage.
> 3. Display of Power into a Bonus Round stack
>  → Triple copies → massive storm → [[Mind's Desire]]  
> 4. [[Vivi Ornitier]]  + [[Curiosity]] / [[Ophidian Eye]] / [[Tandem Lookout]]
>  → Damage draws cards → draws cast spells → spells deal damage
>  → Fully self-sustaining loop.
> 5. Playstyle
> This is a control-storm hybrid:
> 
> You don’t need mass removal; [[Cyclonic Rift]] is your only real reset.
> You wait for the exact turn cycle where nobody can meaningfully interact.
> Then you unload, generate storm/mana/card advantage, and win in one go.
> The deck is designed to avoid “forced” storm turns; your engines make the combo turn naturally self-sustaining.
> 
> 
> EDIT: I have recently decided to cut some of the fetchlands. This is due to me not playing many important fetchable lands, thus the use of the cards is rather limited. I instead opted for adding them to my [[Sméagol, Helpful Guide]]  Deck, which I also play a lot more frequent. 
> 
> You call this SEMI-BUDGET?!
> I specifically addressed this in a comment below. I hope that this is reasonable.

## Appendix C — The Magdanomicon (Moxfield 8Y4qOAcLN0O_HHYhOboV3Q, 834 likes)

Moxfield exemplar: markdown/plain text, no embeds — a community
"megaprimer" mission statement.

> [Last Update: 8/09/26 - Blood Moon Variant Moved To New List (in primer intro section) - Turbo Slanted in Considering] This deck seeks to control the game with its diverse interaction package and tutorable silver bullet targets, eventually finding an artifact combo to leverage your commander abilites ability to win. Comprehensive primer for new and experienced players aimed to help players make their own changes based on playstyle preferences or meta requirements.  Essentially this functions as the Magda CEDH community's Megaprimer. Shodokan's list is current front facing & test/active list in the opening section of the primer, Rust_ITG's decklist link is also in the opening section of the primer. Come chat, ask questions and hang out in the Magda discord server: Discord.gg/magda
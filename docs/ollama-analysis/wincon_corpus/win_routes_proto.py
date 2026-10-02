"""Prototype win-route classifier for the research (NOT repo code).
Inputs: corpus.json (58 decks: cmd, cards, primer text), oracle capture
(name -> oracle fields), combos capture (top-1500 Spellbook)."""
import json, re, sys, collections
S = sys.argv[1]; ORACLE = sys.argv[2]; COMBOS = sys.argv[3]
corpus = json.load(open(f"{S}/corpus.json"))
oracle = json.load(open(ORACLE))["cards"]
combos = json.load(open(COMBOS))["combos"]

def front(n): return n.split(" // ", 1)[0]
def card(n):
    return oracle.get(n) or oracle.get(front(n))
def text(n):
    c = card(n); return ((c or {}).get("oracle_text") or "").lower()
def types(n):
    c = card(n); return ((c or {}).get("type_line") or "").lower()

GAME_ENDING = ("win the game", "win ", "infinite", "mill out", "lose the game")
def game_ending(c): 
    p = str(c.get("produces", "")).lower(); return any(t in p for t in GAME_ENDING)

# --- route patterns (oracle text, lowercase) ---
ALT_WIN = re.compile(r"you win the game|target opponent loses the game|each opponent loses the game|each player who .* loses the game")
DRAIN_TRIG = re.compile(r"(whenever|when) [^.]*?, (each opponent loses|target opponent loses|you may have target opponent lose|each player loses)")
DRAIN_BIG = re.compile(r"each opponent loses (x|\d+) life|loses life equal to")
BURN_EACH = re.compile(r"deals (\d+|x|that much) damage to each opponent|deals damage equal to [^.]* to each opponent|deals \d+ damage to each (player|creature and each player)|deals x damage to any target")
POISON = re.compile(r"\binfect\b|\btoxic \d|poison counter|proliferate")
MILL_OPP = re.compile(r"(target player|each opponent|target opponent|each player) mills|mills (that many|x|\d+) cards|puts the top [^.]* of (their|his or her) library into (their|his or her) graveyard")
OVERRUN = re.compile(r"creatures you control (get \+[\dx]+/\+[\dx]+ (and|until)[^.]*trample|gain trample and get)|craterhoof|for each creature you control")
ANTHEM = re.compile(r"(other )?creatures you control get \+\d/\+\d|creature tokens you control get \+")
TOKEN_MAKER = re.compile(r"create (a|one|two|three|four|x|that many|\d+) [^.]*creature tokens?")
EQUIP = re.compile(r"\bequip\b|enchant creature|enchanted creature gets|equipped creature gets")
CMDR_DMG = re.compile(r"commander|double strike|can't be blocked|unblockable|extra combat|additional combat phase")
EXTRA_COMBAT = re.compile(r"additional combat phase")
BIG_X = re.compile(r"deals x damage|x damage divided")
STAX = re.compile(r"can't cast|can't untap|players can't|each player can't|skip their|opponents can't")


KILL_FEATS = ("win the game", "loses the game", "infinite damage", "near-infinite damage",
              "infinite lifeloss", "near-infinite lifeloss", "infinite mill", "infinite combat damage",
              "infinite creature tokens with haste", "infinite combat phases", "infinite turns",
              "infinitely large creature")
RESOURCE_KIND = {  # feature substring -> outlet kind it needs
    "creature etb": "etb", "creature ltb": "ltb", "death triggers": "death", "sacrifice triggers": "death",
    "creature tokens": "tokens", "storm count": "storm", "card draw": "draw", "draw triggers": "draw",
    "mana": "mana", "lifegain": "lifegain", "landfall": "landfall", "artifact etb": "artifact_etb",
    "magecraft": "magecraft", "+1/+1 counters": "counters", "blink": "etb", "untap": "mana",
}
def combo_kind(c):
    p = c["produces"].lower()
    if any(k in p for k in KILL_FEATS): return "kill", set()
    needs = {v for k, v in RESOURCE_KIND.items() if k in p}
    return ("resource", needs) if needs else ("value", set())
OUTLET = {  # outlet kind -> oracle regex that converts the resource into a kill
    "etb": re.compile(r"whenever (a|another) creature (you control )?enters[^.]*(deals? \d+ damage to each opponent|each opponent loses \d+ life)"),
    "ltb": re.compile(r"whenever (a|another) creature (you control )?(dies|leaves)[^.]*(loses? \d+ life|deals? \d+ damage)"),
    "death": re.compile(r"whenever (a|another|a nontoken) creature (you control )?dies[^.]*(each opponent loses|target opponent loses|loses \d+ life|deals? \d+ damage)"),
    "tokens": re.compile(r"creatures you control (get \+|gain trample|have haste)|creature tokens you control (get|have)|haste"),
    "storm": re.compile(r"\bstorm\b|for each spell cast|instants and sorceries you've cast this turn"),
    "draw": re.compile(r"whenever you draw a card[^.]*(deals? \d+ damage|loses \d+ life)|you win the game|target opponent loses the game"),
    "mana": re.compile(r"deals x damage|x damage divided|each opponent loses x life|\{x\}[^.]*:(?:[^.]*)deals? (1|x) damage"),
    "lifegain": re.compile(r"whenever you gain life[^.]*(loses? \d+ life|deals? \d+ damage|put a \+1/\+1 counter)"),
    "landfall": re.compile(r"landfall[^.]*(deals? \d+ damage|loses? \d+ life)|whenever a land (you control )?enters[^.]*(deals? \d+ damage|loses? \d+ life)"),
    "artifact_etb": re.compile(r"whenever an artifact (you control )?enters[^.]*(deals? \d+ damage|loses? \d+ life)"),
    "magecraft": re.compile(r"magecraft[^.]*(deals? \d+ damage|loses? \d+ life|draw a card)"),
    "counters": re.compile(r"trample|can't be blocked|double strike|fling|deals damage equal to its power"),
}
def classify(deck):
    cards = list(dict.fromkeys(deck["cmd"] + deck["cards"]))
    have = {c.lower() for c in cards} | {front(c).lower() for c in cards}
    R = collections.defaultdict(list)
    present = [c for c in combos if all(x.lower() in have for x in c["cards"])]
    kills, resource, value = [], [], []
    alltext = {n: text(n) for n in cards}
    outlets = {k: [n for n, t in alltext.items() if rx.search(t)] for k, rx in OUTLET.items()}
    for c in present:
        kind, needs = combo_kind(c)
        if kind == "kill": kills.append(c)
        elif kind == "resource":
            if any(outlets[k] for k in needs): kills.append({**c, "via": sorted(k for k in needs if outlets[k])})
            else: resource.append(c)
        else: value.append(c)
    one = [c for c in combos if combo_kind(c)[0] == "kill" and sum(x.lower() not in have for x in c["cards"]) == 1]
    for c in kills: R["combo"].append(" + ".join(c["cards"]) + (f" [via {','.join(c['via'])}]" if c.get("via") else ""))
    stats = {"combo_kill": len(kills), "combo_resource_no_outlet": len(resource), "combo_value": len(value), "combo_one_away": len(one)}
    for n in cards:
        t = alltext[n]; ty = types(n)
        if not t and not ty: continue
        if ALT_WIN.search(t): R["alt_win"].append(n)
        if DRAIN_TRIG.search(t) or DRAIN_BIG.search(t): R["drain"].append(n)
        if BURN_EACH.search(t) or (BIG_X.search(t) and ("sorcery" in ty or "instant" in ty)): R["burn"].append(n)
        if "infect" in t or re.search(r"toxic \d", t) or "poison counter" in t: R["poison"].append(n)
        if MILL_OPP.search(t) and "you mill" not in t: R["mill"].append(n)
        if OVERRUN.search(t): R["overrun"].append(n)
        if ANTHEM.search(t): R["anthem"].append(n)
        if TOKEN_MAKER.search(t): R["tokens"].append(n)
        if EQUIP.search(t) and ("equipment" in ty or "aura" in ty): R["voltron_gear"].append(n)
        if EXTRA_COMBAT.search(t): R["extra_combat"].append(n)
        if "creature" in ty:
            c = card(n) or {}
            try: p = int(str(c.get("power") or "0").replace("*", "0"))
            except ValueError: p = 0
            if p >= 5: R["fatties"].append(n)
        if STAX.search(t): R["stax"].append(n)
    routes = {}
    routes["combo"] = len(kills) >= 1
    routes["alt_win"] = len(R["alt_win"]) >= 1
    routes["drain"] = len(R["drain"]) >= 3
    routes["burn"] = len(R["burn"]) >= 3
    routes["poison"] = len(R["poison"]) >= 5
    routes["mill"] = len(R["mill"]) >= 4
    routes["combat_wide"] = (len(R["overrun"]) >= 1 and len(R["tokens"]) >= 4) or (len(R["anthem"]) >= 3 and len(R["tokens"]) >= 4)
    routes["combat_voltron"] = len(R["voltron_gear"]) >= 8
    routes["combat_big"] = len(R["fatties"]) >= 10 or (len(R["fatties"]) >= 7 and (len(R["extra_combat"]) >= 1 or len(R["overrun"]) >= 1))
    return {"routes": [k for k, v in routes.items() if v], "signals": {k: len(v) for k, v in R.items()}, "pieces": {k: v[:8] for k, v in R.items()}, "outlets": {k: v[:4] for k, v in outlets.items() if v}, **stats}

out = {}
for k, d in corpus.items():
    out[k] = classify(d)
    cov = sum(1 for n in d["cmd"] + d["cards"] if card(n)) / max(1, len(d["cmd"] + d["cards"]))
    out[k]["oracle_coverage"] = round(cov, 3)
json.dump(out, open(f"{S}/routes.json", "w"), indent=1)
for k, d in corpus.items():
    o = out[k]
    print(f"{k:32s} {d['cmd'][0][:28]:28s} cov={o['oracle_coverage']:.2f} kill/res/val/1away={o['combo_kill']}/{o['combo_resource_no_outlet']}/{o['combo_value']}/{o['combo_one_away']} routes={o['routes']} sig={ {a:b for a,b in o['signals'].items() if b} }")

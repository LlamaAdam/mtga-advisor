# DATA_CLEANUP.md — mtga_draft_helper

> Inventory of accumulated data cruft and a prioritized cleanup plan.
> Living doc — items get checked off as they're applied.
>
> Written 2026-04-27 during a state survey. None of this is destructive
> until you choose to act on it; cataloging first, applying second.

---

## What we found

### Tracked files that probably shouldn't be in git

| File | Size | Why it's a problem |
|---|---|---|
| `Screenshot 2026-04-05 005301.png` | **4.1 MB** | Debug capture from 3 weeks ago; appears unused. Inflates clone size for nothing. |
| `arena_id_cache.json` | **1.6 MB** | Machine-rebuildable cache (Arena ID → name + sparse oracle data for ~14k cards). Re-fetched on first run. Re-bloats every time it's modified, which is often. |
| `ratings_cache.json` | **820 KB** | 17lands GIH win-rate cache. Re-fetched per draft set. Same churn problem. |
| `__pycache__/*.pyc` (10 files) | ~250 KB | Python bytecode. **Should never be tracked.** Already in .gitignore but the rule was added *after* these were committed, so they're still tracked. |
| `.claude/settings.local.json` | small | Per-user Claude settings; should probably be in `.claude/` gitignore but isn't. |

Total: ~6.7 MB of avoidable bloat. Not huge in absolute terms but it
all churns frequently, so the *delta history* is much larger than the
file sizes suggest. Every modification to `arena_id_cache.json` adds
~1.6MB to git's pack file.

### Untracked files that might or might not need attention

| File | Status | Recommendation |
|---|---|---|
| `Launch Draft Helper (no console).vbs` | Untracked | TRACK — these are useful Windows launchers, should be in repo. |
| `Launch Draft Helper.bat` | Untracked | TRACK — same. |
| `draft_advisor.py` | Untracked | INVESTIGATE — is this an in-progress new module or dead code? |
| `game_advisor/saved_decks.json` | Untracked | GITIGNORE — user state, not code. |
| `.claude/scheduled_tasks.lock` | Untracked | GITIGNORE — runtime lockfile. |

### Empty / vestigial directories

- `game_advisor/logs/` — empty (`du -sh` returns 0). Probably gets
  populated at runtime; should be gitignored once it starts producing
  real logs. Add `game_advisor/logs/*` to .gitignore preemptively.

### Existing `.gitignore` gaps

Current `.gitignore` covers:
- ✅ Python bytecode patterns (`__pycache__/`, `*.pyc`, etc.)
- ✅ Build artifacts
- ✅ Editor / IDE
- ✅ Test cache
- ✅ Secret files

Missing rules:
- ❌ Cache files (`arena_id_cache.json`, `ratings_cache.json`)
- ❌ Screenshots / debug captures (`Screenshot *.png`)
- ❌ Runtime logs (`game_advisor/logs/`)
- ❌ User-state JSONs (`game_advisor/saved_decks.json`)
- ❌ Lockfiles (`.claude/scheduled_tasks.lock`)

---

## Cleanup options, ranked by safety

### Option 1 — Tighten `.gitignore` (SAFE, no destructive ops) ✅ recommended

Add the missing rules. New tracked files matching these patterns won't
get added going forward, but **existing tracked files keep their
tracking** — Git doesn't retroactively untrack files just because the
gitignore changed.

This is the smallest reversible step. **Do this first.**

### Option 2 — Untrack already-committed cache files (SAFE if done with `--cached`)

Run `git rm --cached <file>` for each cache file. This removes them
from the index but keeps them on disk. Combined with Option 1, future
commits won't include them. The history still contains the old
versions, but the working tree stops churning them.

Files to untrack:
- `__pycache__/*.pyc` (10 files)
- `arena_id_cache.json`
- `ratings_cache.json`
- `Screenshot 2026-04-05 005301.png`
- `.claude/settings.local.json`

This is mildly disruptive — anyone else cloning the repo will need
to regenerate the caches on first run, which is the correct behavior.

### Option 3 — Track the launcher files

Add the three untracked launchers to git so they're shareable:
- `Launch Draft Helper (no console).vbs`
- `Launch Draft Helper.bat`

Already-tracked: `Launch MTGA Advisor.bat`, `Launch MTGA Advisor (no console).vbs`.
The Draft Helper launchers were probably forgotten when added.

### Option 4 — Track `draft_advisor.py` ✅ INVESTIGATED 2026-04-27

**Finding.** `draft_advisor.py` (266 lines) is **live production code** —
imported by `main.py` at lines 35, 138, 141, 193. It provides LLM-powered
explanation of close draft picks via the Ollama/OpenAI backend (mirrors
`game_advisor/llm_advisor.py`). It was simply forgotten in `git add` after
creation.

**Action.** TRACK it (Option 3 / 4 are now the same operation).

If you run the program with this file missing, `import draft_advisor`
fails on startup. So this isn't optional — the file *must* be there for
the program to work, but it's not in git, so a fresh clone is broken.

### Option 5 — Rewrite history to remove tracked binary blobs (RISKY)

`git filter-repo` could strip `Screenshot 2026-04-05 005301.png` and
the historical cache versions from history entirely, shrinking the
repo. **Don't do this** unless:
- You're ok with rewriting commit hashes
- No one else has cloned this repo (force-push required)
- You verify backups first

This is heavy machinery for a 4MB savings. Skip unless the repo grows
to a real problem size.

### Option 6 — Adopt the shared `mtg_cards/` folder (BIGGER LIFT)

Per `FUTURE_PLANS.md` FP-A: stop maintaining `arena_id_cache.json`'s
oracle data locally. Use the shared `C:\dev\mtg_cards\oracle_snapshots\`
store instead. The Arena-ID-to-name mapping stays here (Arena IDs
don't exist in Scryfall data), but the oracle text + cmc + type_line
data moves out.

This is part of the planned consolidation across all three MTG
projects. Tracked as FP-A in FUTURE_PLANS.md, not a quick cleanup.

---

## Recommended cleanup order

1. **Update `.gitignore`** (Option 1). 5 minutes. Reversible. Does
   nothing destructive.
2. **Investigate `draft_advisor.py`** (Option 4). 10 minutes. Decide
   keep or remove.
3. **Track the launchers** (Option 3). 1 minute.
4. **Untrack the committed caches** (Option 2). 15 minutes. Verify
   the working tree is intact after `git rm --cached`.
5. **Defer Option 5 indefinitely** unless the repo size becomes
   painful.
6. **Plan FP-A** for a future session — shared oracle store via
   `mtg_cards/`. Bigger lift, real architectural value.

---

## Status checkboxes

- [x] Option 1 — `.gitignore` updated with cache + screenshot + logs + lockfile rules (2026-04-27)
- [x] Option 2 — Tracked caches `git rm --cached`'d (2026-04-27): 10 `__pycache__/*.pyc`, `arena_id_cache.json`, `ratings_cache.json`, `Screenshot 2026-04-05 005301.png`, `.claude/settings.local.json`. All 14 files remain on disk; only the index changed. Tests all pass.
- [x] Option 3 — Launchers tracked (2026-04-27): `Launch Draft Helper.bat`, `Launch Draft Helper (no console).vbs`, plus `draft_advisor.py` (which was live code never `git add`'d).
- [x] Option 4 — `draft_advisor.py` investigated and resolved (now tracked).
- [x] Option 6 — FP-A shared-oracle migration ✅ DONE 2026-04-27. `card_db.get_oracle/cmc/type_line/mana_cost` now consult `C:\dev\mtg_cards\oracle_snapshots\` first. 16 tests added; FP-B (LLM card-text appendix) follows on top of this.

(Boxes checked as actions land. Unchecked = pending.)

## What's left

**Option 5 (history rewrite via `git filter-repo`) — permanently
skipped (user-confirmed 2026-04-27).** The repo isn't big enough to
justify the destructive operation. The 4MB screenshot stays in past
commits but won't be added going forward.

(Boxes checked as actions land. Unchecked = pending.)

---

## How to apply Option 1 (the safe first step)

Append the following to `.gitignore`:

```gitignore
# Caches that get rewritten frequently — never commit these.
arena_id_cache.json
ratings_cache.json

# User state (per-installation, not code).
game_advisor/saved_decks.json

# Runtime logs (populated at execution time).
game_advisor/logs/
*.log

# Debug screenshots / captures (rotate as needed).
Screenshot *.png
*.screenshot.png

# Claude Code per-user lockfiles.
.claude/scheduled_tasks.lock
.claude/settings.local.json
```

Then verify with:

```cmd
git status
:: → should not show any of the above as modified or untracked-of-interest
```

(That doesn't fix the *already tracked* files — that's Option 2's job.
But Option 1 is the prerequisite to Option 2, and it's safe to do
on its own.)

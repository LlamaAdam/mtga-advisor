"""
MTGA Draft Helper - Main entry point.

How it works:
  1. Reads Arena's Player.log to detect when a draft starts and what
     cards are in each pack (no screen capture / OCR needed).
  2. Fetches GIH win rates from the 17Lands API for the detected set.
  3. Shows a transparent overlay with letter grades and win rates
     over each card's position on screen.
  4. Highlights the recommended "best pick" based on your current
     deck colors.

First-time setup:
  pip install -r requirements.txt
  python calibrate.py     (set card overlay positions for your screen)
  python main.py

Controls (while overlay is open):
  R      = force refresh badges
  U      = undo last recorded pick
  C      = clear deck / start new draft
  ESC    = quit
"""

import threading
import time

from . import api
from . import card_db
from . import ratings as ratings_engine
from .deck import DeckTracker
from .log_scanner import ArenaLogScanner
from .overlay import OverlayApp
from . import config
from . import draft_advisor


def main():
    print("=" * 55)
    print("  MTGA Draft Helper  |  Powered by 17Lands")
    print("=" * 55)
    print(f"\n  Arena log:    {config.ARENA_LOG_PATH}")
    print(f"  Ratings cache: {config.RATINGS_CACHE_FILE}\n")

    tracker = DeckTracker()
    app = OverlayApp(tracker)
    scanner = ArenaLogScanner()

    # ------------------------------------------------------------------
    # Wire up log scanner callbacks
    # ------------------------------------------------------------------

    def on_draft_start(set_code: str, draft_format: str):
        """Called when a new draft begins — fetch card names + ratings for this set."""
        print(f"\n[main] Draft detected: {set_code} {draft_format}")
        print(f"[main] Looking for cache at: {config.RATINGS_CACHE_FILE}")
        tracker.clear()

        # Try cache first
        cached = api.load_cache(set_code, draft_format)
        if cached:
            print(f"[main] Using cached ratings for {set_code} ({len(cached)} entries).")
            ratings_engine.load(cached)
            app.set_status(f"Ratings loaded — {set_code} (cached)")
            # Resync overlay with now-loaded ratings (safe from any thread)
            threading.Thread(target=do_resync, daemon=True).start()
            return

        print(f"[main] Fetching 17Lands ratings for {set_code} {draft_format}...")

        def fetch():
            # Preload card names first so packs resolve correctly
            card_db.preload_set(set_code)

            def progress(i, total, label):
                pct = int(i / total * 100)
                print(f"  [{pct:3d}%] {label}")
                app.set_status(f"Loading ratings… {pct}%")

            try:
                print(f"[main] Starting 17Lands fetch for {set_code} {draft_format}...")
                data = api.fetch_all_ratings(
                    set_code,
                    draft_format,
                    progress_callback=progress,
                )
                print(f"[main] Fetch complete — {len(data)} cards returned.")
                api.save_cache(set_code, draft_format, data)
                print(f"[main] Cache saved to: {config.RATINGS_CACHE_FILE}")
                ratings_engine.load(data)
                print(f"[main] Ratings ready for {set_code}. Refreshing overlay...")
                app.set_status(f"Ratings loaded — {set_code}")
                # Auto-refresh badges now that ratings are available
                do_resync()
            except Exception as e:
                import traceback
                print(f"[main] Failed to fetch ratings: {e}")
                traceback.print_exc()
                app.set_status("Ratings failed — press R to retry")

        threading.Thread(target=fetch, daemon=True).start()

    def on_pack_update(card_names: list[str]):
        """Called whenever a new pack is shown."""
        tracker.sync_from_log(scanner.state)
        pack_num  = scanner.state.pack_number
        pick_num  = scanner.state.pick_number
        orig      = scanner.state.original_pack_size

        # Pack-opening pick (pick 1 of packs 2 and 3): recommend the strongest
        # card by absolute win rate regardless of current deck colors.
        # Taking the best card in the pack signals and preserves flexibility.
        is_pack_opener = (pick_num == 1 and pack_num >= 2)

        best = tracker.best_pick(card_names, ignore_colors=is_pack_opener)
        app.schedule_update(card_names, best, orig)

        if best and ratings_engine.is_loaded():
            # Grade all cards and sort descending
            graded = sorted(
                [(name, *tracker.adjusted_rating(name)) for name in card_names if name],
                key=lambda x: x[1] if x[1] is not None else -999,
                reverse=True,
            )
            print(f"\n  === Pack {pack_num} | Pick {pick_num} ===")
            if is_pack_opener:
                print(f"  [Pack opener — recommending strongest card regardless of color]")
            print(f"  {'Grade':<6} {'WR':>6}   Card")
            print(f"  {'-'*42}")
            for name, wr, grade in graded:
                wr_s = f"{wr:.1f}%" if wr is not None else "  N/A"
                arrow = "  <-- PICK THIS" if name == best else ""
                print(f"  {grade:<6} {wr_s:>6}   {name}{arrow}")

            # LLM explanation — fires async when the decision is genuinely close
            # or at the start of a new pack. Output appears below the card table.
            main_colors = tracker.main_colors()
            if draft_advisor.should_explain(graded, main_colors, pack_num, pick_num):
                def _on_advice(text: str):
                    print(f"\n  [Advisor] {text}\n")
                draft_advisor.explain_pick_async(
                    pack_number=pack_num,
                    pick_number=pick_num,
                    top_cards=graded,
                    picks_so_far=tracker.picks,
                    main_colors=main_colors,
                    on_complete=_on_advice,
                )

    def on_pick(card_name: str):
        """Called when the player picks a card."""
        tracker.sync_from_log(scanner.state)
        orig = scanner.state.original_pack_size
        app.schedule_update(scanner.state.current_pack, None, orig)

        if not ratings_engine.is_loaded():
            return

        wr, grade = tracker.adjusted_rating(card_name)
        wr_str = f"{wr:.1f}%" if wr is not None else "N/A"
        print(f"  Picked: {card_name} ({grade}, {wr_str})")

        # Mid-draft review every 5 picks — catch direction problems early
        n_picks = len(tracker.picks)
        if n_picks > 0 and n_picks % 5 == 0:
            _fire_draft_review(scanner.state.pack_number, scanner.state.pick_number)

    def _fire_draft_review(pack_number: int, pick_number: int) -> None:
        """Build pick context and fire an async mid-draft review via the LLM."""
        from . import ratings as _r

        picks_with_meta: list[tuple[str, str, str]] = []
        curve: dict[int, int] = {}
        for name in tracker.picks:
            _, grade = tracker.adjusted_rating(name)
            colors = "".join(_r.get_colors(name)) or "C"  # C = colorless
            picks_with_meta.append((name, grade, colors))
            cmc = _r.get_cmc(name)
            if cmc is not None:
                curve[cmc] = curve.get(cmc, 0) + 1

        main_colors = tracker.main_colors()

        def _on_review(text: str) -> None:
            total = len(tracker.picks)
            print(f"\n  {'=' * 50}")
            print(f"  MID-DRAFT REVIEW  ({total} picks in)")
            print(f"  {'=' * 50}")
            for line in text.splitlines():
                print(f"  {line}")
            print(f"  {'=' * 50}\n")

        draft_advisor.review_draft_async(
            pack_number=pack_number,
            pick_number=pick_number,
            picks=picks_with_meta,
            main_colors=main_colors,
            curve=curve,
            on_complete=_on_review,
        )

    def _ensure_ratings_loaded():
        """Load ratings from cache (or fetch) if not yet loaded. Called before resync."""
        if ratings_engine.is_loaded():
            return

        # Use set_code already found by recover_current_draft, or fall back to log scan
        sc  = scanner.state.set_code
        fmt = scanner.state.draft_format or "QuickDraft"

        if not sc:
            try:
                with open(scanner.log_path, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read()
                set_info = scanner._extract_set_code(content)
                if not set_info:
                    print("[main] Cannot load ratings — no draft found in log.")
                    return
                sc, fmt = set_info
            except Exception as e:
                print(f"[main] Failed to read log: {e}")
                return

        print(f"[main] Ratings not loaded — checking cache for {sc} {fmt}...")
        try:
            cached = api.load_cache(sc, fmt)
            if cached:
                ratings_engine.load(cached)
                app.set_status(f"Ratings loaded — {sc} (cached)")
            else:
                print(f"[main] No cache — fetching from 17Lands (~30s)...")
                app.set_status(f"Fetching ratings for {sc}…")
                card_db.preload_set(sc)
                data = api.fetch_all_ratings(sc, fmt)
                api.save_cache(sc, fmt, data)
                ratings_engine.load(data)
                app.set_status(f"Ratings loaded — {sc}")
        except Exception as e:
            print(f"[main] Failed to load ratings: {e}")

    _resync_lock = threading.Lock()

    def do_resync():
        """
        Re-read the full log to rebuild picked cards and current pack.
        Called when the user presses R. Loads ratings from cache if not yet loaded.
        A lock prevents two resync threads from running simultaneously.
        """
        if not _resync_lock.acquire(blocking=False):
            return  # Another resync already in progress — skip
        try:
            _do_resync_inner()
        finally:
            _resync_lock.release()

    def _do_resync_inner():
        print("\n[main] Resyncing...")
        _ensure_ratings_loaded()

        found = scanner.resync()
        if found:
            tracker.sync_from_log(scanner.state)
            pack = scanner.state.current_pack
            is_pack_opener = (scanner.state.pick_number == 1 and scanner.state.pack_number >= 2)
            best = tracker.best_pick(pack, ignore_colors=is_pack_opener)
            orig = scanner.state.original_pack_size
            app.schedule_update(pack, best, orig)
            print(f"[main] Resync complete — {len(scanner.state.picked_cards)} picks loaded.")

            # Always print full summary to terminal as a readable fallback
            if ratings_engine.is_loaded():
                cf = tracker.color_filter_for_ratings()

                # Picked cards graded
                print(f"\n  === Picks so far (color filter: {cf or 'Undecided'}) ===")
                for name in tracker.picks:
                    wr, grade = tracker.adjusted_rating(name)
                    wr_s = f"{wr:.1f}%" if wr is not None else "N/A"
                    print(f"  {grade:<4} {wr_s:>6}   {name}")

                # Current pack — sorted best-to-worst
                if pack:
                    graded = sorted(
                        [(name, *tracker.adjusted_rating(name)) for name in pack if name],
                        key=lambda x: x[1] if x[1] is not None else -999,
                        reverse=True,
                    )
                    print(f"\n  === Pack {scanner.state.pack_number} | Pick {scanner.state.pick_number} ===")
                    print(f"  {'Grade':<6} {'WR':>6}   Card")
                    print(f"  {'-'*42}")
                    for name, wr, grade in graded:
                        wr_s = f"{wr:.1f}%" if wr is not None else "  N/A"
                        arrow = "  <-- PICK THIS" if name == best else ""
                        print(f"  {grade:<6} {wr_s:>6}   {name}{arrow}")
                print()
        else:
            print("[main] No active draft found during resync.")

    app.on_resync = do_resync

    scanner.on_draft_start = on_draft_start
    scanner.on_pack_update = on_pack_update
    scanner.on_pick        = on_pick

    # Scan existing log to recover any in-progress draft, then tail from end
    scanner.recover_current_draft()

    # Schedule a resync 1.5s after the mainloop starts.
    # This ensures badges refresh with real grades even if ratings were
    # loaded after the initial recovery callbacks already fired.
    threading.Thread(target=do_resync, daemon=True).start()

    # ------------------------------------------------------------------
    # Background log polling thread
    # ------------------------------------------------------------------

    def poll_loop():
        while app._running:
            try:
                scanner.poll()
            except Exception as e:
                print(f"[poll] Error: {e}")
            time.sleep(config.OVERLAY_REFRESH_SECONDS)

    poll_thread = threading.Thread(target=poll_loop, daemon=True)
    poll_thread.start()

    # ------------------------------------------------------------------
    # Unknown card resolver thread
    # Prompts the user on stdin whenever an arena ID can't be resolved.
    # ------------------------------------------------------------------

    def resolver_loop():
        seen = set()   # Don't prompt for the same ID twice per session
        while app._running:
            try:
                arena_id = card_db.pending_unknowns.get(timeout=1)
            except Exception:
                continue
            if arena_id in seen:
                continue
            seen.add(arena_id)
            try:
                print(f"\n[?] Unknown card ID {arena_id}.")
                print(f"    Type the card name exactly and press Enter to teach the program.")
                print(f"    (Leave blank and press Enter to skip and mark as invalid.)")
                name = input(f"    Card name for ID {arena_id}: ").strip()
            except EOFError:
                continue
            if name:
                card_db.learn_name(arena_id, name)
                # Resync so the newly named card appears correctly in the pack
                do_resync()
            else:
                card_db._bad_ids.add(arena_id)
                print(f"[card_db] Marked {arena_id} as permanently unknown.")

    resolver_thread = threading.Thread(target=resolver_loop, daemon=True)
    resolver_thread.start()

    print("[main] Overlay started. Open MTGA and start a draft!\n")
    app.run()
    print("\nGoodbye!")


if __name__ == "__main__":
    main()

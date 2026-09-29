"""Command line entry point.

    python -m weather_advice preview    # decide and print; touches no state
    python -m weather_advice check      # decide, record, alert once per night
    python -m weather_advice resolve    # confirm the NWS grid for the location
    python -m weather_advice report     # the history record
    python -m weather_advice doctor     # is this thing actually set up?

`preview` reads and writes nothing, so it is safe to run repeatedly -- the same
affordance the deal tracker's `preview` provides, and for the same reason: the
first thing you want on a new machine is to see what it WOULD do.

`check` is the scheduled command. It records every night to history, including
the nights it stays silent, because "the windows stayed shut for nine days" is
only visible if the quiet nights are written down too.
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from .config import CONFIG_FILE, Settings, env_file
from .db import History
from .models import Decision
from .notify import Notifier
from .weather import NWSClient, WeatherError
from .windows import evaluate

log = logging.getLogger("weather_advice")


def _now(settings: Settings, grid_tz: str = "") -> datetime:
    """Local wall-clock time, tz-aware.

    The forecast comes back with offsets attached, and the schedule is written
    in wall-clock time, so a naive `datetime.now()` would compare an aware
    timestamp to a naive one and raise -- or worse, be off by the UTC offset
    and pick the wrong night.
    """
    tz = ZoneInfo(grid_tz or "America/Chicago")
    return datetime.now(tz)


def _describe(d: Decision) -> str:
    head = {
        "open": "OPEN THEM",
        "marginal": "MARGINAL",
        "shut": "KEEP SHUT",
        "unknown": "UNKNOWN",
    }.get(d.route, d.route.upper())
    lines = [f"{head}  ({d.night})"]
    lines.append(Notifier.body_for(d))
    return "\n".join(lines)


def _fetch(settings: Settings, use_cache: bool = True):
    client = NWSClient(cache_path=settings.grid_cache)
    grid = client.resolve(settings.location.lat, settings.location.lon,
                          use_cache=use_cache)
    hours = client.hourly(grid)
    return client, grid, hours


def cmd_resolve(settings: Settings, args) -> int:
    client, grid, _hours = _fetch(settings, use_cache=False)
    pinned = settings.location.station
    print(f"ZIP in config    : {settings.location.zip_code}")
    print(f"coordinate used  : {grid.lat:.4f}, {grid.lon:.4f}"
          + ("   (approximate -- see below)" if settings.location.approximate else ""))
    print(f"NWS says that is : {grid.city}, {grid.state}")
    print(f"grid cell        : {grid.grid_id} {grid.grid_x},{grid.grid_y}")
    print(f"time zone        : {grid.time_zone}")
    print(f"cached to        : {settings.grid_cache}")

    # Confirm the pinned station is one NWS serves for this cell. A typo'd
    # identifier is otherwise indistinguishable from a station that is down:
    # both just produce no observations, quietly, for as long as it takes
    # someone to notice the accuracy table is empty.
    if pinned:
        nearby = client.nearby_stations(grid)
        if not nearby:
            print(f"station          : {pinned}  (could not verify -- "
                  "station list unavailable)")
        elif pinned in nearby:
            rank = nearby.index(pinned) + 1
            print(f"station          : {pinned}  (ok, #{rank} nearest)")
        else:
            print(f"station          : {pinned}  ** NOT in this grid's "
                  "station list **")
            print(f"  nearest are    : {', '.join(nearby[:5])}")
            print("  Fix location.station in the config, or blank it to use")
            print("  the nearest available.")
    else:
        print("station          : not pinned -- accuracy history may mix "
              "stations")
    if settings.location.approximate:
        print()
        print("The coordinate is an approximate centroid for the ZIP. If the")
        print("city above is not right, put exact values in")
        print(f"  {CONFIG_FILE}")
        print("under location.lat / location.lon and set approximate: false.")
    return 0


def cmd_preview(settings: Settings, args) -> int:
    try:
        _client, grid, hours = _fetch(settings)
    except WeatherError as exc:
        print(f"could not reach the forecast: {exc}", file=sys.stderr)
        return 2
    now = _now(settings, grid.time_zone)
    if args.at:
        now = datetime.fromisoformat(args.at)
        if now.tzinfo is None:
            now = now.replace(tzinfo=ZoneInfo(grid.time_zone or "America/Chicago"))
    d = evaluate(hours, now, settings.schedule, settings.thresholds)
    print(_describe(d))
    if args.hours:
        print()
        print("  hour    temp  rain%  dewpt")
        _e, _l, close = settings.schedule.night_bounds(now)
        for h in hours:
            if not (now <= h.start < close):
                continue
            t = "   -" if h.temp_f is None else f"{h.temp_f:4.0f}"
            p = "   -" if h.precip_pct is None else f"{h.precip_pct:4.0f}"
            dp = "    -" if h.dewpoint_f is None else f"{h.dewpoint_f:5.0f}"
            print(f"  {h.start:%a %H:%M} {t}F  {p}  {dp}")
    return 0


def cmd_check(settings: Settings, args) -> int:
    with History(settings.db_path) as history:
        try:
            client, grid, hours = _fetch(settings)
        except WeatherError as exc:
            log.error("forecast unavailable: %s", exc)
            # Recorded, not silently dropped: a run that could not decide is
            # itself a fact worth keeping in the record.
            now = _now(settings)
            history.record_decision(
                Decision(night=now.date().isoformat(), route="unknown",
                         reasons=[f"forecast unavailable: {exc}"]), alerted=False)
            return 2

        now = _now(settings, grid.time_zone)
        history.record_forecast(hours, fetched_at=now)
        obs = client.latest_observation(grid, station=settings.location.station)
        if obs:
            history.record_observation(obs)

        d = evaluate(hours, now, settings.schedule, settings.thresholds)
        print(_describe(d))

        previous = history.last_alerted_route(d.night)
        alerted = False

        # A retraction is worth more than the original alert. If we said OPEN
        # at 8pm and the 10pm forecast has rain at 3am, staying quiet because
        # "we already alerted tonight" is the one failure that actually costs
        # you a wet floor. So: send when nothing has gone out yet, OR when the
        # verdict has CHANGED since whatever we last delivered.
        revision = previous is not None and previous != d.route
        worth_sending = d.should_alert or revision

        if worth_sending and (previous is None or revision):
            if revision:
                d.reasons.insert(
                    0, f"revised since the earlier '{previous}' alert tonight")
            if settings.notifier.handles(d.route) or revision:
                alerted = settings.notifier.send(d, force=revision)
                if not alerted:
                    log.warning("alert for %s was NOT delivered", d.night)
        elif previous is not None:
            log.info("already alerted '%s' for %s; unchanged, staying quiet",
                     previous, d.night)

        # `alerted` must stay true for the night once anything was delivered,
        # or a later unchanged run would re-send the original.
        history.record_decision(d, alerted=alerted or previous is not None)
    return 0


def cmd_report(settings: Settings, args) -> int:
    with History(settings.db_path) as history:
        rows = history.recent_decisions(limit=args.limit)
        if not rows:
            print("no history yet -- run `check` at least once")
            return 0
        print(f"{'night':12} {'verdict':9} {'hours':>5}  window / reason")
        for r in rows:
            window = ""
            if r["open_at"] and r["close_at"]:
                o = datetime.fromisoformat(r["open_at"])
                c = datetime.fromisoformat(r["close_at"])
                window = f"{o:%H:%M}-{c:%H:%M}"
            note = window or (r["reasons"] or "")
            flag = "" if r["alerted"] else "  (no alert)"
            hours = f"{r['hours']:.1f}" if r["hours"] is not None else "   -"
            print(f"{r['night']:12} {r['route']:9} {hours:>5}  {note}{flag}")

        counts = history.route_counts()
        if counts:
            print()
            print("tally: " + ", ".join(f"{r['route']}={r['n']}" for r in counts))

        acc = history.forecast_accuracy(limit=args.limit * 12)
        if acc:
            errs = [abs(r["error_f"]) for r in acc if r["error_f"] is not None]
            if errs:
                print(f"forecast error: {sum(errs)/len(errs):.1f}F mean "
                      f"absolute over {len(errs)} matched hours "
                      f"(worst {max(errs):.1f}F)")
        else:
            print("forecast accuracy: no matched forecast/observation pairs yet")
    return 0


def cmd_doctor(settings: Settings, args) -> int:
    """Answer the only question that matters about an unattended program:
    is it actually set up to tell me anything?"""
    ok = True
    print(f"config file   : {CONFIG_FILE}"
          f"{'' if CONFIG_FILE.is_file() else '   (missing -- using defaults)'}")
    secrets = env_file()
    print(f"secrets file  : {secrets or 'NONE FOUND'}")
    print(f"history db    : {settings.db_path}")
    print(f"location      : ZIP {settings.location.zip_code} -> "
          f"{settings.location.lat:.4f},{settings.location.lon:.4f}"
          + ("  (approximate)" if settings.location.approximate else ""))
    print(f"station       : {settings.location.station or 'nearest available'}"
          + ("" if settings.location.station
             else "   (unpinned -- accuracy history may mix stations)"))
    t = settings.thresholds
    print(f"open below    : {t.max_temp_f:.0f}F"
          + (f", floor {t.min_temp_f:.0f}F" if t.min_temp_f is not None
             else ", no cold floor"))
    print(f"hours         : want {t.target_hours:.0f}h, "
          f"never below {t.min_hours:.0f}h")
    s = settings.schedule
    print(f"asleep        : {s.bedtime:%H:%M} -> {s.wake_weekday:%H:%M} "
          f"weekdays / {s.wake_weekend:%H:%M} weekends")

    n = settings.notifier
    print(f"email to      : {', '.join(n.email_to) or 'NOT SET'}")
    print(f"sms to        : {', '.join(n.sms_to) or 'not set'}")
    if not n.configured:
        ok = False
        print()
        print("NOT CONFIGURED TO ALERT. Set SMTP_HOST, SMTP_USER,")
        print("SMTP_PASSWORD and WEATHER_ALERT_EMAIL_TO in the secrets file.")
    for w in n.configured_warnings():
        ok = False
        print()
        print(f"WARNING: {w}")
    print()
    print("ok" if ok else "problems found (above)")
    return 0 if ok else 1


def main(argv=None) -> int:
    p = argparse.ArgumentParser(
        prog="weather_advice",
        description="Tell me when to open the windows for the night.")
    p.add_argument("--verbose", "-v", action="store_true")
    p.add_argument("--config", type=str, default=None)
    p.add_argument("--dry-run", action="store_true",
                   help="decide and record, but do not actually send")
    sub = p.add_subparsers(dest="cmd", required=True)

    pv = sub.add_parser("preview", help="decide and print; changes nothing")
    pv.add_argument("--hours", action="store_true",
                    help="also print the hour-by-hour forecast")
    pv.add_argument("--at", type=str, default=None,
                    help="pretend it is this local time, e.g. 2026-10-05T20:00")
    pv.set_defaults(func=cmd_preview)

    ck = sub.add_parser("check", help="decide, record to history, alert once")
    ck.set_defaults(func=cmd_check)

    rs = sub.add_parser("resolve", help="confirm the NWS grid for the location")
    rs.set_defaults(func=cmd_resolve)

    rp = sub.add_parser("report", help="show the history record")
    rp.add_argument("--limit", type=int, default=14)
    rp.set_defaults(func=cmd_report)

    dr = sub.add_parser("doctor", help="check the setup")
    dr.set_defaults(func=cmd_doctor)

    args = p.parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(message)s")

    from pathlib import Path
    settings = Settings.load(
        config_file=Path(args.config) if args.config else None,
        dry_run=args.dry_run)
    return args.func(settings, args)


if __name__ == "__main__":
    raise SystemExit(main())

"""Decide whether tonight is a windows-open night, and for how long.

The model, stated plainly because every rule below follows from it:

    The windows are opened once, in the evening, and closed on waking.

Two consequences do most of the work here.

**Rain is evaluated over the whole unattended period, not just the good part.**
This is the trap. Suppose it is 72F and clear from 11pm, then rain starts at
5am and the operator wakes at 8am. A naive "longest comfortable run" finds six
clean hours, says OPEN, and the operator wakes to rain blowing through the
window it never occurred to anyone to close. So once an open time is chosen,
`[open, wake]` must be rain-free end to end -- not merely the hours being
counted toward the total.

**Temperature is not symmetrical with rain.** If it hits 80F at 7am and the
alarm is at 8am, that is one warm hour at the tail: annoying, survivable, and
worth a sentence in the alert rather than cancelling the night. So temperature
bounds the hours we COUNT, while rain vetoes the night outright.

A null precipitation probability is treated as blocking, not as zero. NWS
returns null on some grids and periods, and "no data" is not "no rain" when
the cost of being wrong is sleeping through a storm.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List, Optional, Sequence

from .models import Decision, HourForecast
from .schedule import SleepSchedule


@dataclass(frozen=True)
class Thresholds:
    """What counts as comfortable.

    max_temp_f -- "below 78 or 77" (operator). 78 is the default; 77 is a
                  one-line config change, not a code change.
    min_temp_f -- a floor so a 34F January night does not read as a nine-hour
                  opportunity. Set to None to switch it off entirely; it is
                  the one threshold that can silently suppress an alert the
                  operator expected, so it is documented in config, not hidden.
    max_dewpoint_f -- OFF by default. Dallas is humid and 75F at a 72F dewpoint
                  is muggy, but the operator asked for a temperature rule, and
                  quietly adding a second one that blocks alerts would be
                  answering a question nobody asked. Available, not assumed.
    target_hours -- worth waking the phone for (operator: "at least 6 hours")
    min_hours    -- below this, opening is "a hassle" and we stay silent
    """

    max_temp_f: float = 78.0
    min_temp_f: Optional[float] = 50.0
    max_precip_pct: float = 20.0
    max_dewpoint_f: Optional[float] = None
    max_wind_mph: Optional[float] = None
    target_hours: float = 6.0
    min_hours: float = 3.0
    unknown_precip_blocks: bool = True

    def temp_ok(self, hour: HourForecast) -> bool:
        if hour.temp_f is None:
            return False
        if hour.temp_f >= self.max_temp_f:
            return False
        if self.min_temp_f is not None and hour.temp_f < self.min_temp_f:
            return False
        return True

    def rain_ok(self, hour: HourForecast) -> bool:
        if hour.precip_pct is None:
            return not self.unknown_precip_blocks
        return hour.precip_pct < self.max_precip_pct

    def air_ok(self, hour: HourForecast) -> bool:
        """The optional extras: humidity and wind."""
        if self.max_dewpoint_f is not None:
            if hour.dewpoint_f is None or hour.dewpoint_f > self.max_dewpoint_f:
                return False
        if self.max_wind_mph is not None:
            if hour.wind_mph is not None and hour.wind_mph > self.max_wind_mph:
                return False
        return True

    def comfortable(self, hour: HourForecast) -> bool:
        return self.temp_ok(hour) and self.rain_ok(hour) and self.air_ok(hour)


def _fmt(dt: datetime) -> str:
    """12-hour clock with no leading zero -- this text goes to a lock screen.

    Built by hand rather than with strftime("%-I"): the no-pad flag is glibc
    only. On Windows -- which is where this actually runs -- it is "%#I", and
    "%-I" raises ValueError. Doing the arithmetic works on both.
    """
    hour = dt.hour % 12 or 12
    ampm = "am" if dt.hour < 12 else "pm"
    return f"{hour}:{dt.minute:02d}{ampm}"


def evaluate(
    hours: Sequence[HourForecast],
    now: datetime,
    schedule: SleepSchedule,
    thresholds: Thresholds,
) -> Decision:
    """Pick tonight's open/close window, or explain why there isn't one."""
    earliest, latest_open, close_at = schedule.night_bounds(now)
    night = now.date().isoformat()
    decision = Decision(night=night, route="shut", wake_at=close_at)

    # Never suggest opening a window in the past.
    open_from = max(earliest, now.replace(minute=0, second=0, microsecond=0))

    span = [h for h in sorted(hours, key=lambda h: h.start)
            if open_from <= h.start < close_at]
    if not span:
        decision.route = "unknown"
        decision.reasons.append(
            "no forecast hours cover tonight "
            f"({_fmt(open_from)} to {_fmt(close_at)})")
        return decision

    # The forecast must actually reach the wake time. If it stops at 3am we
    # cannot promise the night is rain-free, and promising it anyway is the
    # failure this module exists to prevent.
    last = span[-1].start + timedelta(hours=1)
    if last < close_at:
        decision.route = "unknown"
        decision.reasons.append(
            f"forecast ends {_fmt(last)}, before the {_fmt(close_at)} wake time")
        return decision

    # -- choose the open time: the first comfortable hour we could act on ----
    openable = [h for h in span if h.start <= latest_open]
    first = next((h for h in openable if thresholds.comfortable(h)), None)
    if first is None:
        decision.reasons.append(_why_not(openable, thresholds))
        return decision

    open_at = first.start

    # -- rain vetoes the night over the WHOLE unattended period -------------
    exposed = [h for h in span if h.start >= open_at]
    wet = [h for h in exposed if not thresholds.rain_ok(h)]
    if wet:
        h = wet[0]
        pct = "unknown chance of" if h.precip_pct is None else f"{h.precip_pct:.0f}% chance of"
        decision.reasons.append(
            f"{pct} rain at {_fmt(h.start)}, while you would be asleep "
            "and unable to close them")
        return decision

    # -- count the comfortable run forward from the open time ---------------
    run: List[HourForecast] = []
    for h in exposed:
        if not thresholds.comfortable(h):
            break
        run.append(h)

    comfort_end = min(run[-1].start + timedelta(hours=1), close_at)
    span_hours = (comfort_end - open_at).total_seconds() / 3600.0

    temps = [h.temp_f for h in run if h.temp_f is not None]
    decision.open_at = open_at
    decision.close_at = comfort_end
    decision.hours = round(span_hours, 1)
    decision.low_f = min(temps) if temps else None
    decision.high_f = max(temps) if temps else None

    # A warm tail is a note, not a veto: the windows stay open until the alarm.
    if comfort_end < close_at:
        warm = next((h for h in exposed
                     if h.start >= comfort_end and not thresholds.temp_ok(h)), None)
        if warm is not None:
            decision.warm_after = warm.start

    if span_hours >= thresholds.target_hours:
        decision.route = "open"
    elif span_hours >= thresholds.min_hours:
        decision.route = "marginal"
        decision.reasons.append(
            f"only {span_hours:.1f}h under {thresholds.max_temp_f:.0f}F, "
            f"short of the {thresholds.target_hours:.0f}h you want")
    else:
        decision.route = "shut"
        decision.reasons.append(
            f"only {span_hours:.1f}h of good air -- under the "
            f"{thresholds.min_hours:.0f}h floor, not worth the hassle")
    return decision


def _why_not(openable: Sequence[HourForecast], t: Thresholds) -> str:
    """One honest sentence about what blocked the evening.

    The operator should never have to open a second tool to find out why the
    answer was no -- the same reason the deal tracker puts the spread on the
    card instead of making you go look it up.
    """
    if not openable:
        return "nothing in the evening window to evaluate"
    warm = [h for h in openable if h.temp_f is not None and h.temp_f >= t.max_temp_f]
    if len(warm) == len(openable):
        coolest = min(h.temp_f for h in warm)
        return (f"never drops below {t.max_temp_f:.0f}F before bed "
                f"(coolest {coolest:.0f}F)")
    rainy = [h for h in openable if not t.rain_ok(h)]
    if rainy:
        h = rainy[0]
        pct = "unknown" if h.precip_pct is None else f"{h.precip_pct:.0f}%"
        return f"rain risk {pct} at {_fmt(h.start)}"
    if t.min_temp_f is not None:
        cold = [h for h in openable if h.temp_f is not None and h.temp_f < t.min_temp_f]
        if cold:
            return (f"too cold -- {min(h.temp_f for h in cold):.0f}F, "
                    f"below the {t.min_temp_f:.0f}F floor")
    if t.max_dewpoint_f is not None:
        muggy = [h for h in openable if not t.air_ok(h)]
        if muggy:
            return f"too humid (dewpoint over {t.max_dewpoint_f:.0f}F)"
    return "no comfortable hour before bedtime"

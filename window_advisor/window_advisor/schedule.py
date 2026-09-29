"""When the operator is asleep, and therefore when the windows are unattended.

The whole program turns on one fact: **windows are opened once in the evening
and closed on waking.** Nobody gets up at 3am to shut a window. That makes the
sleep schedule a hard physical constraint, not a preference.

The subtle bit -- and the one an earlier sketch of this got wrong -- is that
the wake time belongs to the MORNING, not to the evening you open the windows.
Friday at 11pm is followed by a Saturday morning, so Friday night gets the
weekend's later wake time. Keying off the evening's weekday makes Friday night
end at 8am and Sunday night end at 9am: both exactly backwards.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta


@dataclass(frozen=True)
class SleepSchedule:
    """Times are local wall-clock, which is what the operator actually lives in.

    bedtime      -- windows must be open BY here; after this nobody is up to do it
    wake_weekday -- Mon-Fri mornings
    wake_weekend -- Sat/Sun mornings ("9 or 10am"; 9 is the safe default, since
                    assuming 10 would recommend a window that needs someone
                    awake at 10 to close it)
    open_earliest -- no point suggesting 2pm; the operator is not home/awake to
                    act on it, and evening air is what is being forecast
    """

    bedtime: time = time(23, 0)
    wake_weekday: time = time(8, 0)
    wake_weekend: time = time(9, 0)
    open_earliest: time = time(20, 0)

    def wake_time_for_morning(self, morning: date) -> time:
        """Saturday and Sunday mornings get the later wake time."""
        # Monday=0 ... Saturday=5, Sunday=6
        return self.wake_weekend if morning.weekday() >= 5 else self.wake_weekday

    def night_bounds(self, evening: datetime) -> tuple[datetime, datetime, datetime]:
        """(earliest open, latest open, close) for the night beginning `evening`.

        `close` is the wake moment on the FOLLOWING calendar day, because the
        window period always crosses midnight for an 11pm bedtime.
        """
        day = evening.date()
        earliest = datetime.combine(day, self.open_earliest, tzinfo=evening.tzinfo)
        latest = datetime.combine(day, self.bedtime, tzinfo=evening.tzinfo)

        morning = day + timedelta(days=1)
        close = datetime.combine(
            morning, self.wake_time_for_morning(morning), tzinfo=evening.tzinfo
        )
        return earliest, latest, close

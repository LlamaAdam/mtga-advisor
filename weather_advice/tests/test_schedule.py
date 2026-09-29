"""The sleep schedule, and the one bug worth a dedicated test."""

from datetime import datetime, time, timedelta

from weather_advice.schedule import SleepSchedule


def test_friday_night_gets_the_weekend_wake_time():
    """The wake time belongs to the MORNING, not the evening.

    Friday at 11pm is followed by a Saturday morning, so Friday night must end
    at the weekend time. Keying off the evening's weekday -- the obvious
    mistake -- makes Friday night end at 8am and Sunday night at 9am: both
    exactly backwards, and both wrong in the direction that either wastes an
    hour of good air or tells you to close a window while you are asleep.
    """
    s = SleepSchedule()
    _e, _l, close = s.night_bounds(datetime(2026, 10, 2, 20, 0))   # a Friday
    assert close == datetime(2026, 10, 3, 9, 0)                    # Saturday 9am


def test_sunday_night_gets_the_weekday_wake_time():
    s = SleepSchedule()
    _e, _l, close = s.night_bounds(datetime(2026, 10, 4, 20, 0))   # a Sunday
    assert close == datetime(2026, 10, 5, 8, 0)                    # Monday 8am


def test_the_close_time_is_always_the_next_calendar_day():
    """An 11pm bedtime means the window always crosses midnight."""
    s = SleepSchedule()
    for day in range(1, 32):
        evening = datetime(2026, 10, day, 20, 0)
        earliest, latest, close = s.night_bounds(evening)
        assert earliest < latest < close
        assert close.date() == evening.date() + timedelta(days=1)


def test_a_ten_am_weekend_lie_in_is_configurable():
    s = SleepSchedule(wake_weekend=time(10, 0))
    _e, _l, close = s.night_bounds(datetime(2026, 10, 2, 20, 0))
    assert close.hour == 10

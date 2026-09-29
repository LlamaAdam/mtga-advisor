"""Config loading. The YAML-boolean case is a regression test, not a nicety."""

import pytest

from window_advisor.config import _opt_float, _time, Settings
from datetime import time


def test_yaml_off_disables_a_threshold_rather_than_setting_it_to_zero():
    """THE BUG THIS GUARDS.

    YAML 1.1 parses the bare word `off` as the boolean False, and
    `float(False)` is 0.0. The shipped config ships `max_dewpoint_f: off`,
    which arrived as 0.0 -- and 0.0 does not mean "ignore humidity", it means
    "only open when the dewpoint is at or below zero Fahrenheit". Every night
    would have been vetoed and the program would have said KEEP SHUT forever,
    looking like bad weather rather than a bug.
    """
    assert _opt_float(False) is None
    assert _opt_float("off") is None
    assert _opt_float("no") is None
    assert _opt_float(None) is None
    assert _opt_float(0) == 0.0          # an explicit zero is still a zero
    assert _opt_float(68) == 68.0


def test_a_threshold_set_to_on_is_rejected_loudly():
    """`on` is not a temperature, and quietly turning it into 1.0F would veto
    every night the same way."""
    with pytest.raises(SystemExit):
        _opt_float(True)


def test_the_shipped_config_does_not_veto_every_night():
    """Loads config/window_advisor.yaml as committed and checks the optional
    thresholds really are off."""
    s = Settings.load()
    assert s.thresholds.max_dewpoint_f is None
    assert s.thresholds.max_wind_mph is None
    assert s.thresholds.max_temp_f == 78
    assert s.thresholds.target_hours == 6
    assert s.thresholds.min_hours == 3


def test_a_bad_time_falls_back_loudly_rather_than_becoming_midnight():
    """A schedule that quietly shifts to 00:00 is a wrong answer that looks
    right."""
    assert _time("23:00", time(1, 0)) == time(23, 0)
    assert _time("9:00", time(1, 0)) == time(9, 0)
    assert _time("nonsense", time(23, 0)) == time(23, 0)
    assert _time(None, time(8, 0)) == time(8, 0)

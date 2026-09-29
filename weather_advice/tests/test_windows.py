"""The decision engine. Most of these encode a way of being wrong."""

from datetime import datetime

import pytest

from conftest import COOL_NIGHT, MONDAY_EVENING, hours_from
from weather_advice.windows import Thresholds, evaluate


def test_a_clear_cool_night_opens(schedule, thresholds):
    d = evaluate(hours_from(COOL_NIGHT), MONDAY_EVENING, schedule, thresholds)
    assert d.route == "open"
    assert d.open_at.hour == 20
    assert d.close_at == datetime(2026, 10, 6, 8, 0)
    assert d.hours == 12.0
    assert (d.low_f, d.high_f) == (70, 76)


def test_rain_at_5am_cancels_the_night_even_though_six_clean_hours_exist(
        schedule, thresholds):
    """THE TRAP THIS MODULE EXISTS FOR.

    Clear and cool from 8pm, rain from 5am, alarm at 8am. A "longest
    comfortable run" reading finds nine clean hours and says OPEN -- and you
    wake at 8am to rain that blew through an open window for three hours,
    because nobody gets up at 5am to close it.

    Rain must therefore be judged over the whole unattended period, not just
    over the hours being counted.
    """
    precip = [0] * 9 + [80, 80, 80]        # index 9 == 5am
    d = evaluate(hours_from(COOL_NIGHT, precip), MONDAY_EVENING,
                 schedule, thresholds)
    assert d.route == "shut"
    assert "5:00am" in d.reasons[0]
    assert "asleep" in d.reasons[0]


def test_rain_before_bedtime_just_delays_the_open_time(schedule, thresholds):
    """Rain at 8-9pm is not the same problem: you are awake, and can simply
    open them later. The night should survive with a later start."""
    precip = [90, 90] + [0] * 10
    d = evaluate(hours_from(COOL_NIGHT, precip), MONDAY_EVENING,
                 schedule, thresholds)
    assert d.route == "open"
    assert d.open_at.hour == 22
    assert d.hours == 10.0


def test_a_warm_tail_is_a_note_not_a_veto(schedule, thresholds):
    """Temperature is not symmetrical with rain. If it hits 79F at 6am and the
    alarm is at 8am, that is a warm tail worth mentioning -- not a reason to
    spend the whole night with the windows shut."""
    temps = [76, 75, 74, 73, 72, 71, 70, 72, 75, 77, 79, 81]
    d = evaluate(hours_from(temps), MONDAY_EVENING, schedule, thresholds)
    assert d.route == "open"
    assert d.hours == 10.0
    assert d.warm_after == datetime(2026, 10, 6, 6, 0)


def test_four_hours_is_marginal(schedule, thresholds):
    temps = [76, 75, 74, 73, 79, 80, 81, 82, 83, 84, 85, 86]
    d = evaluate(hours_from(temps), MONDAY_EVENING, schedule, thresholds)
    assert d.route == "marginal"
    assert d.hours == 4.0


def test_two_hours_is_below_the_floor_and_stays_silent(schedule, thresholds):
    """The operator's words: under three hours "would be a hassle". Below the
    floor there is no alert at all, only a history row."""
    temps = [76, 75, 79, 80, 81, 82, 83, 84, 85, 86, 87, 88]
    d = evaluate(hours_from(temps), MONDAY_EVENING, schedule, thresholds)
    assert d.route == "shut"
    assert d.should_alert is False
    assert "not worth the hassle" in d.reasons[-1]


def test_a_hot_night_explains_itself(schedule, thresholds):
    temps = [88, 87, 86, 85, 84, 83, 82, 81, 80, 80, 81, 83]
    d = evaluate(hours_from(temps), MONDAY_EVENING, schedule, thresholds)
    assert d.route == "shut"
    assert "never drops below 78F" in d.reasons[0]
    assert "85F" in d.reasons[0]


def test_null_precipitation_is_treated_as_might_rain(schedule, thresholds):
    """NWS returns null for chance-of-rain on some grids and periods. Null is
    not zero, and the cost of guessing wrong is sleeping through a storm."""
    precip = [0] * 6 + [None] + [0] * 5
    d = evaluate(hours_from(COOL_NIGHT, precip), MONDAY_EVENING,
                 schedule, thresholds)
    assert d.route == "shut"
    assert "unknown chance of rain" in d.reasons[0]


def test_null_precipitation_can_be_opted_out_of(schedule):
    t = Thresholds(unknown_precip_blocks=False)
    precip = [0] * 6 + [None] + [0] * 5
    d = evaluate(hours_from(COOL_NIGHT, precip), MONDAY_EVENING, schedule, t)
    assert d.route == "open"


def test_a_truncated_forecast_is_unknown_not_a_recommendation(
        schedule, thresholds):
    """If the forecast stops at 3am we cannot promise the night is rain-free,
    and saying OPEN anyway would be a guess dressed as an answer."""
    d = evaluate(hours_from(COOL_NIGHT[:7]), MONDAY_EVENING,
                 schedule, thresholds)
    assert d.route == "unknown"
    assert "forecast ends" in d.reasons[0]


def test_no_forecast_at_all_is_unknown(schedule, thresholds):
    d = evaluate([], MONDAY_EVENING, schedule, thresholds)
    assert d.route == "unknown"


def test_the_cold_floor_blocks_a_january_night(schedule):
    t = Thresholds(min_temp_f=50.0)
    temps = [44, 42, 40, 38, 36, 35, 34, 34, 35, 36, 38, 41]
    d = evaluate(hours_from(temps), MONDAY_EVENING, schedule, t)
    assert d.route == "shut"
    assert "too cold" in d.reasons[0]


def test_the_cold_floor_can_be_switched_off(schedule):
    t = Thresholds(min_temp_f=None)
    temps = [44, 42, 40, 38, 36, 35, 34, 34, 35, 36, 38, 41]
    d = evaluate(hours_from(temps), MONDAY_EVENING, schedule, t)
    assert d.route == "open"


def test_seventy_seven_is_a_config_change_not_a_code_change(schedule):
    """The operator said "below 78 or 77"."""
    temps = [77.5] * 12
    assert evaluate(hours_from(temps), MONDAY_EVENING, schedule,
                    Thresholds(max_temp_f=78)).route == "open"
    assert evaluate(hours_from(temps), MONDAY_EVENING, schedule,
                    Thresholds(max_temp_f=77)).route == "shut"


def test_dewpoint_is_off_by_default_and_can_be_switched_on(schedule):
    """Humidity must not silently veto a night that passes the stated rule."""
    dew = [74] * 12
    assert evaluate(hours_from(COOL_NIGHT, dewpoints=dew), MONDAY_EVENING,
                    schedule, Thresholds()).route == "open"
    d = evaluate(hours_from(COOL_NIGHT, dewpoints=dew), MONDAY_EVENING,
                 schedule, Thresholds(max_dewpoint_f=68))
    assert d.route == "shut"
    assert "humid" in d.reasons[0]


def test_it_never_suggests_opening_a_window_in_the_past(schedule, thresholds):
    """Run at 2am and the advice must start now, not at 8pm yesterday."""
    late = datetime(2026, 10, 5, 23, 30)
    d = evaluate(hours_from(COOL_NIGHT), late, schedule, thresholds)
    assert d.open_at is None or d.open_at >= late.replace(minute=0)

"""Parsing api.weather.gov. Mostly about units, because that is where the
silent errors live."""

import json
from pathlib import Path

from window_advisor.weather import parse_observation, parse_period

FIXTURES = Path(__file__).parent / "fixtures"


def _periods():
    doc = json.loads((FIXTURES / "hourly.json").read_text())
    return [parse_period(p) for p in doc["properties"]["periods"]]


def test_temperature_is_fahrenheit_but_dewpoint_is_celsius():
    """The trap. NWS reports temperature in F and dewpoint in C IN THE SAME
    DOCUMENT. Assuming one unit for both is a silent ~30-degree error, and a
    dewpoint of 18 read as Fahrenheit would make every humid night look
    perfectly dry.
    """
    first = _periods()[0]
    assert first.temp_f == 76
    assert round(first.dewpoint_f, 1) == 65.0          # 18.33C -> 65F


def test_a_null_chance_of_rain_stays_none_and_is_not_coerced_to_zero():
    second = _periods()[1]
    assert second.precip_pct is None


def test_a_wind_range_takes_the_high_end():
    """"5 to 10 mph" -> 10. For rain blowing through an open window the gust
    is the number that matters, not the average."""
    assert _periods()[0].wind_mph == 10.0
    assert _periods()[1].wind_mph == 10.0


def test_the_start_time_keeps_its_offset():
    """A naive timestamp here would be compared against an aware 'now' and
    either raise or silently pick the wrong night."""
    assert _periods()[0].start.utcoffset() is not None


def test_observation_units_are_converted():
    doc = json.loads((FIXTURES / "observation.json").read_text())
    obs = parse_observation(doc, "KDAL")
    assert obs.station == "KDAL"
    assert obs.temp_f == 77.0                          # 25C
    assert round(obs.dewpoint_f, 1) == 64.4            # 18C
    assert round(obs.wind_mph, 0) == 10                # 16.09 km/h
    # precipitationLastHour is METRES: 0.000254 m == 0.01 inch
    assert round(obs.precip_last_hour_in, 3) == 0.01

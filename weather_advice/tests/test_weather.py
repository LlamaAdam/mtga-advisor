"""Parsing api.weather.gov. Mostly about units, because that is where the
silent errors live."""

import json
from pathlib import Path

from weather_advice.weather import (Grid, NWSClient, WeatherError,
                                    parse_observation, parse_period)

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


class _FakeClient(NWSClient):
    """An NWSClient whose HTTP layer is a scripted dict."""

    def __init__(self, responses):
        super().__init__()
        self.responses = responses
        self.asked = []

    def _get(self, url):
        self.asked.append(url)
        value = self.responses.get(url)
        if value is None:
            raise WeatherError(f"no stub for {url}")
        return value


GRID = Grid(lat=32.97, lon=-96.83, grid_id="FWD", grid_x=90, grid_y=110,
            time_zone="America/Chicago", forecast_hourly="https://x/hourly",
            observation_stations="https://x/stations")


def _obs_doc():
    return json.loads((FIXTURES / "observation.json").read_text())


def test_a_pinned_station_is_fetched_directly_without_listing_others():
    c = _FakeClient({
        "https://api.weather.gov/stations/KADS/observations/latest": _obs_doc()})
    obs = c.latest_observation(GRID, station="KADS")
    assert obs is not None and obs.station == "KADS"
    # The station list must not even be consulted -- pinning is the point.
    assert "https://x/stations" not in c.asked


def test_a_pinned_station_that_is_down_does_not_silently_substitute_another():
    """Losing a few rows while KADS is down is recoverable. A history table
    that quietly mixes in a different airport's readings is not -- the
    forecast-error number would start measuring the gap between two stations
    instead of the quality of the forecast."""
    c = _FakeClient({})          # every fetch fails
    assert c.latest_observation(GRID, station="KADS") is None
    assert "https://x/stations" not in c.asked


def test_without_a_pin_it_falls_back_to_the_nearest_stations():
    c = _FakeClient({
        "https://x/stations": {"features": [
            {"properties": {"stationIdentifier": "KDAL"}},
            {"properties": {"stationIdentifier": "KADS"}}]},
        "https://api.weather.gov/stations/KDAL/observations/latest": _obs_doc()})
    obs = c.latest_observation(GRID)
    assert obs is not None and obs.station == "KDAL"

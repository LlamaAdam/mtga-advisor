"""The history record."""

from datetime import datetime, timedelta

import pytest

from window_advisor.db import History
from window_advisor.models import Decision, HourForecast, Observation

BASE = datetime(2026, 10, 5, 20, 0)


@pytest.fixture
def history(tmp_path):
    with History(tmp_path / "h.db") as h:
        yield h


def test_the_same_night_is_only_alerted_once(history):
    """A poller that runs every 30 minutes must not text eight times about the
    same night."""
    d = Decision(night="2026-10-05", route="open", hours=9.0)
    assert history.already_alerted("2026-10-05") is False
    history.record_decision(d, alerted=True)
    assert history.already_alerted("2026-10-05") is True


def test_a_recorded_but_undelivered_alert_does_not_count_as_alerted(history):
    """Otherwise a failed send would suppress every retry for that night."""
    history.record_decision(Decision(night="2026-10-05", route="open"),
                            alerted=False)
    assert history.already_alerted("2026-10-05") is False


def test_successive_forecasts_for_one_hour_are_all_kept(history):
    """The interesting record is how a given hour's forecast MOVED as the
    night approached, so a later fetch must not overwrite an earlier one."""
    for offset, temp in ((3, 71.0), (2, 74.0), (1, 77.0)):
        history.record_forecast(
            [HourForecast(start=BASE, temp_f=temp, precip_pct=0)],
            fetched_at=BASE - timedelta(hours=offset))
    drift = history.forecast_drift(BASE.isoformat())
    assert [r["temp_f"] for r in drift] == [71.0, 74.0, 77.0]


def test_accuracy_grades_the_forecast_on_what_it_knew_at_the_time(history):
    """Scoring against the latest-ever forecast for an hour would grade it on
    information it did not have, which flatters it. Only forecasts issued
    BEFORE the hour count."""
    history.record_forecast([HourForecast(start=BASE, temp_f=75.0, precip_pct=0)],
                            fetched_at=BASE - timedelta(hours=2))
    # A "forecast" issued after the fact must be ignored by the join.
    history.record_forecast([HourForecast(start=BASE, temp_f=77.0, precip_pct=0)],
                            fetched_at=BASE + timedelta(hours=1))
    history.record_observation(
        Observation(observed_at=BASE, station="KDAL", temp_f=77.0))
    rows = history.forecast_accuracy()
    assert len(rows) == 1
    assert rows[0]["forecast_f"] == 75.0
    assert rows[0]["actual_f"] == 77.0
    assert rows[0]["error_f"] == 2.0


def test_an_observation_far_from_the_hour_is_not_matched(history):
    history.record_forecast([HourForecast(start=BASE, temp_f=75.0, precip_pct=0)],
                            fetched_at=BASE - timedelta(hours=1))
    history.record_observation(Observation(
        observed_at=BASE + timedelta(hours=5), station="KDAL", temp_f=90.0))
    assert history.forecast_accuracy() == []


def test_quiet_nights_are_recorded_too(history):
    """"The windows stayed shut for nine days" is only visible if the nights
    with no alert are written down."""
    for day, route in ((1, "shut"), (2, "shut"), (3, "open")):
        history.record_decision(
            Decision(night=f"2026-10-0{day}", route=route),
            alerted=(route == "open"))
    counts = {r["route"]: r["n"] for r in history.route_counts()}
    assert counts == {"shut": 2, "open": 1}
    assert len(history.recent_decisions()) == 3


def test_a_retraction_is_detectable(history):
    """Told "open them" at 8pm, then rain appears in the 10pm forecast. The
    night is already flagged as alerted, so de-duplicating on the night alone
    would swallow the retraction -- which is the message that actually matters.
    """
    history.record_decision(Decision(night="2026-10-05", route="open"),
                            alerted=True)
    assert history.last_alerted_route("2026-10-05") == "open"
    # An undelivered attempt must not be mistaken for a delivered verdict.
    history.record_decision(Decision(night="2026-10-06", route="open"),
                            alerted=False)
    assert history.last_alerted_route("2026-10-06") is None

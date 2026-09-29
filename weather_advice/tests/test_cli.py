"""End-to-end `check`, with the network stubbed out.

Both of the operator's other repos keep their tests deliberately offline, so
nothing here touches api.weather.gov.
"""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from conftest import COOL_NIGHT, hours_from
from weather_advice import __main__ as cli
from weather_advice.config import Location, Settings
from weather_advice.db import History
from weather_advice.notify import Notifier
from weather_advice.schedule import SleepSchedule
from weather_advice.weather import Grid
from weather_advice.windows import Thresholds

CHICAGO = ZoneInfo("America/Chicago")
EVENING = datetime(2026, 10, 5, 20, 30, tzinfo=CHICAGO)
EIGHT_PM = datetime(2026, 10, 5, 20, 0, tzinfo=CHICAGO)

GRID = Grid(lat=32.9968, lon=-96.84, grid_id="FWD", grid_x=90, grid_y=110,
            time_zone="America/Chicago", forecast_hourly="https://x/hourly",
            observation_stations="https://x/stations", city="Dallas", state="TX")


class Recorder(Notifier):
    """A notifier that records instead of sending."""

    def __init__(self, **kw):
        super().__init__(smtp_host="h", smtp_user="u", smtp_password="p",
                         email_to=["me@example.com"],
                         sms_to=["5551234567@vtext.com"], **kw)
        self.sent = []

    def send(self, d, force=False):
        if not force and not self.handles(d.route):
            return False
        self.sent.append((d.route, force, list(d.reasons)))
        return True


@pytest.fixture
def settings(tmp_path):
    return Settings(
        location=Location(), schedule=SleepSchedule(),
        thresholds=Thresholds(), db_path=tmp_path / "h.db",
        grid_cache=tmp_path / "grid.json", notifier=Recorder())


def _stub(monkeypatch, hours, now=EVENING):
    class FakeClient:
        def latest_observation(self, grid, station=None):
            FakeClient.asked_for = station
            return None
    monkeypatch.setattr(cli, "_fetch", lambda s, use_cache=True:
                        (FakeClient(), GRID, hours))
    monkeypatch.setattr(cli, "_now", lambda s, tz="": now)


class Args:
    pass


def test_a_good_night_alerts_once_and_is_recorded(settings, monkeypatch, capsys):
    _stub(monkeypatch, hours_from(COOL_NIGHT, start=EIGHT_PM))
    assert cli.cmd_check(settings, Args()) == 0
    assert [s[0] for s in settings.notifier.sent] == ["open"]
    assert "OPEN THEM" in capsys.readouterr().out

    with History(settings.db_path) as h:
        rows = h.recent_decisions()
        assert len(rows) == 1
        assert rows[0]["route"] == "open" and rows[0]["alerted"] == 1
        # The forecast itself was kept, which is the tracking record.
        assert h.forecast_drift(EIGHT_PM.isoformat())


def test_an_unchanged_second_run_stays_quiet(settings, monkeypatch):
    """The 9pm and 10pm runs must not re-text the same verdict."""
    _stub(monkeypatch, hours_from(COOL_NIGHT, start=EIGHT_PM))
    cli.cmd_check(settings, Args())
    cli.cmd_check(settings, Args())
    cli.cmd_check(settings, Args())
    assert len(settings.notifier.sent) == 1


def test_rain_appearing_later_in_the_evening_sends_a_retraction(
        settings, monkeypatch):
    """Told "open them" at 8pm; by 10pm the forecast has rain at 3am. The
    retraction is the message that actually matters, and de-duplicating on the
    night alone would have swallowed it."""
    _stub(monkeypatch, hours_from(COOL_NIGHT, start=EIGHT_PM))
    cli.cmd_check(settings, Args())
    assert settings.notifier.sent[0][0] == "open"

    # Same night, revised forecast: rain from 3am (index 7).
    precip = [0] * 7 + [90] * 5
    _stub(monkeypatch, hours_from(COOL_NIGHT, precip, start=EIGHT_PM),
          now=datetime(2026, 10, 5, 22, 0, tzinfo=CHICAGO))
    cli.cmd_check(settings, Args())

    assert len(settings.notifier.sent) == 2
    route, forced, reasons = settings.notifier.sent[1]
    assert route == "shut"
    assert forced is True          # forced through, though "shut" is silent
    assert "revised since the earlier 'open' alert" in reasons[0]
    assert any("asleep" in r for r in reasons)


def test_a_bad_night_never_alerts_but_is_still_recorded(settings, monkeypatch):
    """The quiet nights have to be written down, or "shut for nine days" is
    invisible in the record."""
    hot = [88, 87, 86, 85, 84, 83, 82, 81, 80, 80, 81, 83]
    _stub(monkeypatch, hours_from(hot, start=EIGHT_PM))
    cli.cmd_check(settings, Args())
    assert settings.notifier.sent == []
    with History(settings.db_path) as h:
        rows = h.recent_decisions()
        assert rows[0]["route"] == "shut" and rows[0]["alerted"] == 0


def test_an_unreachable_forecast_is_recorded_as_unknown(settings, monkeypatch):
    """A run that could not decide is itself a fact worth keeping -- and it
    must not be silently indistinguishable from "no good window"."""
    from weather_advice.weather import WeatherError

    def boom(s, use_cache=True):
        raise WeatherError("connection reset")
    monkeypatch.setattr(cli, "_fetch", boom)
    monkeypatch.setattr(cli, "_now", lambda s, tz="": EVENING)

    assert cli.cmd_check(settings, Args()) == 2
    with History(settings.db_path) as h:
        rows = h.recent_decisions()
        assert rows[0]["route"] == "unknown"
        assert "connection reset" in rows[0]["reasons"]


def test_the_pinned_station_is_the_one_actually_asked_for(settings, monkeypatch):
    """The config pins KADS; the run must request KADS by name rather than
    falling through to whichever station happens to answer first."""
    settings.location.station = "KADS"
    captured = {}

    class FakeClient:
        def latest_observation(self, grid, station=None):
            captured["station"] = station
            return None

    monkeypatch.setattr(cli, "_fetch", lambda s, use_cache=True:
                        (FakeClient(), GRID, hours_from(COOL_NIGHT, start=EIGHT_PM)))
    monkeypatch.setattr(cli, "_now", lambda s, tz="": EVENING)
    cli.cmd_check(settings, Args())
    assert captured["station"] == "KADS"

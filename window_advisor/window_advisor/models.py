"""Data shapes shared across the advisor.

Deliberately plain dataclasses: every one of these gets written to SQLite and
read back for the history record, so nothing here may depend on a live network
handle or a config object.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional


@dataclass(frozen=True)
class HourForecast:
    """One hour of the NWS hourly forecast, normalised to imperial units.

    `precip_pct` is a probability, not an amount. NWS returns null for it on
    some grids and periods; a null is NOT zero, and treating it as zero is how
    you end up asleep with the windows open in a thunderstorm. Callers must
    decide explicitly -- see `Comfort.unknown_precip`.
    """

    start: datetime
    temp_f: Optional[float]
    precip_pct: Optional[float]
    dewpoint_f: Optional[float] = None
    wind_mph: Optional[float] = None
    short_forecast: str = ""


@dataclass(frozen=True)
class Observation:
    """What actually happened, from an NWS station. Used to score the forecast
    after the fact -- the 'overall record' the operator asked for."""

    observed_at: datetime
    station: str
    temp_f: Optional[float]
    dewpoint_f: Optional[float] = None
    wind_mph: Optional[float] = None
    precip_last_hour_in: Optional[float] = None
    text: str = ""


@dataclass
class Decision:
    """The verdict for one night.

    `route` mirrors the deal tracker's routing vocabulary on purpose, because
    the alert-fatigue lesson is the same one:

      open     -- >= target_hours of good air. Worth waking your phone.
      marginal -- >= min_hours but short of target. Real, but a hassle.
      shut     -- not worth opening. Recorded, never alerted.
      unknown  -- the forecast could not be evaluated (fetch failed, nulls).
    """

    night: str                      # the date of the EVENING, YYYY-MM-DD
    route: str
    open_at: Optional[datetime] = None
    close_at: Optional[datetime] = None
    hours: float = 0.0
    low_f: Optional[float] = None
    high_f: Optional[float] = None
    warm_after: Optional[datetime] = None
    reasons: List[str] = field(default_factory=list)
    wake_at: Optional[datetime] = None

    @property
    def should_alert(self) -> bool:
        return self.route in ("open", "marginal")

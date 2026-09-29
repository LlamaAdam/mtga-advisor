"""National Weather Service client (api.weather.gov).

Why NWS and not a commercial API: it is free, it needs no API key, no account
and no affiliate agreement, and it is the authoritative US source rather than a
reseller of it. The one real constraint is that it is US-only, which is fine
for a house in Texas. Compare the data-sourcing problem in the deal tracker's
SEALED_PRICE_ALERTS note -- there the numbers were behind ToS-hostile scraping
and approval-gated APIs, and that is what made the idea hard. Here the good
source is simply open, so this is the easy case and worth taking.

NWS requires a User-Agent that identifies the application; a request without
one is rejected. There is no key to leak, so nothing here is a secret.

Two calls make a forecast:
  1. /points/{lat},{lon}  -> which grid cell you are in, and its station list.
     The answer is stable for a fixed location, so it is cached on disk.
  2. .../forecast/hourly  -> the hourly periods themselves.

Unit handling is explicit throughout. The hourly forecast reports temperature
in Fahrenheit but dewpoint in Celsius, in the same JSON document; assuming one
unit for both is a silent 30-degree error.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

from .models import HourForecast, Observation

log = logging.getLogger(__name__)

API = "https://api.weather.gov"
USER_AGENT = "window-advisor (github.com/LlamaAdam/window-advisor)"

# NWS asks for GeoJSON explicitly; the default content type has changed before.
HEADERS = {"User-Agent": USER_AGENT, "Accept": "application/geo+json"}


class WeatherError(RuntimeError):
    """A fetch failed in a way the caller must not paper over.

    Distinct from "no window tonight": if the forecast never arrived we do not
    know whether the windows should be open, and saying "stay shut" would be a
    guess dressed as an answer.
    """


def _c_to_f(c: Optional[float]) -> Optional[float]:
    return None if c is None else (c * 9.0 / 5.0) + 32.0


def _kmh_to_mph(kmh: Optional[float]) -> Optional[float]:
    return None if kmh is None else kmh * 0.621371


def _quantity_f(node: Any) -> Optional[float]:
    """Read an NWS quantity object, converting to Fahrenheit by its unitCode.

    Shape: {"unitCode": "wmoUnit:degC", "value": 21.1}. The value is routinely
    null, which means "not forecast", not zero.
    """
    if not isinstance(node, dict):
        return None
    value = node.get("value")
    if value is None:
        return None
    unit = (node.get("unitCode") or "").lower()
    if "degf" in unit:
        return float(value)
    return _c_to_f(float(value))


def _wind_mph(node: Any) -> Optional[float]:
    """Wind arrives either as "10 mph" / "5 to 10 mph" (forecast) or as a
    quantity in km/h or m/s (observations). Take the HIGH end of a range --
    for rain blowing through an open window the gust is the number that
    matters, not the average.
    """
    if isinstance(node, str):
        nums = [float(t) for t in node.replace("to", " ").split() if _isnum(t)]
        return max(nums) if nums else None
    if isinstance(node, dict):
        value = node.get("value")
        if value is None:
            return None
        unit = (node.get("unitCode") or "").lower()
        if "km_h" in unit or "km/h" in unit:
            return _kmh_to_mph(float(value))
        if "m_s" in unit:
            return float(value) * 2.23694
        return float(value)
    return None


def _isnum(tok: str) -> bool:
    try:
        float(tok)
        return True
    except ValueError:
        return False


@dataclass
class Grid:
    """A resolved location: which NWS grid cell, and where to read actuals."""

    lat: float
    lon: float
    grid_id: str
    grid_x: int
    grid_y: int
    time_zone: str
    forecast_hourly: str
    observation_stations: str
    city: str = ""
    state: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return dict(lat=self.lat, lon=self.lon, grid_id=self.grid_id,
                    grid_x=self.grid_x, grid_y=self.grid_y,
                    time_zone=self.time_zone,
                    forecast_hourly=self.forecast_hourly,
                    observation_stations=self.observation_stations,
                    city=self.city, state=self.state)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Grid":
        return cls(**d)


class NWSClient:
    def __init__(self, timeout: int = 20, retries: int = 4,
                 cache_path: Optional[Path] = None):
        self.timeout = timeout
        self.retries = retries
        self.cache_path = cache_path
        self.session = requests.Session()
        self.session.headers.update(HEADERS)

    # -- transport ----------------------------------------------------------

    def _get(self, url: str) -> Dict[str, Any]:
        """GET with backoff. NWS rate-limits and returns 503 under load; a
        single attempt would turn a routine blip into a missed night."""
        last: Optional[Exception] = None
        for attempt in range(self.retries):
            try:
                r = self.session.get(url, timeout=self.timeout)
                # 404 on a points lookup means the coordinate is outside NWS
                # coverage. Retrying cannot fix that, so fail loudly now.
                if r.status_code == 404:
                    raise WeatherError(
                        f"{url} returned 404 -- outside NWS coverage "
                        "(this API is US-only)")
                r.raise_for_status()
                return r.json()
            except WeatherError:
                raise
            except Exception as exc:       # noqa: BLE001 - retried below
                last = exc
                if attempt < self.retries - 1:
                    delay = 2 ** attempt
                    log.warning("weather fetch failed (%s), retry in %ds",
                                exc, delay)
                    time.sleep(delay)
        raise WeatherError(f"could not fetch {url}: {last}")

    # -- location -----------------------------------------------------------

    def resolve(self, lat: float, lon: float, use_cache: bool = True) -> Grid:
        """Find the grid cell for a coordinate.

        Cached on disk: the answer never changes for a fixed house, and this
        halves the request count on every run.
        """
        if use_cache and self.cache_path and self.cache_path.exists():
            try:
                cached = json.loads(self.cache_path.read_text())
                if (round(cached.get("lat", 0), 4) == round(lat, 4)
                        and round(cached.get("lon", 0), 4) == round(lon, 4)):
                    return Grid.from_dict(cached)
            except (OSError, ValueError, TypeError) as exc:
                log.warning("ignoring unreadable grid cache: %s", exc)

        # NWS rejects more than 4 decimal places on this endpoint.
        data = self._get(f"{API}/points/{lat:.4f},{lon:.4f}")
        p = data.get("properties") or {}
        rel = ((p.get("relativeLocation") or {}).get("properties") or {})
        grid = Grid(
            lat=lat, lon=lon,
            grid_id=p.get("gridId", ""),
            grid_x=int(p.get("gridX") or 0),
            grid_y=int(p.get("gridY") or 0),
            time_zone=p.get("timeZone", ""),
            forecast_hourly=p.get("forecastHourly", ""),
            observation_stations=p.get("observationStations", ""),
            city=rel.get("city", ""),
            state=rel.get("state", ""),
        )
        if not grid.forecast_hourly:
            raise WeatherError(f"points lookup for {lat},{lon} returned no "
                               "hourly forecast URL")
        if self.cache_path:
            try:
                self.cache_path.parent.mkdir(parents=True, exist_ok=True)
                self.cache_path.write_text(json.dumps(grid.to_dict(), indent=2))
            except OSError as exc:
                log.warning("could not write grid cache: %s", exc)
        return grid

    # -- forecast -----------------------------------------------------------

    def hourly(self, grid: Grid) -> List[HourForecast]:
        data = self._get(grid.forecast_hourly)
        periods = (data.get("properties") or {}).get("periods") or []
        if not periods:
            raise WeatherError("hourly forecast contained no periods")
        return [parse_period(p) for p in periods]

    def latest_observation(self, grid: Grid) -> Optional[Observation]:
        """Actual conditions from the nearest reporting station.

        Best-effort on purpose: this feeds the accuracy record, not tonight's
        decision, so a station that is down must not fail the run.
        """
        try:
            stations = self._get(grid.observation_stations)
            ids = [f.get("properties", {}).get("stationIdentifier")
                   for f in stations.get("features", [])]
            ids = [i for i in ids if i]
            for station in ids[:3]:
                try:
                    obs = self._get(f"{API}/stations/{station}/observations/latest")
                    return parse_observation(obs, station)
                except WeatherError as exc:
                    log.info("station %s had no usable observation: %s",
                             station, exc)
        except WeatherError as exc:
            log.warning("could not read observations: %s", exc)
        return None


def parse_period(p: Dict[str, Any]) -> HourForecast:
    """One hourly period -> HourForecast.

    Temperature is already Fahrenheit here (temperatureUnit "F") but is read
    through the unit-aware helper anyway, so a future change of default units
    shows up as correct numbers rather than as a silent 30-degree shift.
    """
    temp = p.get("temperature")
    unit = (p.get("temperatureUnit") or "F").upper()
    temp_f = None if temp is None else (
        float(temp) if unit == "F" else _c_to_f(float(temp)))

    precip = (p.get("probabilityOfPrecipitation") or {}).get("value")
    return HourForecast(
        start=datetime.fromisoformat(p["startTime"]),
        temp_f=temp_f,
        precip_pct=None if precip is None else float(precip),
        dewpoint_f=_quantity_f(p.get("dewpoint")),
        wind_mph=_wind_mph(p.get("windSpeed")),
        short_forecast=p.get("shortForecast", "") or "",
    )


def parse_observation(doc: Dict[str, Any], station: str) -> Observation:
    p = doc.get("properties") or {}
    ts = p.get("timestamp")
    precip = (p.get("precipitationLastHour") or {}).get("value")
    # precipitationLastHour is metres. 0.001 m is a millimetre of rain.
    precip_in = None if precip is None else float(precip) * 39.3701
    return Observation(
        observed_at=datetime.fromisoformat(ts) if ts else datetime.now(),
        station=station,
        temp_f=_quantity_f(p.get("temperature")),
        dewpoint_f=_quantity_f(p.get("dewpoint")),
        wind_mph=_wind_mph(p.get("windSpeed")),
        precip_last_hour_in=precip_in,
        text=p.get("textDescription", "") or "",
    )

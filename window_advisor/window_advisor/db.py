"""SQLite history: what was forecast, what actually happened, what we decided.

Three tables because they answer three different questions, and merging any two
of them loses the ability to answer one:

  forecast_hour -- what the forecast SAID, stamped with when it said it. Keyed
                   (fetched_at, start) rather than (start), so successive runs
                   do not overwrite each other. That is the whole point: the
                   interesting record is how a given hour's forecast MOVED as
                   the night approached.
  observation   -- what actually happened, from a station. The truth column.
  decision      -- what was recommended, and whether an alert went out.

Keeping forecast history rather than only the latest reading is the same
principle the deal tracker settled on for prices: "record price history, so
'near MSRP' is measured rather than eyeballed". Here it lets "the forecast
said 74F and it was 81F" become a number instead of a memory.

WAL mode: a long-running poller and an interactive `report` must not lock each
other out.
"""

from __future__ import annotations

import logging
import sqlite3
from contextlib import closing
from datetime import datetime
from pathlib import Path
from typing import Iterable, List, Optional, Sequence

from .models import Decision, HourForecast, Observation

log = logging.getLogger(__name__)

SCHEMA = """
CREATE TABLE IF NOT EXISTS forecast_hour (
    fetched_at   TEXT NOT NULL,
    start        TEXT NOT NULL,
    temp_f       REAL,
    precip_pct   REAL,
    dewpoint_f   REAL,
    wind_mph     REAL,
    short        TEXT,
    PRIMARY KEY (fetched_at, start)
);
CREATE INDEX IF NOT EXISTS forecast_hour_start ON forecast_hour (start);

CREATE TABLE IF NOT EXISTS observation (
    observed_at  TEXT NOT NULL,
    station      TEXT NOT NULL,
    temp_f       REAL,
    dewpoint_f   REAL,
    wind_mph     REAL,
    precip_in    REAL,
    text         TEXT,
    PRIMARY KEY (observed_at, station)
);

CREATE TABLE IF NOT EXISTS decision (
    night        TEXT PRIMARY KEY,
    decided_at   TEXT NOT NULL,
    route        TEXT NOT NULL,
    open_at      TEXT,
    close_at     TEXT,
    hours        REAL,
    low_f        REAL,
    high_f       REAL,
    warm_after   TEXT,
    reasons      TEXT,
    alerted      INTEGER NOT NULL DEFAULT 0
);
"""


def _iso(dt: Optional[datetime]) -> Optional[str]:
    return None if dt is None else dt.isoformat()


class History:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.path), timeout=30)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()

    def __enter__(self) -> "History":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    # -- writes -------------------------------------------------------------

    def record_forecast(self, hours: Sequence[HourForecast],
                        fetched_at: Optional[datetime] = None) -> int:
        stamp = _iso(fetched_at or datetime.now())
        rows = [(stamp, _iso(h.start), h.temp_f, h.precip_pct,
                 h.dewpoint_f, h.wind_mph, h.short_forecast) for h in hours]
        with self.conn:
            self.conn.executemany(
                "INSERT OR REPLACE INTO forecast_hour "
                "(fetched_at, start, temp_f, precip_pct, dewpoint_f, wind_mph, short) "
                "VALUES (?,?,?,?,?,?,?)", rows)
        return len(rows)

    def record_observation(self, obs: Observation) -> None:
        with self.conn:
            self.conn.execute(
                "INSERT OR REPLACE INTO observation "
                "(observed_at, station, temp_f, dewpoint_f, wind_mph, precip_in, text) "
                "VALUES (?,?,?,?,?,?,?)",
                (_iso(obs.observed_at), obs.station, obs.temp_f, obs.dewpoint_f,
                 obs.wind_mph, obs.precip_last_hour_in, obs.text))

    def record_decision(self, d: Decision, alerted: bool) -> None:
        with self.conn:
            self.conn.execute(
                "INSERT OR REPLACE INTO decision "
                "(night, decided_at, route, open_at, close_at, hours, low_f, "
                " high_f, warm_after, reasons, alerted) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (d.night, _iso(datetime.now()), d.route, _iso(d.open_at),
                 _iso(d.close_at), d.hours, d.low_f, d.high_f,
                 _iso(d.warm_after), " | ".join(d.reasons), int(alerted)))

    # -- reads --------------------------------------------------------------

    def already_alerted(self, night: str) -> bool:
        """Has an alert already gone out for this night?

        The de-duplication guard. Without it a poller that runs every 30
        minutes texts you eight times about the same night -- exactly the
        alert fatigue the deal tracker spent two weeks undoing.
        """
        row = self.conn.execute(
            "SELECT alerted FROM decision WHERE night = ?", (night,)).fetchone()
        return bool(row and row["alerted"])

    def last_alerted_route(self, night: str) -> Optional[str]:
        """Which verdict was last actually DELIVERED for this night.

        Drives revision alerts. The forecast moves during the evening, and
        having been told "open them" at 8pm, the one message you must not miss
        is the 10pm "actually, rain at 3am". De-duplicating on the night alone
        would swallow exactly that retraction.
        """
        row = self.conn.execute(
            "SELECT route FROM decision WHERE night = ? AND alerted = 1",
            (night,)).fetchone()
        return row["route"] if row else None

    def recent_decisions(self, limit: int = 14) -> List[sqlite3.Row]:
        return list(self.conn.execute(
            "SELECT * FROM decision ORDER BY night DESC LIMIT ?", (limit,)))

    def route_counts(self, since: Optional[str] = None) -> List[sqlite3.Row]:
        if since:
            return list(self.conn.execute(
                "SELECT route, COUNT(*) n FROM decision WHERE night >= ? "
                "GROUP BY route ORDER BY n DESC", (since,)))
        return list(self.conn.execute(
            "SELECT route, COUNT(*) n FROM decision GROUP BY route "
            "ORDER BY n DESC"))

    def forecast_accuracy(self, limit: int = 200) -> List[sqlite3.Row]:
        """Forecast vs actual, hour by hour.

        Joins the LAST forecast issued before each hour against the
        observation nearest that hour (within 30 minutes). Comparing against
        the latest-ever forecast instead would grade the forecast on
        information it did not have, which flatters it.
        """
        return list(self.conn.execute(
            """
            WITH latest AS (
                SELECT start, temp_f, precip_pct, MAX(fetched_at) AS fetched_at
                FROM forecast_hour
                WHERE fetched_at <= start
                GROUP BY start
            )
            SELECT l.start,
                   l.temp_f      AS forecast_f,
                   o.temp_f      AS actual_f,
                   l.precip_pct  AS forecast_precip,
                   o.precip_in   AS actual_precip_in,
                   ROUND(o.temp_f - l.temp_f, 1) AS error_f
            FROM latest l
            JOIN observation o
              ON ABS(julianday(o.observed_at) - julianday(l.start)) * 1440 <= 30
            WHERE l.temp_f IS NOT NULL AND o.temp_f IS NOT NULL
            ORDER BY l.start DESC
            LIMIT ?
            """, (limit,)))

    def forecast_drift(self, start_iso: str) -> List[sqlite3.Row]:
        """Every forecast ever issued for one hour, oldest first -- how the
        prediction for a given hour moved as it approached."""
        return list(self.conn.execute(
            "SELECT fetched_at, temp_f, precip_pct FROM forecast_hour "
            "WHERE start = ? ORDER BY fetched_at", (start_iso,)))

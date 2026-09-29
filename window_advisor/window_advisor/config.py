"""Settings: a YAML file for preferences, the environment for secrets.

The split follows the deal tracker. Thresholds and the sleep schedule are
preferences worth committing and diffing, so they live in
`config/window_advisor.yaml`. The SMTP password is not, so it comes from the
environment, loaded from a `.env` that sits OUTSIDE the project directory.

That last point is load-bearing, and the reasoning is lifted verbatim from
`mtgdeals/config.py`: `.gitignore` stops the honest mistake but does nothing
against `git add -f`, a zipped folder, a copied directory, or a tool that
ignores gitignore. Keeping the file where the repo cannot reach it makes the
accident unavailable.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from datetime import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from .notify import Notifier
from .schedule import SleepSchedule
from .windows import Thresholds

log = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = Path(os.environ.get("WINDOW_CONFIG_DIR") or (ROOT / "config"))
DATA_DIR = Path(os.environ.get("WINDOW_DATA_DIR") or (ROOT / "data"))
CONFIG_FILE = CONFIG_DIR / "window_advisor.yaml"


def env_candidates() -> List[Path]:
    """Where the secrets file may live, best first."""
    explicit = os.getenv("WINDOW_ENV")
    out: List[Path] = []
    if explicit:
        out.append(Path(explicit))
    # A `.secrets` directory ALONGSIDE the project: portable, obviously
    # outside the repo, and no absolute path baked into the code.
    out.append(ROOT.parent / ".secrets" / "window-advisor" / ".env")
    appdata = os.getenv("APPDATA")
    if appdata:
        out.append(Path(appdata) / "window-advisor" / ".env")
    home = Path.home()
    out.append(home / ".config" / "window-advisor" / ".env")
    # Honoured LAST so an existing install keeps working, but never preferred.
    out.append(ROOT / ".env")
    return out


def env_file() -> Optional[Path]:
    for p in env_candidates():
        if p.is_file():
            return p
    return None


def load_env(path: Optional[Path] = None) -> Dict[str, str]:
    """Minimal KEY=VALUE reader.

    Hand-rolled rather than adding python-dotenv: this is a dozen lines and
    the alternative is a dependency on the one code path that must work on a
    machine nobody is watching.
    """
    target = path or env_file()
    found: Dict[str, str] = {}
    if not target or not target.is_file():
        return found
    try:
        for raw in target.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            value = value.strip().strip('"').strip("'")
            found[key.strip()] = value
            os.environ.setdefault(key.strip(), value)
    except OSError as exc:
        log.warning("could not read %s: %s", target, exc)
    return found


def _time(text: Any, fallback: time) -> time:
    """Parse "23:00" / "9:00". A bad value must not silently become midnight:
    a schedule that quietly shifts is a wrong answer that looks right."""
    if isinstance(text, time):
        return text
    if not text:
        return fallback
    try:
        parts = str(text).strip().split(":")
        return time(int(parts[0]), int(parts[1]) if len(parts) > 1 else 0)
    except (ValueError, IndexError):
        log.warning("could not parse time %r; using %s", text, fallback)
        return fallback


def _opt_float(value: Any) -> Optional[float]:
    """Read an optional threshold, where absent means "disabled".

    The bool branch is not defensive padding -- it is the fix for a live bug.
    YAML 1.1 parses the bare words `off`, `no` and `false` as the BOOLEAN
    False, and `float(False)` is `0.0`. So the shipped config's

        max_dewpoint_f: off

    arrived here as 0.0, which does not mean "ignore humidity" -- it means
    "only open the windows when the dewpoint is at or below zero Fahrenheit".
    Every night in Texas would have been vetoed, the program would have said
    KEEP SHUT forever, and it would have looked like a run of bad weather
    rather than a bug. Exactly the silent wrongness this project is built to
    avoid, so it is caught here and regression-tested.
    """
    if value is None or value is False:
        return None
    if value is True:
        raise SystemExit(
            "a threshold was set to `on`/`true`, which is not a temperature. "
            "Use a number, or `off` to disable it.")
    if isinstance(value, str) and value.strip().lower() in {
            "", "off", "no", "none", "null", "false", "disabled"}:
        return None
    return float(value)


@dataclass
class Location:
    zip_code: str = "75287"
    # Approximate centroid for 75287 (far north Dallas). `window-advisor
    # resolve` replaces these with the values NWS confirms and prints the city
    # it matched, so a wrong coordinate is visible rather than assumed.
    lat: float = 32.9968
    lon: float = -96.8400
    approximate: bool = True


@dataclass
class Settings:
    location: Location = field(default_factory=Location)
    schedule: SleepSchedule = field(default_factory=SleepSchedule)
    thresholds: Thresholds = field(default_factory=Thresholds)
    db_path: Path = field(default_factory=lambda: DATA_DIR / "history.db")
    grid_cache: Path = field(default_factory=lambda: DATA_DIR / "grid.json")
    notifier: Notifier = field(default_factory=Notifier)

    @classmethod
    def load(cls, config_file: Optional[Path] = None,
             dry_run: bool = False) -> "Settings":
        load_env()
        raw = _read_yaml(config_file or CONFIG_FILE)

        loc_raw = raw.get("location") or {}
        location = Location(
            zip_code=str(loc_raw.get("zip", "") or "75287"),
            lat=float(loc_raw.get("lat", 32.9968)),
            lon=float(loc_raw.get("lon", -96.8400)),
            approximate=bool(loc_raw.get("approximate", True)),
        )

        s = raw.get("schedule") or {}
        schedule = SleepSchedule(
            bedtime=_time(s.get("bedtime"), time(23, 0)),
            wake_weekday=_time(s.get("wake_weekday"), time(8, 0)),
            wake_weekend=_time(s.get("wake_weekend"), time(9, 0)),
            open_earliest=_time(s.get("open_earliest"), time(20, 0)),
        )

        t = raw.get("thresholds") or {}
        thresholds = Thresholds(
            max_temp_f=float(t.get("max_temp_f", 78.0)),
            min_temp_f=_opt_float(t.get("min_temp_f", 50.0)),
            max_precip_pct=float(t.get("max_precip_pct", 20.0)),
            max_dewpoint_f=_opt_float(t.get("max_dewpoint_f")),
            max_wind_mph=_opt_float(t.get("max_wind_mph")),
            target_hours=float(t.get("target_hours", 6.0)),
            min_hours=float(t.get("min_hours", 3.0)),
            unknown_precip_blocks=bool(t.get("unknown_precip_blocks", True)),
        )

        g = os.getenv
        alerts = raw.get("alerts") or {}
        notifier = Notifier(
            smtp_host=g("SMTP_HOST", ""),
            smtp_port=int(g("SMTP_PORT", "587") or 587),
            smtp_user=g("SMTP_USER", ""),
            smtp_password=g("SMTP_PASSWORD", ""),
            email_to=_csv(g("WINDOW_ALERT_EMAIL_TO", "")),
            sms_to=_csv(g("WINDOW_ALERT_SMS_TO", "")),
            routes=tuple(alerts.get("routes") or ("open", "marginal")),
            sms_routes=tuple(alerts.get("sms_routes") or ("open",)),
            dry_run=dry_run or _truthy(g("DRY_RUN", "")),
        )

        return cls(location=location, schedule=schedule, thresholds=thresholds,
                   db_path=Path(g("WINDOW_DB") or (DATA_DIR / "history.db")),
                   grid_cache=DATA_DIR / "grid.json",
                   notifier=notifier)


def _csv(value: str) -> List[str]:
    return [p.strip() for p in (value or "").split(",") if p.strip()]


def _truthy(value: str) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _read_yaml(path: Path) -> Dict[str, Any]:
    """Read the YAML config, tolerating its absence.

    A missing config is fine -- every value has a default, so a fresh clone
    runs. A malformed one is NOT silently ignored: that would hand back
    defaults while the operator believed their edits were live.
    """
    if not path.is_file():
        log.info("no config at %s; using defaults", path)
        return {}
    try:
        import yaml  # noqa: PLC0415 - optional until a config file exists
    except ImportError:
        raise SystemExit(
            f"{path} exists but PyYAML is not installed.\n"
            "  python -m pip install -r requirements.txt")
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        raise SystemExit(f"{path} is not valid YAML: {exc}")
    if not isinstance(data, dict):
        raise SystemExit(f"{path} must contain a mapping at the top level")
    return data

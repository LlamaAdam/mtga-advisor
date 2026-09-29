import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from window_advisor.models import HourForecast          # noqa: E402
from window_advisor.schedule import SleepSchedule       # noqa: E402
from window_advisor.windows import Thresholds           # noqa: E402

# Monday 5 Oct 2026, 7pm -> the night runs to Tuesday 8am.
MONDAY_EVENING = datetime(2026, 10, 5, 19, 0)
EIGHT_PM = datetime(2026, 10, 5, 20, 0)


@pytest.fixture
def schedule():
    return SleepSchedule()


@pytest.fixture
def thresholds():
    return Thresholds()


def hours_from(temps, precip=None, start=EIGHT_PM, dewpoints=None):
    """Build an hourly forecast from 8pm. `None` entries stay None."""
    out = []
    for i, t in enumerate(temps):
        out.append(HourForecast(
            start=start + timedelta(hours=i),
            temp_f=t,
            precip_pct=0 if precip is None else precip[i],
            dewpoint_f=None if dewpoints is None else dewpoints[i],
        ))
    return out


# 8pm Monday through 8am Tuesday inclusive of the 7am hour = 12 hours.
COOL_NIGHT = [76, 75, 74, 73, 72, 71, 70, 70, 71, 72, 74, 76]

from dataclasses import dataclass, field
from datetime import datetime

from dateutil import parser as dateutil_parser


@dataclass
class NormalizedRecord:
    source: str
    source_name: str
    metric_type: str
    start_timestamp: datetime
    end_timestamp: datetime
    value: float
    unit: str = ""
    sub_key: str = ""
    raw: dict = field(default_factory=dict)


@dataclass
class NormalizedWorkout:
    source: str
    source_name: str
    workout_type: str
    start_timestamp: datetime
    end_timestamp: datetime
    duration_minutes: float | None = None
    distance: float | None = None
    distance_unit: str | None = None
    energy_burned: float | None = None
    energy_unit: str | None = None
    external_id: str = ""
    raw: dict = field(default_factory=dict)


def parse_datetime(value: str) -> datetime:
    """Robust datetime parsing for the varied string formats health-data
    exports use (e.g. Apple's "YYYY-MM-DD HH:MM:SS +ZZZZ")."""
    return dateutil_parser.parse(value)


def to_float(value, default: float | None = None) -> float | None:
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default

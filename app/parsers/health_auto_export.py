"""Normalize Health Auto Export JSON payloads without retaining raw payloads."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from config import APP_TIMEZONE
from parsers.common import NormalizedRecord, NormalizedWorkout, parse_datetime, to_float

SOURCE = "health_auto_export"

METRIC_MAP = {
    "step_count": "steps",
    "active_energy": "active_energy",
    "resting_heart_rate": "resting_heart_rate",
    "heart_rate_variability": "hrv",
    "weight_body_mass": "weight",
    "vo2max": "vo2_max",
    "heart_rate": "heart_rate",
    "sleep_analysis": "sleep_stage",
}

SLEEP_FIELDS = {
    "core": "core",
    "rem": "rem",
    "deep": "deep",
    "awake": "awake",
    "inBed": "in_bed",
}


@dataclass
class ParseResult:
    metrics: list[NormalizedRecord]
    workouts: list[NormalizedWorkout]
    ignored: int
    notes: list[str]


def _as_datetime(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = parse_datetime(value)
        return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=ZoneInfo(APP_TIMEZONE))
    except (TypeError, ValueError, OverflowError):
        return None


def _source(item: dict[str, Any]) -> str:
    return str(item.get("source") or "Health Auto Export")


def _minutes(value: Any, unit: str) -> float | None:
    amount = to_float(value)
    if amount is None:
        return None
    normalized = unit.strip().lower()
    if normalized in {"h", "hr", "hrs", "hour", "hours"}:
        return amount * 60.0
    if normalized in {"s", "sec", "secs", "second", "seconds"}:
        return amount / 60.0
    return amount


def _metric_value(metric_name: str, item: dict[str, Any]) -> float | None:
    if metric_name == "heart_rate":
        return to_float(item.get("Avg", item.get("avg", item.get("qty"))))
    return to_float(item.get("qty"))


def _normalize_quantity(metric_type: str, value: float, unit: str) -> tuple[float, str]:
    normalized = unit.strip().lower()
    if metric_type == "weight" and normalized in {"lb", "lbs", "pound", "pounds"}:
        return value * 0.45359237, "kg"
    if metric_type == "active_energy" and normalized in {"kj", "kilojoule", "kilojoules"}:
        return value / 4.184, "kcal"
    if metric_type == "hrv" and normalized in {"s", "sec", "second", "seconds"}:
        return value * 1000.0, "ms"
    return value, unit


def _parse_metric_group(group: dict[str, Any]) -> tuple[list[NormalizedRecord], int]:
    name = str(group.get("name") or "")
    metric_type = METRIC_MAP.get(name)
    data = group.get("data")
    if not metric_type or not isinstance(data, list):
        return [], 1

    units = str(group.get("units") or "")
    records: list[NormalizedRecord] = []
    ignored = 0
    for item in data:
        if not isinstance(item, dict):
            ignored += 1
            continue
        timestamp = _as_datetime(item.get("date"))
        if timestamp is None:
            ignored += 1
            continue

        if metric_type == "sleep_stage":
            for field, stage in SLEEP_FIELDS.items():
                minutes = _minutes(item.get(field), units)
                if minutes is None or minutes <= 0:
                    continue
                records.append(
                    NormalizedRecord(
                        source=SOURCE,
                        source_name=_source(item),
                        metric_type=metric_type,
                        start_timestamp=timestamp,
                        end_timestamp=timestamp + timedelta(minutes=minutes),
                        value=minutes,
                        unit="min",
                        sub_key=stage,
                        raw={"metric_name": name},
                    )
                )
            continue

        value = _metric_value(name, item)
        if value is None:
            ignored += 1
            continue
        value, normalized_unit = _normalize_quantity(
            metric_type, value, str(item.get("units") or units)
        )
        records.append(
            NormalizedRecord(
                source=SOURCE,
                source_name=_source(item),
                metric_type=metric_type,
                start_timestamp=timestamp,
                end_timestamp=timestamp,
                value=value,
                unit=normalized_unit,
                raw={"metric_name": name},
            )
        )
    return records, ignored


def _quantity(item: Any) -> tuple[float | None, str | None]:
    if not isinstance(item, dict):
        return None, None
    return to_float(item.get("qty")), str(item.get("units") or "") or None


def _parse_workout(item: Any) -> NormalizedWorkout | None:
    if not isinstance(item, dict):
        return None
    start = _as_datetime(item.get("start"))
    end = _as_datetime(item.get("end"))
    if start is None or end is None:
        return None

    duration = to_float(item.get("duration"))
    if duration is None:
        duration = max((end - start).total_seconds() / 60.0, 0.0)
    else:
        elapsed_minutes = max((end - start).total_seconds() / 60.0, 0.0)
        if elapsed_minutes and duration > elapsed_minutes * 10:
            duration /= 60.0

    distance, distance_unit = _quantity(item.get("distance"))
    energy, energy_unit = _quantity(
        item.get("activeEnergyBurned") or item.get("activeEnergy")
    )
    return NormalizedWorkout(
        source=SOURCE,
        source_name=str(item.get("source") or "Health Auto Export"),
        workout_type=str(item.get("name") or "unknown"),
        start_timestamp=start,
        end_timestamp=end,
        duration_minutes=duration,
        distance=distance,
        distance_unit=distance_unit,
        energy_burned=energy,
        energy_unit=energy_unit,
        external_id=str(item.get("id") or ""),
        raw={"has_route": bool(item.get("route"))},
    )


def parse_health_auto_export(payload: dict[str, Any]) -> ParseResult:
    envelope = payload.get("data")
    if not isinstance(envelope, dict):
        raise ValueError("payload.data must be an object")

    records: list[NormalizedRecord] = []
    workouts: list[NormalizedWorkout] = []
    ignored = 0
    notes: list[str] = []

    metric_groups = envelope.get("metrics", [])
    if metric_groups is not None and not isinstance(metric_groups, list):
        raise ValueError("payload.data.metrics must be an array")
    for group in metric_groups or []:
        if not isinstance(group, dict):
            ignored += 1
            continue
        parsed, group_ignored = _parse_metric_group(group)
        records.extend(parsed)
        ignored += group_ignored
        if not parsed and group.get("name") not in METRIC_MAP:
            notes.append(f"unsupported metric: {group.get('name', '<missing>')}")

    workout_items = envelope.get("workouts", [])
    if workout_items is not None and not isinstance(workout_items, list):
        raise ValueError("payload.data.workouts must be an array")
    for item in workout_items or []:
        workout = _parse_workout(item)
        if workout is None:
            ignored += 1
        else:
            workouts.append(workout)

    return ParseResult(records, workouts, ignored, notes)

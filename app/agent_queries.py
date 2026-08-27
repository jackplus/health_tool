"""Bounded, read-only query surface for AI agents."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from statistics import mean
from zoneinfo import ZoneInfo

import db
from analysis import CORE_METRICS, UNITS, build_report, load_daily_series
from config import APP_TIMEZONE

ALLOWED_METRICS = set(CORE_METRICS) | {"weight", "vo2_max"}
MAX_TREND_DAYS = 366
MAX_WORKOUT_DAYS = 90


def _date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("dates must use YYYY-MM-DD") from exc


def _today() -> date:
    return datetime.now(ZoneInfo(APP_TIMEZONE)).date()


def _window(days: int, maximum: int) -> tuple[date, date]:
    if days < 1 or days > maximum:
        raise ValueError(f"days must be between 1 and {maximum}")
    end = _today() - timedelta(days=1)
    return end - timedelta(days=days - 1), end


def health_overview(days: int = 7) -> dict:
    start, end = _window(days, 90)
    series = load_daily_series(start, end)
    metrics = {}
    for metric in CORE_METRICS:
        values = [day[metric] for day in series.values() if metric in day]
        if values:
            metrics[metric] = {
                "average": round(mean(values), 2),
                "valid_days": len(values),
                "unit": UNITS[metric],
            }
    return {
        "period": {"start": start.isoformat(), "end": end.isoformat()},
        "timezone": APP_TIMEZONE,
        "data_coverage": {"days_requested": days, "days_with_any_data": len(series)},
        "metrics": metrics,
        "limitations": ["Aggregated data only", "Not medical advice"],
    }


def metric_trend(metric: str, start_date: str, end_date: str) -> dict:
    if metric not in ALLOWED_METRICS:
        raise ValueError(f"metric must be one of: {', '.join(sorted(ALLOWED_METRICS))}")
    start = _date(start_date)
    end = _date(end_date)
    span = (end - start).days + 1
    if span < 1 or span > MAX_TREND_DAYS:
        raise ValueError(f"date range must be between 1 and {MAX_TREND_DAYS} days")
    series = load_daily_series(start, end)
    points = [
        {"date": day.isoformat(), "value": values[metric], "unit": UNITS[metric]}
        for day, values in sorted(series.items())
        if metric in values
    ]
    return {
        "metric": metric,
        "period": {"start": start.isoformat(), "end": end.isoformat()},
        "timezone": APP_TIMEZONE,
        "data_coverage": {"days_requested": span, "valid_days": len(points)},
        "points": points,
        "limitations": ["One preferred-source aggregate per local calendar day"],
    }


def recent_workouts(days: int = 14, workout_type: str | None = None) -> dict:
    start, end = _window(days, MAX_WORKOUT_DAYS)
    query = """
        SELECT workout_type, start_timestamp, end_timestamp, duration_minutes,
               distance, distance_unit, energy_burned, energy_unit, source
        FROM workouts
        WHERE start_timestamp >= (%s::date AT TIME ZONE %s)
          AND start_timestamp < ((%s::date + 1) AT TIME ZONE %s)
    """
    params: list = [start, APP_TIMEZONE, end, APP_TIMEZONE]
    if workout_type:
        query += " AND workout_type = %s"
        params.append(workout_type)
    query += " ORDER BY start_timestamp DESC LIMIT 200"
    rows = db.fetch_rows(query, tuple(params))
    for row in rows:
        for key in ("start_timestamp", "end_timestamp"):
            if row.get(key):
                row[key] = row[key].isoformat()
    return {
        "period": {"start": start.isoformat(), "end": end.isoformat()},
        "timezone": APP_TIMEZONE,
        "data_coverage": {"returned_workouts": len(rows), "limit": 200},
        "workouts": rows,
        "limitations": ["GPS routes and raw workout metadata are never returned"],
    }


def recovery_context(target_date: str) -> dict:
    target = _date(target_date)
    if target >= _today():
        raise ValueError("target_date must be before today")
    series = load_daily_series(target - timedelta(days=28), target)
    report = build_report(series, "daily", target)
    return {
        "period": {"start": target.isoformat(), "end": target.isoformat()},
        "timezone": APP_TIMEZONE,
        "data_coverage": report["data_coverage"],
        "baseline_comparisons": report["comparisons"],
        "rule_findings": report["findings"],
        "recommendations": report["recommendations"],
        "limitations": ["Baseline-relative informational analysis; not a diagnosis"],
    }


def data_quality(days: int = 30) -> dict:
    start, end = _window(days, MAX_TREND_DAYS)
    series = load_daily_series(start, end)
    metrics = {
        metric: sum(1 for values in series.values() if metric in values)
        for metric in sorted(ALLOWED_METRICS)
    }
    sync = db.fetch_rows(
        """
        SELECT uploaded_at, status, records_parsed, records_inserted,
               records_duplicate, records_ignored
        FROM raw_uploads
        ORDER BY uploaded_at DESC LIMIT 1
        """
    )
    latest_sync = sync[0] if sync else None
    if latest_sync and latest_sync.get("uploaded_at"):
        latest_sync["uploaded_at"] = latest_sync["uploaded_at"].isoformat()
    return {
        "period": {"start": start.isoformat(), "end": end.isoformat()},
        "timezone": APP_TIMEZONE,
        "days_with_any_data": len(series),
        "valid_days_by_metric": metrics,
        "latest_sync": latest_sync,
        "limitations": ["Missing days may mean either no measurement or no device coverage"],
    }


def generated_report(report_type: str = "weekly", period_end: str | None = None) -> dict:
    if report_type not in {"daily", "weekly"}:
        raise ValueError("report_type must be daily or weekly")
    query = """
        SELECT report_type, period_start, period_end, generated_at, rule_version,
               status, data_coverage, summary, comparisons, findings, recommendations
        FROM insight_reports WHERE report_type = %s
    """
    params: list = [report_type]
    if period_end:
        query += " AND period_end = %s"
        params.append(_date(period_end))
    query += " ORDER BY period_end DESC, generated_at DESC LIMIT 1"
    rows = db.fetch_rows(query, tuple(params))
    if not rows:
        return {"status": "not_found", "report_type": report_type}
    report = rows[0]
    for key in ("period_start", "period_end", "generated_at"):
        report[key] = report[key].isoformat()
    return report


def profile_and_goals() -> dict:
    rows = db.fetch_rows(
        "SELECT timezone, goals, constraints, updated_at FROM health_profile WHERE id = 1"
    )
    if not rows:
        return {"timezone": APP_TIMEZONE, "goals": [], "constraints": []}
    profile = rows[0]
    profile["updated_at"] = profile["updated_at"].isoformat()
    return profile

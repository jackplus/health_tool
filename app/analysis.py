"""Transparent, baseline-relative daily and weekly health findings."""

from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from statistics import mean
from typing import Iterable

import db
from config import ANALYSIS_SOURCE_ORDER, APP_TIMEZONE

RULE_VERSION = "1.0.0"
CORE_METRICS = (
    "sleep_minutes",
    "resting_heart_rate",
    "hrv",
    "steps",
    "active_energy",
    "workout_minutes",
)
UNITS = {
    "sleep_minutes": "min",
    "resting_heart_rate": "bpm",
    "hrv": "ms",
    "steps": "steps",
    "active_energy": "kcal",
    "workout_minutes": "min",
    "weight": "kg",
    "vo2_max": "mL/kg/min",
}
LABELS = {
    "sleep_minutes": "睡眠时长",
    "resting_heart_rate": "静息心率",
    "hrv": "心率变异性",
    "steps": "日均步数",
    "active_energy": "日均活动能量",
    "workout_minutes": "日均运动时长",
}


def _daily_rows(start: date, end: date) -> list[dict]:
    rows = db.fetch_rows(
        """
        SELECT (start_timestamp AT TIME ZONE %s)::date AS day,
               source, metric_type, sub_key,
               CASE WHEN metric_type IN ('resting_heart_rate', 'hrv', 'weight', 'vo2_max')
                    THEN AVG(value) ELSE SUM(value) END AS value
        FROM health_metrics
        WHERE start_timestamp >= (%s::date AT TIME ZONE %s)
          AND start_timestamp < ((%s::date + 1) AT TIME ZONE %s)
          AND metric_type IN ('sleep_stage', 'resting_heart_rate', 'hrv', 'steps',
                              'active_energy', 'weight', 'vo2_max')
          AND (metric_type <> 'sleep_stage' OR sub_key IN ('asleep', 'core', 'deep', 'rem'))
        GROUP BY day, source, metric_type, sub_key
        ORDER BY day
        """,
        (APP_TIMEZONE, start, APP_TIMEZONE, end, APP_TIMEZONE),
    )
    workouts = db.fetch_rows(
        """
        SELECT (start_timestamp AT TIME ZONE %s)::date AS day,
               source, SUM(duration_minutes) AS value
        FROM workouts
        WHERE start_timestamp >= (%s::date AT TIME ZONE %s)
          AND start_timestamp < ((%s::date + 1) AT TIME ZONE %s)
        GROUP BY day, source
        ORDER BY day
        """,
        (APP_TIMEZONE, start, APP_TIMEZONE, end, APP_TIMEZONE),
    )
    normalized_rows: list[dict] = []
    sleep: dict[tuple[date, str], dict[str, float]] = defaultdict(dict)
    for row in rows:
        if row["metric_type"] != "sleep_stage":
            normalized_rows.append(row)
            continue
        key = (row["day"], row["source"])
        sleep[key][row["sub_key"]] = float(row["value"])
    for (day, source), stages in sleep.items():
        detailed = sum(stages.get(stage, 0.0) for stage in ("core", "deep", "rem"))
        normalized_rows.append(
            {
                "day": day,
                "source": source,
                "metric_type": "sleep_minutes",
                "value": detailed if detailed > 0 else stages.get("asleep", 0.0),
            }
        )
    for row in workouts:
        row["metric_type"] = "workout_minutes"
        normalized_rows.append(row)
    return normalized_rows


def _prefer_sources(rows: Iterable[dict]) -> dict[date, dict[str, float]]:
    candidates: dict[tuple[date, str], dict[str, float]] = defaultdict(dict)
    for row in rows:
        if row.get("value") is not None:
            candidates[(row["day"], row["metric_type"])][row["source"]] = float(row["value"])

    result: dict[date, dict[str, float]] = defaultdict(dict)
    for (day, metric), sources in candidates.items():
        selected = next((sources[s] for s in ANALYSIS_SOURCE_ORDER if s in sources), None)
        if selected is not None:
            result[day][metric] = selected
    return dict(result)


def load_daily_series(start: date, end: date) -> dict[date, dict[str, float]]:
    if end < start:
        raise ValueError("end date must not be before start date")
    return _prefer_sources(_daily_rows(start, end))


def _metric_values(
    series: dict[date, dict[str, float]], start: date, end: date, metric: str
) -> list[float]:
    values: list[float] = []
    cursor = start
    while cursor <= end:
        value = series.get(cursor, {}).get(metric)
        if value is not None:
            values.append(value)
        cursor += timedelta(days=1)
    return values


def _finding(metric: str, current: float, baseline: float, valid_days: int) -> dict | None:
    if baseline == 0:
        return None
    delta = current - baseline
    delta_pct = delta / baseline
    severity = "attention"
    title = interpretation = ""

    if metric == "sleep_minutes" and delta <= -30 and delta_pct <= -0.10:
        title = "近期睡眠低于个人基线"
        interpretation = "恢复时间出现持续性下降，宜优先稳定作息和训练后的休息。"
    elif metric == "resting_heart_rate" and delta >= 5 and delta_pct >= 0.08:
        title = "静息心率高于个人基线"
        interpretation = "这可能与恢复不足、压力或近期负荷有关，需要结合其他指标观察。"
    elif metric == "hrv" and delta_pct <= -0.15:
        title = "HRV 低于个人基线"
        interpretation = "近期自主神经恢复指标偏低，单独一项不能作为医学判断。"
    elif metric == "steps" and delta_pct <= -0.20:
        title = "近期活动量下降"
        interpretation = "日常活动明显少于个人惯常水平。"
    elif metric == "active_energy" and delta_pct <= -0.20:
        title = "近期活动能量下降"
        interpretation = "整体身体活动低于个人惯常水平。"
    elif metric == "workout_minutes" and delta >= 20 and delta_pct >= 0.50:
        title = "近期运动负荷增长较快"
        interpretation = "训练时长相对个人基线有明显跃升，需关注恢复是否同步。"
    else:
        return None

    return {
        "metric": metric,
        "severity": severity,
        "title": title,
        "evidence": {
            "current": round(current, 2),
            "baseline": round(baseline, 2),
            "delta_percent": round(delta_pct * 100, 1),
            "unit": UNITS[metric],
            "baseline_valid_days": valid_days,
        },
        "interpretation": interpretation,
    }


def build_report(
    series: dict[date, dict[str, float]], report_type: str, period_end: date
) -> dict:
    if report_type not in {"daily", "weekly"}:
        raise ValueError("report_type must be daily or weekly")
    period_days = 1 if report_type == "daily" else 7
    period_start = period_end - timedelta(days=period_days - 1)
    baseline_end = period_start - timedelta(days=1)
    baseline_start = baseline_end - timedelta(days=27)

    present_days = sum(1 for day in (period_start + timedelta(days=i) for i in range(period_days)) if series.get(day))
    coverage = {
        "period_days": period_days,
        "days_with_data": present_days,
        "coverage_percent": round(present_days / period_days * 100, 1),
        "baseline_start": baseline_start.isoformat(),
        "baseline_end": baseline_end.isoformat(),
        "timezone": APP_TIMEZONE,
        "metrics": {},
    }

    findings: list[dict] = []
    comparisons: dict[str, dict] = {}
    for metric in CORE_METRICS:
        current_values = _metric_values(series, period_start, period_end, metric)
        baseline_values = _metric_values(series, baseline_start, baseline_end, metric)
        coverage["metrics"][metric] = {
            "current_valid_days": len(current_values),
            "baseline_valid_days": len(baseline_values),
        }
        if not current_values or len(baseline_values) < 14:
            continue
        current = mean(current_values)
        baseline = mean(baseline_values)
        comparisons[metric] = {
            "current": round(current, 2),
            "baseline": round(baseline, 2),
            "unit": UNITS[metric],
        }
        item = _finding(metric, current, baseline, len(baseline_values))
        if item:
            findings.append(item)

    recommendations: list[dict] = []
    finding_metrics = {item["metric"] for item in findings}
    if finding_metrics & {"sleep_minutes", "resting_heart_rate", "hrv"}:
        recommendations.append(
            {
                "priority": "high",
                "text": "未来两到三天优先保证睡眠和恢复；若主观疲劳明显，可降低训练强度。",
                "basis": sorted(finding_metrics & {"sleep_minutes", "resting_heart_rate", "hrv"}),
            }
        )
    if "workout_minutes" in finding_metrics:
        recommendations.append(
            {
                "priority": "medium",
                "text": "避免继续快速增加运动时长，先观察睡眠、静息心率和 HRV 是否恢复。",
                "basis": ["workout_minutes"],
            }
        )
    if finding_metrics & {"steps", "active_energy"}:
        recommendations.append(
            {
                "priority": "medium",
                "text": "在身体状态允许时，安排容易完成的步行或轻量活动，逐步回到个人惯常水平。",
                "basis": sorted(finding_metrics & {"steps", "active_energy"}),
            }
        )

    has_baseline = any(
        metric["baseline_valid_days"] >= 14 for metric in coverage["metrics"].values()
    )
    if not has_baseline:
        status = "insufficient_data"
        summary = "个人基线数据不足，至少需要 14 个有效日后才能生成趋势建议。"
    elif findings:
        status = "attention"
        summary = f"发现 {len(findings)} 项相对个人基线的明显变化。"
    else:
        status = "stable"
        summary = "已覆盖的核心指标与个人基线大体一致。"

    return {
        "report_type": report_type,
        "period_start": period_start,
        "period_end": period_end,
        "rule_version": RULE_VERSION,
        "status": status,
        "data_coverage": coverage,
        "summary": summary,
        "comparisons": comparisons,
        "findings": findings,
        "recommendations": recommendations,
    }


def generate_report(report_type: str, period_end: date) -> dict:
    period_days = 1 if report_type == "daily" else 7
    period_start = period_end - timedelta(days=period_days - 1)
    series = load_daily_series(period_start - timedelta(days=28), period_end)
    report = build_report(series, report_type, period_end)
    db.upsert_insight_report(report)
    return report

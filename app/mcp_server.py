from typing import Callable

from mcp.server.fastmcp import FastMCP

import db
from agent_queries import (
    data_quality,
    generated_report,
    health_overview,
    metric_trend,
    profile_and_goals,
    recent_workouts,
    recovery_context,
)

mcp = FastMCP(
    "Private Health Data",
    instructions=(
        "Read-only personal health tools. Check data quality before analysis. "
        "Separate measured facts from inference and suggestions. Never diagnose disease. "
        "Do not claim that missing data means a zero value."
    ),
)


def _call(tool_name: str, params: dict, function: Callable, *args, **kwargs):
    try:
        result = function(*args, **kwargs)
        count = len(result.get("points", result.get("workouts", []))) if isinstance(result, dict) else 0
        db.record_mcp_audit(tool_name, params, count, "success")
        return result
    except Exception:
        db.record_mcp_audit(tool_name, params, 0, "failed")
        raise


@mcp.tool()
def get_health_overview(days: int = 7) -> dict:
    """Get bounded daily aggregates for a recent period; no raw HealthKit events."""
    return _call("get_health_overview", {"days": days}, health_overview, days)


@mcp.tool()
def get_metric_trend(metric: str, start_date: str, end_date: str) -> dict:
    """Get one allowed daily metric trend for an ISO date range of at most one year."""
    params = {"metric": metric, "start_date": start_date, "end_date": end_date}
    return _call("get_metric_trend", params, metric_trend, metric, start_date, end_date)


@mcp.tool()
def get_recent_workouts(days: int = 14, workout_type: str | None = None) -> dict:
    """Get recent workout summaries without GPS routes or raw metadata."""
    params = {"days": days, "workout_type": workout_type}
    return _call("get_recent_workouts", params, recent_workouts, days, workout_type)


@mcp.tool()
def get_recovery_context(target_date: str) -> dict:
    """Compare one past day with the user's preceding 28-day baseline."""
    return _call(
        "get_recovery_context", {"target_date": target_date}, recovery_context, target_date
    )


@mcp.tool()
def get_data_quality(days: int = 30) -> dict:
    """Check coverage, missing metrics, and latest ingestion before drawing conclusions."""
    return _call("get_data_quality", {"days": days}, data_quality, days)


@mcp.tool()
def get_generated_report(report_type: str = "weekly", period_end: str | None = None) -> dict:
    """Read a persisted deterministic daily or weekly report."""
    params = {"report_type": report_type, "period_end": period_end}
    return _call("get_generated_report", params, generated_report, report_type, period_end)


@mcp.tool()
def get_profile_and_goals() -> dict:
    """Read the user's explicitly configured goals and constraints."""
    return _call("get_profile_and_goals", {}, profile_and_goals)


def main() -> None:
    db.apply_migrations()
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()

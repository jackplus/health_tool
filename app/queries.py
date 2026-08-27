from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import streamlit as st

import db
from config import APP_TIMEZONE, DEFAULT_SOURCE_PRIORITY

SOURCES = ("health_auto_export", "apple_health", "xiaomi")
SLEEP_STAGES = ("asleep", "core", "deep", "rem")


def _resolve_source_order(metric_type: str, source_filter: str) -> list[str]:
    if source_filter in SOURCES:
        return [source_filter]
    primary = DEFAULT_SOURCE_PRIORITY.get(metric_type, "apple_health")
    return [primary] + [s for s in SOURCES if s != primary]


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def today_range() -> tuple[datetime, datetime]:
    local_now = datetime.now(ZoneInfo(APP_TIMEZONE))
    local_start = local_now.replace(hour=0, minute=0, second=0, microsecond=0)
    return local_start.astimezone(timezone.utc), (local_start + timedelta(days=1)).astimezone(timezone.utc)


def local_dates_to_utc(start: date, end: date) -> tuple[datetime, datetime]:
    zone = ZoneInfo(APP_TIMEZONE)
    local_start = datetime.combine(start, datetime.min.time(), tzinfo=zone)
    local_end = datetime.combine(end + timedelta(days=1), datetime.min.time(), tzinfo=zone)
    return local_start.astimezone(timezone.utc), local_end.astimezone(timezone.utc)


def last_n_days_range(n: int) -> tuple[datetime, datetime]:
    end = now_utc()
    return end - timedelta(days=n), end


@st.cache_data(ttl=300)
def kpi_value(
    metric_type: str,
    agg: str,
    start: datetime,
    end: datetime,
    source_filter: str = "all",
    sub_keys: tuple[str, ...] | None = None,
) -> tuple[float | None, str | None]:
    """Returns (value, source_used). Falls back to the non-priority source
    only when the caller left source_filter="all" and the priority source
    has no rows in range."""
    assert agg in ("sum", "avg", "min", "max", "count")
    for src in _resolve_source_order(metric_type, source_filter):
        query = f"""
            SELECT {agg}(value) AS v FROM health_metrics
            WHERE metric_type = %s AND source = %s
              AND start_timestamp >= %s AND start_timestamp < %s
        """
        params = [metric_type, src, start, end]
        if sub_keys:
            placeholders = ",".join(["%s"] * len(sub_keys))
            query += f" AND sub_key IN ({placeholders})"
            params.extend(sub_keys)
        df = db.fetch_df(query, tuple(params))
        if not df.empty and df.iloc[0]["v"] is not None:
            return float(df.iloc[0]["v"]), src
    return None, None


@st.cache_data(ttl=300)
def trend_df(
    metric_type: str,
    start: datetime,
    end: datetime,
    source_filter: str = "all",
    sub_keys: tuple[str, ...] | None = None,
):
    sources = [source_filter] if source_filter in SOURCES else list(SOURCES)
    src_placeholders = ",".join(["%s"] * len(sources))
    query = f"""
        SELECT date_trunc('day', start_timestamp) AS day, source,
               SUM(value) AS total, AVG(value) AS avg_value
        FROM health_metrics
        WHERE metric_type = %s AND source IN ({src_placeholders})
          AND start_timestamp >= %s AND start_timestamp < %s
    """
    params = [metric_type] + sources + [start, end]
    if sub_keys:
        sub_placeholders = ",".join(["%s"] * len(sub_keys))
        query += f" AND sub_key IN ({sub_placeholders})"
        params.extend(sub_keys)
    query += " GROUP BY day, source ORDER BY day"
    return db.fetch_df(query, tuple(params))


@st.cache_data(ttl=300)
def workouts_df(start: datetime, end: datetime, source_filter: str = "all"):
    sources = [source_filter] if source_filter in SOURCES else list(SOURCES)
    placeholders = ",".join(["%s"] * len(sources))
    query = f"""
        SELECT source, source_name, workout_type, start_timestamp, end_timestamp,
               duration_minutes, distance, distance_unit, energy_burned, energy_unit
        FROM workouts
        WHERE source IN ({placeholders}) AND start_timestamp >= %s AND start_timestamp < %s
        ORDER BY start_timestamp DESC
    """
    params = sources + [start, end]
    return db.fetch_df(query, tuple(params))


@st.cache_data(ttl=60)
def upload_history_df(limit: int = 50):
    return db.fetch_df(
        """
        SELECT source, transport, filename, uploaded_at, status, records_parsed,
               records_inserted, records_duplicate, records_ignored, notes
        FROM raw_uploads ORDER BY uploaded_at DESC LIMIT %s
        """,
        (limit,),
    )


@st.cache_data(ttl=300)
def latest_value(
    metric_type: str, source_filter: str = "all", within_days: int = 30
) -> tuple[float | None, "datetime | None", str | None]:
    """Most recent single reading (e.g. weight), not an aggregate."""
    start, end = last_n_days_range(within_days)
    for src in _resolve_source_order(metric_type, source_filter):
        df = db.fetch_df(
            """
            SELECT value, start_timestamp FROM health_metrics
            WHERE metric_type = %s AND source = %s
              AND start_timestamp >= %s AND start_timestamp < %s
            ORDER BY start_timestamp DESC LIMIT 1
            """,
            (metric_type, src, start, end),
        )
        if not df.empty:
            return float(df.iloc[0]["value"]), df.iloc[0]["start_timestamp"], src
    return None, None, None


@st.cache_data(ttl=300)
def available_sources() -> list[str]:
    df = db.fetch_df("SELECT DISTINCT source FROM health_metrics")
    return sorted(df["source"].tolist()) if not df.empty else []


@st.cache_data(ttl=60)
def insight_reports_df(report_type: str, limit: int = 12):
    return db.fetch_df(
        """
        SELECT period_start, period_end, generated_at, status, summary,
               data_coverage, comparisons, findings, recommendations
        FROM insight_reports
        WHERE report_type = %s
        ORDER BY period_end DESC LIMIT %s
        """,
        (report_type, limit),
    )


def update_profile(goals: list[str], constraints: list[str]) -> None:
    with db.get_conn() as conn:
        with conn.cursor() as cur:
            import psycopg2.extras

            cur.execute(
                """
                UPDATE health_profile
                SET goals = %s, constraints = %s, updated_at = now()
                WHERE id = 1
                """,
                (psycopg2.extras.Json(goals), psycopg2.extras.Json(constraints)),
            )


def profile() -> dict:
    rows = db.fetch_rows(
        "SELECT timezone, goals, constraints, updated_at FROM health_profile WHERE id = 1"
    )
    return rows[0] if rows else {"timezone": APP_TIMEZONE, "goals": [], "constraints": []}

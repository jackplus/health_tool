"""Optional v2: precomputed daily rollups for faster dashboard queries.

Not required for v1 -- personal-scale data with the indexes in schema.sql
is fast enough queried live (see queries.py + st.cache_data). This exists
for the "Recompute rollups" button on the Settings page, and as the payload
for the optional APScheduler job in scheduler.py.
"""

import db


def compute_daily_rollups(days_back: int | None = None) -> dict:
    """(Re)computes sum/avg daily_rollups rows from health_metrics.

    days_back limits recomputation to recent history (cheap, for a routine
    nightly refresh); pass None to rebuild the full history (e.g. after a
    schema/parser fix).
    """
    date_filter = ""
    params: list = []
    if days_back is not None:
        date_filter = "WHERE start_timestamp >= now() - (%s * interval '1 day')"
        params.append(days_back)

    affected = {"sum": 0, "avg": 0}
    with db.get_conn() as conn:
        with conn.cursor() as cur:
            for agg_type, agg_fn in (("sum", "SUM"), ("avg", "AVG")):
                cur.execute(
                    f"""
                    INSERT INTO daily_rollups (day, metric_type, source, agg_type, agg_value)
                    SELECT date_trunc('day', start_timestamp)::date AS day,
                           metric_type, source, %s AS agg_type, {agg_fn}(value)
                    FROM health_metrics
                    {date_filter}
                    GROUP BY day, metric_type, source
                    ON CONFLICT (day, metric_type, source, agg_type)
                    DO UPDATE SET agg_value = EXCLUDED.agg_value, computed_at = now()
                    """,
                    tuple([agg_type] + params),
                )
                affected[agg_type] = cur.rowcount
    return affected

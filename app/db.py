from contextlib import contextmanager

import psycopg2
import psycopg2.extras

from config import DB_CONFIG, MIGRATIONS_DIR


@contextmanager
def get_conn():
    conn = psycopg2.connect(**DB_CONFIG)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def record_upload_start(source: str, filename: str) -> int:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO raw_uploads (source, filename, status)
                VALUES (%s, %s, 'pending')
                RETURNING id
                """,
                (source, filename),
            )
            return cur.fetchone()[0]


def record_api_ingestion_start(payload_hash: str) -> tuple[int, bool, str]:
    """Return (upload id, already_seen, current status)."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO raw_uploads
                    (source, filename, status, transport, payload_hash)
                VALUES ('health_auto_export', %s, 'pending', 'api', %s)
                ON CONFLICT DO NOTHING
                RETURNING id, status
                """,
                (f"api-{payload_hash[:12]}.json", payload_hash),
            )
            created = cur.fetchone()
            if created:
                return created[0], False, created[1]
            cur.execute(
                """
                SELECT id, status FROM raw_uploads
                WHERE transport = 'api' AND payload_hash = %s
                """,
                (payload_hash,),
            )
            existing = cur.fetchone()
            if existing is None:
                raise RuntimeError("failed to create or locate API ingestion record")
            return existing[0], True, existing[1]


def record_upload_finish(
    upload_id: int,
    status: str,
    records_parsed: int,
    records_inserted: int,
    notes: str | None,
    records_duplicate: int = 0,
    records_ignored: int = 0,
) -> None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE raw_uploads
                SET status = %s, records_parsed = %s, records_inserted = %s,
                    records_duplicate = %s, records_ignored = %s, notes = %s
                WHERE id = %s
                """,
                (
                    status,
                    records_parsed,
                    records_inserted,
                    records_duplicate,
                    records_ignored,
                    notes,
                    upload_id,
                ),
            )


def upsert_metrics(rows: list[dict], ingestion_batch_id: int) -> int:
    """Batch-upsert normalized metric rows. Returns rows actually inserted
    (conflicts on the dedup key are silently skipped, not counted)."""
    if not rows:
        return 0

    template = (
        "(%(source)s, %(source_name)s, %(metric_type)s, %(start_timestamp)s, "
        "%(end_timestamp)s, %(value)s, %(unit)s, %(sub_key)s, %(raw)s, "
        f"{ingestion_batch_id})"
    )
    inserted = 0
    with get_conn() as conn:
        with conn.cursor() as cur:
            result = psycopg2.extras.execute_values(
                cur,
                """
                INSERT INTO health_metrics
                    (source, source_name, metric_type, start_timestamp,
                     end_timestamp, value, unit, sub_key, raw, ingestion_batch_id)
                VALUES %s
                ON CONFLICT (source, source_name, metric_type, start_timestamp,
                             end_timestamp, sub_key)
                DO NOTHING
                RETURNING id
                """,
                rows,
                template=template,
                page_size=1000,
                fetch=True,
            )
            inserted = len(result) if result else 0
    return inserted


def upsert_workouts(rows: list[dict], ingestion_batch_id: int) -> int:
    if not rows:
        return 0

    template = (
        "(%(source)s, %(source_name)s, %(external_id)s, %(workout_type)s, %(start_timestamp)s, "
        "%(end_timestamp)s, %(duration_minutes)s, %(distance)s, %(distance_unit)s, "
        f"%(energy_burned)s, %(energy_unit)s, %(raw)s, {ingestion_batch_id})"
    )
    with get_conn() as conn:
        with conn.cursor() as cur:
            result = psycopg2.extras.execute_values(
                cur,
                """
                INSERT INTO workouts
                    (source, source_name, external_id, workout_type, start_timestamp, end_timestamp,
                     duration_minutes, distance, distance_unit, energy_burned,
                     energy_unit, raw, ingestion_batch_id)
                VALUES %s
                ON CONFLICT DO NOTHING
                RETURNING id
                """,
                rows,
                template=template,
                page_size=500,
                fetch=True,
            )
            return len(result) if result else 0


def apply_migrations() -> None:
    from pathlib import Path

    migration_dir = Path(MIGRATIONS_DIR)
    if not migration_dir.exists():
        migration_dir = Path(__file__).resolve().parents[1] / "db" / "migrations"
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    name TEXT PRIMARY KEY,
                    applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
                )
                """
            )
            for path in sorted(migration_dir.glob("*.sql")):
                cur.execute("SELECT 1 FROM schema_migrations WHERE name = %s", (path.name,))
                if cur.fetchone():
                    continue
                cur.execute(path.read_text())
                cur.execute("INSERT INTO schema_migrations (name) VALUES (%s)", (path.name,))


def fetch_df(query: str, params: tuple = ()):
    import pandas as pd

    with get_conn() as conn:
        return pd.read_sql_query(query, conn, params=params)


def fetch_rows(query: str, params: tuple = ()) -> list[dict]:
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(query, params)
            return [dict(row) for row in cur.fetchall()]


def upsert_insight_report(report: dict) -> None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO insight_reports
                    (report_type, period_start, period_end, rule_version, status,
                     data_coverage, summary, comparisons, findings, recommendations)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (report_type, period_end, rule_version)
                DO UPDATE SET
                    period_start = EXCLUDED.period_start,
                    generated_at = now(),
                    status = EXCLUDED.status,
                    data_coverage = EXCLUDED.data_coverage,
                    summary = EXCLUDED.summary,
                    comparisons = EXCLUDED.comparisons,
                    findings = EXCLUDED.findings,
                    recommendations = EXCLUDED.recommendations
                """,
                (
                    report["report_type"],
                    report["period_start"],
                    report["period_end"],
                    report["rule_version"],
                    report["status"],
                    psycopg2.extras.Json(report["data_coverage"]),
                    report["summary"],
                    psycopg2.extras.Json(report["comparisons"]),
                    psycopg2.extras.Json(report["findings"]),
                    psycopg2.extras.Json(report["recommendations"]),
                ),
            )


def record_mcp_audit(tool_name: str, params: dict, record_count: int, status: str) -> None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO mcp_audit_log (tool_name, params, record_count, status)
                VALUES (%s, %s, %s, %s)
                """,
                (tool_name, psycopg2.extras.Json(params), record_count, status),
            )

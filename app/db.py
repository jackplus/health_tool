from contextlib import contextmanager

import psycopg2
import psycopg2.extras
import streamlit as st

from config import DB_CONFIG


@st.cache_resource
def _pool_placeholder():
    # Streamlit singleton hook so we only log the connection target once per
    # process. Actual connections are opened per-use below (personal-scale
    # traffic doesn't need a real pool).
    return object()


@contextmanager
def get_conn():
    _pool_placeholder()
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


def record_upload_finish(
    upload_id: int,
    status: str,
    records_parsed: int,
    records_inserted: int,
    notes: str | None,
) -> None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE raw_uploads
                SET status = %s, records_parsed = %s, records_inserted = %s, notes = %s
                WHERE id = %s
                """,
                (status, records_parsed, records_inserted, notes, upload_id),
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
        "(%(source)s, %(source_name)s, %(workout_type)s, %(start_timestamp)s, "
        "%(end_timestamp)s, %(duration_minutes)s, %(distance)s, %(distance_unit)s, "
        f"%(energy_burned)s, %(energy_unit)s, %(raw)s, {ingestion_batch_id})"
    )
    with get_conn() as conn:
        with conn.cursor() as cur:
            result = psycopg2.extras.execute_values(
                cur,
                """
                INSERT INTO workouts
                    (source, source_name, workout_type, start_timestamp, end_timestamp,
                     duration_minutes, distance, distance_unit, energy_burned,
                     energy_unit, raw, ingestion_batch_id)
                VALUES %s
                ON CONFLICT (source, source_name, start_timestamp, end_timestamp, workout_type)
                DO NOTHING
                RETURNING id
                """,
                rows,
                template=template,
                page_size=500,
                fetch=True,
            )
            return len(result) if result else 0


def fetch_df(query: str, params: tuple = ()):
    import pandas as pd

    with get_conn() as conn:
        return pd.read_sql_query(query, conn, params=params)

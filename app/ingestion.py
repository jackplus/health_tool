import io
import hashlib
import json
import os
from datetime import datetime, timezone
from typing import IO

import psycopg2.extras

import db
from config import BATCH_SIZE, UPLOAD_DIR
from parsers.apple_health import parse_apple_export
from parsers.health_auto_export import parse_health_auto_export
from parsers.common import NormalizedRecord, NormalizedWorkout
from parsers.xiaomi import parse_xiaomi_export


def _save_raw_file(file_bytes: bytes, source: str, filename: str) -> str:
    target_dir = os.path.join(UPLOAD_DIR, source)
    os.makedirs(target_dir, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = os.path.join(target_dir, f"{stamp}_{filename}")
    with open(path, "wb") as f:
        f.write(file_bytes)
    return path


def _record_to_row(rec: NormalizedRecord) -> dict:
    return {
        "source": rec.source,
        "source_name": rec.source_name,
        "metric_type": rec.metric_type,
        "start_timestamp": rec.start_timestamp,
        "end_timestamp": rec.end_timestamp,
        "value": rec.value,
        "unit": rec.unit,
        "sub_key": rec.sub_key,
        "raw": psycopg2.extras.Json(rec.raw),
    }


def _workout_to_row(w: NormalizedWorkout) -> dict:
    return {
        "source": w.source,
        "source_name": w.source_name,
        "workout_type": w.workout_type,
        "start_timestamp": w.start_timestamp,
        "end_timestamp": w.end_timestamp,
        "duration_minutes": w.duration_minutes,
        "distance": w.distance,
        "distance_unit": w.distance_unit,
        "energy_burned": w.energy_burned,
        "energy_unit": w.energy_unit,
        "external_id": w.external_id,
        "raw": psycopg2.extras.Json(w.raw),
    }


def ingest_apple_health(file_obj: IO[bytes], filename: str) -> dict:
    file_bytes = file_obj.read()
    _save_raw_file(file_bytes, "apple_health", filename)

    upload_id = db.record_upload_start("apple_health", filename)

    parsed = 0
    inserted = 0
    metric_batch: list[dict] = []
    workout_batch: list[dict] = []
    type_counts: dict[str, int] = {}

    def flush():
        nonlocal inserted, metric_batch, workout_batch
        if metric_batch:
            inserted += db.upsert_metrics(metric_batch, upload_id)
            metric_batch = []
        if workout_batch:
            inserted += db.upsert_workouts(workout_batch, upload_id)
            workout_batch = []

    try:
        for item in parse_apple_export(io.BytesIO(file_bytes)):
            parsed += 1
            if isinstance(item, NormalizedRecord):
                type_counts[item.metric_type] = type_counts.get(item.metric_type, 0) + 1
                metric_batch.append(_record_to_row(item))
            elif isinstance(item, NormalizedWorkout):
                type_counts["workout"] = type_counts.get("workout", 0) + 1
                workout_batch.append(_workout_to_row(item))

            if len(metric_batch) >= BATCH_SIZE or len(workout_batch) >= BATCH_SIZE:
                flush()
        flush()

        notes = ", ".join(f"{k}: {v}" for k, v in sorted(type_counts.items()))
        db.record_upload_finish(upload_id, "success", parsed, inserted, notes)
        return {
            "status": "success",
            "parsed": parsed,
            "inserted": inserted,
            "type_counts": type_counts,
            "notes": notes,
        }
    except Exception as exc:
        db.record_upload_finish(upload_id, "failed", parsed, inserted, str(exc))
        raise


def ingest_xiaomi(file_obj: IO[bytes], filename: str) -> dict:
    file_bytes = file_obj.read()
    _save_raw_file(file_bytes, "xiaomi", filename)

    upload_id = db.record_upload_start("xiaomi", filename)

    try:
        records, parse_notes = parse_xiaomi_export(io.BytesIO(file_bytes), filename)
        parsed = len(records)
        inserted = 0
        type_counts: dict[str, int] = {}
        for i in range(0, len(records), BATCH_SIZE):
            batch = records[i : i + BATCH_SIZE]
            for r in batch:
                type_counts[r.metric_type] = type_counts.get(r.metric_type, 0) + 1
            inserted += db.upsert_metrics([_record_to_row(r) for r in batch], upload_id)

        notes = "; ".join(parse_notes) if parse_notes else ", ".join(
            f"{k}: {v}" for k, v in sorted(type_counts.items())
        )
        status = "success" if records else ("partial" if parse_notes else "failed")
        db.record_upload_finish(upload_id, status, parsed, inserted, notes)
        return {
            "status": status,
            "parsed": parsed,
            "inserted": inserted,
            "type_counts": type_counts,
            "notes": notes,
        }
    except Exception as exc:
        db.record_upload_finish(upload_id, "failed", 0, 0, str(exc))
        raise


def ingest_health_auto_export(file_bytes: bytes) -> dict:
    payload_hash = hashlib.sha256(file_bytes).hexdigest()
    upload_id, already_seen, prior_status = db.record_api_ingestion_start(payload_hash)
    if already_seen and prior_status == "success":
        return {
            "status": "duplicate_request",
            "parsed": 0,
            "inserted": 0,
            "duplicates": 0,
            "ignored": 0,
        }

    parsed_count = inserted = ignored = 0
    try:
        payload = json.loads(file_bytes)
        if not isinstance(payload, dict):
            raise ValueError("request body must be a JSON object")
        result = parse_health_auto_export(payload)
        metric_rows = [_record_to_row(item) for item in result.metrics]
        workout_rows = [_workout_to_row(item) for item in result.workouts]
        parsed_count = len(metric_rows) + len(workout_rows)

        for i in range(0, len(metric_rows), BATCH_SIZE):
            inserted += db.upsert_metrics(metric_rows[i : i + BATCH_SIZE], upload_id)
        for i in range(0, len(workout_rows), BATCH_SIZE):
            inserted += db.upsert_workouts(workout_rows[i : i + BATCH_SIZE], upload_id)

        ignored = result.ignored
        duplicates = parsed_count - inserted
        notes = "; ".join(result.notes[:20]) or None
        db.record_upload_finish(
            upload_id,
            "success",
            parsed_count,
            inserted,
            notes,
            records_duplicate=duplicates,
            records_ignored=ignored,
        )
        return {
            "status": "success",
            "parsed": parsed_count,
            "inserted": inserted,
            "duplicates": duplicates,
            "ignored": ignored,
            "notes": result.notes,
        }
    except Exception as exc:
        db.record_upload_finish(
            upload_id,
            "failed",
            parsed_count,
            inserted,
            str(exc),
            records_ignored=ignored,
        )
        raise

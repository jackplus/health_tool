"""Best-effort adapter for 小米运动健康/Zepp personal data exports.

Xiaomi has no publicly documented personal-export schema, so this is
deliberately built as a small registry of independent, swappable per-metric
parsers driven by fuzzy column-name matching rather than one rigid parser
tied to an assumed exact layout. Anything that can't be confidently mapped
is skipped with a logged reason instead of raising -- once a real sample
export is available, only the relevant `_parse_*` function should need
adjusting, not this file's structure.
"""

import io
import json
import zipfile
from typing import IO

import pandas as pd

from parsers.common import NormalizedRecord, parse_datetime, to_float

SOURCE = "xiaomi"

FIELD_ALIASES = {
    "timestamp": ["date", "time", "timestamp", "datetime", "day", "recordtime"],
    "steps": ["steps", "step_count", "stepcount", "step"],
    "heart_rate": ["heart_rate", "heartrate", "hr", "bpm", "value"],
    "weight": ["weight", "weight_kg", "bodyweight", "bodymass"],
    "sleep_start": ["sleep_start", "start", "bedtime", "starttime"],
    "sleep_end": ["sleep_end", "end", "waketime", "endtime"],
    "sleep_duration": ["duration", "sleep_duration", "total_minutes", "totalminutes"],
}

# filename keyword -> which sub-parser to try first
FILENAME_HINTS = {
    "step": "steps",
    "heart": "heart_rate",
    "hr": "heart_rate",
    "sleep": "sleep",
    "weight": "weight",
    "body": "weight",
}


def _find_column(columns, aliases) -> str | None:
    lower_map = {str(c).lower(): c for c in columns}
    for alias in aliases:
        if alias in lower_map:
            return lower_map[alias]
    for c in columns:
        cl = str(c).lower()
        for alias in aliases:
            if alias in cl:
                return c
    return None


def _load_dataframe(f: IO[bytes], name: str) -> pd.DataFrame | None:
    raw = f.read()
    if not raw:
        return None
    name_lower = name.lower()
    try:
        if name_lower.endswith(".json"):
            data = json.loads(raw)
            if isinstance(data, dict):
                # common export shape: {"data": [...]} or similar wrapper
                for key in ("data", "records", "items", "list"):
                    if key in data and isinstance(data[key], list):
                        return pd.json_normalize(data[key])
                return pd.json_normalize([data])
            return pd.json_normalize(data)
        return pd.read_csv(io.BytesIO(raw))
    except Exception:
        return None


def _parse_steps(df: pd.DataFrame, source_name: str) -> tuple[list[NormalizedRecord], str | None]:
    ts_col = _find_column(df.columns, FIELD_ALIASES["timestamp"])
    val_col = _find_column(df.columns, FIELD_ALIASES["steps"])
    if not ts_col or not val_col:
        return [], "steps: no matching timestamp/steps columns found"
    records = []
    for _, row in df.iterrows():
        ts = _safe_parse_dt(row.get(ts_col))
        val = to_float(row.get(val_col))
        if ts is None or val is None:
            continue
        records.append(
            NormalizedRecord(
                source=SOURCE, source_name=source_name, metric_type="steps",
                start_timestamp=ts, end_timestamp=ts, value=val, unit="count",
            )
        )
    return records, None


def _parse_heart_rate(df: pd.DataFrame, source_name: str) -> tuple[list[NormalizedRecord], str | None]:
    ts_col = _find_column(df.columns, FIELD_ALIASES["timestamp"])
    val_col = _find_column(df.columns, FIELD_ALIASES["heart_rate"])
    if not ts_col or not val_col:
        return [], "heart_rate: no matching timestamp/heart-rate columns found"
    records = []
    for _, row in df.iterrows():
        ts = _safe_parse_dt(row.get(ts_col))
        val = to_float(row.get(val_col))
        if ts is None or val is None:
            continue
        records.append(
            NormalizedRecord(
                source=SOURCE, source_name=source_name, metric_type="heart_rate",
                start_timestamp=ts, end_timestamp=ts, value=val, unit="count/min",
            )
        )
    return records, None


def _parse_weight(df: pd.DataFrame, source_name: str) -> tuple[list[NormalizedRecord], str | None]:
    ts_col = _find_column(df.columns, FIELD_ALIASES["timestamp"])
    val_col = _find_column(df.columns, FIELD_ALIASES["weight"])
    if not ts_col or not val_col:
        return [], "weight: no matching timestamp/weight columns found"
    records = []
    for _, row in df.iterrows():
        ts = _safe_parse_dt(row.get(ts_col))
        val = to_float(row.get(val_col))
        if ts is None or val is None:
            continue
        records.append(
            NormalizedRecord(
                source=SOURCE, source_name=source_name, metric_type="weight",
                start_timestamp=ts, end_timestamp=ts, value=val, unit="kg",
            )
        )
    return records, None


def _parse_sleep(df: pd.DataFrame, source_name: str) -> tuple[list[NormalizedRecord], str | None]:
    start_col = _find_column(df.columns, FIELD_ALIASES["sleep_start"])
    end_col = _find_column(df.columns, FIELD_ALIASES["sleep_end"])
    dur_col = _find_column(df.columns, FIELD_ALIASES["sleep_duration"])
    ts_col = _find_column(df.columns, FIELD_ALIASES["timestamp"])

    if not (start_col and end_col) and not (ts_col and dur_col):
        return [], "sleep: no matching start/end or date/duration columns found"

    records = []
    for _, row in df.iterrows():
        if start_col and end_col:
            start = _safe_parse_dt(row.get(start_col))
            end = _safe_parse_dt(row.get(end_col))
            if start is None or end is None:
                continue
            duration_minutes = max((end - start).total_seconds() / 60.0, 0.0)
        else:
            start = _safe_parse_dt(row.get(ts_col))
            duration_minutes = to_float(row.get(dur_col))
            if start is None or duration_minutes is None:
                continue
            end = start
        # Xiaomi exports rarely distinguish sleep stages the way Apple does;
        # best-effort tags the whole interval as "asleep" until a real
        # sample export shows finer-grained stage data to map.
        records.append(
            NormalizedRecord(
                source=SOURCE, source_name=source_name, metric_type="sleep_stage",
                start_timestamp=start, end_timestamp=end, value=duration_minutes,
                unit="min", sub_key="asleep",
            )
        )
    return records, None


def _safe_parse_dt(value):
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    try:
        return parse_datetime(str(value))
    except Exception:
        return None


_PARSERS = {
    "steps": _parse_steps,
    "heart_rate": _parse_heart_rate,
    "weight": _parse_weight,
    "sleep": _parse_sleep,
}


def _guess_metric(filename: str) -> str | None:
    name_lower = filename.lower()
    for keyword, metric in FILENAME_HINTS.items():
        if keyword in name_lower:
            return metric
    return None


def _parse_single_file(f: IO[bytes], name: str, source_name: str) -> tuple[list[NormalizedRecord], str | None]:
    df = _load_dataframe(f, name)
    if df is None or df.empty:
        return [], f"{name}: could not read as CSV/JSON or file was empty"

    guess = _guess_metric(name)
    order = [guess] + [m for m in _PARSERS if m != guess] if guess else list(_PARSERS)

    for metric in order:
        records, note = _PARSERS[metric](df, source_name)
        if records:
            return records, None

    return [], f"{name}: none of the known metric parsers matched its columns"


def parse_xiaomi_export(file_obj: IO[bytes], filename: str) -> tuple[list[NormalizedRecord], list[str]]:
    """Returns (records, notes). Notes describe any files/columns that
    couldn't be confidently parsed -- surfaced to raw_uploads.notes rather
    than raising, since the real export schema is unverified."""
    source_name = "小米运动健康"
    records: list[NormalizedRecord] = []
    notes: list[str] = []

    if filename.lower().endswith(".zip"):
        with zipfile.ZipFile(file_obj) as zf:
            for name in zf.namelist():
                if name.endswith("/"):
                    continue
                with zf.open(name) as f:
                    recs, note = _parse_single_file(f, name, source_name)
                    records.extend(recs)
                    if note:
                        notes.append(note)
    else:
        recs, note = _parse_single_file(file_obj, filename, source_name)
        records.extend(recs)
        if note:
            notes.append(note)

    return records, notes

"""Streaming parser for Apple Health `export.zip` -> `export.xml`.

Apple's export XML can be hundreds of MB for a multi-year history with dense
heart-rate/step records, so this uses `iterparse` and clears each element
right after it's read instead of holding the whole tree in memory. Only a
small allow-list of record types we actually care about is mapped -- Apple's
export contains dozens of obscure HK types we don't need for a personal BI
dashboard.
"""

import xml.etree.ElementTree as ET
import zipfile
from typing import IO, Iterator

from parsers.common import NormalizedRecord, NormalizedWorkout, parse_datetime, to_float

SOURCE = "apple_health"

# HealthKit type identifier -> our normalized metric_type.
QUANTITY_TYPE_MAP = {
    "HKQuantityTypeIdentifierStepCount": "steps",
    "HKQuantityTypeIdentifierDistanceWalkingRunning": "distance",
    "HKQuantityTypeIdentifierHeartRate": "heart_rate",
    "HKQuantityTypeIdentifierRestingHeartRate": "resting_heart_rate",
    "HKQuantityTypeIdentifierWalkingHeartRateAverage": "walking_heart_rate",
    "HKQuantityTypeIdentifierActiveEnergyBurned": "active_energy",
    "HKQuantityTypeIdentifierBodyMass": "weight",
}
CATEGORY_TYPE_MAP = {
    "HKCategoryTypeIdentifierSleepAnalysis": "sleep_stage",
}

_SLEEP_STAGE_PREFIX = "HKCategoryValueSleepAnalysis"
_SLEEP_STAGE_ALIASES = {
    "InBed": "in_bed",
    "Asleep": "asleep",
    "AsleepUnspecified": "asleep",
    "Awake": "awake",
    "AsleepCore": "core",
    "AsleepDeep": "deep",
    "AsleepREM": "rem",
}

# Workout total fields moved from Workout attributes (pre-iOS 17) to nested
# <WorkoutStatistics type="..."> children (iOS 17+). Map the HK type used in
# the nested form to the attribute name used in the old form.
_WORKOUT_STAT_TYPES = {
    "HKQuantityTypeIdentifierDistanceWalkingRunning": "distance",
    "HKQuantityTypeIdentifierActiveEnergyBurned": "energy",
}


def _find_export_xml(zf: zipfile.ZipFile) -> str:
    candidates = [
        n for n in zf.namelist() if n.endswith("export.xml") and "export_cda" not in n
    ]
    if not candidates:
        raise ValueError("export.zip does not contain an export.xml file")
    # Prefer the shortest matching path (the top-level export.xml, not a
    # nested duplicate if one somehow exists).
    return min(candidates, key=len)


def _normalize_sleep_stage(value: str | None) -> str:
    if not value:
        return "unknown"
    stage = value[len(_SLEEP_STAGE_PREFIX):] if value.startswith(_SLEEP_STAGE_PREFIX) else value
    return _SLEEP_STAGE_ALIASES.get(stage, stage.lower() or "unknown")


def _parse_record(elem: ET.Element) -> NormalizedRecord | None:
    hk_type = elem.get("type")
    start = elem.get("startDate")
    end = elem.get("endDate")
    if not hk_type or not start or not end:
        return None

    source_name = elem.get("sourceName", "")
    start_ts = parse_datetime(start)
    end_ts = parse_datetime(end)

    if hk_type in QUANTITY_TYPE_MAP:
        value = to_float(elem.get("value"))
        if value is None:
            return None
        return NormalizedRecord(
            source=SOURCE,
            source_name=source_name,
            metric_type=QUANTITY_TYPE_MAP[hk_type],
            start_timestamp=start_ts,
            end_timestamp=end_ts,
            value=value,
            unit=elem.get("unit", ""),
            raw={"type": hk_type, "device": elem.get("device", "")},
        )

    if hk_type in CATEGORY_TYPE_MAP:
        stage = _normalize_sleep_stage(elem.get("value"))
        duration_minutes = max((end_ts - start_ts).total_seconds() / 60.0, 0.0)
        return NormalizedRecord(
            source=SOURCE,
            source_name=source_name,
            metric_type=CATEGORY_TYPE_MAP[hk_type],
            start_timestamp=start_ts,
            end_timestamp=end_ts,
            value=duration_minutes,
            unit="min",
            sub_key=stage,
            raw={"type": hk_type, "value": elem.get("value", "")},
        )

    return None


def _parse_workout(elem: ET.Element) -> NormalizedWorkout | None:
    start = elem.get("startDate")
    end = elem.get("endDate")
    if not start or not end:
        return None

    start_ts = parse_datetime(start)
    end_ts = parse_datetime(end)

    duration_minutes = to_float(elem.get("duration"))
    if duration_minutes is None:
        duration_minutes = max((end_ts - start_ts).total_seconds() / 60.0, 0.0)

    distance = to_float(elem.get("totalDistance"))
    distance_unit = elem.get("totalDistanceUnit")
    energy = to_float(elem.get("totalEnergyBurned"))
    energy_unit = elem.get("totalEnergyBurnedUnit")

    # iOS 17+ export shape: totals live in nested WorkoutStatistics children
    # instead of attributes directly on <Workout>.
    if distance is None or energy is None:
        for stat in elem.findall("WorkoutStatistics"):
            stat_type = stat.get("type")
            field = _WORKOUT_STAT_TYPES.get(stat_type)
            if field == "distance" and distance is None:
                distance = to_float(stat.get("sum"))
                distance_unit = stat.get("unit")
            elif field == "energy" and energy is None:
                energy = to_float(stat.get("sum"))
                energy_unit = stat.get("unit")

    return NormalizedWorkout(
        source=SOURCE,
        source_name=elem.get("sourceName", ""),
        workout_type=elem.get("workoutActivityType", "unknown"),
        start_timestamp=start_ts,
        end_timestamp=end_ts,
        duration_minutes=duration_minutes,
        distance=distance,
        distance_unit=distance_unit,
        energy_burned=energy,
        energy_unit=energy_unit,
        raw={"device": elem.get("device", "")},
    )


def parse_apple_export(
    file_obj: IO[bytes],
) -> Iterator[NormalizedRecord | NormalizedWorkout]:
    """Yields NormalizedRecord/NormalizedWorkout objects one at a time.

    Caller is responsible for batching inserts -- this function never holds
    more than one parsed record in memory at a time beyond what iterparse
    itself retains.
    """
    with zipfile.ZipFile(file_obj) as zf:
        xml_name = _find_export_xml(zf)
        with zf.open(xml_name) as xml_file:
            for event, elem in ET.iterparse(xml_file, events=("end",)):
                # Only clear elements we've fully handled. Workout's child
                # WorkoutStatistics elements fire their own "end" event
                # first (iterparse fires "end" bottom-up) -- clearing them
                # unconditionally here would wipe their attributes before
                # _parse_workout() gets to read totalDistance/totalEnergy
                # off them for the iOS 17+ nested-stats export shape.
                if elem.tag == "Record":
                    parsed = _parse_record(elem)
                    if parsed is not None:
                        yield parsed
                    elem.clear()
                elif elem.tag == "Workout":
                    parsed = _parse_workout(elem)
                    if parsed is not None:
                        yield parsed
                    elem.clear()

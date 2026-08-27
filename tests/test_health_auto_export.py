import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))

from parsers.health_auto_export import parse_health_auto_export


class HealthAutoExportParserTests(unittest.TestCase):
    def test_parses_core_metrics_sleep_and_workout(self):
        payload = {
            "data": {
                "metrics": [
                    {
                        "name": "step_count",
                        "units": "count",
                        "data": [
                            {
                                "qty": 8123,
                                "date": "2026-08-20T00:00:00+08:00",
                                "source": "iPhone",
                            }
                        ],
                    },
                    {
                        "name": "heart_rate_variability",
                        "units": "ms",
                        "data": [
                            {
                                "qty": 48,
                                "date": "2026-08-20T07:00:00+08:00",
                                "source": "Apple Watch",
                            }
                        ],
                    },
                    {
                        "name": "weight_body_mass",
                        "units": "lb",
                        "data": [
                            {
                                "qty": 176.37,
                                "date": "2026-08-20",
                                "source": "Scale",
                            }
                        ],
                    },
                    {
                        "name": "sleep_analysis",
                        "units": "hr",
                        "data": [
                            {
                                "date": "2026-08-20T00:00:00+08:00",
                                "core": 4.5,
                                "deep": 1.2,
                                "rem": 1.4,
                                "awake": 0.2,
                                "source": "Apple Watch",
                            }
                        ],
                    },
                ],
                "workouts": [
                    {
                        "id": "workout-1",
                        "name": "Running",
                        "start": "2026-08-20T18:00:00+08:00",
                        "end": "2026-08-20T18:30:00+08:00",
                        "duration": 1800,
                        "distance": {"qty": 5, "units": "km"},
                        "activeEnergyBurned": {"qty": 320, "units": "kcal"},
                    }
                ],
            }
        }

        result = parse_health_auto_export(payload)

        self.assertEqual(result.ignored, 0)
        self.assertEqual(len(result.metrics), 7)
        self.assertEqual(
            {m.metric_type for m in result.metrics}, {"steps", "hrv", "weight", "sleep_stage"}
        )
        deep = next(m for m in result.metrics if m.sub_key == "deep")
        self.assertAlmostEqual(deep.value, 72)
        weight = next(m for m in result.metrics if m.metric_type == "weight")
        self.assertAlmostEqual(weight.value, 80, places=1)
        self.assertEqual(weight.unit, "kg")
        self.assertIsNotNone(weight.start_timestamp.tzinfo)
        self.assertEqual(result.workouts[0].external_id, "workout-1")
        self.assertAlmostEqual(result.workouts[0].duration_minutes, 30)

    def test_ignores_unknown_metric_without_failing_batch(self):
        result = parse_health_auto_export(
            {"data": {"metrics": [{"name": "unknown", "data": []}]}}
        )
        self.assertEqual(result.ignored, 1)
        self.assertEqual(result.metrics, [])
        self.assertIn("unsupported metric", result.notes[0])

    def test_rejects_invalid_envelope(self):
        with self.assertRaisesRegex(ValueError, "payload.data"):
            parse_health_auto_export({"data": []})


if __name__ == "__main__":
    unittest.main()

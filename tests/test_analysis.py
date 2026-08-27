import sys
from datetime import date, timedelta
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))

from analysis import build_report


def baseline_series(period_end: date) -> dict:
    start = period_end - timedelta(days=28)
    return {
        start + timedelta(days=i): {
            "sleep_minutes": 450,
            "resting_heart_rate": 60,
            "hrv": 50,
            "steps": 8000,
            "active_energy": 500,
            "workout_minutes": 30,
        }
        for i in range(29)
    }


class AnalysisRuleTests(unittest.TestCase):
    def test_requires_fourteen_baseline_days(self):
        end = date(2026, 8, 20)
        report = build_report({end: {"steps": 5000}}, "daily", end)
        self.assertEqual(report["status"], "insufficient_data")
        self.assertEqual(report["findings"], [])

    def test_detects_recovery_changes_against_personal_baseline(self):
        end = date(2026, 8, 20)
        series = baseline_series(end)
        series[end] = {
            "sleep_minutes": 360,
            "resting_heart_rate": 68,
            "hrv": 38,
            "steps": 8000,
            "active_energy": 500,
            "workout_minutes": 30,
        }

        report = build_report(series, "daily", end)

        metrics = {finding["metric"] for finding in report["findings"]}
        self.assertEqual(report["status"], "attention")
        self.assertTrue({"sleep_minutes", "resting_heart_rate", "hrv"}.issubset(metrics))
        self.assertEqual(report["recommendations"][0]["priority"], "high")

    def test_stable_report_has_no_recommendations(self):
        end = date(2026, 8, 20)
        report = build_report(baseline_series(end), "daily", end)
        self.assertEqual(report["status"], "stable")
        self.assertEqual(report["recommendations"], [])


if __name__ == "__main__":
    unittest.main()

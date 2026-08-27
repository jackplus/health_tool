import sys
from pathlib import Path
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))

from fastapi.testclient import TestClient
import api


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(api.app)

    def test_rejects_invalid_api_key(self):
        with patch.object(api, "HEALTH_API_KEY", "expected"):
            response = self.client.post(
                "/api/v1/health-auto-export",
                headers={"api-key": "wrong"},
                json={"data": {}},
            )
        self.assertEqual(response.status_code, 401)

    def test_accepts_valid_request(self):
        result = {"status": "success", "parsed": 1, "inserted": 1, "duplicates": 0, "ignored": 0}
        with (
            patch.object(api, "HEALTH_API_KEY", "expected"),
            patch.object(api, "ingest_health_auto_export", return_value=result),
        ):
            response = self.client.post(
                "/api/v1/health-auto-export",
                headers={"api-key": "expected"},
                json={"data": {}},
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), result)


if __name__ == "__main__":
    unittest.main()

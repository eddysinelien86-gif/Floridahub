import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from database import fetch_dashboard_payload, init_db


class MarketHubServerTests(unittest.TestCase):
    def setUp(self) -> None:
        init_db()

    def test_dashboard_payload_contains_expected_sections(self) -> None:
        payload = fetch_dashboard_payload()
        self.assertIn("profile", payload)
        self.assertIn("metrics", payload)
        self.assertIn("reviews", payload)
        self.assertIn("customers", payload)
        self.assertIn("cards", payload)
        self.assertGreaterEqual(len(payload["cards"]), 8)


if __name__ == "__main__":
    unittest.main()

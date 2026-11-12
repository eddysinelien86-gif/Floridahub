import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import tempfile

import database
from database import add_lead, fetch_dashboard_payload, fetch_leadcount, init_db


class MarketHubServerTests(unittest.TestCase):
    def setUp(self) -> None:
        # Use a throwaway database so tests never touch real saved leads.
        self._tmp = tempfile.TemporaryDirectory()
        self._real_path = database.DB_PATH
        database.DB_PATH = Path(self._tmp.name) / "test.db"
        init_db()

    def tearDown(self) -> None:
        database.DB_PATH = self._real_path
        self._tmp.cleanup()

    def test_starts_with_no_demo_leads_or_reviews(self) -> None:
        payload = fetch_dashboard_payload()
        self.assertEqual(payload["customers"], [])
        self.assertEqual(payload["reviews"], [])
        self.assertEqual(payload["leadboard"]["hot_leads"], 0)

    def test_real_leads_survive_a_restart_and_demo_rows_are_removed(self) -> None:
        conn = database.get_connection()
        conn.execute(
            "INSERT INTO customers (name, company, contact, status) VALUES (?, ?, ?, ?)",
            ("Ava Brooks", "Attic insulation", "ava@email.com", "Hot lead"),
        )
        conn.commit()
        conn.close()
        self.assertEqual(add_lead("Pat Real", "555-0100", "Attic"), 2)

        init_db()  # what happens every time the backend restarts

        payload = fetch_dashboard_payload()
        self.assertEqual([c["name"] for c in payload["customers"]], ["Pat Real"])
        self.assertEqual(fetch_leadcount()["hot_leads"], 1)
        tiles = {m["label"]: m["value"] for m in payload["metrics"]}
        self.assertEqual(tiles["Hot leads"], "1")
        self.assertEqual(tiles["Website form"], "1")
        self.assertEqual(tiles["Facebook leads"], "—")

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

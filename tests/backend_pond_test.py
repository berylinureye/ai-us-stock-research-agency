import tempfile
import unittest
from pathlib import Path

import backend.server as server


class FailingRequests:
    @staticmethod
    def get(*_args, **_kwargs):
        raise RuntimeError("price source unavailable")


class BackendPondTest(unittest.TestCase):
    def setUp(self):
        self.original_pond_dir = server.POND_DIR
        self.original_requests = server.requests
        self.tempdir = tempfile.TemporaryDirectory()
        server.POND_DIR = Path(self.tempdir.name) / "conclusion-pool"

    def tearDown(self):
        server.POND_DIR = self.original_pond_dir
        server.requests = self.original_requests
        self.tempdir.cleanup()

    def test_select_candidate_is_idempotent_and_visible_in_pond(self):
        candidate = {
            "runId": "run-1",
            "decisionDate": "2026-06-26",
            "thesisId": "NVDA-1",
            "rank": 1,
            "ticker": "NVDA",
            "company": "NVIDIA",
            "actionRating": "Research Buy",
            "confidence": 82,
            "estimatedUpsideLowPct": 2,
            "estimatedUpsideBasePct": 4,
            "estimatedUpsideHighPct": 6,
            "whyNow": "AI demand thesis",
        }

        server.select_pond_candidate({"candidate": candidate})
        payload = server.select_pond_candidate({"candidate": candidate})

        self.assertEqual(payload["summary"]["openCount"], 1)
        self.assertEqual(len(payload["openItems"]), 1)
        self.assertEqual(payload["openItems"][0]["ticker"], "NVDA")
        self.assertEqual(payload["openItems"][0]["status"], "open")

    def test_refresh_marks_price_data_failed_without_inventing_prices(self):
        server.select_pond_candidate(
            {
                "candidate": {
                    "runId": "run-1",
                    "decisionDate": "2026-06-26",
                    "thesisId": "NVDA-1",
                    "ticker": "NVDA",
                }
            }
        )
        server.requests = FailingRequests

        payload = server.refresh_pond_prices()

        self.assertEqual(payload["failed"], 1)
        self.assertEqual(payload["openItems"][0]["status"], "price_data_failed")
        self.assertEqual(payload["openItems"][0]["reviewExitPrice"], None)


if __name__ == "__main__":
    unittest.main()

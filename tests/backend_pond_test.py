import tempfile
import unittest
from pathlib import Path

from backend.app.clients import market_data
from backend.app.repositories import pond


class FailingRequests:
    @staticmethod
    def get(*_args, **_kwargs):
        raise RuntimeError("price source unavailable")


class BackendPondTest(unittest.TestCase):
    def setUp(self):
        self.original_pond_dir = pond.POND_DIR
        self.original_requests = market_data.requests
        self.tempdir = tempfile.TemporaryDirectory()
        pond.POND_DIR = Path(self.tempdir.name) / "conclusion-pool"

    def tearDown(self):
        pond.POND_DIR = self.original_pond_dir
        market_data.requests = self.original_requests
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

        pond.select_pond_candidate({"candidate": candidate})
        payload = pond.select_pond_candidate({"candidate": candidate})

        self.assertEqual(payload["summary"]["openCount"], 1)
        self.assertEqual(len(payload["openItems"]), 1)
        self.assertEqual(payload["openItems"][0]["ticker"], "NVDA")
        self.assertEqual(payload["openItems"][0]["status"], "open")

    def test_refresh_marks_price_data_failed_without_inventing_prices(self):
        pond.select_pond_candidate(
            {
                "candidate": {
                    "runId": "run-1",
                    "decisionDate": "2026-06-26",
                    "thesisId": "NVDA-1",
                    "ticker": "NVDA",
                }
            }
        )
        market_data.requests = FailingRequests

        payload = pond.refresh_pond_prices()

        self.assertEqual(payload["failed"], 1)
        self.assertEqual(payload["openItems"][0]["status"], "price_data_failed")
        self.assertEqual(payload["openItems"][0]["reviewExitPrice"], None)


if __name__ == "__main__":
    unittest.main()

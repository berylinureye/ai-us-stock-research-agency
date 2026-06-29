import json
import tempfile
import unittest
from unittest import mock
from pathlib import Path

from fastapi.testclient import TestClient


ROOT = Path(__file__).resolve().parents[1]


class BackendFastApiStructureTest(unittest.TestCase):
    def test_backend_python_files_stay_under_2000_lines(self):
        oversized = []
        for path in (ROOT / "backend").rglob("*.py"):
            if "__pycache__" in path.parts:
                continue
            line_count = len(path.read_text(encoding="utf-8").splitlines())
            if line_count >= 2000:
                oversized.append(f"{path.relative_to(ROOT)}:{line_count}")

        self.assertEqual(oversized, [])

    def test_fastapi_health_and_mock_weekly_brief(self):
        from backend.app.main import create_app

        with tempfile.TemporaryDirectory() as tempdir:
            with mock.patch.dict(
                "os.environ",
                {"WEEKLY_BRIEF_MOCK": "1", "REPORT_HISTORY_DIR": tempdir},
                clear=False,
            ):
                client = TestClient(create_app())

                health = client.get("/api/health")
                self.assertEqual(health.status_code, 200)
                self.assertEqual(health.json()["mode"], "mock")

                response = client.post(
                    "/api/weekly-brief",
                    json={"prompt": "fastapi smoke"},
                    headers={"Accept": "application/json"},
                )
                self.assertEqual(response.status_code, 200)
                payload = response.json()
                self.assertRegex(payload["reportMarkdown"], r"^# 老板决策页")
                self.assertIn("agentTrace", payload)
                self.assertGreaterEqual(len(payload["agentTrace"]), 1)
                self.assertIn("historyId", payload["runMetadata"])

                reports = client.get("/api/reports")
                self.assertEqual(reports.status_code, 200)
                self.assertEqual(reports.json()["summary"]["count"], 1)

    def test_fastapi_sse_weekly_brief_ends_with_done(self):
        from backend.app.main import create_app

        with tempfile.TemporaryDirectory() as tempdir:
            with mock.patch.dict(
                "os.environ",
                {"WEEKLY_BRIEF_MOCK": "1", "REPORT_HISTORY_DIR": tempdir},
                clear=False,
            ):
                client = TestClient(create_app())

                with client.stream(
                    "POST",
                    "/api/weekly-brief",
                    json={"prompt": "sse smoke"},
                    headers={"Accept": "text/event-stream"},
                ) as response:
                    self.assertEqual(response.status_code, 200)
                    body = "".join(response.iter_text())

                self.assertIn("data: [DONE]", body)
                events = [
                    json.loads(line.removeprefix("data: ").strip())
                    for line in body.splitlines()
                    if line.startswith("data: {")
                ]
                self.assertTrue(any(event.get("event") == "run_done" for event in events))

    def test_fastapi_health_redacts_configured_urls(self):
        from backend.app.main import create_app

        with mock.patch.dict(
            "os.environ",
            {
                "WEEKLY_BRIEF_MOCK": "0",
                "OPENAI_BASE_URL": "https://user:secret@example.test/v1?api_key=abc&region=us",
                "WEEKLY_BRIEF_UPSTREAM_URL": "https://token@example.test/api?token=secret&mode=proxy",
            },
            clear=False,
        ):
            client = TestClient(create_app())

            payload = client.get("/api/health").json()

        self.assertEqual(payload["baseUrl"], "https://***@example.test/v1?api_key=***&region=us")
        self.assertEqual(payload["upstreamUrl"], "https://***@example.test/api?token=***&mode=proxy")

    def test_fastapi_proxy_mode_uses_json_when_accept_includes_sse(self):
        from backend.app.main import create_app
        from backend.app.services import weekly_brief as weekly_service
        upstream_payload = {
            "title": "Proxy Smoke",
            "summaryMarkdown": "# 老板决策页：Proxy Smoke\n\n摘要",
            "reportMarkdown": "# 老板决策页：Proxy Smoke\n\n完整报告",
            "evidenceMarkdown": "# 证据包\n\nproxy",
        }

        with tempfile.TemporaryDirectory() as tempdir:
            with mock.patch.dict(
                "os.environ",
                {
                    "WEEKLY_BRIEF_MOCK": "0",
                    "WEEKLY_BRIEF_UPSTREAM_URL": "https://proxy.example.test/weekly",
                    "REPORT_HISTORY_DIR": tempdir,
                },
                clear=False,
            ):
                with mock.patch.object(weekly_service, "call_upstream", return_value=upstream_payload) as upstream:
                    client = TestClient(create_app())
                    response = client.post(
                        "/api/weekly-brief",
                        json={"prompt": "proxy smoke"},
                        headers={"Accept": "application/json, text/event-stream, */*"},
                    )

        self.assertEqual(response.status_code, 200)
        self.assertIn("application/json", response.headers["content-type"])
        upstream.assert_called_once()
        self.assertEqual(response.json()["agentTrace"], [])

    def test_fastapi_weekly_json_error_shape_and_history(self):
        from backend.app.main import create_app
        from backend.app.services import weekly_brief as weekly_service

        with tempfile.TemporaryDirectory() as tempdir:
            with mock.patch.dict(
                "os.environ",
                {
                    "WEEKLY_BRIEF_MOCK": "0",
                    "WEEKLY_BRIEF_UPSTREAM_URL": "",
                    "REPORT_HISTORY_DIR": tempdir,
                },
                clear=False,
            ):
                with mock.patch.object(weekly_service, "call_openai", side_effect=RuntimeError("boom")):
                    client = TestClient(create_app())
                    response = client.post(
                        "/api/weekly-brief",
                        json={"prompt": "error smoke"},
                        headers={"Accept": "application/json"},
                    )
                    reports = client.get("/api/reports")

        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.json(), {"ok": False, "error": "boom"})
        self.assertEqual(reports.json()["summary"]["count"], 1)


if __name__ == "__main__":
    unittest.main()

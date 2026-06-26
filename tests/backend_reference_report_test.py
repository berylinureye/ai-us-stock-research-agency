import json
import os
import unittest

import backend.server as server


class OkResponse:
    status_code = 200
    headers = {"content-type": "application/json"}

    def json(self):
        index = len(RecordingRequests.calls)
        if index == 1:
            content = "# Intent Route Plan\n\n用户请求已进入 agent：传统行业 / 消费品行业。"
        else:
            content = "# 老板决策页：传统行业与消费品行业研究\n\n本次响应用户输入，不复用旧 AI 周报。"
        return {
            "choices": [
                {
                    "message": {
                        "content": content,
                    }
                }
            ]
        }

    def raise_for_status(self):
        return None


class UnauthorizedResponse:
    status_code = 401
    headers = {"content-type": "application/json"}
    text = '{"error":"unauthorized"}'

    def raise_for_status(self):
        raise RuntimeError("401 Client Error: Unauthorized")


class RecordingRequests:
    calls = []
    response = OkResponse()

    @classmethod
    def post(cls, url, **kwargs):
        cls.calls.append({"url": url, **kwargs})
        return cls.response


class BackendReferenceReportTest(unittest.TestCase):
    def setUp(self):
        self.original_requests = server.requests
        self.original_env = os.environ.copy()
        self.original_workflow = server.AGENT_WORKFLOW
        RecordingRequests.calls = []
        RecordingRequests.response = OkResponse()
        server.requests = RecordingRequests
        os.environ["OPENAI_API_KEY"] = "test-key-good"
        os.environ["OPENAI_BASE_URL"] = "https://api.viviai.cc/v1"
        os.environ["OPENAI_MODEL"] = "gpt-5.5"
        server.AGENT_WORKFLOW = [
            ("intent_router", "Intent Router", "agents/08-intent-router.md"),
            ("final_narrative", "Final Narrative", "agents/01-ai-trend-narrative-analyst.md"),
        ]

    def tearDown(self):
        server.requests = self.original_requests
        server.AGENT_WORKFLOW = self.original_workflow
        os.environ.clear()
        os.environ.update(self.original_env)

    def test_call_openai_runs_agent_workflow_with_user_prompt(self):
        payload = server.call_openai({"prompt": "搜索传统行业，消费品行业"})

        self.assertEqual(len(RecordingRequests.calls), 2)
        for call in RecordingRequests.calls:
            self.assertEqual(call["url"], "https://api.viviai.cc/v1/chat/completions")
            self.assertEqual(call["headers"]["Authorization"], "Bearer test-key-good")
            self.assertEqual(call["json"]["model"], "gpt-5.5")

        request_text = "\n".join(
            message["content"]
            for call in RecordingRequests.calls
            for message in call["json"]["messages"]
        )
        self.assertIn("搜索传统行业，消费品行业", request_text)
        self.assertNotIn("reports/*stock-discovery*.md", request_text)

        self.assertIn("传统行业与消费品行业", payload["title"])
        self.assertIn("传统行业与消费品行业", payload["summaryMarkdown"])
        self.assertNotIn("AVGO / Custom inference silicon", payload["reportMarkdown"])
        self.assertIn("Agent Run Audit", payload["reportMarkdown"])
        self.assertIn("本次 Agent 原始过程", payload["reportMarkdown"])
        self.assertEqual(payload["runMetadata"]["source"], "live_agent_workflow")
        self.assertIn("agentTrace", payload)
        self.assertEqual(len(payload["agentTrace"]), 2)
        self.assertEqual(payload["agentTrace"][0]["agent"], "Intent Router")
        self.assertIn("thinking", payload["agentTrace"][0])
        self.assertIn("toolPlan", payload["agentTrace"][0])
        self.assertIn("Evidence Index", payload["evidenceMarkdown"])
        self.assertIn("Data Node Status", payload["evidenceMarkdown"])
        self.assertIn("Historical Reports Cache", payload["evidenceMarkdown"])

    def test_gateway_auth_failure_does_not_return_cached_report(self):
        RecordingRequests.response = UnauthorizedResponse()

        with self.assertRaisesRegex(RuntimeError, "模型网关鉴权失败"):
            server.call_openai({"prompt": "搜索传统行业，消费品行业"})


if __name__ == "__main__":
    unittest.main()

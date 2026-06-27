import json
import os
import tempfile
import unittest
from pathlib import Path

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


class QuotaResponse:
    status_code = 429
    headers = {"content-type": "application/json"}
    text = '{"error":{"message":"You exceeded your current quota","code":"insufficient_quota"}}'

    def raise_for_status(self):
        raise RuntimeError("429 Client Error: Too Many Requests")


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
        self.original_run_agent_section = server.run_agent_section
        self.original_report_history_dir = server.REPORT_HISTORY_DIR
        RecordingRequests.calls = []
        RecordingRequests.response = OkResponse()
        server.requests = RecordingRequests
        os.environ["OPENAI_API_KEY"] = "test-key-good"
        os.environ["OPENAI_BASE_URL"] = "https://api.viviai.cc/v1"
        os.environ["OPENAI_MODEL"] = "gpt-5.5"
        os.environ["WEEKLY_BRIEF_PREFLIGHT"] = "0"
        server.AGENT_WORKFLOW = [
            ("intent_router", "Intent Router", "agents/08-intent-router.md"),
            ("final_narrative", "Final Narrative", "agents/01-ai-trend-narrative-analyst.md"),
        ]

    def tearDown(self):
        server.requests = self.original_requests
        server.AGENT_WORKFLOW = self.original_workflow
        server.run_agent_section = self.original_run_agent_section
        server.REPORT_HISTORY_DIR = self.original_report_history_dir
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

    def test_call_openai_uses_default_intent_for_empty_prompt(self):
        payload = server.call_openai({})

        self.assertEqual(len(RecordingRequests.calls), 2)
        request_text = "\n".join(
            message["content"]
            for call in RecordingRequests.calls
            for message in call["json"]["messages"]
        )
        self.assertIn(server.DEFAULT_RESEARCH_INTENT, request_text)
        self.assertEqual(payload["runMetadata"]["userPrompt"], server.DEFAULT_RESEARCH_INTENT)
        self.assertEqual(server.prompt_label(server.DEFAULT_RESEARCH_INTENT), "美股全市场机会扫描")

    def test_section_status_distinguishes_agent_status_from_data_node_failures(self):
        self.assertEqual(
            server.infer_section_status("## Section 状态\n- 状态：complete\n- 外部数据节点 failed。"),
            "complete",
        )
        self.assertEqual(
            server.infer_section_status("**Section 状态：partial**\n新闻节点 failed，行情未接入。"),
            "partial",
        )
        self.assertEqual(
            server.infer_section_status("# 研究未完成\n\n后端运行失败：boom"),
            "failed",
        )

    def test_gateway_auth_failure_does_not_return_cached_report(self):
        RecordingRequests.response = UnauthorizedResponse()

        with self.assertRaisesRegex(RuntimeError, "模型网关鉴权失败"):
            server.chat_completion(
                api_key="test-key-good",
                base_url="https://api.viviai.cc/v1",
                model="gpt-5.5",
                messages=[{"role": "user", "content": "pong"}],
            )

    def test_gateway_quota_failure_is_specific(self):
        RecordingRequests.response = QuotaResponse()

        with self.assertRaisesRegex(RuntimeError, "模型网关额度不足"):
            server.chat_completion(
                api_key="test-key-good",
                base_url="https://api.openai.com/v1",
                model="gpt-5.5",
                messages=[{"role": "user", "content": "pong"}],
            )

    def test_agent_section_failure_continues_workflow(self):
        events = []
        server.AGENT_WORKFLOW = [
            ("intent_router", "Intent Router", "agents/08-intent-router.md"),
            ("information_sentiment", "AI 信息与舆情", "agents/02-ai-information-sentiment-analyst.md"),
            ("final_narrative", "Final Narrative", "agents/01-ai-trend-narrative-analyst.md"),
        ]

        def fake_run_agent_section(**kwargs):
            section_name = kwargs["section_name"]
            if section_name == "AI 信息与舆情":
                raise RuntimeError("read timeout=120")
            return f"# {section_name}\n\n## Agent 公开思考摘要\n{section_name} 已运行。\n\n## Section 状态\n状态：complete"

        server.run_agent_section = fake_run_agent_section

        payload = server.run_agent_workflow(
            api_key="test-key-good",
            base_url="https://api.viviai.cc/v1",
            model="gpt-5.5",
            user_prompt="空输入默认测试",
            on_event=events.append,
        )

        self.assertIn("AI 信息与舆情", payload["runMetadata"]["agents"])
        self.assertIn("后端运行失败：read timeout=120", payload["reportMarkdown"])
        done_events = [event for event in events if event.get("event") == "agent_done"]
        self.assertEqual([event["agent"] for event in done_events], ["Intent Router", "AI 信息与舆情", "Final Narrative"])
        failed_trace = next(event["thinkingTrace"] for event in done_events if event["agent"] == "AI 信息与舆情")
        self.assertEqual(failed_trace["status"], "failed")

    def test_empty_discovery_output_is_repaired_so_every_agent_has_output(self):
        events = []
        server.AGENT_WORKFLOW = [
            ("intent_router", "Intent Router", "agents/08-intent-router.md"),
            ("stock_discovery", "Stock Discovery", "agents/00-stock-discovery-analyst.md"),
            ("information_sentiment", "AI 信息与舆情", "agents/02-ai-information-sentiment-analyst.md"),
            ("fundamental", "Fundamental", "agents/03-fundamental-analyst.md"),
            ("technical", "Technical", "agents/04-technical-analyst.md"),
            ("reflection", "Reflection", "agents/05-reflection-judge.md"),
            ("final_narrative", "Final Narrative", "agents/01-ai-trend-narrative-analyst.md"),
            ("paper_attribution", "Paper Attribution", "agents/07-paper-portfolio-attribution-agent.md"),
        ]

        def fake_run_agent_section(**kwargs):
            section_name = kwargs["section_name"]
            if section_name == "Stock Discovery":
                return """
# Stock Discovery Section

## Agent 公开思考摘要
- 给 AI Information & Sentiment：当前无 ticker 可验证；请先等待 Stock Discovery 补充真实候选，或接入新闻、舆情、GitHub、YouTube/播客、行业事件数据后补跑。
- 给 Fundamental：当前无候选可做财务验证；需要财报、SEC filings、consensus、估值、收入分部、现金流和指引数据。
- 给 Technical：当前无候选可做图表验证；需要价格、成交量、相对强弱、行业 ETF、突破/回撤和波动率数据。

## 当前判断
当前判断：本次 Stock Discovery 只能完成“扫描框架、数据节点状态、候选准入规则和下游验证路线”，不能输出 active research candidates。

## Section 状态
状态：partial
""".strip()
            return f"""
# {section_name} Section

## Agent 公开思考摘要
当前无候选可验证，等待上游 Stock Discovery 补充 ticker。

## 当前判断
没有上游股票池，因此本 section 暂无输出。

## Section 状态
状态：partial
""".strip()

        server.run_agent_section = fake_run_agent_section

        payload = server.run_agent_workflow(
            api_key="test-key-good",
            base_url="https://api.viviai.cc/v1",
            model="gpt-5.5",
            user_prompt="搜索传统行业，消费品行业",
            on_event=events.append,
        )

        expected_agents = [
            "Intent Router",
            "Stock Discovery",
            "AI 信息与舆情",
            "Fundamental",
            "Technical",
            "Reflection",
            "Final Narrative",
            "Paper Attribution",
        ]
        self.assertEqual([trace["agent"] for trace in payload["agentTrace"]], expected_agents)
        forbidden_patterns = [
            "当前无 ticker",
            "请先等待",
            "当前无候选",
            "等待上游",
            "不能输出 active research candidates",
            "暂无输出",
        ]
        visible_trace_text = json.dumps(payload["agentTrace"], ensure_ascii=False)
        report_text = payload["reportMarkdown"]
        for pattern in forbidden_patterns:
            self.assertNotIn(pattern, visible_trace_text)
            self.assertNotIn(pattern, report_text)
        for trace in payload["agentTrace"]:
            self.assertTrue(trace["findings"], f"{trace['agent']} should expose non-empty findings")
            self.assertTrue(trace["judgment"], f"{trace['agent']} should expose a non-empty judgment")
            self.assertTrue(trace["nextStep"], f"{trace['agent']} should expose a non-empty next step")
        self.assertIn("fallback_seed_universe", report_text)
        self.assertIn("WMT", report_text)
        self.assertIn("PG", report_text)

    def test_report_history_persists_each_report_output_for_review(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            server.REPORT_HISTORY_DIR = Path(temp_dir)
            first_payload = {
                "title": "老板决策页：第一次扫描",
                "summaryMarkdown": "# 老板决策页：第一次扫描\n\n摘要 A",
                "reportMarkdown": "# 老板决策页：第一次扫描\n\n完整 A",
                "evidenceMarkdown": "# 证据包\n\nA",
                "runMetadata": {"runId": "same-run-id", "userPrompt": "扫描 A"},
            }
            second_payload = {
                "title": "老板决策页：第二次扫描",
                "summaryMarkdown": "# 老板决策页：第二次扫描\n\n摘要 B",
                "reportMarkdown": "# 老板决策页：第二次扫描\n\n完整 B",
                "evidenceMarkdown": "# 证据包\n\nB",
                "runMetadata": {"runId": "same-run-id", "userPrompt": "扫描 B"},
            }

            first_record = server.save_report_history(first_payload, {"prompt": "扫描 A"}, source="test")
            second_record = server.save_report_history(second_payload, {"prompt": "扫描 B"}, source="test")
            history = server.report_history_payload()

            self.assertNotEqual(first_record["id"], second_record["id"])
            self.assertEqual(history["summary"]["count"], 2)
            self.assertEqual([item["title"] for item in history["items"]], ["老板决策页：第二次扫描", "老板决策页：第一次扫描"])

            detail = server.report_history_detail(first_record["id"])
            self.assertEqual(detail["payload"]["reportMarkdown"], "# 老板决策页：第一次扫描\n\n完整 A")
            self.assertEqual(detail["prompt"], "扫描 A")

    def test_report_history_marks_failed_outputs_as_viewable_records(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            server.REPORT_HISTORY_DIR = Path(temp_dir)
            failed_payload = server.error_report_payload("api.viviai.cc read timeout", {"prompt": "美股扫描"})

            record = server.save_report_history(failed_payload, {"prompt": "美股扫描"}, source="stream_error")
            detail = server.report_history_detail(record["id"])

            self.assertEqual(record["status"], "failed")
            self.assertIn("后端运行失败：api.viviai.cc read timeout", detail["payload"]["reportMarkdown"])
            self.assertEqual(detail["payload"]["title"], "研究未完成")


if __name__ == "__main__":
    unittest.main()

import json
import os
import tempfile
import time
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
        self.original_collect_research_data_nodes = server.collect_research_data_nodes
        self.original_report_history_dir = server.REPORT_HISTORY_DIR
        RecordingRequests.calls = []
        RecordingRequests.response = OkResponse()
        server.requests = RecordingRequests
        os.environ["OPENAI_API_KEY"] = "test-key-good"
        os.environ["OPENAI_BASE_URL"] = "https://api.viviai.cc/v1"
        os.environ["OPENAI_MODEL"] = "gpt-5.5"
        os.environ["WEEKLY_BRIEF_PREFLIGHT"] = "0"
        os.environ["WEEKLY_BRIEF_ENABLE_DATA_NODES"] = "0"
        server.AGENT_WORKFLOW = [
            ("intent_router", "Intent Router", "agents/08-intent-router.md"),
            ("final_narrative", "Final Narrative", "agents/01-ai-trend-narrative-analyst.md"),
        ]

    def tearDown(self):
        server.requests = self.original_requests
        server.AGENT_WORKFLOW = self.original_workflow
        server.run_agent_section = self.original_run_agent_section
        server.collect_research_data_nodes = self.original_collect_research_data_nodes
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

    def test_prompt_builders_include_version_a_output_standard(self):
        messages = server.build_messages("跑本周周报")
        full_prompt_text = "\n".join(message["content"] for message in messages)
        final_agent_prompt = server.agent_system_prompt("agents/01-ai-trend-narrative-analyst.md")
        stock_discovery_prompt = server.agent_system_prompt("agents/00-stock-discovery-analyst.md")

        for prompt_text in [full_prompt_text, final_agent_prompt, stock_discovery_prompt]:
            self.assertIn("Research Report Output Standard", prompt_text)
            self.assertIn("Version A：老板决策页 + 证据包", prompt_text)
            self.assertIn("Downstream Handoff", prompt_text)

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

    def test_wall_clock_timeout_interrupts_hung_section(self):
        started = time.monotonic()

        def slow_section():
            time.sleep(1)
            return "too late"

        with self.assertRaisesRegex(TimeoutError, "Hung Section reached wall-clock timeout=0.1s"):
            server.run_with_wall_clock_timeout("Hung Section", 0.1, slow_section)

        self.assertLess(time.monotonic() - started, 0.8)

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

    def test_graph_workflow_runs_data_nodes_before_local_agent_sections(self):
        events = []
        os.environ["WEEKLY_BRIEF_ENABLE_DATA_NODES"] = "1"
        os.environ["WEEKLY_BRIEF_LOCAL_DATA_SECTIONS"] = "1"
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

        def fake_items(count, *, ticker="NVDA", source="Test Node"):
            return [
                {
                    "ticker": ticker,
                    "title": f"{source} item {index}",
                    "source": source,
                    "date": "2026-06-29",
                    "url": f"https://example.com/{source.lower().replace(' ', '-')}/{index}",
                    "summary": f"{ticker} evidence {index}",
                }
                for index in range(1, count + 1)
            ]

        def fake_bundle(prompt):
            nodes = {
                "finnhub_news": server.data_node_result("finnhub_news", "Finnhub company news", "news", fake_items(10, source="Finnhub"), required=10),
                "arxiv_papers": server.data_node_result("arxiv_papers", "arXiv papers", "papers", fake_items(5, ticker="", source="arXiv"), required=5),
                "github_projects": server.data_node_result("github_projects", "GitHub project search", "open_source", fake_items(5, ticker="", source="GitHub"), required=5),
                "finnhub_sentiment": server.data_node_result("finnhub_sentiment", "Finnhub news sentiment", "sentiment", fake_items(5, source="Finnhub Sentiment"), required=5),
                "market_quotes": server.data_node_result("market_quotes", "Finnhub quotes", "market_data", fake_items(5, source="Finnhub Quote"), required=5),
                "finnhub_fundamentals": server.data_node_result("finnhub_fundamentals", "Finnhub profile / metrics", "fundamentals", fake_items(3, source="Finnhub Fundamentals"), required=3),
                "sec_filings": server.data_node_result("sec_filings", "SEC recent filings", "filings", fake_items(3, source="SEC EDGAR"), required=3),
                "technical_prices": server.data_node_result("technical_prices", "Yahoo daily technicals", "market_data", fake_items(5, source="Yahoo Finance"), required=5),
                "fred_macro": server.data_node_result("fred_macro", "FRED macro", "macro", fake_items(2, ticker="", source="FRED"), required=2),
            }
            bundle = {
                "enabled": True,
                "configuredApis": ["FINNHUB_API_KEY", "FRED_API_KEY", "SEC_EDGAR_USER_AGENT"],
                "tickers": [item["ticker"] for item in server.fallback_research_universe(prompt)],
                "nodes": nodes,
            }
            bundle["markdown"] = server.data_node_bundle_markdown(bundle)
            return bundle

        server.collect_research_data_nodes = fake_bundle

        def unexpected_model_call(**kwargs):
            raise AssertionError(f"model section should not run in local data section mode: {kwargs['section_name']}")

        server.run_agent_section = unexpected_model_call

        payload = server.run_agent_workflow(
            api_key="test-key-good",
            base_url="https://api.viviai.cc/v1",
            model="gpt-5.5",
            user_prompt="跑本周 AI 周报",
            on_event=events.append,
        )

        self.assertEqual(events[0]["event"], "data_node_start")
        self.assertEqual(events[1]["event"], "data_node_done")
        self.assertIn("StateGraph", payload["runMetadata"]["workflowEngine"])
        self.assertEqual(payload["runMetadata"]["workflowGraph"][0], "collect_data_nodes")
        self.assertTrue(payload["runMetadata"]["dataNodesEnabled"])
        self.assertTrue(payload["runMetadata"]["localDataSections"])
        self.assertEqual([trace["agent"] for trace in payload["agentTrace"]], [name for _key, name, _path in server.AGENT_WORKFLOW])
        self.assertTrue(payload["reportMarkdown"].startswith("# 老板决策页"))
        self.assertIn("Hold-Watch", payload["reportMarkdown"])
        self.assertIn("Data Node Detail", payload["evidenceMarkdown"])

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

    def test_failed_final_narrative_is_repaired_to_version_a_partial_report(self):
        sections = {
            "Intent Router": "# Intent Route Plan\n\n## Section 状态\n状态：complete",
            "Stock Discovery": "# Stock Discovery Section\n\n## Section 状态\n状态：partial",
            "AI 信息与舆情": "# AI 信息与舆情 Section\n\n## Section 状态\n状态：failed",
            "Fundamental": "# 基本面验证报告\n\n## Section 状态\n状态：partial",
            "Technical": "# 技术分析报告\n\n## Section 状态\n状态：partial",
            "Reflection": "# Reflection Section\n\n## Section 状态\n状态：failed",
            "Final Narrative": "# Final Narrative Section\n\n## Section 状态\n状态：failed\n\n后端运行失败：read timeout",
        }

        payload = server.build_workflow_payload_from_sections("跑本周 AI 周报", sections)

        self.assertIn("老板决策页", payload["summaryMarkdown"])
        self.assertIn("Confidence", payload["summaryMarkdown"])
        self.assertIn("Est. Upside Range", payload["summaryMarkdown"])
        self.assertIn("Exit / Trim Rule", payload["summaryMarkdown"])
        self.assertIn("No Rating", payload["summaryMarkdown"])
        self.assertIn("数据节点不足", payload["summaryMarkdown"])
        self.assertNotIn("Final Narrative Section\n\n## Section 状态\n状态：failed", payload["summaryMarkdown"])
        self.assertIn("Agent Run Audit", payload["reportMarkdown"])
        self.assertEqual(payload["researchActionPool"], [])

    def test_action_pool_parser_ignores_not_core_pool_table(self):
        report = server.build_local_version_a_report(
            "跑本周 AI 周报",
            {
                "Intent Router": "## Section 状态\n状态：failed",
                "Stock Discovery": "## Section 状态\n状态：failed",
                "AI 信息与舆情": "## Section 状态\n状态：failed",
                "Fundamental": "## Section 状态\n状态：failed",
                "Technical": "## Section 状态\n状态：failed",
                "Reflection": "## Section 状态\n状态：failed",
                "Final Narrative": "## Section 状态\n状态：failed",
            },
        )

        self.assertEqual(server.parse_action_pool_from_markdown(report), [])
        self.assertNotRegex(report, r"Ticker / Theme \| Research Rating\n\n\|---")


if __name__ == "__main__":
    unittest.main()

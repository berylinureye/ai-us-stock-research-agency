import json
import os
import tempfile
import time
import unittest
from pathlib import Path

from backend.app.clients import data_nodes
from backend.app.core import config
from backend.app.services import agent_sections
from backend.app.services import payloads
from backend.app.services import workflow as server
from backend.app.services import workflow_reports


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
        self.original_requests = agent_sections.requests
        self.original_env = os.environ.copy()
        self.original_workflow = server.AGENT_WORKFLOW
        self.original_run_agent_section = server.run_agent_section
        self.original_collect_research_data_nodes = server.collect_research_data_nodes
        self.original_report_history_dir = payloads.REPORT_HISTORY_DIR
        RecordingRequests.calls = []
        RecordingRequests.response = OkResponse()
        agent_sections.requests = RecordingRequests
        os.environ["OPENAI_API_KEY"] = "test-key-good"
        os.environ["OPENAI_BASE_URL"] = "https://api.viviai.cc/v1"
        os.environ["OPENAI_MODEL"] = "gpt-5.5"
        os.environ["WEEKLY_BRIEF_PREFLIGHT"] = "0"
        os.environ["WEEKLY_BRIEF_ENABLE_DATA_NODES"] = "0"
        self.set_agent_workflow([
            ("intent_router", "Intent Router", "agents/08-intent-router.md"),
            ("final_narrative", "Final Narrative", "agents/01-ai-trend-narrative-analyst.md"),
        ])

    def tearDown(self):
        agent_sections.requests = self.original_requests
        self.set_agent_workflow(self.original_workflow)
        server.run_agent_section = self.original_run_agent_section
        server.collect_research_data_nodes = self.original_collect_research_data_nodes
        payloads.REPORT_HISTORY_DIR = self.original_report_history_dir
        os.environ.clear()
        os.environ.update(self.original_env)

    def set_agent_workflow(self, value):
        server.AGENT_WORKFLOW = value

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
        self.assertEqual(config.prompt_label(server.DEFAULT_RESEARCH_INTENT), "美股全市场机会扫描")

    def test_prompt_builders_include_version_a_output_standard(self):
        messages = payloads.build_messages("跑本周周报")
        full_prompt_text = "\n".join(message["content"] for message in messages)
        final_agent_prompt = agent_sections.agent_system_prompt("agents/01-ai-trend-narrative-analyst.md")
        stock_discovery_prompt = agent_sections.agent_system_prompt("agents/00-stock-discovery-analyst.md")

        for prompt_text in [full_prompt_text, final_agent_prompt, stock_discovery_prompt]:
            self.assertIn("Research Report Output Standard", prompt_text)
            self.assertIn("Version A：老板决策页 + 证据包", prompt_text)
            self.assertIn("Downstream Handoff", prompt_text)

    def test_section_status_distinguishes_agent_status_from_data_node_failures(self):
        self.assertEqual(
            workflow_reports.infer_section_status("## Section 状态\n- 状态：complete\n- 外部数据节点 failed。"),
            "complete",
        )
        self.assertEqual(
            workflow_reports.infer_section_status("**Section 状态：partial**\n新闻节点 failed，行情未接入。"),
            "partial",
        )
        self.assertEqual(
            workflow_reports.infer_section_status("# 研究未完成\n\n后端运行失败：boom"),
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
        self.set_agent_workflow([
            ("intent_router", "Intent Router", "agents/08-intent-router.md"),
            ("information_sentiment", "AI 信息与舆情", "agents/02-ai-information-sentiment-analyst.md"),
            ("final_narrative", "Final Narrative", "agents/01-ai-trend-narrative-analyst.md"),
        ])

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
        self.set_agent_workflow([
            ("intent_router", "Intent Router", "agents/08-intent-router.md"),
            ("stock_discovery", "Stock Discovery", "agents/00-stock-discovery-analyst.md"),
            ("information_sentiment", "AI 信息与舆情", "agents/02-ai-information-sentiment-analyst.md"),
            ("fundamental", "Fundamental", "agents/03-fundamental-analyst.md"),
            ("technical", "Technical", "agents/04-technical-analyst.md"),
            ("reflection", "Reflection", "agents/05-reflection-judge.md"),
            ("final_narrative", "Final Narrative", "agents/01-ai-trend-narrative-analyst.md"),
            ("paper_attribution", "Paper Attribution", "agents/07-paper-portfolio-attribution-agent.md"),
        ])

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
                "finnhub_news": data_nodes.data_node_result("finnhub_news", "Finnhub company news", "news", fake_items(10, source="Finnhub"), required=10),
                "arxiv_papers": data_nodes.data_node_result("arxiv_papers", "arXiv papers", "papers", fake_items(5, ticker="", source="arXiv"), required=5),
                "github_projects": data_nodes.data_node_result("github_projects", "GitHub project search", "open_source", fake_items(5, ticker="", source="GitHub"), required=5),
                "finnhub_sentiment": data_nodes.data_node_result("finnhub_sentiment", "Finnhub news sentiment", "sentiment", fake_items(5, source="Finnhub Sentiment"), required=5),
                "market_quotes": data_nodes.data_node_result("market_quotes", "Finnhub quotes", "market_data", fake_items(5, source="Finnhub Quote"), required=5),
                "finnhub_fundamentals": data_nodes.data_node_result("finnhub_fundamentals", "Finnhub profile / metrics", "fundamentals", fake_items(3, source="Finnhub Fundamentals"), required=3),
                "sec_filings": data_nodes.data_node_result("sec_filings", "SEC recent filings", "filings", fake_items(3, source="SEC EDGAR"), required=3),
                "technical_prices": data_nodes.data_node_result("technical_prices", "Yahoo daily technicals", "market_data", fake_items(5, source="Yahoo Finance"), required=5),
                "fred_macro": data_nodes.data_node_result("fred_macro", "FRED macro", "macro", fake_items(2, ticker="", source="FRED"), required=2),
            }
            bundle = {
                "enabled": True,
                "configuredApis": ["FINNHUB_API_KEY", "FRED_API_KEY", "SEC_EDGAR_USER_AGENT"],
                "tickers": [item["ticker"] for item in config.fallback_research_universe(prompt)],
                "nodes": nodes,
            }
            bundle["markdown"] = data_nodes.data_node_bundle_markdown(bundle)
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

    def test_local_data_sections_auto_does_not_bypass_model_agents(self):
        os.environ.pop("WEEKLY_BRIEF_LOCAL_DATA_SECTIONS", None)
        bundle = {
            "enabled": True,
            "configuredApis": ["FINNHUB_API_KEY", "FRED_API_KEY", "SEC_EDGAR_USER_AGENT"],
            "nodes": {},
        }

        self.assertFalse(data_nodes.local_data_sections_enabled(bundle))

    def test_full_market_seed_universe_expands_beyond_static_broad_list(self):
        broad = [item["ticker"] for item in config.fallback_research_universe("普通扫描")]
        full_market = [item["ticker"] for item in config.research_seed_universe("美股全市场机会扫描")]

        self.assertGreater(len(full_market), len(broad))
        self.assertIn("NVDA", full_market)
        self.assertIn("JPM", full_market)
        self.assertIn("WMT", full_market)
        self.assertNotEqual(full_market[: len(broad)], broad)

    def test_local_data_action_pool_uses_differentiated_watch_metrics(self):
        def item(ticker, source, index, summary=""):
            return {
                "ticker": ticker,
                "title": f"{ticker} {source} item {index}",
                "source": source,
                "date": "2026-06-29",
                "url": f"https://example.com/{ticker}/{source}/{index}",
                "summary": summary or f"{ticker} evidence {index}",
            }

        tickers = ["MSFT", "NVDA", "AMZN", "GOOGL", "META"]
        news = [item(ticker, "Finnhub", index) for ticker in tickers for index in range(1, 3)]
        market = [item(ticker, "Finnhub Quote", 1, "change_pct=1.2%") for ticker in tickers]
        technical = [
            item("MSFT", "Yahoo Finance", 1, "trend=above_20d_sma; sma20=100; sma50=90"),
            item("NVDA", "Yahoo Finance", 1, "trend=near_20d_sma; sma20=100; sma50=98"),
            item("AMZN", "Yahoo Finance", 1, "trend=below_20d_sma; sma20=100; sma50=105"),
            item("GOOGL", "Yahoo Finance", 1, "trend=above_20d_sma; sma20=100; sma50=92"),
            item("META", "Yahoo Finance", 1, "trend=below_20d_sma; sma20=100; sma50=110"),
        ]
        fundamentals = [item(ticker, "Finnhub Fundamentals", 1, "revenueGrowthTTMYoy=10") for ticker in tickers[:3]]
        filings = [item(ticker, "SEC EDGAR", 1, "10-K filed") for ticker in tickers[:3]]
        nodes = {
            "finnhub_news": data_nodes.data_node_result("finnhub_news", "Finnhub company news", "news", news, required=10),
            "arxiv_papers": data_nodes.data_node_result("arxiv_papers", "arXiv papers", "papers", [item("", "arXiv", i) for i in range(1, 6)], required=5),
            "github_projects": data_nodes.data_node_result("github_projects", "GitHub project search", "open_source", [item("", "GitHub", i) for i in range(1, 6)], required=5),
            "finnhub_sentiment": data_nodes.data_node_result("finnhub_sentiment", "Finnhub news sentiment", "sentiment", [], required=5, status="failed", error="403"),
            "market_quotes": data_nodes.data_node_result("market_quotes", "Finnhub quotes", "market_data", market, required=5),
            "finnhub_fundamentals": data_nodes.data_node_result("finnhub_fundamentals", "Finnhub profile / metrics", "fundamentals", fundamentals, required=3),
            "sec_filings": data_nodes.data_node_result("sec_filings", "SEC recent filings", "filings", filings, required=3),
            "technical_prices": data_nodes.data_node_result("technical_prices", "Yahoo daily technicals", "market_data", technical, required=5),
            "fred_macro": data_nodes.data_node_result("fred_macro", "FRED macro", "macro", [item("", "FRED", i) for i in range(1, 3)], required=2),
        }
        bundle = {
            "enabled": True,
            "configuredApis": ["FINNHUB_API_KEY", "FRED_API_KEY", "SEC_EDGAR_USER_AGENT"],
            "tickers": tickers,
            "nodes": nodes,
        }

        report = workflow_reports.build_local_data_version_a_report("美股全市场机会扫描", {}, bundle)
        pool = payloads.parse_action_pool_from_markdown(report)

        self.assertGreaterEqual(len(pool), 3)
        self.assertTrue(all(candidate["actionRating"] == "Hold-Watch" for candidate in pool))
        self.assertTrue(all(candidate["confidence"] <= 74 for candidate in pool))
        self.assertGreater(len({candidate["confidence"] for candidate in pool}), 1)
        self.assertGreater(
            len({(candidate["estimatedHoldingMinDays"], candidate["estimatedHoldingMaxDays"]) for candidate in pool}),
            1,
        )

    def test_data_node_status_redacts_query_credentials(self):
        bundle = {
            "enabled": True,
            "nodes": {
                "finnhub_sentiment": data_nodes.data_node_result(
                    "finnhub_sentiment",
                    "Finnhub news sentiment",
                    "sentiment",
                    [],
                    required=5,
                    status="failed",
                    error="403 Client Error for url: https://finnhub.io/api/v1/news-sentiment?symbol=MSFT&token=secret&api_key=abc",
                )
            },
        }

        rows = "\n".join(data_nodes.data_node_status_rows(bundle))

        self.assertIn("token=***", rows)
        self.assertIn("api_key=***", rows)
        self.assertNotIn("secret", rows)
        self.assertNotIn("api_key=abc", rows)

    def test_empty_discovery_output_is_repaired_so_every_agent_has_output(self):
        events = []
        self.set_agent_workflow([
            ("intent_router", "Intent Router", "agents/08-intent-router.md"),
            ("stock_discovery", "Stock Discovery", "agents/00-stock-discovery-analyst.md"),
            ("information_sentiment", "AI 信息与舆情", "agents/02-ai-information-sentiment-analyst.md"),
            ("fundamental", "Fundamental", "agents/03-fundamental-analyst.md"),
            ("technical", "Technical", "agents/04-technical-analyst.md"),
            ("reflection", "Reflection", "agents/05-reflection-judge.md"),
            ("final_narrative", "Final Narrative", "agents/01-ai-trend-narrative-analyst.md"),
            ("paper_attribution", "Paper Attribution", "agents/07-paper-portfolio-attribution-agent.md"),
        ])

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
            payloads.REPORT_HISTORY_DIR = Path(temp_dir)
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

            first_record = payloads.save_report_history(first_payload, {"prompt": "扫描 A"}, source="test")
            second_record = payloads.save_report_history(second_payload, {"prompt": "扫描 B"}, source="test")
            history = payloads.report_history_payload()

            self.assertNotEqual(first_record["id"], second_record["id"])
            self.assertEqual(history["summary"]["count"], 2)
            self.assertEqual([item["title"] for item in history["items"]], ["老板决策页：第二次扫描", "老板决策页：第一次扫描"])

            detail = payloads.report_history_detail(first_record["id"])
            self.assertEqual(detail["payload"]["reportMarkdown"], "# 老板决策页：第一次扫描\n\n完整 A")
            self.assertEqual(detail["prompt"], "扫描 A")

    def test_report_history_marks_failed_outputs_as_viewable_records(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            payloads.REPORT_HISTORY_DIR = Path(temp_dir)
            failed_payload = payloads.error_report_payload("api.viviai.cc read timeout", {"prompt": "美股扫描"})

            record = payloads.save_report_history(failed_payload, {"prompt": "美股扫描"}, source="stream_error")
            detail = payloads.report_history_detail(record["id"])

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

        payload = workflow_reports.build_workflow_payload_from_sections("跑本周 AI 周报", sections)

        self.assertIn("老板决策页", payload["summaryMarkdown"])
        self.assertIn("Confidence", payload["summaryMarkdown"])
        self.assertIn("Est. Upside Range", payload["summaryMarkdown"])
        self.assertIn("Exit / Trim Rule", payload["summaryMarkdown"])
        self.assertIn("No Rating", payload["summaryMarkdown"])
        self.assertIn("数据节点不足", payload["summaryMarkdown"])
        self.assertNotIn("Final Narrative Section\n\n## Section 状态\n状态：failed", payload["summaryMarkdown"])
        self.assertIn("Agent Run Audit", payload["reportMarkdown"])
        self.assertEqual(payload["researchActionPool"], [])

    def test_failed_final_narrative_uses_data_driven_fallback_when_bundle_exists(self):
        def item(ticker, source, index, summary=""):
            return {
                "ticker": ticker,
                "title": f"{ticker} {source} item {index}",
                "source": source,
                "date": "2026-06-29",
                "url": f"https://example.com/{ticker}/{source}/{index}",
                "summary": summary or f"{ticker} evidence {index}",
            }

        tickers = ["NVDA", "MSFT", "AVGO", "AMD", "TSM", "ASML"]
        nodes = {
            "finnhub_news": data_nodes.data_node_result(
                "finnhub_news",
                "Finnhub company news",
                "news",
                [item(ticker, "Finnhub", index) for ticker in tickers for index in range(1, 3)],
                required=10,
            ),
            "arxiv_papers": data_nodes.data_node_result(
                "arxiv_papers",
                "arXiv papers",
                "papers",
                [item("", "arXiv", index) for index in range(1, 6)],
                required=5,
            ),
            "github_projects": data_nodes.data_node_result(
                "github_projects",
                "GitHub project search",
                "open_source",
                [item("", "GitHub", index) for index in range(1, 6)],
                required=5,
            ),
            "finnhub_sentiment": data_nodes.data_node_result(
                "finnhub_sentiment",
                "Finnhub news sentiment",
                "sentiment",
                [],
                required=5,
                status="failed",
                error="403",
            ),
            "market_quotes": data_nodes.data_node_result(
                "market_quotes",
                "Finnhub quotes",
                "market_data",
                [item(ticker, "Finnhub Quote", 1) for ticker in tickers],
                required=5,
            ),
            "finnhub_fundamentals": data_nodes.data_node_result(
                "finnhub_fundamentals",
                "Finnhub profile / metrics",
                "fundamentals",
                [item(ticker, "Finnhub Fundamentals", 1) for ticker in tickers],
                required=3,
            ),
            "sec_filings": data_nodes.data_node_result(
                "sec_filings",
                "SEC recent filings",
                "filings",
                [item(ticker, "SEC EDGAR", 1) for ticker in tickers[:4]],
                required=3,
            ),
            "technical_prices": data_nodes.data_node_result(
                "technical_prices",
                "Yahoo daily technicals",
                "market_data",
                [
                    item("NVDA", "Yahoo Finance", 1, "trend=below_20d_sma"),
                    item("MSFT", "Yahoo Finance", 1, "trend=above_20d_sma"),
                    item("AVGO", "Yahoo Finance", 1, "trend=below_20d_sma"),
                    item("AMD", "Yahoo Finance", 1, "trend=above_20d_sma"),
                    item("TSM", "Yahoo Finance", 1, "trend=near_20d_sma"),
                    item("ASML", "Yahoo Finance", 1, "trend=near_20d_sma"),
                ],
                required=5,
            ),
            "fred_macro": data_nodes.data_node_result(
                "fred_macro",
                "FRED macro",
                "macro",
                [item("", "FRED", index) for index in range(1, 3)],
                required=2,
            ),
        }
        bundle = {"enabled": True, "tickers": tickers, "nodes": nodes}
        sections = {
            "Intent Router": "# Intent Route Plan\n\n## Section 状态\n状态：complete",
            "Stock Discovery": "# Stock Discovery Section\n\n## Section 状态\n状态：partial",
            "AI 信息与舆情": "# AI 信息与舆情 Section\n\n## Section 状态\n状态：partial",
            "Fundamental": "# 基本面验证报告\n\n## Section 状态\n状态：partial",
            "Technical": "# 技术分析报告\n\n## Section 状态\n状态：partial",
            "Reflection": "# Reflection Section\n\n## Section 状态\n状态：partial",
            "Final Narrative": "# Final Narrative Section\n\n## Section 状态\n状态：failed\n\n后端运行失败：Final Narrative reached wall-clock timeout=180.0s",
        }

        payload = workflow_reports.build_workflow_payload_from_sections("美股全市场机会扫描", sections, bundle)

        pool = payload["researchActionPool"]
        self.assertGreaterEqual(len(pool), 3)
        self.assertNotEqual([item["ticker"] for item in pool[:5]], ["MSFT", "NVDA", "AMZN", "GOOGL", "META"])
        self.assertGreater(len({item["confidence"] for item in pool}), 1)
        self.assertGreater(len({(item["estimatedHoldingMinDays"], item["estimatedHoldingMaxDays"]) for item in pool}), 1)
        self.assertIn("Data Node", payload["summaryMarkdown"])
        self.assertNotIn("fallback_seed_universe；缺少本周新闻、财务、行情和证据包确认", payload["summaryMarkdown"])

    def test_final_narrative_prompt_uses_compact_upstream_context(self):
        long_context = {
            "Intent Router": "A" * 9000,
            "Stock Discovery": "B" * 9000,
            "AI 信息与舆情": "C" * 9000,
            "Fundamental": "D" * 9000,
            "Technical": "E" * 9000,
            "Reflection": "F" * 9000,
        }
        data_bundle = {"markdown": "G" * 20000}

        prompt = agent_sections.build_section_user_prompt(
            section_name="Final Narrative",
            user_prompt="美股全市场机会扫描",
            context_sections=long_context,
            data_bundle=data_bundle,
        )

        self.assertLess(len(prompt), 35000)
        self.assertNotIn("A" * 8000, prompt)
        self.assertNotIn("G" * 12000, prompt)

    def test_data_complete_workflow_uses_data_driven_final_without_model_timeout(self):
        def item(ticker, source, index, summary=""):
            return {
                "ticker": ticker,
                "title": f"{ticker} {source} item {index}",
                "source": source,
                "date": "2026-06-29",
                "url": f"https://example.com/{ticker}/{source}/{index}",
                "summary": summary or f"{ticker} evidence {index}",
            }

        tickers = ["NVDA", "MSFT", "AVGO", "AMD", "TSM"]
        nodes = {
            "finnhub_news": data_nodes.data_node_result(
                "finnhub_news",
                "Finnhub company news",
                "news",
                [item(ticker, "Finnhub", index) for ticker in tickers for index in range(1, 3)],
                required=10,
            ),
            "arxiv_papers": data_nodes.data_node_result("arxiv_papers", "arXiv papers", "papers", [item("", "arXiv", i) for i in range(1, 6)], required=5),
            "github_projects": data_nodes.data_node_result("github_projects", "GitHub project search", "open_source", [item("", "GitHub", i) for i in range(1, 6)], required=5),
            "market_quotes": data_nodes.data_node_result("market_quotes", "Finnhub quotes", "market_data", [item(ticker, "Finnhub Quote", 1) for ticker in tickers], required=5),
            "technical_prices": data_nodes.data_node_result("technical_prices", "Yahoo daily technicals", "market_data", [item(ticker, "Yahoo Finance", 1, "trend=above_20d_sma") for ticker in tickers], required=5),
            "finnhub_fundamentals": data_nodes.data_node_result("finnhub_fundamentals", "Finnhub profile / metrics", "fundamentals", [item(ticker, "Finnhub Fundamentals", 1) for ticker in tickers], required=3),
            "sec_filings": data_nodes.data_node_result("sec_filings", "SEC recent filings", "filings", [item(ticker, "SEC EDGAR", 1) for ticker in tickers[:3]], required=3),
            "finnhub_sentiment": data_nodes.data_node_result("finnhub_sentiment", "Finnhub news sentiment", "sentiment", [], required=5, status="failed", error="403"),
        }
        bundle = {"enabled": True, "tickers": tickers, "nodes": nodes}
        self.set_agent_workflow([
            ("intent_router", "Intent Router", "agents/08-intent-router.md"),
            ("stock_discovery", "Stock Discovery", "agents/00-stock-discovery-analyst.md"),
            ("information_sentiment", "AI 信息与舆情", "agents/02-ai-information-sentiment-analyst.md"),
            ("fundamental", "Fundamental", "agents/03-fundamental-analyst.md"),
            ("technical", "Technical", "agents/04-technical-analyst.md"),
            ("reflection", "Reflection", "agents/05-reflection-judge.md"),
            ("final_narrative", "Final Narrative", "agents/01-ai-trend-narrative-analyst.md"),
        ])

        server.collect_research_data_nodes = lambda _prompt: bundle

        def fake_run_agent_section(**kwargs):
            section_name = kwargs["section_name"]
            if section_name == "Final Narrative":
                raise AssertionError("Final Narrative model call should be skipped when data nodes are enough")
            return f"# {section_name} Section\n\n## Agent 公开思考摘要\n本 section 已完成公开摘要。\n\n## Section 状态\n状态：partial\n"

        server.run_agent_section = fake_run_agent_section

        payload = server.run_agent_workflow(
            api_key="test-key-good",
            base_url="https://api.viviai.cc/v1",
            model="gpt-5.5",
            user_prompt="美股全市场机会扫描",
        )

        final_trace = [trace for trace in payload["agentTrace"] if trace["agent"] == "Final Narrative"][0]
        self.assertNotEqual(final_trace["status"], "failed")
        self.assertNotIn("reached wall-clock timeout", payload["reportMarkdown"])
        self.assertGreaterEqual(len(payload["researchActionPool"]), 3)

    def test_history_status_complete_when_action_pool_exists_despite_data_gaps(self):
        payload = {
            "title": "老板决策页：美股全市场机会扫描",
            "reportMarkdown": "# 老板决策页：美股全市场机会扫描\n\n最大反证：finnhub_sentiment: failed(0/5)\n\n下周补齐数据缺口。",
            "researchActionPool": [{"ticker": "NVDA", "actionRating": "Hold-Watch", "confidence": 73}],
        }

        self.assertEqual(payloads.report_history_status(payload), "complete")

    def test_history_status_complete_when_recovered_report_keeps_failed_section_appendix(self):
        payload = {
            "title": "老板决策页：美股全市场机会扫描",
            "reportMarkdown": "\n\n".join(
                [
                    "# 老板决策页：美股全市场机会扫描",
                    "## 本周研究动作\n| Rank | Ticker / Theme | Research Rating | Confidence |\n|---:|---|---|---:|\n| 1 | NVDA / NVIDIA | Hold-Watch | 73 |",
                    "# 附录：本次 Agent 原始过程",
                    "## Final Narrative",
                    "## Section 状态\n状态：failed",
                    "后端运行失败：Final Narrative reached wall-clock timeout=180.0s",
                ]
            ),
            "researchActionPool": [{"ticker": "NVDA", "actionRating": "Hold-Watch", "confidence": 73}],
        }

        self.assertEqual(payloads.report_history_status(payload), "complete")

    def test_action_pool_parser_ignores_not_core_pool_table(self):
        report = workflow_reports.build_local_version_a_report(
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

        self.assertEqual(payloads.parse_action_pool_from_markdown(report), [])
        self.assertNotRegex(report, r"Ticker / Theme \| Research Rating\n\n\|---")


if __name__ == "__main__":
    unittest.main()

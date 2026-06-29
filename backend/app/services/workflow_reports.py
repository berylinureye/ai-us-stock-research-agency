from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from ..clients.data_nodes import data_node_complete_enough, data_node_status_rows, evidence_items_table, node_items
from ..core.config import (
    DEFAULT_RESEARCH_INTENT,
    compact_output_standard_text,
    fallback_research_universe,
    normalize_ticker,
    research_seed_universe,
    safe_text,
    today_iso,
    truncate_text,
)
from .agent_sections import generated_handoff_markdown, repaired_section_markdown
from .payloads import extract_summary, normalize_research_action_pool
from .trace import is_unhelpful_deferral_text

def bundle_status(bundle: dict[str, Any], required_keys: list[str]) -> str:
    if not bundle.get("enabled"):
        return "partial"
    nodes = bundle.get("nodes") or {}
    if not required_keys:
        return "complete"
    statuses = [safe_text((nodes.get(key) or {}).get("status")) for key in required_keys]
    if statuses and all(status == "success" for status in statuses):
        return "complete"
    if any(status in {"success", "partial"} for status in statuses):
        return "partial"
    return "failed"


def missing_node_summary(bundle: dict[str, Any]) -> str:
    missing = []
    for key, node in (bundle.get("nodes") or {}).items():
        if node.get("status") != "success":
            missing.append(f"{node.get('label') or key}: {node.get('status')}({node.get('count', 0)}/{node.get('required', 0)})")
    return "；".join(missing[:8]) or "无重大缺口。"


def ticker_evidence_counts(bundle: dict[str, Any], ticker: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for key, node in (bundle.get("nodes") or {}).items():
        count = 0
        for item in node.get("items") or []:
            if isinstance(item, dict) and safe_text(item.get("ticker")).upper() == ticker:
                count += 1
        counts[key] = count
    return counts


def stock_discovery_table(user_prompt: str, bundle: dict[str, Any]) -> str:
    rows = ["| Ticker | Company | Evidence Coverage | Treatment | Reason |", "|---|---|---:|---|---|"]
    for item in research_candidate_universe(user_prompt, bundle):
        ticker = item["ticker"]
        counts = ticker_evidence_counts(bundle, ticker)
        coverage = sum(counts.values())
        treatment = "active research candidate" if coverage >= 3 else "watchlist / needs evidence"
        reason = item["why"]
        if coverage:
            reason += f"；真实节点命中 {coverage} 条。"
        else:
            reason += "；暂未被真实节点充分命中。"
        rows.append(f"| {ticker} | {item['company']} | {coverage} | {treatment} | {reason} |")
    return "\n".join(rows)


def research_candidate_universe(user_prompt: str, bundle: dict[str, Any] | None = None) -> list[dict[str, str]]:
    candidates = research_seed_universe(user_prompt)
    seen = {normalize_ticker(item["ticker"]) for item in candidates}
    for raw_ticker in (bundle or {}).get("tickers") or []:
        ticker = normalize_ticker(raw_ticker)
        if not ticker or ticker in seen:
            continue
        seen.add(ticker)
        candidates.append(
            {
                "ticker": ticker,
                "company": ticker,
                "why": "本次 Data Node seed universe 命中；需要后续 section 继续验证。",
            }
        )
    return candidates


def local_data_section_markdown(section_name: str, user_prompt: str, bundle: dict[str, Any], context_sections: dict[str, str]) -> str:
    if section_name == "Intent Router":
        status = "complete" if bundle.get("enabled") else "partial"
        body = "\n\n".join(
            [
                "## Route Plan",
                "| Field | Decision |",
                "|---|---|",
                "| Task Type | full_weekly_brief |",
                "| Final Report Format | Version A：老板决策页 + 证据包 |",
                "| Core Pipeline | Intent Router -> Stock Discovery -> AI 信息与舆情 -> Fundamental -> Technical -> Reflection -> Final Narrative -> Paper Attribution |",
                "| Active Candidate Cap | 8 |",
                "| Safety Boundary | 研究用途；不下单、不调仓、不输出个性化仓位 |",
                "",
                "## Data Node Status",
                "\n".join(data_node_status_rows(bundle)),
            ]
        )
        decision_needed = "Stock Discovery 使用 seed universe 和真实节点命中情况生成候选入口。"
    elif section_name == "Stock Discovery":
        status = bundle_status(bundle, ["finnhub_news", "market_quotes", "technical_prices"])
        body = "\n\n".join(
            [
                "## Active Candidate Scan",
                stock_discovery_table(user_prompt, bundle),
                "",
                "## Data Node Status",
                "\n".join(data_node_status_rows(bundle)),
            ]
        )
        decision_needed = "AI 信息与舆情继续验证 active/watchlist candidates，不把低覆盖 ticker 升级为结论。"
    elif section_name == "AI 信息与舆情":
        status = bundle_status(bundle, ["finnhub_news", "arxiv_papers", "github_projects", "finnhub_sentiment"])
        body = "\n\n".join(
            [
                "## AI Technology News",
                evidence_items_table(node_items(bundle, "finnhub_news"), max_rows=10),
                "",
                "## AI Academic Papers",
                evidence_items_table(node_items(bundle, "arxiv_papers"), max_rows=5),
                "",
                "## AI Open Source Projects",
                evidence_items_table(node_items(bundle, "github_projects"), max_rows=5),
                "",
                "## High-Signal Information / Sentiment Evidence",
                evidence_items_table(node_items(bundle, "finnhub_sentiment"), max_rows=5),
                "",
                "## Data Node Status",
                "\n".join(data_node_status_rows(bundle)),
            ]
        )
        decision_needed = "Fundamental 只继承有 source/date/link 的故事和 ticker，不继承社媒/新闻热度本身。"
    elif section_name == "Fundamental":
        status = bundle_status(bundle, ["finnhub_fundamentals", "sec_filings"])
        body = "\n\n".join(
            [
                "## Fundamental Evidence",
                evidence_items_table(node_items(bundle, "finnhub_fundamentals") + node_items(bundle, "sec_filings"), max_rows=14),
                "",
                "## Market Context",
                evidence_items_table(node_items(bundle, "market_quotes") + node_items(bundle, "fred_macro"), max_rows=12),
                "",
                "## Data Node Status",
                "\n".join(data_node_status_rows(bundle)),
            ]
        )
        decision_needed = "Technical 使用真实价格数据验证时机；Final Narrative 不能把新闻或 GitHub 证据当作财务证明。"
    elif section_name == "Technical":
        status = bundle_status(bundle, ["technical_prices", "market_quotes"])
        body = "\n\n".join(
            [
                "## Technical Evidence",
                evidence_items_table(node_items(bundle, "technical_prices") + node_items(bundle, "market_quotes"), max_rows=14),
                "",
                "## Data Node Status",
                "\n".join(data_node_status_rows(bundle)),
            ]
        )
        decision_needed = "Reflection 审查信息、基本面、技术面是否形成闭环；图表强势不能单独升级为投资结论。"
    elif section_name == "Reflection":
        upstream_statuses = [infer_section_status(markdown) for markdown in context_sections.values()]
        status = "partial" if any(item in {"partial", "failed"} for item in upstream_statuses) else "complete"
        body = "\n\n".join(
            [
                "## Cathie Wood vs Buffett Debate",
                "| Lens | Challenge | Result |",
                "|---|---|---|",
                "| Cathie Wood | AI 扩散、agent/inference/open-source 是否形成非线性增长曲线？ | 只把新闻、论文、GitHub 与行情同时支持的故事保留为观察假设。 |",
                "| Buffett | 现金流、估值、护城河和安全边际是否能验证？ | 若缺 SEC/财务/估值证据，则只能 No Rating 或 Hold-Watch，不给 Research Buy。 |",
                "| Synthesis | 三层证据是否闭环？ | 信息、基本面、技术面至少两层支持才进入老板页动作表。 |",
                "",
                "## Data Gaps",
                missing_node_summary(bundle),
            ]
        )
        decision_needed = "Final Narrative 只输出研究动作，不输出交易动作；缺口要降低置信度。"
    elif section_name == "Final Narrative":
        return build_local_data_version_a_report(user_prompt, context_sections, bundle)
    elif section_name == "Paper Attribution":
        return repaired_section_markdown(section_name, user_prompt, "partial")
    else:
        status = "partial"
        body = bundle.get("markdown") or "数据节点不可用。"
        decision_needed = "下游继续验证。"

    return "\n\n".join(
        [
            f"# {section_name} Section",
            "",
            "## Agent 公开思考摘要",
            (
                f"我直接使用本次后端采集的 Data Node Evidence Bundle 运行 {section_name}，"
                "不再让模型自行检索或补编来源；缺失节点会被显式降级。"
            ),
            "",
            "## Section 状态",
            f"状态：{status}",
            "",
            body,
            "",
            "## 当前判断",
            f"当前判断：{missing_node_summary(bundle)}",
            "",
            "## 下一步",
            decision_needed,
            "",
            generated_handoff_markdown(
                section_name=section_name,
                user_prompt=user_prompt,
                status=status,
                decision_needed=decision_needed,
                missing_proof=missing_node_summary(bundle),
                notes="Data Node Evidence Bundle",
            ),
        ]
    )


def ensure_section_actionable_output(section_name: str, markdown: str, user_prompt: str) -> str:
    if not str(markdown or "").strip():
        return repaired_section_markdown(section_name, user_prompt, "partial")
    if is_unhelpful_deferral_text(markdown):
        return repaired_section_markdown(section_name, user_prompt, infer_section_status(markdown))
    return markdown


def build_final_payload_prompt(user_prompt: str, sections: dict[str, str]) -> str:
    section_bundle = "\n\n".join(
        f"# Agent Output: {name}\n{truncate_text(markdown, 16000)}"
        for name, markdown in sections.items()
    )
    output_standard = compact_output_standard_text()
    return f"""
请把以下本次运行产生的 agent sections 汇总成前端需要的 JSON。

用户原始请求：
{user_prompt}

本次 agent outputs：
{section_bundle}

报告输出标准：
{output_standard}

只输出 JSON，不要输出 JSON 以外的文字。Schema:
{{
  "title": "报告标题，必须响应用户原始请求",
  "summaryMarkdown": "精简版 Markdown。必须从 # 老板决策页 开始。",
  "reportMarkdown": "完整周报 Markdown。必须从 # 老板决策页 开始，Route Plan 和 agent 状态放附录。",
  "evidenceMarkdown": "证据包 Markdown。必须包含返回主报告、Evidence Index、Data Node Status、Agent Run Audit。",
  "researchActionPool": [
    {{
      "ticker": "Ticker",
      "company": "Company name",
      "actionRating": "Research Buy / Hold-Watch / Take-Profit / Trim Bias / Avoid-Sell Bias / No Rating",
      "confidence": 0,
      "estimatedUpsideLowPct": 0,
      "estimatedUpsideBasePct": 0,
      "estimatedUpsideHighPct": 0,
      "estimatedHoldingMinDays": 0,
      "estimatedHoldingMaxDays": 0,
      "exitOrTrimRule": "研究池层面的退出/止盈规则",
      "invalidationCondition": "反证或失效条件",
      "thesisSummary": "本周 thesis",
      "hardEvidence": "2-3 条硬证据摘要",
      "whyNow": "为什么现在关注",
      "nextWeekCheck": "下周检查点",
      "evidencePackHref": "./report.evidence.md#ticker"
    }}
  ]
}}

硬性要求：
- 完整周报默认使用 Version A：老板决策页 + 证据包；`summaryMarkdown` 和 `reportMarkdown` 都必须从 `# 老板决策页` 开始。
- 老板决策页的研究动作表必须包含 Research Rating、Confidence、Est. Upside Range、Est. Holding Range、Exit / Trim Rule、Evidence Pack 和 Falsification。
- 每个 agent section 的 Downstream Handoff 必须保留在完整报告附录或 Agent Run Audit 中。
- 不得使用旧报告标题或旧报告 Top 5，除非本次 agent outputs 明确重新得出。
- 如果本次没有真实数据节点结果，最终结论必须降级为 partial / framework / research plan，不能伪装成完整实盘数据周报。
- evidenceMarkdown 中要列出所有 agent section 的状态，并说明哪些是模型生成、哪些外部数据节点缺失。
- 报告只能是研究用途，不输出目标价、仓位、下单或账户动作。
""".strip()


def append_run_audit(payload: dict[str, Any], sections: dict[str, str], user_prompt: str) -> dict[str, Any]:
    run_id = datetime.now().strftime("%Y%m%d-%H%M%S")
    audit_rows = [
        "| Step | Agent / Section | Status | Notes |",
        "|---:|---|---|---|",
    ]
    for index, name in enumerate(sections, start=1):
        status = infer_section_status(sections.get(name, ""))
        audit_rows.append(
            f"| {index} | {name} | {status} | 本次请求内独立模型调用或本地恢复节点；外部数据节点按 section 标注 partial/failed。 |"
        )

    audit = "\n".join(
        [
            "",
            "## Agent Run Audit",
            f"- Run ID：{run_id}",
            f"- User Prompt：{user_prompt}",
            "- Source：live model agent workflow, not cached report file",
            "",
            *audit_rows,
            "",
        ]
    )
    process_appendix = "\n\n".join(
        [
            "# 附录：本次 Agent 原始过程",
            *(
                f"## {name}\n\n{markdown.strip()}"
                for name, markdown in sections.items()
            ),
        ]
    )

    report = str(payload.get("reportMarkdown") or "")
    evidence = str(payload.get("evidenceMarkdown") or "")
    if "Agent Run Audit" not in report:
        report = f"{report.rstrip()}\n\n# 附录：Agent Run Audit{audit}"
    if "本次 Agent 原始过程" not in report:
        report = f"{report.rstrip()}\n\n{process_appendix}"
    if "Agent Run Audit" not in evidence:
        evidence = f"{evidence.rstrip()}\n\n{audit}"

    payload["reportMarkdown"] = report
    payload["summaryMarkdown"] = payload.get("summaryMarkdown") or extract_summary(report)
    payload["evidenceMarkdown"] = evidence
    payload["runMetadata"] = {
        "runId": run_id,
        "source": "live_agent_workflow",
        "userPrompt": user_prompt,
        "agents": list(sections.keys()),
    }
    pool = normalize_research_action_pool(payload, report, run_id=run_id, decision_date=today_iso())
    for item in pool:
        item["runId"] = item.get("runId") or run_id
        item["decisionDate"] = item.get("decisionDate") or today_iso()
    payload["researchActionPool"] = pool
    return payload


def prompt_label(user_prompt: str, max_chars: int = 42) -> str:
    label = re.sub(r"\s+", " ", str(user_prompt).strip()) or "本次研究"
    if label == DEFAULT_RESEARCH_INTENT:
        label = "美股全市场机会扫描"
    if len(label) <= max_chars:
        return label
    return label[:max_chars].rstrip() + "..."


def title_from_markdown(markdown: str, fallback: str) -> str:
    match = re.search(r"^#\s+(.+)$", markdown.strip(), re.MULTILINE)
    if match:
        return match.group(1).strip()
    return fallback


def ensure_boss_decision_page(markdown: str, user_prompt: str) -> str:
    content = str(markdown or "").strip()
    if not content:
        content = "## 本次状态\nFinal Narrative agent 未返回内容。"
    if re.match(r"^#\s*老板决策页", content):
        return content

    title = f"老板决策页：{prompt_label(user_prompt)}"
    return "\n\n".join(
        [
            f"# {title}",
            (
                "> 本报告由本次 agent workflow 生成。当前后端未接入外部实时数据节点，"
                "涉及新闻、论文、GitHub、行情、财务和舆情的内容必须以各 section 标注的 partial/failed 为准。"
            ),
            content,
        ]
    )


def infer_section_status(markdown: str) -> str:
    text = str(markdown or "")
    lowered = text.lower()
    explicit_status = re.search(
        r"(?:section\s*状态|section\s*status|本\s*section\s*状态|状态)\s*[:：]\s*`?\s*(complete|generated|partial|failed)\s*`?",
        lowered,
        re.IGNORECASE,
    )
    if explicit_status:
        status = explicit_status.group(1).lower()
        if status == "generated":
            return "complete"
        return status
    if re.search(r"(后端运行失败|运行失败|agent\s+failed|section\s+failed|traceback|exception)", lowered, re.IGNORECASE):
        return "failed"
    if (
        "partial" in lowered
        or "缺口" in text
        or "缺少" in text
        or "不可用" in text
        or "未接入" in text
        or "failed" in lowered
        or "失败" in text
    ):
        return "partial"
    return "complete"


def build_workflow_evidence(user_prompt: str, sections: dict[str, str], data_bundle: dict[str, Any] | None = None) -> str:
    title = prompt_label(user_prompt)
    evidence_rows = [
        "| ID | Source Type | Evidence Anchor | Notes |",
        "|---|---|---|---|",
    ]
    manifest_rows = [
        "| Step | Agent / Section | Status | Notes |",
        "|---:|---|---|---|",
    ]
    for index, (name, markdown) in enumerate(sections.items(), start=1):
        status = infer_section_status(markdown)
        evidence_rows.append(
            f"| A{index} | Agent Section | {name} | 本次请求内独立模型调用；不是历史 reports 缓存。 |"
        )
        manifest_rows.append(
            f"| {index} | {name} | {status} | 详细原文见主报告的「本次 Agent 原始过程」附录。 |"
        )

    if data_bundle and data_bundle.get("enabled"):
        data_status_lines = data_node_status_rows(data_bundle)
        node_note = "| Data Node Evidence Bundle | success | 后端已先采集结构化数据节点；各节点成功/部分/失败见下表。 |"
    else:
        data_status_lines = [
            "| Input Node | Status | Notes |",
            "|---|---|---|",
            "| News / Papers / GitHub / Market / Fundamentals / Sentiment Nodes | partial/failed | 数据节点未启用或未配置；不得把缺失数据伪装成事实。 |",
        ]
        node_note = "| Data Node Evidence Bundle | partial | 未启用或未配置。 |"

    return "\n".join(
        [
            f"# 证据包：{title}",
            "",
            "[返回主报告](./weekly-brief.md)",
            "",
            "## Evidence Index",
            *evidence_rows,
            "",
            "## Data Node Status",
            "| Input Node | Status | Notes |",
            "|---|---|---|",
            "| Model Agent Workflow | success | 已按本次用户提示词顺序运行各 agent section。 |",
            "| Historical Reports Cache | disabled | 本次响应不读取 `reports/` 旧报告作为结论来源。 |",
            node_note,
            "",
            "### Data Node Detail",
            *data_status_lines,
            "",
            "## Agent Section Manifest",
            *manifest_rows,
        ]
    )


def section_status_table(sections: dict[str, str]) -> str:
    rows = ["| Section | Status | Impact |", "|---|---|---|"]
    for name, markdown in sections.items():
        status = infer_section_status(markdown)
        if status == "complete":
            impact = "可作为流程证据，但仍需检查数据节点状态。"
        elif status == "partial":
            impact = "只能支持低置信研究框架，不能支持入池结论。"
        else:
            impact = "缺失关键输入，最终结论必须降级为 No Rating / partial。"
        rows.append(f"| {name} | {status} | {impact} |")
    return "\n".join(rows)


def fallback_seed_treatment_rows(user_prompt: str) -> str:
    rows = ["| Ticker / Theme | Treatment | Reason |", "|---|---|---|"]
    for item in fallback_research_universe(user_prompt):
        rows.append(
            f"| {item['ticker']} / {item['company']} | Defer / Watchlist Only | "
            "仅来自 fallback_seed_universe；缺少本周新闻、财务、行情和证据包确认。 |"
        )
    return "\n".join(rows)


def markdown_table_cell(value: Any) -> str:
    return safe_text(value).replace("|", "/").replace("\n", " ")


def candidate_evidence_items(bundle: dict[str, Any], ticker: str) -> list[dict[str, Any]]:
    ticker = normalize_ticker(ticker)
    items: list[dict[str, Any]] = []
    for key in [
        "finnhub_news",
        "finnhub_sentiment",
        "market_quotes",
        "technical_prices",
        "finnhub_fundamentals",
        "sec_filings",
    ]:
        for item in node_items(bundle, key):
            if normalize_ticker(safe_text(item.get("ticker"))) == ticker:
                items.append(item)
    return items


def global_ai_evidence_items(bundle: dict[str, Any]) -> list[dict[str, Any]]:
    return node_items(bundle, "arxiv_papers")[:2] + node_items(bundle, "github_projects")[:2]


def candidate_hard_evidence_summary(bundle: dict[str, Any], ticker: str) -> str:
    parts = []
    for item in candidate_evidence_items(bundle, ticker)[:3]:
        source = safe_text(item.get("source"))
        item_date = safe_text(item.get("date"))
        title = safe_text(item.get("title"))
        summary = safe_text(item.get("summary"))
        parts.append(f"{source} {item_date}: {title} {summary}".strip())
    if len(parts) < 2:
        for item in global_ai_evidence_items(bundle)[: 2 - len(parts)]:
            source = safe_text(item.get("source"))
            item_date = safe_text(item.get("date"))
            title = safe_text(item.get("title"))
            parts.append(f"{source} {item_date}: {title}".strip())
    return markdown_table_cell("；".join(parts[:3]) or "数据节点未返回 ticker-linked hard evidence。")


def candidate_technical_adjustment(bundle: dict[str, Any], ticker: str) -> int:
    ticker = normalize_ticker(ticker)
    summaries = [
        safe_text(item.get("summary")).lower()
        for item in node_items(bundle, "technical_prices")
        if normalize_ticker(safe_text(item.get("ticker"))) == ticker
    ]
    text = " ".join(summaries)
    if "above_20d_sma" in text or "above_50d_sma" in text:
        return 2
    if "below_20d_sma" in text or "below_50d_sma" in text:
        return -4
    return 0


def candidate_watch_metrics(bundle: dict[str, Any], ticker: str, *, rank: int, coverage: int) -> tuple[int, str]:
    counts = ticker_evidence_counts(bundle, ticker)
    breadth = sum(1 for key in ["finnhub_news", "market_quotes", "technical_prices", "finnhub_fundamentals", "sec_filings", "finnhub_sentiment"] if counts.get(key, 0) > 0)
    technical_adjustment = candidate_technical_adjustment(bundle, ticker)
    confidence = 48 + coverage * 2 + breadth * 3 + technical_adjustment - max(rank - 1, 0)
    confidence = max(50, min(74, confidence))

    if technical_adjustment < 0:
        holding_range = "3-7 days research review"
    elif breadth >= 5 and coverage >= 6:
        holding_range = "10-20 days research review"
    elif coverage >= 5:
        holding_range = "7-14 days research review"
    else:
        holding_range = "3-7 days research review"
    return int(confidence), holding_range


def build_local_data_version_a_report(user_prompt: str, sections: dict[str, str], bundle: dict[str, Any]) -> str:
    enough = data_node_complete_enough(bundle)
    scored = []
    for index, item in enumerate(research_candidate_universe(user_prompt, bundle), start=1):
        counts = ticker_evidence_counts(bundle, item["ticker"])
        coverage = sum(counts.values())
        scored.append((coverage, -index, item))
    scored.sort(reverse=True)
    ranked = [(coverage, item) for coverage, _neg_index, item in scored if enough and coverage >= 3][:5]

    action_rows = [
        "| Rank | Ticker / Theme | Research Rating | Confidence | Est. Upside Range | Est. Holding Range | Exit / Trim Rule | Why Now | Hard Evidence Summary | Evidence Pack | Falsification |",
        "|---:|---|---|---:|---|---|---|---|---|---|---|",
    ]
    if ranked:
        for rank, (coverage, item) in enumerate(ranked, start=1):
            confidence, holding_range = candidate_watch_metrics(bundle, item["ticker"], rank=rank, coverage=coverage)
            action_rows.append(
                "| {rank} | {ticker} / {company} | Hold-Watch | {confidence} | n/a：研究观察，不生成目标价 | "
                "{holding_range} | 仅用于下周复核；不代表交易退出/止盈规则 | "
                "{why_now}；本次数据节点命中 {coverage} 条 | {evidence} | "
                "[证据包](./weekly-brief.evidence.md#data-node-detail) | "
                "若新闻/论文/GitHub/行情/财务/舆情任两类节点回落或 SEC/财务不能支持叙事，则降级为 No Rating |".format(
                    rank=rank,
                    ticker=item["ticker"],
                    company=markdown_table_cell(item["company"]),
                    confidence=confidence,
                    holding_range=holding_range,
                    why_now=markdown_table_cell(item["why"]),
                    coverage=coverage,
                    evidence=candidate_hard_evidence_summary(bundle, item["ticker"]),
                )
            )
    else:
        action_rows.append(
            "| 1 | AI US Equity Research Workflow | No Rating | 0 | n/a | n/a | 不进入 Top 5 / 不进入 shadow ledger | "
            "数据节点已运行，但未达到完整入池阈值 | "
            f"{markdown_table_cell(missing_node_summary(bundle))} | "
            "[证据包](./weekly-brief.evidence.md#data-node-detail) | "
            "若 10 news / 5 papers / 5 GitHub / 5 technical/market 节点同时达标，可重新生成 Hold-Watch pool |"
        )

    ranked_tickers = {item["ticker"] for _coverage, item in ranked}
    not_core_rows = ["| Ticker / Theme | Treatment | Reason |", "|---|---|---|"]
    for coverage, _neg_index, item in scored:
        if item["ticker"] in ranked_tickers:
            continue
        treatment = "Defer / Needs Evidence" if enough else "No Rating / Data Node Gap"
        reason = f"真实节点命中 {coverage} 条；{item['why']}；未达到本轮 Top 5 证据阈值。"
        not_core_rows.append(f"| {item['ticker']} / {markdown_table_cell(item['company'])} | {treatment} | {markdown_table_cell(reason)} |")
    if len(not_core_rows) == 2:
        not_core_rows.append("| n/a | n/a | 本轮没有额外候选。 |")

    statuses = {name: infer_section_status(markdown) for name, markdown in sections.items()}
    risk_block = "\n".join(
        [
            f"- 最大反证：{markdown_table_cell(missing_node_summary(bundle))}",
            "- 下周只看：",
            "  1. AI 信息节点是否持续满足 10 news / 5 papers / 5 GitHub / 5 sentiment。",
            "  2. Fundamental 是否能用 SEC/IR/财务指标验证同一批 ticker 的收入、利润率或 capex 传导。",
            "  3. Technical 是否继续支持相对强弱，而不是只由新闻热度推动。",
        ]
    )
    return "\n\n".join(
        [
            f"# 老板决策页：{prompt_label(user_prompt)}",
            "## 1. 一句话结论",
            (
                "- 主结论：本次由后端 Data Node -> Agent Graph 直接编排生成，"
                + ("数据覆盖达到最低结构化阈值，可形成 Hold-Watch 研究观察池。" if ranked else "数据覆盖仍不足，最终降级为 No Rating / partial research plan。")
            ),
            f"- 整体置信度：{'中' if ranked else '低'}",
            f"- 本周研究裁决：{'保留 / Hold-Watch' if ranked else '暂缓 / No Rating'}",
            "",
            "## 2. 本周研究动作",
            "\n".join(action_rows),
            "",
            "## 3. 不进核心池",
            "\n".join(not_core_rows),
            "",
            "## 4. 最大风险与下周验证",
            risk_block,
            "",
            "# 附录：Data Node 与 Agent Graph 审计",
            "## Data Node Status",
            "\n".join(data_node_status_rows(bundle)),
            "",
            "## Agent Section Status",
            "\n".join(["| Section | Status |", "|---|---|"] + [f"| {name} | {status} |" for name, status in statuses.items()]),
            "",
            "## Downstream Handoff",
            "\n".join(
                [
                    "| Field | Content |",
                    "|---|---|",
                    f"| Handoff ID | local-data-version-a-{today_iso()} |",
                    f"| Input Status | {'complete' if ranked else 'partial'} |",
                    "| Decision Needed From Next Agent | 若继续跑模型型 Final Narrative，只能继承 Data Node Evidence Bundle 中有 source/date/link 的证据。 |",
                    "| Must-Carry Evidence | Data Node Status、ticker evidence coverage、Agent Section Status、缺口摘要。 |",
                    "| Key Assumptions | Fact：节点结果来自本次后端 API；Inference：覆盖高的 ticker 可进入研究观察；Hypothesis：仍需下周复核和更完整基本面验证。 |",
                    f"| Missing Proof | {markdown_table_cell(missing_node_summary(bundle))} |",
                    "| Downgrade Triggers | 任一关键节点 failed；来源缺链接；财务和技术面不能验证新闻/开源/论文叙事。 |",
                    "| Do-Not-Carry | 目标价、仓位、下单、自动交易、私人账户动作、把社媒或 GitHub 热度当作财务事实。 |",
                    "| Evidence Anchors | evidenceMarkdown 的 Data Node Detail。 |",
                ]
            ),
        ]
    )


def build_local_version_a_report(user_prompt: str, sections: dict[str, str]) -> str:
    failed_sections = [name for name, markdown in sections.items() if infer_section_status(markdown) == "failed"]
    partial_sections = [name for name, markdown in sections.items() if infer_section_status(markdown) == "partial"]
    failed_text = "、".join(failed_sections) if failed_sections else "无"
    partial_text = "、".join(partial_sections) if partial_sections else "无"
    action_table = "\n".join(
        [
            "| Rank | Ticker / Theme | Research Rating | Confidence | Est. Upside Range | Est. Holding Range | Exit / Trim Rule | Why Now | Hard Evidence Summary | Evidence Pack | Falsification |",
            "|---:|---|---|---:|---|---|---|---|---|---|---|",
            (
                "| 1 | AI US Equity Research Workflow | No Rating | 0 | n/a | n/a | "
                "不进入 Top 5 / 不进入 shadow ledger | 真实运行暴露数据和模型调用缺口 | "
                f"failed sections：{failed_text}；partial sections：{partial_text} | "
                "[证据包](./weekly-brief.evidence.md#agent-section-manifest) | "
                "若新闻/论文/GitHub/行情/财务/舆情节点成功返回并通过 Reflection，可重新评级 |"
            ),
        ]
    )
    handoff_table = "\n".join(
        [
            "| Field | Content |",
            "|---|---|",
            f"| Handoff ID | local-version-a-{today_iso()} |",
            "| Input Status | partial |",
            "| Decision Needed From Next Agent | 补齐真实数据节点后重新运行完整周报；本次不进入 Top 5 或 paper ledger。 |",
            "| Must-Carry Evidence | section 状态、失败原因、fallback_seed_universe、证据包 manifest。 |",
            "| Key Assumptions | Fact：真实运行发生 section partial/failed；Inference：当前不能形成投资结论；Hypothesis：补齐数据后可重跑。 |",
            "| Missing Proof | 新闻、论文、GitHub、舆情、SEC/IR、财务、行情、Reflection 完整输出。 |",
            "| Downgrade Triggers | 任一关键 section failed；数据节点无链接；无法交叉验证；Final Narrative 超时。 |",
            "| Do-Not-Carry | Research Buy、Top 5 入池、目标价、仓位、下单、未验证 ticker 结论。 |",
            "| Evidence Anchors | evidenceMarkdown 的 Agent Section Manifest 与 Data Node Status。 |",
        ]
    )
    risk_block = "\n".join(
        [
            "- 最大反证：关键数据节点和 Final Narrative 能稳定返回，且信息、基本面、技术面、Reflection 至少三方支持同一候选。",
            "- 下周只看：",
            "  1. AI 信息与舆情节点是否能返回 10 news / 5 papers / 5 GitHub / 5 sentiment。",
            "  2. 基本面和技术面是否能用真实 SEC/IR/行情数据验证 fallback candidates。",
            "  3. Reflection 是否能在 Wood vs Buffett 辩论后保留至少 1 个高置信候选。",
        ]
    )
    return "\n\n".join(
        [
            f"# 老板决策页：{prompt_label(user_prompt)}",
            "## 1. 一句话结论",
            (
                "- 主结论：本次真实 API workflow 没有形成可发布的完整投资结论；"
                "由于关键数据节点不足或 section 失败，输出降级为 Version A partial research plan。"
            ),
            "- 整体置信度：低",
            "- 本周研究裁决：暂缓",
            "",
            "## 2. 本周研究动作",
            action_table,
            "",
            "## 3. 不进核心池",
            fallback_seed_treatment_rows(user_prompt),
            "",
            "## 4. 最大风险与下周验证",
            risk_block,
            "",
            "# 证据索引",
            "完整证据链写入同名 evidence 子文件；本页只保留运行质量和降级原因。",
            "",
            "## 5. 上游 Section 状态",
            section_status_table(sections),
            "",
            "## 6. Downstream Handoff",
            handoff_table,
        ]
    )


def should_use_local_final_narrative(sections: dict[str, str]) -> bool:
    critical = ["AI 信息与舆情", "Reflection"]
    return any(infer_section_status(sections.get(name, "")) == "failed" for name in critical)


def build_workflow_payload_from_sections(user_prompt: str, sections: dict[str, str], data_bundle: dict[str, Any] | None = None) -> dict[str, Any]:
    final_section = sections.get("Final Narrative") or ""
    if infer_section_status(final_section) == "failed" or not final_section.strip():
        if data_bundle and data_bundle.get("enabled"):
            report_source = build_local_data_version_a_report(user_prompt, sections, data_bundle)
        else:
            report_source = build_local_version_a_report(user_prompt, sections)
    else:
        report_source = final_section
    report = ensure_boss_decision_page(report_source, user_prompt)
    title = title_from_markdown(report, f"老板决策页：{prompt_label(user_prompt)}")
    payload: dict[str, Any] = {
        "title": title,
        "summaryMarkdown": extract_summary(report),
        "reportMarkdown": report,
        "evidenceMarkdown": build_workflow_evidence(user_prompt, sections, data_bundle),
    }
    return append_run_audit(payload, sections, user_prompt)


def workflow_engine_name(langgraph_available: bool = False) -> str:
    return "langgraph.StateGraph" if langgraph_available else "local.StateGraphFallback"

#!/usr/bin/env python3
"""Local API adapter for the weekly AI US equity research frontend.

The browser should never receive model API keys. This server keeps keys on the
local machine, exposes a small CORS-safe API to the static frontend, and either
proxies an existing weekly-brief backend or calls an OpenAI-compatible chat API.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import csv
import html
import json
import os
import queue
import re
import sys
import threading
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import unquote

try:
    import requests
except ImportError:  # pragma: no cover - surfaced via health/error response
    requests = None

try:
    from langgraph.graph import END as LANGGRAPH_END
    from langgraph.graph import START as LANGGRAPH_START
    from langgraph.graph import StateGraph as LangGraphStateGraph

    LANGGRAPH_AVAILABLE = True
except ImportError:  # pragma: no cover - optional dependency, local fallback below
    LANGGRAPH_AVAILABLE = False
    LANGGRAPH_START = "__start__"
    LANGGRAPH_END = "__end__"
    LangGraphStateGraph = None


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PORT = 8787
DEFAULT_RESEARCH_INTENT = "请先按美股全市场周报流程做一次机会扫描，默认发现最多 8 个候选，输出中文研究周报和双跳证据。"
FALLBACK_RESEARCH_UNIVERSES: dict[str, list[dict[str, str]]] = {
    "consumer": [
        {"ticker": "WMT", "company": "Walmart", "why": "零售与必需消费需求验证入口"},
        {"ticker": "COST", "company": "Costco", "why": "会员制零售与消费韧性验证入口"},
        {"ticker": "PG", "company": "Procter & Gamble", "why": "日用品与定价权验证入口"},
        {"ticker": "KO", "company": "Coca-Cola", "why": "饮料与品牌现金流验证入口"},
        {"ticker": "PEP", "company": "PepsiCo", "why": "食品饮料与渠道库存验证入口"},
        {"ticker": "MCD", "company": "McDonald's", "why": "餐饮消费与客流验证入口"},
        {"ticker": "HD", "company": "Home Depot", "why": "家装与地产后周期验证入口"},
        {"ticker": "NKE", "company": "Nike", "why": "可选消费与品牌库存验证入口"},
    ],
    "ai": [
        {"ticker": "NVDA", "company": "NVIDIA", "why": "AI 加速器与数据中心资本开支验证入口"},
        {"ticker": "MSFT", "company": "Microsoft", "why": "云与企业 AI 落地验证入口"},
        {"ticker": "AVGO", "company": "Broadcom", "why": "AI 网络与定制芯片验证入口"},
        {"ticker": "AMD", "company": "AMD", "why": "AI GPU 竞争格局验证入口"},
        {"ticker": "TSM", "company": "TSMC", "why": "先进制程与供应链验证入口"},
        {"ticker": "ASML", "company": "ASML", "why": "半导体设备周期验证入口"},
        {"ticker": "GOOGL", "company": "Alphabet", "why": "AI 搜索、云和广告传导验证入口"},
        {"ticker": "AMZN", "company": "Amazon", "why": "云基础设施与 AI 应用需求验证入口"},
    ],
    "finance": [
        {"ticker": "JPM", "company": "JPMorgan Chase", "why": "大型银行信贷与净息差验证入口"},
        {"ticker": "BAC", "company": "Bank of America", "why": "利率敏感性与消费信贷验证入口"},
        {"ticker": "GS", "company": "Goldman Sachs", "why": "投行业务与风险偏好验证入口"},
        {"ticker": "MS", "company": "Morgan Stanley", "why": "财富管理与投行业务验证入口"},
        {"ticker": "V", "company": "Visa", "why": "支付量与跨境消费验证入口"},
        {"ticker": "MA", "company": "Mastercard", "why": "支付网络与消费强度验证入口"},
        {"ticker": "AXP", "company": "American Express", "why": "高端消费与信用质量验证入口"},
        {"ticker": "BLK", "company": "BlackRock", "why": "资产管理资金流验证入口"},
    ],
    "broad": [
        {"ticker": "MSFT", "company": "Microsoft", "why": "大型科技与企业软件验证入口"},
        {"ticker": "NVDA", "company": "NVIDIA", "why": "AI 与半导体景气验证入口"},
        {"ticker": "AMZN", "company": "Amazon", "why": "云、零售和消费需求验证入口"},
        {"ticker": "GOOGL", "company": "Alphabet", "why": "广告、云与 AI 应用验证入口"},
        {"ticker": "META", "company": "Meta Platforms", "why": "广告与 AI 推荐系统验证入口"},
        {"ticker": "JPM", "company": "JPMorgan Chase", "why": "金融与信贷周期验证入口"},
        {"ticker": "COST", "company": "Costco", "why": "消费韧性验证入口"},
        {"ticker": "LLY", "company": "Eli Lilly", "why": "医疗创新与防御成长验证入口"},
    ],
}
AGENT_WORKFLOW = [
    ("intent_router", "Intent Router", "agents/08-intent-router.md"),
    ("stock_discovery", "Stock Discovery", "agents/00-stock-discovery-analyst.md"),
    ("information_sentiment", "AI 信息与舆情", "agents/02-ai-information-sentiment-analyst.md"),
    ("fundamental", "Fundamental", "agents/03-fundamental-analyst.md"),
    ("technical", "Technical", "agents/04-technical-analyst.md"),
    ("reflection", "Reflection", "agents/05-reflection-judge.md"),
    ("final_narrative", "Final Narrative", "agents/01-ai-trend-narrative-analyst.md"),
    ("paper_attribution", "Paper Attribution", "agents/07-paper-portfolio-attribution-agent.md"),
]
POND_DIR = ROOT / "data" / "conclusion-pool"
REPORT_HISTORY_DIR = Path(os.environ.get("REPORT_HISTORY_DIR") or ROOT / "data" / "report-history")
POND_STATUSES = {"candidate", "open", "closed", "archived", "price_data_failed"}
POND_COLUMNS = [
    "run_id",
    "decision_date",
    "review_week",
    "thesis_id",
    "rank",
    "ticker",
    "company",
    "action_rating",
    "confidence",
    "selected_by_user",
    "selected_date",
    "selection_notes",
    "expected_entry_date",
    "entry_rule",
    "expected_entry_price",
    "actual_entry_date",
    "actual_entry_price",
    "planned_review_date",
    "actual_review_date",
    "review_exit_price",
    "estimated_upside_low_pct",
    "estimated_upside_base_pct",
    "estimated_upside_high_pct",
    "estimated_holding_min_days",
    "estimated_holding_max_days",
    "exit_or_trim_bias",
    "trim_take_profit_range_pct",
    "invalidation_condition",
    "benchmark_primary",
    "benchmark_entry_price",
    "benchmark_review_price",
    "actual_return_pct",
    "benchmark_return_pct",
    "excess_return_pct",
    "expected_vs_actual",
    "primary_attribution",
    "next_week_action",
    "thesis_summary",
    "hard_evidence",
    "why_now",
    "next_week_check",
    "evidence_pack_href",
    "status",
    "notes",
]


def load_env_file(path: Path, *, override: bool = True) -> None:
    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if override or key not in os.environ:
            os.environ[key] = value


def env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def configured_api_key() -> str:
    key_env = env("LLM_API_KEY_ENV", "OPENAI_API_KEY")
    return env(key_env) or env("OPENAI_API_KEY") or env("ANTHROPIC_API_KEY")


def configured_base_url() -> str:
    return env("OPENAI_BASE_URL") or env("LLM_BASE_URL") or "https://api.openai.com/v1"


def configured_model() -> str:
    return env("OPENAI_MODEL") or env("LLM_MODEL") or "gpt-5.5"


def configured_fast_model() -> str:
    return env("WEEKLY_BRIEF_SECTION_MODEL") or env("LLM_FAST_MODEL") or env("OPENAI_FAST_MODEL") or configured_model()


def request_user_prompt(body: dict[str, Any]) -> str:
    prompt = body.get("prompt") or body.get("user_prompt") or body.get("intent") or ""
    return str(prompt).strip() or DEFAULT_RESEARCH_INTENT


def fallback_universe_key(user_prompt: str) -> str:
    prompt = str(user_prompt or "").lower()
    if re.search(r"消费|consumer|retail|staple|discretionary|传统|食品|饮料|零售|餐饮|品牌", prompt, re.IGNORECASE):
        return "consumer"
    if re.search(r"金融|银行|支付|保险|券商|finance|bank|payment|credit", prompt, re.IGNORECASE):
        return "finance"
    if re.search(r"\bai\b|人工智能|半导体|芯片|算力|数据中心|gpu|云|软件|科技|semiconductor", prompt, re.IGNORECASE):
        return "ai"
    return "broad"


def fallback_research_universe(user_prompt: str) -> list[dict[str, str]]:
    return [dict(item) for item in FALLBACK_RESEARCH_UNIVERSES[fallback_universe_key(user_prompt)]]


def fallback_universe_markdown(user_prompt: str) -> str:
    rows = [
        "| Ticker | Company | Why included | Source Type |",
        "|---|---|---|---|",
    ]
    for item in fallback_research_universe(user_prompt):
        rows.append(
            "| {ticker} | {company} | {why} | fallback_seed_universe，"
            "仅作研究脚手架；不是模型发现结论、买卖建议或实时数据。 |".format(**item)
        )
    return "\n".join(rows)


def fallback_ticker_list(user_prompt: str) -> str:
    return ", ".join(item["ticker"] for item in fallback_research_universe(user_prompt))


def redact_url(value: str) -> str:
    if not value:
        return ""
    return re.sub(r"(?<=://)[^/@]+@", "***@", value)


def read_text(path: str, max_chars: int) -> str:
    file_path = ROOT / path
    if not file_path.exists():
        return ""
    text = file_path.read_text(encoding="utf-8", errors="replace")
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "\n\n[truncated]\n"


def output_standard_text(max_chars: int = 18000) -> str:
    return read_text("docs/research-report-output-standard.md", max_chars)


def compact_output_standard_text() -> str:
    return """
# Research Report Output Standard

默认最终报告结构：Version A：老板决策页 + 证据包。

## Version A required first page
# 老板决策页：{report_title}

## 1. 一句话结论
- 主结论：
- 整体置信度：高 / 中 / 低
- 本周研究裁决：强确认 / 保留 / 降级 / 暂缓 / 剔除

## 2. 本周研究动作
| Rank | Ticker / Theme | Research Rating | Confidence | Est. Upside Range | Est. Holding Range | Exit / Trim Rule | Why Now | Hard Evidence Summary | Evidence Pack | Falsification |
|---:|---|---|---:|---|---|---|---|---|---|---|

## 3. 不进核心池
| Ticker / Theme | Treatment | Reason |
|---|---|---|

## 4. 最大风险与下周验证
- 最大反证：
- 下周只看：
  1.
  2.
  3.

## Hard limits
- 不以 Intent Route Plan、运行日志、数据节点状态、工具失败、质量检查开头。
- 不把长证据表、长新闻/论文/GitHub/舆情清单塞进老板决策页。
- 不输出真实下单、账户操作、仓位比例、资金分配、再平衡或 broker 指令。
- 不输出无估值方法和风险说明支撑的 target price；使用 estimated_upside_range_pct 且标明研究情景。
- 不承诺收益，不写必涨/必跌/确定跑赢。
- 不把新闻、KOL、播客、社媒热度、论文、GitHub stars 或 K 线强势当作公司收入、利润或投资价值证明。
- 不混淆 Fact / Inference / Hypothesis / Opinion / Market Signal / Data Gap。
- 不凑满 Top 5；低于门槛时宁可少于 5 个。
- 不隐藏数据节点失败；失败必须降低置信度或降级为 partial。

## Downstream Handoff
每个 agent section 必须包含：
| Field | Content |
|---|---|
| Handoff ID | agent-date-theme/ticker |
| Input Status | complete / partial / failed |
| Decision Needed From Next Agent |  |
| Must-Carry Evidence |  |
| Key Assumptions | Fact / Inference / Hypothesis 分列 |
| Missing Proof |  |
| Downgrade Triggers |  |
| Do-Not-Carry | 下游不能继承的噪音、弱证据或禁区 |
| Evidence Anchors | 源链接、上游 section anchor 或 evidence subfile anchor |
""".strip()


def truncate_text(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "\n\n[truncated]\n"


def today_iso() -> str:
    return date.today().isoformat()


def safe_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def snake_from_camel(name: str) -> str:
    return re.sub(r"(?<!^)([A-Z])", r"_\1", name).lower()


def compact_percent(value: Any) -> str:
    text = safe_text(value).replace("%", "")
    match = re.search(r"-?\d+(?:\.\d+)?", text)
    return match.group(0) if match else ""


def parse_float(value: Any) -> float | None:
    text = compact_percent(value)
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def parse_iso_date(value: Any) -> date | None:
    text = safe_text(value)
    if not text:
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def next_weekday_on_or_after(start: date, weekday: int) -> date:
    days = (weekday - start.weekday()) % 7
    return start + timedelta(days=days)


def next_weekday_after(start: date, weekday: int) -> date:
    days = (weekday - start.weekday()) % 7
    if days == 0:
        days = 7
    return start + timedelta(days=days)


def expected_entry_for_decision(decision_date: str) -> str:
    parsed = parse_iso_date(decision_date) or date.today()
    return next_weekday_after(parsed, 0).isoformat()


def planned_review_for_entry(entry_date: str) -> str:
    parsed = parse_iso_date(entry_date) or date.today()
    return next_weekday_on_or_after(parsed, 4).isoformat()


def review_week_for_date(value: str) -> str:
    parsed = parse_iso_date(value) or date.today()
    year, week, _weekday = parsed.isocalendar()
    return f"{year}-W{week:02d}"


def pond_file_for_date(decision_date: str) -> Path:
    return POND_DIR / f"conclusion-pool-{decision_date[:10] or today_iso()}.csv"


def pond_files() -> list[Path]:
    if not POND_DIR.exists():
        return []
    return sorted(
        path
        for path in POND_DIR.glob("conclusion-pool-*.csv")
        if path.name != "conclusion-pool-template.csv"
    )


def read_pond_file(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = []
        for raw in reader:
            row = {column: safe_text(raw.get(column, "")) for column in POND_COLUMNS}
            for key, value in raw.items():
                if key and key not in row:
                    row[key] = safe_text(value)
            rows.append(row)
        return rows


def write_pond_file(path: Path, rows: list[dict[str, str]]) -> None:
    POND_DIR.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=POND_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({column: safe_text(row.get(column, "")) for column in POND_COLUMNS})


def load_pond_entries() -> list[tuple[Path, dict[str, str]]]:
    entries: list[tuple[Path, dict[str, str]]] = []
    for path in pond_files():
        entries.extend((path, row) for row in read_pond_file(path))
    return entries


def pond_row_id(row: dict[str, str]) -> str:
    return "|".join(
        [
            safe_text(row.get("run_id")),
            safe_text(row.get("thesis_id")),
            safe_text(row.get("ticker")).upper(),
        ]
    )


def canonical_status(value: str, fallback: str = "open") -> str:
    status = safe_text(value).lower()
    return status if status in POND_STATUSES else fallback


def camelize_row(row: dict[str, str]) -> dict[str, Any]:
    result: dict[str, Any] = {"id": pond_row_id(row)}
    for key, value in row.items():
        camel = re.sub(r"_([a-z])", lambda match: match.group(1).upper(), key)
        result[camel] = value

    for key in [
        "confidence",
        "expectedEntryPrice",
        "actualEntryPrice",
        "reviewExitPrice",
        "estimatedUpsideLowPct",
        "estimatedUpsideBasePct",
        "estimatedUpsideHighPct",
        "benchmarkEntryPrice",
        "benchmarkReviewPrice",
        "actualReturnPct",
        "benchmarkReturnPct",
        "excessReturnPct",
    ]:
        number = parse_float(result.get(key))
        result[key] = number if number is not None else None

    result["status"] = canonical_status(safe_text(result.get("status")))
    return result


def pond_payload() -> dict[str, Any]:
    entries = load_pond_entries()
    rows = [row for _path, row in entries]
    active_statuses = {"candidate", "open", "price_data_failed"}
    open_rows = [
        row
        for row in rows
        if row.get("selected_by_user") == "yes" and canonical_status(row.get("status")) in active_statuses
    ]
    history_rows = [
        row
        for row in rows
        if canonical_status(row.get("status")) in {"closed", "archived"}
    ]

    open_rows.sort(key=lambda row: (row.get("selected_date"), row.get("decision_date")), reverse=True)
    history_rows.sort(key=lambda row: (row.get("actual_review_date"), row.get("decision_date")), reverse=True)

    groups: dict[str, list[dict[str, Any]]] = {}
    for row in history_rows:
        key = row.get("decision_date") or "unknown"
        groups.setdefault(key, []).append(camelize_row(row))

    latest_refresh = max(
        [safe_text(row.get("actual_review_date")) for row in rows if safe_text(row.get("actual_review_date"))],
        default="",
    )

    return {
        "summary": {
            "openCount": len(open_rows),
            "historyCount": len(history_rows),
            "recentTickers": [row.get("ticker", "") for row in open_rows[:3] if row.get("ticker")],
            "latestRefreshDate": latest_refresh,
            "storage": "data/conclusion-pool",
        },
        "openItems": [camelize_row(row) for row in open_rows],
        "historyGroups": [
            {"decisionDate": decision_date, "items": items}
            for decision_date, items in sorted(groups.items(), reverse=True)
        ],
    }


def get_candidate_field(candidate: dict[str, Any], *names: str) -> str:
    for name in names:
        value = candidate.get(name)
        if value is not None and safe_text(value):
            return safe_text(value)
        snake = snake_from_camel(name)
        value = candidate.get(snake)
        if value is not None and safe_text(value):
            return safe_text(value)
    return ""


def normalize_ticker(value: Any) -> str:
    text = safe_text(value).upper()
    match = re.search(r"\b[A-Z][A-Z0-9.-]{0,7}\b", text)
    return match.group(0) if match else text[:12]


def normalize_pond_candidate(body: dict[str, Any]) -> dict[str, str]:
    candidate = body.get("candidate") if isinstance(body.get("candidate"), dict) else body
    if not isinstance(candidate, dict):
        raise ValueError("candidate must be an object")

    ticker = normalize_ticker(get_candidate_field(candidate, "ticker", "symbol", "tickerTheme", "tickerOrTheme"))
    if not ticker:
        raise ValueError("candidate.ticker is required")

    decision_date = get_candidate_field(candidate, "decisionDate") or today_iso()
    entry_date = get_candidate_field(candidate, "expectedEntryDate") or expected_entry_for_decision(decision_date)
    review_date = get_candidate_field(candidate, "plannedReviewDate") or planned_review_for_entry(entry_date)
    run_id = (
        get_candidate_field(candidate, "runId")
        or get_candidate_field(body, "runId")
        or f"pond-{decision_date.replace('-', '')}"
    )
    thesis_id = get_candidate_field(candidate, "thesisId") or f"{ticker}-{get_candidate_field(candidate, 'rank') or 'watch'}"

    low = get_candidate_field(candidate, "estimatedUpsideLowPct")
    base = get_candidate_field(candidate, "estimatedUpsideBasePct")
    high = get_candidate_field(candidate, "estimatedUpsideHighPct")
    if not any([low, base, high]):
        low, base, high = parse_upside_range(get_candidate_field(candidate, "estimatedUpsideRange"))

    return {
        "run_id": run_id,
        "decision_date": decision_date[:10],
        "review_week": review_week_for_date(review_date),
        "thesis_id": thesis_id,
        "rank": get_candidate_field(candidate, "rank"),
        "ticker": ticker,
        "company": get_candidate_field(candidate, "company", "name"),
        "action_rating": get_candidate_field(candidate, "actionRating", "rating"),
        "confidence": compact_percent(get_candidate_field(candidate, "confidence")),
        "selected_by_user": "yes",
        "selected_date": today_iso(),
        "selection_notes": get_candidate_field(body, "selectionNotes", "notes"),
        "expected_entry_date": entry_date[:10],
        "entry_rule": get_candidate_field(candidate, "entryRule") or "next_monday_regular_session_close",
        "planned_review_date": review_date[:10],
        "estimated_upside_low_pct": compact_percent(low),
        "estimated_upside_base_pct": compact_percent(base),
        "estimated_upside_high_pct": compact_percent(high),
        "estimated_holding_min_days": compact_percent(get_candidate_field(candidate, "estimatedHoldingMinDays")),
        "estimated_holding_max_days": compact_percent(get_candidate_field(candidate, "estimatedHoldingMaxDays")),
        "exit_or_trim_bias": get_candidate_field(candidate, "exitOrTrimRule", "exitOrTrimBias"),
        "invalidation_condition": get_candidate_field(candidate, "invalidationCondition", "invalidation"),
        "benchmark_primary": get_candidate_field(candidate, "benchmarkPrimary") or "QQQ",
        "thesis_summary": get_candidate_field(candidate, "thesisSummary", "summary"),
        "hard_evidence": get_candidate_field(candidate, "hardEvidence", "hardEvidenceSummary"),
        "why_now": get_candidate_field(candidate, "whyNow"),
        "next_week_check": get_candidate_field(candidate, "nextWeekCheck"),
        "evidence_pack_href": get_candidate_field(candidate, "evidencePackHref", "evidencePack"),
        "status": "open",
    }


def select_pond_candidate(body: dict[str, Any]) -> dict[str, Any]:
    row = normalize_pond_candidate(body)
    path = pond_file_for_date(row["decision_date"])
    rows = read_pond_file(path)
    target_key = pond_row_id(row)
    updated = False

    for index, existing in enumerate(rows):
        if pond_row_id(existing) == target_key:
            merged = {**existing, **{key: value for key, value in row.items() if value != ""}}
            merged["selected_by_user"] = "yes"
            merged["selected_date"] = today_iso()
            merged["status"] = "open"
            rows[index] = merged
            updated = True
            break

    if not updated:
        rows.append(row)

    write_pond_file(path, rows)
    return {"ok": True, "item": camelize_row(row), **pond_payload()}


def yahoo_symbol(ticker: str) -> str:
    return normalize_ticker(ticker).replace(".", "-")


def fetch_daily_closes(ticker: str, *, timeout_seconds: float | None = None) -> list[tuple[str, float]]:
    if requests is None:
        raise RuntimeError("Python package 'requests' is required")
    symbol = yahoo_symbol(ticker)
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
    response = requests.get(
        url,
        params={"range": "6mo", "interval": "1d", "events": "history"},
        headers={"Accept": "application/json", "User-Agent": "weekly-brief-pond/0.1"},
        timeout=timeout_seconds if timeout_seconds is not None else 12,
    )
    response.raise_for_status()
    data = response.json()
    result = ((data.get("chart") or {}).get("result") or [None])[0]
    if not isinstance(result, dict):
        raise RuntimeError(f"No price result for {ticker}")
    timestamps = result.get("timestamp") or []
    quote = (((result.get("indicators") or {}).get("quote") or [{}])[0])
    closes = quote.get("close") or []
    prices: list[tuple[str, float]] = []
    for timestamp, close in zip(timestamps, closes):
        if close is None:
            continue
        prices.append((date.fromtimestamp(int(timestamp)).isoformat(), float(close)))
    if not prices:
        raise RuntimeError(f"No regular-session close data for {ticker}")
    return prices


def close_on_or_after(prices: list[tuple[str, float]], target_date: str) -> tuple[str, float] | None:
    target = parse_iso_date(target_date)
    if target is None:
        return prices[-1] if prices else None
    for price_date, close in prices:
        parsed = parse_iso_date(price_date)
        if parsed and parsed >= target:
            return price_date, close
    return None


def compute_expected_vs_actual(row: dict[str, str], actual_return: float | None) -> str:
    if actual_return is None:
        return "pending_entry"
    low = parse_float(row.get("estimated_upside_low_pct"))
    high = parse_float(row.get("estimated_upside_high_pct"))
    if low is not None and high is not None and low <= actual_return <= high:
        return "in_range"
    if high is not None and actual_return > high:
        return "above_range"
    if low is not None and 0 < actual_return < low:
        return "direction_right_below_range"
    if actual_return >= 0:
        return "interim_on_track"
    return "direction_wrong"


def refresh_pond_prices() -> dict[str, Any]:
    grouped: dict[Path, list[dict[str, str]]] = {}
    for path, row in load_pond_entries():
        grouped.setdefault(path, []).append(row)

    refreshed = 0
    failed = 0
    cache: dict[str, list[tuple[str, float]]] = {}

    for path, rows in grouped.items():
        changed = False
        for row in rows:
            status = canonical_status(row.get("status"))
            if row.get("selected_by_user") != "yes" or status not in {"open", "price_data_failed"}:
                continue

            ticker = normalize_ticker(row.get("ticker"))
            try:
                if ticker not in cache:
                    cache[ticker] = fetch_daily_closes(ticker)
                prices = cache[ticker]
                latest_date, latest_close = prices[-1]
                entry = close_on_or_after(prices, row.get("expected_entry_date") or row.get("decision_date"))

                if entry is None:
                    row["expected_vs_actual"] = "pending_entry"
                    row["status"] = "open"
                    refreshed += 1
                    changed = True
                    continue

                entry_date, entry_close = entry
                row["actual_entry_date"] = row.get("actual_entry_date") or entry_date
                row["actual_entry_price"] = row.get("actual_entry_price") or f"{entry_close:.4f}"
                row["actual_review_date"] = latest_date
                row["review_exit_price"] = f"{latest_close:.4f}"

                entry_price = parse_float(row.get("actual_entry_price"))
                actual_return = None
                if entry_price and entry_price > 0:
                    actual_return = ((latest_close - entry_price) / entry_price) * 100
                    row["actual_return_pct"] = f"{actual_return:.2f}"

                benchmark = normalize_ticker(row.get("benchmark_primary") or "QQQ")
                if benchmark:
                    try:
                        if benchmark not in cache:
                            cache[benchmark] = fetch_daily_closes(benchmark)
                        benchmark_prices = cache[benchmark]
                        benchmark_entry = close_on_or_after(benchmark_prices, row["actual_entry_date"])
                        benchmark_latest = benchmark_prices[-1]
                        if benchmark_entry:
                            row["benchmark_entry_price"] = f"{benchmark_entry[1]:.4f}"
                            row["benchmark_review_price"] = f"{benchmark_latest[1]:.4f}"
                            benchmark_return = ((benchmark_latest[1] - benchmark_entry[1]) / benchmark_entry[1]) * 100
                            row["benchmark_return_pct"] = f"{benchmark_return:.2f}"
                            if actual_return is not None:
                                row["excess_return_pct"] = f"{actual_return - benchmark_return:.2f}"
                    except Exception:
                        pass

                row["expected_vs_actual"] = compute_expected_vs_actual(row, actual_return)
                row["status"] = "open"
                refreshed += 1
                changed = True
            except Exception as exc:  # noqa: BLE001 - surfaced in pond notes
                row["status"] = "price_data_failed"
                row["expected_vs_actual"] = "price_data_failed"
                row["notes"] = f"Price refresh failed: {exc}"
                failed += 1
                changed = True

        if changed:
            write_pond_file(path, rows)

    return {"ok": True, "refreshed": refreshed, "failed": failed, **pond_payload()}


DATA_NODE_REQUIRED_COUNTS = {
    "finnhub_news": 10,
    "arxiv_papers": 5,
    "github_projects": 5,
    "finnhub_sentiment": 5,
    "market_quotes": 5,
    "technical_prices": 5,
    "sec_filings": 3,
    "finnhub_fundamentals": 3,
    "fred_macro": 2,
}

SEC_CIK_BY_TICKER = {
    "AAPL": "0000320193",
    "AMD": "0000002488",
    "AMZN": "0001018724",
    "AVGO": "0001730168",
    "BAC": "0000070858",
    "BLK": "0001364742",
    "COST": "0000909832",
    "GOOGL": "0001652044",
    "GS": "0000886982",
    "HD": "0000354950",
    "JPM": "0000019617",
    "KO": "0000021344",
    "LLY": "0000059478",
    "MA": "0001141391",
    "MCD": "0000063908",
    "META": "0001326801",
    "MS": "0000895421",
    "MSFT": "0000789019",
    "NKE": "0000320187",
    "NVDA": "0001045810",
    "PEP": "0000077476",
    "PG": "0000080424",
    "V": "0001403161",
    "WMT": "0000104169",
}


def first_env(*names: str) -> str:
    for name in names:
        value = env(name)
        if value:
            return value
    return ""


def data_node_timeout_seconds() -> float:
    return float(env("WEEKLY_BRIEF_DATA_NODE_TIMEOUT", "8"))


def data_node_enabled() -> bool:
    configured = any(
        first_env(name)
        for name in [
            "FINNHUB_API_KEY",
            "ALPHA_VANTAGE_API_KEY",
            "ALPHA_VANTAGE",
            "FRED_API_KEY",
            "SEC_EDGAR_USER_AGENT",
            "TRANSCRIPT_API_KEY",
            "SCRAPECREATORS_API_KEY",
        ]
    )
    value = env("WEEKLY_BRIEF_ENABLE_DATA_NODES", "auto").lower()
    if value in {"0", "false", "no", "off"}:
        return False
    if value in {"1", "true", "yes", "on"}:
        return True
    return configured


def local_data_sections_enabled(bundle: dict[str, Any]) -> bool:
    value = env("WEEKLY_BRIEF_LOCAL_DATA_SECTIONS", "auto").lower()
    if value in {"0", "false", "no", "off"}:
        return False
    if value in {"1", "true", "yes", "on"}:
        return True
    return bool(bundle.get("enabled") and bundle.get("configuredApis"))


def data_node_result(
    key: str,
    label: str,
    source_type: str,
    items: list[dict[str, Any]] | None = None,
    *,
    required: int | None = None,
    status: str | None = None,
    error: str = "",
) -> dict[str, Any]:
    rows = items or []
    required_count = DATA_NODE_REQUIRED_COUNTS.get(key, 0) if required is None else required
    if status is None:
        if rows and (required_count <= 0 or len(rows) >= required_count):
            status = "success"
        elif rows:
            status = "partial"
        else:
            status = "failed" if error else "partial"
    return {
        "key": key,
        "label": label,
        "sourceType": source_type,
        "status": status,
        "required": required_count,
        "count": len(rows),
        "items": rows,
        "error": safe_text(error),
    }


def request_json_value(url: str, *, params: dict[str, Any] | None = None, headers: dict[str, str] | None = None) -> Any:
    if requests is None:
        raise RuntimeError("Python package 'requests' is required")
    response = requests.get(url, params=params or {}, headers=headers or {"Accept": "application/json"}, timeout=data_node_timeout_seconds())
    response.raise_for_status()
    return response.json()


def request_json(url: str, *, params: dict[str, Any] | None = None, headers: dict[str, str] | None = None) -> dict[str, Any]:
    value = request_json_value(url, params=params, headers=headers)
    if not isinstance(value, dict):
        raise RuntimeError("JSON response is not an object")
    return value


def request_text(url: str, *, params: dict[str, Any] | None = None, headers: dict[str, str] | None = None) -> str:
    if requests is None:
        raise RuntimeError("Python package 'requests' is required")
    response = requests.get(url, params=params or {}, headers=headers or {"Accept": "text/plain, application/xml"}, timeout=data_node_timeout_seconds())
    response.raise_for_status()
    return response.text


def recent_date(days: int) -> str:
    return (date.today() - timedelta(days=days)).isoformat()


def fetch_finnhub_news(tickers: list[str]) -> dict[str, Any]:
    token = first_env("FINNHUB_API_KEY")
    if not token:
        return data_node_result("finnhub_news", "Finnhub company news", "news", required=10, status="partial", error="FINNHUB_API_KEY missing")
    items: list[dict[str, Any]] = []
    seen: set[str] = set()
    for ticker in tickers[:6]:
        data = request_json_value(
            "https://finnhub.io/api/v1/company-news",
            params={"symbol": ticker, "from": recent_date(14), "to": today_iso(), "token": token},
        )
        rows = data if isinstance(data, list) else []
        if not rows:
            continue
        for row in rows[:3]:
            if not isinstance(row, dict):
                continue
            url = safe_text(row.get("url"))
            key = url or safe_text(row.get("headline"))
            if not key or key in seen:
                continue
            seen.add(key)
            timestamp = row.get("datetime")
            item_date = ""
            if isinstance(timestamp, (int, float)) and timestamp > 0:
                item_date = date.fromtimestamp(int(timestamp)).isoformat()
            items.append(
                {
                    "ticker": ticker,
                    "title": safe_text(row.get("headline")),
                    "source": safe_text(row.get("source")) or "Finnhub",
                    "date": item_date,
                    "url": url,
                    "summary": safe_text(row.get("summary"))[:260],
                }
            )
            if len(items) >= 10:
                break
        if len(items) >= 10:
            break
    return data_node_result("finnhub_news", "Finnhub company news", "news", items, required=10)


def fetch_finnhub_quotes(tickers: list[str]) -> dict[str, Any]:
    token = first_env("FINNHUB_API_KEY")
    if not token:
        return data_node_result("market_quotes", "Finnhub quotes", "market_data", required=5, status="partial", error="FINNHUB_API_KEY missing")
    items: list[dict[str, Any]] = []
    for ticker in tickers[:8]:
        row = request_json("https://finnhub.io/api/v1/quote", params={"symbol": ticker, "token": token})
        price = parse_float(row.get("c"))
        previous = parse_float(row.get("pc"))
        if price is None:
            continue
        change_pct = None
        if previous and previous > 0:
            change_pct = ((price - previous) / previous) * 100
        items.append(
            {
                "ticker": ticker,
                "title": f"{ticker} quote",
                "source": "Finnhub",
                "date": today_iso(),
                "url": f"https://finnhub.io/api/v1/quote?symbol={ticker}",
                "price": price,
                "previousClose": previous,
                "changePct": change_pct,
                "summary": f"latest={price}; previous_close={previous}; change_pct={change_pct:.2f}%" if change_pct is not None else f"latest={price}",
            }
        )
    return data_node_result("market_quotes", "Finnhub quotes", "market_data", items, required=5)


def fetch_finnhub_fundamentals(tickers: list[str]) -> dict[str, Any]:
    token = first_env("FINNHUB_API_KEY")
    if not token:
        return data_node_result("finnhub_fundamentals", "Finnhub profile / metrics", "fundamentals", required=3, status="partial", error="FINNHUB_API_KEY missing")
    items: list[dict[str, Any]] = []
    for ticker in tickers[:6]:
        profile = request_json("https://finnhub.io/api/v1/stock/profile2", params={"symbol": ticker, "token": token})
        metric = request_json("https://finnhub.io/api/v1/stock/metric", params={"symbol": ticker, "metric": "all", "token": token})
        metrics = metric.get("metric") if isinstance(metric.get("metric"), dict) else {}
        if not profile and not metrics:
            continue
        summary_parts = []
        for key in ["marketCapitalization", "peNormalizedAnnual", "revenueGrowthTTMYoy", "grossMarginTTM", "operatingMarginTTM"]:
            if metrics.get(key) is not None:
                summary_parts.append(f"{key}={metrics.get(key)}")
        items.append(
            {
                "ticker": ticker,
                "title": safe_text(profile.get("name")) or f"{ticker} fundamentals",
                "source": "Finnhub",
                "date": today_iso(),
                "url": f"https://finnhub.io/api/v1/stock/metric?symbol={ticker}",
                "summary": "; ".join(summary_parts[:6]) or "profile / metric returned",
            }
        )
    return data_node_result("finnhub_fundamentals", "Finnhub profile / metrics", "fundamentals", items, required=3)


def fetch_finnhub_sentiment(tickers: list[str]) -> dict[str, Any]:
    token = first_env("FINNHUB_API_KEY")
    if not token:
        return data_node_result("finnhub_sentiment", "Finnhub news sentiment", "sentiment", required=5, status="partial", error="FINNHUB_API_KEY missing")
    items: list[dict[str, Any]] = []
    for ticker in tickers[:8]:
        row = request_json("https://finnhub.io/api/v1/news-sentiment", params={"symbol": ticker, "token": token})
        sentiment = row.get("sentiment") if isinstance(row.get("sentiment"), dict) else {}
        buzz = row.get("buzz") if isinstance(row.get("buzz"), dict) else {}
        if not sentiment and not buzz:
            continue
        score = sentiment.get("companyNewsScore")
        articles = buzz.get("articlesInLastWeek")
        items.append(
            {
                "ticker": ticker,
                "title": f"{ticker} news sentiment",
                "source": "Finnhub",
                "date": today_iso(),
                "url": f"https://finnhub.io/api/v1/news-sentiment?symbol={ticker}",
                "summary": f"companyNewsScore={score}; articlesInLastWeek={articles}; sectorAverageBullishPercent={sentiment.get('sectorAverageBullishPercent')}",
            }
        )
    return data_node_result("finnhub_sentiment", "Finnhub news sentiment", "sentiment", items, required=5)


def fetch_github_projects() -> dict[str, Any]:
    queries = [
        "AI agent stars:>500",
        "LLM inference OR vLLM OR SGLang stars:>500",
    ]
    items: list[dict[str, Any]] = []
    seen: set[str] = set()
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "weekly-brief-research/0.1"}
    for query in queries:
        data = request_json(
            "https://api.github.com/search/repositories",
            params={"q": query, "sort": "updated", "order": "desc", "per_page": 5},
            headers=headers,
        )
        for repo in data.get("items") or []:
            if not isinstance(repo, dict):
                continue
            name = safe_text(repo.get("full_name"))
            if not name or name in seen:
                continue
            seen.add(name)
            items.append(
                {
                    "title": name,
                    "source": "GitHub",
                    "date": safe_text(repo.get("updated_at"))[:10],
                    "url": safe_text(repo.get("html_url")),
                    "summary": f"stars={repo.get('stargazers_count')}; forks={repo.get('forks_count')}; {safe_text(repo.get('description'))[:180]}",
                }
            )
            if len(items) >= 5:
                break
        if len(items) >= 5:
            break
    return data_node_result("github_projects", "GitHub project search", "open_source", items, required=5)


def fetch_arxiv_papers() -> dict[str, Any]:
    text = request_text(
        "https://export.arxiv.org/api/query",
        params={
            "search_query": 'cat:cs.AI AND (agent OR "tool use" OR reasoning OR inference)',
            "start": 0,
            "max_results": 5,
            "sortBy": "submittedDate",
            "sortOrder": "descending",
        },
        headers={"Accept": "application/atom+xml", "User-Agent": "weekly-brief-research/0.1"},
    )
    root = ET.fromstring(text)
    ns = {"atom": "http://www.w3.org/2005/Atom"}
    items: list[dict[str, Any]] = []
    for entry in root.findall("atom:entry", ns):
        title = re.sub(r"\s+", " ", entry.findtext("atom:title", default="", namespaces=ns)).strip()
        published = entry.findtext("atom:published", default="", namespaces=ns)[:10]
        link = ""
        for link_node in entry.findall("atom:link", ns):
            href = link_node.attrib.get("href", "")
            if href:
                link = href
                break
        summary = re.sub(r"\s+", " ", html.unescape(entry.findtext("atom:summary", default="", namespaces=ns))).strip()
        if title:
            items.append({"title": title, "source": "arXiv", "date": published, "url": link, "summary": summary[:260]})
    return data_node_result("arxiv_papers", "arXiv papers", "papers", items, required=5)


def fetch_sec_filings(tickers: list[str]) -> dict[str, Any]:
    user_agent = first_env("SEC_EDGAR_USER_AGENT")
    if not user_agent:
        return data_node_result("sec_filings", "SEC recent filings", "filings", required=3, status="partial", error="SEC_EDGAR_USER_AGENT missing")
    items: list[dict[str, Any]] = []
    headers = {"Accept": "application/json", "User-Agent": user_agent}
    for ticker in tickers[:6]:
        cik = SEC_CIK_BY_TICKER.get(ticker)
        if not cik:
            continue
        data = request_json(f"https://data.sec.gov/submissions/CIK{cik}.json", headers=headers)
        recent = (data.get("filings") or {}).get("recent") or {}
        forms = recent.get("form") or []
        dates = recent.get("filingDate") or []
        accessions = recent.get("accessionNumber") or []
        for form, filing_date, accession in zip(forms, dates, accessions):
            if form not in {"10-K", "10-Q", "8-K"}:
                continue
            accession_compact = safe_text(accession).replace("-", "")
            url = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accession_compact}/"
            items.append(
                {
                    "ticker": ticker,
                    "title": f"{ticker} {form}",
                    "source": "SEC EDGAR",
                    "date": safe_text(filing_date),
                    "url": url,
                    "summary": f"Recent SEC filing: {form}",
                }
            )
            break
        if len(items) >= 6:
            break
    return data_node_result("sec_filings", "SEC recent filings", "filings", items, required=3)


def fetch_yahoo_technicals(tickers: list[str]) -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    for ticker in tickers[:6]:
        try:
            prices = fetch_daily_closes(ticker, timeout_seconds=data_node_timeout_seconds())
        except Exception as exc:  # noqa: BLE001
            items.append({"ticker": ticker, "title": f"{ticker} technical data failed", "source": "Yahoo Finance", "date": today_iso(), "url": "", "summary": f"failed: {exc}"})
            continue
        if len(prices) < 20:
            continue
        latest_date, latest_close = prices[-1]
        closes = [close for _price_date, close in prices]
        sma20 = sum(closes[-20:]) / 20
        sma50 = sum(closes[-50:]) / 50 if len(closes) >= 50 else None
        six_month_low = min(closes)
        six_month_high = max(closes)
        trend = "above_20d_sma" if latest_close >= sma20 else "below_20d_sma"
        summary = f"close={latest_close:.2f}; sma20={sma20:.2f}; range_6m={six_month_low:.2f}-{six_month_high:.2f}; trend={trend}"
        if sma50 is not None:
            summary += f"; sma50={sma50:.2f}"
        items.append(
            {
                "ticker": ticker,
                "title": f"{ticker} daily technical snapshot",
                "source": "Yahoo Finance chart",
                "date": latest_date,
                "url": f"https://finance.yahoo.com/quote/{yahoo_symbol(ticker)}",
                "summary": summary,
            }
        )
    valid_items = [item for item in items if not item.get("summary", "").startswith("failed:")]
    status = None if valid_items else "failed"
    return data_node_result("technical_prices", "Yahoo daily technicals", "market_data", valid_items, required=5, status=status)


def fetch_fred_macro() -> dict[str, Any]:
    token = first_env("FRED_API_KEY")
    if not token:
        return data_node_result("fred_macro", "FRED macro", "macro", required=2, status="partial", error="FRED_API_KEY missing")
    series = [("DGS10", "10Y Treasury yield"), ("VIXCLS", "VIX close"), ("FEDFUNDS", "Fed funds")]
    items: list[dict[str, Any]] = []
    for series_id, title in series:
        data = request_json(
            "https://api.stlouisfed.org/fred/series/observations",
            params={"series_id": series_id, "api_key": token, "file_type": "json", "sort_order": "desc", "limit": 1},
        )
        observations = data.get("observations") or []
        if not observations:
            continue
        row = observations[0]
        items.append(
            {
                "title": title,
                "source": "FRED",
                "date": safe_text(row.get("date")),
                "url": f"https://fred.stlouisfed.org/series/{series_id}",
                "summary": f"{series_id}={safe_text(row.get('value'))}",
            }
        )
    return data_node_result("fred_macro", "FRED macro", "macro", items, required=2)


def collect_research_data_nodes(user_prompt: str) -> dict[str, Any]:
    tickers = [item["ticker"] for item in fallback_research_universe(user_prompt)]
    configured_apis = [
        name
        for name, present in {
            "FINNHUB_API_KEY": bool(first_env("FINNHUB_API_KEY")),
            "ALPHA_VANTAGE": bool(first_env("ALPHA_VANTAGE_API_KEY", "ALPHA_VANTAGE")),
            "FRED_API_KEY": bool(first_env("FRED_API_KEY")),
            "SEC_EDGAR_USER_AGENT": bool(first_env("SEC_EDGAR_USER_AGENT")),
            "TRANSCRIPT_API_KEY": bool(first_env("TRANSCRIPT_API_KEY")),
            "SCRAPECREATORS_API_KEY": bool(first_env("SCRAPECREATORS_API_KEY")),
        }.items()
        if present
    ]
    if not data_node_enabled():
        bundle = {
            "enabled": False,
            "configuredApis": configured_apis,
            "tickers": tickers,
            "nodes": {},
            "markdown": "## Data Node Evidence Bundle\n\n数据节点未启用。",
        }
        return bundle

    task_specs = [
        ("finnhub_news", lambda: fetch_finnhub_news(tickers)),
        ("arxiv_papers", fetch_arxiv_papers),
        ("github_projects", fetch_github_projects),
        ("finnhub_sentiment", lambda: fetch_finnhub_sentiment(tickers)),
        ("market_quotes", lambda: fetch_finnhub_quotes(tickers)),
        ("finnhub_fundamentals", lambda: fetch_finnhub_fundamentals(tickers)),
        ("sec_filings", lambda: fetch_sec_filings(tickers)),
        ("technical_prices", lambda: fetch_yahoo_technicals(tickers)),
        ("fred_macro", fetch_fred_macro),
    ]
    nodes: dict[str, dict[str, Any]] = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(6, len(task_specs))) as executor:
        future_to_key = {executor.submit(func): key for key, func in task_specs}
        for future in concurrent.futures.as_completed(future_to_key):
            key = future_to_key[future]
            try:
                result = future.result()
            except Exception as exc:  # noqa: BLE001 - node failures become evidence status, not request failure
                result = data_node_result(key, key, "data_node", required=DATA_NODE_REQUIRED_COUNTS.get(key, 0), status="failed", error=str(exc))
            nodes[key] = result

    bundle = {
        "enabled": True,
        "configuredApis": configured_apis,
        "tickers": tickers,
        "nodes": nodes,
    }
    bundle["markdown"] = data_node_bundle_markdown(bundle)
    return bundle


def node_items(bundle: dict[str, Any], key: str) -> list[dict[str, Any]]:
    node = (bundle.get("nodes") or {}).get(key) or {}
    items = node.get("items") or []
    return [item for item in items if isinstance(item, dict)]


def data_node_status_rows(bundle: dict[str, Any]) -> list[str]:
    rows = ["| Node | Status | Count / Required | Notes |", "|---|---|---:|---|"]
    nodes = bundle.get("nodes") or {}
    for key in [
        "finnhub_news",
        "arxiv_papers",
        "github_projects",
        "finnhub_sentiment",
        "market_quotes",
        "finnhub_fundamentals",
        "sec_filings",
        "technical_prices",
        "fred_macro",
    ]:
        node = nodes.get(key) or data_node_result(key, key, "data_node", status="partial", error="not collected")
        rows.append(
            f"| {node.get('label') or key} | {node.get('status')} | {node.get('count', 0)} / {node.get('required', 0)} | {safe_text(node.get('error')) or node.get('sourceType', '')} |"
        )
    return rows


def evidence_items_table(items: list[dict[str, Any]], *, max_rows: int = 10) -> str:
    rows = ["| Date | Source | Ticker / Topic | Evidence | Link |", "|---|---|---|---|---|"]
    for item in items[:max_rows]:
        ticker = safe_text(item.get("ticker"))
        topic = ticker or safe_text(item.get("title"))[:36]
        title = safe_text(item.get("title"))
        summary = safe_text(item.get("summary"))
        url = safe_text(item.get("url"))
        link = f"[source]({url})" if url else "n/a"
        evidence = title if not summary else f"{title}: {summary}"
        rows.append(f"| {safe_text(item.get('date')) or today_iso()} | {safe_text(item.get('source'))} | {topic} | {evidence[:260]} | {link} |")
    if len(rows) == 2:
        rows.append("| n/a | n/a | n/a | 数据节点没有返回可用条目 | n/a |")
    return "\n".join(rows)


def data_node_bundle_markdown(bundle: dict[str, Any]) -> str:
    lines = [
        "## Data Node Evidence Bundle",
        "",
        f"- Enabled：{bundle.get('enabled')}",
        f"- Configured APIs：{', '.join(bundle.get('configuredApis') or []) or 'none detected'}",
        f"- Seed tickers：{', '.join(bundle.get('tickers') or [])}",
        "",
        "### Data Node Status",
        *data_node_status_rows(bundle),
        "",
        "### News",
        evidence_items_table(node_items(bundle, "finnhub_news"), max_rows=10),
        "",
        "### Papers",
        evidence_items_table(node_items(bundle, "arxiv_papers"), max_rows=5),
        "",
        "### Open Source",
        evidence_items_table(node_items(bundle, "github_projects"), max_rows=5),
        "",
        "### Sentiment / Market Attention",
        evidence_items_table(node_items(bundle, "finnhub_sentiment"), max_rows=5),
        "",
        "### Market / Technical / Fundamentals",
        evidence_items_table(
            node_items(bundle, "market_quotes")
            + node_items(bundle, "technical_prices")
            + node_items(bundle, "finnhub_fundamentals")
            + node_items(bundle, "sec_filings")
            + node_items(bundle, "fred_macro"),
            max_rows=18,
        ),
    ]
    return "\n".join(lines)


def data_node_counts(bundle: dict[str, Any]) -> dict[str, int]:
    return {key: len(node_items(bundle, key)) for key in (bundle.get("nodes") or {})}


def data_node_complete_enough(bundle: dict[str, Any]) -> bool:
    counts = data_node_counts(bundle)
    return (
        counts.get("finnhub_news", 0) >= 10
        and counts.get("arxiv_papers", 0) >= 5
        and counts.get("github_projects", 0) >= 5
        and counts.get("market_quotes", 0) >= 5
        and counts.get("technical_prices", 0) >= 5
    )


TRACE_DATA_NODE_PATTERNS = [
    ("YouTube / podcast / transcript", r"youtube|podcast|transcript|播客|高管|访谈|发言|字幕"),
    ("last30days / 社区舆情", r"last30days|reddit|x/twitter|twitter|社区|舆情|讨论"),
    ("GitHub / 开源项目", r"github|repo|开源|star|fork"),
    ("arXiv / 论文", r"arxiv|paper|论文|research"),
    ("RSS / news", r"rss|news|新闻|媒体"),
    ("SEC / filings", r"sec|10-k|10-q|8-k|filing|edgar|年报|季报"),
    ("Fundamentals", r"fundamental|财报|收入|利润|现金流|估值|margin|capex|eps"),
    ("Market data / K-line", r"k-line|k线|ohlcv|价格|支撑|阻力|均线|rsi|macd|技术"),
    ("Reflection lenses", r"cathie|wood|木头姐|buffett|巴菲特|reflection|反方"),
    ("Paper ledger", r"paper|ledger|shadow|归因|复盘|观察账本"),
]

UNHELPFUL_DEFERRAL_PATTERNS = [
    r"当前无\s*ticker",
    r"当前无候选",
    r"无候选可",
    r"等待上游",
    r"请先等待",
    r"没有上游股票池",
    r"不能输出\s*active\s+research\s+candidates",
    r"暂无输出",
    r"no\s+ticker",
    r"no\s+candidate",
]


TRACE_AGENT_DEFAULTS = {
    "Intent Router": {
        "thinking": "我先判断这次请求属于哪种任务，哪些 agent 应该运行，哪些数据节点缺失。",
        "next": "按路由结果进入候选发现或单点研究，不把路由表放到最终报告第一屏。",
    },
    "Stock Discovery": {
        "thinking": "我先把候选入口控噪，判断哪些公司只是噪音，哪些值得进入后续验证。",
        "next": "把 active candidates 交给信息、基本面和技术面分别验证。",
    },
    "AI 信息与舆情": {
        "thinking": "我在看最近信息流里哪些 AI 叙事有重复出现的证据，而不是只看单个观点。",
        "next": "把可成立的故事交给基本面，看它能不能落到收入、订单、capex、margin 或估值预期。",
    },
    "Fundamental": {
        "thinking": "我在检查叙事能否传导到财务科目，以及哪些部分已经被价格或预期反映。",
        "next": "把财务上能站住的候选交给技术面确认时机和失效位。",
    },
    "Technical": {
        "thinking": "我先只看价格、K 线、量能和关键位，避免被新闻叙事带偏。",
        "next": "把图表支持、犹豫或反对的信号交给 Reflection 做闭环审查。",
    },
    "Reflection": {
        "thinking": "我让木头姐式长期创新视角和巴菲特式价值纪律分别审查这个故事。",
        "next": "把被强化、被降级和仍需证伪的部分交给最终叙事分析师。",
    },
    "Final Narrative": {
        "thinking": "我把前面几层证据收束成老板能先看的结论、Top 5、风险和下周验证。",
        "next": "把入池候选写入结论池和 paper ledger，等下周价格回看。",
    },
    "Paper Attribution": {
        "thinking": "我把上周观察对象和这周价格结果对齐，判断是 thesis 错、时机错，还是市场环境拖累。",
        "next": "更新信号权重和下周观察规则。",
    },
}


def clean_trace_text(text: str) -> str:
    text = re.sub(r"```[\s\S]*?```", " ", str(text or ""))
    text = re.sub(r"`([^`]+)`", r"\1", text)
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1", text)
    text = re.sub(r"^\s*\|.*\|\s*$", " ", text, flags=re.MULTILINE)
    text = re.sub(r"^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?\s*$", " ", text, flags=re.MULTILINE)
    text = re.sub(r"^#{1,6}\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\s*[-*]\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def is_unhelpful_deferral_text(text: str) -> bool:
    value = str(text or "")
    return any(re.search(pattern, value, re.IGNORECASE) for pattern in UNHELPFUL_DEFERRAL_PATTERNS)


def remove_unhelpful_deferral_items(items: list[str]) -> list[str]:
    return [item for item in items if not is_unhelpful_deferral_text(item)]


def split_trace_sentences(text: str, limit: int = 6) -> list[str]:
    cleaned = clean_trace_text(text)
    if not cleaned:
        return []
    parts = re.split(r"(?<=[。！？.!?])\s+|\s+[;；]\s+", cleaned)
    sentences = []
    for part in parts:
        item = part.strip(" -:：")
        if len(item) < 8:
            continue
        if item.lower() in {"complete", "partial", "failed"}:
            continue
        if is_unhelpful_deferral_text(item):
            continue
        sentences.append(item[:180])
        if len(sentences) >= limit:
            break
    return sentences


def extract_trace_bullets(markdown: str, limit: int = 4) -> list[str]:
    bullets = []
    for line in str(markdown or "").splitlines():
        stripped = line.strip()
        match = re.match(r"^(?:[-*]|\d+[.、])\s+(.+)$", stripped)
        if not match:
            continue
        item = clean_trace_text(match.group(1))
        if len(item) < 8:
            continue
        if is_unhelpful_deferral_text(item):
            continue
        bullets.append(item[:180])
        if len(bullets) >= limit:
            break
    if bullets:
        return bullets
    return split_trace_sentences(markdown, limit=limit)


def infer_trace_data_nodes(markdown: str) -> list[str]:
    text = str(markdown or "").lower()
    nodes = []
    for label, pattern in TRACE_DATA_NODE_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            nodes.append(label)
    return nodes[:5] or ["本地 agent prompt / 上游 section"]


def extract_lens_summary(markdown: str, patterns: list[str], fallback: str) -> str:
    lines = [line.strip() for line in str(markdown or "").splitlines() if line.strip()]
    joined = "\n".join(lines)
    for pattern in patterns:
        match = re.search(pattern, joined, re.IGNORECASE)
        if match:
            start = max(match.start() - 80, 0)
            end = min(match.end() + 220, len(joined))
            return clean_trace_text(joined[start:end])[:220]
    return fallback


def build_agent_trace(
    *,
    section_name: str,
    markdown: str,
    user_prompt: str,
    step_index: int,
    step_total: int,
) -> dict[str, Any]:
    defaults = TRACE_AGENT_DEFAULTS.get(section_name, {})
    status = infer_section_status(markdown)
    bullets = extract_trace_bullets(markdown, limit=4)
    sentences = split_trace_sentences(markdown, limit=5)
    if not bullets:
        bullets = section_output_focus(section_name)[:3]
    headline = bullets[0] if bullets else (sentences[0] if sentences else f"{section_name} 已生成公开思考摘要。")
    judgment = sentences[1] if len(sentences) > 1 else (
        f"{section_name} 已产出可继续验证的研究输出，候选入口为 {fallback_ticker_list(user_prompt)}。"
    )
    next_step = defaults.get("next") or "把本 section 的结论交给下一层 agent 继续验证。"
    trace: dict[str, Any] = {
        "agent": section_name,
        "stepIndex": step_index,
        "stepTotal": step_total,
        "status": status,
        "headline": headline,
        "thinking": defaults.get("thinking") or f"我正在根据用户请求「{prompt_label(user_prompt)}」整理这一层该回答的问题。",
        "toolPlan": infer_trace_data_nodes(markdown),
        "findings": bullets[:3],
        "judgment": judgment,
        "nextStep": next_step,
    }

    if section_name == "Reflection":
        trace["debate"] = {
            "cathieWood": extract_lens_summary(
                markdown,
                [r"(cathie|wood|木头姐)[^\n。！？.!?]{0,220}", r"创新[^\n。！？.!?]{0,220}"],
                "木头姐视角：先问这个 AI 叙事是否可能被非线性扩散低估，以及市场是否低估长期 TAM。",
            ),
            "buffett": extract_lens_summary(
                markdown,
                [r"(buffett|巴菲特)[^\n。！？.!?]{0,220}", r"(现金流|护城河|安全边际)[^\n。！？.!?]{0,220}"],
                "巴菲特视角：先问现金流、护城河、估值和安全边际能否支撑这个故事。",
            ),
            "synthesis": "我会把长期创新弹性和价值纪律的分歧交给 Final Narrative，只保留能被证据链支撑的部分。",
        }

    return trace


def build_messages(user_prompt: str) -> list[dict[str, str]]:
    today = date.today().isoformat()
    agency = read_text("AGENCY.md", 12000)
    agents = read_text("AGENTS.md", 5000)
    output_standard = compact_output_standard_text()
    quality_gate = read_text("docs/weekly-brief-quality-gate.md", 7000)
    router = read_text("agents/08-intent-router.md", 6000)

    system = f"""
你是 AI 美股投资研究系统的本地 API 后端。你必须遵守仓库投研规则：

- 投资输出只做 research-oriented 分析，不下单、不调仓、不提供个性化仓位。
- 任何事实、推断、假设必须分开。
- 如果当前 API 调用没有实时联网或数据节点不可用，必须显式标记 partial/failed，不得编造新闻、论文、项目、行情或链接。
- 发布报告必须从老板决策页开始，Intent Route Plan 放到附录。
- 使用双跳证据链接：主报告 -> evidence 子文件 -> 原始来源。如果没有真实来源，只能写数据节点不足。
- 报告默认中文。

今天日期：{today}

项目规则：
{agents}

Harness runbook 摘要：
{agency}

Research Report Output Standard：
{output_standard}

质量门槛：
{quality_gate}

Intent Router：
{router}
""".strip()

    user = f"""
用户研究意图：
{user_prompt}

请生成 JSON，不要输出 JSON 以外的文字。Schema:
{{
  "title": "报告标题",
  "summaryMarkdown": "精简版 Markdown。必须从 # 老板决策页 开始。",
  "reportMarkdown": "完整周报 Markdown。必须从 # 老板决策页 开始，Route Plan 放附录。",
  "evidenceMarkdown": "证据包 Markdown。必须包含返回主报告、Evidence Index、Data Node Status。"
}}

重要约束：
- 如果无法访问实时新闻/论文/GitHub/行情/舆情，请在 Data Node Status 中写 partial 或 failed。
- 不要补编具体日期、链接、财务数字、新闻标题或行情。
- 可以基于用户意图生成可执行的研究框架、Route Plan、待采集清单和质量门槛状态。
- 研究 rating 只能是 Research Buy / Hold-Watch / Take-Profit / Trim Bias / Avoid-Sell Bias / No Rating，且必须说明是研究动作而非交易指令。
""".strip()

    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


def extract_json_object(text: str) -> dict[str, Any] | None:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:json)?\s*", "", stripped)
        stripped = re.sub(r"\s*```$", "", stripped)

    try:
        value = json.loads(stripped)
        return value if isinstance(value, dict) else None
    except json.JSONDecodeError:
        pass

    start = stripped.find("{")
    end = stripped.rfind("}")
    if start >= 0 and end > start:
        try:
            value = json.loads(stripped[start : end + 1])
            return value if isinstance(value, dict) else None
        except json.JSONDecodeError:
            return None
    return None


def fallback_payload(markdown: str) -> dict[str, str]:
    title = "AI 美股研究周报"
    first_heading = re.search(r"^#\s+(.+)$", markdown, re.MULTILINE)
    if first_heading:
        title = first_heading.group(1).strip()

    return {
        "title": title,
        "summaryMarkdown": extract_summary(markdown),
        "reportMarkdown": markdown,
        "evidenceMarkdown": build_minimal_evidence(markdown),
    }


def extract_summary(markdown: str) -> str:
    text = markdown.strip()
    if not text:
        return "# 老板决策页\n\nAPI 未返回 Markdown。"

    match = re.search(r"^#\s*老板决策页.*$", text, re.MULTILINE)
    start = match.start() if match else 0
    sliced = text[start:]
    end_markers = [
        r"\n##\s*附录",
        r"\n#\s*附录",
        r"\n##\s*Intent Route Plan",
        r"\n##\s*Data Node Status",
    ]
    ends = [m.start() for pattern in end_markers if (m := re.search(pattern, sliced, re.IGNORECASE))]
    if ends:
        return sliced[: min(ends)].strip()
    return "\n".join(sliced.splitlines()[:120]).strip()


def build_minimal_evidence(markdown: str) -> str:
    links = re.findall(r"\[([^\]]+)\]\(([^)]+)\)", markdown)
    rows = []
    for index, (label, href) in enumerate(links, start=1):
        escaped_label = label.replace("|", "\\|")
        escaped_href = href.replace("|", "\\|")
        rows.append(f"| E{index} | Link | [{escaped_label}]({href}) | {escaped_href} |")

    if not rows:
        rows.append("| E1 | Data Node Status | 无可用证据链接 | API 未返回独立 evidenceMarkdown |")

    return "\n".join(
        [
            "# 证据包：AI 美股研究周报",
            "",
            "[返回主报告](./weekly-brief.md)",
            "",
            "## Evidence Index",
            "| ID | Source Type | Evidence Anchor | Notes |",
            "|---|---|---|---|",
            *rows,
            "",
            "## Data Node Status",
            "| Input Node | Status | Notes |",
            "|---|---|---|",
            "| Backend Adapter | partial | API 未返回独立 evidenceMarkdown，前端从主报告链接生成最小证据视图。 |",
        ]
    )


def split_markdown_table_row(line: str) -> list[str]:
    stripped = line.strip().strip("|")
    if not stripped:
        return []
    return [cell.strip() for cell in re.split(r"(?<!\\)\|", stripped)]


def is_markdown_separator(line: str) -> bool:
    cells = split_markdown_table_row(line)
    return bool(cells) and all(re.fullmatch(r":?-{3,}:?", cell.strip()) for cell in cells)


def is_markdown_heading(line: str) -> bool:
    return bool(re.match(r"^\s*#{1,6}\s+", line))


def markdown_plain_text(value: str) -> str:
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", safe_text(value))
    text = re.sub(r"`([^`]+)`", r"\1", text)
    return re.sub(r"\s+", " ", text).strip()


def markdown_link_href(value: str) -> str:
    match = re.search(r"\[[^\]]+\]\(([^)]+)\)", safe_text(value))
    return match.group(1).strip() if match else ""


def parse_upside_range(value: str) -> tuple[str, str, str]:
    numbers = re.findall(r"-?\d+(?:\.\d+)?", safe_text(value))
    if len(numbers) >= 3:
        return numbers[0], numbers[1], numbers[2]
    if len(numbers) == 2:
        return numbers[0], "", numbers[1]
    if len(numbers) == 1:
        return "", numbers[0], ""
    return "", "", ""


def parse_holding_range(value: str) -> tuple[str, str]:
    numbers = re.findall(r"\d+(?:\.\d+)?", safe_text(value))
    if len(numbers) >= 2:
        return numbers[0], numbers[1]
    if len(numbers) == 1:
        return numbers[0], numbers[0]
    return "", ""


def normalize_header(value: str) -> str:
    header = markdown_plain_text(value).lower()
    header = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", " ", header).strip()
    if "rank" in header or header in {"序号", "排名"}:
        return "rank"
    if "ticker" in header or "theme" in header or "公司" in header or "主题" in header:
        return "ticker"
    if "rating" in header or "动作" in header:
        return "actionRating"
    if "confidence" in header or "置信" in header:
        return "confidence"
    if "upside" in header or "涨幅" in header:
        return "estimatedUpsideRange"
    if "holding" in header or "观察" in header or "周期" in header:
        return "estimatedHoldingRange"
    if "exit" in header or "trim" in header or "止盈" in header:
        return "exitOrTrimRule"
    if "why now" in header or "为什么" in header:
        return "whyNow"
    if "hard evidence" in header or "证据" in header:
        return "hardEvidence"
    if "evidence pack" in header or "证据包" in header:
        return "evidencePack"
    if "falsification" in header or "invalidation" in header or "反证" in header or "失效" in header:
        return "invalidationCondition"
    if "next" in header or "下周" in header:
        return "nextWeekCheck"
    return header.replace(" ", "_")


def parse_ticker_and_company(value: str) -> tuple[str, str]:
    text = markdown_plain_text(value)
    match = re.search(r"\b[A-Z][A-Z0-9.-]{0,7}\b", text)
    if not match:
        return text[:12].upper(), text
    ticker = match.group(0)
    company = text.replace(ticker, "", 1).strip(" -/()：:")
    return ticker, company


def candidate_from_table_row(headers: list[str], cells: list[str], decision_date: str, run_id: str) -> dict[str, Any] | None:
    values: dict[str, str] = {}
    for header, cell in zip(headers, cells):
        values[normalize_header(header)] = cell

    ticker_text = values.get("ticker", "")
    ticker, company = parse_ticker_and_company(ticker_text)
    if not ticker:
        return None

    low, base, high = parse_upside_range(values.get("estimatedUpsideRange", ""))
    holding_min, holding_max = parse_holding_range(values.get("estimatedHoldingRange", ""))
    evidence_href = markdown_link_href(values.get("evidencePack", ""))
    rank = compact_percent(values.get("rank"))
    thesis_id = f"{ticker}-{rank or len(headers)}"

    return {
        "runId": run_id,
        "decisionDate": decision_date,
        "thesisId": thesis_id,
        "rank": rank,
        "ticker": ticker,
        "company": company,
        "actionRating": markdown_plain_text(values.get("actionRating", "")),
        "confidence": parse_float(values.get("confidence")),
        "estimatedUpsideLowPct": parse_float(low),
        "estimatedUpsideBasePct": parse_float(base),
        "estimatedUpsideHighPct": parse_float(high),
        "estimatedHoldingMinDays": parse_float(holding_min),
        "estimatedHoldingMaxDays": parse_float(holding_max),
        "exitOrTrimRule": markdown_plain_text(values.get("exitOrTrimRule", "")),
        "invalidationCondition": markdown_plain_text(values.get("invalidationCondition", "")),
        "thesisSummary": markdown_plain_text(ticker_text),
        "hardEvidence": markdown_plain_text(values.get("hardEvidence", "")),
        "whyNow": markdown_plain_text(values.get("whyNow", "")),
        "nextWeekCheck": markdown_plain_text(values.get("nextWeekCheck", "")),
        "evidencePackHref": evidence_href or markdown_plain_text(values.get("evidencePack", "")),
        "benchmarkPrimary": "QQQ",
    }


def is_action_pool_header(headers: list[str]) -> bool:
    normalized = {normalize_header(header) for header in headers}
    return {"rank", "ticker", "actionRating"}.issubset(normalized)


def is_actionable_research_candidate(candidate: dict[str, Any]) -> bool:
    rating = markdown_plain_text(safe_text(candidate.get("actionRating"))).lower()
    if not rating:
        return False
    blocked = ["no rating", "defer", "watchlist only", "avoid-only"]
    if any(term in rating for term in blocked):
        return False
    return True


def parse_action_pool_from_markdown(markdown: str, *, run_id: str = "", decision_date: str = "") -> list[dict[str, Any]]:
    text = safe_text(markdown)
    if not text:
        return []

    lines = text.splitlines()
    candidates: list[dict[str, Any]] = []
    section_patterns = [
        re.compile(r"^\s*#{1,4}\s+.*Top\s*5\s*Research\s*Action\s*Pool", re.I),
        re.compile(r"^\s*#{1,4}\s+.*本周研究动作", re.I),
    ]
    run_id = run_id or f"report-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    decision_date = decision_date or today_iso()

    for index, line in enumerate(lines):
        if not any(pattern.search(line) for pattern in section_patterns):
            continue

        section_end = len(lines)
        for end_index in range(index + 1, len(lines)):
            if is_markdown_heading(lines[end_index]):
                section_end = end_index
                break
        section_lines = [section_line for section_line in lines[index + 1 : section_end] if section_line.strip()]

        for table_index in range(0, max(0, len(section_lines) - 1)):
            if "|" not in section_lines[table_index]:
                continue
            headers = split_markdown_table_row(section_lines[table_index])
            if table_index + 1 >= len(section_lines) or not is_markdown_separator(section_lines[table_index + 1]):
                continue
            if not is_action_pool_header(headers):
                continue

            for row_line in section_lines[table_index + 2 :]:
                if "|" not in row_line or is_markdown_heading(row_line):
                    break
                cells = split_markdown_table_row(row_line)
                if len(cells) < 2:
                    continue
                candidate = candidate_from_table_row(headers, cells, decision_date, run_id)
                if candidate and is_actionable_research_candidate(candidate):
                    candidates.append(candidate)
            if candidates:
                return candidates[:5]
    return []


def normalize_research_action_pool(value: Any, markdown: str, *, run_id: str = "", decision_date: str = "") -> list[dict[str, Any]]:
    raw_pool: Any = None
    if isinstance(value, dict):
        raw_pool = (
            value.get("researchActionPool")
            or value.get("research_action_pool")
            or value.get("top5")
            or value.get("top_5")
            or value.get("candidates")
        )

    pool: list[dict[str, Any]] = []
    if isinstance(raw_pool, list):
        for index, item in enumerate(raw_pool, start=1):
            if not isinstance(item, dict):
                continue
            ticker = normalize_ticker(item.get("ticker") or item.get("symbol") or item.get("tickerTheme"))
            if not ticker:
                continue
            low, base, high = parse_upside_range(safe_text(item.get("estimatedUpsideRange") or ""))
            holding_min, holding_max = parse_holding_range(safe_text(item.get("estimatedHoldingRange") or ""))
            candidate = {
                "runId": safe_text(item.get("runId") or run_id),
                "decisionDate": safe_text(item.get("decisionDate") or decision_date or today_iso()),
                "thesisId": safe_text(item.get("thesisId") or f"{ticker}-{item.get('rank') or index}"),
                "rank": item.get("rank") or index,
                "ticker": ticker,
                "company": safe_text(item.get("company") or item.get("name")),
                "actionRating": safe_text(item.get("actionRating") or item.get("rating")),
                "confidence": parse_float(item.get("confidence")),
                "estimatedUpsideLowPct": parse_float(item.get("estimatedUpsideLowPct")) or parse_float(low),
                "estimatedUpsideBasePct": parse_float(item.get("estimatedUpsideBasePct")) or parse_float(base),
                "estimatedUpsideHighPct": parse_float(item.get("estimatedUpsideHighPct")) or parse_float(high),
                "estimatedHoldingMinDays": parse_float(item.get("estimatedHoldingMinDays")) or parse_float(holding_min),
                "estimatedHoldingMaxDays": parse_float(item.get("estimatedHoldingMaxDays")) or parse_float(holding_max),
                "exitOrTrimRule": safe_text(item.get("exitOrTrimRule") or item.get("exitOrTrimBias")),
                "invalidationCondition": safe_text(item.get("invalidationCondition") or item.get("invalidation")),
                "thesisSummary": safe_text(item.get("thesisSummary") or item.get("summary")),
                "hardEvidence": safe_text(item.get("hardEvidence") or item.get("hardEvidenceSummary")),
                "whyNow": safe_text(item.get("whyNow")),
                "nextWeekCheck": safe_text(item.get("nextWeekCheck")),
                "evidencePackHref": safe_text(item.get("evidencePackHref") or item.get("evidencePack")),
                "benchmarkPrimary": safe_text(item.get("benchmarkPrimary") or "QQQ"),
            }
            if is_actionable_research_candidate(candidate):
                pool.append(candidate)

    if not pool:
        pool = parse_action_pool_from_markdown(markdown, run_id=run_id, decision_date=decision_date)

    return pool[:5]


def normalize_payload(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        report = (
            value.get("reportMarkdown")
            or value.get("report_markdown")
            or value.get("markdown")
            or value.get("content")
            or ""
        )
        summary = value.get("summaryMarkdown") or value.get("summary_markdown") or ""
        evidence = value.get("evidenceMarkdown") or value.get("evidence_markdown") or ""
        payload = {
            "title": value.get("title") or value.get("report_title") or "AI 美股研究周报",
            "summaryMarkdown": summary or extract_summary(str(report)),
            "reportMarkdown": str(report),
            "evidenceMarkdown": evidence or build_minimal_evidence(str(report)),
        }
        payload["researchActionPool"] = normalize_research_action_pool(value, payload["reportMarkdown"])
        return payload

    payload = fallback_payload(str(value))
    payload["researchActionPool"] = normalize_research_action_pool({}, payload["reportMarkdown"])
    return payload


def error_report_payload(message: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
    user_prompt = request_user_prompt(body or {}) if body is not None else DEFAULT_RESEARCH_INTENT
    report = f"# 研究未完成\n\n后端运行失败：{message}"
    return {
        "title": "研究未完成",
        "summaryMarkdown": report,
        "reportMarkdown": report,
        "evidenceMarkdown": "# 证据包：研究未完成\n\n## Data Node Status\n- Backend：failed",
        "researchActionPool": [],
        "runMetadata": {
            "runId": datetime.now().strftime("failed-%Y%m%d-%H%M%S-%f"),
            "source": "backend_error",
            "userPrompt": user_prompt,
        },
    }


def report_history_status(payload: dict[str, Any]) -> str:
    report = safe_text(payload.get("reportMarkdown"))
    title = safe_text(payload.get("title"))
    if "研究未完成" in title or "后端运行失败" in report:
        return "failed"
    lowered = report.lower()
    if re.search(r"(section\s*状态|状态)\s*[:：]\s*`?\s*failed", lowered, re.IGNORECASE):
        return "partial"
    if re.search(r"(partial|数据节点不足|缺口|未接入|failed)", report, re.IGNORECASE):
        return "partial"
    return "complete"


def report_history_slug(value: str) -> str:
    text = re.sub(r"[^\w\u4e00-\u9fff.-]+", "-", safe_text(value), flags=re.UNICODE).strip("-")
    return text[:48] or "weekly-brief"


def report_history_excerpt(markdown: str, max_chars: int = 180) -> str:
    text = re.sub(r"[#>*_`|]+", " ", safe_text(markdown))
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rstrip() + "..."


def report_history_files() -> list[Path]:
    if not REPORT_HISTORY_DIR.exists():
        return []
    return sorted(REPORT_HISTORY_DIR.glob("*.json"), reverse=True)


def display_path(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def read_report_history_file(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def report_history_item(record: dict[str, Any]) -> dict[str, Any]:
    payload = record.get("payload") if isinstance(record.get("payload"), dict) else {}
    return {
        "id": safe_text(record.get("id")),
        "createdAt": safe_text(record.get("createdAt")),
        "title": safe_text(record.get("title") or payload.get("title") or "未命名报告"),
        "status": safe_text(record.get("status") or report_history_status(payload)),
        "source": safe_text(record.get("source")),
        "prompt": safe_text(record.get("prompt")),
        "model": safe_text(record.get("model")),
        "summaryExcerpt": safe_text(record.get("summaryExcerpt")),
        "historyPath": safe_text(record.get("historyPath")),
    }


def save_report_history(payload: dict[str, Any], body: dict[str, Any] | None = None, *, source: str = "") -> dict[str, Any]:
    REPORT_HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    created_at = datetime.now().isoformat(timespec="seconds")
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    title = safe_text(payload.get("title")) or title_from_markdown(safe_text(payload.get("reportMarkdown")), "未命名报告")
    record_id = f"{timestamp}-{report_history_slug(title)}"
    payload_copy = json.loads(json.dumps(payload, ensure_ascii=False, default=str))
    payload_copy.setdefault("runMetadata", {})
    if isinstance(payload_copy["runMetadata"], dict):
        payload_copy["runMetadata"]["historyId"] = record_id
        payload_copy["runMetadata"]["historyCreatedAt"] = created_at

    prompt = safe_text((body or {}).get("prompt") or (body or {}).get("user_prompt") or (body or {}).get("intent"))
    if not prompt and isinstance(payload_copy.get("runMetadata"), dict):
        prompt = safe_text(payload_copy["runMetadata"].get("userPrompt"))

    run_metadata = payload_copy.get("runMetadata") if isinstance(payload_copy.get("runMetadata"), dict) else {}
    record = {
        "id": record_id,
        "createdAt": created_at,
        "title": title,
        "status": report_history_status(payload_copy),
        "source": source or safe_text(run_metadata.get("source")),
        "prompt": prompt,
        "model": safe_text((body or {}).get("model") or configured_model()),
        "summaryExcerpt": report_history_excerpt(safe_text(payload_copy.get("summaryMarkdown") or payload_copy.get("reportMarkdown"))),
        "payload": payload_copy,
    }
    path = REPORT_HISTORY_DIR / f"{record_id}.json"
    record["historyPath"] = display_path(path)
    temp_path = path.with_suffix(".tmp")
    temp_path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    temp_path.replace(path)
    return report_history_item(record)


def report_history_payload(limit: int = 50) -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    for path in report_history_files()[:limit]:
        try:
            items.append(report_history_item(read_report_history_file(path)))
        except Exception:
            continue
    return {
        "summary": {
            "count": len(items),
            "storage": display_path(REPORT_HISTORY_DIR),
        },
        "items": items,
    }


def report_history_detail(record_id: str) -> dict[str, Any]:
    safe_id = Path(unquote(record_id)).name
    path = REPORT_HISTORY_DIR / f"{safe_id}.json"
    if not path.exists():
        raise FileNotFoundError(f"Report history not found: {safe_id}")
    return read_report_history_file(path)


def mock_payload() -> dict[str, str]:
    report = """# 老板决策页：本地 API 联通测试

## 1. 一句话结论
前端已经连到本地 `/api/weekly-brief`，当前是 mock 模式。

## 2. 本周研究动作
| Rank | Ticker / Theme | Research Rating | Confidence | Est. Upside Range | Est. Holding Range | Exit / Trim Rule | Why Now | Hard Evidence Summary | Evidence Pack | Falsification |
|---:|---|---|---:|---|---|---|---|---|---|---|
| 1 | API Connection | No Rating | 0 | n/a | n/a | connection test only | 用于验证前后端链路 | 本地 backend 返回成功 | [证据包](./weekly-brief.evidence.md#api) | 真实后端未启动 |

## 3. 不进核心池
| Ticker / Theme | Treatment | Reason |
|---|---|---|
| Live Trading | Excluded | 项目只做研究，不做交易 |

## 4. 最大风险与下周验证
- 最大反证：真实 GPT 网关或上游后端不可用。
- 下周只看：
  1. API health 是否正常。
  2. 真实模型是否返回 JSON。
  3. evidenceMarkdown 是否包含原始来源。

## 附录：Intent Route Plan
- Task Type：connection_test。
- Data Node Status：mock only。
"""
    evidence = """# 证据包：本地 API 联通测试

[返回主报告](./weekly-brief.md)

## Evidence Index
| Ticker / Theme | Main Claim | Evidence Anchor |
|---|---|---|
| API | 前端已连接本地后端 | [API](#api) |

## API
| Evidence ID | Source Type | Date | Supports Which Claim | Fact / Inference / Hypothesis | Link | Notes |
|---|---|---|---|---|---|---|
| API-1 | Local health check | 2026-06-26 | 前后端联通 | Fact | ./api/health | Mock mode |

## Data Node Status
| Input Node | Status | Notes |
|---|---|---|
| Backend Adapter | success | Mock mode enabled |
"""
    return {
        "title": "本地 API 联通测试",
        "summaryMarkdown": extract_summary(report),
        "reportMarkdown": report,
        "evidenceMarkdown": evidence,
        "researchActionPool": [],
        "agentTrace": [
            {
                "agent": "Intent Router",
                "stepIndex": 1,
                "stepTotal": 3,
                "status": "success",
                "headline": "我先确认这只是本地 API 联通测试，不进入真实投研。",
                "thinking": "我在判断用户当前是不是要跑完整周报，还是只验证前后端是否连通。",
                "toolPlan": ["Backend health check", "Mock response"],
                "findings": ["后端可以返回 summary、report 和 evidence 三类 Markdown。"],
                "judgment": "当前只验证链路，不给任何研究型买卖倾向。",
                "nextStep": "如果真实模型和数据节点可用，再运行完整 agent workflow。",
            },
            {
                "agent": "Reflection",
                "stepIndex": 2,
                "stepTotal": 3,
                "status": "success",
                "headline": "这一步只验证 Wood/Buffett 辩论卡片的可视化样式。",
                "thinking": "我在检查 UI 是否能展示双方视角，而不是把原始 markdown 丢给用户。",
                "toolPlan": ["Mock reflection lens"],
                "findings": ["木头姐和巴菲特视角会被拆成两个清晰的观点块。"],
                "judgment": "可视化结构可用，但这不是实际投资结论。",
                "nextStep": "真实运行时由 Reflection agent 用上游证据生成辩论摘要。",
                "debate": {
                    "cathieWood": "木头姐视角：如果 AI 扩散速度被低估，市场可能低估长期创新弹性。",
                    "buffett": "巴菲特视角：如果现金流和估值不能支撑，故事再漂亮也要降级。",
                    "synthesis": "当前 mock 只验证呈现方式，不输出真实判断。",
                },
            },
        ],
    }


def chat_completion(
    *,
    api_key: str,
    base_url: str,
    model: str,
    messages: list[dict[str, str]],
    temperature: float = 0.2,
    timeout: float | None = None,
) -> str:
    if requests is None:
        raise RuntimeError("Python package 'requests' is required")

    response = requests.post(
        f"{base_url}/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        json={
            "model": model,
            "messages": messages,
            "temperature": temperature,
        },
        timeout=timeout if timeout is not None else float(env("WEEKLY_BRIEF_SECTION_TIMEOUT", "180")),
    )
    if response.status_code in {HTTPStatus.UNAUTHORIZED, HTTPStatus.FORBIDDEN}:
        raise RuntimeError(
            "模型网关鉴权失败：请检查 OPENAI_API_KEY、OPENAI_BASE_URL、OPENAI_MODEL，"
            "或确认当前 key 是否有该模型权限。这不是 Local Auth Token 问题。"
        )
    if response.status_code == HTTPStatus.TOO_MANY_REQUESTS:
        body = response.text[:1000] if hasattr(response, "text") else ""
        if re.search(r"insufficient_quota|quota|billing", body, re.IGNORECASE):
            raise RuntimeError(
                "模型网关额度不足：OpenAI 返回 429 insufficient_quota。"
                "请检查 API 账户余额、计费计划或更换可用的 OPENAI_API_KEY。"
            )
        raise RuntimeError("模型网关限流：OpenAI 返回 429，请稍后重试或更换可用模型/key。")

    response.raise_for_status()

    try:
        data = response.json()
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"模型网关响应不是合法 JSON：{exc}") from exc

    content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
    if not str(content).strip():
        raise RuntimeError("模型网关返回空内容")
    return str(content).strip()


def preflight_model_gateway(*, api_key: str, base_url: str, model: str) -> None:
    if env("WEEKLY_BRIEF_PREFLIGHT", "1").lower() in {"0", "false", "no"}:
        return
    chat_completion(
        api_key=api_key,
        base_url=base_url,
        model=model,
        messages=[{"role": "user", "content": "请只回复 pong，用于确认模型网关可用。"}],
        temperature=0,
        timeout=float(env("WEEKLY_BRIEF_PREFLIGHT_TIMEOUT", "20")),
    )


def agent_system_prompt(agent_path: str) -> str:
    prompt = read_text(agent_path, 30000)
    if not prompt:
        raise RuntimeError(f"Agent prompt not found: {agent_path}")
    output_standard = compact_output_standard_text()

    return f"""
{prompt}

## Research Report Output Standard

{output_standard}

## Runtime Boundary

- 你正在作为本地后端中的一个独立 agent section 运行，不是读取旧 reports 文件。
- 用户提示词是本次运行的最高任务输入；标题、主题、股票池和行业范围必须响应用户提示词。
- 当前后端会在上游输入中提供 `Data Node Evidence Bundle`。你只能使用该 bundle 里已经返回的新闻、论文、GitHub、行情、财报、SEC、舆情或宏观数据；bundle 缺失或不足的节点必须标为 `partial` 或 `failed`。
- 不得编造具体新闻标题、论文、链接、财务数字、实时行情或来源。可以输出研究框架、候选方向、验证清单和需要补充的数据。
- 如果用户主题不是 AI 行业，请按用户主题做美股研究编排，并把 AI 专用质量门槛标为不适用或 partial；不要把用户主题强行改回 AI。
- 输出中文 Markdown。投资输出只限研究用途，不输出下单、仓位、账户或自动交易动作。
- 在正文靠前位置写一个 `## Agent 公开思考摘要`，用清晰自然语言说明：我现在在判断什么、我需要/正在调用哪些数据节点、我看到了什么证据或缺口、我当前判断是什么、下一步交给谁。不要输出隐藏推理链、内部自言自语或未经验证的事实。
- 每个 section 必须包含 `## Downstream Handoff`，字段至少包括 Input Status、Decision Needed From Next Agent、Must-Carry Evidence、Key Assumptions、Missing Proof、Downgrade Triggers、Do-Not-Carry 和 Evidence Anchors。
- 完整周报最终输出默认使用 Version A：老板决策页 + 证据包。
""".strip()


def build_section_user_prompt(
    *,
    section_name: str,
    user_prompt: str,
    context_sections: dict[str, str],
    data_bundle: dict[str, Any] | None = None,
) -> str:
    today = date.today().isoformat()
    upstream = "\n\n".join(
        f"## 上游 Section：{name}\n{truncate_text(markdown, 12000)}"
        for name, markdown in context_sections.items()
    )
    if not upstream:
        upstream = "无。"
    fallback_universe = fallback_universe_markdown(user_prompt)
    data_markdown = (data_bundle or {}).get("markdown") or "## Data Node Evidence Bundle\n\n数据节点未采集或不可用。"

    return f"""
请运行当前 agent section：{section_name}

当前日期：{today}

用户原始请求：
{user_prompt}

上游输入：
{upstream}

候选研究脚手架（fallback_seed_universe）：
{fallback_universe}

本次真实数据节点输入（Data Node Evidence Bundle）：
{truncate_text(data_markdown, 14000)}

执行要求：
- 只输出当前 section 的 Markdown，不要输出 JSON。
- 明确写出本 section 是否 complete / partial / failed。
- 必须包含 `## Downstream Handoff`；下游能继承什么、缺什么、何时降级、不能带走什么都要写清楚。
- 用自然语言写清楚 agent 的公开工作轨迹，不要只输出参数表、状态表或原始 Markdown。
- 如果缺少真实外部数据源，必须写出缺口和下一步需要补的数据，不能用旧报告或想象数据补齐。
- 只把 Data Node Evidence Bundle 中有 source/date/link 或明确 API 来源的数据当作事实；不能自行补充 bundle 之外的新闻、论文、行情、财务数字或链接。
- 不允许把“上游没有候选、等待 Stock Discovery、暂无输出”作为本 section 的最终输出；如果真实发现不足，必须使用 `fallback_seed_universe` 输出本 agent 自己的验证清单和降级判断。
- `fallback_seed_universe` 只是研究脚手架，不是买卖建议、实时筛选结果或完整证据结论。
- 不要复用 `reports/` 目录中的历史结论。
""".strip()


def run_agent_section(
    *,
    api_key: str,
    base_url: str,
    model: str,
    agent_path: str,
    section_name: str,
    user_prompt: str,
    context_sections: dict[str, str],
    data_bundle: dict[str, Any] | None = None,
) -> str:
    return chat_completion(
        api_key=api_key,
        base_url=base_url,
        model=model,
        messages=[
            {"role": "system", "content": agent_system_prompt(agent_path)},
            {
                "role": "user",
                "content": build_section_user_prompt(
                    section_name=section_name,
                    user_prompt=user_prompt,
                    context_sections=context_sections,
                    data_bundle=data_bundle,
                ),
            },
        ],
        temperature=0.2,
    )


def section_wall_timeout_seconds() -> float:
    return float(env("WEEKLY_BRIEF_SECTION_WALL_TIMEOUT", env("WEEKLY_BRIEF_SECTION_TIMEOUT", "180")))


def run_with_wall_clock_timeout(label: str, timeout_seconds: float, func: Any, *args: Any, **kwargs: Any) -> Any:
    if timeout_seconds <= 0:
        return func(*args, **kwargs)

    result_queue: queue.Queue[tuple[bool, Any]] = queue.Queue(maxsize=1)

    def target() -> None:
        try:
            result_queue.put((True, func(*args, **kwargs)))
        except Exception as exc:  # noqa: BLE001 - preserve worker exception for caller
            result_queue.put((False, exc))

    thread = threading.Thread(target=target, name=f"weekly-brief-section-{label}", daemon=True)
    thread.start()
    thread.join(timeout_seconds)
    if thread.is_alive():
        raise TimeoutError(f"{label} reached wall-clock timeout={timeout_seconds:.1f}s")
    ok, value = result_queue.get()
    if ok:
        return value
    raise value


def generated_handoff_markdown(
    *,
    section_name: str,
    user_prompt: str,
    status: str,
    decision_needed: str,
    missing_proof: str,
    notes: str = "",
) -> str:
    return "\n".join(
        [
            "## Downstream Handoff",
            "| Field | Content |",
            "|---|---|",
            f"| Handoff ID | {snake_from_camel(section_name).replace(' ', '_')}-{today_iso()} |",
            f"| Input Status | {status} |",
            f"| Decision Needed From Next Agent | {decision_needed} |",
            "| Must-Carry Evidence | 仅继承本 section 明确标注的事实、框架、缺口、fallback_seed_universe 和 Data Node Evidence Bundle 状态。 |",
            "| Key Assumptions | Fact：本次只能使用 Data Node Evidence Bundle 中已返回的数据；Inference：seed universe 可作为研究入口；Hypothesis：候选仍需更多真实数据交叉验证。 |",
            f"| Missing Proof | {missing_proof} |",
            "| Downgrade Triggers | 实时新闻/论文/GitHub/财务/行情/舆情节点缺失、来源无法验证、上游 section failed。 |",
            "| Do-Not-Carry | 买卖建议、target price、仓位、账户动作、保证收益、旧报告结论、未验证新闻/财务/行情数字。 |",
            f"| Evidence Anchors | 用户请求：{prompt_label(user_prompt)}；fallback_seed_universe；docs/research-report-output-standard.md；{notes} |",
        ]
    )


def failed_section_markdown(section_name: str, exc: Exception) -> str:
    user_prompt = "本次研究"
    return "\n\n".join(
        [
            f"# {section_name} Section",
            "",
            "## Agent 公开思考摘要",
            (
                f"我正在运行 {section_name}，但这一段模型调用或数据输入节点失败，"
                "因此本 section 不能提供完整结论。后续 agent 会继续运行，并把这里标为缺口。"
            ),
            "",
            "## Section 状态",
            "状态：failed",
            "",
            "## 失败原因",
            f"后端运行失败：{exc}",
            "",
            "## 下一步",
            "后续 section 只能把本段作为缺失输入处理，不能补编新闻、论文、行情、财务数字或候选结论。",
            "",
            generated_handoff_markdown(
                section_name=section_name,
                user_prompt=user_prompt,
                status="failed",
                decision_needed="下游只能把本 section 作为缺失输入处理，并降低最终置信度。",
                missing_proof="本 section 模型调用或数据输入失败，缺失完整 section 输出。",
                notes=f"失败原因：{exc}",
            ),
        ]
    )


def section_output_focus(section_name: str) -> list[str]:
    if section_name == "Stock Discovery":
        return [
            "从 fallback_seed_universe 生成可继续验证的研究入口，避免候选池断流。",
            "把每个 ticker 标为“待真实数据验证”，不把它们升级为模型发现结论。",
            "下游 agent 必须围绕这组入口输出验证清单、缺口和降级判断。",
        ]
    if section_name == "AI 信息与舆情":
        return [
            "逐一列出新闻、论文、开源项目和高信号舆情需要验证的证据类型。",
            "把尚未接入的真实信息流标为 partial，不用旧报告或想象来源补齐。",
            "为每个 seed ticker 产出可执行的信息验证问题。",
        ]
    if section_name == "Fundamental":
        return [
            "围绕收入、利润率、现金流、capex、指引、估值和 SEC filings 建立验证清单。",
            "把缺少真实财报/consensus 数据标为 partial，不编造财务数字。",
            "指出哪些财务科目最能证伪或支持本轮研究入口。",
        ]
    if section_name == "Technical":
        return [
            "围绕价格、成交量、相对强弱、行业 ETF、支撑阻力和波动率建立图表验证清单。",
            "把缺少实时行情/K 线数据标为 partial，不编造价格点位。",
            "为每个 seed ticker 给出下一步需要拉取的技术面字段。",
        ]
    if section_name == "Reflection":
        return [
            "用长期创新弹性和价值纪律直接审查 seed universe。",
            "把所有结论降级为待证伪假设，不把脚手架 ticker 当作推荐。",
            "输出 Wood/Buffett 双视角的关键分歧和下一步验证动作。",
        ]
    if section_name == "Final Narrative":
        return [
            "报告首页仍从老板决策页开始，但结论降级为 partial research plan。",
            "Top list 只能展示待验证研究入口，不能伪装成完整筛选结果。",
            "把 Route Plan、数据缺口和 agent 输出审计放到附录。",
        ]
    if section_name == "Paper Attribution":
        return [
            "为 seed universe 建立 shadow ledger 观察字段，不连接实盘或交易。",
            "说明本轮无法做真实归因的原因，并列出下次复盘需要的数据。",
            "把反馈循环限制在研究观察层，不输出账户动作。",
        ]
    return [
        "基于 fallback_seed_universe 输出本 section 的验证清单。",
        "明确标注数据缺口，不编造事实或来源。",
        "给下一层 agent 留下可继续处理的结构化输入。",
    ]


def repaired_section_markdown(section_name: str, user_prompt: str, original_status: str = "partial") -> str:
    status = original_status if original_status in {"complete", "partial", "failed"} else "partial"
    if status == "complete":
        status = "partial"
    tickers = fallback_ticker_list(user_prompt)
    focus = section_output_focus(section_name)
    focus_lines = "\n".join(f"- {item}" for item in focus)
    return "\n\n".join(
        [
            f"# {section_name} Section",
            "",
            "## Agent 公开思考摘要",
            (
                f"本 section 没有把上游真实发现不足当成终点；我改用 `fallback_seed_universe` "
                f"作为可继续验证的研究脚手架，覆盖 {tickers}。这些 ticker 不是买卖建议，也不是实时筛选结论。"
            ),
            "",
            "## Section 状态",
            f"状态：{status}",
            "",
            "## 可继续验证的 fallback_seed_universe",
            fallback_universe_markdown(user_prompt),
            "",
            "## 本 section 输出",
            focus_lines,
            "",
            "## 当前判断",
            (
                "当前判断：真实外部数据节点仍为 partial；本 section 已产出可继续交给下一层的验证对象、"
                "验证问题和数据缺口，不能把 seed universe 直接升级为投资结论。"
            ),
            "",
            "## 下一步",
            "下一层 agent 必须基于这组 seed universe 继续输出自己的验证清单、缺口和降级判断。",
            "",
            generated_handoff_markdown(
                section_name=section_name,
                user_prompt=user_prompt,
                status=status,
                decision_needed="下游继续验证 seed universe，但必须保持 partial 降级纪律。",
                missing_proof="缺少真实外部新闻、论文、GitHub、行情、财务、SEC、舆情或图表数据。",
                notes=f"seed tickers：{tickers}",
            ),
        ]
    )


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
    for item in fallback_research_universe(user_prompt):
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
        audit_rows.append(
            f"| {index} | {name} | generated | 本次请求内独立模型调用；外部数据节点按 section 标注 partial/failed。 |"
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


def build_local_data_version_a_report(user_prompt: str, sections: dict[str, str], bundle: dict[str, Any]) -> str:
    enough = data_node_complete_enough(bundle)
    scored = []
    for index, item in enumerate(fallback_research_universe(user_prompt), start=1):
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
            confidence = min(75, 45 + coverage * 5)
            action_rows.append(
                "| {rank} | {ticker} / {company} | Hold-Watch | {confidence} | n/a：研究观察，不生成目标价 | "
                "7-14 days research review | 仅用于下周复核；不代表交易退出/止盈规则 | "
                "{why_now}；本次数据节点命中 {coverage} 条 | {evidence} | "
                "[证据包](./weekly-brief.evidence.md#data-node-detail) | "
                "若新闻/论文/GitHub/行情/财务/舆情任两类节点回落或 SEC/财务不能支持叙事，则降级为 No Rating |".format(
                    rank=rank,
                    ticker=item["ticker"],
                    company=markdown_table_cell(item["company"]),
                    confidence=confidence,
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


def workflow_engine_name() -> str:
    return "langgraph.StateGraph" if LANGGRAPH_AVAILABLE else "local.StateGraphFallback"


def workflow_node_name(value: str) -> str:
    name = re.sub(r"[^a-zA-Z0-9_]+", "_", value).strip("_").lower()
    return name or "node"


def emit_workflow_event(state: dict[str, Any], event: dict[str, Any]) -> None:
    emit = state.get("emit")
    if emit:
        emit(event)


def data_node_graph_node(state: dict[str, Any]) -> dict[str, Any]:
    next_state = dict(state)
    user_prompt = str(next_state.get("user_prompt") or DEFAULT_RESEARCH_INTENT)
    emit_workflow_event(next_state, {"event": "data_node_start", "stage": "数据节点采集开始"})
    data_bundle = collect_research_data_nodes(user_prompt)
    use_local_data_sections = local_data_sections_enabled(data_bundle)
    emit_workflow_event(
        next_state,
        {
            "event": "data_node_done",
            "stage": "数据节点采集完成",
            "preview": truncate_text((data_bundle.get("markdown") or "").replace("\n", " "), 520),
            "dataNodeStatus": data_bundle.get("nodes", {}),
            "useLocalDataSections": use_local_data_sections,
        },
    )
    next_state["data_bundle"] = data_bundle
    next_state["use_local_data_sections"] = use_local_data_sections
    return next_state


def agent_graph_node(
    state: dict[str, Any],
    *,
    section_name: str,
    agent_path: str,
    step_index: int,
    step_total: int,
) -> dict[str, Any]:
    next_state = dict(state)
    sections = dict(next_state.get("sections") or {})
    agent_traces = list(next_state.get("agent_traces") or [])
    user_prompt = str(next_state.get("user_prompt") or DEFAULT_RESEARCH_INTENT)
    data_bundle = next_state.get("data_bundle") or {"enabled": False, "nodes": {}, "markdown": ""}
    use_local_data_sections = bool(next_state.get("use_local_data_sections"))
    section_error = ""

    emit_workflow_event(
        next_state,
        {
            "event": "agent_start",
            "stage": f"{section_name} 开始",
            "agent": section_name,
            "stepIndex": step_index,
            "stepTotal": step_total,
        },
    )

    context = sections
    if use_local_data_sections:
        section_error = "local_data_node_section"
        section_markdown = local_data_section_markdown(section_name, user_prompt, data_bundle, context)
    elif section_name == "Final Narrative" and should_use_local_final_narrative(sections):
        section_error = "local_version_a_fallback_due_to_failed_critical_sections"
        section_markdown = build_local_version_a_report(user_prompt, sections)
    elif section_name == "Paper Attribution" and infer_section_status(sections.get("Final Narrative", "")) != "complete":
        section_error = "local_paper_attribution_due_to_partial_final_narrative"
        section_markdown = repaired_section_markdown(section_name, user_prompt, "partial")
    else:
        try:
            section_markdown = run_with_wall_clock_timeout(
                section_name,
                section_wall_timeout_seconds(),
                run_agent_section,
                api_key=next_state.get("api_key", ""),
                base_url=next_state.get("base_url", ""),
                model=next_state.get("fast_model") if section_name != "Final Narrative" else next_state.get("model"),
                agent_path=agent_path,
                section_name=section_name,
                user_prompt=user_prompt,
                context_sections=context,
                data_bundle=data_bundle,
            )
        except Exception as exc:  # noqa: BLE001 - section failures should not hide the rest of the workflow
            section_error = str(exc)
            section_markdown = failed_section_markdown(section_name, exc)

    sections[section_name] = ensure_section_actionable_output(
        section_name=section_name,
        markdown=section_markdown,
        user_prompt=user_prompt,
    )
    trace = build_agent_trace(
        section_name=section_name,
        markdown=sections[section_name],
        user_prompt=user_prompt,
        step_index=step_index,
        step_total=step_total,
    )
    agent_traces.append(trace)
    emit_workflow_event(
        next_state,
        {
            "event": "agent_done",
            "stage": f"{section_name} 完成",
            "agent": section_name,
            "stepIndex": step_index,
            "stepTotal": step_total,
            "preview": truncate_text(sections[section_name].replace("\n", " "), 420),
            "thinkingTrace": trace,
            "sectionMarkdown": sections[section_name],
            "sectionError": section_error,
        },
    )

    next_state["sections"] = sections
    next_state["agent_traces"] = agent_traces
    return next_state


def final_payload_graph_node(state: dict[str, Any]) -> dict[str, Any]:
    next_state = dict(state)
    user_prompt = str(next_state.get("user_prompt") or DEFAULT_RESEARCH_INTENT)
    sections = dict(next_state.get("sections") or {})
    data_bundle = next_state.get("data_bundle") or {"enabled": False, "nodes": {}, "markdown": ""}

    emit_workflow_event(next_state, {"event": "final_payload_start", "stage": "Final Report 组装开始"})
    payload = build_workflow_payload_from_sections(user_prompt, sections, data_bundle)
    payload["agentTrace"] = list(next_state.get("agent_traces") or [])
    payload.setdefault("runMetadata", {})
    if isinstance(payload["runMetadata"], dict):
        payload["runMetadata"]["workflowEngine"] = safe_text(next_state.get("workflow_engine") or workflow_engine_name())
        payload["runMetadata"]["workflowGraph"] = list(next_state.get("workflow_graph") or [])
        payload["runMetadata"]["dataNodesEnabled"] = bool(data_bundle.get("enabled"))
        payload["runMetadata"]["localDataSections"] = bool(next_state.get("use_local_data_sections"))
    emit_workflow_event(
        next_state,
        {
            "event": "final_payload_done",
            "stage": "Final Report 组装完成",
            "title": payload.get("title"),
        },
    )
    next_state["payload"] = payload
    return next_state


def workflow_graph_nodes() -> tuple[list[str], dict[str, Any]]:
    total = len(AGENT_WORKFLOW)
    node_order = ["collect_data_nodes"]
    node_funcs: dict[str, Any] = {"collect_data_nodes": data_node_graph_node}
    for index, (section_key, section_name, agent_path) in enumerate(AGENT_WORKFLOW, start=1):
        node_name = f"agent_{workflow_node_name(section_key)}"
        node_order.append(node_name)

        def make_node(section_name: str = section_name, agent_path: str = agent_path, index: int = index) -> Any:
            return lambda state: agent_graph_node(
                state,
                section_name=section_name,
                agent_path=agent_path,
                step_index=index,
                step_total=total,
            )

        node_funcs[node_name] = make_node()
    node_order.append("assemble_final_payload")
    node_funcs["assemble_final_payload"] = final_payload_graph_node
    return node_order, node_funcs


def run_workflow_graph_locally(
    initial_state: dict[str, Any],
    node_order: list[str],
    node_funcs: dict[str, Any],
    *,
    engine_name: str,
) -> dict[str, Any]:
    state = dict(initial_state)
    state["workflow_engine"] = engine_name
    for node_name in node_order:
        state = node_funcs[node_name](state)
    return state


def run_workflow_graph(initial_state: dict[str, Any], node_order: list[str], node_funcs: dict[str, Any]) -> dict[str, Any]:
    if LANGGRAPH_AVAILABLE and LangGraphStateGraph is not None:
        try:
            graph = LangGraphStateGraph(dict)
            for node_name in node_order:
                graph.add_node(node_name, node_funcs[node_name])
            graph.add_edge(LANGGRAPH_START, node_order[0])
            for current_node, next_node in zip(node_order, node_order[1:]):
                graph.add_edge(current_node, next_node)
            graph.add_edge(node_order[-1], LANGGRAPH_END)
            state = dict(initial_state)
            state["workflow_engine"] = "langgraph.StateGraph"
            return graph.compile().invoke(state)
        except Exception as exc:  # noqa: BLE001 - keep delivery stable if optional dependency changes
            fallback_state = dict(initial_state)
            fallback_state["workflow_engine_error"] = str(exc)
            return run_workflow_graph_locally(
                fallback_state,
                node_order,
                node_funcs,
                engine_name="local.StateGraphFallback(after_langgraph_error)",
            )

    return run_workflow_graph_locally(
        initial_state,
        node_order,
        node_funcs,
        engine_name="local.StateGraphFallback",
    )


def run_agent_workflow(
    *,
    api_key: str,
    base_url: str,
    model: str,
    user_prompt: str,
    on_event: Any | None = None,
) -> dict[str, Any]:
    node_order, node_funcs = workflow_graph_nodes()
    initial_state = {
        "api_key": api_key,
        "base_url": base_url,
        "model": model,
        "fast_model": configured_fast_model(),
        "user_prompt": user_prompt,
        "sections": {},
        "agent_traces": [],
        "workflow_graph": node_order,
        "emit": on_event,
    }
    final_state = run_workflow_graph(initial_state, node_order, node_funcs)
    payload = final_state.get("payload")
    if isinstance(payload, dict):
        return payload

    sections = dict(final_state.get("sections") or {})
    data_bundle = final_state.get("data_bundle") if isinstance(final_state.get("data_bundle"), dict) else None
    fallback_payload_result = build_workflow_payload_from_sections(user_prompt, sections, data_bundle)
    fallback_payload_result["agentTrace"] = list(final_state.get("agent_traces") or [])
    return fallback_payload_result


def call_upstream(body: dict[str, Any]) -> dict[str, Any]:
    upstream_url = env("WEEKLY_BRIEF_UPSTREAM_URL")
    if not upstream_url:
        raise RuntimeError("WEEKLY_BRIEF_UPSTREAM_URL is not configured")
    if requests is None:
        raise RuntimeError("Python package 'requests' is required")

    headers = {"Accept": "application/json, text/markdown, text/plain"}
    upstream_token = env("WEEKLY_BRIEF_UPSTREAM_TOKEN")
    if upstream_token:
        headers["Authorization"] = f"Bearer {upstream_token}"

    response = requests.post(
        upstream_url,
        json=body,
        headers=headers,
        timeout=float(env("WEEKLY_BRIEF_TIMEOUT", "900")),
    )
    response.raise_for_status()

    content_type = response.headers.get("content-type", "")
    if "application/json" in content_type:
        return normalize_payload(response.json())
    return fallback_payload(response.text)


def call_openai(body: dict[str, Any]) -> dict[str, Any]:
    user_prompt = request_user_prompt(body)

    if requests is None:
        raise RuntimeError("Python package 'requests' is required")

    api_key = configured_api_key()
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is missing. Fill .env or set LLM_API_KEY_ENV.")

    base_url = configured_base_url().rstrip("/")
    model = body.get("model") or configured_model()
    preflight_model_gateway(api_key=api_key, base_url=base_url, model=str(model))

    if env("WEEKLY_BRIEF_SINGLE_CALL") == "1":
        content = chat_completion(
            api_key=api_key,
            base_url=base_url,
            model=str(model),
            messages=build_messages(str(user_prompt)),
            temperature=0.2,
        )
        parsed = extract_json_object(content)
        payload = normalize_payload(parsed or content)
        payload["runMetadata"] = {
            "source": "single_model_call",
            "userPrompt": str(user_prompt),
        }
        return payload

    return run_agent_workflow(
        api_key=api_key,
        base_url=base_url,
        model=str(model),
        user_prompt=str(user_prompt),
    )


def current_mode() -> str:
    if env("WEEKLY_BRIEF_MOCK") == "1":
        return "mock"
    if env("WEEKLY_BRIEF_UPSTREAM_URL"):
        return "proxy"
    return "openai"


def health_payload() -> dict[str, Any]:
    return {
        "ok": True,
        "service": "weekly-brief-backend",
        "mode": current_mode(),
        "model": configured_model(),
        "baseUrl": redact_url(configured_base_url()),
        "hasApiKey": bool(configured_api_key()),
        "upstreamUrl": redact_url(env("WEEKLY_BRIEF_UPSTREAM_URL")),
    }


class Handler(BaseHTTPRequestHandler):
    server_version = "WeeklyBriefBackend/0.1"

    def do_OPTIONS(self) -> None:
        self.send_response(HTTPStatus.NO_CONTENT)
        self.send_cors_headers()
        self.end_headers()

    def do_GET(self) -> None:
        path = self.path.split("?", 1)[0].rstrip("/")
        if path in {"", "/"}:
            self.send_json({"ok": True, "endpoints": ["/api/health", "/api/weekly-brief", "/api/pond"]})
            return
        if path == "/api/health":
            self.send_json(health_payload())
            return
        if path == "/api/reports":
            self.send_json(report_history_payload())
            return
        if path.startswith("/api/reports/"):
            try:
                self.send_json(report_history_detail(path.rsplit("/", 1)[-1]))
            except FileNotFoundError as exc:
                self.send_error_json(HTTPStatus.NOT_FOUND, str(exc))
            except Exception as exc:  # noqa: BLE001
                self.send_error_json(HTTPStatus.INTERNAL_SERVER_ERROR, str(exc))
            return
        if path == "/api/pond":
            self.send_json(pond_payload())
            return
        self.send_error_json(HTTPStatus.NOT_FOUND, "Not found")

    def do_POST(self) -> None:
        path = self.path.split("?", 1)[0].rstrip("/")
        if path == "/api/pond/select":
            try:
                self.send_json(select_pond_candidate(self.read_json_body()))
            except Exception as exc:  # noqa: BLE001
                self.send_error_json(HTTPStatus.INTERNAL_SERVER_ERROR, str(exc))
            return
        if path == "/api/pond/refresh":
            try:
                self.send_json(refresh_pond_prices())
            except Exception as exc:  # noqa: BLE001
                self.send_error_json(HTTPStatus.INTERNAL_SERVER_ERROR, str(exc))
            return
        if path != "/api/weekly-brief":
            self.send_error_json(HTTPStatus.NOT_FOUND, "Not found")
            return

        body: dict[str, Any] = {}
        try:
            body = self.read_json_body()
            if current_mode() == "openai" and "text/event-stream" in self.headers.get("Accept", ""):
                self.send_openai_event_stream(body)
                return
            if current_mode() == "mock":
                payload = mock_payload()
            elif current_mode() == "proxy":
                payload = call_upstream(body)
            else:
                payload = call_openai(body)
            history_item = save_report_history(payload, body, source=current_mode())
            payload.setdefault("runMetadata", {})
            if isinstance(payload["runMetadata"], dict):
                payload["runMetadata"]["historyId"] = history_item["id"]
                payload["runMetadata"]["historyCreatedAt"] = history_item["createdAt"]
            self.send_json(payload)
        except Exception as exc:  # noqa: BLE001 - endpoint returns readable errors
            if path == "/api/weekly-brief":
                try:
                    save_report_history(error_report_payload(str(exc), body), body, source=f"{current_mode()}_error")
                except Exception:
                    pass
            self.send_error_json(HTTPStatus.INTERNAL_SERVER_ERROR, str(exc))

    def send_openai_event_stream(self, body: dict[str, Any]) -> None:
        self.send_response(HTTPStatus.OK)
        self.send_cors_headers()
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.end_headers()

        def emit(event: dict[str, Any]) -> None:
            data = json.dumps(event, ensure_ascii=False).encode("utf-8")
            self.wfile.write(b"data: " + data + b"\n\n")
            self.wfile.flush()

        try:
            user_prompt = request_user_prompt(body)
            emit({"event": "run_start", "stage": "后端已接收请求", "prompt": user_prompt})

            api_key = configured_api_key()
            if not api_key:
                raise RuntimeError("OPENAI_API_KEY is missing. Fill .env or set LLM_API_KEY_ENV.")
            base_url = configured_base_url().rstrip("/")
            model = str(body.get("model") or configured_model())
            emit({"event": "gateway_check_start", "stage": "模型网关预检开始"})
            preflight_model_gateway(api_key=api_key, base_url=base_url, model=model)
            emit({"event": "gateway_check_done", "stage": "模型网关预检通过"})

            payload = run_agent_workflow(
                api_key=api_key,
                base_url=base_url,
                model=model,
                user_prompt=str(user_prompt),
                on_event=emit,
            )
            history_item = save_report_history(payload, body, source="openai_stream")
            payload.setdefault("runMetadata", {})
            if isinstance(payload["runMetadata"], dict):
                payload["runMetadata"]["historyId"] = history_item["id"]
                payload["runMetadata"]["historyCreatedAt"] = history_item["createdAt"]
            emit({"event": "run_done", "stage": "完成", **payload})
            self.wfile.write(b"data: [DONE]\n\n")
            self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            return
        except Exception as exc:  # noqa: BLE001
            error_payload = error_report_payload(str(exc), body)
            try:
                history_item = save_report_history(error_payload, body, source="openai_stream_error")
                error_payload.setdefault("runMetadata", {})
                if isinstance(error_payload["runMetadata"], dict):
                    error_payload["runMetadata"]["historyId"] = history_item["id"]
                    error_payload["runMetadata"]["historyCreatedAt"] = history_item["createdAt"]
            except Exception:
                pass
            try:
                emit(
                    {
                        "event": "run_error",
                        "stage": "运行失败",
                        **error_payload,
                        "error": str(exc),
                    }
                )
                self.wfile.write(b"data: [DONE]\n\n")
                self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError):
                return

    def read_json_body(self) -> dict[str, Any]:
        raw_length = self.headers.get("Content-Length", "0")
        length = int(raw_length or "0")
        raw = self.rfile.read(length).decode("utf-8") if length else "{}"
        try:
            value = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON: {exc}") from exc
        if not isinstance(value, dict):
            raise ValueError("Request body must be a JSON object")
        return value

    def send_cors_headers(self) -> None:
        origin = self.headers.get("Origin") or "*"
        self.send_header("Access-Control-Allow-Origin", origin)
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.send_header("Vary", "Origin")

    def send_json(self, payload: dict[str, Any], status: int = HTTPStatus.OK) -> None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_cors_headers()
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def send_error_json(self, status: int, message: str) -> None:
        self.send_json({"ok": False, "error": message}, status)

    def log_message(self, fmt: str, *args: Any) -> None:
        sys.stderr.write("%s - - [%s] %s\n" % (self.address_string(), self.log_date_time_string(), fmt % args))


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the weekly brief local backend")
    parser.add_argument("--host", default=env("WEEKLY_BRIEF_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(env("WEEKLY_BRIEF_PORT", str(DEFAULT_PORT))))
    args = parser.parse_args()

    load_env_file(ROOT / ".env")
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"Weekly brief backend listening on http://{args.host}:{args.port}")
    print(f"Mode: {current_mode()} | Model: {configured_model()} | API key: {'set' if configured_api_key() else 'missing'}")
    server.serve_forever()


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Local API adapter for the weekly AI US equity research frontend.

The browser should never receive model API keys. This server keeps keys on the
local machine, exposes a small CORS-safe API to the static frontend, and either
proxies an existing weekly-brief backend or calls an OpenAI-compatible chat API.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
from datetime import date, datetime, timedelta
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

try:
    import requests
except ImportError:  # pragma: no cover - surfaced via health/error response
    requests = None


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PORT = 8787
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


def fetch_daily_closes(ticker: str) -> list[tuple[str, float]]:
    if requests is None:
        raise RuntimeError("Python package 'requests' is required")
    symbol = yahoo_symbol(ticker)
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
    response = requests.get(
        url,
        params={"range": "6mo", "interval": "1d", "events": "history"},
        headers={"Accept": "application/json", "User-Agent": "weekly-brief-pond/0.1"},
        timeout=12,
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
    headline = bullets[0] if bullets else (sentences[0] if sentences else f"{section_name} 已生成公开思考摘要。")
    judgment = sentences[1] if len(sentences) > 1 else headline
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

        for table_index in range(index + 1, min(index + 24, len(lines))):
            if "|" not in lines[table_index]:
                continue
            headers = split_markdown_table_row(lines[table_index])
            if table_index + 1 >= len(lines) or not is_markdown_separator(lines[table_index + 1]):
                continue

            for row_line in lines[table_index + 2 :]:
                if "|" not in row_line or row_line.lstrip().startswith("#"):
                    break
                cells = split_markdown_table_row(row_line)
                if len(cells) < 2:
                    continue
                candidate = candidate_from_table_row(headers, cells, decision_date, run_id)
                if candidate:
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
            pool.append(
                {
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
            )

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


def mock_payload() -> dict[str, str]:
    report = """# 老板决策页：本地 API 联通测试

## 1. 一句话结论
前端已经连到本地 `/api/weekly-brief`，当前是 mock 模式。

## 2. 本周研究动作
| Rank | Ticker / Theme | Research Rating | Why Now | Hard Evidence Summary | Evidence Pack | Falsification |
|---:|---|---|---|---|---|---|
| 1 | API Connection | No Rating | 用于验证前后端链路 | 本地 backend 返回成功 | [证据包](./weekly-brief.evidence.md#api) | 真实后端未启动 |

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
        "researchActionPool": [
            {
                "runId": f"mock-{today_iso()}",
                "decisionDate": today_iso(),
                "thesisId": "API-1",
                "rank": 1,
                "ticker": "API",
                "company": "API Connection",
                "actionRating": "No Rating",
                "confidence": None,
                "estimatedUpsideLowPct": None,
                "estimatedUpsideBasePct": None,
                "estimatedUpsideHighPct": None,
                "estimatedHoldingMinDays": None,
                "estimatedHoldingMaxDays": None,
                "exitOrTrimRule": "connection test only",
                "invalidationCondition": "真实后端未启动",
                "thesisSummary": "本地 API 联通测试",
                "hardEvidence": "本地 backend 返回成功",
                "whyNow": "用于验证前后端链路",
                "nextWeekCheck": "API health 是否正常",
                "evidencePackHref": "./weekly-brief.evidence.md#api",
                "benchmarkPrimary": "QQQ",
            }
        ],
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
        timeout=float(env("WEEKLY_BRIEF_TIMEOUT", "900")),
    )
    if response.status_code in {HTTPStatus.UNAUTHORIZED, HTTPStatus.FORBIDDEN}:
        raise RuntimeError(
            "模型网关鉴权失败：请检查 OPENAI_API_KEY、OPENAI_BASE_URL、OPENAI_MODEL，"
            "或确认当前 key 是否有该模型权限。这不是 Local Auth Token 问题。"
        )

    response.raise_for_status()

    try:
        data = response.json()
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"模型网关响应不是合法 JSON：{exc}") from exc

    content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
    if not str(content).strip():
        raise RuntimeError("模型网关返回空内容")
    return str(content).strip()


def agent_system_prompt(agent_path: str) -> str:
    prompt = read_text(agent_path, 30000)
    if not prompt:
        raise RuntimeError(f"Agent prompt not found: {agent_path}")

    return f"""
{prompt}

## Runtime Boundary

- 你正在作为本地后端中的一个独立 agent section 运行，不是读取旧 reports 文件。
- 用户提示词是本次运行的最高任务输入；标题、主题、股票池和行业范围必须响应用户提示词。
- 当前后端没有直接接入新闻、论文、GitHub、行情、财报、SEC、舆情或券商账户数据节点。除非上游输入中已经提供了可核验数据，否则必须把对应数据节点标为 `partial` 或 `failed`。
- 不得编造具体新闻标题、论文、链接、财务数字、实时行情或来源。可以输出研究框架、候选方向、验证清单和需要补充的数据。
- 如果用户主题不是 AI 行业，请按用户主题做美股研究编排，并把 AI 专用质量门槛标为不适用或 partial；不要把用户主题强行改回 AI。
- 输出中文 Markdown。投资输出只限研究用途，不输出下单、仓位、账户或自动交易动作。
- 在正文靠前位置写一个 `## Agent 公开思考摘要`，用清晰自然语言说明：我现在在判断什么、我需要/正在调用哪些数据节点、我看到了什么证据或缺口、我当前判断是什么、下一步交给谁。不要输出隐藏推理链、内部自言自语或未经验证的事实。
""".strip()


def build_section_user_prompt(
    *,
    section_name: str,
    user_prompt: str,
    context_sections: dict[str, str],
) -> str:
    today = date.today().isoformat()
    upstream = "\n\n".join(
        f"## 上游 Section：{name}\n{truncate_text(markdown, 12000)}"
        for name, markdown in context_sections.items()
    )
    if not upstream:
        upstream = "无。"

    return f"""
请运行当前 agent section：{section_name}

当前日期：{today}

用户原始请求：
{user_prompt}

上游输入：
{upstream}

执行要求：
- 只输出当前 section 的 Markdown，不要输出 JSON。
- 明确写出本 section 是否 complete / partial / failed。
- 用自然语言写清楚 agent 的公开工作轨迹，不要只输出参数表、状态表或原始 Markdown。
- 如果缺少真实外部数据源，必须写出缺口和下一步需要补的数据，不能用旧报告或想象数据补齐。
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
                ),
            },
        ],
        temperature=0.2,
    )


def build_final_payload_prompt(user_prompt: str, sections: dict[str, str]) -> str:
    section_bundle = "\n\n".join(
        f"# Agent Output: {name}\n{truncate_text(markdown, 16000)}"
        for name, markdown in sections.items()
    )
    return f"""
请把以下本次运行产生的 agent sections 汇总成前端需要的 JSON。

用户原始请求：
{user_prompt}

本次 agent outputs：
{section_bundle}

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
    if "failed" in lowered or "失败" in text:
        return "failed/partial"
    if "partial" in lowered or "缺口" in text or "缺少" in text or "不可用" in text:
        return "partial"
    return "generated"


def build_workflow_evidence(user_prompt: str, sections: dict[str, str]) -> str:
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
            "| News / Papers / GitHub / Market / Fundamentals / Sentiment Nodes | partial/failed | 当前本地后端尚未接入这些实时外部数据节点；不得把缺失数据伪装成事实。 |",
            "",
            "## Agent Section Manifest",
            *manifest_rows,
        ]
    )


def build_workflow_payload_from_sections(user_prompt: str, sections: dict[str, str]) -> dict[str, Any]:
    report_source = sections.get("Final Narrative") or "\n\n".join(
        f"# {name}\n\n{markdown.strip()}" for name, markdown in sections.items()
    )
    report = ensure_boss_decision_page(report_source, user_prompt)
    title = title_from_markdown(report, f"老板决策页：{prompt_label(user_prompt)}")
    payload: dict[str, Any] = {
        "title": title,
        "summaryMarkdown": extract_summary(report),
        "reportMarkdown": report,
        "evidenceMarkdown": build_workflow_evidence(user_prompt, sections),
    }
    return append_run_audit(payload, sections, user_prompt)


def run_agent_workflow(
    *,
    api_key: str,
    base_url: str,
    model: str,
    user_prompt: str,
    on_event: Any | None = None,
) -> dict[str, Any]:
    sections: dict[str, str] = {}
    agent_traces: list[dict[str, Any]] = []
    total = len(AGENT_WORKFLOW)

    def emit(event: dict[str, Any]) -> None:
        if on_event:
            on_event(event)

    for index, (_key, section_name, agent_path) in enumerate(AGENT_WORKFLOW, start=1):
        emit(
            {
                "event": "agent_start",
                "stage": f"{section_name} 开始",
                "agent": section_name,
                "stepIndex": index,
                "stepTotal": total,
            }
        )
        if section_name == "Paper Attribution":
            context = sections
        elif section_name == "Final Narrative":
            context = sections
        else:
            context = sections
        sections[section_name] = run_agent_section(
            api_key=api_key,
            base_url=base_url,
            model=model,
            agent_path=agent_path,
            section_name=section_name,
            user_prompt=user_prompt,
            context_sections=context,
        )
        trace = build_agent_trace(
            section_name=section_name,
            markdown=sections[section_name],
            user_prompt=user_prompt,
            step_index=index,
            step_total=total,
        )
        agent_traces.append(trace)
        emit(
            {
                "event": "agent_done",
                "stage": f"{section_name} 完成",
                "agent": section_name,
                "stepIndex": index,
                "stepTotal": total,
                "preview": truncate_text(sections[section_name].replace("\n", " "), 420),
                "thinkingTrace": trace,
                "sectionMarkdown": sections[section_name],
            }
        )

    emit({"event": "final_payload_start", "stage": "Final Report 组装开始"})
    payload = build_workflow_payload_from_sections(user_prompt, sections)
    emit(
        {
            "event": "final_payload_done",
            "stage": "Final Report 组装完成",
            "title": payload.get("title"),
        }
    )
    payload["agentTrace"] = agent_traces
    return payload


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
    user_prompt = body.get("prompt") or body.get("user_prompt") or body.get("intent") or ""
    if not str(user_prompt).strip():
        raise ValueError("Request body must include prompt")

    if requests is None:
        raise RuntimeError("Python package 'requests' is required")

    api_key = configured_api_key()
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is missing. Fill .env or set LLM_API_KEY_ENV.")

    base_url = configured_base_url().rstrip("/")
    model = body.get("model") or configured_model()

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
            self.send_json(payload)
        except Exception as exc:  # noqa: BLE001 - endpoint returns readable errors
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
            emit({"event": "run_start", "stage": "后端已接收请求", "prompt": body.get("prompt") or body.get("intent")})
            user_prompt = body.get("prompt") or body.get("user_prompt") or body.get("intent") or ""
            if not str(user_prompt).strip():
                raise ValueError("Request body must include prompt")

            api_key = configured_api_key()
            if not api_key:
                raise RuntimeError("OPENAI_API_KEY is missing. Fill .env or set LLM_API_KEY_ENV.")

            payload = run_agent_workflow(
                api_key=api_key,
                base_url=configured_base_url().rstrip("/"),
                model=str(body.get("model") or configured_model()),
                user_prompt=str(user_prompt),
                on_event=emit,
            )
            emit({"event": "run_done", "stage": "完成", **payload})
            self.wfile.write(b"data: [DONE]\n\n")
            self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            return
        except Exception as exc:  # noqa: BLE001
            error_report = f"# 研究未完成\n\n后端运行失败：{exc}"
            try:
                emit(
                    {
                        "event": "run_error",
                        "stage": "运行失败",
                        "title": "研究未完成",
                        "summaryMarkdown": error_report,
                        "reportMarkdown": error_report,
                        "evidenceMarkdown": "# 证据包：研究未完成\n\n## Data Node Status\n- Backend：failed",
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

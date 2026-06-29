from __future__ import annotations

import os
import re
from datetime import date, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import unquote_plus, urlsplit, urlunsplit

try:
    import requests
except ImportError:  # pragma: no cover - surfaced via health/error response
    requests = None

ROOT = Path(__file__).resolve().parents[3]
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


def research_seed_universe(user_prompt: str) -> list[dict[str, str]]:
    prompt = str(user_prompt or "").lower()
    full_market = bool(
        re.search(
            r"全市场|全美股|美股全市场|market[-\s]?wide|broad\s+market|all\s+market|周报|机会扫描",
            prompt,
            re.IGNORECASE,
        )
    )
    keys = ["ai", "consumer", "finance", "broad"] if full_market else [fallback_universe_key(user_prompt)]
    seen: set[str] = set()
    universe: list[dict[str, str]] = []
    for key in keys:
        for item in FALLBACK_RESEARCH_UNIVERSES[key]:
            ticker = item["ticker"]
            if ticker in seen:
                continue
            seen.add(ticker)
            universe.append(dict(item))
    try:
        limit = int(env("WEEKLY_BRIEF_SEED_LIMIT", "24"))
    except ValueError:
        limit = 24
    return universe[: max(limit, 1)]


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
    redacted = re.sub(r"(?<=://)[^/@]+@", "***@", str(value))
    redacted = re.sub(
        r"([?&](?:token|api_key|apikey|key|secret|password|auth)=)[^&\s|)]+",
        r"\1***",
        redacted,
        flags=re.IGNORECASE,
    )
    parts = urlsplit(redacted)
    if not parts.query:
        return redacted

    sensitive_terms = ("token", "api_key", "apikey", "key", "secret", "password", "auth")
    query_parts: list[str] = []
    for raw_part in parts.query.split("&"):
        if not raw_part:
            query_parts.append(raw_part)
            continue
        raw_key, separator, raw_value = raw_part.partition("=")
        decoded_key = unquote_plus(raw_key).lower()
        if separator and any(term in decoded_key for term in sensitive_terms):
            query_parts.append(f"{raw_key}=***")
        else:
            query_parts.append(raw_part)
    return urlunsplit(parts._replace(query="&".join(query_parts)))


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


def normalize_ticker(value: str) -> str:
    match = re.search(r"\b[A-Z]{1,5}(?:\.[A-Z])?\b", safe_text(value).upper())
    return match.group(0) if match else ""


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


def prompt_label(user_prompt: str, max_chars: int = 42) -> str:
    label = re.sub(r"\s+", " ", str(user_prompt).strip()) or "本次研究"
    if label == DEFAULT_RESEARCH_INTENT:
        label = "美股全市场机会扫描"
    if len(label) <= max_chars:
        return label
    return label[:max_chars].rstrip() + "..."


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

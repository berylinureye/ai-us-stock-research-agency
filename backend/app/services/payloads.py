from __future__ import annotations

import json
import os
import re
from datetime import date, datetime
from pathlib import Path
from typing import Any
from urllib.parse import unquote

from ..core.config import (
    DEFAULT_RESEARCH_INTENT,
    ROOT,
    compact_output_standard_text,
    compact_percent,
    configured_model,
    normalize_ticker,
    parse_float,
    read_text,
    request_user_prompt,
    safe_text,
    today_iso,
)

REPORT_HISTORY_DIR = Path(os.environ.get("REPORT_HISTORY_DIR") or ROOT / "data" / "report-history")

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


def title_from_markdown(markdown: str, fallback: str) -> str:
    match = re.search(r"^#\s+(.+)$", markdown.strip(), re.MULTILINE)
    return match.group(1).strip() if match else fallback


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
        if isinstance(value.get("agentTrace"), list):
            payload["agentTrace"] = value["agentTrace"]
        elif isinstance(value.get("agent_trace"), list):
            payload["agentTrace"] = value["agent_trace"]
        else:
            payload["agentTrace"] = []
        if isinstance(value.get("runMetadata"), dict):
            payload["runMetadata"] = dict(value["runMetadata"])
        elif isinstance(value.get("run_metadata"), dict):
            payload["runMetadata"] = dict(value["run_metadata"])
        payload["researchActionPool"] = normalize_research_action_pool(value, payload["reportMarkdown"])
        return payload

    payload = fallback_payload(str(value))
    payload["researchActionPool"] = normalize_research_action_pool({}, payload["reportMarkdown"])
    payload["agentTrace"] = []
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
    first_screen = report[:1200]
    if "研究未完成" in title or re.search(r"^#\s*研究未完成", report, re.MULTILINE):
        return "failed"
    lowered = report.lower()
    action_pool = payload.get("researchActionPool")
    if isinstance(action_pool, list) and action_pool:
        return "complete"
    if "后端运行失败" in first_screen:
        return "failed"
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
| 1 | API Connection | No Rating | 0 | n/a | n/a | connection test only | 用于验证前后端链路 | 本地 backend 返回成功 | [证据包](./weekly-brief.evidence.md#api) | 真实投研 workflow 未运行 |

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

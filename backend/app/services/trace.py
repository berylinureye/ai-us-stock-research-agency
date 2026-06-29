from __future__ import annotations

import re
from typing import Any

from ..core.config import fallback_ticker_list, infer_section_status, prompt_label
from .agent_sections import section_output_focus

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

from __future__ import annotations

import queue
import re
import threading
from datetime import date
from http import HTTPStatus
from typing import Any

try:
    import requests
except ImportError:  # pragma: no cover - surfaced via health/error response
    requests = None

from ..core.config import (
    compact_output_standard_text,
    env,
    fallback_ticker_list,
    fallback_universe_markdown,
    prompt_label,
    read_text,
    snake_from_camel,
    today_iso,
    truncate_text,
)

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
    context_limit = section_context_limit(section_name)
    data_limit = section_data_limit(section_name)
    upstream = "\n\n".join(
        f"## 上游 Section：{name}\n{truncate_text(markdown, context_limit)}"
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
{truncate_text(data_markdown, data_limit)}

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


def section_context_limit(section_name: str) -> int:
    if section_name == "Final Narrative":
        return int(env("WEEKLY_BRIEF_FINAL_CONTEXT_LIMIT", "3000"))
    return int(env("WEEKLY_BRIEF_SECTION_CONTEXT_LIMIT", "12000"))


def section_data_limit(section_name: str) -> int:
    if section_name == "Final Narrative":
        return int(env("WEEKLY_BRIEF_FINAL_DATA_LIMIT", "6000"))
    return int(env("WEEKLY_BRIEF_SECTION_DATA_LIMIT", "14000"))


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

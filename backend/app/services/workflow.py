from __future__ import annotations

import re
from typing import Any

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

from ..clients.data_nodes import collect_research_data_nodes, data_node_complete_enough, local_data_sections_enabled
from ..core.config import (
    AGENT_WORKFLOW,
    DEFAULT_RESEARCH_INTENT,
    configured_api_key,
    configured_base_url,
    configured_fast_model,
    configured_model,
    env,
    request_user_prompt,
    safe_text,
    truncate_text,
)
from .agent_sections import (
    chat_completion,
    failed_section_markdown,
    preflight_model_gateway,
    repaired_section_markdown,
    run_agent_section,
    run_with_wall_clock_timeout,
    section_wall_timeout_seconds,
)
from .payloads import build_messages, extract_json_object, fallback_payload, normalize_payload
from .trace import build_agent_trace
from .workflow_reports import (
    build_local_data_version_a_report,
    build_local_version_a_report,
    build_workflow_payload_from_sections,
    ensure_section_actionable_output,
    infer_section_status,
    local_data_section_markdown,
    should_use_local_final_narrative,
    workflow_engine_name,
)

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
    elif (
        section_name == "Final Narrative"
        and data_node_complete_enough(data_bundle)
        and env("WEEKLY_BRIEF_FORCE_MODEL_FINAL", "0").lower() not in {"1", "true", "yes"}
    ):
        section_error = "local_data_final_narrative"
        section_markdown = build_local_data_version_a_report(user_prompt, sections, data_bundle)
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
        payload["runMetadata"]["workflowEngine"] = safe_text(
            next_state.get("workflow_engine") or workflow_engine_name(LANGGRAPH_AVAILABLE)
        )
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

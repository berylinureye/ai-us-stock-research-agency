from __future__ import annotations

import json
import queue
import threading
from typing import Any, Callable, Iterator, Optional

from ..core.config import configured_api_key, configured_base_url, configured_model, env, redact_url, request_user_prompt
from .payloads import error_report_payload, mock_payload, normalize_payload, save_report_history
from .workflow import call_openai, call_upstream, preflight_model_gateway, run_agent_workflow


EventEmitter = Callable[[dict[str, Any]], None]


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


class WeeklyBriefService:
    def generate(self, body: dict[str, Any], *, source: Optional[str] = None) -> dict[str, Any]:
        mode = source or current_mode()
        if mode == "mock":
            payload = mock_payload()
        elif mode == "proxy":
            payload = call_upstream(body)
        else:
            payload = call_openai(body)
        return self._persist(payload, body, source=mode)

    def event_stream(self, body: dict[str, Any]) -> Iterator[str]:
        def encode(event: dict[str, Any]) -> str:
            return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

        event_queue: queue.Queue[dict[str, Any] | object] = queue.Queue()
        done = object()

        def emit(event: dict[str, Any]) -> None:
            event_queue.put(event)

        def run() -> None:
            try:
                mode = current_mode()
                user_prompt = request_user_prompt(body)
                emit({"event": "run_start", "stage": "后端已接收请求", "prompt": user_prompt})
                if mode == "mock":
                    emit({"event": "run_done", "stage": "完成", **self._persist(mock_payload(), body, source="mock_stream")})
                    return

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
                emit({"event": "run_done", "stage": "完成", **self._persist(payload, body, source="openai_stream")})
            except Exception as exc:  # noqa: BLE001 - surface readable workflow errors
                error_payload = self._persist(error_report_payload(str(exc), body), body, source=f"{current_mode()}_stream_error")
                emit({"event": "run_error", "stage": "运行失败", "error": str(exc), **error_payload})
            finally:
                event_queue.put(done)

        threading.Thread(target=run, name="weekly-brief-sse", daemon=True).start()
        while True:
            event = event_queue.get()
            if event is done:
                break
            yield encode(event)
        yield "data: [DONE]\n\n"

    def persist_error(self, body: dict[str, Any], exc: Exception, *, source: Optional[str] = None) -> dict[str, Any]:
        mode = source or f"{current_mode()}_error"
        return self._persist(error_report_payload(str(exc), body), body, source=mode)

    @staticmethod
    def _persist(payload: dict[str, Any], body: dict[str, Any], *, source: str) -> dict[str, Any]:
        normalized = normalize_payload(payload)
        history_item = save_report_history(normalized, body, source=source)
        normalized.setdefault("runMetadata", {})
        if isinstance(normalized["runMetadata"], dict):
            normalized["runMetadata"]["historyId"] = history_item["id"]
            normalized["runMetadata"]["historyCreatedAt"] = history_item["createdAt"]
        return normalized

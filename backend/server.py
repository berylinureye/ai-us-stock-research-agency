#!/usr/bin/env python3
"""Compatibility launcher for the FastAPI weekly brief backend."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import uvicorn

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# Kept here for static compatibility checks; actual raising logic lives in
# backend.app.services.agent_sections.chat_completion.
MODEL_GATEWAY_AUTH_ERROR = "模型网关鉴权失败"
MODEL_GATEWAY_QUOTA_ERROR = "模型网关额度不足"

from backend.app.core.config import (
    DEFAULT_PORT,
    ROOT,
    configured_api_key,
    configured_base_url,
    configured_model,
    env,
    load_env_file,
)
from backend.app.main import create_app
from backend.app.repositories.pond import (
    POND_DIR,
    pond_payload,
    refresh_pond_prices,
    select_pond_candidate,
)
from backend.app.services.payloads import (
    REPORT_HISTORY_DIR,
    mock_payload,
    report_history_detail,
    report_history_payload,
    save_report_history,
)
from backend.app.services.weekly_brief import current_mode, health_payload
from backend.app.services.workflow import call_openai, call_upstream, run_agent_workflow


def main() -> None:
    load_env_file(ROOT / ".env")
    parser = argparse.ArgumentParser(description="Run the local weekly brief backend.")
    parser.add_argument("--host", default=env("WEEKLY_BRIEF_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(env("WEEKLY_BRIEF_PORT", str(DEFAULT_PORT)) or DEFAULT_PORT))
    args = parser.parse_args()

    payload = health_payload()
    print(f"Weekly brief backend listening on http://{args.host}:{args.port}")
    print(f"Mode: {payload['mode']} | Model: {payload['model']} | API key: {'set' if payload['hasApiKey'] else 'missing'}")
    uvicorn.run(create_app(), host=args.host, port=args.port, log_level="warning")


__all__ = [
    "POND_DIR",
    "REPORT_HISTORY_DIR",
    "call_openai",
    "call_upstream",
    "configured_api_key",
    "configured_base_url",
    "configured_model",
    "create_app",
    "current_mode",
    "env",
    "health_payload",
    "load_env_file",
    "main",
    "mock_payload",
    "pond_payload",
    "refresh_pond_prices",
    "report_history_detail",
    "report_history_payload",
    "run_agent_workflow",
    "save_report_history",
    "select_pond_candidate",
]


if __name__ == "__main__":
    main()

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
import os

from .routers import health, pond, reports, weekly_brief
from .services import payloads


def create_app() -> FastAPI:
    payloads.REPORT_HISTORY_DIR = Path(os.environ.get("REPORT_HISTORY_DIR") or payloads.ROOT / "data" / "report-history")
    app = FastAPI(title="Weekly Brief Backend")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(health.router)
    app.include_router(weekly_brief.router)
    app.include_router(pond.router)
    app.include_router(reports.router)
    return app


app = create_app()

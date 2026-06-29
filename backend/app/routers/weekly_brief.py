from __future__ import annotations

from fastapi import APIRouter, Header
from fastapi.responses import JSONResponse, StreamingResponse

from ..schemas.weekly import WeeklyBriefRequest
from ..services.weekly_brief import WeeklyBriefService, current_mode


router = APIRouter()
service = WeeklyBriefService()


@router.post("/api/weekly-brief")
def weekly_brief(payload: WeeklyBriefRequest, accept: str = Header(default="")):
    body = payload.as_body()
    if "text/event-stream" in accept and current_mode() in {"mock", "openai"}:
        return StreamingResponse(service.event_stream(body), media_type="text/event-stream")
    try:
        return JSONResponse(service.generate(body))
    except Exception as exc:  # noqa: BLE001 - preserve legacy JSON error contract
        service.persist_error(body, exc)
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=500)

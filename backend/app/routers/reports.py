from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from ..services.payloads import report_history_detail, report_history_payload


router = APIRouter()


@router.get("/api/reports")
def list_reports() -> Any:
    try:
        return report_history_payload()
    except Exception as exc:  # noqa: BLE001 - preserve legacy JSON error contract
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=500)


@router.get("/api/reports/{record_id}")
def get_report(record_id: str) -> Any:
    try:
        return report_history_detail(record_id)
    except FileNotFoundError as exc:
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=404)
    except Exception as exc:  # noqa: BLE001 - preserve legacy JSON error contract
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=500)

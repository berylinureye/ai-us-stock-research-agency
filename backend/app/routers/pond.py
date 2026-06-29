from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from ..repositories.pond import pond_payload, refresh_pond_prices, select_pond_candidate


router = APIRouter()


@router.get("/api/pond")
def get_pond() -> Any:
    try:
        return pond_payload()
    except Exception as exc:  # noqa: BLE001 - preserve legacy JSON error contract
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=500)


@router.post("/api/pond/select")
def select_pond(body: dict[str, Any]) -> Any:
    try:
        return select_pond_candidate(body)
    except Exception as exc:  # noqa: BLE001 - preserve legacy JSON error contract
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=500)


@router.post("/api/pond/refresh")
def refresh_pond() -> Any:
    try:
        return refresh_pond_prices()
    except Exception as exc:  # noqa: BLE001 - preserve legacy JSON error contract
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=500)

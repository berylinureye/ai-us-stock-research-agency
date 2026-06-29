from __future__ import annotations

from fastapi import APIRouter

from ..services.weekly_brief import health_payload


router = APIRouter()


@router.get("/api/health")
def health() -> dict:
    return health_payload()

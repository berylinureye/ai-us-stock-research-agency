from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, ConfigDict


class WeeklyBriefRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    prompt: Optional[str] = None
    user_prompt: Optional[str] = None
    intent: Optional[str] = None
    model: Optional[str] = None

    def as_body(self) -> dict[str, Any]:
        return dict(self.model_dump(exclude_none=True), **self.model_extra)

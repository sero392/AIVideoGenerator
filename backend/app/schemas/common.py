from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

ComponentState = Literal["ok", "unavailable", "disabled", "error"]


class HealthResponse(BaseModel):
    status: Literal["ok"]
    application: str
    version: str

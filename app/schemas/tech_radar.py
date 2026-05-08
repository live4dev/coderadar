from __future__ import annotations
from datetime import datetime
from pydantic import BaseModel


class TechRadarBlip(BaseModel):
    name: str
    quadrant: str       # "languages" | "frameworks" | "infrastructure" | "dependencies"
    ring: str           # "adopt" | "trial" | "assess" | "hold"
    auto_ring: str      # computed ring before any manual override
    is_overridden: bool
    repo_count: int
    quality_signal: float | None  # avg ScanScore.overall for repos using this tech
    license_risk: str | None      # relevant for dependencies
    notes: str | None

    model_config = {"from_attributes": True}


class TechRadarResponse(BaseModel):
    blips: list[TechRadarBlip]
    total_repos: int
    generated_at: datetime
    project_id: int | None


class TechRadarOverrideCreate(BaseModel):
    tech_name: str
    quadrant: str
    ring: str
    project_id: int | None = None
    notes: str | None = None


class TechRadarOverrideOut(BaseModel):
    id: int
    tech_name: str
    quadrant: str
    ring: str
    project_id: int | None
    notes: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

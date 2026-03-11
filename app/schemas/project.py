from __future__ import annotations
from datetime import datetime
from pydantic import BaseModel


class ProjectCreate(BaseModel):
    name: str
    description: str | None = None


class ProjectOut(BaseModel):
    id: int
    name: str
    description: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class ProjectSummaryOut(BaseModel):
    """Project with aggregate metrics from latest completed scan per repository."""
    id: int
    name: str
    description: str | None
    created_at: datetime
    repo_count: int
    repos_with_completed_scan: int
    total_loc: int | None
    total_files: int | None
    avg_score: float | None
    last_scan_at: datetime | None

    model_config = {"from_attributes": True}

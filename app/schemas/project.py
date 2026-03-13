from __future__ import annotations
from datetime import datetime
from pydantic import BaseModel, model_validator


class ProjectCreate(BaseModel):
    name: str
    description: str | None = None
    tags: list[str] = []


class ProjectOut(BaseModel):
    id: int
    name: str
    description: str | None
    created_at: datetime
    tags: list[str] = []

    model_config = {"from_attributes": True}

    @model_validator(mode="wrap")
    @classmethod
    def _tags_from_orm(cls, data, handler):
        if not isinstance(data, dict) and hasattr(data, "tags") and data.tags is not None:
            d = {f: getattr(data, f) for f in ("id", "name", "description", "created_at")}
            d["tags"] = [t.tag for t in data.tags]
            return handler(d)
        return handler(data)


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
    tags: list[str] = []

    model_config = {"from_attributes": True}


class TagsUpdate(BaseModel):
    """Replace entity tags with the given list."""
    tags: list[str] = []

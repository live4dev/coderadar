from __future__ import annotations
from datetime import datetime
from pydantic import BaseModel, model_validator


class DeveloperProfileOut(BaseModel):
    """One profile of a developer (canonical_username + email)."""
    id: int
    developer_id: int
    canonical_username: str
    display_name: str | None
    primary_email: str | None

    model_config = {"from_attributes": True}


class DeveloperOut(BaseModel):
    """Global developer with their profiles."""
    id: int
    profiles: list[DeveloperProfileOut]
    created_at: datetime | None = None
    tags: list[str] = []

    model_config = {"from_attributes": True}

    @model_validator(mode="wrap")
    @classmethod
    def _tags_from_orm(cls, data, handler):
        if not isinstance(data, dict) and hasattr(data, "tags") and data.tags is not None:
            d = {"id": data.id, "profiles": data.profiles, "created_at": data.created_at, "tags": [t.tag for t in data.tags]}
            return handler(d)
        return handler(data)


class DeveloperListOut(BaseModel):
    """Developer with aggregates across all their profiles (optionally filtered by project)."""
    id: int
    total_commits: int
    total_insertions: int
    total_deletions: int
    files_changed: int
    active_days: int
    first_commit_at: datetime | None
    last_commit_at: datetime | None
    project_id: int | None = None
    project_name: str | None = None
    profiles: list[DeveloperProfileOut] = []
    tags: list[str] = []

    model_config = {"from_attributes": True}


class DeveloperContributionsSummaryOut(BaseModel):
    """Aggregated contribution stats across all scans for one developer."""
    commit_count: int
    insertions: int
    deletions: int
    files_changed: int
    active_days: int
    first_commit_at: datetime | None
    last_commit_at: datetime | None
    project_total_commits: int | None = None
    share_pct: float | None = None

    model_config = {"from_attributes": True}


class DeveloperContributionOut(BaseModel):
    developer: DeveloperOut
    commit_count: int
    insertions: int
    deletions: int
    files_changed: int
    active_days: int
    first_commit_at: datetime | None
    last_commit_at: datetime | None

    model_config = {"from_attributes": True}


class DeveloperLanguageOut(BaseModel):
    language: str
    commit_count: int
    files_changed: int
    loc_added: int
    percentage: float

    model_config = {"from_attributes": True}


class DeveloperModuleOut(BaseModel):
    module_path: str
    module_name: str
    commit_count: int
    files_changed: int
    loc_added: int
    percentage: float

    model_config = {"from_attributes": True}


class ModuleOwnershipOut(BaseModel):
    module_path: str
    owners: list[dict]  # [{username, percentage}]

    model_config = {"from_attributes": True}


class IdentityOverrideCreate(BaseModel):
    project_id: int
    raw_name: str | None = None
    raw_email: str | None = None
    canonical_username: str
    note: str | None = None


class DeveloperProfileUpdate(BaseModel):
    display_name: str | None = None
    primary_email: str | None = None


class IdentityOverrideOut(BaseModel):
    id: int
    project_id: int | None
    raw_name: str | None
    raw_email: str | None
    canonical_username: str
    note: str | None
    created_at: datetime

    model_config = {"from_attributes": True}

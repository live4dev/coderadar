from __future__ import annotations
from datetime import datetime
from pydantic import BaseModel


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

    model_config = {"from_attributes": True}


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

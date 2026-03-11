from __future__ import annotations
from datetime import datetime
from pydantic import BaseModel


class RepositoryCreate(BaseModel):
    project_id: int
    name: str
    url: str
    provider_type: str  # "bitbucket" | "gitlab"
    default_branch: str | None = None
    credentials_username: str | None = None
    credentials_token: str | None = None


class RepositoryOut(BaseModel):
    id: int
    project_id: int
    name: str
    url: str
    provider_type: str
    default_branch: str | None
    last_commit_sha: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class LatestScanOut(BaseModel):
    """Summary of the latest completed scan for a repository."""
    scan_id: int
    total_loc: int | None
    total_files: int | None
    project_type: str | None
    primary_language: str | None
    started_at: datetime | None
    completed_at: datetime | None
    overall_score: float | None


class RepositoryWithLatestScanOut(BaseModel):
    """Repository with optional latest completed scan summary."""
    id: int
    project_id: int
    name: str
    url: str
    provider_type: str
    default_branch: str | None
    last_commit_sha: str | None
    created_at: datetime
    latest_scan: LatestScanOut | None = None


class ScanTrigger(BaseModel):
    branch: str | None = None  # defaults to repository.default_branch

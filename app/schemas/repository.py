from __future__ import annotations
from datetime import datetime
from pydantic import BaseModel, model_validator


class RepositoryGitTagOut(BaseModel):
    name: str
    sha: str | None
    message: str | None
    tagger_name: str | None
    tagger_email: str | None
    tagged_at: datetime | None

    model_config = {"from_attributes": True}


class RepositoryTagIn(BaseModel):
    name: str
    description: str | None = None


class RepositoryDailyActivityOut(BaseModel):
    date: str   # "YYYY-MM-DD"
    count: int


class RepositoryTagOut(BaseModel):
    name: str
    description: str | None
    date: datetime | None


class RepositoryTagsUpdate(BaseModel):
    tags: list[RepositoryTagIn] = []


class RepositoryCreate(BaseModel):
    project_id: int
    name: str
    url: str
    provider_type: str  # "bitbucket" | "gitlab" | "github"
    default_branch: str | None = None
    credentials_username: str | None = None
    credentials_token: str | None = None
    tags: list[RepositoryTagIn] = []


class RepositoryOut(BaseModel):
    """Serialises a ProjectRepository ORM object.

    ``id`` is the ProjectRepository.id (the project-scoped handle used by all
    sub-resource endpoints).  ``repository_id`` is the global Repository.id
    (the deduplicated row keyed on URL).
    """
    id: int
    repository_id: int
    project_id: int
    name: str
    url: str
    provider_type: str
    default_branch: str | None
    last_commit_sha: str | None
    created_at: datetime
    tags: list[RepositoryTagOut] = []

    model_config = {"from_attributes": True}

    @model_validator(mode="wrap")
    @classmethod
    def _from_project_repository(cls, data, handler):
        if not isinstance(data, dict) and hasattr(data, "repository"):
            repo = data.repository
            d = {
                "id": data.id,
                "repository_id": repo.id,
                "project_id": data.project_id,
                "name": data.name,
                "url": repo.url,
                "provider_type": repo.provider_type.value if hasattr(repo.provider_type, "value") else repo.provider_type,
                "default_branch": data.default_branch,
                "last_commit_sha": repo.last_commit_sha,
                "created_at": data.created_at,
                "tags": [
                    {"name": t.tag, "description": t.description, "date": t.created_at}
                    for t in (data.tags or [])
                ],
            }
            return handler(d)
        return handler(data)


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
    repository_id: int
    project_id: int
    name: str
    url: str
    provider_type: str
    default_branch: str | None
    last_commit_sha: str | None
    created_at: datetime
    latest_scan: LatestScanOut | None = None
    tags: list[RepositoryTagOut] = []


class RepositoryUpdate(BaseModel):
    project_id: int | None = None
    name: str
    url: str
    provider_type: str
    default_branch: str | None = None
    credentials_username: str | None = None
    credentials_token: str | None = None  # None = clear credential


class ScanTrigger(BaseModel):
    branch: str | None = None  # defaults to project_repository.default_branch

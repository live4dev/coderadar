from __future__ import annotations
from datetime import datetime
from pydantic import BaseModel


class RepositoryCreate(BaseModel):
    project_id: int
    name: str
    url: str
    provider_type: str  # "bitbucket" | "gitlab"
    default_branch: str = "main"
    credentials_username: str | None = None
    credentials_token: str | None = None


class RepositoryOut(BaseModel):
    id: int
    project_id: int
    name: str
    url: str
    provider_type: str
    default_branch: str
    last_commit_sha: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class ScanTrigger(BaseModel):
    branch: str | None = None  # defaults to repository.default_branch

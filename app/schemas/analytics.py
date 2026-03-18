"""Schemas for analytics (treemap tree)."""
from __future__ import annotations
from pydantic import BaseModel


class TreemapNode(BaseModel):
    """One node in the treemap tree (recursive)."""
    name: str
    value: int | float
    id: int | None = None
    type: str | None = None  # "project" | "repository" | "root"
    children: list[TreemapNode] | None = None


class RepoLanguage(BaseModel):
    name: str
    loc: int
    file_count: int
    percentage: float


class LanguageStat(BaseModel):
    total_loc: int
    total_files: int
    repo_count: int


class TechMapRepo(BaseModel):
    repo_id: int
    repo_name: str
    project_id: int
    project_name: str
    primary_language: str | None
    project_type: str | None
    languages: list[RepoLanguage]
    frameworks: list[str]
    package_managers: list[str]
    ci_provider: str | None
    infra_tools: list[str]
    linters: list[str]
    has_docker: bool
    has_kubernetes: bool
    has_terraform: bool


class TechCounts(BaseModel):
    languages: dict[str, LanguageStat]
    frameworks: dict[str, int]
    ci_providers: dict[str, int]
    package_managers: dict[str, int]
    infra_tools: dict[str, int]


class TechMapResponse(BaseModel):
    repos: list[TechMapRepo]
    tech_counts: TechCounts

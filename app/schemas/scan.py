from __future__ import annotations
from datetime import datetime
from pydantic import BaseModel


class ScanOut(BaseModel):
    id: int
    repository_id: int
    status: str
    branch: str
    commit_sha: str | None
    error_message: str | None
    total_files: int | None
    total_loc: int | None
    size_bytes: int | None
    project_type: str | None
    primary_language: str | None
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class ScanSummaryOut(BaseModel):
    id: int
    status: str
    branch: str
    commit_sha: str | None
    total_files: int | None
    total_loc: int | None
    size_bytes: int | None
    file_count_source: int | None
    file_count_test: int | None
    file_count_config: int | None
    avg_file_loc: float | None
    large_files_count: int | None
    project_type: str | None
    primary_language: str | None
    started_at: datetime | None
    completed_at: datetime | None

    model_config = {"from_attributes": True}


class ScanLanguageOut(BaseModel):
    language: str
    file_count: int
    loc: int
    percentage: float

    model_config = {"from_attributes": True}


class DependencyOut(BaseModel):
    name: str
    version: str | None
    dep_type: str
    manifest_file: str | None
    ecosystem: str | None

    model_config = {"from_attributes": True}


class ScanScoreOut(BaseModel):
    domain: str
    score: float
    details: str | None

    model_config = {"from_attributes": True}


class ScanRiskOut(BaseModel):
    risk_type: str
    severity: str
    title: str
    description: str | None
    entity_type: str | None
    entity_ref: str | None

    model_config = {"from_attributes": True}


class ScanMetricsDiff(BaseModel):
    total_files_delta: int | None
    total_loc_delta: int | None
    size_bytes_delta: int | None


class ScanLanguageDiff(BaseModel):
    language: str
    change: str  # added | removed | changed
    loc_delta: int | None
    percentage_delta: float | None


class ScanScoreDiff(BaseModel):
    domain: str
    score_a: float
    score_b: float
    delta: float


class ScanRiskDiff(BaseModel):
    risk_type: str
    title: str
    severity: str
    change: str  # new | resolved


class ScanDeveloperDiff(BaseModel):
    canonical_username: str
    change: str  # joined | left


class ScanCompareOut(BaseModel):
    scan_a_id: int
    scan_b_id: int
    metrics: ScanMetricsDiff
    languages: list[ScanLanguageDiff]
    scores: list[ScanScoreDiff]
    risks: list[ScanRiskDiff]
    developers: list[ScanDeveloperDiff]

from __future__ import annotations
from datetime import datetime
from pydantic import BaseModel, model_validator


class ScanOut(BaseModel):
    id: int
    repository_id: int  # maps to project_repository_id (the project-scoped handle)
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
    cancel_requested: bool = False

    model_config = {"from_attributes": True}

    @model_validator(mode="wrap")
    @classmethod
    def _map_project_repository_id(cls, data, handler):
        if not isinstance(data, dict) and hasattr(data, "project_repository_id"):
            d = {
                "id": data.id,
                "repository_id": data.project_repository_id,
                "status": data.status.value if hasattr(data.status, "value") else data.status,
                "branch": data.branch,
                "commit_sha": data.commit_sha,
                "error_message": data.error_message,
                "total_files": data.total_files,
                "total_loc": data.total_loc,
                "size_bytes": data.size_bytes,
                "project_type": data.project_type.value if data.project_type and hasattr(data.project_type, "value") else data.project_type,
                "primary_language": data.primary_language,
                "started_at": data.started_at,
                "completed_at": data.completed_at,
                "created_at": data.created_at,
                "cancel_requested": data.cancel_requested,
            }
            return handler(d)
        return handler(data)


class ScanQueueItemOut(BaseModel):
    id: int
    repository_id: int
    repository_name: str
    status: str
    branch: str
    created_at: datetime
    started_at: datetime | None
    cancel_requested: bool

    model_config = {"from_attributes": True}


class ScanSummaryOut(BaseModel):
    id: int
    status: str
    branch: str
    commit_sha: str | None
    error_message: str | None = None
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
    license_spdx: str | None = None
    license_raw: str | None = None
    license_risk: str = "unknown"
    is_direct: bool = True

    model_config = {"from_attributes": True}


class DependencyLicenseSummaryOut(BaseModel):
    total: int
    direct_count: int
    transitive_count: int
    license_counts: dict[str, int]  # SPDX id (or "unknown") → count
    unknown_count: int
    risky_count: int
    safe_count: int
    risk_score: int  # 0–100: percentage of risky deps


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


class PersonalDataCountOut(BaseModel):
    pdn_type: str
    count: int


class PersonalDataFindingOut(BaseModel):
    pdn_type: str
    matched_identifier: str
    file_path: str
    line_number: int
    source_url: str | None = None

    model_config = {"from_attributes": True}


class PersonalDataOut(BaseModel):
    counts: list[PersonalDataCountOut]
    findings: list[PersonalDataFindingOut]


class PersonalDataReportEntry(BaseModel):
    """One row in the personal data report: repo + its latest scan PDn summary."""
    project_id: int
    project_name: str
    repository_id: int
    repository_name: str
    scan_id: int
    scan_started_at: datetime | None
    scan_completed_at: datetime | None
    counts: list[PersonalDataCountOut]
    findings: list[PersonalDataFindingOut] | None = None
    repository_source_url: str | None = None


class PersonalDataReportOut(BaseModel):
    """Aggregated personal data report by projects/repositories (latest scan per repo)."""
    entries: list[PersonalDataReportEntry]


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


class LicenseRiskyDepOut(BaseModel):
    name: str
    version: str | None
    ecosystem: str | None
    license_spdx: str | None
    license_raw: str | None


class LicenseReportEntry(BaseModel):
    project_id: int
    project_name: str
    repository_id: int
    repository_name: str
    scan_id: int
    scan_started_at: datetime | None
    scan_completed_at: datetime | None
    total: int
    direct_count: int
    transitive_count: int
    safe_count: int
    risky_count: int
    unknown_count: int
    risk_score: int  # 0–100
    ecosystem_counts: dict[str, int]
    risky_deps: list[LicenseRiskyDepOut]


class LicenseReportOut(BaseModel):
    entries: list[LicenseReportEntry]

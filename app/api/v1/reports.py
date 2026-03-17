"""Report endpoints (e.g. aggregated personal data by projects/repos)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import (
    Project,
    Repository,
    Scan,
    ScanStatus,
    ScanPersonalDataFinding,
)
from app.schemas.scan import (
    PersonalDataReportOut,
    PersonalDataReportEntry,
    PersonalDataCountOut,
    PersonalDataFindingOut,
)
from app.services.source_links import build_source_url

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/personal-data", response_model=PersonalDataReportOut)
def get_personal_data_report(
    project_id: int | None = Query(None, description="Filter by project"),
    repository_id: int | None = Query(None, description="Filter by repository"),
    include_findings: bool = Query(False, description="Include full findings list per scan"),
    db: Session = Depends(get_db),
):
    """
    Aggregated PDn report: for each repository (optionally filtered), the latest
    completed scan's personal data counts and optionally findings.
    """
    # Base repos query
    q = (
        db.query(Repository)
        .join(Project, Repository.project_id == Project.id)
        .order_by(Project.id, Repository.id)
    )
    if project_id is not None:
        q = q.filter(Repository.project_id == project_id)
    if repository_id is not None:
        q = q.filter(Repository.id == repository_id)
    repos = q.all()
    if not repos:
        return PersonalDataReportOut(entries=[])

    repo_ids = [r.id for r in repos]
    # Latest completed scan per repo: order by started_at desc, take first per repo
    latest_scans = (
        db.query(Scan)
        .filter(
            Scan.repository_id.in_(repo_ids),
            Scan.status == ScanStatus.completed,
        )
        .order_by(Scan.started_at.desc(), Scan.id.desc())
        .all()
    )
    scan_by_repo: dict[int, Scan] = {}
    for s in latest_scans:
        if s.repository_id not in scan_by_repo:
            scan_by_repo[s.repository_id] = s

    # Load project names
    project_ids = list({r.project_id for r in repos})
    projects = db.query(Project).filter(Project.id.in_(project_ids)).all()
    project_name_by_id = {p.id: p.name for p in projects}

    entries: list[PersonalDataReportEntry] = []
    for r in repos:
        scan = scan_by_repo.get(r.id)
        if not scan:
            continue
        # Counts by pdn_type for this scan
        count_rows = (
            db.query(
                ScanPersonalDataFinding.pdn_type,
                func.count(ScanPersonalDataFinding.id).label("count"),
            )
            .filter(ScanPersonalDataFinding.scan_id == scan.id)
            .group_by(ScanPersonalDataFinding.pdn_type)
            .all()
        )
        counts = [PersonalDataCountOut(pdn_type=t, count=c) for t, c in count_rows]
        ref = scan.commit_sha or scan.branch or r.default_branch or "HEAD"
        provider = r.provider_type.value
        repo_url = r.url
        repository_source_url = build_source_url(repo_url, provider, ref, None, None) if repo_url and provider else None

        findings = None
        if include_findings:
            finding_rows = (
                db.query(ScanPersonalDataFinding)
                .filter(ScanPersonalDataFinding.scan_id == scan.id)
                .order_by(
                    ScanPersonalDataFinding.pdn_type,
                    ScanPersonalDataFinding.file_path,
                    ScanPersonalDataFinding.line_number,
                )
                .all()
            )
            findings = [
                PersonalDataFindingOut(
                    pdn_type=row.pdn_type,
                    matched_identifier=row.matched_identifier,
                    file_path=row.file_path,
                    line_number=row.line_number,
                    source_url=build_source_url(repo_url, provider, ref, row.file_path, row.line_number) if repo_url and provider else None,
                )
                for row in finding_rows
            ]
        entries.append(
            PersonalDataReportEntry(
                project_id=r.project_id,
                project_name=project_name_by_id.get(r.project_id, ""),
                repository_id=r.id,
                repository_name=r.name,
                scan_id=scan.id,
                scan_started_at=scan.started_at,
                scan_completed_at=scan.completed_at,
                counts=counts,
                findings=findings,
                repository_source_url=repository_source_url,
            )
        )
    return PersonalDataReportOut(entries=entries)

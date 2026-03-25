"""Report endpoints (e.g. aggregated personal data by projects/repos)."""
from __future__ import annotations

from collections import defaultdict

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import (
    Dependency,
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
    LicenseReportOut,
    LicenseReportEntry,
    LicenseRiskyDepOut,
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


@router.get("/license-dependencies", response_model=LicenseReportOut)
def get_license_dependencies_report(
    project_id: int | None = Query(None, description="Filter by project"),
    repository_id: int | None = Query(None, description="Filter by repository"),
    db: Session = Depends(get_db),
):
    """
    Aggregated license/dependency report: for each repository (latest completed scan),
    return dependency counts by license risk level and a list of risky packages.
    """
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
        return LicenseReportOut(entries=[])

    repo_ids = [r.id for r in repos]
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

    project_ids = list({r.project_id for r in repos})
    projects = db.query(Project).filter(Project.id.in_(project_ids)).all()
    project_name_by_id = {p.id: p.name for p in projects}

    entries: list[LicenseReportEntry] = []
    for r in repos:
        scan = scan_by_repo.get(r.id)
        if not scan:
            continue

        deps = db.query(Dependency).filter(Dependency.scan_id == scan.id).all()

        total = len(deps)
        direct_count = sum(1 for d in deps if d.is_direct)
        transitive_count = total - direct_count
        safe_count = sum(1 for d in deps if d.license_risk == "safe")
        risky_count = sum(1 for d in deps if d.license_risk == "risky")
        unknown_count = sum(1 for d in deps if d.license_risk not in ("safe", "risky"))
        risk_score = round(risky_count * 100 / total) if total > 0 else 0

        ecosystem_counts: dict[str, int] = defaultdict(int)
        for d in deps:
            if d.ecosystem:
                ecosystem_counts[d.ecosystem] += 1

        risky_deps = [
            LicenseRiskyDepOut(
                name=d.name,
                version=d.version,
                ecosystem=d.ecosystem,
                license_spdx=d.license_spdx,
                license_raw=d.license_raw,
            )
            for d in deps
            if d.license_risk == "risky"
        ]

        entries.append(
            LicenseReportEntry(
                project_id=r.project_id,
                project_name=project_name_by_id.get(r.project_id, ""),
                repository_id=r.id,
                repository_name=r.name,
                scan_id=scan.id,
                scan_started_at=scan.started_at,
                scan_completed_at=scan.completed_at,
                total=total,
                direct_count=direct_count,
                transitive_count=transitive_count,
                safe_count=safe_count,
                risky_count=risky_count,
                unknown_count=unknown_count,
                risk_score=risk_score,
                ecosystem_counts=dict(ecosystem_counts),
                risky_deps=risky_deps,
            )
        )
    return LicenseReportOut(entries=entries)

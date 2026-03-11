from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import distinct
from sqlalchemy.orm import Session, joinedload

from app.db.session import get_db
from app.models import (
    Project, Developer, DeveloperProfile, DeveloperContribution,
    Repository, Scan, ScanScore, ScanStatus,
)
from app.models.scan_score import ScoreDomain
from app.schemas.project import ProjectCreate, ProjectOut, ProjectSummaryOut
from app.schemas.developer import DeveloperOut, DeveloperProfileOut
from app.schemas.repository import (
    RepositoryOut,
    RepositoryWithLatestScanOut,
    LatestScanOut,
)

router = APIRouter(prefix="/projects", tags=["projects"])


@router.post("", response_model=ProjectOut, status_code=201)
def create_project(body: ProjectCreate, db: Session = Depends(get_db)):
    project = Project(name=body.name, description=body.description)
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


@router.get("", response_model=list[ProjectOut])
def list_projects(db: Session = Depends(get_db)):
    return db.query(Project).order_by(Project.id).all()


@router.get("/summary", response_model=list[ProjectSummaryOut])
def list_projects_summary(db: Session = Depends(get_db)):
    """List projects with aggregate metrics from latest completed scan per repository."""
    projects = db.query(Project).order_by(Project.id).all()
    if not projects:
        return []

    # All repos with project_id
    repos = (
        db.query(Repository.id, Repository.project_id)
        .filter(Repository.project_id.in_([p.id for p in projects]))
        .all()
    )
    repo_ids = [r.id for r in repos]
    project_repo_count = {}
    for r in repos:
        project_repo_count[r.project_id] = project_repo_count.get(r.project_id, 0) + 1

    if not repo_ids:
        return [
            ProjectSummaryOut(
                id=p.id,
                name=p.name,
                description=p.description,
                created_at=p.created_at,
                repo_count=project_repo_count.get(p.id, 0),
                repos_with_completed_scan=0,
                total_loc=None,
                total_files=None,
                avg_score=None,
                last_scan_at=None,
            )
            for p in projects
        ]

    # Latest completed scan per repo (first by started_at desc per repo)
    latest_scans = (
        db.query(Scan)
        .filter(
            Scan.repository_id.in_(repo_ids),
            Scan.status == ScanStatus.completed,
        )
        .order_by(Scan.started_at.desc(), Scan.id.desc())
        .all()
    )
    scan_by_repo = {}
    for s in latest_scans:
        if s.repository_id not in scan_by_repo:
            scan_by_repo[s.repository_id] = s

    # repo_id -> project_id
    repo_to_project = {r.id: r.project_id for r in repos}

    # Aggregate per project: scan stats + scan_ids for scores
    proj_loc: dict[int, int] = {}
    proj_files: dict[int, int] = {}
    proj_last_at: dict[int, datetime | None] = {}
    proj_scan_ids: dict[int, list[int]] = {}
    for repo_id, scan in scan_by_repo.items():
        pid = repo_to_project[repo_id]
        proj_loc[pid] = proj_loc.get(pid, 0) + (scan.total_loc or 0)
        proj_files[pid] = proj_files.get(pid, 0) + (scan.total_files or 0)
        if scan.completed_at:
            current = proj_last_at.get(pid)
            if current is None or scan.completed_at > current:
                proj_last_at[pid] = scan.completed_at
        proj_scan_ids.setdefault(pid, []).append(scan.id)

    scan_ids_flat = [sid for ids in proj_scan_ids.values() for sid in ids]
    overall_scores = {}
    if scan_ids_flat:
        scores = (
            db.query(ScanScore.scan_id, ScanScore.score)
            .filter(
                ScanScore.scan_id.in_(scan_ids_flat),
                ScanScore.domain == ScoreDomain.overall,
            )
            .all()
        )
        overall_scores = {row.scan_id: row.score for row in scores}

    # Average score per project
    proj_avg_score: dict[int, float] = {}
    for pid, sids in proj_scan_ids.items():
        vals = [overall_scores[sid] for sid in sids if overall_scores.get(sid) is not None]
        if vals:
            proj_avg_score[pid] = sum(vals) / len(vals)

        return [
        ProjectSummaryOut(
            id=p.id,
            name=p.name,
            description=p.description,
            created_at=p.created_at,
            repo_count=project_repo_count.get(p.id, 0),
            repos_with_completed_scan=len(proj_scan_ids.get(p.id, [])),
            total_loc=proj_loc.get(p.id) if p.id in proj_scan_ids else None,
            total_files=proj_files.get(p.id) if p.id in proj_scan_ids else None,
            avg_score=proj_avg_score.get(p.id),
            last_scan_at=proj_last_at.get(p.id),
        )
        for p in projects
    ]


@router.get("/{project_id}", response_model=ProjectOut)
def get_project(project_id: int, db: Session = Depends(get_db)):
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    return project


@router.get("/{project_id}/repositories", response_model=list[RepositoryOut])
def list_project_repositories(project_id: int, db: Session = Depends(get_db)):
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    return db.query(Repository).filter_by(project_id=project_id).order_by(Repository.id).all()


@router.get(
    "/{project_id}/repositories/with-latest-scan",
    response_model=list[RepositoryWithLatestScanOut],
)
def list_project_repositories_with_latest_scan(
    project_id: int,
    db: Session = Depends(get_db),
):
    """List project repositories with summary of their latest completed scan."""
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    repos = (
        db.query(Repository)
        .filter_by(project_id=project_id)
        .order_by(Repository.id)
        .all()
    )
    if not repos:
        return []

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
    # One scan per repo (first occurrence is latest for that repo)
    seen_repo_ids = set()
    scan_by_repo = {}
    for s in latest_scans:
        if s.repository_id not in seen_repo_ids:
            seen_repo_ids.add(s.repository_id)
            scan_by_repo[s.repository_id] = s

    scan_ids = [s.id for s in scan_by_repo.values()]
    overall_scores = {}
    if scan_ids:
        scores = (
            db.query(ScanScore.scan_id, ScanScore.score)
            .filter(
                ScanScore.scan_id.in_(scan_ids),
                ScanScore.domain == ScoreDomain.overall,
            )
            .all()
        )
        overall_scores = {row.scan_id: row.score for row in scores}

    result = []
    for r in repos:
        latest_scan = None
        if r.id in scan_by_repo:
            s = scan_by_repo[r.id]
            latest_scan = LatestScanOut(
                scan_id=s.id,
                total_loc=s.total_loc,
                total_files=s.total_files,
                project_type=s.project_type.value if s.project_type else None,
                primary_language=s.primary_language,
                started_at=s.started_at,
                completed_at=s.completed_at,
                overall_score=overall_scores.get(s.id),
            )
        result.append(
            RepositoryWithLatestScanOut(
                id=r.id,
                project_id=r.project_id,
                name=r.name,
                url=r.url,
                provider_type=r.provider_type.value,
                default_branch=r.default_branch,
                last_commit_sha=r.last_commit_sha,
                created_at=r.created_at,
                latest_scan=latest_scan,
            )
        )
    return result


@router.get("/{project_id}/developers", response_model=list[DeveloperOut])
def list_project_developers(project_id: int, db: Session = Depends(get_db)):
    """List developers that have at least one contribution in this project (via scans)."""
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    dev_ids = (
        db.query(distinct(DeveloperProfile.developer_id))
        .join(DeveloperContribution, DeveloperContribution.profile_id == DeveloperProfile.id)
        .join(Scan, DeveloperContribution.scan_id == Scan.id)
        .join(Repository, Scan.repository_id == Repository.id)
        .filter(Repository.project_id == project_id)
        .all()
    )
    dev_ids = [r[0] for r in dev_ids]
    if not dev_ids:
        return []
    developers = (
        db.query(Developer)
        .options(joinedload(Developer.profiles))
        .filter(Developer.id.in_(dev_ids))
        .all()
    )
    return [
        DeveloperOut(
            id=d.id,
            profiles=[
                DeveloperProfileOut(
                    id=p.id,
                    developer_id=p.developer_id,
                    canonical_username=p.canonical_username,
                    display_name=p.display_name,
                    primary_email=p.primary_email,
                )
                for p in d.profiles
            ],
            created_at=d.created_at,
        )
        for d in developers
    ]

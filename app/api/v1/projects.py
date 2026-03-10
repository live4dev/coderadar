from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import Project, Developer, Repository, Scan, ScanScore, ScanStatus
from app.models.scan_score import ScoreDomain
from app.schemas.project import ProjectCreate, ProjectOut
from app.schemas.developer import DeveloperOut
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
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    return db.query(Developer).filter_by(project_id=project_id).all()

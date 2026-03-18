from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import distinct
from sqlalchemy.orm import Session, joinedload

from app.db.session import get_db
from app.models import (
    Project, ProjectTag, Developer, DeveloperProfile, DeveloperContribution,
    Repository, Scan, ScanScore, ScanStatus,
)
from app.models.scan_score import ScoreDomain
from app.schemas.project import ProjectCreate, ProjectOut, ProjectSummaryOut, ProjectUpdate, TagsUpdate
from app.schemas.developer import DeveloperOut, DeveloperProfileOut
from app.schemas.repository import (
    RepositoryOut,
    RepositoryWithLatestScanOut,
    RepositoryTagOut,
    LatestScanOut,
)
from app.schemas.scan import ScanOut
from app.services.scanning.queue import enqueue

router = APIRouter(prefix="/projects", tags=["projects"])


@router.post("", response_model=ProjectOut, status_code=201)
def create_project(body: ProjectCreate, db: Session = Depends(get_db)):
    project = Project(name=body.name, description=body.description)
    db.add(project)
    db.commit()
    db.refresh(project)
    _set_project_tags(db, project.id, body.tags)
    db.commit()
    project = db.query(Project).options(joinedload(Project.tags)).filter(Project.id == project.id).first()
    return project


@router.get("", response_model=list[ProjectOut])
def list_projects(db: Session = Depends(get_db)):
    return db.query(Project).options(joinedload(Project.tags)).order_by(Project.id).all()


PROJECT_SORT_FIELDS = {"name", "id", "repo_count", "scanned", "loc", "files", "avg_score", "last_scan_at"}


@router.get("/summary", response_model=list[ProjectSummaryOut])
def list_projects_summary(
    sort_by: str = Query("name", description="Sort by: name, id, repo_count, scanned, loc, files, avg_score, last_scan_at"),
    order: str = Query("asc", description="Sort order: asc or desc"),
    q: str | None = Query(None, description="Search by name or description"),
    has_scans: bool = Query(False, description="Only projects with at least one completed scan"),
    db: Session = Depends(get_db),
):
    """List projects with aggregate metrics from latest completed scan per repository."""
    projects = db.query(Project).options(joinedload(Project.tags)).order_by(Project.id).all()
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
        result = [
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
                tags=[t.tag for t in p.tags],
            )
            for p in projects
        ]
        return _filter_and_sort_projects(result, q, has_scans, sort_by, order)

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

    result = [
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
            tags=[t.tag for t in p.tags],
        )
        for p in projects
    ]
    return _filter_and_sort_projects(result, q, has_scans, sort_by, order)


def _filter_and_sort_projects(
    items: list[ProjectSummaryOut],
    q: str | None,
    has_scans: bool,
    sort_by: str,
    order: str,
) -> list[ProjectSummaryOut]:
    if q and q.strip():
        term = q.strip().lower()
        items = [p for p in items if (p.name or "").lower().find(term) >= 0 or (p.description or "").lower().find(term) >= 0]
    if has_scans:
        items = [p for p in items if p.repos_with_completed_scan > 0]
    if sort_by not in PROJECT_SORT_FIELDS:
        sort_by = "name"
    reverse = order.lower() == "desc"

    def _nullable_key(p: ProjectSummaryOut, get_val, none_last: bool = True):
        """Sort key for nullable fields: non-null first, nulls last (when none_last=True)."""
        val = get_val(p)
        if val is None:
            return (1, 0) if none_last else (0, 0)
        return (0, -val if reverse else val)

    def sort_key(p: ProjectSummaryOut):
        if sort_by == "name":
            return (0, (p.name or "").lower())
        if sort_by == "id":
            return (0, p.id)
        if sort_by == "repo_count":
            return (0, p.repo_count)
        if sort_by == "scanned":
            return (0, p.repos_with_completed_scan)
        if sort_by == "loc":
            return _nullable_key(p, lambda x: x.total_loc)
        if sort_by == "files":
            return _nullable_key(p, lambda x: x.total_files)
        if sort_by == "avg_score":
            return _nullable_key(p, lambda x: x.avg_score)
        if sort_by == "last_scan_at":
            ts = p.last_scan_at
            if ts is None:
                return (1, 0)
            return (0, -ts.timestamp() if reverse else ts.timestamp())
        return (0, (p.name or "").lower())

    items = sorted(items, key=sort_key, reverse=reverse)
    return items


def _normalize_tags(tags: list[str]) -> list[str]:
    """Strip and dedupe, max 128 chars per tag."""
    seen: set[str] = set()
    out = []
    for t in tags:
        if not isinstance(t, str):
            continue
        s = t.strip()[:128]
        if s and s not in seen:
            seen.add(s)
            out.append(s)
    return out


def _set_project_tags(db: Session, project_id: int, tags: list[str]) -> None:
    db.query(ProjectTag).filter(ProjectTag.project_id == project_id).delete()
    for tag in _normalize_tags(tags):
        db.add(ProjectTag(project_id=project_id, tag=tag))


@router.put("/{project_id}", response_model=ProjectOut)
def update_project(project_id: int, body: ProjectUpdate, db: Session = Depends(get_db)):
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    project.name = body.name
    project.description = body.description
    db.commit()
    project = db.query(Project).options(joinedload(Project.tags)).filter(Project.id == project_id).first()
    return project


@router.delete("/{project_id}", status_code=204)
def delete_project(project_id: int, db: Session = Depends(get_db)):
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    db.delete(project)
    db.commit()


@router.get("/{project_id}", response_model=ProjectOut)
def get_project(project_id: int, db: Session = Depends(get_db)):
    project = db.query(Project).options(joinedload(Project.tags)).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(404, "Project not found")
    return project


@router.put("/{project_id}/tags", response_model=ProjectOut)
def set_project_tags(project_id: int, body: TagsUpdate, db: Session = Depends(get_db)):
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    _set_project_tags(db, project_id, body.tags)
    db.commit()
    db.refresh(project)
    project = db.query(Project).options(joinedload(Project.tags)).filter(Project.id == project_id).first()
    return project


@router.get("/{project_id}/repositories", response_model=list[RepositoryOut])
def list_project_repositories(project_id: int, db: Session = Depends(get_db)):
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    return db.query(Repository).options(joinedload(Repository.tags)).filter_by(project_id=project_id).order_by(Repository.id).all()


@router.post("/{project_id}/scan-all", response_model=list[ScanOut], status_code=202)
def trigger_project_scan_all(project_id: int, db: Session = Depends(get_db)):
    """Create a pending scan for every repository in the project."""
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    repos = db.query(Repository).filter_by(project_id=project_id).all()
    if not repos:
        return []
    created = []
    for repo in repos:
        scan = Scan(repository_id=repo.id, branch=repo.default_branch or "", status=ScanStatus.pending)
        db.add(scan)
        created.append(scan)
    db.commit()
    for scan in created:
        db.refresh(scan)
        enqueue(scan.id)
    return created


REPO_SORT_FIELDS = {"name", "id", "loc", "files", "project_type", "last_updated", "primary_language", "score"}


@router.get(
    "/{project_id}/repositories/with-latest-scan",
    response_model=list[RepositoryWithLatestScanOut],
)
def list_project_repositories_with_latest_scan(
    project_id: int,
    sort_by: str = Query("name", description="Sort by: name, id, loc, files, project_type, last_updated, primary_language, score"),
    order: str = Query("asc", description="Sort order: asc or desc"),
    q: str | None = Query(None, description="Search by name or URL"),
    has_scans: bool = Query(False, description="Only repositories with at least one completed scan"),
    db: Session = Depends(get_db),
):
    """List project repositories with summary of their latest completed scan."""
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    repos = (
        db.query(Repository)
        .options(joinedload(Repository.tags))
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
                tags=[RepositoryTagOut(name=t.tag, description=t.description, date=t.created_at) for t in r.tags],
            )
        )
    return _filter_and_sort_repos(result, q, has_scans, sort_by, order)


def _filter_and_sort_repos(
    items: list[RepositoryWithLatestScanOut],
    q: str | None,
    has_scans: bool,
    sort_by: str,
    order: str,
) -> list[RepositoryWithLatestScanOut]:
    if q and q.strip():
        term = q.strip().lower()
        items = [x for x in items if (x.name or "").lower().find(term) >= 0 or (x.url or "").lower().find(term) >= 0]
    if has_scans:
        items = [x for x in items if x.latest_scan is not None]
    if sort_by not in REPO_SORT_FIELDS:
        sort_by = "name"
    reverse = order.lower() == "desc"

    def _last_updated(r: RepositoryWithLatestScanOut):
        if r.latest_scan is None:
            return None
        ls = r.latest_scan
        return ls.completed_at or ls.started_at

    def sort_key(r: RepositoryWithLatestScanOut):
        if sort_by == "name":
            return (0, (r.name or "").lower())
        if sort_by == "id":
            return (0, r.id)
        if sort_by == "loc":
            val = r.latest_scan.total_loc if r.latest_scan else None
            if val is None:
                return (0, 0) if reverse else (1, 0)
            return (0, -val if reverse else val)
        if sort_by == "files":
            val = r.latest_scan.total_files if r.latest_scan else None
            if val is None:
                return (0, 0) if reverse else (1, 0)
            return (0, -val if reverse else val)
        if sort_by == "project_type":
            val = (r.latest_scan.project_type or "").lower() if r.latest_scan else None
            if val is None:
                return (1, "")
            return (0, val)
        if sort_by == "last_updated":
            ts = _last_updated(r)
            if ts is None:
                return (1, 0)
            return (0, -ts.timestamp() if reverse else ts.timestamp())
        if sort_by == "primary_language":
            val = (r.latest_scan.primary_language or "").lower() if r.latest_scan else None
            if val is None:
                return (1, "")
            return (0, val)
        if sort_by == "score":
            val = r.latest_scan.overall_score if r.latest_scan else None
            if val is None:
                return (0, 0) if reverse else (1, 0)
            return (0, -val if reverse else val)
        return (0, (r.name or "").lower())

    items = sorted(items, key=sort_key, reverse=reverse)
    return items


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
        .options(joinedload(Developer.profiles), joinedload(Developer.tags))
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
            tags=[t.tag for t in d.tags],
        )
        for d in developers
    ]

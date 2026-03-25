from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from app.db.session import get_db
from app.models import Repository, RepositoryTag, RepositoryDailyActivity, Scan, ScanStatus, Project, ProviderType, RepositoryGitTag
from app.schemas.repository import RepositoryCreate, RepositoryOut, RepositoryUpdate, RepositoryTagsUpdate, RepositoryTagIn, ScanTrigger, RepositoryGitTagOut, RepositoryDailyActivityOut
from app.schemas.scan import ScanOut
from app.services.scanning.queue import enqueue

router = APIRouter(prefix="/repositories", tags=["repositories"])


def _normalize_tags(tags: list[RepositoryTagIn]) -> list[RepositoryTagIn]:
    seen: set[str] = set()
    out = []
    for t in tags:
        name = t.name.strip()[:128]
        if name and name not in seen:
            seen.add(name)
            out.append(RepositoryTagIn(name=name, description=t.description))
    return out


def _set_repository_tags(db: Session, repository_id: int, tags: list[RepositoryTagIn]) -> None:
    db.query(RepositoryTag).filter(RepositoryTag.repository_id == repository_id).delete()
    for t in _normalize_tags(tags):
        db.add(RepositoryTag(repository_id=repository_id, tag=t.name, description=t.description))


@router.post("", response_model=RepositoryOut, status_code=201)
def create_repository(body: RepositoryCreate, db: Session = Depends(get_db)):
    project = db.get(Project, body.project_id)
    if not project:
        raise HTTPException(404, "Project not found")

    try:
        provider = ProviderType(body.provider_type)
    except ValueError:
        raise HTTPException(400, f"Unknown provider_type: {body.provider_type!r}. Use 'bitbucket', 'gitlab', or 'github'.")

    repo = Repository(
        project_id=body.project_id,
        name=body.name,
        url=body.url,
        provider_type=provider,
        default_branch=body.default_branch,
        credentials_username=body.credentials_username,
        credentials_token=body.credentials_token,
    )
    db.add(repo)
    db.commit()
    db.refresh(repo)
    _set_repository_tags(db, repo.id, body.tags)
    db.commit()
    db.refresh(repo)
    repo = db.query(Repository).options(joinedload(Repository.tags)).filter(Repository.id == repo.id).first()
    return repo


@router.get("/{repo_id}", response_model=RepositoryOut)
def get_repository(repo_id: int, db: Session = Depends(get_db)):
    repo = db.query(Repository).options(joinedload(Repository.tags)).filter(Repository.id == repo_id).first()
    if not repo:
        raise HTTPException(404, "Repository not found")
    return repo


@router.post("/scan-all", response_model=list[ScanOut], status_code=202)
def trigger_scan_all(db: Session = Depends(get_db)):
    """Create a pending scan for every repository. Worker will process them in order."""
    repos = db.query(Repository).all()
    if not repos:
        return []
    created = []
    for repo in repos:
        branch = repo.default_branch or ""
        scan = Scan(
            repository_id=repo.id,
            branch=branch,
            status=ScanStatus.pending,
        )
        db.add(scan)
        created.append(scan)
    db.commit()
    for scan in created:
        db.refresh(scan)
        enqueue(scan.id)
    return created


@router.put("/{repo_id}/tags", response_model=RepositoryOut)
def set_repository_tags(repo_id: int, body: RepositoryTagsUpdate, db: Session = Depends(get_db)):
    repo = db.get(Repository, repo_id)
    if not repo:
        raise HTTPException(404, "Repository not found")
    _set_repository_tags(db, repo_id, body.tags)
    db.commit()
    db.refresh(repo)
    repo = db.query(Repository).options(joinedload(Repository.tags)).filter(Repository.id == repo_id).first()
    return repo


@router.put("/{repo_id}", response_model=RepositoryOut)
def update_repository(repo_id: int, body: RepositoryUpdate, db: Session = Depends(get_db)):
    repo = db.get(Repository, repo_id)
    if not repo:
        raise HTTPException(404, "Repository not found")
    try:
        provider = ProviderType(body.provider_type)
    except ValueError:
        raise HTTPException(400, f"Unknown provider_type: {body.provider_type!r}. Use 'bitbucket', 'gitlab', or 'github'.")
    if body.project_id is not None and body.project_id != repo.project_id:
        if not db.get(Project, body.project_id):
            raise HTTPException(404, "Project not found")
        repo.project_id = body.project_id
    repo.name = body.name
    repo.url = body.url
    repo.provider_type = provider
    repo.default_branch = body.default_branch
    repo.credentials_username = body.credentials_username
    repo.credentials_token = body.credentials_token
    db.commit()
    repo = db.query(Repository).options(joinedload(Repository.tags)).filter(Repository.id == repo_id).first()
    return repo


@router.delete("/{repo_id}", status_code=204)
def delete_repository(repo_id: int, db: Session = Depends(get_db)):
    repo = db.get(Repository, repo_id)
    if not repo:
        raise HTTPException(404, "Repository not found")
    db.delete(repo)
    db.commit()


@router.post("/{repo_id}/scan", response_model=ScanOut, status_code=202)
def trigger_scan(
    repo_id: int,
    body: ScanTrigger,
    db: Session = Depends(get_db),
):
    repo = db.get(Repository, repo_id)
    if not repo:
        raise HTTPException(404, "Repository not found")

    branch = body.branch or repo.default_branch
    # Store "" when branch is None so we use remote default; orchestrator fills scan.branch after clone
    scan = Scan(
        repository_id=repo.id,
        branch=branch or "",
        status=ScanStatus.pending,
    )
    db.add(scan)
    db.commit()
    db.refresh(scan)

    enqueue(scan.id)
    return scan


@router.get("/{repo_id}/scans", response_model=list[ScanOut])
def list_scans(repo_id: int, db: Session = Depends(get_db)):
    repo = db.get(Repository, repo_id)
    if not repo:
        raise HTTPException(404, "Repository not found")
    return (
        db.query(Scan)
        .filter_by(repository_id=repo_id)
        .order_by(Scan.created_at.desc())
        .all()
    )


@router.get("/{repo_id}/git-tags", response_model=list[RepositoryGitTagOut])
def list_git_tags(repo_id: int, db: Session = Depends(get_db)):
    repo = db.get(Repository, repo_id)
    if not repo:
        raise HTTPException(404, "Repository not found")
    return (
        db.query(RepositoryGitTag)
        .filter_by(repository_id=repo_id)
        .order_by(RepositoryGitTag.tagged_at.desc().nullslast())
        .all()
    )


@router.get("/{repo_id}/modules")
def list_modules(repo_id: int, db: Session = Depends(get_db)):
    from app.models import Module
    repo = db.get(Repository, repo_id)
    if not repo:
        raise HTTPException(404, "Repository not found")
    modules = db.query(Module).filter_by(repository_id=repo_id).all()
    return [{"id": m.id, "path": m.path, "name": m.name} for m in modules]


@router.get("/{repo_id}/activity", response_model=list[RepositoryDailyActivityOut])
def get_repository_activity(repo_id: int, db: Session = Depends(get_db)):
    """Daily commit activity for a repository across all time."""
    repo = db.get(Repository, repo_id)
    if not repo:
        raise HTTPException(404, "Repository not found")
    rows = (
        db.query(RepositoryDailyActivity)
        .filter_by(repository_id=repo_id)
        .order_by(RepositoryDailyActivity.commit_date)
        .all()
    )
    return [RepositoryDailyActivityOut(date=str(r.commit_date), count=r.commit_count) for r in rows]

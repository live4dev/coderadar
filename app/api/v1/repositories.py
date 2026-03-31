from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from app.db.session import get_db
from app.models import Repository, ProjectRepository, RepositoryTag, RepositoryDailyActivity, Scan, ScanStatus, Project, ProviderType, RepositoryGitTag
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


def _set_repository_tags(db: Session, project_repository_id: int, tags: list[RepositoryTagIn]) -> None:
    db.query(RepositoryTag).filter(RepositoryTag.project_repository_id == project_repository_id).delete()
    for t in _normalize_tags(tags):
        db.add(RepositoryTag(project_repository_id=project_repository_id, tag=t.name, description=t.description))


def _load_pr(db: Session, pr_id: int) -> ProjectRepository:
    pr = (
        db.query(ProjectRepository)
        .options(joinedload(ProjectRepository.repository), joinedload(ProjectRepository.tags))
        .filter(ProjectRepository.id == pr_id)
        .first()
    )
    if not pr:
        raise HTTPException(404, "Repository not found")
    return pr


@router.post("", response_model=RepositoryOut, status_code=201)
def create_repository(body: RepositoryCreate, db: Session = Depends(get_db)):
    project = db.get(Project, body.project_id)
    if not project:
        raise HTTPException(404, "Project not found")

    try:
        provider = ProviderType(body.provider_type)
    except ValueError:
        raise HTTPException(400, f"Unknown provider_type: {body.provider_type!r}. Use 'bitbucket', 'gitlab', or 'github'.")

    # Upsert repository by URL (globally unique)
    repo = db.query(Repository).filter_by(url=body.url).first()
    if not repo:
        repo = Repository(url=body.url, provider_type=provider)
        db.add(repo)
        db.flush()
    elif repo.provider_type != provider:
        # Update provider_type if caller specifies a different one
        repo.provider_type = provider

    # Check this project doesn't already link to this repo URL
    existing_pr = db.query(ProjectRepository).filter_by(
        project_id=body.project_id, repository_id=repo.id
    ).first()
    if existing_pr:
        raise HTTPException(409, "This project already has a repository with that URL")

    pr = ProjectRepository(
        project_id=body.project_id,
        repository_id=repo.id,
        name=body.name,
        default_branch=body.default_branch,
        credentials_username=body.credentials_username,
        credentials_token=body.credentials_token,
    )
    db.add(pr)
    db.commit()
    db.refresh(pr)
    _set_repository_tags(db, pr.id, body.tags)
    db.commit()
    return _load_pr(db, pr.id)


@router.get("/{repo_id}", response_model=RepositoryOut)
def get_repository(repo_id: int, db: Session = Depends(get_db)):
    return _load_pr(db, repo_id)


@router.post("/scan-all", response_model=list[ScanOut], status_code=202)
def trigger_scan_all(db: Session = Depends(get_db)):
    """Create a pending scan for every project-repository association. Worker processes them in order."""
    prs = db.query(ProjectRepository).all()
    if not prs:
        return []
    created = []
    for pr in prs:
        scan = Scan(
            project_repository_id=pr.id,
            branch=pr.default_branch or "",
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
    pr = db.get(ProjectRepository, repo_id)
    if not pr:
        raise HTTPException(404, "Repository not found")
    _set_repository_tags(db, repo_id, body.tags)
    db.commit()
    return _load_pr(db, repo_id)


@router.put("/{repo_id}", response_model=RepositoryOut)
def update_repository(repo_id: int, body: RepositoryUpdate, db: Session = Depends(get_db)):
    pr = db.get(ProjectRepository, repo_id)
    if not pr:
        raise HTTPException(404, "Repository not found")

    try:
        provider = ProviderType(body.provider_type)
    except ValueError:
        raise HTTPException(400, f"Unknown provider_type: {body.provider_type!r}. Use 'bitbucket', 'gitlab', or 'github'.")

    if body.project_id is not None and body.project_id != pr.project_id:
        if not db.get(Project, body.project_id):
            raise HTTPException(404, "Project not found")
        pr.project_id = body.project_id

    # Handle URL change
    current_url = pr.repository.url
    if body.url != current_url:
        old_repo = pr.repository
        new_repo = db.query(Repository).filter_by(url=body.url).first()
        if not new_repo:
            new_repo = Repository(url=body.url, provider_type=provider)
            db.add(new_repo)
            db.flush()
        else:
            # Check no duplicate ProjectRepository for this project + new repo
            conflict = db.query(ProjectRepository).filter_by(
                project_id=pr.project_id, repository_id=new_repo.id
            ).filter(ProjectRepository.id != pr.id).first()
            if conflict:
                raise HTTPException(409, "This project already has a repository with that URL")
        pr.repository_id = new_repo.id
        pr.repository = new_repo
        # Clean up old repository if it has no remaining project_repositories
        remaining = db.query(ProjectRepository).filter_by(repository_id=old_repo.id).count()
        if remaining == 0:
            db.delete(old_repo)
    elif pr.repository.provider_type != provider:
        pr.repository.provider_type = provider

    pr.name = body.name
    pr.default_branch = body.default_branch
    pr.credentials_username = body.credentials_username
    pr.credentials_token = body.credentials_token
    db.commit()
    return _load_pr(db, repo_id)


@router.delete("/{repo_id}", status_code=204)
def delete_repository(repo_id: int, db: Session = Depends(get_db)):
    pr = db.get(ProjectRepository, repo_id)
    if not pr:
        raise HTTPException(404, "Repository not found")
    repo_id_global = pr.repository_id
    db.delete(pr)
    db.flush()
    # Clean up underlying Repository if no longer referenced
    remaining = db.query(ProjectRepository).filter_by(repository_id=repo_id_global).count()
    if remaining == 0:
        repo = db.get(Repository, repo_id_global)
        if repo:
            db.delete(repo)
    db.commit()


@router.post("/{repo_id}/scan", response_model=ScanOut, status_code=202)
def trigger_scan(
    repo_id: int,
    body: ScanTrigger,
    db: Session = Depends(get_db),
):
    pr = db.get(ProjectRepository, repo_id)
    if not pr:
        raise HTTPException(404, "Repository not found")

    branch = body.branch or pr.default_branch
    scan = Scan(
        project_repository_id=pr.id,
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
    pr = db.get(ProjectRepository, repo_id)
    if not pr:
        raise HTTPException(404, "Repository not found")
    return (
        db.query(Scan)
        .filter_by(project_repository_id=repo_id)
        .order_by(Scan.created_at.desc())
        .all()
    )


@router.get("/{repo_id}/git-tags", response_model=list[RepositoryGitTagOut])
def list_git_tags(repo_id: int, db: Session = Depends(get_db)):
    pr = (
        db.query(ProjectRepository)
        .options(joinedload(ProjectRepository.repository))
        .filter(ProjectRepository.id == repo_id)
        .first()
    )
    if not pr:
        raise HTTPException(404, "Repository not found")
    return (
        db.query(RepositoryGitTag)
        .filter_by(repository_id=pr.repository_id)
        .order_by(RepositoryGitTag.tagged_at.desc().nullslast())
        .all()
    )


@router.get("/{repo_id}/modules")
def list_modules(repo_id: int, db: Session = Depends(get_db)):
    from app.models import Module
    pr = db.get(ProjectRepository, repo_id)
    if not pr:
        raise HTTPException(404, "Repository not found")
    modules = db.query(Module).filter_by(project_repository_id=repo_id).all()
    return [{"id": m.id, "path": m.path, "name": m.name} for m in modules]


@router.get("/{repo_id}/activity", response_model=list[RepositoryDailyActivityOut])
def get_repository_activity(repo_id: int, db: Session = Depends(get_db)):
    """Daily commit activity for a project-repository association across all time."""
    pr = db.get(ProjectRepository, repo_id)
    if not pr:
        raise HTTPException(404, "Repository not found")
    rows = (
        db.query(RepositoryDailyActivity)
        .filter_by(project_repository_id=repo_id)
        .order_by(RepositoryDailyActivity.commit_date)
        .all()
    )
    return [RepositoryDailyActivityOut(date=str(r.commit_date), count=r.commit_count) for r in rows]

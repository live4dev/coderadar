from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import Repository, Scan, ScanStatus, Project, ProviderType
from app.schemas.repository import RepositoryCreate, RepositoryOut, ScanTrigger
from app.schemas.scan import ScanOut
from app.services.scanning.queue import enqueue

router = APIRouter(prefix="/repositories", tags=["repositories"])


@router.post("", response_model=RepositoryOut, status_code=201)
def create_repository(body: RepositoryCreate, db: Session = Depends(get_db)):
    project = db.get(Project, body.project_id)
    if not project:
        raise HTTPException(404, "Project not found")

    try:
        provider = ProviderType(body.provider_type)
    except ValueError:
        raise HTTPException(400, f"Unknown provider_type: {body.provider_type!r}. Use 'bitbucket' or 'gitlab'.")

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
    return repo


@router.get("/{repo_id}", response_model=RepositoryOut)
def get_repository(repo_id: int, db: Session = Depends(get_db)):
    repo = db.get(Repository, repo_id)
    if not repo:
        raise HTTPException(404, "Repository not found")
    return repo


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


@router.get("/{repo_id}/modules")
def list_modules(repo_id: int, db: Session = Depends(get_db)):
    from app.models import Module
    repo = db.get(Repository, repo_id)
    if not repo:
        raise HTTPException(404, "Repository not found")
    modules = db.query(Module).filter_by(repository_id=repo_id).all()
    return [{"id": m.id, "path": m.path, "name": m.name} for m in modules]

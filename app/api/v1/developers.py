from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from app.db.session import get_db
from app.models import (
    Developer, DeveloperLanguageContribution, DeveloperModuleContribution,
    DeveloperModuleContribution, IdentityOverride,
)
from app.schemas.developer import (
    DeveloperOut, DeveloperLanguageOut, DeveloperModuleOut, IdentityOverrideCreate,
)

router = APIRouter(prefix="/developers", tags=["developers"])


@router.get("/{developer_id}", response_model=DeveloperOut)
def get_developer(developer_id: int, db: Session = Depends(get_db)):
    dev = db.get(Developer, developer_id)
    if not dev:
        raise HTTPException(404, "Developer not found")
    return dev


@router.get("/{developer_id}/languages", response_model=list[DeveloperLanguageOut])
def get_developer_languages(
    developer_id: int,
    scan_id: int | None = None,
    db: Session = Depends(get_db),
):
    dev = db.get(Developer, developer_id)
    if not dev:
        raise HTTPException(404, "Developer not found")

    q = (
        db.query(DeveloperLanguageContribution)
        .options(joinedload(DeveloperLanguageContribution.language))
        .filter_by(developer_id=developer_id)
    )
    if scan_id:
        q = q.filter_by(scan_id=scan_id)

    rows = q.order_by(DeveloperLanguageContribution.percentage.desc()).all()
    return [
        DeveloperLanguageOut(
            language=r.language.name,
            commit_count=r.commit_count,
            files_changed=r.files_changed,
            loc_added=r.loc_added,
            percentage=r.percentage,
        )
        for r in rows
    ]


@router.get("/{developer_id}/modules", response_model=list[DeveloperModuleOut])
def get_developer_modules(
    developer_id: int,
    scan_id: int | None = None,
    db: Session = Depends(get_db),
):
    dev = db.get(Developer, developer_id)
    if not dev:
        raise HTTPException(404, "Developer not found")

    q = (
        db.query(DeveloperModuleContribution)
        .options(joinedload(DeveloperModuleContribution.module))
        .filter_by(developer_id=developer_id)
    )
    if scan_id:
        q = q.filter_by(scan_id=scan_id)

    rows = q.order_by(DeveloperModuleContribution.percentage.desc()).all()
    return [
        DeveloperModuleOut(
            module_path=r.module.path,
            module_name=r.module.name,
            commit_count=r.commit_count,
            files_changed=r.files_changed,
            loc_added=r.loc_added,
            percentage=r.percentage,
        )
        for r in rows
    ]


@router.post("/identity-overrides", status_code=201)
def create_identity_override(body: IdentityOverrideCreate, db: Session = Depends(get_db)):
    override = IdentityOverride(
        project_id=body.project_id,
        raw_name=body.raw_name,
        raw_email=body.raw_email,
        canonical_username=body.canonical_username,
        note=body.note,
    )
    db.add(override)
    db.commit()
    return {"status": "created", "canonical_username": body.canonical_username}

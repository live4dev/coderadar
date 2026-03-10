from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.db.session import get_db
from app.models import (
    Developer, DeveloperContribution, DeveloperLanguageContribution,
    DeveloperModuleContribution, IdentityOverride, Language, Module, Project,
    Repository, Scan,
)
from app.schemas.developer import (
    DeveloperOut, DeveloperListOut, DeveloperLanguageOut, DeveloperModuleOut,
    DeveloperContributionsSummaryOut, IdentityOverrideCreate,
)

router = APIRouter(prefix="/developers", tags=["developers"])


@router.get("", response_model=list[DeveloperListOut])
def list_developers(
    project_id: int | None = None,
    db: Session = Depends(get_db),
):
    """List all developers with aggregated stats across all their scans. Optional project_id filter."""
    q = (
        db.query(
            Developer.id,
            Developer.canonical_username,
            Developer.display_name,
            Developer.primary_email,
            Developer.project_id,
            Project.name.label("project_name"),
            func.coalesce(func.sum(DeveloperContribution.commit_count), 0).label("total_commits"),
            func.coalesce(func.sum(DeveloperContribution.insertions), 0).label("total_insertions"),
            func.coalesce(func.sum(DeveloperContribution.deletions), 0).label("total_deletions"),
            func.coalesce(func.sum(DeveloperContribution.files_changed), 0).label("files_changed"),
            func.coalesce(func.sum(DeveloperContribution.active_days), 0).label("active_days"),
            func.min(DeveloperContribution.first_commit_at).label("first_commit_at"),
            func.max(DeveloperContribution.last_commit_at).label("last_commit_at"),
        )
        .join(Project, Developer.project_id == Project.id)
        .outerjoin(DeveloperContribution, Developer.id == DeveloperContribution.developer_id)
        .group_by(Developer.id, Project.id, Project.name)
    )
    if project_id is not None:
        q = q.filter(Developer.project_id == project_id)
    # Order by total commits descending (same expression as in select)
    total_commits_expr = func.coalesce(func.sum(DeveloperContribution.commit_count), 0)
    rows = q.order_by(total_commits_expr.desc()).all()
    return [
        DeveloperListOut(
            id=r.id,
            canonical_username=r.canonical_username,
            display_name=r.display_name,
            primary_email=r.primary_email,
            project_id=r.project_id,
            project_name=r.project_name,
            total_commits=int(r.total_commits),
            total_insertions=int(r.total_insertions),
            total_deletions=int(r.total_deletions),
            files_changed=int(r.files_changed),
            active_days=int(r.active_days),
            first_commit_at=r.first_commit_at,
            last_commit_at=r.last_commit_at,
        )
        for r in rows
    ]


@router.get("/{developer_id}", response_model=DeveloperOut)
def get_developer(developer_id: int, db: Session = Depends(get_db)):
    dev = (
        db.query(Developer)
        .options(joinedload(Developer.project))
        .filter(Developer.id == developer_id)
        .first()
    )
    if not dev:
        raise HTTPException(404, "Developer not found")
    return DeveloperOut(
        id=dev.id,
        canonical_username=dev.canonical_username,
        display_name=dev.display_name,
        primary_email=dev.primary_email,
        project_id=dev.project_id,
        project_name=dev.project.name if dev.project else None,
    )


@router.get("/{developer_id}/contributions", response_model=DeveloperContributionsSummaryOut)
def get_developer_contributions(developer_id: int, db: Session = Depends(get_db)):
    """Aggregated contribution stats across all scans for this developer."""
    dev = db.get(Developer, developer_id)
    if not dev:
        raise HTTPException(404, "Developer not found")
    row = (
        db.query(
            func.coalesce(func.sum(DeveloperContribution.commit_count), 0).label("commit_count"),
            func.coalesce(func.sum(DeveloperContribution.insertions), 0).label("insertions"),
            func.coalesce(func.sum(DeveloperContribution.deletions), 0).label("deletions"),
            func.coalesce(func.sum(DeveloperContribution.files_changed), 0).label("files_changed"),
            func.coalesce(func.sum(DeveloperContribution.active_days), 0).label("active_days"),
            func.min(DeveloperContribution.first_commit_at).label("first_commit_at"),
            func.max(DeveloperContribution.last_commit_at).label("last_commit_at"),
        )
        .filter(DeveloperContribution.developer_id == developer_id)
        .one()
    )
    dev_commits = int(row.commit_count)
    project_total_commits = None
    share_pct = None
    if dev_commits > 0 and dev:
        project_total = (
            db.query(func.coalesce(func.sum(DeveloperContribution.commit_count), 0))
            .join(Scan, DeveloperContribution.scan_id == Scan.id)
            .join(Repository, Scan.repository_id == Repository.id)
            .filter(Repository.project_id == dev.project_id)
            .scalar()
        )
        if project_total and project_total > 0:
            project_total_commits = int(project_total)
            share_pct = round(100.0 * dev_commits / project_total_commits, 2)
    return DeveloperContributionsSummaryOut(
        commit_count=dev_commits,
        insertions=int(row.insertions),
        deletions=int(row.deletions),
        files_changed=int(row.files_changed),
        active_days=int(row.active_days),
        first_commit_at=row.first_commit_at,
        last_commit_at=row.last_commit_at,
        project_total_commits=project_total_commits,
        share_pct=share_pct,
    )


@router.get("/{developer_id}/languages", response_model=list[DeveloperLanguageOut])
def get_developer_languages(
    developer_id: int,
    scan_id: int | None = None,
    db: Session = Depends(get_db),
):
    dev = db.get(Developer, developer_id)
    if not dev:
        raise HTTPException(404, "Developer not found")

    if scan_id is not None:
        q = (
            db.query(DeveloperLanguageContribution)
            .options(joinedload(DeveloperLanguageContribution.language))
            .filter_by(developer_id=developer_id, scan_id=scan_id)
        )
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

    # Aggregate across all scans: group by language_id, sum metrics, recompute percentage
    agg = (
        db.query(
            Language.name,
            func.sum(DeveloperLanguageContribution.commit_count).label("commit_count"),
            func.sum(DeveloperLanguageContribution.files_changed).label("files_changed"),
            func.sum(DeveloperLanguageContribution.loc_added).label("loc_added"),
        )
        .join(DeveloperLanguageContribution, DeveloperLanguageContribution.language_id == Language.id)
        .filter(DeveloperLanguageContribution.developer_id == developer_id)
        .group_by(Language.id, Language.name)
    )
    rows = agg.order_by(func.sum(DeveloperLanguageContribution.loc_added).desc()).all()
    total_loc = sum(r.loc_added or 0 for r in rows)
    return [
        DeveloperLanguageOut(
            language=r.name,
            commit_count=int(r.commit_count or 0),
            files_changed=int(r.files_changed or 0),
            loc_added=int(r.loc_added or 0),
            percentage=round(100.0 * (r.loc_added or 0) / total_loc, 2) if total_loc else 0.0,
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

    if scan_id is not None:
        q = (
            db.query(DeveloperModuleContribution)
            .options(joinedload(DeveloperModuleContribution.module))
            .filter_by(developer_id=developer_id, scan_id=scan_id)
        )
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

    # Aggregate across all scans: group by module_id, sum metrics, recompute percentage
    agg = (
        db.query(
            Module.path,
            Module.name,
            func.sum(DeveloperModuleContribution.commit_count).label("commit_count"),
            func.sum(DeveloperModuleContribution.files_changed).label("files_changed"),
            func.sum(DeveloperModuleContribution.loc_added).label("loc_added"),
        )
        .join(DeveloperModuleContribution, DeveloperModuleContribution.module_id == Module.id)
        .filter(DeveloperModuleContribution.developer_id == developer_id)
        .group_by(Module.id, Module.path, Module.name)
    )
    rows = agg.order_by(func.sum(DeveloperModuleContribution.loc_added).desc()).all()
    total_loc = sum(r.loc_added or 0 for r in rows)
    return [
        DeveloperModuleOut(
            module_path=r.path,
            module_name=r.name,
            commit_count=int(r.commit_count or 0),
            files_changed=int(r.files_changed or 0),
            loc_added=int(r.loc_added or 0),
            percentage=round(100.0 * (r.loc_added or 0) / total_loc, 2) if total_loc else 0.0,
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

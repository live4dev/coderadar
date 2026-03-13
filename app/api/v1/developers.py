from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_
from sqlalchemy.orm import Session, joinedload

from app.db.session import get_db
from app.models import (
    Developer, DeveloperTag, DeveloperProfile, DeveloperContribution, DeveloperLanguageContribution,
    DeveloperModuleContribution, IdentityOverride, Language, Module, Project,
    Repository, Scan,
)
from app.schemas.project import TagsUpdate
from app.schemas.developer import (
    DeveloperOut, DeveloperListOut, DeveloperProfileOut, DeveloperLanguageOut,
    DeveloperModuleOut, DeveloperContributionsSummaryOut, IdentityOverrideCreate,
)

router = APIRouter(prefix="/developers", tags=["developers"])


def _profile_to_out(p: DeveloperProfile) -> DeveloperProfileOut:
    return DeveloperProfileOut(
        id=p.id,
        developer_id=p.developer_id,
        canonical_username=p.canonical_username,
        display_name=p.display_name,
        primary_email=p.primary_email,
    )


SORT_FIELDS = {"commits", "insertions", "deletions", "files_changed", "active_days", "last_commit_at", "name"}


@router.get("", response_model=list[DeveloperListOut])
def list_developers(
    project_id: int | None = None,
    sort_by: str = Query("commits", description="Sort by: commits, insertions, deletions, files_changed, active_days, last_commit_at, name"),
    order: str = Query("desc", description="Sort order: asc or desc"),
    q: str | None = Query(None, description="Search by display name, username or email"),
    db: Session = Depends(get_db),
):
    """List all developers with aggregated stats (across all their profiles). Optional project_id, sort, search."""
    if sort_by not in SORT_FIELDS:
        sort_by = "commits"
    order_asc = order.lower() == "asc"

    if project_id is not None:
        q_base = (
            db.query(
                Developer.id,
                func.coalesce(func.sum(DeveloperContribution.commit_count), 0).label("total_commits"),
                func.coalesce(func.sum(DeveloperContribution.insertions), 0).label("total_insertions"),
                func.coalesce(func.sum(DeveloperContribution.deletions), 0).label("total_deletions"),
                func.coalesce(func.sum(DeveloperContribution.files_changed), 0).label("files_changed"),
                func.coalesce(func.sum(DeveloperContribution.active_days), 0).label("active_days"),
                func.min(DeveloperContribution.first_commit_at).label("first_commit_at"),
                func.max(DeveloperContribution.last_commit_at).label("last_commit_at"),
            )
            .join(DeveloperProfile, DeveloperProfile.developer_id == Developer.id)
            .join(DeveloperContribution, DeveloperContribution.profile_id == DeveloperProfile.id)
            .join(Scan, DeveloperContribution.scan_id == Scan.id)
            .join(Repository, Scan.repository_id == Repository.id)
            .filter(Repository.project_id == project_id)
            .group_by(Developer.id)
        )
    else:
        q_base = (
            db.query(
                Developer.id,
                func.coalesce(func.sum(DeveloperContribution.commit_count), 0).label("total_commits"),
                func.coalesce(func.sum(DeveloperContribution.insertions), 0).label("total_insertions"),
                func.coalesce(func.sum(DeveloperContribution.deletions), 0).label("total_deletions"),
                func.coalesce(func.sum(DeveloperContribution.files_changed), 0).label("files_changed"),
                func.coalesce(func.sum(DeveloperContribution.active_days), 0).label("active_days"),
                func.min(DeveloperContribution.first_commit_at).label("first_commit_at"),
                func.max(DeveloperContribution.last_commit_at).label("last_commit_at"),
            )
            .join(DeveloperProfile, DeveloperProfile.developer_id == Developer.id)
            .outerjoin(DeveloperContribution, DeveloperContribution.profile_id == DeveloperProfile.id)
            .group_by(Developer.id)
        )

    if q and q.strip():
        search_term = f"%{q.strip()}%"
        dev_ids_with_search = (
            db.query(Developer.id)
            .join(DeveloperProfile, DeveloperProfile.developer_id == Developer.id)
            .filter(
                or_(
                    DeveloperProfile.display_name.ilike(search_term),
                    DeveloperProfile.canonical_username.ilike(search_term),
                    DeveloperProfile.primary_email.ilike(search_term),
                )
            )
            .distinct()
            .subquery()
        )
        q_base = q_base.filter(Developer.id.in_(db.query(dev_ids_with_search.c.id)))

    if sort_by == "name":
        rows = q_base.all()
        dev_ids = [r.id for r in rows]
        if not dev_ids:
            return []
        developers_with_profiles = (
            db.query(Developer)
            .options(joinedload(Developer.profiles), joinedload(Developer.tags))
            .filter(Developer.id.in_(dev_ids))
            .all()
        )
        dev_map = {d.id: d for d in developers_with_profiles}

        def name_key(rid):
            dev = dev_map.get(rid, Developer())
            profs = dev.profiles or []
            first = profs[0] if profs else None
            if first:
                return (first.display_name or first.canonical_username or "").lower()
            return ""

        rows = sorted(rows, key=lambda r: name_key(r.id), reverse=not order_asc)
    else:
        if sort_by == "commits":
            order_expr = func.coalesce(func.sum(DeveloperContribution.commit_count), 0)
        elif sort_by == "insertions":
            order_expr = func.coalesce(func.sum(DeveloperContribution.insertions), 0)
        elif sort_by == "deletions":
            order_expr = func.coalesce(func.sum(DeveloperContribution.deletions), 0)
        elif sort_by == "files_changed":
            order_expr = func.coalesce(func.sum(DeveloperContribution.files_changed), 0)
        elif sort_by == "active_days":
            order_expr = func.coalesce(func.sum(DeveloperContribution.active_days), 0)
        elif sort_by == "last_commit_at":
            order_expr = func.max(DeveloperContribution.last_commit_at)
        else:
            order_expr = func.coalesce(func.sum(DeveloperContribution.commit_count), 0)
        if order_asc:
            order_expr = order_expr.asc()
        else:
            order_expr = order_expr.desc()
        rows = q_base.order_by(order_expr).all()

    if not rows:
        return []

    dev_ids = [r.id for r in rows]
    developers_with_profiles = (
        db.query(Developer)
        .options(joinedload(Developer.profiles), joinedload(Developer.tags))
        .filter(Developer.id.in_(dev_ids))
        .all()
    )
    dev_map = {d.id: d for d in developers_with_profiles}
    project_name = None
    if project_id is not None:
        proj = db.get(Project, project_id)
        project_name = proj.name if proj else None

    return [
        DeveloperListOut(
            id=r.id,
            total_commits=int(r.total_commits),
            total_insertions=int(r.total_insertions),
            total_deletions=int(r.total_deletions),
            files_changed=int(r.files_changed),
            active_days=int(r.active_days),
            first_commit_at=r.first_commit_at,
            last_commit_at=r.last_commit_at,
            project_id=project_id,
            project_name=project_name,
            profiles=[_profile_to_out(p) for p in dev_map.get(r.id, Developer()).profiles],
            tags=[t.tag for t in (dev_map.get(r.id).tags if dev_map.get(r.id) else [])],
        )
        for r in rows
    ]


def _normalize_tags(tags: list[str]) -> list[str]:
    seen = set()
    out = []
    for t in tags:
        if not isinstance(t, str):
            continue
        s = t.strip()[:128]
        if s and s not in seen:
            seen.add(s)
            out.append(s)
    return out


def _set_developer_tags(db: Session, developer_id: int, tags: list[str]) -> None:
    db.query(DeveloperTag).filter(DeveloperTag.developer_id == developer_id).delete()
    for tag in _normalize_tags(tags):
        db.add(DeveloperTag(developer_id=developer_id, tag=tag))


@router.get("/{developer_id}", response_model=DeveloperOut)
def get_developer(developer_id: int, db: Session = Depends(get_db)):
    dev = (
        db.query(Developer)
        .options(joinedload(Developer.profiles), joinedload(Developer.tags))
        .filter(Developer.id == developer_id)
        .first()
    )
    if not dev:
        raise HTTPException(404, "Developer not found")
    return DeveloperOut(
        id=dev.id,
        profiles=[_profile_to_out(p) for p in dev.profiles],
        created_at=dev.created_at,
        tags=[t.tag for t in dev.tags],
    )


@router.put("/{developer_id}/tags", response_model=DeveloperOut)
def set_developer_tags(developer_id: int, body: TagsUpdate, db: Session = Depends(get_db)):
    dev = db.get(Developer, developer_id)
    if not dev:
        raise HTTPException(404, "Developer not found")
    _set_developer_tags(db, developer_id, body.tags)
    db.commit()
    db.refresh(dev)
    dev = (
        db.query(Developer)
        .options(joinedload(Developer.profiles), joinedload(Developer.tags))
        .filter(Developer.id == developer_id)
        .first()
    )
    return DeveloperOut(
        id=dev.id,
        profiles=[_profile_to_out(p) for p in dev.profiles],
        created_at=dev.created_at,
        tags=[t.tag for t in dev.tags],
    )


@router.get("/{developer_id}/profiles", response_model=list[DeveloperProfileOut])
def list_developer_profiles(developer_id: int, db: Session = Depends(get_db)):
    """List all profiles for a developer."""
    dev = db.get(Developer, developer_id)
    if not dev:
        raise HTTPException(404, "Developer not found")
    profiles = db.query(DeveloperProfile).filter_by(developer_id=developer_id).all()
    return [_profile_to_out(p) for p in profiles]


@router.get("/{developer_id}/contributions", response_model=DeveloperContributionsSummaryOut)
def get_developer_contributions(
    developer_id: int,
    project_id: int | None = Query(None),
    db: Session = Depends(get_db),
):
    """Aggregated contribution stats across all scans (and all profiles) for this developer."""
    dev = db.get(Developer, developer_id)
    if not dev:
        raise HTTPException(404, "Developer not found")
    profile_ids = [p.id for p in dev.profiles] if dev.profiles else []
    if not profile_ids:
        subq = db.query(DeveloperProfile.id).filter(DeveloperProfile.developer_id == developer_id)
        profile_ids = [r[0] for r in subq.all()]
    if not profile_ids:
        return DeveloperContributionsSummaryOut(
            commit_count=0,
            insertions=0,
            deletions=0,
            files_changed=0,
            active_days=0,
            first_commit_at=None,
            last_commit_at=None,
        )
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
        .filter(DeveloperContribution.profile_id.in_(profile_ids))
        .one()
    )
    dev_commits = int(row.commit_count)
    project_total_commits = None
    share_pct = None
    if project_id is not None and dev_commits > 0:
        project_total = (
            db.query(func.coalesce(func.sum(DeveloperContribution.commit_count), 0))
            .join(Scan, DeveloperContribution.scan_id == Scan.id)
            .join(Repository, Scan.repository_id == Repository.id)
            .filter(Repository.project_id == project_id)
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
    profile_ids_subq = db.query(DeveloperProfile.id).filter(DeveloperProfile.developer_id == developer_id)
    profile_ids = [r[0] for r in profile_ids_subq.all()]
    if not profile_ids:
        return []

    if scan_id is not None:
        q = (
            db.query(DeveloperLanguageContribution)
            .options(joinedload(DeveloperLanguageContribution.language))
            .filter(
                DeveloperLanguageContribution.profile_id.in_(profile_ids),
                DeveloperLanguageContribution.scan_id == scan_id,
            )
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

    agg = (
        db.query(
            Language.name,
            func.sum(DeveloperLanguageContribution.commit_count).label("commit_count"),
            func.sum(DeveloperLanguageContribution.files_changed).label("files_changed"),
            func.sum(DeveloperLanguageContribution.loc_added).label("loc_added"),
        )
        .join(DeveloperLanguageContribution, DeveloperLanguageContribution.language_id == Language.id)
        .filter(DeveloperLanguageContribution.profile_id.in_(profile_ids))
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
    profile_ids_subq = db.query(DeveloperProfile.id).filter(DeveloperProfile.developer_id == developer_id)
    profile_ids = [r[0] for r in profile_ids_subq.all()]
    if not profile_ids:
        return []

    if scan_id is not None:
        q = (
            db.query(DeveloperModuleContribution)
            .options(joinedload(DeveloperModuleContribution.module))
            .filter(
                DeveloperModuleContribution.profile_id.in_(profile_ids),
                DeveloperModuleContribution.scan_id == scan_id,
            )
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

    agg = (
        db.query(
            Module.path,
            Module.name,
            func.sum(DeveloperModuleContribution.commit_count).label("commit_count"),
            func.sum(DeveloperModuleContribution.files_changed).label("files_changed"),
            func.sum(DeveloperModuleContribution.loc_added).label("loc_added"),
        )
        .join(DeveloperModuleContribution, DeveloperModuleContribution.module_id == Module.id)
        .filter(DeveloperModuleContribution.profile_id.in_(profile_ids))
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

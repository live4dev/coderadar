from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_
from sqlalchemy.orm import Session, joinedload

from app.db.session import get_db
from app.models import (
    Repository, Scan, ScanLanguage, Dependency, ScanScore, ScanRisk, ScanPersonalDataFinding,
    DeveloperContribution, DeveloperProfile,
)
from app.services.source_links import build_source_url
from app.schemas.scan import (
    ScanOut, ScanSummaryOut, ScanLanguageOut,
    DependencyOut, ScanScoreOut, ScanRiskOut,
    PersonalDataOut, PersonalDataCountOut, PersonalDataFindingOut,
    ScanCompareOut, ScanMetricsDiff, ScanLanguageDiff,
    ScanScoreDiff, ScanRiskDiff, ScanDeveloperDiff,
)

router = APIRouter(prefix="/scans", tags=["scans"])


def _get_scan_or_404(scan_id: int, db: Session) -> Scan:
    scan = db.get(Scan, scan_id)
    if not scan:
        raise HTTPException(404, "Scan not found")
    return scan


@router.get("/{scan_id}", response_model=ScanOut)
def get_scan(scan_id: int, db: Session = Depends(get_db)):
    return _get_scan_or_404(scan_id, db)


@router.get("/{scan_id}/summary", response_model=ScanSummaryOut)
def get_scan_summary(scan_id: int, db: Session = Depends(get_db)):
    return _get_scan_or_404(scan_id, db)


@router.get("/{scan_id}/languages", response_model=list[ScanLanguageOut])
def get_scan_languages(scan_id: int, db: Session = Depends(get_db)):
    _get_scan_or_404(scan_id, db)
    rows = (
        db.query(ScanLanguage)
        .options(joinedload(ScanLanguage.language))
        .filter_by(scan_id=scan_id)
        .order_by(ScanLanguage.loc.desc())
        .all()
    )
    return [
        ScanLanguageOut(
            language=row.language.name,
            file_count=row.file_count,
            loc=row.loc,
            percentage=row.percentage,
        )
        for row in rows
    ]


@router.get("/{scan_id}/dependencies", response_model=list[DependencyOut])
def get_scan_dependencies(scan_id: int, db: Session = Depends(get_db)):
    _get_scan_or_404(scan_id, db)
    return db.query(Dependency).filter_by(scan_id=scan_id).all()


@router.get("/{scan_id}/scores", response_model=list[ScanScoreOut])
def get_scan_scores(scan_id: int, db: Session = Depends(get_db)):
    _get_scan_or_404(scan_id, db)
    return db.query(ScanScore).filter_by(scan_id=scan_id).all()


@router.get("/{scan_id}/risks", response_model=list[ScanRiskOut])
def get_scan_risks(scan_id: int, db: Session = Depends(get_db)):
    _get_scan_or_404(scan_id, db)
    return (
        db.query(ScanRisk)
        .filter_by(scan_id=scan_id)
        .order_by(ScanRisk.severity.desc())
        .all()
    )


@router.get("/{scan_id}/personal-data", response_model=PersonalDataOut)
def get_scan_personal_data(scan_id: int, db: Session = Depends(get_db)):
    scan = _get_scan_or_404(scan_id, db)
    repo = db.get(Repository, scan.repository_id)
    ref = scan.commit_sha or scan.branch or (repo.default_branch if repo else None) or "HEAD"
    provider = repo.provider_type.value if repo else ""
    repo_url = repo.url if repo else ""

    rows = (
        db.query(ScanPersonalDataFinding)
        .filter_by(scan_id=scan_id)
        .order_by(ScanPersonalDataFinding.pdn_type, ScanPersonalDataFinding.file_path, ScanPersonalDataFinding.line_number)
        .all()
    )
    # Aggregate counts by pdn_type
    count_q = (
        db.query(ScanPersonalDataFinding.pdn_type, func.count(ScanPersonalDataFinding.id).label("count"))
        .filter_by(scan_id=scan_id)
        .group_by(ScanPersonalDataFinding.pdn_type)
    )
    counts = [PersonalDataCountOut(pdn_type=t, count=c) for t, c in count_q.all()]
    findings = [
        PersonalDataFindingOut(
            pdn_type=r.pdn_type,
            matched_identifier=r.matched_identifier,
            file_path=r.file_path,
            line_number=r.line_number,
            source_url=build_source_url(repo_url, provider, ref, r.file_path, r.line_number) if repo_url and provider else None,
        )
        for r in rows
    ]
    return PersonalDataOut(counts=counts, findings=findings)


@router.get("/{scan_id}/compare", response_model=ScanCompareOut)
def compare_scans(
    scan_id: int,
    with_scan: int = Query(..., alias="with"),
    db: Session = Depends(get_db),
):
    scan_a = _get_scan_or_404(scan_id, db)
    scan_b = _get_scan_or_404(with_scan, db)

    # Metrics diff
    def _safe_delta(a, b):
        if a is None or b is None:
            return None
        return b - a

    metrics = ScanMetricsDiff(
        total_files_delta=_safe_delta(scan_a.total_files, scan_b.total_files),
        total_loc_delta=_safe_delta(scan_a.total_loc, scan_b.total_loc),
        size_bytes_delta=_safe_delta(scan_a.size_bytes, scan_b.size_bytes),
    )

    # Language diff
    def _lang_map(scan: Scan) -> dict[str, ScanLanguage]:
        rows = (
            db.query(ScanLanguage)
            .options(joinedload(ScanLanguage.language))
            .filter_by(scan_id=scan.id)
            .all()
        )
        return {row.language.name: row for row in rows}

    langs_a = _lang_map(scan_a)
    langs_b = _lang_map(scan_b)
    all_langs = set(langs_a) | set(langs_b)
    lang_diffs: list[ScanLanguageDiff] = []
    for lang in all_langs:
        if lang in langs_a and lang not in langs_b:
            lang_diffs.append(ScanLanguageDiff(language=lang, change="removed", loc_delta=None, percentage_delta=None))
        elif lang not in langs_a and lang in langs_b:
            lang_diffs.append(ScanLanguageDiff(language=lang, change="added", loc_delta=langs_b[lang].loc, percentage_delta=langs_b[lang].percentage))
        else:
            loc_delta = langs_b[lang].loc - langs_a[lang].loc
            pct_delta = round(langs_b[lang].percentage - langs_a[lang].percentage, 2)
            if loc_delta != 0:
                lang_diffs.append(ScanLanguageDiff(language=lang, change="changed", loc_delta=loc_delta, percentage_delta=pct_delta))

    # Score diff
    scores_a = {r.domain: r.score for r in db.query(ScanScore).filter_by(scan_id=scan_a.id).all()}
    scores_b = {r.domain: r.score for r in db.query(ScanScore).filter_by(scan_id=scan_b.id).all()}
    score_diffs = [
        ScanScoreDiff(
            domain=domain,
            score_a=scores_a.get(domain, 0.0),
            score_b=scores_b.get(domain, 0.0),
            delta=round(scores_b.get(domain, 0.0) - scores_a.get(domain, 0.0), 1),
        )
        for domain in set(scores_a) | set(scores_b)
    ]

    # Risk diff
    risks_a = {r.risk_type: r for r in db.query(ScanRisk).filter_by(scan_id=scan_a.id).all()}
    risks_b = {r.risk_type: r for r in db.query(ScanRisk).filter_by(scan_id=scan_b.id).all()}
    risk_diffs: list[ScanRiskDiff] = []
    for rt, r in risks_b.items():
        if rt not in risks_a:
            risk_diffs.append(ScanRiskDiff(risk_type=rt, title=r.title, severity=r.severity, change="new"))
    for rt, r in risks_a.items():
        if rt not in risks_b:
            risk_diffs.append(ScanRiskDiff(risk_type=rt, title=r.title, severity=r.severity, change="resolved"))

    # Developer diff (by profile canonical_username)
    def _dev_usernames(scan: Scan) -> set[str]:
        rows = (
            db.query(DeveloperContribution)
            .options(joinedload(DeveloperContribution.profile))
            .filter_by(scan_id=scan.id)
            .all()
        )
        return {r.profile.canonical_username for r in rows}

    devs_a = _dev_usernames(scan_a)
    devs_b = _dev_usernames(scan_b)
    dev_diffs = (
        [ScanDeveloperDiff(canonical_username=u, change="joined") for u in devs_b - devs_a]
        + [ScanDeveloperDiff(canonical_username=u, change="left") for u in devs_a - devs_b]
    )

    return ScanCompareOut(
        scan_a_id=scan_id,
        scan_b_id=with_scan,
        metrics=metrics,
        languages=lang_diffs,
        scores=score_diffs,
        risks=risk_diffs,
        developers=dev_diffs,
    )


SCAN_DEVELOPERS_SORT_FIELDS = {
    "name", "commits", "insertions", "deletions",
    "files_changed", "active_days", "last_commit_at",
}


@router.get("/{scan_id}/developers")
def get_scan_developers(
    scan_id: int,
    sort_by: str = Query(
        "commits",
        description="Sort by: name, commits, insertions, deletions, files_changed, active_days, last_commit_at",
    ),
    order: str = Query("desc", description="Sort order: asc or desc"),
    q: str | None = Query(None, description="Search by display name, username or email"),
    db: Session = Depends(get_db),
):
    _get_scan_or_404(scan_id, db)
    if sort_by not in SCAN_DEVELOPERS_SORT_FIELDS:
        sort_by = "commits"
    order_asc = order.lower() == "asc"

    query = (
        db.query(DeveloperContribution)
        .options(joinedload(DeveloperContribution.profile))
        .filter_by(scan_id=scan_id)
    )

    if q and q.strip():
        search_term = f"%{q.strip()}%"
        query = query.join(DeveloperProfile, DeveloperContribution.profile_id == DeveloperProfile.id).filter(
            or_(
                DeveloperProfile.display_name.ilike(search_term),
                DeveloperProfile.canonical_username.ilike(search_term),
                DeveloperProfile.primary_email.ilike(search_term),
            )
        )

    if sort_by == "name":
        query = query.join(DeveloperProfile, DeveloperContribution.profile_id == DeveloperProfile.id)
        name_col = func.coalesce(DeveloperProfile.display_name, DeveloperProfile.canonical_username)
        query = query.order_by(name_col.asc() if order_asc else name_col.desc())
    elif sort_by == "commits":
        query = query.order_by(
            DeveloperContribution.commit_count.asc() if order_asc else DeveloperContribution.commit_count.desc()
        )
    elif sort_by == "insertions":
        query = query.order_by(
            DeveloperContribution.insertions.asc() if order_asc else DeveloperContribution.insertions.desc()
        )
    elif sort_by == "deletions":
        query = query.order_by(
            DeveloperContribution.deletions.asc() if order_asc else DeveloperContribution.deletions.desc()
        )
    elif sort_by == "files_changed":
        query = query.order_by(
            DeveloperContribution.files_changed.asc() if order_asc else DeveloperContribution.files_changed.desc()
        )
    elif sort_by == "active_days":
        query = query.order_by(
            DeveloperContribution.active_days.asc() if order_asc else DeveloperContribution.active_days.desc()
        )
    elif sort_by == "last_commit_at":
        query = query.order_by(
            DeveloperContribution.last_commit_at.asc().nullslast() if order_asc
            else DeveloperContribution.last_commit_at.desc().nullsfirst()
        )

    rows = query.all()
    dev_ids = list({r.profile.developer_id for r in rows})
    dev_tags = {}
    if dev_ids:
        from app.models import Developer
        devs = db.query(Developer).options(joinedload(Developer.tags)).filter(Developer.id.in_(dev_ids)).all()
        dev_tags = {d.id: [t.tag for t in d.tags] for d in devs}
    return [
        {
            "developer_id": r.profile.developer_id,
            "profile": {
                "id": r.profile.id,
                "canonical_username": r.profile.canonical_username,
                "display_name": r.profile.display_name,
                "primary_email": r.profile.primary_email,
            },
            "commit_count": r.commit_count,
            "insertions": r.insertions,
            "deletions": r.deletions,
            "files_changed": r.files_changed,
            "active_days": r.active_days,
            "first_commit_at": r.first_commit_at,
            "last_commit_at": r.last_commit_at,
            "tags": dev_tags.get(r.profile.developer_id, []),
        }
        for r in rows
    ]

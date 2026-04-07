"""Analytics API: treemap tree and similar."""
import json
from calendar import monthrange
from collections import defaultdict
from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.db.session import get_db
from app.models import Project, Repository, ProjectRepository, Scan, ScanStatus, RepositoryDailyActivity
from app.models.contribution import DeveloperContribution
from app.models.scan_language import ScanLanguage
from app.schemas.analytics import TreemapNode, TechMapRepo, TechCounts, TechMapResponse, RepoLanguage, LanguageStat, SizeHistoryRepo, SizeHistoryResponse

router = APIRouter(prefix="/analytics", tags=["analytics"])


def _latest_scan_per_pr(db: Session, pr_ids: list[int]) -> dict[int, Scan]:
    """Return project_repository_id -> latest completed scan (with languages eager-loaded)."""
    if not pr_ids:
        return {}
    latest = (
        db.query(Scan)
        .options(
            joinedload(Scan.languages).joinedload(ScanLanguage.language)
        )
        .filter(
            Scan.project_repository_id.in_(pr_ids),
            Scan.status == ScanStatus.completed,
        )
        .order_by(Scan.started_at.desc(), Scan.id.desc())
        .all()
    )
    scan_by_pr: dict[int, Scan] = {}
    for s in latest:
        if s.project_repository_id not in scan_by_pr:
            scan_by_pr[s.project_repository_id] = s
    return scan_by_pr


@router.get("/treemap", response_model=TreemapNode)
def get_treemap(
    metric: str = Query("loc", description="Size metric: loc or files"),
    group_by: str = Query("projects_repos", description="Grouping: projects_repos"),
    project_id: int | None = Query(None, description="Optional: limit to one project"),
    db: Session = Depends(get_db),
):
    """Return a tree for treemap: root -> projects -> repositories (value = LOC or file count)."""
    if group_by != "projects_repos":
        raise HTTPException(400, "Only group_by=projects_repos is supported")
    if metric not in ("loc", "files"):
        raise HTTPException(400, "metric must be loc or files")

    projects = (
        db.query(Project)
        .options(joinedload(Project.tags))
        .order_by(Project.id)
        .all()
    )
    if project_id is not None:
        projects = [p for p in projects if p.id == project_id]
        if not projects:
            raise HTTPException(404, "Project not found")

    if not projects:
        return TreemapNode(name="root", value=0, type="root", children=[])

    pr_ids = []
    pr_to_project: dict[int, int] = {}
    for p in projects:
        prs = db.query(ProjectRepository).filter_by(project_id=p.id).all()
        for pr in prs:
            pr_ids.append(pr.id)
            pr_to_project[pr.id] = p.id

    scan_by_pr = _latest_scan_per_pr(db, pr_ids)

    # project_id -> list of (repo_name, pr_id, value)
    proj_children: dict[int, list[tuple[str, int, int]]] = {p.id: [] for p in projects}
    proj_value: dict[int, int] = {p.id: 0 for p in projects}

    prs_q = (
        db.query(ProjectRepository.id, ProjectRepository.name, ProjectRepository.project_id)
        .filter(ProjectRepository.id.in_(pr_ids))
        .all()
    )
    for r in prs_q:
        scan = scan_by_pr.get(r.id)
        if scan is None:
            continue
        val = (scan.total_loc or 0) if metric == "loc" else (scan.total_files or 0)
        proj_children[r.project_id].append((r.name, r.id, val))
        proj_value[r.project_id] = proj_value.get(r.project_id, 0) + val

    root_value = 0
    project_nodes: list[TreemapNode] = []
    for p in projects:
        pid = p.id
        repo_nodes = [
            TreemapNode(name=name, value=val, id=rid, type="repository", children=None)
            for name, rid, val in proj_children[pid]
        ]
        pval = proj_value[pid]
        root_value += pval
        project_nodes.append(
            TreemapNode(
                name=p.name,
                value=pval,
                id=pid,
                type="project",
                children=repo_nodes if repo_nodes else None,
            )
        )

    return TreemapNode(
        name="root",
        value=root_value,
        type="root",
        children=project_nodes,
    )


@router.get("/activity-tree", response_model=TreemapNode)
def get_activity_tree(
    metric: str = Query("commits", description="Activity metric: commits or lines"),
    period: str = Query("1y", description="Time window: 1m, 3m, 6m, 1y"),
    db: Session = Depends(get_db),
):
    """Return a tree for activity map: root -> projects -> repositories (value = commit count or lines added)."""
    if metric not in ("commits", "lines"):
        raise HTTPException(400, "metric must be commits or lines")
    if period not in ("1m", "3m", "6m", "1y"):
        raise HTTPException(400, "period must be 1m, 3m, 6m or 1y")

    projects = db.query(Project).order_by(Project.id).all()
    if not projects:
        return TreemapNode(name="root", value=0, type="root", children=[])

    pr_ids: list[int] = []
    for p in projects:
        prs = db.query(ProjectRepository).filter_by(project_id=p.id).all()
        for pr in prs:
            pr_ids.append(pr.id)

    if metric == "commits":
        period_days = {"1m": 30, "3m": 90, "6m": 180, "1y": 365}
        cutoff = date.today() - timedelta(days=period_days[period])
        rows = (
            db.query(
                RepositoryDailyActivity.project_repository_id,
                func.sum(RepositoryDailyActivity.commit_count).label("total"),
            )
            .filter(
                RepositoryDailyActivity.project_repository_id.in_(pr_ids),
                RepositoryDailyActivity.commit_date >= cutoff,
            )
            .group_by(RepositoryDailyActivity.project_repository_id)
            .all()
        )
        pr_activity: dict[int, int] = {r.project_repository_id: r.total or 0 for r in rows if (r.total or 0) > 0}
    else:
        scan_by_pr = _latest_scan_per_pr(db, pr_ids)
        if not scan_by_pr:
            return TreemapNode(name="root", value=0, type="root", children=[])
        scan_ids = {scan.id for scan in scan_by_pr.values()}
        rows = (
            db.query(
                Scan.project_repository_id,
                func.sum(DeveloperContribution.insertions).label("total"),
            )
            .join(DeveloperContribution, DeveloperContribution.scan_id == Scan.id)
            .filter(Scan.id.in_(list(scan_ids)))
            .group_by(Scan.project_repository_id)
            .all()
        )
        pr_activity = {r.project_repository_id: r.total or 0 for r in rows if (r.total or 0) > 0}

    prs_q = (
        db.query(ProjectRepository.id, ProjectRepository.name, ProjectRepository.project_id)
        .filter(ProjectRepository.id.in_(pr_ids))
        .all()
    )
    proj_repo_nodes: dict[int, list[TreemapNode]] = {p.id: [] for p in projects}
    proj_values: dict[int, int] = {p.id: 0 for p in projects}

    for r in prs_q:
        val = pr_activity.get(r.id, 0)
        if val == 0:
            continue
        proj_repo_nodes[r.project_id].append(
            TreemapNode(name=r.name, value=val, id=r.id, type="repository", children=None)
        )
        proj_values[r.project_id] += val

    root_value = 0
    project_nodes: list[TreemapNode] = []
    for p in projects:
        repo_nodes = proj_repo_nodes[p.id]
        pval = proj_values[p.id]
        if not repo_nodes:
            continue
        root_value += pval
        project_nodes.append(
            TreemapNode(name=p.name, value=pval, id=p.id, type="project", children=repo_nodes)
        )

    return TreemapNode(name="root", value=root_value, type="root", children=project_nodes)


@router.get("/tech-map", response_model=TechMapResponse)
def get_tech_map(
    project_id: int | None = Query(None, description="Optional: limit to one project"),
    db: Session = Depends(get_db),
):
    """Return technology stack summary for all repositories (latest completed scan per repo)."""
    projects = (
        db.query(Project)
        .order_by(Project.id)
        .all()
    )
    if project_id is not None:
        projects = [p for p in projects if p.id == project_id]
        if not projects:
            raise HTTPException(404, "Project not found")

    project_map = {p.id: p.name for p in projects}
    pr_ids = []
    prs_by_id: dict[int, ProjectRepository] = {}

    for p in projects:
        prs = (
            db.query(ProjectRepository)
            .options(joinedload(ProjectRepository.repository))
            .filter_by(project_id=p.id)
            .all()
        )
        for pr in prs:
            pr_ids.append(pr.id)
            prs_by_id[pr.id] = pr

    scan_by_pr = _latest_scan_per_pr(db, pr_ids)

    def _load(col: str | None) -> list[str]:
        if not col:
            return []
        try:
            return json.loads(col)
        except Exception:
            return []

    repo_entries: list[TechMapRepo] = []
    lang_stats: dict[str, dict] = defaultdict(lambda: {"total_loc": 0, "total_files": 0, "repo_count": 0})
    fw_counts: dict[str, int] = defaultdict(int)
    ci_counts: dict[str, int] = defaultdict(int)
    pm_counts: dict[str, int] = defaultdict(int)
    infra_counts: dict[str, int] = defaultdict(int)

    for pr_id, pr in prs_by_id.items():
        scan = scan_by_pr.get(pr_id)
        if scan is None:
            continue

        repo = pr.repository
        frameworks = _load(scan.frameworks_json)
        package_managers = _load(scan.package_managers_json)
        infra_tools = _load(scan.infra_tools_json)
        linters = _load(scan.linters_json)

        repo_languages: list[RepoLanguage] = []
        for sl in sorted(scan.languages, key=lambda s: -(s.loc or 0)):
            lang_name = sl.language.name
            repo_languages.append(RepoLanguage(
                name=lang_name,
                loc=sl.loc or 0,
                file_count=sl.file_count or 0,
                percentage=sl.percentage or 0.0,
            ))
            lang_stats[lang_name]["total_loc"] += sl.loc or 0
            lang_stats[lang_name]["total_files"] += sl.file_count or 0
            lang_stats[lang_name]["repo_count"] += 1

        for f in frameworks:
            fw_counts[f] += 1
        if scan.ci_provider:
            ci_counts[scan.ci_provider] += 1
        for pm in package_managers:
            pm_counts[pm] += 1
        for it in infra_tools:
            infra_counts[it] += 1

        repo_entries.append(TechMapRepo(
            repo_id=pr_id,
            repo_name=pr.name,
            project_id=pr.project_id,
            project_name=project_map.get(pr.project_id, ""),
            primary_language=scan.primary_language,
            project_type=scan.project_type.value if scan.project_type else None,
            languages=repo_languages,
            frameworks=frameworks,
            package_managers=package_managers,
            ci_provider=scan.ci_provider,
            infra_tools=infra_tools,
            linters=linters,
            has_docker=bool(scan.has_docker),
            has_kubernetes=bool(scan.has_kubernetes),
            has_terraform=bool(scan.has_terraform),
        ))

    sorted_langs = dict(
        sorted(lang_stats.items(), key=lambda x: -x[1]["total_loc"])
    )

    return TechMapResponse(
        repos=repo_entries,
        tech_counts=TechCounts(
            languages={k: LanguageStat(**v) for k, v in sorted_langs.items()},
            frameworks=dict(sorted(fw_counts.items(), key=lambda x: -x[1])),
            ci_providers=dict(sorted(ci_counts.items(), key=lambda x: -x[1])),
            package_managers=dict(sorted(pm_counts.items(), key=lambda x: -x[1])),
            infra_tools=dict(sorted(infra_counts.items(), key=lambda x: -x[1])),
        ),
    )


@router.get("/size-history", response_model=SizeHistoryResponse)
def get_size_history(
    metric: str = Query("loc", description="Size metric: loc, files, or bytes"),
    years: int = Query(5, description="Number of years to look back (1, 2, 3, or 5)"),
    project_id: int | None = Query(None, description="Optional: limit to one project"),
    group_by: str = Query("repository", description="Group series by: repository or project"),
    db: Session = Depends(get_db),
):
    """Return monthly codebase size over the requested period, grouped by repo or project."""
    if metric not in ("loc", "files", "bytes"):
        raise HTTPException(400, "metric must be loc, files, or bytes")
    if years not in (1, 2, 3, 5):
        raise HTTPException(400, "years must be 1, 2, 3, or 5")
    if group_by not in ("repository", "project"):
        raise HTTPException(400, "group_by must be repository or project")

    # Generate monthly slots for the requested period
    num_months = years * 12
    today = date.today()
    months: list[str] = []
    month_ends: list[date] = []
    y, m = today.year, today.month
    for _ in range(num_months):
        last_day = monthrange(y, m)[1]
        months.append(f"{y:04d}-{m:02d}")
        month_ends.append(date(y, m, last_day))
        m -= 1
        if m == 0:
            m = 12
            y -= 1
    months.reverse()
    month_ends.reverse()

    # Resolve pr_ids (optionally filtered by project)
    if project_id is not None:
        project = db.query(Project).filter_by(id=project_id).first()
        if not project:
            raise HTTPException(404, "Project not found")
        allowed_prs = db.query(ProjectRepository.id).filter_by(project_id=project_id).all()
        allowed_pr_ids: set[int] | None = {r.id for r in allowed_prs}
    else:
        allowed_pr_ids = None

    # Load all completed scans with their metric values
    q = (
        db.query(
            Scan.id,
            Scan.project_repository_id,
            Scan.created_at,
            Scan.total_loc,
            Scan.total_files,
            Scan.size_bytes,
        )
        .filter(Scan.status == ScanStatus.completed)
    )
    if allowed_pr_ids is not None:
        q = q.filter(Scan.project_repository_id.in_(allowed_pr_ids))
    rows = q.order_by(Scan.project_repository_id, Scan.created_at).all()

    # Group scans by pr
    pr_scans: dict[int, list[tuple[date, int]]] = defaultdict(list)
    for row in rows:
        created = row.created_at.date() if isinstance(row.created_at, datetime) else row.created_at
        if metric == "loc":
            val = row.total_loc or 0
        elif metric == "files":
            val = row.total_files or 0
        else:
            val = row.size_bytes or 0
        pr_scans[row.project_repository_id].append((created, val))

    if not pr_scans:
        return SizeHistoryResponse(months=months, repos=[], totals=[0] * len(months))

    # Load pr metadata (name + project_id)
    pr_ids = list(pr_scans.keys())
    pr_rows = (
        db.query(ProjectRepository.id, ProjectRepository.name, ProjectRepository.project_id)
        .filter(ProjectRepository.id.in_(pr_ids))
        .all()
    )
    pr_meta: dict[int, tuple[str, int]] = {r.id: (r.name, r.project_id) for r in pr_rows}

    # Compute per-pr monthly values
    pr_monthly: dict[int, list[int | None]] = {}
    for pr_id, scans in pr_scans.items():
        values: list[int | None] = []
        for end_date in month_ends:
            val = None
            for scan_date, scan_val in reversed(scans):
                if scan_date <= end_date:
                    val = scan_val
                    break
            values.append(val)
        pr_monthly[pr_id] = values

    if group_by == "project":
        project_rows = db.query(Project.id, Project.name).all()
        project_names: dict[int, str] = {p.id: p.name for p in project_rows}

        proj_monthly: dict[int, list[int]] = defaultdict(lambda: [0] * len(months))
        for pr_id, values in pr_monthly.items():
            _, proj_id = pr_meta.get(pr_id, ("", 0))
            for i, v in enumerate(values):
                if v is not None:
                    proj_monthly[proj_id][i] += v

        result_repos: list[SizeHistoryRepo] = []
        totals = [0] * len(months)
        for proj_id, values in sorted(proj_monthly.items()):
            for i, v in enumerate(values):
                totals[i] += v
            result_repos.append(SizeHistoryRepo(
                id=proj_id,
                name=project_names.get(proj_id, str(proj_id)),
                values=[v if v > 0 else None for v in values],
            ))
    else:
        result_repos = []
        totals = [0] * len(months)
        for pr_id in sorted(pr_monthly.keys()):
            values = pr_monthly[pr_id]
            for i, v in enumerate(values):
                if v is not None:
                    totals[i] += v
            pr_name, _ = pr_meta.get(pr_id, (str(pr_id), 0))
            result_repos.append(SizeHistoryRepo(
                id=pr_id,
                name=pr_name,
                values=values,
            ))

    return SizeHistoryResponse(months=months, repos=result_repos, totals=totals)

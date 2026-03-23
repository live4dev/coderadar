"""Analytics API: treemap tree and similar."""
import json
from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.db.session import get_db
from app.models import Project, Repository, Scan, ScanStatus
from app.models.contribution import DeveloperModuleContribution
from app.models.module import Module
from app.models.scan_language import ScanLanguage
from app.schemas.analytics import TreemapNode, TechMapRepo, TechCounts, TechMapResponse, RepoLanguage, LanguageStat

router = APIRouter(prefix="/analytics", tags=["analytics"])


def _latest_scan_per_repo(db: Session, repo_ids: list[int]) -> dict[int, Scan]:
    """Return repo_id -> latest completed scan (with languages eager-loaded)."""
    if not repo_ids:
        return {}
    latest = (
        db.query(Scan)
        .options(
            joinedload(Scan.languages).joinedload(ScanLanguage.language)
        )
        .filter(
            Scan.repository_id.in_(repo_ids),
            Scan.status == ScanStatus.completed,
        )
        .order_by(Scan.started_at.desc(), Scan.id.desc())
        .all()
    )
    scan_by_repo = {}
    for s in latest:
        if s.repository_id not in scan_by_repo:
            scan_by_repo[s.repository_id] = s
    return scan_by_repo


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

    repo_ids = []
    repo_to_project: dict[int, int] = {}
    for p in projects:
        repos = (
            db.query(Repository)
            .filter_by(project_id=p.id)
            .all()
        )
        for r in repos:
            repo_ids.append(r.id)
            repo_to_project[r.id] = p.id

    scan_by_repo = _latest_scan_per_repo(db, repo_ids)

    # project_id -> list of (repo_name, repo_id, value)
    proj_children: dict[int, list[tuple[str, int, int]]] = {p.id: [] for p in projects}
    proj_value: dict[int, int] = {p.id: 0 for p in projects}

    repos = (
        db.query(Repository.id, Repository.name, Repository.project_id)
        .filter(Repository.id.in_(repo_ids))
        .all()
    )
    for r in repos:
        scan = scan_by_repo.get(r.id)
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
    db: Session = Depends(get_db),
):
    """Return a tree for activity map: root -> projects -> repositories -> modules (value = commit count or loc added)."""
    if metric not in ("commits", "lines"):
        raise HTTPException(400, "metric must be commits or lines")

    projects = db.query(Project).order_by(Project.id).all()
    if not projects:
        return TreemapNode(name="root", value=0, type="root", children=[])

    repo_ids: list[int] = []
    repo_to_project: dict[int, int] = {}
    for p in projects:
        repos = db.query(Repository).filter_by(project_id=p.id).all()
        for r in repos:
            repo_ids.append(r.id)
            repo_to_project[r.id] = p.id

    scan_by_repo = _latest_scan_per_repo(db, repo_ids)
    if not scan_by_repo:
        return TreemapNode(name="root", value=0, type="root", children=[])

    scan_ids = {scan.id for scan in scan_by_repo.values()}

    rows = (
        db.query(
            Module.id,
            Module.name,
            Module.repository_id,
            func.sum(DeveloperModuleContribution.commit_count).label("total_commits"),
            func.sum(DeveloperModuleContribution.loc_added).label("total_loc"),
        )
        .join(DeveloperModuleContribution, DeveloperModuleContribution.module_id == Module.id)
        .filter(DeveloperModuleContribution.scan_id.in_(list(scan_ids)))
        .group_by(Module.id, Module.name, Module.repository_id)
        .all()
    )

    repo_modules: dict[int, list[tuple]] = defaultdict(list)
    for r in rows:
        val = (r.total_commits if metric == "commits" else r.total_loc) or 0
        if val > 0:
            repo_modules[r.repository_id].append((r.name, r.id, val))

    repos_q = (
        db.query(Repository.id, Repository.name, Repository.project_id)
        .filter(Repository.id.in_(repo_ids))
        .all()
    )
    proj_repo_nodes: dict[int, list[TreemapNode]] = {p.id: [] for p in projects}
    proj_values: dict[int, int] = {p.id: 0 for p in projects}

    for r in repos_q:
        mod_tuples = repo_modules.get(r.id, [])
        if not mod_tuples:
            continue
        module_nodes = [
            TreemapNode(name=name, value=val, id=mid, type="module", children=None)
            for name, mid, val in mod_tuples
        ]
        repo_val = sum(val for _, _, val in mod_tuples)
        proj_repo_nodes[r.project_id].append(
            TreemapNode(name=r.name, value=repo_val, id=r.id, type="repository", children=module_nodes)
        )
        proj_values[r.project_id] += repo_val

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
    repo_ids = []
    repos_by_id: dict[int, Repository] = {}

    for p in projects:
        repos = db.query(Repository).filter_by(project_id=p.id).all()
        for r in repos:
            repo_ids.append(r.id)
            repos_by_id[r.id] = r

    scan_by_repo = _latest_scan_per_repo(db, repo_ids)

    def _load(col: str | None) -> list[str]:
        if not col:
            return []
        try:
            return json.loads(col)
        except Exception:
            return []

    repo_entries: list[TechMapRepo] = []
    # language name -> accumulated stats across all repos
    lang_stats: dict[str, dict] = defaultdict(lambda: {"total_loc": 0, "total_files": 0, "repo_count": 0})
    fw_counts: dict[str, int] = defaultdict(int)
    ci_counts: dict[str, int] = defaultdict(int)
    pm_counts: dict[str, int] = defaultdict(int)
    infra_counts: dict[str, int] = defaultdict(int)

    for rid, repo in repos_by_id.items():
        scan = scan_by_repo.get(rid)
        if scan is None:
            continue

        frameworks = _load(scan.frameworks_json)
        package_managers = _load(scan.package_managers_json)
        infra_tools = _load(scan.infra_tools_json)
        linters = _load(scan.linters_json)

        # Accumulate per-language LOC and files from ScanLanguage records
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
            repo_id=rid,
            repo_name=repo.name,
            project_id=repo.project_id,
            project_name=project_map.get(repo.project_id, ""),
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

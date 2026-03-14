"""Analytics API: treemap tree and similar."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.db.session import get_db
from app.models import (
    Project,
    Repository,
    Scan,
    ScanStatus,
    ScanLanguage,
    DeveloperContribution,
)
from app.schemas.analytics import TreemapNode

router = APIRouter(prefix="/analytics", tags=["analytics"])


def _latest_scan_per_repo(db: Session, repo_ids: list[int]) -> dict[int, Scan]:
    """Return repo_id -> latest completed scan."""
    if not repo_ids:
        return {}
    latest = (
        db.query(Scan)
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
    """Return a tree for treemap: root -> projects -> repositories (and optionally -> languages)."""
    if group_by not in ("projects_repos", "projects_repos_languages"):
        raise HTTPException(400, "group_by must be projects_repos or projects_repos_languages")
    if group_by == "projects_repos_languages" and metric not in ("loc", "files"):
        raise HTTPException(400, "For group_by=projects_repos_languages only metric=loc or files is supported")
    if group_by == "projects_repos" and metric not in ("loc", "files", "commits", "developers"):
        raise HTTPException(400, "metric must be loc, files, commits, or developers")

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
    repo_id_to_name: dict[int, str] = {}
    for p in projects:
        repos = (
            db.query(Repository)
            .filter_by(project_id=p.id)
            .all()
        )
        for r in repos:
            repo_ids.append(r.id)
            repo_to_project[r.id] = p.id
            repo_id_to_name[r.id] = r.name

    scan_by_repo = _latest_scan_per_repo(db, repo_ids)
    scan_ids = [s.id for s in scan_by_repo.values()]
    scan_id_to_repo: dict[int, int] = {s.id: rid for rid, s in scan_by_repo.items()}

    if group_by == "projects_repos_languages":
        # repo_id -> list of (language_name, loc, file_count)
        repo_languages: dict[int, list[tuple[str, int, int]]] = {}
        if scan_ids:
            lang_rows = (
                db.query(ScanLanguage)
                .options(joinedload(ScanLanguage.language))
                .filter(ScanLanguage.scan_id.in_(scan_ids))
                .all()
            )
            for row in lang_rows:
                rid = scan_id_to_repo.get(row.scan_id)
                if rid is None:
                    continue
                lang_name = row.language.name if row.language else ""
                loc = row.loc or 0
                fc = row.file_count or 0
                repo_languages.setdefault(rid, []).append((lang_name, loc, fc))
        use_loc = metric == "loc"
        root_val = 0
        project_nodes_list: list[TreemapNode] = []
        for p in projects:
            repo_nodes_list: list[TreemapNode] = []
            pval = 0
            for rid in repo_ids:
                if repo_to_project.get(rid) != p.id:
                    continue
                lang_tuples = repo_languages.get(rid, [])
                lang_children = [
                    TreemapNode(
                        name=lang_name,
                        value=loc if use_loc else fc,
                        type="language",
                        children=None,
                    )
                    for lang_name, loc, fc in lang_tuples
                ]
                repo_val = sum(n.value for n in lang_children)
                if not lang_children:
                    continue
                repo_nodes_list.append(
                    TreemapNode(
                        name=repo_id_to_name.get(rid, ""),
                        value=repo_val,
                        id=rid,
                        type="repository",
                        children=lang_children,
                    )
                )
                pval += repo_val
            if repo_nodes_list:
                project_nodes_list.append(
                    TreemapNode(
                        name=p.name,
                        value=pval,
                        id=p.id,
                        type="project",
                        children=repo_nodes_list,
                    )
                )
                root_val += pval
        return TreemapNode(
            name="root",
            value=root_val,
            type="root",
            children=project_nodes_list,
        )

    # For commits/developers: scan_id -> value
    scan_commits: dict[int, int] = {}
    scan_developers: dict[int, int] = {}
    if scan_ids and metric in ("commits", "developers"):
        if metric == "commits":
            rows = (
                db.query(DeveloperContribution.scan_id, func.coalesce(func.sum(DeveloperContribution.commit_count), 0).label("total"))
                .filter(DeveloperContribution.scan_id.in_(scan_ids))
                .group_by(DeveloperContribution.scan_id)
                .all()
            )
            scan_commits = {r.scan_id: int(r.total) for r in rows}
        else:
            rows = (
                db.query(DeveloperContribution.scan_id, func.count(DeveloperContribution.profile_id).label("cnt"))
                .filter(DeveloperContribution.scan_id.in_(scan_ids))
                .group_by(DeveloperContribution.scan_id)
                .all()
            )
            scan_developers = {r.scan_id: int(r.cnt) for r in rows}

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
        if metric == "loc":
            val = scan.total_loc or 0
        elif metric == "files":
            val = scan.total_files or 0
        elif metric == "commits":
            val = scan_commits.get(scan.id, 0)
        else:
            val = scan_developers.get(scan.id, 0)
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

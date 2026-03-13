"""Analytics API: treemap tree and similar."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload

from app.db.session import get_db
from app.models import Project, Repository, Scan, ScanStatus
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

"""Tech radar computation: aggregates scan data into Adopt/Trial/Assess/Hold blips."""
from __future__ import annotations
import json
from collections import defaultdict
from datetime import datetime

from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.models import Project, ProjectRepository, Scan, ScanStatus
from app.models.scan_language import ScanLanguage
from app.models.scan_score import ScanScore, ScoreDomain
from app.models.dependency import Dependency
from app.models.tech_radar_override import TechRadarOverride
from app.schemas.tech_radar import TechRadarBlip, TechRadarResponse

RING_ORDER = {"adopt": 0, "trial": 1, "assess": 2, "hold": 3}

_CI_LABELS = {
    "gitlab": "GitLab CI",
    "bitbucket": "Bitbucket Pipelines",
    "github_actions": "GitHub Actions",
    "jenkins": "Jenkins",
    "circleci": "CircleCI",
}


def _latest_scan_per_pr(db: Session, pr_ids: list[int]) -> dict[int, Scan]:
    if not pr_ids:
        return {}
    rows = (
        db.query(Scan)
        .options(joinedload(Scan.languages).joinedload(ScanLanguage.language))
        .filter(
            Scan.project_repository_id.in_(pr_ids),
            Scan.status == ScanStatus.completed,
        )
        .order_by(Scan.started_at.desc(), Scan.id.desc())
        .all()
    )
    seen: dict[int, Scan] = {}
    for s in rows:
        if s.project_repository_id not in seen:
            seen[s.project_repository_id] = s
    return seen


def _load_json(col: str | None) -> list[str]:
    if not col:
        return []
    try:
        return json.loads(col)
    except Exception:
        return []


def compute_tech_radar(db: Session, project_id: int | None = None) -> TechRadarResponse:
    projects = db.query(Project).order_by(Project.id).all()
    if project_id is not None:
        projects = [p for p in projects if p.id == project_id]

    pr_ids: list[int] = []
    for p in projects:
        prs = db.query(ProjectRepository).filter_by(project_id=p.id).all()
        pr_ids.extend(pr.id for pr in prs)

    scan_by_pr = _latest_scan_per_pr(db, pr_ids)
    total_repos = len(scan_by_pr)

    if total_repos == 0:
        return TechRadarResponse(
            blips=[],
            total_repos=0,
            generated_at=datetime.utcnow(),
            project_id=project_id,
        )

    scan_ids = [s.id for s in scan_by_pr.values()]

    # Overall quality scores keyed by scan_id
    score_by_scan: dict[int, float] = {
        r.scan_id: r.score
        for r in db.query(ScanScore)
        .filter(
            ScanScore.scan_id.in_(scan_ids),
            ScanScore.domain == ScoreDomain.overall,
        )
        .all()
    }

    # Aggregate tech presence: tech_name → set of scan_ids that use it
    lang_scans: dict[str, set[int]] = defaultdict(set)
    fw_scans: dict[str, set[int]] = defaultdict(set)
    infra_scans: dict[str, set[int]] = defaultdict(set)

    for scan in scan_by_pr.values():
        sid = scan.id
        for sl in scan.languages:
            lang_scans[sl.language.name].add(sid)
        for fw in _load_json(scan.frameworks_json):
            fw_scans[fw].add(sid)
        if scan.has_docker:
            infra_scans["Docker"].add(sid)
        if scan.has_kubernetes:
            infra_scans["Kubernetes"].add(sid)
        if scan.has_terraform:
            infra_scans["Terraform"].add(sid)
        if scan.ci_provider:
            infra_scans[_CI_LABELS.get(scan.ci_provider, scan.ci_provider)].add(sid)
        for it in _load_json(scan.infra_tools_json):
            infra_scans[it].add(sid)
        for pm in _load_json(scan.package_managers_json):
            infra_scans[pm].add(sid)

    # Top 50 direct non-private dependencies by repo count
    dep_rows = (
        db.query(
            Dependency.name,
            Dependency.ecosystem,
            func.count(Dependency.scan_id.distinct()).label("repo_count"),
        )
        .filter(
            Dependency.scan_id.in_(scan_ids),
            Dependency.is_direct == True,
            Dependency.is_private == False,
        )
        .group_by(Dependency.name, Dependency.ecosystem)
        .order_by(func.count(Dependency.scan_id.distinct()).desc())
        .limit(50)
        .all()
    )

    dep_names = [r.name for r in dep_rows]
    high_risk_names: set[str] = set()
    if dep_names:
        high_risk_names = {
            row[0]
            for row in db.query(Dependency.name)
            .filter(
                Dependency.scan_id.in_(scan_ids),
                Dependency.name.in_(dep_names),
                Dependency.license_risk == "high",
            )
            .distinct()
            .all()
        }

    # Load manual overrides (global ones, plus project-scoped if project_id given)
    override_q = db.query(TechRadarOverride)
    if project_id is not None:
        override_q = override_q.filter(
            (TechRadarOverride.project_id == project_id)
            | (TechRadarOverride.project_id.is_(None))
        )
    else:
        override_q = override_q.filter(TechRadarOverride.project_id.is_(None))
    overrides: dict[tuple[str, str], TechRadarOverride] = {
        (o.tech_name, o.quadrant): o for o in override_q.all()
    }

    def _avg_quality(sids: set[int]) -> float | None:
        scores = [score_by_scan[s] for s in sids if s in score_by_scan]
        return sum(scores) / len(scores) if scores else None

    def _auto_ring(repo_count: int, quality: float | None, is_high_risk: bool = False) -> str:
        if is_high_risk:
            return "hold"
        pct = repo_count / total_repos
        if repo_count >= 10 or pct >= 0.25:
            ring = "adopt"
        elif repo_count >= 2 or pct >= 0.05:
            ring = "trial"
        else:
            ring = "assess"
        # Demote one ring if quality is poor
        if quality is not None and quality < 35:
            ring = {"adopt": "trial", "trial": "assess"}.get(ring, ring)
        return ring

    def _make_blip(name: str, quadrant: str, sids: set[int], license_risk: str | None = None) -> TechRadarBlip:
        rc = len(sids)
        quality = _avg_quality(sids)
        computed = _auto_ring(rc, quality, is_high_risk=(license_risk == "high"))
        ov = overrides.get((name, quadrant))
        return TechRadarBlip(
            name=name,
            quadrant=quadrant,
            ring=ov.ring if ov else computed,
            auto_ring=computed,
            is_overridden=ov is not None,
            repo_count=rc,
            quality_signal=round(quality, 1) if quality is not None else None,
            license_risk=license_risk,
            notes=ov.notes if ov else None,
        )

    blips: list[TechRadarBlip] = []

    for name, sids in sorted(lang_scans.items(), key=lambda x: -len(x[1])):
        blips.append(_make_blip(name, "languages", sids))

    for name, sids in sorted(fw_scans.items(), key=lambda x: -len(x[1])):
        blips.append(_make_blip(name, "frameworks", sids))

    for name, sids in sorted(infra_scans.items(), key=lambda x: -len(x[1])):
        blips.append(_make_blip(name, "infrastructure", sids))

    for row in dep_rows:
        lr = "high" if row.name in high_risk_names else None
        computed = _auto_ring(row.repo_count, None, is_high_risk=(lr == "high"))
        ov = overrides.get((row.name, "dependencies"))
        blips.append(TechRadarBlip(
            name=row.name,
            quadrant="dependencies",
            ring=ov.ring if ov else computed,
            auto_ring=computed,
            is_overridden=ov is not None,
            repo_count=row.repo_count,
            quality_signal=None,
            license_risk=lr,
            notes=ov.notes if ov else None,
        ))

    blips.sort(key=lambda b: (RING_ORDER.get(b.ring, 4), b.quadrant, -b.repo_count))
    return TechRadarResponse(
        blips=blips,
        total_repos=total_repos,
        generated_at=datetime.utcnow(),
        project_id=project_id,
    )

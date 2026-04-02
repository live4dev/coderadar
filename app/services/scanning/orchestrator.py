from __future__ import annotations
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.models import (
    Scan, ScanStatus, Repository, ProjectRepository, Developer, DeveloperProfile, DeveloperIdentity,
    Language, ScanLanguage, Module, Dependency,
    DeveloperContribution, DeveloperLanguageContribution, DeveloperModuleContribution,
    DeveloperDailyActivity, RepositoryDailyActivity,
    ScanScore, ScanRisk, ScanPersonalDataFinding, IdentityOverride, RepositoryGitTag,
)
from app.services.pii import load_pdn_config, scan_repository_for_pdn
from app.services.vcs.workspace import RepoWorkspaceManager
from app.services.analysis.file_analyzer import analyze_files
from app.services.analysis.stack_detector import detect_stack
from app.services.analysis.dependency_parser import parse_all as parse_deps
from app.services.analysis.license_scanner import scan_licenses
from app.services.analysis.complexity import analyze_complexity
from app.services.git_analytics.contributor_aggregator import aggregate_contributions
from app.services.git_analytics.git_parser import parse_git_tags
from app.services.scoring.engine import compute_scorecard
from app.services.risks.engine import detect_risks

logger = get_logger(__name__)
workspace = RepoWorkspaceManager()


class ScanCancelledError(Exception):
    pass


def _check_cancelled(scan: Scan, db: Session) -> None:
    """Refresh scan from DB and raise ScanCancelledError if cancellation was requested."""
    db.refresh(scan)
    if scan.cancel_requested:
        raise ScanCancelledError("Scan cancelled by user")


def run_scan(scan_id: int, db: Session) -> None:
    """
    Main scan pipeline. Runs synchronously.
    All errors are caught per-stage; fatal errors set status=failed.
    """
    scan: Scan | None = db.get(Scan, scan_id)
    if not scan:
        logger.error("scan_not_found", scan_id=scan_id)
        return

    pr: ProjectRepository = scan.project_repository
    repo: Repository = pr.repository

    scan.status = ScanStatus.running
    scan.started_at = datetime.now(timezone.utc)
    db.commit()
    logger.info("scan_started", scan_id=scan_id, repo=repo.url)

    try:
        # ── Stage 1: prepare repo ──────────────────────────────────────────
        branch_arg = scan.branch or None  # empty string means "use remote default"
        clone_result = workspace.prepare(
            repository_id=repo.id,
            repo_url=repo.url,
            provider_type=repo.provider_type.value,
            project_name=pr.project.name,
            repo_name=pr.name,
            branch=branch_arg,
            credentials_username=pr.credentials_username or "",
            credentials_token=pr.credentials_token or "",
        )
        repo_path = clone_result.local_path
        scan.commit_sha = clone_result.commit_sha
        repo.clone_path = str(repo_path)
        repo.last_commit_sha = clone_result.commit_sha
        if not scan.branch:
            scan.branch = clone_result.branch
        db.commit()
        logger.info("repo_prepared", commit_sha=scan.commit_sha)
        _check_cancelled(scan, db)

        # ── Stage 2: file analysis ─────────────────────────────────────────
        logger.info("stage_file_analysis")
        file_result = analyze_files(repo_path)
        scan.total_files = file_result.total_files
        scan.total_loc = file_result.total_loc
        scan.size_bytes = file_result.size_bytes
        scan.file_count_source = file_result.file_count_source
        scan.file_count_test = file_result.file_count_test
        scan.file_count_config = file_result.file_count_config
        scan.dir_count = file_result.dir_count
        scan.avg_file_loc = file_result.avg_file_loc
        scan.large_files_count = file_result.large_files_count

        _persist_languages(db, scan, file_result.languages)
        db.commit()
        _check_cancelled(scan, db)

        # ── Stage 3: stack & dependencies ─────────────────────────────────
        logger.info("stage_stack_analysis")
        stack = detect_stack(repo_path, file_result.languages)
        scan.project_type = stack.project_type  # type: ignore[assignment]
        scan.primary_language = stack.primary_language
        import json as _json
        scan.frameworks_json = _json.dumps(stack.frameworks)
        scan.package_managers_json = _json.dumps(stack.package_managers)
        scan.ci_provider = stack.ci_provider
        scan.infra_tools_json = _json.dumps(stack.infra_tools)
        scan.linters_json = _json.dumps(stack.linters + stack.formatters)
        scan.has_docker = stack.has_docker
        scan.has_kubernetes = stack.has_kubernetes
        scan.has_terraform = stack.has_terraform

        deps = parse_deps(repo_path)
        license_map = scan_licenses(repo_path, deps)
        for d in deps:
            lic = license_map.get((d.name, d.ecosystem))
            db.add(Dependency(
                scan_id=scan.id,
                name=d.name,
                version=d.version,
                dep_type=d.dep_type,
                manifest_file=d.manifest_file,
                ecosystem=d.ecosystem,
                package_manager=d.package_manager,
                license_spdx=lic.spdx if lic else None,
                license_raw=lic.raw if lic else None,
                license_risk=lic.risk if lic else "unknown",
                is_direct=lic.is_direct if lic else d.is_direct,
                license_expression=lic.expression if lic else None,
                license_confidence=lic.confidence if lic else "unknown",
                license_source=lic.source if lic else None,
                license_notes=lic.notes if lic else None,
                discovery_mode=d.discovery_mode,
                is_optional_dependency=d.is_optional,
                is_private=d.is_private,
            ))
        db.commit()
        _check_cancelled(scan, db)

        # ── Stage 4: complexity ────────────────────────────────────────────
        logger.info("stage_complexity")
        complexity = analyze_complexity(repo_path, file_result.languages)

        _check_cancelled(scan, db)

        # ── Stage 5: git analytics ─────────────────────────────────────────
        logger.info("stage_git_analytics")
        overrides = _load_overrides(db, pr.project_id)
        dev_stats = aggregate_contributions(repo_path, overrides)

        _persist_developers(db, scan, pr.project_id, pr.id, dev_stats, file_result.languages)

        # Aggregate repo-level daily commits from all developers
        repo_daily: dict[str, int] = defaultdict(int)
        for ds in dev_stats:
            for day_str, count in ds.daily_commits.items():
                repo_daily[day_str] += count
        _persist_repo_daily_activity(db, pr.id, repo_daily)

        db.commit()
        _check_cancelled(scan, db)

        # ── Stage 5b: git tags ─────────────────────────────────────────────
        logger.info("stage_git_tags")
        try:
            _persist_git_tags(db, repo, repo_path)
            db.commit()
        except Exception as tags_exc:
            logger.warning("git_tags_failed", scan_id=scan_id, error=str(tags_exc))
            db.rollback()

        # ── Stage 6: scoring & risks ───────────────────────────────────────
        logger.info("stage_scoring")
        scorecard = compute_scorecard(file_result, stack, complexity, dev_stats)
        for domain_score in scorecard.all_domains():
            db.add(ScanScore(
                scan_id=scan.id,
                domain=domain_score.domain,
                score=domain_score.score,
                details=domain_score.details_json(),
            ))

        logger.info("stage_risks")
        latest_commit_date = max(
            (d.last_commit_at for d in dev_stats if d.last_commit_at is not None),
            default=None,
        )
        risks = detect_risks(file_result, stack, complexity, dev_stats, latest_commit_date)
        for r in risks:
            db.add(ScanRisk(
                scan_id=scan.id,
                risk_type=r.risk_type,
                severity=r.severity,
                title=r.title,
                description=r.description,
                entity_type=r.entity_type,
                entity_ref=r.entity_ref,
            ))
        db.commit()
        _check_cancelled(scan, db)

        # ── Stage 6b: personal data (PDn) scan ───────────────────────────────
        logger.info("stage_personal_data")
        try:
            pdn_types = load_pdn_config()
            findings = scan_repository_for_pdn(repo_path, pdn_types)
            for f in findings:
                db.add(ScanPersonalDataFinding(
                    scan_id=scan.id,
                    pdn_type=f.pdn_type,
                    file_path=f.file_path,
                    line_number=f.line_number,
                    matched_identifier=f.matched_identifier,
                ))
            db.commit()
        except Exception as pdn_exc:
            logger.warning("pdn_scan_failed", scan_id=scan_id, error=str(pdn_exc))
            db.rollback()

        # ── Stage 7: complete ──────────────────────────────────────────────
        scan.status = ScanStatus.completed
        scan.completed_at = datetime.now(timezone.utc)
        db.commit()
        logger.info("scan_completed", scan_id=scan_id)

    except ScanCancelledError:
        scan.status = ScanStatus.cancelled
        scan.completed_at = datetime.now(timezone.utc)
        db.commit()
        logger.info("scan_cancelled", scan_id=scan_id)
    except Exception as exc:
        logger.exception("scan_failed", scan_id=scan_id, error=str(exc))
        scan.status = ScanStatus.failed
        scan.error_message = str(exc)
        scan.completed_at = datetime.now(timezone.utc)
        db.commit()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _persist_git_tags(db: Session, repo: Repository, repo_path) -> None:
    from pathlib import Path
    tags = parse_git_tags(Path(repo_path))
    # Upsert: update existing, insert new
    existing = {t.name: t for t in db.query(RepositoryGitTag).filter_by(repository_id=repo.id).all()}
    for tag in tags:
        if tag.name in existing:
            row = existing[tag.name]
            row.sha = tag.sha
            row.message = tag.message
            row.tagger_name = tag.tagger_name
            row.tagger_email = tag.tagger_email
            row.tagged_at = tag.tagged_at
        else:
            db.add(RepositoryGitTag(
                repository_id=repo.id,
                name=tag.name,
                sha=tag.sha,
                message=tag.message,
                tagger_name=tag.tagger_name,
                tagger_email=tag.tagger_email,
                tagged_at=tag.tagged_at,
            ))
    # Remove tags no longer in the repo
    current_names = {t.name for t in tags}
    for name, row in existing.items():
        if name not in current_names:
            db.delete(row)


def _persist_languages(db: Session, scan: Scan, languages: dict) -> None:
    total_loc = sum(s.loc for s in languages.values())
    for name, stat in languages.items():
        lang = db.query(Language).filter_by(name=name).first()
        if not lang:
            lang = Language(name=name)
            db.add(lang)
            db.flush()
        percentage = (stat.loc / total_loc * 100) if total_loc else 0
        db.add(ScanLanguage(
            scan_id=scan.id,
            language_id=lang.id,
            file_count=stat.file_count,
            loc=stat.loc,
            percentage=round(percentage, 2),
        ))


def _load_overrides(db: Session, project_id: int) -> dict[str, str]:
    rows = db.query(IdentityOverride).filter_by(project_id=project_id).all()
    result: dict[str, str] = {}
    for row in rows:
        if row.raw_name:
            result[row.raw_name.strip().lower()] = row.canonical_username
        if row.raw_email:
            result[row.raw_email.strip().lower()] = row.canonical_username
    return result


def _persist_developers(
    db: Session,
    scan: Scan,
    project_id: int,
    pr_id: int,
    dev_stats: list,
    languages: dict,
) -> None:
    # Build language name → id map
    lang_id_map: dict[str, int] = {}
    for name in languages:
        lang = db.query(Language).filter_by(name=name).first()
        if lang:
            lang_id_map[name] = lang.id

    # Ensure modules exist (keyed by project_repository_id)
    module_id_map: dict[str, int] = {}
    existing_modules = db.query(Module).filter_by(project_repository_id=pr_id).all()
    for m in existing_modules:
        module_id_map[m.path] = m.id

    for ds in dev_stats:
        # Find or create profile (by canonical_username globally)
        profile = (
            db.query(DeveloperProfile)
            .filter_by(canonical_username=ds.canonical_username)
            .first()
        )
        if not profile:
            dev = Developer()
            db.add(dev)
            db.flush()
            profile = DeveloperProfile(
                developer_id=dev.id,
                canonical_username=ds.canonical_username,
                display_name=ds.display_name,
                primary_email=ds.primary_email,
            )
            db.add(profile)
            db.flush()

        # Persist raw identities (linked to profile)
        for raw_name, raw_email in ds.raw_identities:
            exists = (
                db.query(DeveloperIdentity)
                .filter_by(profile_id=profile.id, raw_name=raw_name)
                .first()
            )
            if not exists:
                db.add(DeveloperIdentity(
                    profile_id=profile.id,
                    raw_name=raw_name,
                    raw_email=raw_email,
                    confidence_score=ds.identity.confidence,
                    is_ambiguous=ds.identity.is_ambiguous,
                ))

        # Aggregate contribution
        db.add(DeveloperContribution(
            scan_id=scan.id,
            profile_id=profile.id,
            commit_count=ds.commit_count,
            insertions=ds.insertions,
            deletions=ds.deletions,
            files_changed=ds.files_changed,
            active_days=ds.active_days,
            first_commit_at=ds.first_commit_at,
            last_commit_at=ds.last_commit_at,
        ))

        # Daily activity (upsert: take max count for re-scans)
        from datetime import date as _date
        existing_daily = {
            row.commit_date: row
            for row in db.query(DeveloperDailyActivity).filter_by(profile_id=profile.id).all()
        }
        for day_str, count in ds.daily_commits.items():
            commit_date = _date.fromisoformat(day_str)
            if commit_date in existing_daily:
                row = existing_daily[commit_date]
                if count > row.commit_count:
                    row.commit_count = count
            else:
                db.add(DeveloperDailyActivity(
                    profile_id=profile.id,
                    commit_date=commit_date,
                    commit_count=count,
                ))

        # Language contributions
        total_files = sum(v[1] for v in ds.language_stats.values()) or 1
        for lang_name, stats in ds.language_stats.items():
            lang_id = lang_id_map.get(lang_name)
            if not lang_id:
                continue
            db.add(DeveloperLanguageContribution(
                scan_id=scan.id,
                profile_id=profile.id,
                language_id=lang_id,
                commit_count=stats[0],
                files_changed=stats[1],
                loc_added=stats[2],
                loc_deleted=stats[3],
                percentage=round(stats[1] / total_files * 100, 2),
            ))

        # Module contributions
        total_mod_files = sum(v[1] for v in ds.module_stats.values()) or 1
        for mod_path, stats in ds.module_stats.items():
            if mod_path not in module_id_map:
                mod = Module(
                    project_repository_id=pr_id,
                    path=mod_path,
                    name=mod_path.split("/")[-1] or mod_path,
                )
                db.add(mod)
                db.flush()
                module_id_map[mod_path] = mod.id

            db.add(DeveloperModuleContribution(
                scan_id=scan.id,
                profile_id=profile.id,
                module_id=module_id_map[mod_path],
                commit_count=stats[0],
                files_changed=stats[1],
                loc_added=stats[2],
                percentage=round(stats[1] / total_mod_files * 100, 2),
            ))


def _persist_repo_daily_activity(db: Session, pr_id: int, daily_counts: dict[str, int]) -> None:
    from datetime import date as _date
    existing = {
        row.commit_date: row
        for row in db.query(RepositoryDailyActivity).filter_by(project_repository_id=pr_id).all()
    }
    for day_str, count in daily_counts.items():
        commit_date = _date.fromisoformat(day_str)
        if commit_date in existing:
            row = existing[commit_date]
            if count > row.commit_count:
                row.commit_count = count
        else:
            db.add(RepositoryDailyActivity(
                project_repository_id=pr_id,
                commit_date=commit_date,
                commit_count=count,
            ))

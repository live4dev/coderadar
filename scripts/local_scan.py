#!/usr/bin/env python3
"""
Demo mode: scan a local git repository without Bitbucket/GitLab credentials.

Usage:
    python scripts/local_scan.py --path /path/to/repo --project-name "My Project"
"""
import sys
import os
import argparse
from pathlib import Path

# Make app importable
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.db.session import SessionLocal
from app.models import Project, Repository, Scan, ScanStatus, ProviderType
from app.services.scanning.orchestrator import (
    analyze_files, detect_stack, parse_deps, analyze_complexity,
    aggregate_contributions, compute_scorecard, detect_risks,
    _persist_languages, _persist_developers,
)
from app.core.logging import setup_logging, get_logger
from datetime import datetime, timezone

logger = get_logger(__name__)


def main():
    parser = argparse.ArgumentParser(description="Scan a local repository")
    parser.add_argument("--path", required=True, help="Path to local git repository")
    parser.add_argument("--project-name", default="Local Demo", help="Project name")
    parser.add_argument("--branch", default="main", help="Branch name (metadata only)")
    args = parser.parse_args()

    repo_path = Path(args.path).resolve()
    if not (repo_path / ".git").exists():
        print(f"Error: {repo_path} is not a git repository")
        sys.exit(1)

    setup_logging()
    db = SessionLocal()

    try:
        # Create or reuse project
        project = db.query(Project).filter_by(name=args.project_name).first()
        if not project:
            project = Project(name=args.project_name, description="Local demo scan")
            db.add(project)
            db.commit()
            db.refresh(project)

        # Create pseudo-repository record
        repo = db.query(Repository).filter_by(
            project_id=project.id, url=str(repo_path)
        ).first()
        if not repo:
            repo = Repository(
                project_id=project.id,
                name=repo_path.name,
                url=str(repo_path),
                provider_type=ProviderType.bitbucket,  # placeholder
                default_branch=args.branch,
                clone_path=str(repo_path),
            )
            db.add(repo)
            db.commit()
            db.refresh(repo)

        # Create scan record
        scan = Scan(
            repository_id=repo.id,
            branch=args.branch,
            status=ScanStatus.running,
            started_at=datetime.now(timezone.utc),
        )
        db.add(scan)
        db.commit()
        db.refresh(scan)

        print(f"\nScanning: {repo_path}")
        print(f"Scan ID:  {scan.id}\n")

        # Stage 1: file analysis
        print("  [1/5] Analysing files...")
        fr = analyze_files(repo_path)
        scan.total_files = fr.total_files
        scan.total_loc = fr.total_loc
        scan.size_bytes = fr.size_bytes
        scan.file_count_source = fr.file_count_source
        scan.file_count_test = fr.file_count_test
        scan.file_count_config = fr.file_count_config
        scan.dir_count = fr.dir_count
        scan.avg_file_loc = fr.avg_file_loc
        scan.large_files_count = fr.large_files_count
        _persist_languages(db, scan, fr.languages)

        # Stage 2: stack
        print("  [2/5] Detecting stack...")
        stack = detect_stack(repo_path, fr.languages)
        scan.project_type = stack.project_type
        scan.primary_language = stack.primary_language

        from app.models import Dependency
        for d in parse_deps(repo_path):
            db.add(Dependency(
                scan_id=scan.id, name=d.name, version=d.version,
                dep_type=d.dep_type, manifest_file=d.manifest_file, ecosystem=d.ecosystem,
            ))

        # Stage 3: complexity
        cx = analyze_complexity(repo_path, fr.languages)

        # Stage 4: git analytics
        print("  [3/5] Parsing git history...")
        dev_stats = aggregate_contributions(repo_path)
        _persist_developers(db, scan, project.id, dev_stats, fr.languages)

        # Stage 5: scoring & risks
        print("  [4/5] Scoring & risk detection...")
        from app.models import ScanScore, ScanRisk
        scorecard = compute_scorecard(fr, stack, cx, dev_stats)
        for ds in scorecard.all_domains():
            db.add(ScanScore(scan_id=scan.id, domain=ds.domain, score=ds.score, details=ds.details_json()))

        latest_commit_date = max(
            (d.last_commit_at for d in dev_stats if d.last_commit_at is not None),
            default=None,
        )
        risks = detect_risks(fr, stack, cx, dev_stats, latest_commit_date)
        for r in risks:
            db.add(ScanRisk(
                scan_id=scan.id, risk_type=r.risk_type, severity=r.severity,
                title=r.title, description=r.description,
                entity_type=r.entity_type, entity_ref=r.entity_ref,
            ))

        scan.status = ScanStatus.completed
        scan.completed_at = datetime.now(timezone.utc)
        db.commit()

        # Print summary
        print("\n" + "=" * 50)
        print(f"  Scan completed (id={scan.id})")
        print("=" * 50)
        print(f"  Files:        {fr.total_files}")
        print(f"  LOC:          {fr.total_loc:,}")
        print(f"  Project type: {stack.project_type}")
        print(f"  Language:     {stack.primary_language}")
        print(f"  Developers:   {len(dev_stats)}")
        print(f"\n  Scores:")
        for ds in scorecard.all_domains():
            print(f"    {ds.domain:<22} {ds.score:5.1f}/100")
        print(f"\n  Risks ({len(risks)}):")
        for r in risks:
            print(f"    [{r.severity.upper():<8}] {r.title}")
        print()
        print(f"  View results: GET /api/v1/scans/{scan.id}/summary")

    except Exception as e:
        logger.exception("local_scan_failed", error=str(e))
        print(f"\nError: {e}")
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()

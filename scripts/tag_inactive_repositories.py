#!/usr/bin/env python3
"""
Tag repositories as 'inactive' based on their commit history patterns.

DISCLAIMER: The 'inactive' tag is a probabilistic signal derived from commit
history. It does NOT mean the repository is abandoned, deprecated, or no longer
maintained. A repository may be stable and intentionally quiet, in a freeze
period, or only updated during releases. Treat this tag as a starting point
for human review, not as a definitive statement.

Why 'inactive' and not 'abandoned' or 'deprecated':
  - Commit history cannot confirm intent or operational status.
  - Strong labels imply certainty the data cannot support.
  - 'inactive' is accurate (no recent commits observed) and reversible.

Usage:
    python scripts/tag_inactive_repositories.py [options]

Options:
    --project-id INT      Restrict analysis to a specific project
    --threshold FLOAT     Inactivity score cutoff (default: 4.0)
    --min-days INT        Minimum days since last commit required (default: 90)
    --dry-run             Print decisions without writing to the database
    --untag-active        Also remove 'inactive' tag from repos below threshold

Inactivity score formula:
    active_days   = COUNT(DISTINCT commit_date) from RepositoryDailyActivity
    span_days     = (max_commit_date - min_commit_date).days
    avg_interval  = span_days / max(active_days - 1, 1)
    recent_ratio  = commits_last_90d / max(avg_daily_commits * 90, 1)  [clamped 0..1]
    score         = (days_since_last_commit / avg_interval) * (1 - recent_ratio)

Thresholds:
    score < 2                         → active
    2 ≤ score < threshold             → borderline (printed, not tagged)
    score ≥ threshold AND D ≥ min-days → tagged as 'inactive'
"""
import sys
import argparse
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import func
from app.db.session import SessionLocal
from app.models import Repository, RepositoryTag, RepositoryDailyActivity, Project

INACTIVE_TAG = "inactive"
WINDOW_DAYS = 90


def _get_activity_stats(db, repository_id: int):
    """Aggregate commit activity stats from RepositoryDailyActivity."""
    return db.query(
        func.max(RepositoryDailyActivity.commit_date).label("max_date"),
        func.min(RepositoryDailyActivity.commit_date).label("min_date"),
        func.count(RepositoryDailyActivity.commit_date).label("active_days"),
        func.sum(RepositoryDailyActivity.commit_count).label("total_commits"),
    ).filter(RepositoryDailyActivity.repository_id == repository_id).one()


def _get_recent_commits(db, repository_id: int, window_days: int) -> int:
    """Count commits in the last `window_days` from RepositoryDailyActivity."""
    cutoff = date.today() - timedelta(days=window_days)
    result = (
        db.query(func.coalesce(func.sum(RepositoryDailyActivity.commit_count), 0))
        .filter(
            RepositoryDailyActivity.repository_id == repository_id,
            RepositoryDailyActivity.commit_date >= cutoff,
        )
        .scalar()
    )
    return int(result or 0)


def compute_inactivity_score(
    max_date: date,
    min_date: date,
    active_days: int,
    total_commits: int,
    recent_commits: int,
) -> tuple[float, int]:
    """
    Returns (inactivity_score, days_since_last).

    avg_interval  = span_days / max(active_days - 1, 1)
    recent_ratio  = recent_commits / max(avg_daily_commits * WINDOW_DAYS, 1)  [0..1]
    score         = (days_since_last / avg_interval) * (1 - recent_ratio)
    """
    today = date.today()
    days_since_last = (today - max_date).days
    span_days = max((max_date - min_date).days, 0)
    avg_interval = span_days / max(active_days - 1, 1)

    if avg_interval < 1:
        avg_interval = 1.0

    total_span_days = max((today - min_date).days, 1)
    avg_daily = total_commits / total_span_days
    recent_ratio = min(recent_commits / max(avg_daily * WINDOW_DAYS, 1), 1.0)

    score = (days_since_last / avg_interval) * (1.0 - recent_ratio)
    return round(score, 2), days_since_last


def _has_inactive_tag(db, repository_id: int) -> bool:
    return (
        db.query(RepositoryTag)
        .filter_by(repository_id=repository_id, tag=INACTIVE_TAG)
        .first()
    ) is not None


def _add_inactive_tag(db, repository_id: int, last_date: date) -> None:
    if not _has_inactive_tag(db, repository_id):
        description = f"Auto-tagged: no commit activity since {last_date.strftime('%Y-%m-%d')}"
        db.add(RepositoryTag(repository_id=repository_id, tag=INACTIVE_TAG, description=description))


def _remove_inactive_tag(db, repository_id: int) -> None:
    db.query(RepositoryTag).filter_by(
        repository_id=repository_id, tag=INACTIVE_TAG
    ).delete()


def main():
    parser = argparse.ArgumentParser(
        description="Tag repositories as 'inactive' based on commit history patterns."
    )
    parser.add_argument("--project-id", type=int, default=None, help="Restrict to a specific project")
    parser.add_argument("--threshold", type=float, default=4.0, help="Inactivity score cutoff (default: 4.0)")
    parser.add_argument("--min-days", type=int, default=90, help="Minimum days since last commit (default: 90)")
    parser.add_argument("--dry-run", action="store_true", help="Print decisions without writing to DB")
    parser.add_argument("--untag-active", action="store_true", help="Remove 'inactive' tag from active repositories")
    args = parser.parse_args()

    print()
    print("=" * 70)
    print("  CodeRadar — Inactive Repository Tagger")
    print("=" * 70)
    print()
    print("  DISCLAIMER: The 'inactive' tag is a probabilistic signal based on")
    print("  commit history only. A repository may be stable, in a freeze period,")
    print("  or intentionally quiet. Use this tag for review, not action.")
    print()
    print(f"  Threshold : score >= {args.threshold} AND days_since_last >= {args.min_days}")
    print(f"  Project   : {args.project_id or 'all'}")
    print(f"  Dry run   : {'yes' if args.dry_run else 'no'}")
    print(f"  Untag active: {'yes' if args.untag_active else 'no'}")
    print()
    print(f"  {'STATUS':<14} {'REPOSITORY':<30} {'SCORE':>7}  {'DAYS':>6}  {'LAST COMMIT'}")
    print("  " + "-" * 68)

    db = SessionLocal()
    tagged = 0
    untagged = 0
    skipped = 0

    try:
        q = db.query(Repository)
        if args.project_id is not None:
            q = q.filter(Repository.project_id == args.project_id)
        repositories = q.all()

        for repo in repositories:
            stats = _get_activity_stats(db, repo.id)

            if stats.max_date is None or stats.total_commits == 0:
                skipped += 1
                continue

            recent_commits = _get_recent_commits(db, repo.id, WINDOW_DAYS)

            score, days_since = compute_inactivity_score(
                max_date=stats.max_date,
                min_date=stats.min_date,
                active_days=int(stats.active_days or 1),
                total_commits=int(stats.total_commits),
                recent_commits=recent_commits,
            )

            last_str = stats.max_date.strftime("%Y-%m-%d")
            should_tag = score >= args.threshold and days_since >= args.min_days

            if should_tag:
                status = "[DRY-RUN]" if args.dry_run else "[INACTIVE]"
                print(f"  {status:<14} {repo.name:<30} {score:>7.2f}  {days_since:>6}d  {last_str}")
                if not args.dry_run:
                    _add_inactive_tag(db, repo.id, stats.max_date)
                tagged += 1
            else:
                already_tagged = _has_inactive_tag(db, repo.id)
                if args.untag_active and already_tagged:
                    status = "[DRY-UNTAG]" if args.dry_run else "[UNTAGGED]"
                    print(f"  {status:<14} {repo.name:<30} {score:>7.2f}  {days_since:>6}d  {last_str}")
                    if not args.dry_run:
                        _remove_inactive_tag(db, repo.id)
                    untagged += 1
                else:
                    if score >= 2.0:
                        print(f"  {'[BORDERLINE]':<14} {repo.name:<30} {score:>7.2f}  {days_since:>6}d  {last_str}")
                    skipped += 1

        if not args.dry_run:
            db.commit()

        print()
        print("  " + "-" * 68)
        print(f"  Tagged   : {tagged}")
        print(f"  Untagged : {untagged}")
        print(f"  Skipped  : {skipped}")
        if args.dry_run:
            print()
            print("  [DRY RUN] No changes written to the database.")
        print()

    except Exception as e:
        db.rollback()
        print(f"\nError: {e}", file=sys.stderr)
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()

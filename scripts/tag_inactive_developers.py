#!/usr/bin/env python3
"""
Tag developers as 'inactive' based on their commit history patterns.

DISCLAIMER: The 'inactive' tag is a probabilistic signal derived from commit
history. It does NOT indicate that a developer has left the company, been
terminated, or offboarded. A developer may be on leave, have moved into a
management role, changed projects, or contribute to repositories not tracked
in this system. Treat this tag as a starting point for human review, not as
a definitive statement.

Why 'inactive' and not 'terminated' or 'offboarded':
  - Commit history cannot confirm employment status.
  - Strong labels imply certainty the data cannot support.
  - 'inactive' is accurate (no recent commits observed) and reversible.

Usage:
    python scripts/tag_inactive_developers.py [options]

Options:
    --project-id INT      Restrict analysis to a specific project
    --threshold FLOAT     Inactivity score cutoff (default: 4.0)
    --min-days INT        Minimum days since last commit required (default: 30)
    --dry-run             Print decisions without writing to the database
    --untag-active        Also remove 'inactive' tag from developers below threshold

Inactivity score formula:
    avg_interval  = (last_commit_at - first_commit_at).days / max(active_days - 1, 1)
    recent_ratio  = recent_90d_commits / max(avg_daily_commits * 90, 1)  [clamped 0..1]
    score         = (days_since_last / avg_interval) * (1 - recent_ratio)

Thresholds:
    score < 2                      → active
    2 ≤ score < threshold          → possibly inactive (not tagged)
    score ≥ threshold AND D ≥ min-days → tagged as 'inactive'
"""
import sys
import argparse
from datetime import date, datetime, timezone, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import func
from app.db.session import SessionLocal
from app.models import (
    Developer, DeveloperProfile, DeveloperContribution,
    DeveloperTag, DeveloperDailyActivity, Repository, Scan,
)

INACTIVE_TAG = "inactive"
WINDOW_DAYS = 90


def _get_profile_ids(db, developer_id: int) -> list[int]:
    return [
        r[0]
        for r in db.query(DeveloperProfile.id)
        .filter(DeveloperProfile.developer_id == developer_id)
        .all()
    ]


def _get_contribution_stats(db, profile_ids: list[int], project_id: int | None):
    """Aggregate first/last commit dates and active_days across profiles, optionally per project."""
    q = db.query(
        func.min(DeveloperContribution.first_commit_at).label("first_commit_at"),
        func.max(DeveloperContribution.last_commit_at).label("last_commit_at"),
        func.sum(DeveloperContribution.active_days).label("active_days"),
        func.sum(DeveloperContribution.commit_count).label("commit_count"),
    ).filter(DeveloperContribution.profile_id.in_(profile_ids))

    if project_id is not None:
        q = (
            q.join(Scan, DeveloperContribution.scan_id == Scan.id)
            .join(Repository, Scan.repository_id == Repository.id)
            .filter(Repository.project_id == project_id)
        )

    return q.one()


def _get_recent_commits(db, profile_ids: list[int], window_days: int) -> int:
    """Count commits in the last `window_days` from DeveloperDailyActivity."""
    cutoff = date.today() - timedelta(days=window_days)
    result = (
        db.query(func.coalesce(func.sum(DeveloperDailyActivity.commit_count), 0))
        .filter(
            DeveloperDailyActivity.profile_id.in_(profile_ids),
            DeveloperDailyActivity.commit_date >= cutoff,
        )
        .scalar()
    )
    return int(result or 0)


def compute_inactivity_score(
    first_commit_at: datetime,
    last_commit_at: datetime,
    active_days: int,
    commit_count: int,
    recent_commits: int,
) -> tuple[float, int]:
    """
    Returns (inactivity_score, days_since_last).

    avg_interval  = span_days / max(active_days - 1, 1)
    recent_ratio  = recent_commits / max(avg_daily_commits * WINDOW_DAYS, 1)  [0..1]
    score         = (days_since_last / avg_interval) * (1 - recent_ratio)
    """
    now = datetime.now(timezone.utc)
    last = last_commit_at if last_commit_at.tzinfo else last_commit_at.replace(tzinfo=timezone.utc)
    first = first_commit_at if first_commit_at.tzinfo else first_commit_at.replace(tzinfo=timezone.utc)

    days_since_last = (now - last).days
    span_days = max((last - first).days, 0)
    avg_interval = span_days / max(active_days - 1, 1)

    # Avoid division by zero for brand-new or single-commit developers
    if avg_interval < 1:
        avg_interval = 1.0

    total_days = max((now - first).days, 1)
    avg_daily = commit_count / total_days
    recent_ratio = min(recent_commits / max(avg_daily * WINDOW_DAYS, 1), 1.0)

    score = (days_since_last / avg_interval) * (1.0 - recent_ratio)
    return round(score, 2), days_since_last


def _has_inactive_tag(db, developer_id: int) -> bool:
    return (
        db.query(DeveloperTag)
        .filter_by(developer_id=developer_id, tag=INACTIVE_TAG)
        .first()
    ) is not None


def _add_inactive_tag(db, developer_id: int) -> None:
    if not _has_inactive_tag(db, developer_id):
        db.add(DeveloperTag(developer_id=developer_id, tag=INACTIVE_TAG))


def _remove_inactive_tag(db, developer_id: int) -> None:
    db.query(DeveloperTag).filter_by(
        developer_id=developer_id, tag=INACTIVE_TAG
    ).delete()


def _primary_username(developer: Developer) -> str:
    if developer.profiles:
        p = developer.profiles[0]
        return p.display_name or p.canonical_username
    return f"developer#{developer.id}"


def main():
    parser = argparse.ArgumentParser(
        description="Tag developers as 'inactive' based on commit history patterns."
    )
    parser.add_argument("--project-id", type=int, default=None, help="Restrict to a specific project")
    parser.add_argument("--threshold", type=float, default=4.0, help="Inactivity score cutoff (default: 4.0)")
    parser.add_argument("--min-days", type=int, default=30, help="Minimum days since last commit (default: 30)")
    parser.add_argument("--dry-run", action="store_true", help="Print decisions without writing to DB")
    parser.add_argument("--untag-active", action="store_true", help="Remove 'inactive' tag from active developers")
    args = parser.parse_args()

    print()
    print("=" * 70)
    print("  CodeRadar — Inactive Developer Tagger")
    print("=" * 70)
    print()
    print("  DISCLAIMER: The 'inactive' tag is a probabilistic signal based on")
    print("  commit history only. It does NOT confirm employment status. A")
    print("  developer may be on leave, in a non-coding role, or contributing")
    print("  outside tracked repositories. Use this tag for review, not action.")
    print()
    print(f"  Threshold : score >= {args.threshold} AND days_since_last >= {args.min_days}")
    print(f"  Project   : {args.project_id or 'all'}")
    print(f"  Dry run   : {'yes' if args.dry_run else 'no'}")
    print(f"  Untag active: {'yes' if args.untag_active else 'no'}")
    print()
    print(f"  {'STATUS':<12} {'DEVELOPER':<30} {'SCORE':>7}  {'DAYS':>6}  {'LAST COMMIT'}")
    print("  " + "-" * 68)

    db = SessionLocal()
    tagged = 0
    untagged = 0
    skipped = 0

    try:
        developers = (
            db.query(Developer)
            .join(DeveloperProfile, DeveloperProfile.developer_id == Developer.id)
            .distinct()
            .all()
        )

        for dev in developers:
            profile_ids = _get_profile_ids(db, dev.id)
            if not profile_ids:
                continue

            stats = _get_contribution_stats(db, profile_ids, args.project_id)

            if stats.last_commit_at is None or stats.first_commit_at is None or stats.commit_count == 0:
                skipped += 1
                continue

            recent_commits = _get_recent_commits(db, profile_ids, WINDOW_DAYS)

            score, days_since = compute_inactivity_score(
                first_commit_at=stats.first_commit_at,
                last_commit_at=stats.last_commit_at,
                active_days=int(stats.active_days or 1),
                commit_count=int(stats.commit_count),
                recent_commits=recent_commits,
            )

            name = _primary_username(dev)
            last_str = stats.last_commit_at.strftime("%Y-%m-%d")
            should_tag = score >= args.threshold and days_since >= args.min_days

            if should_tag:
                status = "[DRY-RUN]" if args.dry_run else "[INACTIVE]"
                print(f"  {status:<12} {name:<30} {score:>7.2f}  {days_since:>6}d  {last_str}")
                if not args.dry_run:
                    _add_inactive_tag(db, dev.id)
                tagged += 1
            else:
                already_tagged = _has_inactive_tag(db, dev.id)
                if args.untag_active and already_tagged:
                    status = "[DRY-UNTAG]" if args.dry_run else "[UNTAGGED]"
                    print(f"  {status:<12} {name:<30} {score:>7.2f}  {days_since:>6}d  {last_str}")
                    if not args.dry_run:
                        _remove_inactive_tag(db, dev.id)
                    untagged += 1
                else:
                    # Verbose only for borderline cases (score in [2, threshold))
                    if score >= 2.0:
                        print(f"  {'[BORDERLINE]':<12} {name:<30} {score:>7.2f}  {days_since:>6}d  {last_str}")
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

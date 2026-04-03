#!/usr/bin/env python3
"""
Clean the CodeRadar database, keeping only Projects and Repositories data.

Removes all scan results, developer data, contributions, modules, languages,
dependencies, scores, risks, and personal data findings.

Usage:
    python scripts/clean_database.py
    python scripts/clean_database.py --dry-run   # preview row counts without deleting
"""
import sys
import os
import argparse
from pathlib import Path

# Allow running from repo root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text
from app.db.session import SessionLocal


TABLES_TO_CLEAN = [
    # Contribution data
    "developer_daily_activity",
    "developer_module_contributions",
    "developer_language_contributions",
    "developer_contributions",
    # Developer identity / profile data
    "identity_overrides",
    "developer_identities",
    "developer_profiles",
    "developer_tags",
    "developers",
    # Module data
    "modules",
    # Scan detail data
    "scan_personal_data_findings",
    "scan_risks",
    "scan_scores",
    "scan_languages",
    "dependencies",
    # Scans
    "scans",
    # Auxiliary repository data
    "repository_daily_activity",
    "repository_git_tags",
    # Languages lookup (safe to clear; re-populated on next scan)
    "languages",
]

# These tables are KEPT
TABLES_KEPT = [
    "projects",
    "project_tags",
    "repositories",
    "repository_tags",
]


def count_rows(db, table: str) -> int:
    result = db.execute(text(f"SELECT COUNT(*) FROM {table}"))
    return result.scalar()


def main():
    parser = argparse.ArgumentParser(description="Clean CodeRadar database, keeping only projects and repositories.")
    parser.add_argument("--dry-run", action="store_true", help="Show row counts without deleting anything.")
    parser.add_argument("--all", action="store_true", help="Also delete projects and repositories.")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        print("Tables to be cleaned:")
        total_rows = 0
        for table in TABLES_TO_CLEAN:
            count = count_rows(db, table)
            total_rows += count
            print(f"  {table:<45} {count:>8} rows")

        if args.all:
            for table in TABLES_KEPT:
                count = count_rows(db, table)
                total_rows += count
                print(f"  {table:<45} {count:>8} rows")
        else:
            print()
            print("Tables kept:")
            for table in TABLES_KEPT:
                count = count_rows(db, table)
                print(f"  {table:<45} {count:>8} rows")

        print()
        print(f"Total rows to delete: {total_rows}")

        if args.dry_run:
            print("\nDry-run mode — no changes made.")
            return

        confirm = input("\nProceed with deletion? [y/N] ").strip().lower()
        if confirm != "y":
            print("Aborted.")
            return

        # Temporarily disable foreign key checks so we can delete in bulk
        tables = TABLES_TO_CLEAN + (TABLES_KEPT if args.all else [])
        db.execute(text("PRAGMA foreign_keys=OFF"))
        try:
            for table in tables:
                db.execute(text(f"DELETE FROM {table}"))
                print(f"  Cleared {table}")
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.execute(text("PRAGMA foreign_keys=ON"))

        # Reclaim disk space
        db.execute(text("VACUUM"))
        db.commit()

        if args.all:
            print("\nDone. All data deleted.")
        else:
            print("\nDone. Projects and repositories data retained.")

    finally:
        db.close()


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Enqueue a scan for every repository in the database.
Scans are created with status=pending; run the worker to process them:

    python -m app.worker

Usage:
    python scripts/scan_all_repositories.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.db.session import SessionLocal
from app.models import Repository, Scan, ScanStatus
from app.services.scanning.queue import enqueue


def main() -> None:
    db = SessionLocal()
    try:
        repos = db.query(Repository).all()
        if not repos:
            print("No repositories in the database.")
            return
        created = []
        for repo in repos:
            branch = repo.default_branch or ""
            scan = Scan(
                repository_id=repo.id,
                branch=branch,
                status=ScanStatus.pending,
            )
            db.add(scan)
            created.append(scan)
        db.commit()
        for scan in created:
            db.refresh(scan)
            enqueue(scan.id)
        print(f"Enqueued {len(created)} scan(s) for all repositories.")
        print("Run the worker to process them: python -m app.worker")
    finally:
        db.close()


if __name__ == "__main__":
    main()

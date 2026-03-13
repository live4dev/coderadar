"""
Scan worker process. Run separately from the API, e.g.:
  python -m app.worker

Polls the database for scans with status=pending, claims one (sets running), then runs
the full scan pipeline. The DB is the queue; no in-memory queue or thread in the API.
"""
from __future__ import annotations
import time
from datetime import datetime, timezone

from sqlalchemy import select, update

from app.core.logging import setup_logging, get_logger
from app.db.session import SessionLocal
from app.models import Scan, ScanStatus
from app.services.scanning.orchestrator import run_scan

logger = get_logger(__name__)
POLL_INTERVAL_SEC = 2.0


def claim_next_pending_scan(session) -> int | None:
    """
    Atomically claim one pending scan: select oldest, update to running if still pending.
    Returns scan_id if claimed, None if none available or already claimed by another process.
    """
    row = session.execute(
        select(Scan.id).where(Scan.status == ScanStatus.pending).order_by(Scan.created_at).limit(1)
    ).first()
    if not row:
        return None
    scan_id = row[0]
    result = session.execute(
        update(Scan)
        .where(Scan.id == scan_id, Scan.status == ScanStatus.pending)
        .values(status=ScanStatus.running, started_at=datetime.now(timezone.utc))
    )
    session.commit()
    if result.rowcount != 1:
        return None
    return scan_id


def run_worker_loop() -> None:
    while True:
        session = SessionLocal()
        try:
            scan_id = claim_next_pending_scan(session)
        finally:
            session.close()

        if scan_id is None:
            time.sleep(POLL_INTERVAL_SEC)
            continue

        logger.info("worker_processing", scan_id=scan_id)
        db = SessionLocal()
        try:
            run_scan(scan_id, db)
        except Exception as e:
            logger.exception("worker_scan_error", scan_id=scan_id, error=str(e))
        finally:
            db.close()


def main() -> None:
    setup_logging()
    logger.info("scan_worker_process_started", poll_interval_sec=POLL_INTERVAL_SEC)
    run_worker_loop()


if __name__ == "__main__":
    main()

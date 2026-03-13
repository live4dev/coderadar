"""
Scan jobs are no longer enqueued in-process. The queue is the database: scans with
status=pending. A separate worker process (python -m app.worker) polls the DB and
runs scans. This module is kept for backwards compatibility; enqueue() is a no-op
and only logs (API still creates Scan with status=pending).
"""
from __future__ import annotations

from app.core.logging import get_logger

logger = get_logger(__name__)


def enqueue(scan_id: int) -> None:
    """No-op. Scans are picked up by the separate worker process polling the DB."""
    logger.debug("scan_created_pending", scan_id=scan_id, hint="run worker: python -m app.worker")

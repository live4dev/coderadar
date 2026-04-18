"""
Tests for the Scans Queue cancel endpoint and queue listing.

Key behaviors verified:
- Cancelling a PENDING scan immediately sets status=cancelled and completed_at.
- Cancelling a RUNNING scan sets cancel_requested=True and keeps status=running
  (frontend shows this as "Running (cancelling...)"; worker finalizes the transition).
- Cancelling a completed/failed/cancelled scan returns 400.
- Cancelling a non-existent scan returns 404.
- Queue listing returns scans and supports status filtering.
- Queue response exposes cancel_requested so the frontend can show the cancelling state.
"""
import pytest
from app.models.scan import Scan, ScanStatus


# ── Helpers ──────────────────────────────────────────────────────────────────

def _create_project(client, name="Test Project") -> int:
    r = client.post("/api/v1/projects", json={"name": name})
    assert r.status_code == 201
    return r.json()["id"]


def _create_repo(client, project_id, name="test-repo", url="https://github.com/org/repo") -> int:
    r = client.post("/api/v1/repositories", json={
        "project_id": project_id,
        "name": name,
        "url": url,
        "provider_type": "github",
    })
    assert r.status_code == 201
    return r.json()["id"]  # project_repository_id


def _create_scan(db_session, project_repository_id: int, status: ScanStatus, cancel_requested: bool = False) -> Scan:
    scan = Scan(
        project_repository_id=project_repository_id,
        branch="main",
        status=status,
        cancel_requested=cancel_requested,
    )
    db_session.add(scan)
    db_session.commit()
    db_session.refresh(scan)
    return scan


# ── Cancel endpoint ───────────────────────────────────────────────────────────

def test_cancel_pending_scan_immediately_cancels(client, db_session):
    pid = _create_project(client)
    pr_id = _create_repo(client, pid)
    scan = _create_scan(db_session, pr_id, ScanStatus.pending)

    resp = client.post(f"/api/v1/scans/{scan.id}/cancel")

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "cancelled"
    assert body["completed_at"] is not None
    assert body["cancel_requested"] is False

    db_session.refresh(scan)
    assert scan.status == ScanStatus.cancelled
    assert scan.completed_at is not None


def test_cancel_running_scan_sets_cancel_requested(client, db_session):
    """
    Stopping a running scan must NOT change the status immediately.
    It sets cancel_requested=True so the worker can stop cleanly.
    The frontend displays this as "Running (cancelling...)".
    """
    pid = _create_project(client)
    pr_id = _create_repo(client, pid)
    scan = _create_scan(db_session, pr_id, ScanStatus.running)

    resp = client.post(f"/api/v1/scans/{scan.id}/cancel")

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "running"       # still running — worker will finalize
    assert body["cancel_requested"] is True  # signals "cancelling..."
    assert body["completed_at"] is None      # not done yet

    db_session.refresh(scan)
    assert scan.status == ScanStatus.running
    assert scan.cancel_requested is True


def test_cancel_completed_scan_returns_400(client, db_session):
    pid = _create_project(client)
    pr_id = _create_repo(client, pid)
    scan = _create_scan(db_session, pr_id, ScanStatus.completed)

    resp = client.post(f"/api/v1/scans/{scan.id}/cancel")

    assert resp.status_code == 400


def test_cancel_failed_scan_returns_400(client, db_session):
    pid = _create_project(client)
    pr_id = _create_repo(client, pid)
    scan = _create_scan(db_session, pr_id, ScanStatus.failed)

    resp = client.post(f"/api/v1/scans/{scan.id}/cancel")

    assert resp.status_code == 400


def test_cancel_already_cancelled_scan_returns_400(client, db_session):
    pid = _create_project(client)
    pr_id = _create_repo(client, pid)
    scan = _create_scan(db_session, pr_id, ScanStatus.cancelled)

    resp = client.post(f"/api/v1/scans/{scan.id}/cancel")

    assert resp.status_code == 400


def test_cancel_nonexistent_scan_returns_404(client):
    resp = client.post("/api/v1/scans/9999/cancel")
    assert resp.status_code == 404


# ── Queue listing ─────────────────────────────────────────────────────────────

def test_queue_returns_all_scans(client, db_session):
    pid = _create_project(client)
    pr_id = _create_repo(client, pid)
    _create_scan(db_session, pr_id, ScanStatus.pending)
    _create_scan(db_session, pr_id, ScanStatus.running)
    _create_scan(db_session, pr_id, ScanStatus.completed)

    resp = client.get("/api/v1/scans/queue")

    assert resp.status_code == 200
    items = resp.json()
    assert len(items) == 3
    statuses = {item["status"] for item in items}
    assert statuses == {"pending", "running", "completed"}


def test_queue_filter_by_status(client, db_session):
    pid = _create_project(client)
    pr_id = _create_repo(client, pid)
    _create_scan(db_session, pr_id, ScanStatus.pending)
    _create_scan(db_session, pr_id, ScanStatus.running)

    resp = client.get("/api/v1/scans/queue?status=running")

    assert resp.status_code == 200
    items = resp.json()
    assert len(items) == 1
    assert items[0]["status"] == "running"


def test_queue_running_scan_shows_cancel_requested(client, db_session):
    """
    After stopping a running scan, GET /queue must expose cancel_requested=True
    so the frontend can render "Running (cancelling...)".
    """
    pid = _create_project(client)
    pr_id = _create_repo(client, pid)
    scan = _create_scan(db_session, pr_id, ScanStatus.running)

    client.post(f"/api/v1/scans/{scan.id}/cancel")

    resp = client.get("/api/v1/scans/queue?status=running")
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) == 1
    assert items[0]["cancel_requested"] is True
    assert items[0]["status"] == "running"

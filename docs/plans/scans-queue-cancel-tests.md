# Plan: Tests for Stop Scan in Scans Queue

## Context

When a user clicks "Stop" on a scan in the Scans Queue:
- A **pending** scan is immediately set to `cancelled`
- A **running** scan gets `cancel_requested = True` (the frontend shows this as "Running (cancelling...)") while the worker eventually transitions it to `cancelled`

There are currently no tests for the cancel endpoint or queue listing. This plan adds a comprehensive `tests/test_scans_queue.py` covering cancel behavior and queue API.

## Critical Files

| File | Role |
|------|------|
| `app/api/v1/scans.py:110-123` | `cancel_scan()` endpoint — the code under test |
| `app/api/v1/scans.py:44-107` | `get_scan_queue()` endpoint |
| `app/models/scan.py` | `Scan` model, `ScanStatus` enum, `cancel_requested` field |
| `tests/conftest.py` | `client`, `db_session` fixtures (reuse as-is) |

## Test Cases

| Test | Action | Expected |
|------|--------|----------|
| `test_cancel_pending_scan_immediately_cancels` | POST /cancel on pending scan | `status=cancelled`, `completed_at` set, HTTP 200 |
| `test_cancel_running_scan_sets_cancel_requested` | POST /cancel on running scan | `status=running`, `cancel_requested=True`, HTTP 200 |
| `test_cancel_completed_scan_returns_400` | POST /cancel on completed scan | HTTP 400 |
| `test_cancel_failed_scan_returns_400` | POST /cancel on failed scan | HTTP 400 |
| `test_cancel_already_cancelled_scan_returns_400` | POST /cancel on cancelled scan | HTTP 400 |
| `test_cancel_nonexistent_scan_returns_404` | POST /cancel on id 9999 | HTTP 404 |
| `test_queue_returns_all_scans` | GET /queue with multiple scans | All scans listed |
| `test_queue_filter_by_status` | GET /queue?status=running | Only running scans returned |
| `test_queue_running_scan_shows_cancel_requested` | GET /queue after cancelling running scan | `cancel_requested=True` in response |

## Verification

```bash
python -m pytest tests/test_scans_queue.py -v
```

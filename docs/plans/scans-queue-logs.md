# Plan: Scans Queue — All Scans + Logs

## Goal
Expand the Scans Queue view to show all scans (not just pending/running) with:
- Project name
- Repository name
- Spent time (duration)
- Scanning status
- Scanning logs (per-stage log entries)
---

## Changes

### 1. `app/models/scan.py`
Add `scan_log: Mapped[str | None]` (Text column) — stores a JSON array of
`{"ts": "<ISO timestamp>", "msg": "<message>"}` entries appended at each pipeline stage.

### 2. `alembic/versions/003_scan_log.py`
Migration to add `scan_log TEXT` column (nullable) to the `scans` table.

### 3. `app/services/scanning/orchestrator.py`
Add helper `_append_log(scan, db, message)` that appends a timestamped entry to
`scan.scan_log`. Call it after each stage (repo prepare, file analysis, stack, complexity,
git analytics, git tags, scoring, risks, PII, finalize).

### 4. `app/schemas/scan.py`
Extend `ScanQueueItemOut`:
- Add `project_name: str`
- Add `completed_at: datetime | None`
- Add `scan_log: list[dict] | None`  (parsed JSON)

### 5. `app/api/v1/scans.py`
Update `GET /scans/queue`:
- Join `ProjectRepository → Project` to obtain `project_name`
- Remove status filter so ALL scans are returned (most recent 200, ordered `created_at DESC`)
- Include `completed_at` and `scan_log` in response

### 6. `app/static/js/views/scans-queue.js`
- Show ALL scans (newest first, limit 200)
- Columns: Project | Repository | Branch | Status | Created | Duration | Actions
- Spent time: compute from `started_at`/`completed_at`; live-update for running scans
- Expandable log row: click on a row to toggle an inline log panel showing timestamped
  entries from `scan_log`
- Auto-refresh (5 s) only while any scan is pending or running

---

## Improvements (2026-04-03)

### UI

- Infinity scroll: load 100 rows at a time; fetch next batch when sentinel scrolls into view
- Filter bar: text inputs for project + repository (debounced 300 ms), status select
- Sort: clickable `#`, `Status`, `Queued`, `Started`, `Duration` column headers with asc/desc toggle
- Datetime: `Queued` and `Started` columns show full datetime (date + HH:MM)
- Columns: `#` (id) | Project | Repository | Branch | Status | Queued | Started | Duration | Actions

### Backend (`app/api/v1/scans.py`)

- New query params on `GET /scans/queue`:
  - `limit` (default 100, max 500), `offset` (default 0)
  - `sort_by`: `id` | `status` | `queued` | `started` | `duration` (default `id`)
  - `sort_order`: `asc` | `desc` (default `desc`)
  - `project`: substring filter on project name (ilike)
  - `repository`: substring filter on repository name (ilike)
  - `status`: exact match filter

### Utils (`app/static/js/utils.js`)

- Add `fmtDatetime(s)` — formats as "3 Apr 2026 14:30"

# Plan: Tests for scripts/ helper functions

## Goal

Add unit tests for the pure / mockable helper functions in the four scripts that contain non-trivial logic:

- `scripts/import_github.py`
- `scripts/import_bitbucket.py`
- `scripts/tag_inactive_developers.py`
- `scripts/tag_inactive_repositories.py`

The `main()` functions of each script are integration points that hit a real DB and network; we leave those untested. We focus on the self-contained helpers that carry the real logic.

---

## Test files to create

### `tests/test_import_github.py`

Covers the pure / mock-friendly helpers in `import_github.py`.

| Function | What to verify |
|---|---|
| `_parse_github_url` | Accepts `https://github.com/org`, `github.com/org/`, `https://github.com/org/repo/` (extra segments ignored); raises `ValueError` on bad inputs (`http://gitlab.com/x`, no name segment). |
| `_make_session` | Returns a `requests.Session` with correct `Authorization: Bearer <token>` header and GitHub-specific `Accept` / `X-GitHub-Api-Version` headers; omits `Authorization` when token is empty. |
| `_paginate` | Single page (no `Link` header) yields all items and stops. Multiple pages (rel="next" Link header) follow the chain and yield all items. `HTTPError` propagates. |

### `tests/test_import_bitbucket.py`

Covers the pure / mock-friendly helpers in `import_bitbucket.py`.

| Function | What to verify |
|---|---|
| `_make_session` | Token → `Authorization: Bearer <token>`. Username+password → `Authorization: Basic <b64>`. Both absent → no `Authorization` header. |
| `_http_clone_url` | Returns the `href` of the first link whose `name == "http"`. Returns `None` when no HTTP link exists. Returns `None` for an empty links dict. |
| `_paginate` | Single page (`isLastPage: true`) yields items and stops. Multi-page (`isLastPage: false`, `nextPageStart` set) follows pages and yields all items. |
| `_get_default_branch` | Returns `displayId` on a successful response. Returns `None` when the server returns a non-2xx status. Returns `None` on a network exception. |

### `tests/test_tag_inactive.py`

Covers the pure math helpers in both tagger scripts (no DB needed).

#### `tag_inactive_developers.compute_inactivity_score`

| Case | Expected outcome |
|---|---|
| Recent active developer (last commit yesterday, commits in last 90 days) | score < 2 |
| Developer who stopped committing 200 days ago with no recent activity | score ≥ 4 |
| Single-commit developer (first == last, active_days=1) | Does not raise; avg_interval falls back to 1.0 |
| recent_ratio clamped at 1.0 (more recent commits than average predicts) | score ≥ 0 (no negative scores) |
| days_since_last returned correctly | Matches `(now - last_commit_at).days` |

#### `tag_inactive_repositories.compute_inactivity_score`

Same logical cases, but uses `date` objects instead of `datetime` objects.

| Case | Expected outcome |
|---|---|
| Repository with recent commits (max_date = today) | days_since_last == 0, score near 0 |
| Repository last committed 365 days ago, sparse history | score ≥ 4 |
| Single active day (active_days=1, min==max) | Does not raise; avg_interval falls back to 1.0 |
| recent_ratio clamped at 1.0 | score ≥ 0 |

---

## Out of scope

- `scripts/import_gitlab.py` — logic is structurally identical to `import_bitbucket.py`; covered implicitly.
- `scripts/local_scan.py`, `scripts/scan_all_repositories.py`, `scripts/clean_database.py`, `scripts/seed_popular_projects.py` — these are thin orchestration wrappers with no isolated pure logic to test independently.
- Full integration tests for `main()` functions (require live DB + network).

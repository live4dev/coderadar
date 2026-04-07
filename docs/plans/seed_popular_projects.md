# Plan: Seed Script for Popular GitHub Projects

## Context

CodeRadar needs sample data for demonstration and development. This script imports several well-known open-source projects (each with multiple repositories) so the app has realistic, varied content out of the box.

The existing `scripts/import_github.py` imports all repos for a single GitHub org/user. This new script instead has a **hardcoded curated list** of popular projects (each spanning multiple GitHub repositories) and imports them into CodeRadar as separate projects with their associated repositories.

**Important:** The existing `import_github.py` uses the outdated model (`Repository(project_id=..., name=...)`). The current model separates `Repository` (global, URL-deduplicated) from `ProjectRepository` (project-scoped join, carries name + credentials). The new script must use the correct model.

---

## Output File

`scripts/seed_popular_projects.py`

---

## Curated Projects List

Each entry maps a CodeRadar project name to a list of `owner/repo` slugs:

| Project | Repositories |
|---------|-------------|
| **Django** | django/django, django/channels, django/asgiref, django/django-filter |
| **FastAPI** | tiangolo/fastapi, tiangolo/sqlmodel, tiangolo/typer |
| **HashiCorp** | hashicorp/terraform, hashicorp/vault, hashicorp/consul, hashicorp/packer |
| **Microsoft Dev Tools** | microsoft/vscode, microsoft/TypeScript, microsoft/playwright, microsoft/pyright |
| **Apache Data** | apache/kafka, apache/spark, apache/airflow, apache/flink |
| **Kubernetes** | kubernetes/kubernetes, kubernetes/ingress-nginx, kubernetes/dashboard, helm/helm |

---

## Implementation Plan

### 1. Script header & imports
```
scripts/seed_popular_projects.py
```
- Same `sys.path.insert` pattern as other scripts
- Import: `SessionLocal`, `Project`, `Repository`, `ProjectRepository`, `Scan`, `ScanStatus`, `ProviderType`
- Import: `setup_logging`, `get_logger`
- Import: `requests` for optional GitHub API metadata lookup

### 2. Data definition
Hardcoded `PROJECTS` dict at module level:
```python
PROJECTS: dict[str, list[str]] = {
    "Django": ["django/django", "django/channels", ...],
    "FastAPI": ["tiangolo/fastapi", ...],
    ...
}
```
Each slug becomes `https://github.com/{owner}/{repo}.git`.

### 3. Optional GitHub API enrichment
If `--token` is provided, fetch `GET /repos/{owner}/{repo}` to get:
- `default_branch` (fallback: `"main"`)
- `description` (used for project description on first project creation)

If no token: use `main` as default branch, generic description.

### 4. CLI arguments
```
--token          GitHub PAT (or GITHUB_TOKEN env var)
--scan           Enqueue a scan for each newly imported repo
--dry-run        Print what would happen, no DB writes
--projects       Comma-separated subset of project names to import (default: all)
```

### 5. Import logic (idempotent)
For each project in `PROJECTS`:
1. **Find or create `Project`** by name
2. For each repo slug:
   a. Build clone URL: `https://github.com/{owner}/{repo}.git`
   b. **Find or create `Repository`** by URL (unique constraint — use `filter_by(url=...)`)
   c. **Find or create `ProjectRepository`** — check `filter_by(project_id=..., repository_id=...)` to avoid duplicates
   d. If `--scan` and newly created `ProjectRepository`: create `Scan(project_repository_id=..., status=pending)`

### 6. Output
```
Project: Django
  [NEW]    django           https://github.com/django/django.git
  [NEW]    channels         https://github.com/django/channels.git
  [EXISTS] asgiref          (skipped)
  ...

Summary: 18 new repos, 2 skipped, 18 scans enqueued.
```

---

## Critical Files

| File | Role |
|------|------|
| `scripts/seed_popular_projects.py` | New file to create |
| `app/models/repository.py` | `Repository`, `ProjectRepository` |
| `app/models/scan.py` | `Scan`, `ScanStatus` |
| `app/models/project.py` | `Project` |
| `app/db/session.py` | `SessionLocal` |
| `app/core/logging.py` | `setup_logging`, `get_logger` |

---

## Verification

1. **Dry run:**
   ```bash
   python scripts/seed_popular_projects.py --dry-run
   ```

2. **Import without scans:**
   ```bash
   python scripts/seed_popular_projects.py --token $GITHUB_TOKEN
   ```

3. **Import subset:**
   ```bash
   python scripts/seed_popular_projects.py --token $GITHUB_TOKEN --projects "Django,FastAPI"
   ```

4. **Idempotency:** Run twice — second run shows all `[EXISTS]`.

5. **With scans:**
   ```bash
   python scripts/seed_popular_projects.py --token $GITHUB_TOKEN --scan
   python -m app.worker
   ```

# CodeRadar

Technical profiling service for Git repositories. Supports **Bitbucket** and **GitLab**.

## What it does

- Detects tech stack, languages, frameworks, dependencies
- Measures project size, complexity, and code quality
- Analyses git history: contributors, ownership by language and module
- Computes quality scores (code, tests, docs, delivery, maintainability)
- Detects risks: no tests, no CI, low bus factor, knowledge concentration, etc.
- Stores all results in SQLite; API-first design

## Stack

| Component | Technology |
|-----------|-----------|
| Language | Python 3.12 |
| Web framework | FastAPI |
| ORM | SQLAlchemy 2 |
| Migrations | Alembic |
| Database | SQLite (PostgreSQL-ready) |
| Schema validation | Pydantic v2 |

## Quick start

```bash
cd coderadar

# 1. Create virtual environment
python3.12 -m venv .venv
source .venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure (optional)
cp .env.example .env
# Edit .env with your Bitbucket / GitLab credentials

# 4. Apply migrations
alembic upgrade head

# 5. Start server
uvicorn app.main:app --reload --port 8000

# 6. (Optional) Start scan worker in another terminal — processes scans (pending → running → completed)
python -m app.worker
```

API docs available at: http://localhost:8000/docs

Scans are processed by a **separate worker process**. After `POST .../scan` the scan stays `pending` until the worker picks it from the DB. Run `python -m app.worker` in a separate terminal (or as a systemd/supervisor service).

## Add a repository and run a scan

```bash
# Create project
curl -X POST http://localhost:8000/api/v1/projects \
  -H "Content-Type: application/json" \
  -d '{"name": "My Project"}'

# Add Bitbucket repository
curl -X POST http://localhost:8000/api/v1/repositories \
  -H "Content-Type: application/json" \
  -d '{
    "project_id": 1,
    "name": "my-repo",
    "url": "https://bitbucket.org/workspace/my-repo.git",
    "provider_type": "bitbucket",
    "default_branch": "main",
    "credentials_username": "YOUR_USERNAME",
    "credentials_token": "YOUR_APP_PASSWORD"
  }'

# Add GitLab repository
curl -X POST http://localhost:8000/api/v1/repositories \
  -H "Content-Type: application/json" \
  -d '{
    "project_id": 1,
    "name": "my-gitlab-repo",
    "url": "https://gitlab.com/group/my-repo.git",
    "provider_type": "gitlab",
    "credentials_token": "YOUR_PERSONAL_ACCESS_TOKEN"
  }'

# Trigger scan
curl -X POST http://localhost:8000/api/v1/repositories/1/scan \
  -H "Content-Type: application/json" \
  -d '{}'

# Check scan status
curl http://localhost:8000/api/v1/scans/1

# Get results
curl http://localhost:8000/api/v1/scans/1/summary
curl http://localhost:8000/api/v1/scans/1/languages
curl http://localhost:8000/api/v1/scans/1/scores
curl http://localhost:8000/api/v1/scans/1/risks
curl http://localhost:8000/api/v1/scans/1/developers
```

## Scripts

### Import from GitLab

Bulk-register groups and repositories from a GitLab instance. Each group becomes a CodeRadar project. Already-imported repos are skipped (idempotent).

```bash
# Import all groups accessible to the token
python scripts/import_gitlab.py --token $GITLAB_TOKEN

# Limit to one group (includes subgroups)
python scripts/import_gitlab.py --token $GITLAB_TOKEN --group my-group

# Self-hosted instance
python scripts/import_gitlab.py --token $GITLAB_TOKEN --base-url https://gitlab.example.com --group my-group

# Preview without writing to the database
python scripts/import_gitlab.py --token $GITLAB_TOKEN --group my-group --dry-run

# Import and immediately enqueue scans
python scripts/import_gitlab.py --token $GITLAB_TOKEN --group my-group --scan
python -m app.worker   # in a separate terminal
```

| Flag | Default | Description |
| ---- | ------- | ----------- |
| `--token` | `$GITLAB_TOKEN` | GitLab Personal Access Token |
| `--base-url` | `$GITLAB_URL` / `https://gitlab.com` | GitLab instance URL |
| `--group` | all groups | Limit to this group path or numeric ID |
| `--project-name` | group full path | Override CodeRadar project name (single-group mode) |
| `--skip-archived` | false | Skip archived repositories |
| `--default-branch` | `main` | Fallback branch name |
| `--scan` | false | Enqueue scans for newly imported repos |
| `--dry-run` | false | Preview without writing to the database |

### Import from GitHub

Bulk-register repositories from a GitHub organisation or user. The org/user becomes a single CodeRadar project. Already-imported repos are skipped (idempotent).

```bash
# Import an organisation's repos
python scripts/import_github.py --token $GITHUB_TOKEN --org my-org

# Import a user's repos
python scripts/import_github.py --token $GITHUB_TOKEN --user octocat

# Import the token owner's own repos (no --org / --user needed)
python scripts/import_github.py --token $GITHUB_TOKEN

# Skip forks and archived repos, preview first
python scripts/import_github.py --token $GITHUB_TOKEN --org my-org --skip-forks --skip-archived --dry-run

# Import and immediately enqueue scans
python scripts/import_github.py --token $GITHUB_TOKEN --org my-org --scan
python -m app.worker   # in a separate terminal
```

| Flag | Default | Description |
| ---- | ------- | ----------- |
| `--token` | `$GITHUB_TOKEN` | GitHub Personal Access Token |
| `--org` | — | Import repos from this GitHub organisation |
| `--user` | — | Import repos from this GitHub user |
| `--skip-archived` | false | Skip archived repositories |
| `--skip-forks` | false | Skip forked repositories |
| `--default-branch` | `main` | Fallback branch name |
| `--scan` | false | Enqueue scans for newly imported repos |
| `--dry-run` | false | Preview without writing to the database |

### Scan a local repository (demo mode)

Scan any local git repository without Bitbucket/GitLab credentials.

```bash
python scripts/local_scan.py --path /path/to/local/repo --project-name "Demo"
# Optional: specify branch metadata
python scripts/local_scan.py --path /path/to/local/repo --project-name "Demo" --branch develop
```

Runs the full analysis pipeline (files, stack, dependencies, git analytics, scoring, risks) and stores results in the database.

### Enqueue scans for all repositories

Create pending scans for every repository already in the database, then process them with the worker.

```bash
python scripts/scan_all_repositories.py
python -m app.worker   # in a separate terminal
```

### Tag inactive developers

Applies an `inactive` tag to developers whose commit history suggests they are no longer active. Uses a composite inactivity score based on days since last commit, personal commit rhythm, and recent-activity drop-off — not a fixed date cutoff.

> **Note:** `inactive` is a probabilistic signal, not a statement about employment status. A developer may be on leave, in a management role, or contributing to repositories not tracked here.

```bash
# Preview without writing to DB
python scripts/tag_inactive_developers.py --dry-run

# Apply tags (default: score >= 4.0 and last commit >= 30 days ago)
python scripts/tag_inactive_developers.py

# Restrict to one project
python scripts/tag_inactive_developers.py --project-id 1

# Adjust sensitivity
python scripts/tag_inactive_developers.py --threshold 3.0 --min-days 60

# Also remove 'inactive' tag from developers who are now active
python scripts/tag_inactive_developers.py --untag-active
```

**Inactivity score formula:**

```
avg_interval  = (last_commit - first_commit).days / max(active_days - 1, 1)
recent_ratio  = commits_last_90d / max(avg_daily_commits × 90, 1)   # clamped 0..1
score         = (days_since_last_commit / avg_interval) × (1 − recent_ratio)
```

| Score | Interpretation |
| ----- | -------------- |
| < 2 | Active |
| 2 – threshold | Possibly inactive (not tagged) |
| ≥ threshold AND days ≥ min-days | Tagged as `inactive` |

### Tag inactive repositories

Applies an `inactive` tag to repositories whose commit history suggests development has gone quiet. Uses the same composite inactivity score as the developer tagger, but sourced from `RepositoryDailyActivity`.

> **Note:** `inactive` is a probabilistic signal. A repository may be stable and intentionally quiet, in a freeze period, or only updated at release time.

```bash
# Preview without writing to DB
python scripts/tag_inactive_repositories.py --dry-run

# Apply tags (default: score >= 4.0 and last commit >= 30 days ago)
python scripts/tag_inactive_repositories.py

# Restrict to one project
python scripts/tag_inactive_repositories.py --project-id 1

# Adjust sensitivity
python scripts/tag_inactive_repositories.py --threshold 3.0 --min-days 60

# Also remove 'inactive' tag from repositories that are now active
python scripts/tag_inactive_repositories.py --untag-active
```

The tag includes a description: `"Auto-tagged: no commit activity since YYYY-MM-DD"`.

## Personal data scanner

CodeRadar can scan source files for variable and field names that suggest personal data (PDn / PII) is being handled — useful for compliance audits and data-flow awareness.

### How it works

The scanner walks every non-test, non-binary source file in the repository and looks for identifier names (variable names, field names, parameter names) that match a configured list. Matches inside **comments, docstrings, and block comments** are ignored so only actual code references are reported.

Supported comment styles:

| Style | Languages |
| ----- | --------- |
| `#` to EOL + `"""` / `'''` docstrings | Python, Ruby, Shell, YAML, TOML |
| `//` to EOL + `/* … */` blocks | JS/TS, Java, Go, C/C++, Rust, Swift, Kotlin, PHP |
| `--` to EOL + `/* … */` blocks | SQL |

### Configuration

PDn types are defined in `config/pdn_types.yaml`:

```yaml
pdn_types:
  - name: email
    identifiers:
      - email
      - email_address
      - emailAddress
      - user_email
      - userEmail
  - name: phone
    identifiers:
      - phone
      - phone_number
      - phoneNumber
```

Each `name` is the category reported in findings. Each entry in `identifiers` is matched as a whole word (word-boundary anchored) against code tokens. The config path can be overridden via the `PDN_TYPES_CONFIG` environment variable.

### Findings

Results are stored per scan in the `scan_personal_data_findings` table and exposed via the API:

```bash
curl http://localhost:8000/api/v1/scans/1/personal-data
```

Each finding includes the PDn category, file path, line number, and the exact matched identifier.

## Add identity override

Map a raw git identity to a canonical username:

```bash
curl -X POST http://localhost:8000/api/v1/developers/identity-overrides \
  -H "Content-Type: application/json" \
  -d '{
    "project_id": 1,
    "raw_email": "d.ivanov@old-company.com",
    "canonical_username": "d_ivanov"
  }'
```

## Run tests

```bash
pytest tests/ -v
```

## Project structure

```
coderadar/
  app/
    api/v1/          # REST endpoints
    core/            # config, logging
    db/              # SQLAlchemy session, base
    models/          # ORM models (15 tables)
    schemas/         # Pydantic schemas
    services/
      vcs/           # BaseVCSProvider, BitbucketProvider, GitLabProvider
      scanning/      # Scan orchestrator (7-stage pipeline)
      analysis/      # File analyser, stack detector, dependency parser, complexity
      git_analytics/ # Git log parser, contributor aggregator
      identity/      # Identity normaliser (transliteration, email hints, overrides)
      scoring/       # Rule-based scoring engine (5 domains + overall)
      risks/         # Risk detection engine (12 risk types)
  alembic/           # Migrations
  tests/             # Unit tests
  scripts/           # Utilities (local scan)
```

## API reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | /api/v1/projects | Create project |
| GET | /api/v1/projects | List projects |
| GET | /api/v1/projects/{id} | Get project |
| GET | /api/v1/projects/{id}/developers | List developers |
| POST | /api/v1/repositories | Add repository |
| GET | /api/v1/repositories/{id} | Get repository |
| POST | /api/v1/repositories/{id}/scan | Trigger scan |
| GET | /api/v1/repositories/{id}/scans | List scans |
| GET | /api/v1/repositories/{id}/modules | List modules |
| GET | /api/v1/scans/{id} | Get scan |
| GET | /api/v1/scans/{id}/summary | Scan summary |
| GET | /api/v1/scans/{id}/languages | Language breakdown |
| GET | /api/v1/scans/{id}/dependencies | Dependencies |
| GET | /api/v1/scans/{id}/scores | Quality scores |
| GET | /api/v1/scans/{id}/risks | Risk list |
| GET | /api/v1/scans/{id}/developers | Developer contributions |
| GET | /api/v1/developers/{id} | Get developer |
| GET | /api/v1/developers/{id}/languages | Developer language stats |
| GET | /api/v1/developers/{id}/modules | Developer module stats |
| POST | /api/v1/developers/identity-overrides | Add identity override |
| GET | /api/v1/modules/{id}/ownership | Module ownership |

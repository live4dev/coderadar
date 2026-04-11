# CodeRadar — Architecture & Technology Stack

> A domain-driven design analysis of the CodeRadar technical profiling service for Git repositories.

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [Technology Stack](#2-technology-stack)
3. [Domain-Driven Design](#3-domain-driven-design)
   - 3.1 [Bounded Contexts](#31-bounded-contexts)
   - 3.2 [Ubiquitous Language](#32-ubiquitous-language)
   - 3.3 [Aggregates & Entities](#33-aggregates--entities)
   - 3.4 [Value Objects](#34-value-objects)
   - 3.5 [Domain Services](#35-domain-services)
   - 3.6 [Domain Events (Implicit)](#36-domain-events-implicit)
4. [Layered Architecture](#4-layered-architecture)
5. [Scan Pipeline (Core Domain Process)](#5-scan-pipeline-core-domain-process)
6. [Data Model](#6-data-model)
7. [API Surface](#7-api-surface)
8. [Infrastructure & Deployment](#8-infrastructure--deployment)
9. [Quality & Testing](#9-quality--testing)

---

## 1. System Overview

CodeRadar is an **API-first technical profiling service** that scans Git repositories and delivers structured analytics across five quality dimensions: code quality, test coverage, documentation, delivery health, and maintainability.

The system clones or fetches repositories from Bitbucket, GitLab, or GitHub, runs a deterministic multi-stage analysis pipeline, and exposes the results through a JSON REST API together with a lightweight single-page frontend.

**Key design decisions:**

- **No ML, fully deterministic.** All scoring and risk detection uses rule-based engines, making results auditable and reproducible.
- **Database as queue.** Rather than a message broker, the scan worker polls the database for `pending` scans, claiming them atomically. This eliminates a dependency on Redis or RabbitMQ at the cost of poll latency.
- **SQLite by default, PostgreSQL-ready.** The SQLAlchemy ORM layer means zero code changes to switch database engines; only the `DATABASE_URL` environment variable needs to change.
- **Per-stage commit.** Each pipeline stage persists its results independently, so a crash mid-scan leaves partially useful data rather than nothing.

---

## 2. Technology Stack

### Backend

| Layer | Choice | Version | Role |
|---|---|---|---|
| Language | Python | 3.12 | Primary runtime |
| Web framework | FastAPI | 0.115.5 | REST API, async routing, OpenAPI |
| ASGI server | Uvicorn (standard) | 0.32.1 | HTTP server with lifespan support |
| ORM | SQLAlchemy | 2.0.36 | Mapped ORM models, session management |
| Migrations | Alembic | 1.14.0 | Versioned schema migrations (12 versions) |
| Validation | Pydantic v2 | 2.10.3 | Request/response schemas, settings |
| Settings | pydantic-settings | 2.7.0 | `.env`-driven configuration |
| Git integration | GitPython | 3.1.43 | Clone, fetch, tag parsing |
| HTTP client | httpx | 0.28.1 | Async HTTP (license API enrichment) |
| Structured logging | structlog | 24.4.0 | JSON-friendly log output |
| Transliteration | transliterate | 1.10.2 | Cyrillic → Latin identity normalisation |
| Syntax highlighting | Pygments | 2.18.0 | Language detection support |
| Env files | python-dotenv | 1.0.1 | `.env` loading |

### Database

| Component | Detail |
|---|---|
| Default engine | SQLite (WAL mode, foreign keys enforced) |
| Production-ready | PostgreSQL (connection string swap only) |
| ORM | SQLAlchemy 2.0 with `Mapped` / `mapped_column` typed API |
| Migrations | Alembic, 12 sequential versions from initial schema to licence fields |

### Frontend

| Component | Choice |
|---|---|
| Architecture | Vanilla JS SPA (no framework, ES Modules) |
| Routing | Custom hash-based client router (`router.js`) |
| State | Shared singleton (`state.js`) |
| Charts | Apache ECharts 5 (CDN) — treemap, heatmap |
| Served by | FastAPI `StaticFiles` mount |

### Infrastructure / DevOps

| Concern | Tool |
|---|---|
| Containerisation | Docker + Docker Compose |
| CI/CD | GitHub Actions (`.github/workflows/ci.yml`, `docker.yml`) |
| Package management | pip + `requirements.txt` |
| Config format | YAML (`pdn_types.yaml`) and `.env` |

### Testing

| Tool | Purpose |
|---|---|
| pytest 8.3.4 | Test runner |
| pytest-asyncio 0.24.0 | Async test support |
| 10 test modules | Complexity, contributor aggregation, dependency parsing, file analysis, git parser, identity normalisation, PDN scanner, risk engine, scoring, stack detection |

---

## 3. Domain-Driven Design

### 3.1 Bounded Contexts

CodeRadar's domain naturally partitions into six bounded contexts. Each context owns its logic, models, and terminology.

```
┌─────────────────────────────────────────────────────────────────────┐
│                          CodeRadar System                           │
│                                                                     │
│  ┌──────────────────┐   ┌──────────────────┐   ┌────────────────┐  │
│  │  Project          │   │  Scan Lifecycle  │   │  VCS           │  │
│  │  Management       │◄──│  & Orchestration │──►│  Integration   │  │
│  │                  │   │                  │   │                │  │
│  │  Project         │   │  Scan            │   │  Repository    │  │
│  │  Repository      │   │  ScanStatus      │   │  clone/fetch   │  │
│  │  Module          │   │  Pipeline stages │   │  Bitbucket     │  │
│  └──────────────────┘   └──────────────────┘   │  GitLab        │  │
│                                  │              │  GitHub        │  │
│  ┌──────────────────┐            │              └────────────────┘  │
│  │  Developer       │            ▼                                  │
│  │  Identity        │   ┌──────────────────┐   ┌────────────────┐  │
│  │                  │   │  Code Analysis   │   │  Compliance    │  │
│  │  Developer       │   │                  │   │  & Privacy     │  │
│  │  DeveloperProfile│   │  FileAnalysis    │   │                │  │
│  │  DeveloperIdentity│  │  StackDetection  │   │  PDNFinding    │  │
│  │  IdentityOverride│   │  Complexity      │   │  PDNType       │  │
│  │  DailyActivity   │   │  Dependency      │   │                │  │
│  └──────────────────┘   │  Scoring         │   └────────────────┘  │
│                          │  RiskDetection   │                       │
│                          └──────────────────┘                       │
└─────────────────────────────────────────────────────────────────────┘
```

#### Context: Project Management
Owns the organisational structure. Projects group repositories; repositories are the unit of analysis. Tags are metadata overlays applied by operators, not derived from code.

#### Context: Scan Lifecycle & Orchestration
The **core domain**. A `Scan` represents one execution of the full analysis pipeline against a repository at a specific commit. The orchestrator coordinates all other contexts. Status transitions are the primary lifecycle event: `pending → running → completed | failed | cancelled`.

#### Context: VCS Integration
An **anti-corruption layer** that shields the domain from VCS provider differences. It exposes a uniform `prepare(repository, branch)` interface regardless of whether the source is Bitbucket, GitLab, GitHub, or a local filesystem path.

#### Context: Code Analysis
The analytical subdomain. Contains five independent analysis services — file analysis, stack detection, dependency parsing, complexity analysis, and the scoring + risk engines. Each is a pure function over the repository's filesystem tree plus previously computed inputs.

#### Context: Developer Identity
Resolves the hard problem of multiple git identities for a single human contributor. Applies a priority chain — manual override → email hint → name parsing — and produces a canonical username. Owns the developer aggregate with its profile, raw identities, contribution records, and daily activity series.

#### Context: Compliance & Privacy
An isolated scanning context that detects personally identifiable data (PDN) in source files using regex patterns loaded from a YAML configuration. It runs as a non-fatal stage, ensuring a failed privacy scan never blocks a completed code-quality scan.

---

### 3.2 Ubiquitous Language

| Term | Definition |
|---|---|
| **Project** | A logical grouping of one or more repositories, typically corresponding to a product or team. |
| **Repository** | A Git repository registered under a Project. It has a VCS provider (Bitbucket / GitLab / GitHub), a URL, and optional credentials. |
| **Scan** | A single execution of the full analysis pipeline on a Repository at a specific branch/commit. The primary unit of analysis output. |
| **ScanStatus** | The lifecycle state of a Scan: `pending`, `running`, `completed`, `failed`, or `cancelled`. |
| **Module** | A top-level directory within a repository, used as the granularity for contribution and complexity attribution. |
| **Developer** | The real-world person contributing to a repository, resolved from one or more raw git identities. |
| **DeveloperProfile** | The canonical representation of a Developer, holding a stable `canonical_username` across scans. |
| **DeveloperIdentity** | A raw (name, email) pair extracted from `git log`, linked to a DeveloperProfile. |
| **IdentityOverride** | A project-scoped operator instruction that forces a raw name or email to resolve to a specific canonical username. |
| **Bus Factor** | The number of developers whose simultaneous absence would critically impair the project. Computed from commit concentration. |
| **Scorecard** | A set of five domain scores (0–100) plus a weighted overall score, produced for each completed Scan. |
| **Risk** | A specific detectable quality or team-health problem, classified by type and severity (`low`, `medium`, `high`, `critical`). |
| **PDN** | Personal Data (Персональные Данные). An identifier of a real person found in source code (name, email, phone, etc.). |
| **Stack** | The technology fingerprint of a repository: project type, primary language, frameworks, package managers, CI/CD, infrastructure tools. |
| **Dependency** | A third-party package declared in a manifest file (e.g. `requirements.txt`, `package.json`), optionally enriched with licence information. |
| **Workspace** | The local filesystem directory where a repository is cloned/cached for analysis. Managed by the VCS context. |

---

### 3.3 Aggregates & Entities

#### Aggregate: `Project`
**Root:** `Project`
**Children:** `ProjectTag` (value-object-like, owned by `Project`)
**Invariants:** Project names need not be unique, but a project must exist before repositories can be registered under it.

```
Project
  ├── id, name, description, created_at, updated_at
  └── ProjectTag[]  (tag: str)
```

#### Aggregate: `Repository`
**Root:** `Repository`
**Children:** `RepositoryTag`, `RepositoryGitTag`, `RepositoryDailyActivity`, `Module`
**Invariants:** A (project_id, url) pair must be unique. A repository belongs to exactly one project. Git tags are synced (upsert + prune) on each scan.

```
Repository
  ├── id, project_id, name, url, provider_type
  ├── default_branch, clone_path, last_commit_sha
  ├── credentials_username, credentials_token
  ├── RepositoryTag[]     (tag, description, created_at)
  ├── RepositoryGitTag[]  (name, sha, message, tagged_at, ...)
  └── RepositoryDailyActivity[]  (commit_date, commit_count)
```

#### Aggregate: `Scan`
**Root:** `Scan`
**Children:** `ScanLanguage`, `ScanScore`, `ScanRisk`, `Dependency`, `DeveloperContribution`, `ScanPersonalDataFinding`
**Invariants:** A Scan always belongs to a Repository. Status transitions are one-directional. Partial results persist even on failure (stages commit independently).

```
Scan
  ├── id, repository_id, status, branch, commit_sha
  ├── total_files, total_loc, size_bytes, ...
  ├── project_type, primary_language
  ├── frameworks_json, package_managers_json, ...
  ├── has_docker, has_kubernetes, has_terraform
  ├── ScanLanguage[]             (language, loc, file_count, percentage)
  ├── ScanScore[]                (domain, score, details_json)
  ├── ScanRisk[]                 (risk_type, severity, title, description, entity_type, entity_ref)
  ├── Dependency[]               (name, version, ecosystem, dep_type, license_spdx, license_risk)
  ├── DeveloperContribution[]    (profile_id, commit_count, insertions, deletions, ...)
  └── ScanPersonalDataFinding[]  (pdn_type, file_path, line_number, matched_identifier)
```

#### Aggregate: `Developer`
**Root:** `Developer` (identity anchor)
**Profile:** `DeveloperProfile` (canonical representation)
**Children:** `DeveloperIdentity`, `DeveloperDailyActivity`, `DeveloperLanguageContribution`, `DeveloperModuleContribution`
**Invariants:** A `DeveloperProfile` has a globally unique `canonical_username`. Multiple `DeveloperIdentity` records (raw git name/email pairs) can link to a single profile.

```
Developer
  └── DeveloperProfile
        ├── canonical_username, display_name, primary_email
        ├── DeveloperIdentity[]            (raw_name, raw_email, confidence_score, is_ambiguous)
        └── DeveloperDailyActivity[]       (commit_date, commit_count)
```

#### Entity: `Language`
A shared catalogue entity. `ScanLanguage` links a `Scan` to a `Language` with scan-specific metrics (LOC, file count, percentage).

#### Entity: `Module`
Represents a top-level directory within a repository. Created on demand during scan processing. `DeveloperModuleContribution` links a developer to a module within a scan.

---

### 3.4 Value Objects

These are immutable data structures with no independent identity:

| Value Object | Where Used | Description |
|---|---|---|
| `ScanStatus` | `Scan` | Enum: `pending`, `running`, `completed`, `failed`, `cancelled` |
| `ProjectType` | `Scan` | Enum classifying the repo: `backend_service`, `frontend_application`, `library`, `cli_tool`, `infra_config`, `monolith`, `monorepo`, `unknown` |
| `ProviderType` | `Repository` | Enum: `bitbucket`, `gitlab`, `github` |
| `ScoreDomain` | `ScanScore` | Enum: the five quality domains |
| `RiskItem` | Risk engine output | Dataclass: `risk_type`, `severity`, `title`, `description`, `entity_type`, `entity_ref` |
| `StackInfo` | Stack detector output | Dataclass: project type, frameworks, CI/CD, infra tools, package managers |
| `FileAnalysisResult` | File analyser output | Dataclass: LOC totals, language map, file counts, large file flag |
| `ComplexityResult` | Complexity analyser output | Dataclass: files/functions above thresholds, top large files |
| `DeveloperStats` | Contributor aggregator output | Dataclass: per-developer contribution summary, language/module breakdown |
| `LicenseInfo` | Licence scanner output | Dataclass: SPDX identifier, raw text, risk level |
| `IdentityResult` | Identity normaliser output | Dataclass: canonical_username, confidence, is_ambiguous |

---

### 3.5 Domain Services

Domain services encapsulate domain logic that does not naturally belong to a single aggregate.

#### `ScanOrchestrator` (`app/services/scanning/orchestrator.py`)
The central domain service of the core domain. Coordinates all bounded contexts in a strict eight-stage pipeline. It is the only service that writes to the `Scan` aggregate during execution.

**Responsibilities:** stage coordination, cancellation checkpointing, partial-result persistence, error isolation per stage.

#### `IdentityNormaliser` (`app/services/identity/normalizer.py`)
Resolves raw (name, email) pairs to canonical developer usernames. Applies a priority chain: manual override → email-derived hint → name parsing. Handles Cyrillic transliteration, diacritic removal, and ambiguity detection. Returns a confidence score (1.0 to 0.7) with each resolved identity.

#### `ContributorAggregator` (`app/services/git_analytics/contributor_aggregator.py`)
Groups parsed git commits by resolved developer profile and computes per-developer statistics: commit count, insertions, deletions, active days, first/last commit, language breakdown, and module ownership percentages.

#### `ScoringEngine` (`app/services/scoring/engine.py`)
Computes a five-domain quality scorecard from the outputs of the analysis services. Weights: Code Quality 25%, Test Quality 20%, Delivery Quality 20%, Maintainability 20%, Doc Quality 15%. All scoring is rule-based and deterministic.

#### `RiskDetectionEngine` (`app/services/risks/engine.py`)
Runs twelve independent risk detectors over the combined analysis outputs. Each detector returns zero or more `RiskItem` value objects with a severity classification. Detectors are composable — `detect_risks()` aggregates all results.

**Risk types detected:**

| Risk Type | Severity Range | Detection Basis |
|---|---|---|
| `no_tests` | medium–high | test file count / ratio |
| `weak_documentation` | low–medium | doc LOC count |
| `no_ci_pipeline` | high | CI config file presence |
| `no_lockfile` | medium | package manager + lockfile check |
| `oversized_file` | medium–high | files ≥ 500 LOC count |
| `oversized_function` | medium | functions ≥ 50 LOC count |
| `knowledge_concentration` | medium–high | top-1 / top-2 commit share |
| `low_bus_factor` | medium–critical | contributor count |
| `mono_owner_language` | medium | single dev > 80% in a language |
| `mono_owner_module` | medium | single dev > 80% in a module |
| `high_complexity_module` | high | avg LOC > 400 across ≥ 3 files |
| `orphan_module` | medium | no commits in last 6 months |

#### `PDNScannerEngine` (`app/services/pii/pdn_scanner.py`)
Scans repository source files for personal data identifiers using word-boundary regex patterns loaded from `pdn_types.yaml`. Skips binary files, test files, and files over 1 MB. Returns a flat list of findings with file path, line number, and matched identifier. Runs as a non-fatal stage.

#### `RepoWorkspaceManager` (`app/services/vcs/workspace.py`)
Manages the local repository cache. Decides whether to perform a fresh `git clone` or an incremental `git fetch` on each scan invocation. Abstracts over VCS provider differences through a provider delegation pattern.

---

### 3.6 Domain Events (Implicit)

CodeRadar does not implement an explicit event bus; instead, domain events are implicit in status transitions persisted directly to the database. The worker loop observes the `Scan.status` field as its event stream.

| Implicit Event | Trigger | Observable Effect |
|---|---|---|
| Scan Requested | `POST /repositories/{id}/scan` | Scan row created with `status=pending` |
| Scan Claimed | Worker poll loop | `status=running`, `started_at` set |
| Stage Completed | Each pipeline stage | Partial results committed, status unchanged |
| Scan Completed | Stage 7 | `status=completed`, `completed_at` set |
| Scan Failed | Unhandled exception | `status=failed`, `error_message` set |
| Scan Cancelled | `POST /scans/{id}/cancel` | `cancel_requested=true`; next checkpoint raises `ScanCancelledError` |

---

## 4. Layered Architecture

CodeRadar follows a classic layered architecture, with dependencies flowing strictly inward.

```
┌────────────────────────────────────────────────────────┐
│                   Presentation Layer                   │
│  FastAPI Routers  ·  Pydantic Schemas  ·  Static SPA   │
│  app/api/v1/      ·  app/schemas/      ·  app/static/  │
└───────────────────────────┬────────────────────────────┘
                            │ depends on
┌───────────────────────────▼────────────────────────────┐
│                   Application Layer                    │
│  Scan Orchestrator  ·  Scan Queue  ·  Background Worker│
│  app/services/scanning/                                │
└───────────────────────────┬────────────────────────────┘
                            │ depends on
┌───────────────────────────▼────────────────────────────┐
│                     Domain Layer                       │
│  Analysis Services  ·  Git Analytics  ·  Scoring       │
│  Risk Engine  ·  Identity Normaliser  ·  PDN Scanner   │
│  app/services/analysis/  app/services/git_analytics/   │
│  app/services/scoring/   app/services/risks/           │
│  app/services/identity/  app/services/pii/             │
└───────────────────────────┬────────────────────────────┘
                            │ depends on
┌───────────────────────────▼────────────────────────────┐
│                 Infrastructure Layer                   │
│  SQLAlchemy Models  ·  Alembic Migrations  ·  DB Session│
│  VCS Providers  ·  Settings  ·  Logging                │
│  app/models/  ·  app/db/  ·  app/core/                 │
│  app/services/vcs/                                     │
└────────────────────────────────────────────────────────┘
```

**Key observations:**

- The **domain layer services are pure functions** over filesystem paths and data structures. They have no direct SQLAlchemy dependencies and hold no database sessions.
- The **orchestrator** is the only service that bridges the application and domain layers — it holds the session, calls domain services, and persists their outputs.
- The **API layer** never calls domain services directly; it reads from the database (via SQLAlchemy queries) and enqueues scans. This keeps the read path fast and the write path async.

---

## 5. Scan Pipeline (Core Domain Process)

The scan pipeline is a sequential eight-stage process. The orchestrator owns the session throughout and commits after each stage. Cancellation is checked at each stage boundary.

```
POST /repositories/{id}/scan
         │
         ▼  202 Accepted
   Scan created (status=pending)
         │
         ▼  Worker polls every 2 seconds
   Scan claimed  (status=running)
         │
┌────────▼─────────────────────────────────────────────┐
│  Stage 1 · Prepare Repository                        │
│  RepoWorkspaceManager → VCS Provider                 │
│  Clone or fetch; write commit_sha, clone_path        │
├────────▼─────────────────────────────────────────────┤
│  Stage 2 · File Analysis                             │
│  FileAnalyzer: traverse tree, detect languages,      │
│  count LOC, classify files (source/test/config/lock) │
│  Write: total_files, total_loc, language records     │
├────────▼─────────────────────────────────────────────┤
│  Stage 3 · Stack & Dependencies                      │
│  StackDetector: project type, frameworks, CI, infra  │
│  DependencyParser: parse manifests (8 ecosystems)    │
│  LicenceScanner: resolve SPDX licences               │
│  Write: project_type, frameworks_json, dependencies  │
├────────▼─────────────────────────────────────────────┤
│  Stage 4 · Complexity Analysis                       │
│  ComplexityAnalyzer: files ≥ 500 LOC,                │
│  functions ≥ 50 LOC, import fan-out                  │
│  (Result held in memory; used by stages 6 & 6b)      │
├────────▼─────────────────────────────────────────────┤
│  Stage 5 · Git Analytics                             │
│  GitParser: git log --format --numstat               │
│  IdentityNormaliser: name/email → canonical_username │
│  ContributorAggregator: per-developer stats          │
│  Write: developer profiles, identities,              │
│         contributions, daily activity                │
│  Stage 5b · Git Tags                                 │
│  ParseGitTags: upsert + prune RepositoryGitTag       │
├────────▼─────────────────────────────────────────────┤
│  Stage 6 · Scoring & Risks                           │
│  ScoringEngine: 5-domain weighted scorecard          │
│  RiskEngine: 12 risk detectors                       │
│  Write: ScanScore[], ScanRisk[]                      │
│  Stage 6b · Personal Data Scan (non-fatal)           │
│  PDNScanner: regex scan for personal identifiers     │
│  Write: ScanPersonalDataFinding[]                    │
├────────▼─────────────────────────────────────────────┤
│  Stage 7 · Complete                                  │
│  Set status=completed, completed_at                  │
└──────────────────────────────────────────────────────┘
```

**Fault tolerance:**

- Any unhandled exception sets `status=failed` and records `error_message`.
- Stage 5b (git tags) and Stage 6b (PDN scan) catch their own exceptions and issue a warning log without propagating — partial data is preserved.
- `cancel_requested=true` is honoured at each inter-stage checkpoint, setting `status=cancelled`.

---

## 6. Data Model

The schema is defined across 12 Alembic migrations. The 20 ORM tables fall into four clusters:

### Organisational

```
projects
  ├── project_tags         (project_id, tag)
  └── repositories
        ├── repository_tags      (repository_id, tag, description)
        ├── repository_git_tags  (repository_id, name, sha, tagged_at, ...)
        ├── repository_daily_activity  (repository_id, commit_date, commit_count)
        └── modules              (repository_id, path, name)
```

### Scan Results

```
scans  (repository_id, status, branch, commit_sha, total_loc, project_type, ...)
  ├── scan_languages           (scan_id, language_id, loc, file_count, percentage)
  ├── scan_scores              (scan_id, domain, score, details)
  ├── scan_risks               (scan_id, risk_type, severity, title, entity_type, entity_ref)
  ├── dependencies             (scan_id, name, version, ecosystem, dep_type, license_spdx, license_risk)
  └── scan_personal_data_findings  (scan_id, pdn_type, file_path, line_number, matched_identifier)
```

### Developer

```
developers
  └── developer_profiles  (developer_id, canonical_username, display_name, primary_email)
        ├── developer_identities       (profile_id, raw_name, raw_email, confidence_score)
        └── developer_daily_activity   (profile_id, commit_date, commit_count)

developer_contributions            (scan_id, profile_id, commit_count, insertions, deletions, ...)
developer_language_contributions   (scan_id, profile_id, language_id, loc_added, percentage)
developer_module_contributions     (scan_id, profile_id, module_id, commit_count, percentage)
```

### Reference & Configuration

```
languages             (name)  ← shared catalogue
identity_overrides    (project_id, raw_name, raw_email, canonical_username)
```

---

## 7. API Surface

All endpoints are prefixed `/api/v1/`. The API is self-documented via FastAPI's built-in OpenAPI schema at `/docs`.

| Router | Path Prefix | Key Endpoints |
|---|---|---|
| Projects | `/projects` | CRUD projects, list with scan summary, activity heatmap data, tags |
| Repositories | `/repositories` | CRUD repositories, trigger scan (`POST /{id}/scan → 202`), list scans, modules |
| Scans | `/scans` | Get scan detail, summary, languages, dependencies, scores, risks, developers, personal data, scan comparison (`?with=id2`), queue, cancel |
| Developers | `/developers` | Developer profile, language contributions, module contributions, identity overrides |
| Modules | `/modules` | Module ownership breakdown |
| Analytics | `/analytics` | Treemap (LOC/files by project and repository), tech map |
| Reports | `/reports` | Aggregated personal data report across repositories |

**Design patterns in the API layer:**

- Read endpoints query the database directly through SQLAlchemy, often with `joinedload` to avoid N+1.
- Write endpoints for scan creation are fire-and-forget: they enqueue a scan and return `202 Accepted` immediately.
- Comparison endpoint (`GET /scans/{id}/compare?with={id2}`) diffs two scan results across all dimensions (metrics, languages, scores, risks, developers).

---

## 8. Infrastructure & Deployment

### Process Model

The system runs as **two separate processes**:

| Process | Entry Point | Role |
|---|---|---|
| API server | `uvicorn app.main:app` | Handles HTTP requests, reads DB, enqueues scans |
| Scan worker | `python -m app.worker` | Polls DB, claims and executes scans |

This separation means the API server is never blocked by a long-running scan. The worker can be scaled horizontally (multiple workers claiming scans atomically via a compare-and-swap `UPDATE`).

### Docker Compose

```yaml
# Conceptual structure from docker-compose.yml
services:
  api:     FastAPI + Uvicorn
  worker:  Python scan worker
```

Both services share the same image and `DATABASE_URL`, which points to a shared SQLite volume (or an external PostgreSQL in production).

### Configuration

All runtime configuration is driven by environment variables (or a `.env` file) via `pydantic-settings`:

| Variable | Default | Purpose |
|---|---|---|
| `DATABASE_URL` | `sqlite:///./coderadar.db` | Database connection string |
| `REPOS_CACHE_DIR` | `./repos_cache` | Local clone storage |
| `BITBUCKET_USERNAME` / `_APP_PASSWORD` | — | Default Bitbucket credentials |
| `GITLAB_TOKEN` / `_BASE_URL` | — | Default GitLab credentials |
| `GITHUB_TOKEN` | — | Default GitHub credential |
| `GIT_HISTORY_SCAN_LIMIT` | `0` (unlimited) | Max commits to parse per scan |
| `ENABLE_LICENSE_API_ENRICHMENT` | `true` | Call PyPI/crates.io/etc. for licence data |
| `PDN_TYPES_CONFIG` | `config/pdn_types.yaml` | Path to personal data type definitions |
| `LOG_LEVEL` | `INFO` | structlog output level |

---

## 9. Quality & Testing

### Test Coverage (10 modules)

| Test File | Domain Area |
|---|---|
| `test_complexity.py` | Complexity analyser |
| `test_contributor_aggregator.py` | Git analytics — contributor aggregation |
| `test_dependency_parser.py` | Dependency parsing (all ecosystems) |
| `test_file_analyzer.py` | File analysis, language detection |
| `test_git_parser.py` | Git log parsing, rename handling |
| `test_identity.py` | Identity normalisation, transliteration |
| `test_pdn_scanner.py` | Personal data detection |
| `test_risks.py` | Risk detection engine (all 12 types) |
| `test_scoring.py` | Scoring engine (all 5 domains) |
| `test_stack.py` | Stack detection heuristics |
| `test_source_links.py` | Source URL construction per provider |

### CI/CD

GitHub Actions runs tests on push and pull request. A separate Docker workflow builds and pushes the container image.

### Structural Constraints

- **No circular imports.** Domain services (`app/services/`) do not import from `app/api/` or `app/models/`. The orchestrator is the sole bridge.
- **Schema separation.** Pydantic schemas (`app/schemas/`) are entirely separate from SQLAlchemy models (`app/models/`), preventing ORM leakage into the API layer.
- **Migration safety.** All schema changes go through Alembic. The 12-version history covers the full evolution of the data model.

---

*Document generated from source analysis of `coderadar-master` — March 2026.*

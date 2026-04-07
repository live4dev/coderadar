# Plan: Repository Dependency License Inventory

## Goal

Extend the existing dependency scanning system to implement a comprehensive license inventory module matching the spec in `docs/todo/licences.md`. The system must cover multiple ecosystems, produce richer license metadata (confidence, source, discovery mode), and expose JSON + CSV reports via new API endpoints.

---

## Current State

| Component | What exists |
|---|---|
| `dependency_parser.py` | Parses package.json, requirements*.txt, pyproject.toml, go.mod, Cargo.toml, pom.xml, Gemfile (manifest-only, `declared_only`) |
| `license_scanner.py` | Offline scanning of npm lockfile, pip dist-info, cargo vendor, go vendor, maven poms, ruby gemspec vendor; API enrichment (PyPI, crates.io, RubyGems, Maven Central); returns `LicenseInfo(spdx, raw, risk, is_direct)` |
| `Dependency` model | `name, version, dep_type, manifest_file, ecosystem, license_spdx, license_raw, license_risk, is_direct` |
| API | `GET /scans/{id}/dependencies` → `DependencyOut`; `GET /scans/{id}/license-summary` → counts |

---

## Changes

### 1. DB Migration — `alembic/versions/014_extend_dependency_license_fields.py`

Add to `dependencies` table:

| Column | Type | Default | Purpose |
|---|---|---|---|
| `license_expression` | TEXT | NULL | SPDX compound expression (e.g. `MIT OR Apache-2.0`) |
| `license_confidence` | VARCHAR(16) | `unknown` | `high` / `medium` / `low` / `unknown` |
| `license_source` | VARCHAR(64) | NULL | Where license data came from |
| `license_notes` | TEXT | NULL | Ambiguity / dual-license notes |
| `discovery_mode` | VARCHAR(32) | `unknown` | `declared_only` / `locked` / `resolved` / `installed` / `unknown` |
| `is_optional_dependency` | BOOLEAN | FALSE | Optional dependency flag |
| `is_private` | BOOLEAN | FALSE | Private/internal package |
| `package_manager` | VARCHAR(64) | NULL | Specific PM (e.g. `yarn`, `pnpm`, `poetry`) |

### 2. `app/models/dependency.py` — add new mapped columns

### 3. `app/services/analysis/license_scanner.py` — enrich `LicenseInfo`

Extend dataclass:
```python
@dataclass
class LicenseInfo:
    spdx: str | None
    raw: str | None
    risk: str
    is_direct: bool = True
    expression: str | None = None      # NEW
    confidence: str = "unknown"        # NEW: high/medium/low/unknown
    source: str | None = None          # NEW: lockfile/dist_info/manifest/vendor_manifest/api_enrichment/license_file
    notes: str | None = None           # NEW
```

Update each scanner function to fill `confidence` and `source`:

| Function | confidence | source |
|---|---|---|
| `_scan_npm` (lockfile) | `high` | `lockfile` |
| `_scan_pip_dist_info` | `high` | `dist_info` |
| `_scan_pyproject` | `medium` | `manifest` |
| `_scan_cargo_vendor` | `high` | `vendor_manifest` |
| `_scan_go_vendor` | `medium` | `license_file` |
| `_scan_maven_poms` | `medium` | `manifest` |
| `_scan_ruby_vendor` | `medium` | `vendor_gemspec` |
| API enrichers | `high` | `api_enrichment` |

Detect SPDX compound expressions (`OR`, `AND`) and populate `expression` field without overwriting `spdx`.

### 4. `app/services/analysis/dependency_parser.py` — extend with lockfile parsers

Extend `ParsedDependency`:
```python
@dataclass
class ParsedDependency:
    name: str
    version: str | None
    dep_type: str
    manifest_file: str
    ecosystem: str
    is_direct: bool = True
    is_optional: bool = False          # NEW
    is_private: bool = False           # NEW
    discovery_mode: str = "declared_only"  # NEW
    package_manager: str | None = None  # NEW (yarn/pnpm/poetry/etc.)
```

Add new parser functions (all return `discovery_mode="locked"`):

| Function | File parsed | Ecosystem |
|---|---|---|
| `_parse_poetry_lock` | `poetry.lock` | pip/poetry |
| `_parse_pipfile_lock` | `Pipfile.lock` | pip/pipenv |
| `_parse_yarn_lock` | `yarn.lock` | npm/yarn |
| `_parse_pnpm_lock` | `pnpm-lock.yaml` | npm/pnpm |
| `_parse_cargo_lock` | `Cargo.lock` | cargo |
| `_parse_gemfile_lock` | `Gemfile.lock` | bundler |
| `_parse_composer` | `composer.json` + `composer.lock` | composer |
| `_parse_nuget` | `*.csproj` files | nuget |

Lockfile parsers override manifest parsers for the same package (exact versions take precedence). `parse_all()` deduplicates: for each (name, ecosystem), prefer `locked` over `declared_only`.

### 5. `app/services/analysis/license_report.py` — NEW

```python
def build_license_report(scan, deps: list[Dependency], repo_name: str) -> dict
def build_license_csv(deps: list[Dependency]) -> str
```

**`build_license_report`** returns the structure from the spec:
- `repository`, `scan_time_utc`, `scanner_version`, `ecosystems`, `packages[]`
- `summary.total_packages`, `by_license`, `by_classification`
- `problems[]` (missing license, ambiguous, private unknown)

License classification (configurable via internal map):
- `permissive`: MIT, Apache-2.0, BSD-*, ISC, CC0-1.0, Unlicense, WTFPL, MPL-2.0, 0BSD, PSF-2.0, Zlib
- `weak_copyleft`: LGPL-*, MPL-2.0, EUPL-*
- `strong_copyleft`: GPL-*, AGPL-*
- `proprietary`: known proprietary identifiers
- `unknown`: everything else

**`build_license_csv`** returns a flat CSV with all package fields as columns.

### 6. `app/services/scanning/orchestrator.py` — update Stage 3

Pass new fields when persisting `Dependency` rows:
```python
db.add(Dependency(
    ...existing fields...,
    license_expression=lic.expression if lic else None,
    license_confidence=lic.confidence if lic else "unknown",
    license_source=lic.source if lic else None,
    license_notes=lic.notes if lic else None,
    discovery_mode=d.discovery_mode,
    is_optional_dependency=d.is_optional,
    is_private=d.is_private,
    package_manager=d.package_manager,
))
```

### 7. `app/schemas/scan.py` — update schemas

`DependencyOut` — add new fields:
- `license_expression: str | None`
- `license_confidence: str = "unknown"`
- `license_source: str | None`
- `license_notes: str | None`
- `discovery_mode: str = "unknown"`
- `is_optional_dependency: bool = False`
- `is_private: bool = False`
- `package_manager: str | None`

`DependencyLicenseSummaryOut` — add classification counts:
- `permissive_count: int`
- `weak_copyleft_count: int`
- `strong_copyleft_count: int`
- `proprietary_count: int`
- `by_classification: dict[str, int]`

Add new schema `LicenseReportOut` for the full report structure.

### 8. `app/api/v1/scans.py` — add endpoints

```
GET /scans/{scan_id}/license-report
    → LicenseReportOut (JSON)

GET /scans/{scan_id}/license-report.csv
    → StreamingResponse (text/csv)
```

### 9. Tests

- `tests/test_license_scanner.py` — confidence/source per scanner, compound expression detection
- `tests/test_dependency_parser.py` — extended with lockfile parser fixtures
- `tests/test_license_report.py` — report builder JSON structure + CSV
- `tests/fixtures/` — fixture lockfiles:
  - `poetry.lock`, `Pipfile.lock`, `yarn.lock`, `pnpm-lock.yaml`
  - `Cargo.lock`, `Gemfile.lock`, `composer.lock`, `example.csproj`

---

## Implementation Order

1. Alembic migration + model update
2. LicenseInfo + license_scanner.py
3. ParsedDependency + dependency_parser.py (lockfile parsers)
4. license_report.py
5. Orchestrator update
6. Schema update
7. API endpoint update
8. Tests + fixtures

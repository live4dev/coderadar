# Repository Dependency License Inventory

## Goal

Implement a dependency license inventory module for repositories.
The module must detect all dependencies used by a repository, determine their licenses as completely as possible, and produce a normalized machine-readable report.

The solution must work across multiple ecosystems.
For some languages and package managers, it is acceptable and expected to resolve the full dependency graph from lockfiles or package manager metadata.
If direct static parsing is insufficient, the scanner may invoke package manager commands or export dependency trees to collect all packages.

The primary objective is **completeness and reproducibility**, not just a quick approximation.

---

## Core Requirements

### 1. Scan target

For each repository, the scanner must:

* detect the language / ecosystem
* detect package manager(s)
* detect manifest and lock files
* extract both:

  * direct dependencies
  * transitive dependencies whenever possible
* determine license information for every discovered package
* produce a unified output report

The scanner must support monorepos and repositories containing multiple package managers.

---

### 2. Supported ecosystems

Start with at least the following ecosystems:

* Python

  * `pip`
  * `poetry`
  * `pipenv`
  * `uv` if possible
* JavaScript / TypeScript

  * `npm`
  * `yarn`
  * `pnpm`
* Java

  * `maven`
  * `gradle`
* .NET

  * `nuget`
* Go

  * `go modules`
* Rust

  * `cargo`
* PHP

  * `composer`
* Ruby

  * `bundler`
* Linux / system packages if present in container/build files

  * optional second phase

Design the architecture so more ecosystems can be added later via pluggable scanners.

---

### 3. Detection strategy

For each repository, detect ecosystems using common files, for example:

* Python:

  * `requirements.txt`
  * `requirements-dev.txt`
  * `pyproject.toml`
  * `poetry.lock`
  * `Pipfile`
  * `Pipfile.lock`
  * `uv.lock`
* JS/TS:

  * `package.json`
  * `package-lock.json`
  * `yarn.lock`
  * `pnpm-lock.yaml`
* Java:

  * `pom.xml`
  * `build.gradle`
  * `build.gradle.kts`
  * `settings.gradle`
* .NET:

  * `*.csproj`
  * `Directory.Packages.props`
  * `packages.lock.json`
* Go:

  * `go.mod`
  * `go.sum`
* Rust:

  * `Cargo.toml`
  * `Cargo.lock`
* PHP:

  * `composer.json`
  * `composer.lock`
* Ruby:

  * `Gemfile`
  * `Gemfile.lock`

The scanner must support multiple manifests in one repository.

---

## Dependency Resolution Requirements

### 4. Resolution modes

Implement two complementary modes:

#### A. Static mode

Parse manifests and lockfiles directly without installing packages.

Use this mode first when possible.

#### B. Resolver / export mode

If static parsing is insufficient to get the full dependency graph or package metadata, run package-manager-native commands to export the dependency tree.

Examples:

* Python:

  * `pip-licenses`
  * `pipdeptree`
  * `poetry export`
  * `poetry show --tree`
  * `pip list --format=json`
* Node:

  * `npm ls --all --json`
  * `yarn list`
  * `pnpm list --json --depth Infinity`
* Maven:

  * `mvn dependency:tree`
* Gradle:

  * `gradle dependencies`
* .NET:

  * `dotnet list package --include-transitive --format json`
* Go:

  * `go list -m -json all`
* Rust:

  * `cargo metadata`
* PHP:

  * parse `composer.lock`
* Ruby:

  * `bundle list` / lockfile parsing

If commands require dependency restore, do it in an isolated temporary environment.

---

### 5. Completeness rules

The report must classify each dependency by discovery quality:

* `declared_only` — found only in manifest
* `locked` — found in lockfile
* `resolved` — found through dependency graph export / metadata command
* `installed` — found from actual installed environment
* `unknown` — package identified but incomplete metadata

Prefer `resolved` or `locked` over `declared_only`.

For ecosystems with lockfiles, prioritize lockfile-based exact versions.

For ecosystems without reliable lockfiles, use the best available reproducible source and mark confidence accordingly.

---

## License Collection Requirements

### 6. License sources

For each package, attempt to determine license from the following sources, in priority order:

1. package manager metadata / registry metadata
2. lockfile metadata if present
3. installed package metadata
4. package manifest fields
5. package source repository metadata if already known
6. license files if package source is vendored in repo
7. fallback heuristic detection

Do not rely only on a single field called `license`.
Some packages use:

* `license`
* `licenses`
* SPDX expressions
* custom strings
* referenced files
* missing values

The implementation must normalize raw values without losing originals.

---

### 7. Normalize license values

For every discovered dependency, return:

* `license_raw` — original raw value
* `license_normalized` — normalized SPDX identifier if determinable
* `license_expression` — SPDX expression if applicable
* `license_confidence` — `high`, `medium`, `low`, `unknown`
* `license_source` — where the value came from
* `license_notes` — ambiguity, custom terms, missing mapping, dual licensing, etc.

Examples:

* `"MIT"` → normalized `MIT`
* `"Apache 2.0"` → normalized `Apache-2.0`
* `"BSD"` → ambiguous, confidence low
* `"MIT OR Apache-2.0"` → expression preserved
* `"SEE LICENSE IN LICENSE.txt"` → raw preserved, normalized may remain null

Keep a mapping layer for common non-standard names to SPDX.

---

### 8. Handle difficult cases

The scanner must explicitly handle:

* missing license field
* multiple license fields
* dual-licensed packages
* custom enterprise licenses
* deprecated metadata formats
* packages with no version resolved
* vendored dependencies
* git-based dependencies
* path/local dependencies
* workspace packages
* private/internal packages
* forked packages

For internal/private packages, mark them as:

* `is_private = true`
* `license_normalized = null` unless found
* `license_status = internal_or_unknown`

---

## Output Format

### 9. Output schema

Produce a normalized JSON report per repository.

Example structure:

```json
{
  "repository": "repo-name",
  "scan_time_utc": "2026-04-02T12:00:00Z",
  "scanner_version": "1.0.0",
  "ecosystems": ["python", "npm"],
  "packages": [
    {
      "name": "requests",
      "version": "2.32.0",
      "ecosystem": "python",
      "package_manager": "pip",
      "dependency_type": "direct",
      "is_transitive": false,
      "is_dev_dependency": false,
      "is_optional_dependency": false,
      "source_manifest": "requirements.txt",
      "discovery_mode": "locked",
      "license_raw": "Apache 2.0",
      "license_normalized": "Apache-2.0",
      "license_expression": "Apache-2.0",
      "license_confidence": "high",
      "license_source": "package_metadata",
      "license_notes": null,
      "homepage_url": "https://...",
      "repository_url": "https://...",
      "is_private": false
    }
  ],
  "summary": {
    "total_packages": 120,
    "licensed_packages": 112,
    "unknown_license_packages": 8,
    "by_license": {
      "MIT": 54,
      "Apache-2.0": 31,
      "BSD-3-Clause": 7
    }
  },
  "problems": [
    {
      "type": "missing_license",
      "package": "some-package",
      "details": "No license metadata found"
    }
  ]
}
```

Also generate a CSV export with flattened rows for easy analysis.

---

## Repository-Level Summary

### 10. In addition to package rows, generate summary fields

For each repository, generate:

* total dependency count
* direct dependency count
* transitive dependency count
* packages with known license
* packages with unknown license
* packages with ambiguous license
* unique normalized licenses
* copyleft packages count
* permissive packages count
* custom / proprietary packages count

If possible, classify licenses into broad categories:

* permissive
* weak copyleft
* strong copyleft
* proprietary/custom
* unknown

This classification must be configurable via a mapping table.

---

## Architecture Requirements

### 11. Design

Implement the feature as a modular scanner framework.

Suggested internal modules:

* `repo_detector`
* `ecosystem_detectors`
* `manifest_parsers`
* `lockfile_parsers`
* `resolver_runners`
* `license_normalizer`
* `report_builder`
* `risk_classifier`

Each ecosystem should have its own adapter implementing a common interface, for example:

* detect()
* collect_declared_dependencies()
* collect_locked_dependencies()
* resolve_full_graph()
* collect_license_metadata()

---

### 12. Execution model

The scanner must support:

* scanning one repository
* scanning many repositories in batch
* running in CI
* running locally for enrichment
* caching results where appropriate

Avoid unnecessary installs if lockfile parsing is sufficient.

Use temp directories and isolate command execution.

---

### 13. Performance and reliability

The implementation must:

* fail softly per ecosystem, not per whole repository
* record partial results even if one resolver fails
* capture stderr/stdout from package manager commands
* set timeouts for external commands
* handle malformed lockfiles gracefully
* produce diagnostic logs

For every package row, preserve enough provenance to explain where the data came from.

---

## Priority Strategy by Ecosystem

### 14. Preferred strategy examples

#### Python

Priority:

1. parse `poetry.lock`, `Pipfile.lock`, `uv.lock`, `requirements*.txt`
2. if needed, create isolated env and run:

   * `pip-licenses`
   * `pipdeptree --json-tree`
   * or inspect installed metadata
3. collect package metadata from installed distributions when available

Important: Python often requires installed distributions to get reliable license fields.
Implement this path carefully.

#### Node.js

Priority:

1. parse lockfile (`package-lock.json`, `pnpm-lock.yaml`, `yarn.lock`)
2. export full tree using package manager command
3. inspect `package.json` metadata for each dependency when available

#### Java

Priority:

1. use package manager export commands
2. parse dependency tree
3. enrich licenses from artifact metadata if available

#### .NET

Priority:

1. `dotnet list package --include-transitive --format json`
2. enrich package metadata

#### Go

Priority:

1. `go list -m -json all`
2. enrich from module metadata

#### Rust

Priority:

1. `cargo metadata`
2. enrich using crate metadata and lockfile

---

## Edge Cases

### 15. Must support

* monorepo with multiple services
* workspace dependencies
* frontend + backend in same repository
* duplicate package names across ecosystems
* same package with multiple versions
* no lockfile present
* lockfile out of sync with manifest
* build-generated dependencies not present in source tree
* optional and dev dependencies where distinguishable

Do not silently merge packages from different ecosystems.

Use composite keys like:

* ecosystem + package manager + name + version + manifest path

---

## Testing Requirements

### 16. Add tests for

* normalization of common license aliases
* dual-license expressions
* missing license metadata
* private dependencies
* monorepo scanning
* partial failures of external resolver commands
* output stability
* parsing of representative sample lockfiles for each supported ecosystem

Include fixture repositories or fixture lockfiles for tests.

---

## Deliverables

### 17. Deliver

1. implementation of the dependency license scanner
2. JSON schema for the output
3. CSV export
4. tests
5. documentation:

   * supported ecosystems
   * data sources
   * known limitations
   * confidence model
6. examples of reports
7. clear extension guide for adding a new ecosystem scanner

---

## Important Decision Rules

### 18. Rules to follow

* Prefer exact resolved versions over loose declared versions
* Never drop raw license values even if normalization fails
* Preserve ambiguity instead of forcing wrong SPDX mapping
* Return partial results instead of failing the whole scan
* Make it obvious which packages were discovered statically vs resolved dynamically
* Make command-based resolution optional but supported
* Design for future integration into a larger repository analytics platform

---

## Expected Outcome

At the end, for each repository we should be able to answer:

* what packages are used
* which versions are actually present
* which licenses they use
* where license data came from
* how reliable that license identification is
* which packages still require manual review


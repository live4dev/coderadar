# Repository Scores Tab

The **Scores** tab appears on the scan detail page (`/ui/projects/{project_id}/repos/{repo_id}/scans/{scan_id}`) and shows a quality scorecard computed for a specific scan.

> **Work in progress** — The scoring model is under active development. Weights, thresholds, and signal definitions may change between scans.

---

## Overview card

At the top of the tab a large numeric badge shows the **Overall** score (0–100). A wide progress bar below it visualises the score. The badge and bar are colour-coded:

| Colour | Range |
|--------|-------|
| Green  | ≥ 70  |
| Yellow | 40–69 |
| Red    | < 40  |

---

## Domain scores table

Below the overall card, a table lists the five quality domains. Each row shows:

- the domain name and its **weight** in the overall score
- a colour-coded progress bar and numeric score
- **signal chips** — the individual penalties and bonuses that contributed to the score, sourced from the `details` field of the API response

Signal chips are colour-coded: green with an ↑ arrow for positive contributions, red with a ↓ arrow for penalties.

| Domain | Weight in Overall |
|--------|------------------|
| Code Quality | 25% |
| Test Quality | 20% |
| Delivery Quality | 20% |
| Maintainability | 20% |
| Doc Quality | 15% |

---

## How each domain is scored

### Code Quality (0–100, starts at 100)

Penalties are applied for structural problems; bonuses are awarded for tooling.

| Signal | Effect |
|--------|--------|
| Files ≥ 500 LOC | −5 per file, capped at −30 |
| Functions ≥ 50 LOC | −3 per function, capped at −20 |
| Average file LOC > 300 | −10 |
| Linters detected in stack | +10 |
| Formatters detected in stack | +5 |

### Test Quality (0–100, starts at 0)

| Signal | Effect |
|--------|--------|
| Any test files present | +50 |
| Test-to-source ratio ≥ 30% | +30 |
| Test-to-source ratio ≥ 15% | +15 |
| Test-to-source ratio ≥ 5% | +5 |

### Doc Quality (0–100, starts at 0)

Points are awarded for the presence of specific documentation artefacts. Raw points are then normalised so that 75 raw points = 100.

| Artefact | Raw points |
|----------|-----------|
| README file | 20 |
| Install/setup docs | 15 |
| Architecture docs or ADRs | 15 |
| CHANGELOG or HISTORY | 15 |
| Runbook | 10 |

### Delivery Quality (0–100, starts at 0)

| Signal | Effect |
|--------|--------|
| CI pipeline config present | +40 |
| Dockerfile present | +30 |
| Kubernetes, Helm, or Terraform config present | +20 |
| Dependency manifest present (requirements.txt, package.json, go.mod, Cargo.toml, pom.xml, …) | +10 |
| All dependency versions are pinned / exact | +10 |

### Maintainability (0–100, starts at 60)

| Signal | Effect |
|--------|--------|
| Single contributor | −20 |
| 3+ contributors | +10 |
| Top contributor has > 80% of commits | −20 |
| Top contributor has > 60% of commits | −10 |
| More than 10 files above complexity threshold | −10 |
| Any test files present | +10 |

### Overall

```
overall = code_quality × 0.25
        + test_quality  × 0.20
        + doc_quality   × 0.15
        + delivery      × 0.20
        + maintainability × 0.20
```

---

## Signal chips per domain

The frontend parses the `details` JSON string from each score record and renders inline signal chips directly under the score bar.

### Code Quality signals

| Key | Chip text |
| --- | --- |
| `large_files_penalty` | Large files (≥500 LOC): N file(s) — −X pts |
| `large_functions_penalty` | Large functions (≥50 LOC) — −X pts |
| `avg_loc_penalty` | Average file LOC > 300 — −10 pts |
| `avg_loc_ok` | Average file LOC < 150 — within healthy range |
| `linters` | Linters detected: … — +10 pts |
| `formatters` | Formatters detected: … — +5 pts |

### Test Quality signals

| Key | Chip text |
| --- | --- |
| `has_tests: false` | No test files found |
| `has_tests: true` | Test files present — +50 pts |
| `test_ratio` | Test-to-source ratio: N% [— +X pts] |

### Doc Quality signals

| Key | Chip text |
| --- | --- |
| `has_docs: false` | No documentation files found |
| `has_readme` | README present — +20 pts |
| `has_install_docs` | Install / setup docs — +15 pts |
| `has_architecture_docs` | Architecture docs or ADRs — +15 pts |
| `has_changelog` | CHANGELOG or HISTORY — +15 pts |
| `has_runbook` | Runbook — +10 pts |

### Delivery Quality signals

| Key | Chip text |
| --- | --- |
| `has_ci` + `ci_provider` | CI pipeline (provider) — +40 pts |
| `has_docker` | Dockerfile present — +30 pts |
| `has_infra_as_code` | Kubernetes / Helm / Terraform config — +20 pts |
| `has_requirements` + `requirements_file` | Dependency manifest (file) — +10 pts |
| `requirements_pinned: true` | Dependencies have pinned versions — +10 pts |
| `requirements_pinned: false` | Dependency versions are not fully pinned |

### Maintainability signals

| Key | Chip text |
| --- | --- |
| `single_dev` | Single contributor — −20 pts |
| `multi_dev` | 3+ contributors — +10 pts |
| `top_dev_share` | Top contributor share: N% [— −X pts] |
| `high_complexity` | High complexity: >10 files above threshold — −10 pts |

---

## Data source

The tab fetches scores from the REST API:

```
GET /api/v1/scans/{scan_id}/scores
```

Response shape:

```json
[
  { "domain": "overall",           "score": 74.3, "details": "{...}" },
  { "domain": "code_quality",      "score": 85.0, "details": "{...}" },
  { "domain": "test_quality",      "score": 65.0, "details": "{...}" },
  { "domain": "doc_quality",       "score": 53.3, "details": "{...}" },
  { "domain": "delivery_quality",  "score": 70.0, "details": "{...}" },
  { "domain": "maintainability",   "score": 60.0, "details": "{...}" }
]
```

The `details` field is a JSON string containing the intermediate signals that contributed to the score (penalties, bonuses, ratios). It is stored in `scan_scores.details` and can be used for tooltips or debugging.

---

## Implementation files

| File | Role |
|------|------|
| [app/services/scoring/engine.py](app/services/scoring/engine.py) | Scoring logic — `compute_scorecard()` |
| [app/models/scan_score.py](app/models/scan_score.py) | `ScanScore` ORM model, `ScoreDomain` enum |
| [app/schemas/scan.py](app/schemas/scan.py) | `ScanScoreOut` Pydantic schema |
| [app/api/v1/scans.py](app/api/v1/scans.py) | `GET /{scan_id}/scores` endpoint |
| [app/static/js/tabs/scores.js](app/static/js/tabs/scores.js) | Frontend tab renderer |

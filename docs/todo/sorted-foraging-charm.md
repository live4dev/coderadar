# Developer Scoring System

## Context

The backlog item "Developers ratings" in `docs/todos.md` requires a multi-dimensional developer scoring system. The design is already specified in `docs/todo/developer_scoring.md`: an anti-gaming, percentile-normalized scorecard with dimensions for implementation, consistency, and quality. The system must resist common gaming patterns (micro-commit spam, LOC inflation) by using log-scaling, weekly caps, and cohort-relative percentile normalization rather than raw counts.

**Constraint:** The current data is entirely git-based. There are no PR reviews, CI coverage delta, or revert tracking yet. The initial implementation uses what is available: commit counts, LOC (insertions/deletions), active days, daily commit history, and per-language LOC. The design is kept extensible for when PR data arrives.

---

## Dimensions (using available data)

### 1. Implementation Score (weight 40%)
Measures meaningful output volume, hardened against spam.

Raw metrics per developer:
- `commits_per_week` = `total_commits / max(active_weeks, 1)` — weekly rate (caps benefit of burst activity)
- `effective_loc` = `log(1 + insertions + deletions)` — log-scaled to reduce bulk-change inflation

Formula: `S_impl = 0.5 * P(commits_per_week) + 0.5 * P(effective_loc)`

### 2. Consistency Score (weight 35%)
Measures sustained, regular contribution over time.

Raw metrics:
- `active_weeks_ratio` = `active_weeks / total_calendar_weeks` (weeks since first commit)
- `commit_entropy` = normalized entropy of weekly commit distribution — high entropy = irregular bursts

Formula: `S_cons = 0.7 * P(active_weeks_ratio) + 0.3 * P(commit_entropy)`

### 3. Quality Proxy Score (weight 25%)
Proxy for quality until real coverage/revert data is available.

Raw metrics:
- `test_loc_ratio` = `test_lang_loc_added / max(total_loc_added, 1)` (from `DeveloperLanguageContribution`, test languages = Python test files, JS test patterns, etc.)

Formula: `S_qual = P(test_loc_ratio)` — developers who consistently contribute test code score higher

### Overall Score
`S_overall = 0.40 * S_impl + 0.35 * S_cons + 0.25 * S_qual`

`P(x)` = percentile rank within cohort → outputs 0–100

---

## Architecture

### New files

**`app/services/scoring/developer_scorer.py`**  
Core scoring logic. Takes a list of `DeveloperScoringInput` (aggregated from DB) and returns `DeveloperScorecardResult` per developer. All percentile normalization is computed across the full cohort list passed in, so the function is pure and testable.

Key function: `compute_developer_scores(developers: list[DeveloperScoringInput]) -> list[DeveloperScorecardResult]`

**`app/models/developer_score.py`**  
SQLAlchemy model `DeveloperScore` — persisted per developer per project (or globally when `project_id=None`).

```python
class DeveloperScore(Base):
    __tablename__ = "developer_scores"
    id: int (PK)
    developer_id: int (FK developers.id, CASCADE)
    project_id: int | None (FK projects.id, CASCADE, nullable)
    implementation_score: float
    consistency_score: float
    quality_score: float
    overall_score: float
    details: str (JSON)
    computed_at: datetime
    __table_args__: UniqueConstraint(developer_id, project_id)
```

**`alembic/versions/004_developer_scores.py`**  
Migration that creates the `developer_scores` table.

### Modified files

**`app/models/__init__.py`**  
Add `DeveloperScore` to imports.

**`app/api/v1/developers.py`**  
- Add `GET /{developer_id}/score?project_id=` endpoint — returns stored score (or triggers compute if missing)
- Add `score` field to `DeveloperListOut` when available

**`app/schemas/developer.py`**  
Add `DeveloperScoreOut` Pydantic schema.

**`app/services/scoring/` (existing `engine.py`)**  
No changes needed — repository scoring and developer scoring are independent.

### Where scoring is triggered

Scores are computed in two ways:
1. **On scan completion** — after a scan stores `DeveloperContribution` records, a call to `recompute_project_developer_scores(project_id, db)` refreshes scores for all devs in that project (upsert by `developer_id + project_id`).
2. **On-demand via API** — if no score exists yet for a developer+project, compute and store it before returning.

The `recompute_project_developer_scores` utility function lives in `app/services/scoring/developer_scorer.py` and is called from the scan service (`app/services/scan_service.py` or wherever scan completion is handled).

---

## Data Flow

```
DeveloperContribution (DB)
DeveloperDailyActivity (DB)
DeveloperLanguageContribution (DB)
        ↓
  build DeveloperScoringInput list (per project cohort)
        ↓
  compute_developer_scores() → percentile normalization across cohort
        ↓
  upsert DeveloperScore records (developer_id + project_id)
        ↓
  GET /developers/{id}/score → return DeveloperScoreOut
```

---

## Critical Files

| File | Change |
|---|---|
| `app/services/scoring/developer_scorer.py` | **New** — core scoring logic |
| `app/models/developer_score.py` | **New** — DB model |
| `alembic/versions/004_developer_scores.py` | **New** — migration |
| `app/models/__init__.py` | Add DeveloperScore import |
| `app/api/v1/developers.py` | Add `/score` endpoint |
| `app/schemas/developer.py` | Add DeveloperScoreOut schema |
| Scan service (wherever scan finishes) | Call recompute after scan |

---

## Anti-Gaming Measures Implemented

- **Weekly rate cap**: `commits_per_week` is capped — mass-commit bursts don't scale infinitely
- **Log-scaling LOC**: `log(1 + loc)` — bulk formatting commits don't dominate
- **Percentile normalization**: scores are relative to cohort, not absolute, preventing gaming by targeting a raw threshold
- **Consistency metric**: rewards regularity over time, not end-of-window spikes
- **Test contribution**: rewards those who add tests alongside code

---

## Verification

1. Run existing tests: `pytest tests/`
2. Run migration: `alembic upgrade head`
3. Trigger a scan for any existing project → check `developer_scores` table is populated
4. Call `GET /api/v1/developers/{id}/score?project_id={pid}` → verify JSON response with all 4 score fields
5. Check that a developer with all commits in one week scores lower on consistency than one with spread contributions

---

## Note on CLAUDE.md

Before implementation begins, copy this plan to `docs/plans/developer_scoring.md` per the project instruction.

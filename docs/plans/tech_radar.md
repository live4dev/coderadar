# Tech Radar from Sources

## Context

CodeRadar already collects the raw material for a tech radar — languages, frameworks, dependencies, CI providers, and infrastructure tools — from every repository scan. The goal is to surface this as a **data-driven Tech Radar**: a four-ring (Adopt / Trial / Assess / Hold), four-quadrant map that tells teams what to lean into and what to phase out, generated automatically from scan signals and refined by manual overrides.

Inspired by the Habr/Kuper article: the radar is a **living process**, not a static picture. Auto-inference keeps it current; the override layer lets humans apply organizational judgment.

Scope: **global by default** (all projects), filterable by project. Ring placement is **auto-computed with manual override support** (same pattern as the existing `IdentityOverride` model). Blips come from **Languages, Frameworks, Infrastructure tools, and top Dependencies**.

---

## Ring Classification Algorithm

All ring placement starts from aggregated `tech_counts` built from the latest completed scan per repo (same query pattern as `analytics.py:_latest_scan_per_pr()`).

| Ring | Threshold | Notes |
|------|-----------|-------|
| Adopt | ≥25% of repos OR ≥10 repos | Widely proven across the codebase |
| Trial | 5–25% / 2–9 repos | Gaining traction, worth committing to |
| Assess | 1 repo or <5% | Experimental, too early to generalize |
| Hold | (auto signals below) | Phase out or avoid |

**Automatic Hold signals:**
- `Dependency.license_risk = "high"` → dependency goes to Hold
- Average `ScanScore.overall < 35` across repos using this technology → demote one ring + flag for review
- Framework or dependency appears only in repos tagged `inactive`

Manual overrides (stored in `tech_radar_overrides` table) take precedence over all computed rings.

## Quadrant Classification

| Quadrant | Source fields |
|----------|--------------|
| **Languages** | `ScanLanguage.language.name` aggregated across scans |
| **Frameworks** | `Scan.frameworks_json` (detected by `stack_detector.py`) |
| **Infrastructure & DevOps** | `has_docker`, `has_kubernetes`, `has_terraform`, `ci_provider`, `infra_tools_json`, `package_managers_json` |
| **Dependencies & Libraries** | Top N `Dependency` records by `COUNT(DISTINCT scan.repository_id)`, grouped by `(name, ecosystem)` |

---

## Implementation Plan

### Step 1 — New Model: `TechRadarOverride`

**File:** `/app/models/tech_radar_override.py`

```python
class TechRadarOverride(Base):
    id: int (PK)
    tech_name: str        # e.g. "React", "Python", "Docker"
    quadrant: str         # "languages" | "frameworks" | "infrastructure" | "dependencies"
    ring: str             # "adopt" | "trial" | "assess" | "hold"
    project_id: int | None  # NULL = global override
    notes: str | None     # rationale for human reviewers
    created_at: datetime
    updated_at: datetime
```

Add to `/app/models/__init__.py`.

### Step 2 — Alembic Migration (014)

**File:** `/alembic/versions/014_add_tech_radar_overrides.py`

Creates `tech_radar_overrides` table with the above schema.

### Step 3 — New Schemas

**File:** `/app/schemas/tech_radar.py`

```python
class TechRadarBlip(BaseModel):
    name: str
    quadrant: str       # "languages" | "frameworks" | "infrastructure" | "dependencies"
    ring: str           # "adopt" | "trial" | "assess" | "hold"
    auto_ring: str      # the computed ring (same as ring if no override)
    is_overridden: bool
    repo_count: int
    quality_signal: float | None   # avg ScanScore.overall for repos using this tech
    license_risk: str | None       # only for dependencies
    notes: str | None

class TechRadarResponse(BaseModel):
    blips: list[TechRadarBlip]
    total_repos: int
    generated_at: datetime
    project_id: int | None
```

### Step 4 — Tech Radar Service

**File:** `/app/services/tech_radar/engine.py`

`compute_tech_radar(db, project_ids: list[int] | None) -> list[TechRadarBlip]`

1. Load latest scans using `_latest_scan_per_pr()` pattern from `analytics.py:20-40`
2. Aggregate tech_counts (reuse logic from `analytics.py:260-309`)
3. Aggregate top dependencies: `GROUP BY name, ecosystem, COUNT(DISTINCT repo_id) ORDER BY count DESC LIMIT 50`
4. Join `ScanScore` to compute average `overall` score per technology cluster
5. Apply ring classification rules (thresholds above)
6. Load all `TechRadarOverride` records, apply where `project_id` matches or is NULL
7. Return sorted blips (by ring order: adopt first, then quadrant alphabetically)

### Step 5 — API Endpoints

Add to `/app/api/v1/analytics.py` (or new `/app/api/v1/tech_radar.py`):

```
GET  /api/v1/analytics/tech-radar?project_id={optional}
     → TechRadarResponse

POST /api/v1/analytics/tech-radar/overrides
     body: {tech_name, quadrant, ring, project_id?, notes?}
     → TechRadarOverride

DELETE /api/v1/analytics/tech-radar/overrides/{id}
     → 204
```

Register router in `/app/main.py` if using a new file.

### Step 6 — Frontend: `tech-radar.js` View

**File:** `/app/static/js/views/tech-radar.js`

Layout:
- **Top bar:** project filter dropdown (reuse pattern from tech-map.js:121)
- **Radar SVG:** classic circular radar — 4 concentric rings (Adopt innermost), 4 quadrant wedges, blips as dots with labels
  - Rings colored: Adopt (green) → Trial (blue) → Assess (orange) → Hold (red/gray)
  - Blips placed at randomized positions within ring+quadrant arc to avoid overlap
  - Hover tooltip: name, ring, repo_count, quality_signal, license_risk, notes
  - Click blip → highlight in table below
- **Legend** showing ring meanings
- **Blip table** below radar: sortable by name / quadrant / ring / repo_count / quality
  - Override button opens inline form to change ring + add notes
- **Override indicator:** blips with manual overrides shown with a pin icon; table row shows auto_ring vs active ring

### Step 7 — Navigation

**Modify:** `/app/static/index.html` or wherever the nav links are rendered — add "Tech Radar" link pointing to `#/tech-radar`.

**Modify:** `/app/static/js/router.js` — add route for `/tech-radar` → `tech-radar.js`.

---

## Critical Files

| File | Action |
|------|--------|
| `/app/models/tech_radar_override.py` | Create |
| `/app/models/__init__.py` | Import new model |
| `/alembic/versions/014_add_tech_radar_overrides.py` | Create |
| `/app/schemas/tech_radar.py` | Create |
| `/app/services/tech_radar/engine.py` | Create |
| `/app/api/v1/analytics.py` | Add 3 endpoints (or new router file) |
| `/app/static/js/views/tech-radar.js` | Create |
| `/app/static/js/router.js` | Add route |
| `/app/static/index.html` | Add nav link |

## Reuse (Do Not Rewrite)

- `analytics.py:_latest_scan_per_pr()` — exact same pattern for deduplicating scans
- `analytics.py:260-309` — framework/language/infra aggregation loop
- `tech-map.js` project filter dropdown — copy the project fetch + dropdown pattern
- `IdentityOverride` model pattern for the override table structure

---

## Verification

1. Run `alembic upgrade head` — migration 014 creates `tech_radar_overrides` table without errors
2. `GET /api/v1/analytics/tech-radar` returns blips with correct rings (spot-check: most-used language should be "adopt")
3. `POST .../overrides` pins a tech to a different ring; subsequent GET reflects the override with `is_overridden: true`
4. Frontend radar renders with 4 quadrants and 4 rings; hovering a blip shows tooltip; table filters work
5. Project filter changes blip set to only repos in that project
6. `DELETE .../overrides/{id}` restores auto-computed ring

"""Tech radar override CRUD endpoints."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.tech_radar_override import TechRadarOverride
from app.schemas.tech_radar import TechRadarOverrideCreate, TechRadarOverrideOut

router = APIRouter(prefix="/tech-radar", tags=["tech-radar"])

VALID_QUADRANTS = {"languages", "frameworks", "infrastructure", "dependencies"}
VALID_RINGS = {"adopt", "trial", "assess", "hold"}


@router.post("/overrides", response_model=TechRadarOverrideOut, status_code=201)
def create_override(body: TechRadarOverrideCreate, db: Session = Depends(get_db)):
    if body.quadrant not in VALID_QUADRANTS:
        raise HTTPException(400, f"quadrant must be one of: {', '.join(sorted(VALID_QUADRANTS))}")
    if body.ring not in VALID_RINGS:
        raise HTTPException(400, f"ring must be one of: {', '.join(sorted(VALID_RINGS))}")

    # Replace existing override for same tech+quadrant+project scope
    existing = (
        db.query(TechRadarOverride)
        .filter_by(tech_name=body.tech_name, quadrant=body.quadrant, project_id=body.project_id)
        .first()
    )
    if existing:
        existing.ring = body.ring
        existing.notes = body.notes
        db.commit()
        db.refresh(existing)
        return existing

    override = TechRadarOverride(
        tech_name=body.tech_name,
        quadrant=body.quadrant,
        ring=body.ring,
        project_id=body.project_id,
        notes=body.notes,
    )
    db.add(override)
    db.commit()
    db.refresh(override)
    return override


@router.delete("/overrides/{override_id}", status_code=204)
def delete_override(override_id: int, db: Session = Depends(get_db)):
    override = db.query(TechRadarOverride).filter_by(id=override_id).first()
    if not override:
        raise HTTPException(404, "Override not found")
    db.delete(override)
    db.commit()


@router.get("/overrides", response_model=list[TechRadarOverrideOut])
def list_overrides(
    project_id: int | None = None,
    db: Session = Depends(get_db),
):
    q = db.query(TechRadarOverride)
    if project_id is not None:
        q = q.filter(
            (TechRadarOverride.project_id == project_id)
            | (TechRadarOverride.project_id.is_(None))
        )
    return q.order_by(TechRadarOverride.quadrant, TechRadarOverride.tech_name).all()

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import Module, DeveloperModuleContribution, Developer

router = APIRouter(prefix="/modules", tags=["modules"])


@router.get("/{module_id}/ownership")
def get_module_ownership(module_id: int, db: Session = Depends(get_db)):
    module = db.get(Module, module_id)
    if not module:
        raise HTTPException(404, "Module not found")

    rows = (
        db.query(DeveloperModuleContribution, Developer)
        .join(Developer, DeveloperModuleContribution.developer_id == Developer.id)
        .filter(DeveloperModuleContribution.module_id == module_id)
        .order_by(DeveloperModuleContribution.percentage.desc())
        .all()
    )

    owners = [
        {
            "developer_id": dev.id,
            "canonical_username": dev.canonical_username,
            "display_name": dev.display_name,
            "commit_count": contrib.commit_count,
            "files_changed": contrib.files_changed,
            "percentage": contrib.percentage,
        }
        for contrib, dev in rows
    ]

    return {"module_id": module_id, "path": module.path, "name": module.name, "owners": owners}

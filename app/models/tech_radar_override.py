from __future__ import annotations
from datetime import datetime
from sqlalchemy import String, Text, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base


class TechRadarOverride(Base):
    """Manual ring placement for a technology on the tech radar."""
    __tablename__ = "tech_radar_overrides"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tech_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    quadrant: Mapped[str] = mapped_column(String(64), nullable=False)
    ring: Mapped[str] = mapped_column(String(32), nullable=False)
    project_id: Mapped[int | None] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=True, index=True
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

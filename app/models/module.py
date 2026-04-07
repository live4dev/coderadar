from __future__ import annotations
from datetime import datetime
from typing import TYPE_CHECKING
from sqlalchemy import String, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base

if TYPE_CHECKING:
    from app.models.repository import ProjectRepository
    from app.models.contribution import DeveloperModuleContribution


class Module(Base):
    __tablename__ = "modules"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_repository_id: Mapped[int] = mapped_column(
        ForeignKey("project_repositories.id", ondelete="CASCADE"), nullable=False, index=True
    )
    path: Mapped[str] = mapped_column(String(512), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    project_repository: Mapped[ProjectRepository] = relationship("ProjectRepository", back_populates="modules")
    developer_contributions: Mapped[list[DeveloperModuleContribution]] = relationship(
        "DeveloperModuleContribution", back_populates="module"
    )

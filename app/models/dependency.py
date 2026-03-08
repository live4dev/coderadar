from __future__ import annotations
from typing import TYPE_CHECKING
from sqlalchemy import String, ForeignKey, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship
import enum
from app.db.base import Base

if TYPE_CHECKING:
    from app.models.scan import Scan


class DependencyType(str, enum.Enum):
    prod = "prod"
    dev = "dev"
    test = "test"
    unknown = "unknown"


class Dependency(Base):
    __tablename__ = "dependencies"

    id: Mapped[int] = mapped_column(primary_key=True)
    scan_id: Mapped[int] = mapped_column(
        ForeignKey("scans.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    version: Mapped[str | None] = mapped_column(String(128), nullable=True)
    dep_type: Mapped[DependencyType] = mapped_column(
        Enum(DependencyType), default=DependencyType.unknown
    )
    manifest_file: Mapped[str | None] = mapped_column(String(255), nullable=True)
    ecosystem: Mapped[str | None] = mapped_column(String(64), nullable=True)

    scan: Mapped[Scan] = relationship("Scan", back_populates="dependencies")

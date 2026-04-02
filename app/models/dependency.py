from __future__ import annotations
from typing import TYPE_CHECKING
from sqlalchemy import String, Text, ForeignKey, Enum, Boolean
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
    package_manager: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # License fields (basic)
    license_spdx: Mapped[str | None] = mapped_column(String(128), nullable=True)
    license_raw: Mapped[str | None] = mapped_column(String(256), nullable=True)
    license_risk: Mapped[str] = mapped_column(String(16), nullable=False, default="unknown")
    is_direct: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # License fields (extended)
    license_expression: Mapped[str | None] = mapped_column(Text, nullable=True)
    license_confidence: Mapped[str] = mapped_column(String(16), nullable=False, default="unknown")
    license_source: Mapped[str | None] = mapped_column(String(64), nullable=True)
    license_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Discovery metadata
    discovery_mode: Mapped[str] = mapped_column(String(32), nullable=False, default="unknown")
    is_optional_dependency: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_private: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    scan: Mapped[Scan] = relationship("Scan", back_populates="dependencies")

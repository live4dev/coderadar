from __future__ import annotations
from typing import TYPE_CHECKING
from sqlalchemy import String, Text, ForeignKey, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship
import enum
from app.db.base import Base

if TYPE_CHECKING:
    from app.models.scan import Scan


class RiskSeverity(str, enum.Enum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class RiskType(str, enum.Enum):
    high_complexity_module = "high_complexity_module"
    no_tests = "no_tests"
    weak_documentation = "weak_documentation"
    no_ci_pipeline = "no_ci_pipeline"
    no_lockfile = "no_lockfile"
    oversized_file = "oversized_file"
    oversized_function = "oversized_function"
    oversized_module = "oversized_module"
    knowledge_concentration = "knowledge_concentration"
    low_bus_factor = "low_bus_factor"
    orphan_module = "orphan_module"
    mono_owner_language = "mono_owner_language"
    mono_owner_module = "mono_owner_module"


class EntityType(str, enum.Enum):
    project = "project"
    module = "module"
    developer = "developer"
    language = "language"
    file = "file"


class ScanRisk(Base):
    __tablename__ = "scan_risks"

    id: Mapped[int] = mapped_column(primary_key=True)
    scan_id: Mapped[int] = mapped_column(
        ForeignKey("scans.id", ondelete="CASCADE"), nullable=False, index=True
    )
    risk_type: Mapped[RiskType] = mapped_column(Enum(RiskType), nullable=False)
    severity: Mapped[RiskSeverity] = mapped_column(Enum(RiskSeverity), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    entity_type: Mapped[EntityType | None] = mapped_column(Enum(EntityType), nullable=True)
    entity_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)

    scan: Mapped[Scan] = relationship("Scan", back_populates="risks")

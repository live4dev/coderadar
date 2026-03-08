from __future__ import annotations
from typing import TYPE_CHECKING
from sqlalchemy import Float, ForeignKey, Enum, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
import enum
from app.db.base import Base

if TYPE_CHECKING:
    from app.models.scan import Scan


class ScoreDomain(str, enum.Enum):
    code_quality = "code_quality"
    test_quality = "test_quality"
    doc_quality = "doc_quality"
    delivery_quality = "delivery_quality"
    maintainability = "maintainability"
    overall = "overall"


class ScanScore(Base):
    __tablename__ = "scan_scores"

    id: Mapped[int] = mapped_column(primary_key=True)
    scan_id: Mapped[int] = mapped_column(
        ForeignKey("scans.id", ondelete="CASCADE"), nullable=False, index=True
    )
    domain: Mapped[ScoreDomain] = mapped_column(Enum(ScoreDomain), nullable=False)
    score: Mapped[float] = mapped_column(Float, nullable=False)
    details: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON

    scan: Mapped[Scan] = relationship("Scan", back_populates="scores")

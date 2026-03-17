from __future__ import annotations
from typing import TYPE_CHECKING
from sqlalchemy import String, Integer, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base

if TYPE_CHECKING:
    from app.models.scan import Scan


class ScanPersonalDataFinding(Base):
    """A single personal data (PDn) identifier found in repository source during scan."""

    __tablename__ = "scan_personal_data_findings"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    scan_id: Mapped[int] = mapped_column(
        ForeignKey("scans.id", ondelete="CASCADE"), nullable=False, index=True
    )
    pdn_type: Mapped[str] = mapped_column(String(128), nullable=False)
    file_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    line_number: Mapped[int] = mapped_column(Integer, nullable=False)
    matched_identifier: Mapped[str] = mapped_column(String(255), nullable=False)

    scan: Mapped[Scan] = relationship("Scan", back_populates="personal_data_findings")

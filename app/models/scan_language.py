from __future__ import annotations
from typing import TYPE_CHECKING
from sqlalchemy import Integer, Float, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base

if TYPE_CHECKING:
    from app.models.scan import Scan
    from app.models.language import Language


class ScanLanguage(Base):
    __tablename__ = "scan_languages"

    id: Mapped[int] = mapped_column(primary_key=True)
    scan_id: Mapped[int] = mapped_column(
        ForeignKey("scans.id", ondelete="CASCADE"), nullable=False, index=True
    )
    language_id: Mapped[int] = mapped_column(
        ForeignKey("languages.id", ondelete="CASCADE"), nullable=False
    )
    file_count: Mapped[int] = mapped_column(Integer, default=0)
    loc: Mapped[int] = mapped_column(Integer, default=0)
    percentage: Mapped[float] = mapped_column(Float, default=0.0)

    scan: Mapped[Scan] = relationship("Scan", back_populates="languages")
    language: Mapped[Language] = relationship("Language", back_populates="scan_languages")

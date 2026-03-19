from __future__ import annotations
from datetime import datetime, date
from typing import TYPE_CHECKING
from sqlalchemy import Integer, Float, DateTime, ForeignKey, Date, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base

if TYPE_CHECKING:
    from app.models.scan import Scan
    from app.models.developer import DeveloperProfile
    from app.models.language import Language
    from app.models.module import Module


class DeveloperContribution(Base):
    """Aggregate contribution of a developer profile within a scan."""
    __tablename__ = "developer_contributions"

    id: Mapped[int] = mapped_column(primary_key=True)
    scan_id: Mapped[int] = mapped_column(
        ForeignKey("scans.id", ondelete="CASCADE"), nullable=False, index=True
    )
    profile_id: Mapped[int] = mapped_column(
        ForeignKey("developer_profiles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    commit_count: Mapped[int] = mapped_column(Integer, default=0)
    insertions: Mapped[int] = mapped_column(Integer, default=0)
    deletions: Mapped[int] = mapped_column(Integer, default=0)
    files_changed: Mapped[int] = mapped_column(Integer, default=0)
    active_days: Mapped[int] = mapped_column(Integer, default=0)
    first_commit_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_commit_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    scan: Mapped[Scan] = relationship("Scan", back_populates="contributions")
    profile: Mapped[DeveloperProfile] = relationship(
        "DeveloperProfile", back_populates="contributions"
    )


class DeveloperLanguageContribution(Base):
    """Per-language contribution breakdown for a developer profile in a scan."""
    __tablename__ = "developer_language_contributions"

    id: Mapped[int] = mapped_column(primary_key=True)
    scan_id: Mapped[int] = mapped_column(
        ForeignKey("scans.id", ondelete="CASCADE"), nullable=False, index=True
    )
    profile_id: Mapped[int] = mapped_column(
        ForeignKey("developer_profiles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    language_id: Mapped[int] = mapped_column(
        ForeignKey("languages.id", ondelete="CASCADE"), nullable=False
    )
    commit_count: Mapped[int] = mapped_column(Integer, default=0)
    files_changed: Mapped[int] = mapped_column(Integer, default=0)
    loc_added: Mapped[int] = mapped_column(Integer, default=0)
    loc_deleted: Mapped[int] = mapped_column(Integer, default=0)
    percentage: Mapped[float] = mapped_column(Float, default=0.0)

    profile: Mapped[DeveloperProfile] = relationship(
        "DeveloperProfile", back_populates="language_contributions"
    )
    language: Mapped[Language] = relationship("Language")


class DeveloperModuleContribution(Base):
    """Per-module contribution breakdown for a developer profile in a scan."""
    __tablename__ = "developer_module_contributions"

    id: Mapped[int] = mapped_column(primary_key=True)
    scan_id: Mapped[int] = mapped_column(
        ForeignKey("scans.id", ondelete="CASCADE"), nullable=False, index=True
    )
    profile_id: Mapped[int] = mapped_column(
        ForeignKey("developer_profiles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    module_id: Mapped[int] = mapped_column(
        ForeignKey("modules.id", ondelete="CASCADE"), nullable=False
    )
    commit_count: Mapped[int] = mapped_column(Integer, default=0)
    files_changed: Mapped[int] = mapped_column(Integer, default=0)
    loc_added: Mapped[int] = mapped_column(Integer, default=0)
    percentage: Mapped[float] = mapped_column(Float, default=0.0)

    profile: Mapped[DeveloperProfile] = relationship(
        "DeveloperProfile", back_populates="module_contributions"
    )
    module: Mapped[Module] = relationship("Module", back_populates="developer_contributions")


class DeveloperDailyActivity(Base):
    """Per-day commit count for a developer profile (across all scans/history)."""
    __tablename__ = "developer_daily_activity"
    __table_args__ = (UniqueConstraint("profile_id", "commit_date"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    profile_id: Mapped[int] = mapped_column(
        ForeignKey("developer_profiles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    commit_date: Mapped[date] = mapped_column(Date, nullable=False)
    commit_count: Mapped[int] = mapped_column(Integer, default=0)

from __future__ import annotations
from datetime import datetime
from typing import TYPE_CHECKING
from sqlalchemy import String, Text, DateTime, ForeignKey, Float, Boolean, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base

if TYPE_CHECKING:
    from app.models.project import Project
    from app.models.contribution import DeveloperContribution, DeveloperLanguageContribution, DeveloperModuleContribution


class Developer(Base):
    __tablename__ = "developers"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    canonical_username: Mapped[str] = mapped_column(String(128), nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    primary_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    project: Mapped[Project] = relationship("Project", back_populates="developers")
    identities: Mapped[list[DeveloperIdentity]] = relationship(
        "DeveloperIdentity", back_populates="developer", cascade="all, delete-orphan"
    )
    contributions: Mapped[list[DeveloperContribution]] = relationship(
        "DeveloperContribution", back_populates="developer"
    )
    language_contributions: Mapped[list[DeveloperLanguageContribution]] = relationship(
        "DeveloperLanguageContribution", back_populates="developer"
    )
    module_contributions: Mapped[list[DeveloperModuleContribution]] = relationship(
        "DeveloperModuleContribution", back_populates="developer"
    )


class DeveloperIdentity(Base):
    __tablename__ = "developer_identities"

    id: Mapped[int] = mapped_column(primary_key=True)
    developer_id: Mapped[int] = mapped_column(
        ForeignKey("developers.id", ondelete="CASCADE"), nullable=False, index=True
    )
    raw_name: Mapped[str] = mapped_column(String(255), nullable=False)
    raw_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    confidence_score: Mapped[float] = mapped_column(Float, default=1.0)
    is_ambiguous: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    developer: Mapped[Developer] = relationship("Developer", back_populates="identities")


class IdentityOverride(Base):
    """Manual mapping: raw identity → canonical developer."""
    __tablename__ = "identity_overrides"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    raw_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    raw_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    canonical_username: Mapped[str] = mapped_column(String(128), nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

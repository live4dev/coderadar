from __future__ import annotations
from datetime import datetime
from typing import TYPE_CHECKING
from sqlalchemy import String, Text, DateTime, ForeignKey, Float, Boolean, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base

if TYPE_CHECKING:
    from app.models.contribution import (
        DeveloperContribution,
        DeveloperLanguageContribution,
        DeveloperModuleContribution,
    )


class DeveloperTag(Base):
    __tablename__ = "developer_tags"
    __table_args__ = (UniqueConstraint("developer_id", "tag", name="uq_developer_tags_developer_id_tag"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    developer_id: Mapped[int] = mapped_column(
        ForeignKey("developers.id", ondelete="CASCADE"), nullable=False, index=True
    )
    tag: Mapped[str] = mapped_column(String(128), nullable=False)

    developer: Mapped[Developer] = relationship("Developer", back_populates="tags")


class Developer(Base):
    """Global developer (person). Can have multiple profiles with different keys and emails."""
    __tablename__ = "developers"

    id: Mapped[int] = mapped_column(primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    profiles: Mapped[list[DeveloperProfile]] = relationship(
        "DeveloperProfile", back_populates="developer", cascade="all, delete-orphan"
    )
    tags: Mapped[list[DeveloperTag]] = relationship(
        "DeveloperTag", back_populates="developer", cascade="all, delete-orphan"
    )


class DeveloperProfile(Base):
    """One of possibly several profiles for a developer (canonical_username + email)."""
    __tablename__ = "developer_profiles"

    id: Mapped[int] = mapped_column(primary_key=True)
    developer_id: Mapped[int] = mapped_column(
        ForeignKey("developers.id", ondelete="CASCADE"), nullable=False, index=True
    )
    canonical_username: Mapped[str] = mapped_column(
        String(128), nullable=False, unique=True, index=True
    )
    display_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    primary_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    developer: Mapped[Developer] = relationship("Developer", back_populates="profiles")
    identities: Mapped[list[DeveloperIdentity]] = relationship(
        "DeveloperIdentity", back_populates="profile", cascade="all, delete-orphan"
    )
    contributions: Mapped[list[DeveloperContribution]] = relationship(
        "DeveloperContribution", back_populates="profile"
    )
    language_contributions: Mapped[list[DeveloperLanguageContribution]] = relationship(
        "DeveloperLanguageContribution", back_populates="profile"
    )
    module_contributions: Mapped[list[DeveloperModuleContribution]] = relationship(
        "DeveloperModuleContribution", back_populates="profile"
    )


class DeveloperIdentity(Base):
    """Raw identity from commits mapped to a profile."""
    __tablename__ = "developer_identities"

    id: Mapped[int] = mapped_column(primary_key=True)
    profile_id: Mapped[int] = mapped_column(
        ForeignKey("developer_profiles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    raw_name: Mapped[str] = mapped_column(String(255), nullable=False)
    raw_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    confidence_score: Mapped[float] = mapped_column(Float, default=1.0)
    is_ambiguous: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    profile: Mapped[DeveloperProfile] = relationship(
        "DeveloperProfile", back_populates="identities"
    )


class IdentityOverride(Base):
    """Manual mapping: raw identity → canonical developer (profile)."""
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

from __future__ import annotations
from datetime import datetime
from typing import TYPE_CHECKING
from sqlalchemy import String, Text, DateTime, ForeignKey, Enum, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
import enum
from app.db.base import Base

if TYPE_CHECKING:
    from app.models.project import Project
    from app.models.scan import Scan
    from app.models.module import Module


class RepositoryTag(Base):
    __tablename__ = "repository_tags"
    __table_args__ = (UniqueConstraint("repository_id", "tag", name="uq_repository_tags_repository_id_tag"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    repository_id: Mapped[int] = mapped_column(
        ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False, index=True
    )
    tag: Mapped[str] = mapped_column(String(128), nullable=False)

    repository: Mapped[Repository] = relationship("Repository", back_populates="tags")


class ProviderType(str, enum.Enum):
    bitbucket = "bitbucket"
    gitlab = "gitlab"
    github = "github"


class Repository(Base):
    __tablename__ = "repositories"
    __table_args__ = (UniqueConstraint("project_id", "url", name="uq_repositories_project_id_url"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    provider_type: Mapped[ProviderType] = mapped_column(
        Enum(ProviderType), nullable=False
    )
    default_branch: Mapped[str | None] = mapped_column(String(255), nullable=True)
    clone_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_commit_sha: Mapped[str | None] = mapped_column(String(40), nullable=True)

    # Credentials stored as references (not plain text — use env or vault in prod)
    credentials_username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    credentials_token: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    project: Mapped[Project] = relationship("Project", back_populates="repositories")
    scans: Mapped[list[Scan]] = relationship(
        "Scan", back_populates="repository", cascade="all, delete-orphan"
    )
    modules: Mapped[list[Module]] = relationship(
        "Module", back_populates="repository", cascade="all, delete-orphan"
    )
    tags: Mapped[list[RepositoryTag]] = relationship(
        "RepositoryTag", back_populates="repository", cascade="all, delete-orphan"
    )

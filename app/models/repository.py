from __future__ import annotations
from datetime import datetime, date
from typing import TYPE_CHECKING
from sqlalchemy import String, Text, DateTime, Date, Integer, ForeignKey, Enum, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
import enum
from app.db.base import Base

if TYPE_CHECKING:
    from app.models.project import Project
    from app.models.scan import Scan
    from app.models.module import Module


class RepositoryTag(Base):
    __tablename__ = "repository_tags"
    __table_args__ = (UniqueConstraint("project_repository_id", "tag", name="uq_repository_tags_project_repository_id_tag"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    project_repository_id: Mapped[int] = mapped_column(
        ForeignKey("project_repositories.id", ondelete="CASCADE"), nullable=False, index=True
    )
    tag: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    project_repository: Mapped[ProjectRepository] = relationship("ProjectRepository", back_populates="tags")


class RepositoryGitTag(Base):
    """A git tag fetched from the repository during a scan (e.g. v1.0.0, release-2024)."""
    __tablename__ = "repository_git_tags"
    __table_args__ = (UniqueConstraint("repository_id", "name", name="uq_repository_git_tags_repository_id_name"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    repository_id: Mapped[int] = mapped_column(
        ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    sha: Mapped[str | None] = mapped_column(String(40), nullable=True)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    tagger_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    tagger_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    tagged_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    repository: Mapped[Repository] = relationship("Repository", back_populates="git_tags")


class ProviderType(str, enum.Enum):
    bitbucket = "bitbucket"
    gitlab = "gitlab"
    github = "github"


class Repository(Base):
    __tablename__ = "repositories"
    __table_args__ = (UniqueConstraint("url", name="uq_repositories_url"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    provider_type: Mapped[ProviderType] = mapped_column(
        Enum(ProviderType), nullable=False
    )
    clone_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_commit_sha: Mapped[str | None] = mapped_column(String(40), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    project_repositories: Mapped[list[ProjectRepository]] = relationship(
        "ProjectRepository", back_populates="repository", cascade="all, delete-orphan"
    )
    git_tags: Mapped[list[RepositoryGitTag]] = relationship(
        "RepositoryGitTag", back_populates="repository", cascade="all, delete-orphan"
    )


class ProjectRepository(Base):
    """Associates a Repository (URL) with a Project, carrying project-specific metadata."""
    __tablename__ = "project_repositories"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    repository_id: Mapped[int] = mapped_column(
        ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    default_branch: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Credentials stored as references (not plain text — use env or vault in prod)
    credentials_username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    credentials_token: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    project: Mapped[Project] = relationship("Project", back_populates="project_repositories")
    repository: Mapped[Repository] = relationship("Repository", back_populates="project_repositories")
    scans: Mapped[list[Scan]] = relationship(
        "Scan", back_populates="project_repository", cascade="all, delete-orphan"
    )
    modules: Mapped[list[Module]] = relationship(
        "Module", back_populates="project_repository", cascade="all, delete-orphan"
    )
    tags: Mapped[list[RepositoryTag]] = relationship(
        "RepositoryTag", back_populates="project_repository", cascade="all, delete-orphan"
    )
    daily_activity: Mapped[list[RepositoryDailyActivity]] = relationship(
        "RepositoryDailyActivity", back_populates="project_repository", cascade="all, delete-orphan"
    )


class RepositoryDailyActivity(Base):
    """Per-day commit count for a project-repository association."""
    __tablename__ = "repository_daily_activity"
    __table_args__ = (UniqueConstraint("project_repository_id", "commit_date", name="uq_repository_daily_activity_pr_id_commit_date"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    project_repository_id: Mapped[int] = mapped_column(
        ForeignKey("project_repositories.id", ondelete="CASCADE"), nullable=False, index=True
    )
    commit_date: Mapped[date] = mapped_column(Date, nullable=False)
    commit_count: Mapped[int] = mapped_column(Integer, default=0)

    project_repository: Mapped[ProjectRepository] = relationship("ProjectRepository", back_populates="daily_activity")

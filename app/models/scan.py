from __future__ import annotations
from datetime import datetime
from typing import TYPE_CHECKING
from sqlalchemy import String, Text, DateTime, ForeignKey, Enum, Integer, Float, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
import enum
from app.db.base import Base

if TYPE_CHECKING:
    from app.models.repository import Repository
    from app.models.scan_language import ScanLanguage
    from app.models.dependency import Dependency
    from app.models.scan_score import ScanScore
    from app.models.scan_risk import ScanRisk
    from app.models.contribution import DeveloperContribution
from app.models.scan_personal_data_finding import ScanPersonalDataFinding


class ScanStatus(str, enum.Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"


class ProjectType(str, enum.Enum):
    backend_service = "backend_service"
    frontend_application = "frontend_application"
    library = "library"
    cli_tool = "cli_tool"
    infra_config = "infra_config"
    monolith = "monolith"
    monorepo = "monorepo"
    unknown = "unknown"


class Scan(Base):
    __tablename__ = "scans"

    id: Mapped[int] = mapped_column(primary_key=True)
    repository_id: Mapped[int] = mapped_column(
        ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[ScanStatus] = mapped_column(
        Enum(ScanStatus), default=ScanStatus.pending, nullable=False
    )
    branch: Mapped[str] = mapped_column(String(255), nullable=False)
    commit_sha: Mapped[str | None] = mapped_column(String(40), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # File stats
    total_files: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_loc: Mapped[int | None] = mapped_column(Integer, nullable=True)
    size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    file_count_source: Mapped[int | None] = mapped_column(Integer, nullable=True)
    file_count_test: Mapped[int | None] = mapped_column(Integer, nullable=True)
    file_count_config: Mapped[int | None] = mapped_column(Integer, nullable=True)
    dir_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Project classification
    project_type: Mapped[ProjectType | None] = mapped_column(
        Enum(ProjectType), nullable=True
    )
    primary_language: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # Complexity summary
    avg_file_loc: Mapped[float | None] = mapped_column(Float, nullable=True)
    large_files_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Timestamps
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    repository: Mapped[Repository] = relationship("Repository", back_populates="scans")
    languages: Mapped[list[ScanLanguage]] = relationship(
        "ScanLanguage", back_populates="scan", cascade="all, delete-orphan"
    )
    dependencies: Mapped[list[Dependency]] = relationship(
        "Dependency", back_populates="scan", cascade="all, delete-orphan"
    )
    scores: Mapped[list[ScanScore]] = relationship(
        "ScanScore", back_populates="scan", cascade="all, delete-orphan"
    )
    risks: Mapped[list[ScanRisk]] = relationship(
        "ScanRisk", back_populates="scan", cascade="all, delete-orphan"
    )
    contributions: Mapped[list[DeveloperContribution]] = relationship(
        "DeveloperContribution", back_populates="scan", cascade="all, delete-orphan"
    )
    personal_data_findings: Mapped[list[ScanPersonalDataFinding]] = relationship(
        "ScanPersonalDataFinding", back_populates="scan", cascade="all, delete-orphan"
    )

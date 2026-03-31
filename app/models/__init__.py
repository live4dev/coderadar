# Import all models so Alembic autogenerate can discover them
from app.models.project import Project, ProjectTag
from app.models.repository import Repository, ProjectRepository, RepositoryTag, RepositoryGitTag, RepositoryDailyActivity, ProviderType
from app.models.scan import Scan, ScanStatus, ProjectType
from app.models.developer import Developer, DeveloperTag, DeveloperProfile, DeveloperIdentity, IdentityOverride
from app.models.language import Language
from app.models.scan_language import ScanLanguage
from app.models.module import Module
from app.models.dependency import Dependency, DependencyType
from app.models.contribution import (
    DeveloperContribution,
    DeveloperLanguageContribution,
    DeveloperModuleContribution,
    DeveloperDailyActivity,
)
from app.models.scan_score import ScanScore, ScoreDomain
from app.models.scan_risk import ScanRisk, RiskSeverity, RiskType, EntityType
from app.models.scan_personal_data_finding import ScanPersonalDataFinding

__all__ = [
    "Project",
    "ProjectTag",
    "Repository",
    "ProjectRepository",
    "RepositoryTag",
    "RepositoryGitTag",
    "RepositoryDailyActivity",
    "ProviderType",
    "Scan",
    "ScanStatus",
    "ProjectType",
    "Developer",
    "DeveloperTag",
    "DeveloperProfile",
    "DeveloperIdentity",
    "IdentityOverride",
    "Language",
    "ScanLanguage",
    "Module",
    "Dependency",
    "DependencyType",
    "DeveloperContribution",
    "DeveloperLanguageContribution",
    "DeveloperModuleContribution",
    "DeveloperDailyActivity",
    "ScanScore",
    "ScoreDomain",
    "ScanRisk",
    "RiskSeverity",
    "RiskType",
    "EntityType",
    "ScanPersonalDataFinding",
]

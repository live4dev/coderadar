# Import all models so Alembic autogenerate can discover them
from app.models.project import Project
from app.models.repository import Repository, ProviderType
from app.models.scan import Scan, ScanStatus, ProjectType
from app.models.developer import Developer, DeveloperIdentity, IdentityOverride
from app.models.language import Language
from app.models.scan_language import ScanLanguage
from app.models.module import Module
from app.models.dependency import Dependency, DependencyType
from app.models.contribution import (
    DeveloperContribution,
    DeveloperLanguageContribution,
    DeveloperModuleContribution,
)
from app.models.scan_score import ScanScore, ScoreDomain
from app.models.scan_risk import ScanRisk, RiskSeverity, RiskType, EntityType

__all__ = [
    "Project",
    "Repository",
    "ProviderType",
    "Scan",
    "ScanStatus",
    "ProjectType",
    "Developer",
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
    "ScanScore",
    "ScoreDomain",
    "ScanRisk",
    "RiskSeverity",
    "RiskType",
    "EntityType",
]

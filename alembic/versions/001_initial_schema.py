"""Merged initial schema

Revision ID: 001
Revises:
Create Date: 2026-04-01 00:00:00.000000

Squashed from migrations 001–014. Creates the complete schema in a single step.
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "projects",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
    )

    op.create_table(
        "repositories",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("provider_type", sa.Enum("bitbucket", "gitlab", "github", name="providertype"), nullable=False),
        sa.Column("clone_path", sa.Text(), nullable=True),
        sa.Column("last_commit_sha", sa.String(40), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
        sa.UniqueConstraint("url", name="uq_repositories_url"),
    )

    op.create_table(
        "project_repositories",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("repository_id", sa.Integer(), sa.ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("default_branch", sa.String(255), nullable=True),
        sa.Column("credentials_username", sa.String(255), nullable=True),
        sa.Column("credentials_token", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("ix_project_repositories_project_id", "project_repositories", ["project_id"])
    op.create_index("ix_project_repositories_repository_id", "project_repositories", ["repository_id"])

    op.create_table(
        "developers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )

    op.create_table(
        "developer_profiles",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("developer_id", sa.Integer(), sa.ForeignKey("developers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("canonical_username", sa.String(128), nullable=False),
        sa.Column("display_name", sa.String(255), nullable=True),
        sa.Column("primary_email", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("ix_developer_profiles_developer_id", "developer_profiles", ["developer_id"])
    op.create_index("ix_developer_profiles_canonical_username", "developer_profiles", ["canonical_username"], unique=True)

    op.create_table(
        "developer_identities",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("profile_id", sa.Integer(), sa.ForeignKey("developer_profiles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("raw_name", sa.String(255), nullable=False),
        sa.Column("raw_email", sa.String(255), nullable=True),
        sa.Column("confidence_score", sa.Float(), server_default="1.0"),
        sa.Column("is_ambiguous", sa.Boolean(), server_default="0"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("ix_developer_identities_profile_id", "developer_identities", ["profile_id"])

    op.create_table(
        "identity_overrides",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("raw_name", sa.String(255), nullable=True),
        sa.Column("raw_email", sa.String(255), nullable=True),
        sa.Column("canonical_username", sa.String(128), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("ix_identity_overrides_project_id", "identity_overrides", ["project_id"])

    op.create_table(
        "languages",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(64), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )

    op.create_table(
        "scans",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_repository_id", sa.Integer(), sa.ForeignKey("project_repositories.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.Enum("pending", "running", "completed", "failed", "cancelled", name="scanstatus"), nullable=False, server_default="pending"),
        sa.Column("branch", sa.String(255), nullable=False),
        sa.Column("commit_sha", sa.String(40), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("total_files", sa.Integer(), nullable=True),
        sa.Column("total_loc", sa.Integer(), nullable=True),
        sa.Column("size_bytes", sa.Integer(), nullable=True),
        sa.Column("file_count_source", sa.Integer(), nullable=True),
        sa.Column("file_count_test", sa.Integer(), nullable=True),
        sa.Column("file_count_config", sa.Integer(), nullable=True),
        sa.Column("dir_count", sa.Integer(), nullable=True),
        sa.Column("project_type", sa.Enum("backend_service", "frontend_application", "library", "cli_tool", "infra_config", "monolith", "monorepo", "unknown", name="projecttype"), nullable=True),
        sa.Column("primary_language", sa.String(64), nullable=True),
        sa.Column("avg_file_loc", sa.Float(), nullable=True),
        sa.Column("large_files_count", sa.Integer(), nullable=True),
        sa.Column("frameworks_json", sa.Text(), nullable=True),
        sa.Column("package_managers_json", sa.Text(), nullable=True),
        sa.Column("ci_provider", sa.String(64), nullable=True),
        sa.Column("infra_tools_json", sa.Text(), nullable=True),
        sa.Column("linters_json", sa.Text(), nullable=True),
        sa.Column("has_docker", sa.Boolean(), nullable=True),
        sa.Column("has_kubernetes", sa.Boolean(), nullable=True),
        sa.Column("has_terraform", sa.Boolean(), nullable=True),
        sa.Column("cancel_requested", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("ix_scans_project_repository_id", "scans", ["project_repository_id"])

    op.create_table(
        "modules",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_repository_id", sa.Integer(), sa.ForeignKey("project_repositories.id", ondelete="CASCADE"), nullable=False),
        sa.Column("path", sa.String(512), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("ix_modules_project_repository_id", "modules", ["project_repository_id"])

    op.create_table(
        "scan_languages",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("scan_id", sa.Integer(), sa.ForeignKey("scans.id", ondelete="CASCADE"), nullable=False),
        sa.Column("language_id", sa.Integer(), sa.ForeignKey("languages.id", ondelete="CASCADE"), nullable=False),
        sa.Column("file_count", sa.Integer(), server_default="0"),
        sa.Column("loc", sa.Integer(), server_default="0"),
        sa.Column("percentage", sa.Float(), server_default="0.0"),
    )
    op.create_index("ix_scan_languages_scan_id", "scan_languages", ["scan_id"])

    op.create_table(
        "dependencies",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("scan_id", sa.Integer(), sa.ForeignKey("scans.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("version", sa.String(128), nullable=True),
        sa.Column("dep_type", sa.Enum("prod", "dev", "test", "unknown", name="dependencytype"), server_default="unknown"),
        sa.Column("manifest_file", sa.String(255), nullable=True),
        sa.Column("ecosystem", sa.String(64), nullable=True),
        sa.Column("license_spdx", sa.String(128), nullable=True),
        sa.Column("license_raw", sa.String(256), nullable=True),
        sa.Column("license_risk", sa.String(16), nullable=False, server_default="unknown"),
        sa.Column("is_direct", sa.Boolean(), nullable=False, server_default="1"),
    )
    op.create_index("ix_dependencies_scan_id", "dependencies", ["scan_id"])

    op.create_table(
        "developer_contributions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("scan_id", sa.Integer(), sa.ForeignKey("scans.id", ondelete="CASCADE"), nullable=False),
        sa.Column("profile_id", sa.Integer(), sa.ForeignKey("developer_profiles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("commit_count", sa.Integer(), server_default="0"),
        sa.Column("insertions", sa.Integer(), server_default="0"),
        sa.Column("deletions", sa.Integer(), server_default="0"),
        sa.Column("files_changed", sa.Integer(), server_default="0"),
        sa.Column("active_days", sa.Integer(), server_default="0"),
        sa.Column("first_commit_at", sa.DateTime(), nullable=True),
        sa.Column("last_commit_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_developer_contributions_scan_id", "developer_contributions", ["scan_id"])
    op.create_index("ix_developer_contributions_profile_id", "developer_contributions", ["profile_id"])

    op.create_table(
        "developer_language_contributions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("scan_id", sa.Integer(), sa.ForeignKey("scans.id", ondelete="CASCADE"), nullable=False),
        sa.Column("profile_id", sa.Integer(), sa.ForeignKey("developer_profiles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("language_id", sa.Integer(), sa.ForeignKey("languages.id", ondelete="CASCADE"), nullable=False),
        sa.Column("commit_count", sa.Integer(), server_default="0"),
        sa.Column("files_changed", sa.Integer(), server_default="0"),
        sa.Column("loc_added", sa.Integer(), server_default="0"),
        sa.Column("loc_deleted", sa.Integer(), server_default="0"),
        sa.Column("percentage", sa.Float(), server_default="0.0"),
    )
    op.create_index("ix_developer_language_contributions_scan_id", "developer_language_contributions", ["scan_id"])
    op.create_index("ix_developer_language_contributions_profile_id", "developer_language_contributions", ["profile_id"])

    op.create_table(
        "developer_module_contributions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("scan_id", sa.Integer(), sa.ForeignKey("scans.id", ondelete="CASCADE"), nullable=False),
        sa.Column("profile_id", sa.Integer(), sa.ForeignKey("developer_profiles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("module_id", sa.Integer(), sa.ForeignKey("modules.id", ondelete="CASCADE"), nullable=False),
        sa.Column("commit_count", sa.Integer(), server_default="0"),
        sa.Column("files_changed", sa.Integer(), server_default="0"),
        sa.Column("loc_added", sa.Integer(), server_default="0"),
        sa.Column("percentage", sa.Float(), server_default="0.0"),
    )
    op.create_index("ix_developer_module_contributions_scan_id", "developer_module_contributions", ["scan_id"])
    op.create_index("ix_developer_module_contributions_profile_id", "developer_module_contributions", ["profile_id"])

    op.create_table(
        "scan_scores",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("scan_id", sa.Integer(), sa.ForeignKey("scans.id", ondelete="CASCADE"), nullable=False),
        sa.Column("domain", sa.Enum("code_quality", "test_quality", "doc_quality", "delivery_quality", "maintainability", "overall", name="scoredomain"), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("details", sa.Text(), nullable=True),
    )
    op.create_index("ix_scan_scores_scan_id", "scan_scores", ["scan_id"])

    op.create_table(
        "scan_risks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("scan_id", sa.Integer(), sa.ForeignKey("scans.id", ondelete="CASCADE"), nullable=False),
        sa.Column("risk_type", sa.Enum(
            "high_complexity_module", "no_tests", "weak_documentation", "no_ci_pipeline",
            "no_lockfile", "oversized_file", "oversized_function", "oversized_module",
            "knowledge_concentration", "low_bus_factor", "orphan_module",
            "mono_owner_language", "mono_owner_module", name="risktype"
        ), nullable=False),
        sa.Column("severity", sa.Enum("low", "medium", "high", "critical", name="riskseverity"), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("entity_type", sa.Enum("project", "module", "developer", "language", "file", name="entitytype"), nullable=True),
        sa.Column("entity_ref", sa.String(255), nullable=True),
    )
    op.create_index("ix_scan_risks_scan_id", "scan_risks", ["scan_id"])

    op.create_table(
        "project_tags",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tag", sa.String(128), nullable=False),
        sa.UniqueConstraint("project_id", "tag", name="uq_project_tags_project_id_tag"),
    )
    op.create_index("ix_project_tags_project_id", "project_tags", ["project_id"])

    op.create_table(
        "repository_tags",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("project_repository_id", sa.Integer(), sa.ForeignKey("project_repositories.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tag", sa.String(128), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("project_repository_id", "tag", name="uq_repository_tags_project_repository_id_tag"),
    )
    op.create_index("ix_repository_tags_project_repository_id", "repository_tags", ["project_repository_id"])

    op.create_table(
        "developer_tags",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("developer_id", sa.Integer(), sa.ForeignKey("developers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tag", sa.String(128), nullable=False),
        sa.UniqueConstraint("developer_id", "tag", name="uq_developer_tags_developer_id_tag"),
    )
    op.create_index("ix_developer_tags_developer_id", "developer_tags", ["developer_id"])

    op.create_table(
        "scan_personal_data_findings",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("scan_id", sa.Integer(), sa.ForeignKey("scans.id", ondelete="CASCADE"), nullable=False),
        sa.Column("pdn_type", sa.String(128), nullable=False),
        sa.Column("file_path", sa.String(1024), nullable=False),
        sa.Column("line_number", sa.Integer(), nullable=False),
        sa.Column("matched_identifier", sa.String(255), nullable=False),
    )
    op.create_index("ix_scan_personal_data_findings_scan_id", "scan_personal_data_findings", ["scan_id"])

    op.create_table(
        "repository_git_tags",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("repository_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("sha", sa.String(40), nullable=True),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("tagger_name", sa.String(255), nullable=True),
        sa.Column("tagger_email", sa.String(255), nullable=True),
        sa.Column("tagged_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["repository_id"], ["repositories.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("repository_id", "name", name="uq_repository_git_tags_repository_id_name"),
    )
    op.create_index("ix_repository_git_tags_repository_id", "repository_git_tags", ["repository_id"])

    op.create_table(
        "developer_daily_activity",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("profile_id", sa.Integer(), nullable=False),
        sa.Column("commit_date", sa.Date(), nullable=False),
        sa.Column("commit_count", sa.Integer(), nullable=False, server_default="0"),
        sa.ForeignKeyConstraint(["profile_id"], ["developer_profiles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("profile_id", "commit_date", name="uq_developer_daily_activity_profile_date"),
    )
    op.create_index("ix_developer_daily_activity_profile_id", "developer_daily_activity", ["profile_id"])

    op.create_table(
        "repository_daily_activity",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("project_repository_id", sa.Integer(), nullable=False),
        sa.Column("commit_date", sa.Date(), nullable=False),
        sa.Column("commit_count", sa.Integer(), nullable=False, server_default="0"),
        sa.ForeignKeyConstraint(["project_repository_id"], ["project_repositories.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_repository_id", "commit_date", name="uq_repository_daily_activity_pr_id_commit_date"),
    )
    op.create_index("ix_repository_daily_activity_project_repository_id", "repository_daily_activity", ["project_repository_id"])


def downgrade() -> None:
    op.drop_index("ix_repository_daily_activity_project_repository_id", table_name="repository_daily_activity")
    op.drop_table("repository_daily_activity")
    op.drop_index("ix_developer_daily_activity_profile_id", table_name="developer_daily_activity")
    op.drop_table("developer_daily_activity")
    op.drop_index("ix_repository_git_tags_repository_id", table_name="repository_git_tags")
    op.drop_table("repository_git_tags")
    op.drop_index("ix_scan_personal_data_findings_scan_id", table_name="scan_personal_data_findings")
    op.drop_table("scan_personal_data_findings")
    op.drop_index("ix_developer_tags_developer_id", table_name="developer_tags")
    op.drop_table("developer_tags")
    op.drop_index("ix_repository_tags_project_repository_id", table_name="repository_tags")
    op.drop_table("repository_tags")
    op.drop_index("ix_project_tags_project_id", table_name="project_tags")
    op.drop_table("project_tags")
    op.drop_index("ix_scan_risks_scan_id", table_name="scan_risks")
    op.drop_table("scan_risks")
    op.drop_index("ix_scan_scores_scan_id", table_name="scan_scores")
    op.drop_table("scan_scores")
    op.drop_index("ix_developer_module_contributions_profile_id", table_name="developer_module_contributions")
    op.drop_index("ix_developer_module_contributions_scan_id", table_name="developer_module_contributions")
    op.drop_table("developer_module_contributions")
    op.drop_index("ix_developer_language_contributions_profile_id", table_name="developer_language_contributions")
    op.drop_index("ix_developer_language_contributions_scan_id", table_name="developer_language_contributions")
    op.drop_table("developer_language_contributions")
    op.drop_index("ix_developer_contributions_profile_id", table_name="developer_contributions")
    op.drop_index("ix_developer_contributions_scan_id", table_name="developer_contributions")
    op.drop_table("developer_contributions")
    op.drop_index("ix_dependencies_scan_id", table_name="dependencies")
    op.drop_table("dependencies")
    op.drop_index("ix_scan_languages_scan_id", table_name="scan_languages")
    op.drop_table("scan_languages")
    op.drop_index("ix_modules_project_repository_id", table_name="modules")
    op.drop_table("modules")
    op.drop_index("ix_scans_project_repository_id", table_name="scans")
    op.drop_table("scans")
    op.drop_table("languages")
    op.drop_index("ix_identity_overrides_project_id", table_name="identity_overrides")
    op.drop_table("identity_overrides")
    op.drop_index("ix_developer_identities_profile_id", table_name="developer_identities")
    op.drop_table("developer_identities")
    op.drop_index("ix_developer_profiles_canonical_username", table_name="developer_profiles")
    op.drop_index("ix_developer_profiles_developer_id", table_name="developer_profiles")
    op.drop_table("developer_profiles")
    op.drop_table("developers")
    op.drop_index("ix_project_repositories_repository_id", table_name="project_repositories")
    op.drop_index("ix_project_repositories_project_id", table_name="project_repositories")
    op.drop_table("project_repositories")
    op.drop_table("repositories")
    op.drop_table("projects")

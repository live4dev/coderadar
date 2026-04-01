# Plan: Merge All Migrations into One

## Goal
Collapse migrations 001–014 into a single `001_initial_schema.py` that creates the final schema state directly, eliminating the chain of incremental changes.

## Final Schema State

### Enums
- `providertype`: bitbucket, gitlab, github
- `scanstatus`: pending, running, completed, failed, cancelled
- `projecttype`: backend_service, frontend_application, library, cli_tool, infra_config, monolith, monorepo, unknown
- `dependencytype`: prod, dev, test, unknown
- `scoredomain`: code_quality, test_quality, doc_quality, delivery_quality, maintainability, overall
- `risktype`: high_complexity_module, no_tests, weak_documentation, no_ci_pipeline, no_lockfile, oversized_file, oversized_function, oversized_module, knowledge_concentration, low_bus_factor, orphan_module, mono_owner_language, mono_owner_module
- `riskseverity`: low, medium, high, critical
- `entitytype`: project, module, developer, language, file

### Tables (in dependency order for creation)
1. `projects`
2. `repositories` — no project_id; url is globally unique
3. `project_repositories` — join table (project_id, repository_id, name, default_branch, creds)
4. `developers`
5. `developer_profiles`
6. `developer_identities`
7. `identity_overrides`
8. `languages`
9. `scans` — references project_repository_id (not repository_id); includes stack columns + cancel_requested
10. `modules` — references project_repository_id
11. `scan_languages`
12. `dependencies` — includes license_spdx, license_raw, license_risk, is_direct
13. `developer_contributions`
14. `developer_language_contributions`
15. `developer_module_contributions`
16. `scan_scores`
17. `scan_risks`
18. `project_tags`
19. `repository_tags` — references project_repository_id; includes description, created_at
20. `developer_tags`
21. `scan_personal_data_findings`
22. `repository_git_tags`
23. `developer_daily_activity`
24. `repository_daily_activity` — references project_repository_id

## Steps
1. Overwrite `alembic/versions/001_initial_schema.py` with the merged upgrade/downgrade
2. Delete `alembic/versions/002_*.py` through `alembic/versions/014_*.py`

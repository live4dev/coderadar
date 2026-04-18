#!/usr/bin/env python3
"""
Seed CodeRadar with several popular open-source projects from GitHub.

Each entry in PROJECTS maps a CodeRadar project name to a list of GitHub
"owner/repo" slugs. Running this script is idempotent — already-imported
repos are skipped.

Usage:
    python scripts/seed_popular_projects.py \\
        [--token <github-pat>]          # fetch real branch names from API
        [--scan]                        # enqueue scans after import
        [--dry-run]                     # preview without DB writes
        [--projects Django,FastAPI]     # import only these projects (default: all)

Credentials can also be supplied via environment variables:
    GITHUB_TOKEN
"""
import sys
import os
import argparse
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.db.session import SessionLocal
from app.models import Project, Repository, ProjectRepository, Scan, ScanStatus, ProviderType
from app.core.logging import setup_logging, get_logger

logger = get_logger(__name__)

GITHUB_API = "https://api.github.com"

# ---------------------------------------------------------------------------
# Curated project list: project name → list of "owner/repo" slugs
# ---------------------------------------------------------------------------

PROJECTS: dict[str, list[str]] = {
    "Django": [
        "django/django",
        "django/channels",
        "django/asgiref",
        "django/django-filter",
    ],
    "FastAPI": [
        "tiangolo/fastapi",
        "tiangolo/sqlmodel",
        "tiangolo/typer",
    ],
    "HashiCorp": [
        "hashicorp/terraform",
        "hashicorp/vault",
        "hashicorp/consul",
        "hashicorp/packer",
    ],
    "Microsoft Dev Tools": [
        "microsoft/vscode",
        "microsoft/TypeScript",
        "microsoft/playwright",
        "microsoft/pyright",
    ],
    "Apache Data": [
        "apache/kafka",
        "apache/spark",
        "apache/airflow",
        "apache/flink",
    ],
    "Kubernetes": [
        "kubernetes/kubernetes",
        "kubernetes/ingress-nginx",
        "kubernetes/dashboard",
        "helm/helm",
    ],
    "Erlang": [
        "erlang/otp",               # Erlang/OTP — the language runtime itself
        "rabbitmq/rabbitmq-server", # most popular Erlang production system
        "emqx/emqx",                # MQTT broker
        "ninenines/cowboy",         # HTTP server
        "processone/ejabberd",      # XMPP server
        "apache/couchdb",           # document database
        "happi/theBeamBook",        # deep-dive book on the BEAM VM
    ],
    "Java": [
        "spring-projects/spring-boot",
        "spring-projects/spring-framework",
        "elastic/elasticsearch",
        "apache/kafka",
        "netty/netty",
        "apache/hadoop",
        "junit-team/junit5",
        "google/guava",
        "square/okhttp",
        "square/retrofit",
        "mybatis/mybatis-3",
        "ReactiveX/RxJava",
        "google/gson",
        "FasterXML/jackson-databind",
    ],
    "Scala": [
        "scala/scala",
        "akka/akka",
        "apache/spark",             # primary language is Scala
        "playframework/playframework",
        "typelevel/cats",
        "typelevel/fs2",
        "zio/zio",
        "slick/slick",
        "scalameta/scalafmt",
        "sbt/sbt",
        "lampepfl/dotty",           # Scala 3 compiler
    ],
    "Python 2 Era": [
        "django/django",           # last Python 2 support: 1.11 LTS
        "kennethreitz/requests",   # widely used, shipped Python 2 builds
        "fabric/fabric",           # originally Python 2-first
        "paramiko/paramiko",       # Python 2 compatible for years
        "pypa/pip",                # carries decades of legacy compat code
        "twisted/twisted",         # one of the oldest Python 2 projects
        "Pylons/pyramid",          # Python 2/3 dual-support era
        "sqlalchemy/sqlalchemy",   # long Python 2 support window
        "pallets/flask",           # 0.x–1.x shipped Python 2 support
        "celery/celery",           # Python 2 support through 4.x
        "boto/boto",               # original AWS SDK, Python 2 only
        "gevent/gevent",           # Python 2 greenlet era
    ],
    "wemake-services": [
        "wemake-services/wemake-python-styleguide",
        "wemake-services/wemake-django-template",
        "wemake-services/wemake-vue-template",
        "wemake-services/wemake-python-package",
        "wemake-services/wemake-frontend-styleguide",
        "wemake-services/django-split-settings",
        "wemake-services/django-test-migrations",
        "wemake-services/flake8-eradicate",
        "wemake-services/flake8-broken-line",
        "wemake-services/coverage-conditional-plugin",
        "wemake-services/pytest-modified-env",
        "wemake-services/asyncio-redis-rate-limit",
        "wemake-services/dump-env",
        "wemake-services/dotenv-linter",
        "wemake-services/docker-image-size-limit",
        "wemake-services/caddy-gen",
        "wemake-services/django-pre-deploy-checks",
    ],
}


# ---------------------------------------------------------------------------
# GitHub API helpers
# ---------------------------------------------------------------------------

def _make_session(token: str) -> requests.Session:
    s = requests.Session()
    if token:
        s.headers["Authorization"] = f"Bearer {token}"
    s.headers["Accept"] = "application/vnd.github+json"
    s.headers["X-GitHub-Api-Version"] = "2022-11-28"
    return s


def _fetch_repo_meta(session: requests.Session, slug: str) -> dict:
    """Return GitHub repo metadata dict, or {} on failure."""
    try:
        resp = session.get(f"{GITHUB_API}/repos/{slug}", timeout=15)
        if resp.status_code == 200:
            return resp.json()
        logger.warning("GitHub API %s for %s", resp.status_code, slug)
    except requests.RequestException as exc:
        logger.warning("GitHub API error for %s: %s", slug, exc)
    return {}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Seed CodeRadar with popular open-source GitHub projects"
    )
    parser.add_argument(
        "--token",
        default=os.environ.get("GITHUB_TOKEN", ""),
        help="GitHub Personal Access Token (used to fetch branch names from the API)",
    )
    parser.add_argument(
        "--scan",
        action="store_true",
        help="Enqueue scans for newly imported repositories",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview what would be imported without writing to the database",
    )
    parser.add_argument(
        "--projects",
        default="",
        help="Comma-separated list of project names to import (default: all)",
    )
    args = parser.parse_args()

    setup_logging()

    # Determine which projects to import
    selected = {p.strip() for p in args.projects.split(",") if p.strip()} if args.projects else set()
    projects_to_import = {
        name: slugs
        for name, slugs in PROJECTS.items()
        if not selected or name in selected
    }

    if not projects_to_import:
        known = ", ".join(PROJECTS)
        print(f"No matching projects found. Available: {known}")
        sys.exit(1)

    gh_session = _make_session(args.token)
    db = SessionLocal() if not args.dry_run else None

    total_new = 0
    total_skipped = 0
    total_scans = 0

    for project_name, slugs in projects_to_import.items():
        print(f"\nProject: {project_name}")

        if not args.dry_run:
            cr_project = db.query(Project).filter_by(name=project_name).first()
            if not cr_project:
                cr_project = Project(
                    name=project_name,
                    description=f"Popular open-source projects — {project_name}",
                )
                db.add(cr_project)
                db.commit()
                db.refresh(cr_project)
        else:
            cr_project = None

        for slug in slugs:
            repo_name = slug.split("/")[-1]
            clone_url = f"https://github.com/{slug}.git"

            # Fetch metadata from GitHub API if a token is provided
            meta: dict = {}
            if args.token:
                meta = _fetch_repo_meta(gh_session, slug)

            default_branch = meta.get("default_branch") or "main"

            if args.dry_run:
                print(f"  [DRY-RUN] {repo_name:<35} {clone_url}  (branch: {default_branch})")
                total_new += 1
                continue

            # Find or create the global Repository (deduplicated by URL)
            repository = db.query(Repository).filter_by(url=clone_url).first()
            if not repository:
                repository = Repository(
                    url=clone_url,
                    provider_type=ProviderType.github,
                )
                db.add(repository)
                db.commit()
                db.refresh(repository)

            # Find or create the project-scoped ProjectRepository
            pr = db.query(ProjectRepository).filter_by(
                project_id=cr_project.id,
                repository_id=repository.id,
            ).first()

            if pr:
                print(f"  [EXISTS]  {repo_name:<35} (skipped)")
                total_skipped += 1
                continue

            pr = ProjectRepository(
                project_id=cr_project.id,
                repository_id=repository.id,
                name=repo_name,
                default_branch=default_branch,
                credentials_username=None,
                credentials_token=args.token or None,
            )
            db.add(pr)
            db.commit()
            db.refresh(pr)
            print(f"  [NEW]     {repo_name:<35} {clone_url}")
            total_new += 1

            if args.scan:
                scan = Scan(
                    project_repository_id=pr.id,
                    branch=default_branch,
                    status=ScanStatus.pending,
                )
                db.add(scan)
                db.commit()
                total_scans += 1

    if db:
        db.close()

    print(f"\nImported: {total_new} new, {total_skipped} skipped.")
    if args.scan and total_scans:
        print(f"Scans enqueued: {total_scans}")
        print("Run the worker to process them: python -m app.worker")
    if args.dry_run:
        print("(Dry run — no changes were written to the database.)")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Import projects and repositories from a Bitbucket Server / Data Center instance.

Each Bitbucket project becomes a CodeRadar project. Repositories are imported
under their matching project. Already-imported repos are skipped (idempotent).

Usage:
    python scripts/import_bitbucket.py \\
        --base-url https://bitbucket.example.com \\
        --token <personal-access-token> \\
        [--username <user> --password <pass>]   # Basic Auth alternative
        [--project-key MYPROJ]                  # limit to one BB project
        [--default-branch main]                 # fallback branch name
        [--scan]                                # enqueue scans after import
        [--dry-run]                             # preview without DB writes

Credentials can also be supplied via environment variables:
    BITBUCKET_SERVER_URL
    BITBUCKET_SERVER_TOKEN
"""
import sys
import os
import argparse
import base64
from pathlib import Path
from typing import Iterator

import requests

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.db.session import SessionLocal
from app.models import Project, Repository, Scan, ScanStatus, ProviderType
from app.services.scanning.queue import enqueue
from app.core.logging import setup_logging, get_logger

logger = get_logger(__name__)

PAGE_LIMIT = 100


# ---------------------------------------------------------------------------
# Bitbucket Server REST API helpers
# ---------------------------------------------------------------------------

def _make_session(token: str | None, username: str | None, password: str | None) -> requests.Session:
    s = requests.Session()
    if token:
        s.headers["Authorization"] = f"Bearer {token}"
    elif username and password:
        credentials = base64.b64encode(f"{username}:{password}".encode()).decode()
        s.headers["Authorization"] = f"Basic {credentials}"
    s.headers["Accept"] = "application/json"
    return s


def _paginate(session: requests.Session, url: str, params: dict | None = None) -> Iterator[dict]:
    """Yield items from a paginated Bitbucket Server endpoint."""
    start = 0
    while True:
        p = {"start": start, "limit": PAGE_LIMIT, **(params or {})}
        resp = session.get(url, params=p, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        for item in data.get("values", []):
            yield item
        if data.get("isLastPage", True):
            break
        start = data["nextPageStart"]


def _get_projects(session: requests.Session, base_url: str, project_key: str | None) -> list[dict]:
    if project_key:
        resp = session.get(f"{base_url}/rest/api/1.0/projects/{project_key}", timeout=30)
        resp.raise_for_status()
        return [resp.json()]
    return list(_paginate(session, f"{base_url}/rest/api/1.0/projects"))


def _get_repos(session: requests.Session, base_url: str, project_key: str) -> Iterator[dict]:
    yield from _paginate(session, f"{base_url}/rest/api/1.0/projects/{project_key}/repos")


def _get_default_branch(session: requests.Session, base_url: str, project_key: str, repo_slug: str) -> str | None:
    try:
        resp = session.get(
            f"{base_url}/rest/api/1.0/projects/{project_key}/repos/{repo_slug}/default-branch",
            timeout=15,
        )
        if resp.ok:
            return resp.json().get("displayId")
    except Exception:
        pass
    return None


def _http_clone_url(repo: dict) -> str | None:
    for link in repo.get("links", {}).get("clone", []):
        if link.get("name") == "http":
            return link["href"]
    return None


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Import repositories from Bitbucket Server into CodeRadar"
    )
    parser.add_argument(
        "--base-url",
        default=os.environ.get("BITBUCKET_SERVER_URL", ""),
        help="Bitbucket Server base URL, e.g. https://bitbucket.example.com",
    )
    parser.add_argument(
        "--token",
        default=os.environ.get("BITBUCKET_SERVER_TOKEN", ""),
        help="Personal Access Token for authentication",
    )
    parser.add_argument("--username", default="", help="Username for Basic Auth")
    parser.add_argument("--password", default="", help="Password for Basic Auth")
    parser.add_argument("--project-key", default="", help="Import only this Bitbucket project key")
    parser.add_argument("--default-branch", default="main", help="Fallback branch name (default: main)")
    parser.add_argument("--scan", action="store_true", help="Enqueue scans for newly imported repos")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing to the database")
    args = parser.parse_args()

    if not args.base_url:
        print("Error: --base-url is required (or set BITBUCKET_SERVER_URL)")
        sys.exit(1)
    if not args.token and not (args.username and args.password):
        print("Error: provide --token or --username + --password")
        sys.exit(1)

    base_url = args.base_url.rstrip("/")
    setup_logging()

    session = _make_session(
        token=args.token or None,
        username=args.username or None,
        password=args.password or None,
    )

    # Store credentials that will be saved per-repository so the worker can clone
    store_username = args.username or None
    store_token = args.token or args.password or None

    db = SessionLocal() if not args.dry_run else None

    total_new = 0
    total_skipped = 0
    total_scans = 0

    try:
        projects = _get_projects(session, base_url, args.project_key or None)
    except requests.HTTPError as e:
        print(f"Error fetching projects from Bitbucket: {e}")
        sys.exit(1)

    for bb_project in projects:
        bb_key = bb_project["key"]
        bb_name = bb_project.get("name", bb_key)
        print(f"\nProject: {bb_key} ({bb_name})")

        if not args.dry_run:
            cr_project = db.query(Project).filter_by(name=bb_name).first()
            if not cr_project:
                cr_project = Project(name=bb_name, description=f"Imported from Bitbucket project {bb_key}")
                db.add(cr_project)
                db.commit()
                db.refresh(cr_project)

        try:
            repos = list(_get_repos(session, base_url, bb_key))
        except requests.HTTPError as e:
            print(f"  Warning: could not fetch repos for {bb_key}: {e}")
            continue

        for repo in repos:
            if repo.get("scmId") != "git":
                continue  # skip non-git repos (e.g. Mercurial)

            slug = repo["slug"]
            name = repo.get("name", slug)
            clone_url = _http_clone_url(repo)

            if not clone_url:
                print(f"  [SKIP]    {name:<40} (no HTTP clone URL)")
                continue

            default_branch = (
                _get_default_branch(session, base_url, bb_key, slug)
                or args.default_branch
            )

            if args.dry_run:
                print(f"  [DRY-RUN] {name:<40} {clone_url}")
                total_new += 1
                continue

            existing = db.query(Repository).filter_by(
                project_id=cr_project.id, url=clone_url
            ).first()

            if existing:
                print(f"  [EXISTS]  {name:<40} (skipped)")
                total_skipped += 1
                continue

            repo_record = Repository(
                project_id=cr_project.id,
                name=name,
                url=clone_url,
                provider_type=ProviderType.bitbucket,
                default_branch=default_branch,
                credentials_username=store_username,
                credentials_token=store_token,
            )
            db.add(repo_record)
            db.commit()
            db.refresh(repo_record)
            print(f"  [NEW]     {name:<40} {clone_url}")
            total_new += 1

            if args.scan:
                scan = Scan(
                    repository_id=repo_record.id,
                    branch=default_branch,
                    status=ScanStatus.pending,
                )
                db.add(scan)
                db.commit()
                db.refresh(scan)
                enqueue(scan.id)
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

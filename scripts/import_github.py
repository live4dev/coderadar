#!/usr/bin/env python3
"""
Import repositories from GitHub into CodeRadar.

Use --org to import an organisation's repositories, --user to import a specific
user's repositories, or omit both to import the token owner's repositories.
Each org / user becomes a single CodeRadar project. Already-imported repos are
skipped (idempotent).

Usage:
    python scripts/import_github.py \\
        --token <personal-access-token> \\
        [--org <github-org>]            # import org repos
        [--user <github-user>]          # import user repos
        [--skip-archived]               # skip archived repositories
        [--skip-forks]                  # skip forked repositories
        [--default-branch main]         # fallback branch name
        [--scan]                        # enqueue scans after import
        [--dry-run]                     # preview without DB writes

Credentials can also be supplied via environment variables:
    GITHUB_TOKEN
"""
import sys
import os
import argparse
import re
from pathlib import Path
from typing import Iterator

import requests

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.db.session import SessionLocal
from app.models import Project, Repository, Scan, ScanStatus, ProviderType
from app.services.scanning.queue import enqueue
from app.core.logging import setup_logging, get_logger

logger = get_logger(__name__)

GITHUB_API = "https://api.github.com"
PER_PAGE = 100


# ---------------------------------------------------------------------------
# GitHub API helpers
# ---------------------------------------------------------------------------

def _make_session(token: str) -> requests.Session:
    s = requests.Session()
    s.headers["Authorization"] = f"Bearer {token}"
    s.headers["Accept"] = "application/vnd.github+json"
    s.headers["X-GitHub-Api-Version"] = "2022-11-28"
    return s


def _paginate(session: requests.Session, url: str, params: dict | None = None) -> Iterator[dict]:
    """Yield items from a paginated GitHub API endpoint (Link header)."""
    next_url: str | None = url
    base_params = {"per_page": PER_PAGE, **(params or {})}
    first = True
    while next_url:
        resp = session.get(next_url, params=base_params if first else None, timeout=30)
        resp.raise_for_status()
        first = False
        yield from resp.json()
        # Parse rel="next" from Link header
        link_header = resp.headers.get("Link", "")
        match = re.search(r'<([^>]+)>;\s*rel="next"', link_header)
        next_url = match.group(1) if match else None


def _get_authenticated_user(session: requests.Session) -> str:
    resp = session.get(f"{GITHUB_API}/user", timeout=30)
    resp.raise_for_status()
    return resp.json()["login"]


def _get_repos(session: requests.Session, org: str, user: str) -> tuple[str, Iterator[dict]]:
    """Return (project_name, repo_iterator) based on --org / --user flags."""
    if org:
        return org, _paginate(session, f"{GITHUB_API}/orgs/{org}/repos", {"type": "all"})
    if user:
        return user, _paginate(session, f"{GITHUB_API}/users/{user}/repos", {"type": "all"})
    # Fall back to token owner's repos
    owner = _get_authenticated_user(session)
    return owner, _paginate(session, f"{GITHUB_API}/user/repos", {"affiliation": "owner"})


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Import repositories from GitHub into CodeRadar"
    )
    parser.add_argument(
        "--token",
        default=os.environ.get("GITHUB_TOKEN", ""),
        help="GitHub Personal Access Token",
    )
    parser.add_argument("--org", default="", help="Import repos from this GitHub organisation")
    parser.add_argument("--user", default="", help="Import repos from this GitHub user")
    parser.add_argument(
        "--skip-archived",
        action="store_true",
        help="Skip archived repositories",
    )
    parser.add_argument(
        "--skip-forks",
        action="store_true",
        help="Skip forked repositories",
    )
    parser.add_argument(
        "--default-branch",
        default="main",
        help="Fallback branch name when not set on the repo (default: main)",
    )
    parser.add_argument("--scan", action="store_true", help="Enqueue scans for newly imported repos")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing to the database")
    args = parser.parse_args()

    if not args.token:
        print("Error: --token is required (or set GITHUB_TOKEN)")
        sys.exit(1)

    setup_logging()
    session = _make_session(args.token)

    try:
        project_name, repo_iter = _get_repos(session, args.org, args.user)
    except requests.HTTPError as e:
        print(f"Error fetching repositories from GitHub: {e}")
        sys.exit(1)

    print(f"\nProject: {project_name}")

    db = SessionLocal() if not args.dry_run else None

    if not args.dry_run:
        cr_project = db.query(Project).filter_by(name=project_name).first()
        if not cr_project:
            cr_project = Project(
                name=project_name,
                description=f"Imported from GitHub ({args.org or args.user or 'owner'})",
            )
            db.add(cr_project)
            db.commit()
            db.refresh(cr_project)
    else:
        cr_project = None

    total_new = 0
    total_skipped = 0
    total_scans = 0

    try:
        for repo in repo_iter:
            if args.skip_archived and repo.get("archived"):
                continue
            if args.skip_forks and repo.get("fork"):
                continue

            name = repo["name"]
            clone_url = repo.get("clone_url")

            if not clone_url:
                print(f"  [SKIP]    {name:<40} (no clone URL)")
                continue

            default_branch = repo.get("default_branch") or args.default_branch

            if args.dry_run:
                markers = []
                if repo.get("archived"):
                    markers.append("archived")
                if repo.get("fork"):
                    markers.append("fork")
                suffix = f" [{', '.join(markers)}]" if markers else ""
                print(f"  [DRY-RUN] {name:<40} {clone_url}{suffix}")
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
                provider_type=ProviderType.github,
                default_branch=default_branch,
                credentials_username=None,
                credentials_token=args.token,
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

    except requests.HTTPError as e:
        print(f"Error fetching repository list: {e}")
        if db:
            db.close()
        sys.exit(1)

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

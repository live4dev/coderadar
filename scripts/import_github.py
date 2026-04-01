#!/usr/bin/env python3
"""
Import repositories from GitHub into CodeRadar.

Use --org to import an organisation's repositories, --user to import a specific
user's repositories, --url to derive the org/user from a GitHub URL, or omit
all three to import the token owner's repositories (requires --token).
Each org / user becomes a single CodeRadar project. Already-imported repos are
skipped (idempotent).

Usage:
    python scripts/import_github.py \\
        [--token <personal-access-token>] \\
        [--url https://github.com/wemake-services]  # import by GitHub URL
        [--org <github-org>]            # import org repos
        [--user <github-user>]          # import user repos
        [--skip-archived]               # skip archived repositories
        [--skip-forks]                  # skip forked repositories
        [--default-branch main]         # fallback branch name
        [--scan]                        # enqueue scans after import
        [--dry-run]                     # preview without DB writes

Credentials can also be supplied via environment variables:
    GITHUB_TOKEN

Note: without --token, GitHub's unauthenticated rate limit applies (60 req/hr).
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
from app.models import Project, Repository, ProjectRepository, Scan, ScanStatus, ProviderType
from app.core.logging import setup_logging, get_logger

logger = get_logger(__name__)

GITHUB_API = "https://api.github.com"
PER_PAGE = 100


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


def _parse_github_url(url: str) -> tuple[str, str]:
    """Parse a GitHub org/user URL and return (kind, name).

    Accepts forms like:
      https://github.com/wemake-services
      https://github.com/wemake-services/
      github.com/wemake-services

    Returns ('org', 'wemake-services') — callers must probe the API to
    distinguish orgs from users, so we return 'org' as the default kind
    and fall back to 'user' on a 404.
    """
    # Strip scheme and trailing slashes, then take the first path segment
    cleaned = re.sub(r"^https?://", "", url).strip("/")
    parts = cleaned.split("/")
    if len(parts) < 2 or parts[0].lower() != "github.com":
        raise ValueError(f"Cannot parse GitHub URL: {url!r}. Expected https://github.com/<org-or-user>")
    name = parts[1]
    if not name:
        raise ValueError(f"No org/user name found in URL: {url!r}")
    return name


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


def _get_repos_by_name(session: requests.Session, name: str) -> tuple[str, Iterator[dict]]:
    """Probe GitHub to determine if *name* is an org or a user, then return repos.

    Tries the orgs endpoint first; falls back to users if the org returns 404.
    """
    resp = session.get(f"{GITHUB_API}/orgs/{name}", timeout=30)
    if resp.status_code == 200:
        return name, _paginate(session, f"{GITHUB_API}/orgs/{name}/repos", {"type": "all"})
    if resp.status_code == 404:
        # Not an org — try as a user
        resp2 = session.get(f"{GITHUB_API}/users/{name}", timeout=30)
        resp2.raise_for_status()
        return name, _paginate(session, f"{GITHUB_API}/users/{name}/repos", {"type": "all"})
    resp.raise_for_status()
    raise RuntimeError("Unreachable")


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
        help="GitHub Personal Access Token (optional for public repos; unauthenticated rate limit: 60 req/hr)",
    )
    parser.add_argument(
        "--url",
        default="",
        help="GitHub org or user URL, e.g. https://github.com/wemake-services",
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

    if not args.token and not args.url and not args.org and not args.user:
        print("Error: --token is required when importing the authenticated user's own repos.")
        print("To import a public org or user without a token, use --url https://github.com/<name>")
        sys.exit(1)

    setup_logging()
    session = _make_session(args.token)

    try:
        if args.url:
            name = _parse_github_url(args.url)
            project_name, repo_iter = _get_repos_by_name(session, name)
        else:
            project_name, repo_iter = _get_repos(session, args.org, args.user)
    except (requests.HTTPError, ValueError) as e:
        print(f"Error fetching repositories from GitHub: {e}")
        sys.exit(1)

    print(f"\nProject: {project_name}")

    db = SessionLocal() if not args.dry_run else None

    if not args.dry_run:
        cr_project = db.query(Project).filter_by(name=project_name).first()
        if not cr_project:
            cr_project = Project(
                name=project_name,
                description=f"Imported from GitHub ({args.url or args.org or args.user or 'owner'})",
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
                print(f"  [EXISTS]  {name:<40} (skipped)")
                total_skipped += 1
                continue

            pr = ProjectRepository(
                project_id=cr_project.id,
                repository_id=repository.id,
                name=name,
                default_branch=default_branch,
                credentials_username=None,
                credentials_token=args.token or None,
            )
            db.add(pr)
            db.commit()
            db.refresh(pr)
            print(f"  [NEW]     {name:<40} {clone_url}")
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

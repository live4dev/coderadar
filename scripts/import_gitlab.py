#!/usr/bin/env python3
"""
Import groups and repositories from a GitLab instance into CodeRadar.

Each GitLab group becomes a CodeRadar project. Repositories are imported
under their matching group. Already-imported repos are skipped (idempotent).

Usage:
    python scripts/import_gitlab.py \\
        --token <personal-access-token> \\
        [--base-url https://gitlab.com]  # default
        [--group <group-path-or-id>]     # limit to one group (+ subgroups)
        [--project-name "My Project"]    # override CodeRadar project name
        [--skip-archived]                # skip archived repositories
        [--default-branch main]          # fallback branch name
        [--scan]                         # enqueue scans after import
        [--dry-run]                      # preview without DB writes

Credentials can also be supplied via environment variables:
    GITLAB_TOKEN
    GITLAB_URL
"""
import sys
import os
import argparse
from pathlib import Path
from typing import Iterator

import requests

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.db.session import SessionLocal
from app.models import Project, Repository, Scan, ScanStatus, ProviderType
from app.services.scanning.queue import enqueue
from app.core.logging import setup_logging, get_logger

logger = get_logger(__name__)

PER_PAGE = 100


# ---------------------------------------------------------------------------
# GitLab API helpers
# ---------------------------------------------------------------------------

def _make_session(token: str) -> requests.Session:
    s = requests.Session()
    s.headers["PRIVATE-TOKEN"] = token
    s.headers["Accept"] = "application/json"
    return s


def _paginate(session: requests.Session, url: str, params: dict | None = None) -> Iterator[dict]:
    """Yield items from a paginated GitLab API endpoint (X-Next-Page header)."""
    page = 1
    while True:
        p = {"per_page": PER_PAGE, "page": page, **(params or {})}
        resp = session.get(url, params=p, timeout=30)
        resp.raise_for_status()
        items = resp.json()
        if not items:
            break
        yield from items
        next_page = resp.headers.get("X-Next-Page", "")
        if not next_page:
            break
        page = int(next_page)


def _get_groups(session: requests.Session, base_url: str, group_filter: str | None) -> list[dict]:
    """Return list of groups to import. If group_filter given, returns only that group."""
    api = f"{base_url}/api/v4"
    if group_filter:
        # group_filter may be a numeric ID or URL-encoded path
        resp = session.get(f"{api}/groups/{requests.utils.quote(group_filter, safe='')}", timeout=30)
        resp.raise_for_status()
        return [resp.json()]
    return list(_paginate(session, f"{api}/groups", params={"top_level_only": "true"}))


def _get_group_repos(
    session: requests.Session, base_url: str, group_id: int | str
) -> Iterator[dict]:
    """Yield all projects in a group (including subgroups)."""
    api = f"{base_url}/api/v4"
    yield from _paginate(
        session,
        f"{api}/groups/{group_id}/projects",
        params={"include_subgroups": "true", "with_shared": "false"},
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Import repositories from GitLab into CodeRadar"
    )
    parser.add_argument(
        "--base-url",
        default=os.environ.get("GITLAB_URL", "https://gitlab.com"),
        help="GitLab base URL (default: https://gitlab.com)",
    )
    parser.add_argument(
        "--token",
        default=os.environ.get("GITLAB_TOKEN", ""),
        help="GitLab Personal Access Token",
    )
    parser.add_argument(
        "--group",
        default="",
        help="Import only this group (path or numeric ID, includes subgroups)",
    )
    parser.add_argument(
        "--project-name",
        default="",
        help="Override CodeRadar project name (only used with --group)",
    )
    parser.add_argument(
        "--skip-archived",
        action="store_true",
        help="Skip archived repositories",
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
        print("Error: --token is required (or set GITLAB_TOKEN)")
        sys.exit(1)

    base_url = args.base_url.rstrip("/")
    setup_logging()

    session = _make_session(args.token)

    db = SessionLocal() if not args.dry_run else None

    total_new = 0
    total_skipped = 0
    total_scans = 0

    try:
        groups = _get_groups(session, base_url, args.group or None)
    except requests.HTTPError as e:
        print(f"Error fetching groups from GitLab: {e}")
        sys.exit(1)

    for group in groups:
        group_id = group["id"]
        group_name = args.project_name or group.get("full_path") or group.get("name", str(group_id))
        print(f"\nGroup: {group_name}")

        if not args.dry_run:
            cr_project = db.query(Project).filter_by(name=group_name).first()
            if not cr_project:
                cr_project = Project(
                    name=group_name,
                    description=f"Imported from GitLab group {group.get('full_path', group_id)}",
                )
                db.add(cr_project)
                db.commit()
                db.refresh(cr_project)

        try:
            repos = list(_get_group_repos(session, base_url, group_id))
        except requests.HTTPError as e:
            print(f"  Warning: could not fetch repos for group {group_name}: {e}")
            continue

        for repo in repos:
            if args.skip_archived and repo.get("archived"):
                continue

            name = repo.get("name", repo.get("path", "unknown"))
            clone_url = repo.get("http_url_to_repo")

            if not clone_url:
                print(f"  [SKIP]    {name:<40} (no HTTP clone URL)")
                continue

            default_branch = repo.get("default_branch") or args.default_branch

            if args.dry_run:
                archived_marker = " [archived]" if repo.get("archived") else ""
                print(f"  [DRY-RUN] {name:<40} {clone_url}{archived_marker}")
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
                provider_type=ProviderType.gitlab,
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

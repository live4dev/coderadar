from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from collections import defaultdict
from pathlib import Path
from typing import Dict

from app.services.git_analytics.git_parser import CommitRecord, parse_git_log_v2
from app.services.identity.normalizer import normalize_identity, NormalizedIdentity


@dataclass
class AuthorKey:
    raw_name: str
    raw_email: str


@dataclass
class DeveloperStats:
    canonical_username: str
    display_name: str
    primary_email: str
    identity: NormalizedIdentity
    raw_identities: list[tuple[str, str]] = field(default_factory=list)  # (name, email)

    commit_count: int = 0
    insertions: int = 0
    deletions: int = 0
    files_changed: int = 0
    active_days: int = 0
    first_commit_at: datetime | None = None
    last_commit_at: datetime | None = None

    # language → (commits, files, loc_added, loc_deleted)
    language_stats: dict[str, list[int]] = field(default_factory=lambda: defaultdict(lambda: [0, 0, 0, 0]))

    # module path → (commits, files, loc_added)
    module_stats: dict[str, list[int]] = field(default_factory=lambda: defaultdict(lambda: [0, 0, 0]))

    # date string YYYY-MM-DD → commit count
    daily_commits: Dict[str, int] = field(default_factory=lambda: defaultdict(int))


def _get_module(filepath: str) -> str:
    """Return top-level directory as module name."""
    parts = Path(filepath).parts
    if len(parts) >= 2:
        return parts[0]
    return "root"


def aggregate_contributions(
    repo_path: Path,
    overrides: dict[str, str] | None = None,
    python_lang_name: str = "Python",
) -> list[DeveloperStats]:
    commits = parse_git_log_v2(repo_path, python_lang_name=python_lang_name)
    overrides = overrides or {}

    # Group commits by canonical username
    developer_map: dict[str, DeveloperStats] = {}
    # raw_key → canonical_username for deduplication
    identity_cache: dict[tuple[str, str], str] = {}

    for commit in commits:
        raw_key = (commit.author_name, commit.author_email)

        if raw_key in identity_cache:
            username = identity_cache[raw_key]
        else:
            identity = normalize_identity(commit.author_name, commit.author_email, overrides)
            username = identity.canonical_username
            identity_cache[raw_key] = username

            if username not in developer_map:
                developer_map[username] = DeveloperStats(
                    canonical_username=username,
                    display_name=commit.author_name,
                    primary_email=commit.author_email,
                    identity=identity,
                )
            developer_map[username].raw_identities.append(raw_key)

        dev = developer_map[username]
        dev.commit_count += 1

        day_str = commit.timestamp.strftime("%Y-%m-%d")
        dev.daily_commits[day_str] += 1

        if dev.first_commit_at is None or commit.timestamp < dev.first_commit_at:
            dev.first_commit_at = commit.timestamp
        if dev.last_commit_at is None or commit.timestamp > dev.last_commit_at:
            dev.last_commit_at = commit.timestamp

        files_in_commit: set[str] = set()
        for fc in commit.file_changes:
            dev.insertions += fc.insertions
            dev.deletions += fc.deletions
            files_in_commit.add(fc.path)

            if fc.language:
                lang_stat = dev.language_stats[fc.language]
                lang_stat[0] += 1        # commits (approximate)
                lang_stat[1] += 1        # files
                lang_stat[2] += fc.insertions
                lang_stat[3] += fc.deletions

            module = _get_module(fc.path)
            mod_stat = dev.module_stats[module]
            mod_stat[0] += 1             # commits
            mod_stat[1] += 1             # files
            mod_stat[2] += fc.insertions

        dev.files_changed += len(files_in_commit)

    for dev in developer_map.values():
        dev.active_days = len(dev.daily_commits)

    return list(developer_map.values())

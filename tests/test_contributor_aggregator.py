from __future__ import annotations
from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from app.services.git_analytics.contributor_aggregator import (
    aggregate_contributions, DeveloperStats,
)
from app.services.git_analytics.git_parser import CommitRecord, FileChange


def _ts(year: int, month: int, day: int) -> datetime:
    return datetime(year, month, day, tzinfo=timezone.utc)


def _commit(
    sha: str,
    author_name: str,
    author_email: str,
    ts: datetime,
    file_changes: list[FileChange] | None = None,
) -> CommitRecord:
    c = CommitRecord(sha, author_name, author_email, ts)
    c.file_changes = file_changes or []
    return c


# ── Basic aggregation ─────────────────────────────────────────────────────────

def test_single_developer(tmp_path):
    commits = [
        _commit("aaa", "Alice", "alice@x.com", _ts(2024, 1, 1),
                [FileChange("src/app.py", 10, 2, "Python")]),
        _commit("bbb", "Alice", "alice@x.com", _ts(2024, 1, 2),
                [FileChange("src/utils.py", 5, 0, "Python")]),
    ]
    with patch("app.services.git_analytics.contributor_aggregator.parse_git_log_v2", return_value=commits):
        devs = aggregate_contributions(tmp_path)

    assert len(devs) == 1
    dev = devs[0]
    assert dev.commit_count == 2
    assert dev.insertions == 15
    assert dev.deletions == 2
    assert dev.active_days == 2


def test_two_developers(tmp_path):
    commits = [
        _commit("aaa", "Alice", "alice@x.com", _ts(2024, 1, 1)),
        _commit("bbb", "Bob", "bob@x.com", _ts(2024, 1, 2)),
        _commit("ccc", "Alice", "alice@x.com", _ts(2024, 1, 3)),
    ]
    with patch("app.services.git_analytics.contributor_aggregator.parse_git_log_v2", return_value=commits):
        devs = aggregate_contributions(tmp_path)

    assert len(devs) == 2
    usernames = {d.canonical_username for d in devs}
    assert len(usernames) == 2


# ── Identity deduplication (aliases) ─────────────────────────────────────────

def test_alias_deduplication(tmp_path):
    """Same person committing with two different email addresses."""
    commits = [
        _commit("aaa", "Dmitry Ivanov", "d.ivanov@corp.com", _ts(2024, 1, 1)),
        _commit("bbb", "Dmitry Ivanov", "d.ivanov@personal.com", _ts(2024, 1, 2)),
    ]
    overrides = {"d.ivanov@personal.com": "d_ivanov"}
    with patch("app.services.git_analytics.contributor_aggregator.parse_git_log_v2", return_value=commits):
        devs = aggregate_contributions(tmp_path, overrides)

    # With override the second email maps to d_ivanov; first will also normalize
    # to d_ivanov → should merge into 1 developer
    d_ivanov_devs = [d for d in devs if d.canonical_username == "d_ivanov"]
    assert len(d_ivanov_devs) == 1
    assert d_ivanov_devs[0].commit_count == 2


def test_name_override(tmp_path):
    commits = [
        _commit("aaa", "Old Name", "dev@x.com", _ts(2024, 1, 1)),
    ]
    overrides = {"old name": "new_canonical"}
    with patch("app.services.git_analytics.contributor_aggregator.parse_git_log_v2", return_value=commits):
        devs = aggregate_contributions(tmp_path, overrides)

    assert devs[0].canonical_username == "new_canonical"


# ── Multi-language tracking ───────────────────────────────────────────────────

def test_language_stats(tmp_path):
    commits = [
        _commit("aaa", "Alice", "alice@x.com", _ts(2024, 1, 1), [
            FileChange("src/app.py", 20, 5, "Python"),
            FileChange("frontend/index.ts", 10, 0, "TypeScript"),
        ]),
    ]
    with patch("app.services.git_analytics.contributor_aggregator.parse_git_log_v2", return_value=commits):
        devs = aggregate_contributions(tmp_path)

    dev = devs[0]
    assert "Python" in dev.language_stats
    assert "TypeScript" in dev.language_stats
    assert dev.language_stats["Python"][2] == 20  # loc_added
    assert dev.language_stats["TypeScript"][2] == 10


def test_module_stats(tmp_path):
    commits = [
        _commit("aaa", "Alice", "alice@x.com", _ts(2024, 1, 1), [
            FileChange("backend/api.py", 10, 0, "Python"),
            FileChange("backend/models.py", 5, 0, "Python"),
            FileChange("frontend/app.ts", 8, 0, "TypeScript"),
        ]),
    ]
    with patch("app.services.git_analytics.contributor_aggregator.parse_git_log_v2", return_value=commits):
        devs = aggregate_contributions(tmp_path)

    dev = devs[0]
    assert "backend" in dev.module_stats
    assert "frontend" in dev.module_stats
    assert dev.module_stats["backend"][1] == 2  # files_changed


# ── Edge cases ────────────────────────────────────────────────────────────────

def test_empty_repo(tmp_path):
    with patch("app.services.git_analytics.contributor_aggregator.parse_git_log_v2", return_value=[]):
        devs = aggregate_contributions(tmp_path)
    assert devs == []


def test_first_last_commit_tracking(tmp_path):
    ts1 = _ts(2023, 6, 1)
    ts2 = _ts(2024, 3, 15)
    commits = [
        _commit("aaa", "Alice", "alice@x.com", ts2),
        _commit("bbb", "Alice", "alice@x.com", ts1),
    ]
    with patch("app.services.git_analytics.contributor_aggregator.parse_git_log_v2", return_value=commits):
        devs = aggregate_contributions(tmp_path)

    dev = devs[0]
    assert dev.first_commit_at == ts1
    assert dev.last_commit_at == ts2

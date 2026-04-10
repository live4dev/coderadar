from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import pytest

from app.services.git_analytics.git_parser import (
    _clean_filepath,
    get_head_sha,
    parse_git_log_v2,
)

_SEP = "CODERADAR_COMMIT_SEP"


def _log(*commits: dict) -> str:
    """Build a fake git log string from a list of commit dicts."""
    parts = []
    for c in commits:
        block = (
            f"{_SEP}\n"
            f"{c.get('sha', 'abc' * 13 + 'ab')}\n"
            f"{c.get('name', 'Dev Name')}\n"
            f"{c.get('email', 'dev@example.com')}\n"
            f"{c.get('ts', '2024-06-01T12:00:00+00:00')}\n"
        )
        for path, ins, dels in c.get("files", []):
            block += f"{ins}\t{dels}\t{path}\n"
        parts.append(block)
    return "\n".join(parts)


# ── _clean_filepath ───────────────────────────────────────────────────────────

def test_clean_filepath_normal():
    assert _clean_filepath("src/main.py") == "src/main.py"


def test_clean_filepath_strips_whitespace():
    assert _clean_filepath("  src/main.py  ") == "src/main.py"


def test_clean_filepath_null_byte_returns_none():
    assert _clean_filepath("src\x00main.py") is None


def test_clean_filepath_replacement_char_returns_none():
    assert _clean_filepath("src\ufffdmain.py") is None


def test_clean_filepath_empty_after_strip_returns_none():
    assert _clean_filepath("   ") is None


def test_clean_filepath_curly_rename():
    result = _clean_filepath("src/{old_dir => new_dir}/file.py")
    assert result == "src/new_dir/file.py"


def test_clean_filepath_curly_rename_empty_new():
    result = _clean_filepath("src/{old => }/file.py")
    assert result == "src//file.py"


def test_clean_filepath_simple_rename():
    result = _clean_filepath("old_file.py => new_file.py")
    assert result == "new_file.py"


# ── parse_git_log_v2 ──────────────────────────────────────────────────────────

def test_parse_empty_output():
    with patch("app.services.git_analytics.git_parser._run_git", return_value=""):
        commits = parse_git_log_v2(Path("/fake/repo"))
    assert commits == []


def test_parse_single_commit():
    raw = _log({"sha": "a" * 40, "name": "Alice", "email": "alice@x.com",
                "ts": "2024-03-10T08:00:00+00:00",
                "files": [("src/app.py", 10, 2)]})
    with patch("app.services.git_analytics.git_parser._run_git", return_value=raw):
        commits = parse_git_log_v2(Path("/fake/repo"))
    assert len(commits) == 1
    c = commits[0]
    assert c.author_name == "Alice"
    assert c.author_email == "alice@x.com"
    assert isinstance(c.timestamp, datetime)


def test_parse_file_change_stats():
    raw = _log({"sha": "b" * 40, "files": [("app/main.py", 15, 3), ("lib/util.py", 5, 1)]})
    with patch("app.services.git_analytics.git_parser._run_git", return_value=raw):
        commits = parse_git_log_v2(Path("/fake/repo"))
    fc = {f.path: f for f in commits[0].file_changes}
    assert fc["app/main.py"].insertions == 15
    assert fc["app/main.py"].deletions == 3
    assert fc["lib/util.py"].insertions == 5


def test_parse_two_commits():
    raw = _log(
        {"sha": "a" * 40, "name": "Alice", "email": "a@x.com",
         "ts": "2024-03-10T08:00:00+00:00", "files": [("src/a.py", 1, 0)]},
        {"sha": "b" * 40, "name": "Bob", "email": "b@x.com",
         "ts": "2024-03-09T08:00:00+00:00", "files": [("src/b.py", 2, 1)]},
    )
    with patch("app.services.git_analytics.git_parser._run_git", return_value=raw):
        commits = parse_git_log_v2(Path("/fake/repo"))
    assert len(commits) == 2


def test_parse_skips_short_sha():
    raw = (
        f"{_SEP}\n"
        "abc\n"           # sha too short (< 7)
        "Dev\n"
        "dev@x.com\n"
        "2024-01-01T00:00:00+00:00\n"
        "5\t2\tfile.py\n"
    )
    with patch("app.services.git_analytics.git_parser._run_git", return_value=raw):
        commits = parse_git_log_v2(Path("/fake/repo"))
    assert commits == []


def test_parse_skips_invalid_timestamp():
    raw = (
        f"{_SEP}\n"
        + "a" * 40 + "\n"
        "Dev\n"
        "dev@x.com\n"
        "not-a-date\n"
        "5\t2\tfile.py\n"
    )
    with patch("app.services.git_analytics.git_parser._run_git", return_value=raw):
        commits = parse_git_log_v2(Path("/fake/repo"))
    assert commits == []


def test_parse_skips_incomplete_block():
    raw = f"{_SEP}\nonly_sha\nOnly Name\n"
    with patch("app.services.git_analytics.git_parser._run_git", return_value=raw):
        commits = parse_git_log_v2(Path("/fake/repo"))
    assert commits == []


def test_parse_binary_file_uses_zero():
    raw = (
        f"{_SEP}\n"
        + "a" * 40 + "\n"
        "Dev\ndev@x.com\n2024-01-01T00:00:00+00:00\n"
        "-\t-\timage.png\n"
        "10\t3\tsrc/main.py\n"
    )
    with patch("app.services.git_analytics.git_parser._run_git", return_value=raw):
        commits = parse_git_log_v2(Path("/fake/repo"))
    assert len(commits) == 1
    png = next((f for f in commits[0].file_changes if f.path == "image.png"), None)
    assert png is not None
    assert png.insertions == 0
    assert png.deletions == 0


def test_parse_skips_node_modules():
    raw = (
        f"{_SEP}\n"
        + "a" * 40 + "\n"
        "Dev\ndev@x.com\n2024-01-01T00:00:00+00:00\n"
        "5\t2\tnode_modules/dep/index.js\n"
        "10\t3\tsrc/main.py\n"
    )
    with patch("app.services.git_analytics.git_parser._run_git", return_value=raw):
        commits = parse_git_log_v2(Path("/fake/repo"))
    paths = {f.path for f in commits[0].file_changes}
    assert "node_modules/dep/index.js" not in paths
    assert "src/main.py" in paths


def test_parse_language_detected_for_known_ext():
    raw = _log({"sha": "a" * 40, "files": [("app/main.py", 5, 1)]})
    with patch("app.services.git_analytics.git_parser._run_git", return_value=raw):
        commits = parse_git_log_v2(Path("/fake/repo"))
    fc = commits[0].file_changes[0]
    assert fc.language == "Python"


def test_parse_language_none_for_unknown_ext():
    raw = _log({"sha": "a" * 40, "files": [("data/file.xyz", 5, 1)]})
    with patch("app.services.git_analytics.git_parser._run_git", return_value=raw):
        commits = parse_git_log_v2(Path("/fake/repo"))
    fc = commits[0].file_changes[0]
    assert fc.language is None


def test_parse_git_log_v2_uses_all_flag(tmp_path):
    """Ensure --all is passed so commits from all branches are captured."""
    with patch("app.services.git_analytics.git_parser._run_git", return_value="") as mock_run:
        parse_git_log_v2(tmp_path)
    called_args = mock_run.call_args[0]
    assert "--all" in called_args


# ── get_head_sha ──────────────────────────────────────────────────────────────

def test_get_head_sha():
    with patch("app.services.git_analytics.git_parser._run_git",
               return_value="deadbeef1234\n"):
        sha = get_head_sha(Path("/fake/repo"))
    assert sha == "deadbeef1234"


def test_get_head_sha_strips_newline():
    with patch("app.services.git_analytics.git_parser._run_git",
               return_value="abc123\n\n"):
        sha = get_head_sha(Path("/fake/repo"))
    assert sha == "abc123"

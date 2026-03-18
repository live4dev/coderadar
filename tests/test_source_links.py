"""Tests for source_links URL builder (GitHub, GitLab, Bitbucket)."""
import pytest
from app.services.source_links import build_source_url


# ── GitHub ──────────────────────────────────────────────────────────────────


def test_github_https_repo_only() -> None:
    url = build_source_url(
        "https://github.com/owner/repo.git",
        "github",
        "main",
        None,
        None,
    )
    assert url == "https://github.com/owner/repo/tree/main"


def test_github_https_file_line() -> None:
    url = build_source_url(
        "https://github.com/org/proj.git",
        "github",
        "abc123",
        "src/auth.py",
        42,
    )
    assert url == "https://github.com/org/proj/blob/abc123/src/auth.py#L42"


def test_github_ssh_file_line() -> None:
    url = build_source_url(
        "git@github.com:foo/bar.git",
        "github",
        "develop",
        "lib/utils.py",
        10,
    )
    assert url == "https://github.com/foo/bar/blob/develop/lib/utils.py#L10"


def test_github_repo_only_empty_ref_uses_head() -> None:
    url = build_source_url(
        "https://github.com/a/b",
        "github",
        "",
        None,
        None,
    )
    assert url == "https://github.com/a/b/tree/HEAD"


# ── GitLab ───────────────────────────────────────────────────────────────────


def test_gitlab_https_repo_only() -> None:
    url = build_source_url(
        "https://gitlab.com/group/subgroup/repo.git",
        "gitlab",
        "main",
        None,
        None,
    )
    assert url == "https://gitlab.com/group/subgroup/repo/-/tree/main"


def test_gitlab_https_file_line() -> None:
    url = build_source_url(
        "https://gitlab.com/team/app.git",
        "gitlab",
        "v1.0",
        "backend/models.py",
        100,
    )
    assert url == "https://gitlab.com/team/app/-/blob/v1.0/backend/models.py#L100"


def test_gitlab_ssh_file_line() -> None:
    url = build_source_url(
        "git@gitlab.com:myorg/myrepo.git",
        "gitlab",
        "master",
        "README.md",
        1,
    )
    assert url == "https://gitlab.com/myorg/myrepo/-/blob/master/README.md#L1"


# ── Bitbucket ─────────────────────────────────────────────────────────────────


def test_bitbucket_https_repo_only() -> None:
    url = build_source_url(
        "https://bitbucket.org/workspace/repo.git",
        "bitbucket",
        "main",
        None,
        None,
    )
    assert url == "https://bitbucket.org/workspace/repo/src/main"


def test_bitbucket_https_file_line() -> None:
    url = build_source_url(
        "https://bitbucket.org/team/project.git",
        "bitbucket",
        "develop",
        "src/main.py",
        5,
    )
    assert url == "https://bitbucket.org/team/project/src/develop/src/main.py#lines-5"


def test_bitbucket_ssh_file_line() -> None:
    url = build_source_url(
        "git@bitbucket.org:org/repo.git",
        "bitbucket",
        "feature",
        "app/config.yaml",
        20,
    )
    assert url == "https://bitbucket.org/org/repo/src/feature/app/config.yaml#lines-20"


# ── Edge cases ────────────────────────────────────────────────────────────────


def test_unknown_provider_returns_none() -> None:
    assert build_source_url("https://github.com/a/b", "unknown", "main", None, None) is None
    assert build_source_url("https://github.com/a/b", "unknown", "main", "f.py", 1) is None


def test_empty_repo_url_returns_none() -> None:
    assert build_source_url("", "github", "main", None, None) is None
    assert build_source_url("   ", "github", "main", "f.py", 1) is None


def test_file_path_with_backslash_normalized() -> None:
    url = build_source_url(
        "https://github.com/o/r",
        "github",
        "main",
        "src\\sub\\file.py",
        7,
    )
    assert "src/sub/file.py" in url or "src%2Fsub%2Ffile.py" in url
    assert url.endswith("#L7")


def test_file_path_leading_slash_stripped() -> None:
    url = build_source_url(
        "https://github.com/o/r",
        "github",
        "main",
        "/src/file.py",
        1,
    )
    assert "src/file.py" in url or "src%2Ffile.py" in url


def test_provider_case_insensitive() -> None:
    url1 = build_source_url("https://github.com/a/b", "GitHub", "main", "x.py", 1)
    url2 = build_source_url("https://github.com/a/b", "github", "main", "x.py", 1)
    assert url1 == url2


def test_line_zero_no_anchor() -> None:
    url = build_source_url(
        "https://github.com/o/r",
        "github",
        "main",
        "f.py",
        0,
    )
    assert url == "https://github.com/o/r/blob/main/f.py"
    assert "#L" not in url

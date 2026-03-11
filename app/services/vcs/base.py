from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path


@dataclass
class CloneResult:
    local_path: Path
    commit_sha: str
    branch: str


class BaseVCSProvider(ABC):
    """Abstract base for VCS providers. Clone/fetch logic is provider-specific;
    all subsequent analysis operates on plain git repos."""

    def __init__(self, username: str = "", token: str = "") -> None:
        self.username = username
        self.token = token

    @abstractmethod
    def build_clone_url(self, repo_url: str) -> str:
        """Return an authenticated clone URL."""

    def clone(self, repo_url: str, target_dir: Path, branch: str | None = None) -> CloneResult:
        import git
        clone_url = self.build_clone_url(repo_url)
        clone_kwargs = {} if branch is None else {"branch": branch}
        repo = git.Repo.clone_from(clone_url, str(target_dir), **clone_kwargs)
        commit_sha = repo.head.commit.hexsha
        actual_branch = repo.active_branch.name
        return CloneResult(local_path=target_dir, commit_sha=commit_sha, branch=actual_branch)

    def fetch(self, local_path: Path, branch: str | None = None) -> CloneResult:
        import git
        repo = git.Repo(str(local_path))
        if branch is None:
            branch = repo.active_branch.name
        origin = repo.remotes.origin
        # Re-set URL with fresh credentials (token may have changed)
        old_url = origin.url
        new_url = self.build_clone_url(old_url)
        with repo.config_writer() as cw:
            cw.set_value('remote "origin"', "url", new_url)
        origin.fetch()
        repo.git.checkout(branch)
        repo.git.pull("origin", branch)
        commit_sha = repo.head.commit.hexsha
        return CloneResult(local_path=local_path, commit_sha=commit_sha, branch=branch)

    @staticmethod
    def detect_provider(repo_url: str) -> str:
        """Guess provider type from URL. Returns 'bitbucket' or 'gitlab'."""
        url_lower = repo_url.lower()
        if "bitbucket" in url_lower:
            return "bitbucket"
        if "gitlab" in url_lower:
            return "gitlab"
        raise ValueError(f"Cannot detect VCS provider from URL: {repo_url}")

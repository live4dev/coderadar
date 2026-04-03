from __future__ import annotations
import shutil
import time
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

_CLONE_RETRIES = 3
_RETRY_BACKOFF = [2, 4]  # seconds between attempts


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

    def clone(self, repo_url: str, target_dir: Path, branch: str = "master") -> CloneResult:
        import git
        clone_url = self.build_clone_url(repo_url)
        clone_kwargs = {"branch": branch}
        last_exc: Exception | None = None
        for attempt in range(_CLONE_RETRIES):
            if attempt > 0:
                if target_dir.exists():
                    shutil.rmtree(target_dir)
                target_dir.mkdir(parents=True, exist_ok=True)
                time.sleep(_RETRY_BACKOFF[attempt - 1])
                logger.warning("retrying_clone", extra={"attempt": attempt + 1, "url": repo_url})
            try:
                repo = git.Repo.clone_from(clone_url, str(target_dir), **clone_kwargs)
                commit_sha = repo.head.commit.hexsha
                actual_branch = repo.active_branch.name
                return CloneResult(local_path=target_dir, commit_sha=commit_sha, branch=actual_branch)
            except git.GitCommandError as exc:
                last_exc = exc
        raise last_exc  # type: ignore[misc]

    def fetch(self, local_path: Path, branch: str = "master") -> CloneResult:
        import git
        repo = git.Repo(str(local_path))
        origin = repo.remotes.origin
        # Re-set URL with fresh credentials (token may have changed)
        old_url = origin.url
        new_url = self.build_clone_url(old_url)
        with repo.config_writer() as cw:
            cw.set_value('remote "origin"', "url", new_url)
        last_exc: Exception | None = None
        for attempt in range(_CLONE_RETRIES):
            if attempt > 0:
                time.sleep(_RETRY_BACKOFF[attempt - 1])
                logger.warning("retrying_fetch", extra={"attempt": attempt + 1})
            try:
                origin.fetch()
                repo.git.checkout(branch)
                repo.git.pull("origin", branch)
                commit_sha = repo.head.commit.hexsha
                return CloneResult(local_path=local_path, commit_sha=commit_sha, branch=branch)
            except git.GitCommandError as exc:
                last_exc = exc
        raise last_exc  # type: ignore[misc]

    @staticmethod
    def detect_provider(repo_url: str) -> str:
        """Guess provider type from URL. Returns 'bitbucket' or 'gitlab'."""
        url_lower = repo_url.lower()
        if "bitbucket" in url_lower:
            return "bitbucket"
        if "gitlab" in url_lower:
            return "gitlab"
        raise ValueError(f"Cannot detect VCS provider from URL: {repo_url}")

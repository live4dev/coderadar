from __future__ import annotations
import re
from pathlib import Path
from app.core.config import settings
from app.core.logging import get_logger
from app.services.vcs.base import BaseVCSProvider, CloneResult
from app.services.vcs.bitbucket import BitbucketProvider
from app.services.vcs.github import GitHubProvider
from app.services.vcs.gitlab import GitLabProvider

logger = get_logger(__name__)


def _slug(name: str, fallback: str) -> str:
    """Sanitize name for filesystem: keep letters, digits, _, -; collapse and strip; empty -> fallback."""
    if not name or not isinstance(name, str):
        return fallback
    s = re.sub(r"[^\w\-]", "_", name.strip())
    s = re.sub(r"[_\-\s]+", "_", s).strip("_-")
    return s if s else fallback


def get_provider(
    provider_type: str,
    username: str = "",
    token: str = "",
) -> BaseVCSProvider:
    if provider_type == "bitbucket":
        return BitbucketProvider(
            username=username or settings.bitbucket_username,
            token=token or settings.bitbucket_app_password,
        )
    if provider_type == "gitlab":
        return GitLabProvider(
            username=username or "oauth2",
            token=token or settings.gitlab_token,
        )
    if provider_type == "github":
        return GitHubProvider(
            username=username or "x-token-auth",
            token=token or settings.github_token,
        )
    raise ValueError(f"Unknown provider_type: {provider_type!r}")


class RepoWorkspaceManager:
    """Manages local clone/fetch lifecycle for repositories."""

    def __init__(self) -> None:
        self.cache_root = settings.repos_cache_path

    def _repo_dir(self, project_name: str, repo_name: str, repository_id: int) -> Path:
        project_slug = _slug(project_name, "project")
        repo_slug = f"{_slug(repo_name, 'repo')}_{repository_id}"
        return self.cache_root / project_slug / repo_slug

    def prepare(
        self,
        repository_id: int,
        repo_url: str,
        provider_type: str,
        project_name: str,
        repo_name: str,
        branch: str | None = None,
        credentials_username: str = "",
        credentials_token: str = "",
    ) -> CloneResult:
        """Clone or fetch the repository. Returns CloneResult with local path and HEAD SHA.
        If branch is None, clone uses remote default (HEAD); fetch uses current branch."""
        provider = get_provider(provider_type, credentials_username, credentials_token)
        target = self._repo_dir(project_name, repo_name, repository_id)

        if target.exists() and (target / ".git").exists():
            logger.info("fetching_repo", repository_id=repository_id, branch=branch or "(default)")
            return provider.fetch(target, branch)

        logger.info("cloning_repo", repository_id=repository_id, url=repo_url, branch=branch or "(default)")
        target.mkdir(parents=True, exist_ok=True)
        return provider.clone(repo_url, target, branch)

    def get_local_path(
        self, repository_id: int, project_name: str, repo_name: str
    ) -> Path | None:
        d = self._repo_dir(project_name, repo_name, repository_id)
        return d if d.exists() else None

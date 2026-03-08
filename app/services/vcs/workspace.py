from __future__ import annotations
from pathlib import Path
from app.core.config import settings
from app.core.logging import get_logger
from app.services.vcs.base import BaseVCSProvider, CloneResult
from app.services.vcs.bitbucket import BitbucketProvider
from app.services.vcs.gitlab import GitLabProvider

logger = get_logger(__name__)


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
    raise ValueError(f"Unknown provider_type: {provider_type!r}")


class RepoWorkspaceManager:
    """Manages local clone/fetch lifecycle for repositories."""

    def __init__(self) -> None:
        self.cache_root = settings.repos_cache_path

    def _repo_dir(self, repository_id: int) -> Path:
        d = self.cache_root / f"repo_{repository_id}"
        return d

    def prepare(
        self,
        repository_id: int,
        repo_url: str,
        provider_type: str,
        branch: str,
        credentials_username: str = "",
        credentials_token: str = "",
    ) -> CloneResult:
        """Clone or fetch the repository. Returns CloneResult with local path and HEAD SHA."""
        provider = get_provider(provider_type, credentials_username, credentials_token)
        target = self._repo_dir(repository_id)

        if target.exists() and (target / ".git").exists():
            logger.info("fetching_repo", repository_id=repository_id, branch=branch)
            return provider.fetch(target, branch)

        logger.info("cloning_repo", repository_id=repository_id, url=repo_url, branch=branch)
        target.mkdir(parents=True, exist_ok=True)
        return provider.clone(repo_url, target, branch)

    def get_local_path(self, repository_id: int) -> Path | None:
        d = self._repo_dir(repository_id)
        return d if d.exists() else None

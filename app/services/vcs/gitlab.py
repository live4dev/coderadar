from __future__ import annotations
import re
from app.services.vcs.base import BaseVCSProvider


class GitLabProvider(BaseVCSProvider):
    """GitLab provider using Personal Access Token or OAuth token.
    Uses oauth2 as username for token-based auth."""

    def build_clone_url(self, repo_url: str) -> str:
        if not self.token:
            return repo_url

        # GitLab token auth: https://oauth2:TOKEN@gitlab.com/group/repo.git
        return re.sub(
            r"https://",
            f"https://oauth2:{self.token}@",
            repo_url,
            count=1,
        )

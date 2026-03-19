from __future__ import annotations
import re
from app.services.vcs.base import BaseVCSProvider


class GitHubProvider(BaseVCSProvider):
    """GitHub provider using Personal Access Token."""

    def build_clone_url(self, repo_url: str) -> str:
        if not self.token:
            return repo_url
        return re.sub(
            r"https://",
            f"https://x-token-auth:{self.token}@",
            repo_url,
            count=1,
        )

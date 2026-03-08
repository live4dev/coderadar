from __future__ import annotations
import re
from app.services.vcs.base import BaseVCSProvider


class BitbucketProvider(BaseVCSProvider):
    """Bitbucket Cloud / Server provider using App Password or OAuth token."""

    def build_clone_url(self, repo_url: str) -> str:
        if not self.username or not self.token:
            return repo_url

        # Inject credentials into https URL
        # https://bitbucket.org/workspace/repo.git
        #  → https://user:token@bitbucket.org/workspace/repo.git
        return re.sub(
            r"https://",
            f"https://{self.username}:{self.token}@",
            repo_url,
            count=1,
        )

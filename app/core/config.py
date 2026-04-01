from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = "sqlite:///./coderadar.db"
    repos_cache_dir: str = "./repos_cache"
    log_level: str = "INFO"

    # Bitbucket defaults (can be overridden per-repository)
    bitbucket_username: str = ""
    bitbucket_app_password: str = ""

    # GitLab defaults (can be overridden per-repository)
    gitlab_token: str = ""
    gitlab_base_url: str = "https://gitlab.com"

    # GitHub defaults (can be overridden per-repository)
    github_token: str = ""

    # PDn (personal data) types config path (relative to project root)
    pdn_types_config: str = "config/pdn_types.yaml"

    # Git history: max commits to scan (0 = unlimited)
    git_history_scan_limit: int = 0

    # License scanning: call public registries (PyPI, crates.io, RubyGems, Maven Central)
    # for packages whose licence was not found in local files.
    enable_license_api_enrichment: bool = True

    # Yandex Metrika counter ID (optional; leave empty to disable tracking)
    yandex_metrika_id: str = ""

    @property
    def repos_cache_path(self) -> Path:
        p = Path(self.repos_cache_dir)
        p.mkdir(parents=True, exist_ok=True)
        return p


settings = Settings()

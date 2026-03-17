"""Build web UI URLs for repository sources (GitHub, GitLab, Bitbucket)."""
from __future__ import annotations

import re
from urllib.parse import quote

# Clone URL patterns: https://host/path or git@host:path
_HTTPS_PATTERN = re.compile(
    r"^https?://(?:[^@]+@)?([^/]+)/(.+?)(?:\.git)?/?$",
    re.IGNORECASE,
)
_SSH_PATTERN = re.compile(
    r"^git@([^:]+):(.+?)(?:\.git)?/?$",
)


def _clone_url_to_web_base(repo_url: str, provider: str) -> str | None:
    """Parse clone URL into web base URL (e.g. https://github.com/owner/repo)."""
    if not repo_url or not isinstance(repo_url, str):
        return None
    url = repo_url.strip()
    if not url:
        return None

    # Try HTTPS first
    m = _HTTPS_PATTERN.match(url)
    if m:
        host, path = m.group(1), m.group(2).rstrip("/")
        path = path.rstrip("/")
        return f"https://{host}/{path}"

    # SSH
    m = _SSH_PATTERN.match(url)
    if m:
        host, path = m.group(1), m.group(2).rstrip("/")
        # Normalize host: gitlab.com stays; github.com stays; bitbucket.org stays
        if "github.com" in host.lower():
            return f"https://github.com/{path}"
        if "gitlab.com" in host.lower():
            return f"https://gitlab.com/{path}"
        if "bitbucket.org" in host.lower():
            return f"https://bitbucket.org/{path}"
        # Self-hosted: assume https
        return f"https://{host}/{path}"

    return None


def build_source_url(
    repo_url: str,
    provider: str,
    ref: str,
    file_path: str | None = None,
    line_number: int | None = None,
) -> str | None:
    """
    Build URL to view repository (or file at line) in provider's web UI.

    - repo_url: clone URL (https or git@)
    - provider: "github", "gitlab", or "bitbucket"
    - ref: branch name or commit SHA
    - file_path: optional path relative to repo root
    - line_number: optional line number for anchor

    Returns None if provider unknown or URL unparseable.
    """
    base = _clone_url_to_web_base(repo_url, provider)
    if not base:
        return None
    provider_lower = (provider or "").strip().lower()
    if not ref:
        ref = "HEAD"

    # Repository-only URL (no file)
    if not file_path or not file_path.strip():
        if provider_lower == "github":
            return f"{base}/tree/{quote(ref, safe='')}"
        if provider_lower == "gitlab":
            return f"{base}/-/tree/{quote(ref, safe='')}"
        if provider_lower == "bitbucket":
            return f"{base}/src/{quote(ref, safe='')}"
        return None

    # Normalize path: no leading slash, use forward slashes
    path = file_path.strip().lstrip("/").replace("\\", "/")
    path_encoded = "/".join(quote(seg, safe="") for seg in path.split("/"))

    if provider_lower == "github":
        url = f"{base}/blob/{quote(ref, safe='')}/{path_encoded}"
        if line_number is not None and line_number > 0:
            url += f"#L{line_number}"
        return url
    if provider_lower == "gitlab":
        url = f"{base}/-/blob/{quote(ref, safe='')}/{path_encoded}"
        if line_number is not None and line_number > 0:
            url += f"#L{line_number}"
        return url
    if provider_lower == "bitbucket":
        url = f"{base}/src/{quote(ref, safe='')}/{path_encoded}"
        if line_number is not None and line_number > 0:
            url += f"#lines-{line_number}"
        return url

    return None

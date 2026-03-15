"""Load and cache PDn (personal data) types configuration from YAML."""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.core.config import settings

_cached_config: list[PDnTypeConfig] | None = None


@dataclass
class PDnTypeConfig:
    """One PDn type with canonical name and identifier variants for search."""
    name: str
    identifiers: list[str]


def _project_root() -> Path:
    """Project root (coderadar)."""
    return Path(__file__).resolve().parent.parent.parent.parent


def load_pdn_config() -> list[PDnTypeConfig]:
    """Load PDn types from YAML. Cached after first load."""
    global _cached_config
    if _cached_config is not None:
        return _cached_config

    config_path = Path(settings.pdn_types_config)
    if not config_path.is_absolute():
        config_path = _project_root() / config_path

    if not config_path.exists():
        _cached_config = []
        return _cached_config

    try:
        import yaml
        with open(config_path, encoding="utf-8") as f:
            data: dict[str, Any] = yaml.safe_load(f) or {}
    except Exception:
        _cached_config = []
        return _cached_config

    types_raw = data.get("pdn_types") or []
    result: list[PDnTypeConfig] = []
    for item in types_raw:
        if not isinstance(item, dict):
            continue
        name = item.get("name")
        identifiers = item.get("identifiers")
        if not name or not isinstance(identifiers, list):
            continue
        result.append(
            PDnTypeConfig(
                name=str(name).strip(),
                identifiers=[str(x).strip() for x in identifiers if x],
            )
        )
    _cached_config = result
    return _cached_config

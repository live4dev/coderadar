from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import json
import re


# ── Data types ────────────────────────────────────────────────────────────────

@dataclass
class LicenseInfo:
    spdx: str | None       # normalised SPDX id, or None
    raw: str | None        # verbatim string from manifest
    risk: str              # "safe" | "risky" | "unknown"
    is_direct: bool = True


# ── SPDX normalisation ────────────────────────────────────────────────────────

_SPDX_MAP: dict[str, str] = {
    "mit": "MIT",
    "mit license": "MIT",
    "apache 2.0": "Apache-2.0",
    "apache-2.0": "Apache-2.0",
    "apache 2": "Apache-2.0",
    "apache license 2.0": "Apache-2.0",
    "apache license, version 2.0": "Apache-2.0",
    "apache software license": "Apache-2.0",
    "bsd": "BSD-2-Clause",
    "bsd-2-clause": "BSD-2-Clause",
    "bsd 2-clause": "BSD-2-Clause",
    "simplified bsd": "BSD-2-Clause",
    "bsd-3-clause": "BSD-3-Clause",
    "bsd 3-clause": "BSD-3-Clause",
    "new bsd": "BSD-3-Clause",
    "isc": "ISC",
    "isc license (iscl)": "ISC",
    "mpl-2.0": "MPL-2.0",
    "mpl 2.0": "MPL-2.0",
    "mozilla public license 2.0": "MPL-2.0",
    "cc0-1.0": "CC0-1.0",
    "cc0": "CC0-1.0",
    "unlicense": "Unlicense",
    "the unlicense (unlicense)": "Unlicense",
    "wtfpl": "WTFPL",
    "0bsd": "0BSD",
    "python software foundation license": "PSF-2.0",
    "psf-2.0": "PSF-2.0",
    "zlib": "Zlib",
    "zlib/libpng": "Zlib",
    "gpl-2.0": "GPL-2.0-only",
    "gpl-2.0-only": "GPL-2.0-only",
    "gpl-2.0-or-later": "GPL-2.0-or-later",
    "gpl 2.0": "GPL-2.0-only",
    "gnu general public license v2 (gplv2)": "GPL-2.0-only",
    "gnu general public license v2 or later (gplv2+)": "GPL-2.0-or-later",
    "gpl-3.0": "GPL-3.0-only",
    "gpl-3.0-only": "GPL-3.0-only",
    "gpl-3.0-or-later": "GPL-3.0-or-later",
    "gpl 3.0": "GPL-3.0-only",
    "gnu general public license v3 (gplv3)": "GPL-3.0-only",
    "gnu general public license v3 or later (gplv3+)": "GPL-3.0-or-later",
    "agpl-3.0": "AGPL-3.0-only",
    "agpl-3.0-only": "AGPL-3.0-only",
    "agpl-3.0-or-later": "AGPL-3.0-or-later",
    "agpl 3.0": "AGPL-3.0-only",
    "lgpl-2.0": "LGPL-2.0-only",
    "lgpl-2.1": "LGPL-2.1-only",
    "lgpl-2.1-only": "LGPL-2.1-only",
    "lgpl-2.1-or-later": "LGPL-2.1-or-later",
    "gnu lesser general public license v2 (lgplv2)": "LGPL-2.0-only",
    "gnu lesser general public license v2 or later (lgplv2+)": "LGPL-2.1-or-later",
    "lgpl-3.0": "LGPL-3.0-only",
    "lgpl-3.0-only": "LGPL-3.0-only",
    "lgpl-3.0-or-later": "LGPL-3.0-or-later",
    "gnu lesser general public license v3 (lgplv3)": "LGPL-3.0-only",
    "eupl-1.1": "EUPL-1.1",
    "eupl-1.2": "EUPL-1.2",
}

_RISKY_PREFIXES = (
    "GPL-", "AGPL-", "LGPL-", "EUPL-", "OSL-", "CPAL-", "RPSL-",
)

_SAFE_IDS: frozenset[str] = frozenset({
    "MIT", "Apache-2.0", "BSD-2-Clause", "BSD-3-Clause", "ISC",
    "CC0-1.0", "Unlicense", "WTFPL", "MPL-2.0", "PSF-2.0",
    "0BSD", "Zlib", "Python-2.0",
})


def _normalise_spdx(raw: str | None) -> str | None:
    if not raw:
        return None
    cleaned = raw.strip().strip("()")
    looked_up = _SPDX_MAP.get(cleaned.lower())
    if looked_up:
        return looked_up
    # Accept it if it looks like an SPDX token (letters, digits, dots, dashes, plus)
    if re.match(r'^[A-Za-z0-9\.\-\+]+$', cleaned):
        return cleaned
    return None


def _classify_risk(spdx: str | None) -> str:
    if spdx is None:
        return "unknown"
    if any(spdx.startswith(p) for p in _RISKY_PREFIXES):
        return "risky"
    if spdx in _SAFE_IDS:
        return "safe"
    return "unknown"


# ── npm via package-lock.json ─────────────────────────────────────────────────

def _scan_npm(root: Path) -> dict[tuple[str, str], LicenseInfo]:
    lock_path = root / "package-lock.json"
    pkg_path = root / "package.json"
    if not lock_path.exists():
        return {}

    try:
        lock = json.loads(lock_path.read_text(encoding="utf-8"))
    except Exception:
        return {}

    direct_names: set[str] = set()
    if pkg_path.exists():
        try:
            pkg = json.loads(pkg_path.read_text(encoding="utf-8"))
            for section in ("dependencies", "devDependencies", "peerDependencies"):
                direct_names.update(pkg.get(section, {}).keys())
        except Exception:
            pass

    result: dict[tuple[str, str], LicenseInfo] = {}
    lock_version = lock.get("lockfileVersion", 1)

    if lock_version >= 2 and "packages" in lock:
        # v2/v3: flat packages dict keyed by "node_modules/foo"
        for pkg_key, pkg_info in lock["packages"].items():
            if not pkg_key:
                continue  # root entry
            if not isinstance(pkg_info, dict):
                continue
            # Extract name: strip leading node_modules/ and handle nested paths
            name = pkg_key.removeprefix("node_modules/")
            if "node_modules/" in name:
                name = name.rsplit("node_modules/", 1)[-1]
            raw = pkg_info.get("license") or pkg_info.get("licence")
            if isinstance(raw, dict):
                raw = raw.get("type") or raw.get("name")
            raw = str(raw) if raw is not None else None
            spdx = _normalise_spdx(raw)
            risk = _classify_risk(spdx)
            is_direct = name in direct_names
            result[(name, "npm")] = LicenseInfo(spdx=spdx, raw=raw, risk=risk, is_direct=is_direct)
    else:
        # v1: nested dependencies dict
        def _walk_v1(deps_dict: dict, is_top: bool = True) -> None:
            for name, info in deps_dict.items():
                if not isinstance(info, dict):
                    continue
                raw = info.get("license") or info.get("licence")
                if isinstance(raw, dict):
                    raw = raw.get("type") or raw.get("name")
                raw = str(raw) if raw is not None else None
                spdx = _normalise_spdx(raw)
                risk = _classify_risk(spdx)
                is_direct = name in direct_names if is_top else False
                if (name, "npm") not in result:
                    result[(name, "npm")] = LicenseInfo(
                        spdx=spdx, raw=raw, risk=risk, is_direct=is_direct
                    )
                nested = info.get("dependencies", {})
                if nested:
                    _walk_v1(nested, is_top=False)

        _walk_v1(lock.get("dependencies", {}), is_top=True)

    return result


# ── pip project self-description via pyproject.toml ──────────────────────────

_TROVE_TO_SPDX: dict[str, str] = {
    "license :: osi approved :: mit license": "MIT",
    "license :: osi approved :: apache software license": "Apache-2.0",
    "license :: osi approved :: bsd license": "BSD-3-Clause",
    "license :: osi approved :: isc license (iscl)": "ISC",
    "license :: osi approved :: mozilla public license 2.0 (mpl 2.0)": "MPL-2.0",
    "license :: osi approved :: python software foundation license": "PSF-2.0",
    "license :: osi approved :: the unlicense (unlicense)": "Unlicense",
    "license :: osi approved :: gnu general public license v2 (gplv2)": "GPL-2.0-only",
    "license :: osi approved :: gnu general public license v2 or later (gplv2+)": "GPL-2.0-or-later",
    "license :: osi approved :: gnu general public license v3 (gplv3)": "GPL-3.0-only",
    "license :: osi approved :: gnu general public license v3 or later (gplv3+)": "GPL-3.0-or-later",
    "license :: osi approved :: gnu lesser general public license v2 (lgplv2)": "LGPL-2.0-only",
    "license :: osi approved :: gnu lesser general public license v2 or later (lgplv2+)": "LGPL-2.1-or-later",
    "license :: osi approved :: gnu lesser general public license v3 (lgplv3)": "LGPL-3.0-only",
}


def _scan_pyproject(root: Path) -> dict[tuple[str, str], LicenseInfo]:
    path = root / "pyproject.toml"
    if not path.exists():
        return {}
    try:
        try:
            import tomllib
        except ImportError:
            import tomli as tomllib  # type: ignore[no-redef]
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}

    project = data.get("project", {})
    name = project.get("name")
    if not name:
        return {}

    # PEP 639: license is a string SPDX expression
    license_field = project.get("license")
    raw: str | None = None
    if isinstance(license_field, str):
        raw = license_field
    elif isinstance(license_field, dict):
        raw = license_field.get("text") or license_field.get("file")

    if not raw:
        for classifier in project.get("classifiers", []):
            spdx_val = _TROVE_TO_SPDX.get(classifier.strip().lower())
            if spdx_val:
                spdx = spdx_val
                risk = _classify_risk(spdx)
                return {(name, "pip"): LicenseInfo(spdx=spdx, raw=classifier, risk=risk, is_direct=True)}

    spdx = _normalise_spdx(raw)
    risk = _classify_risk(spdx)
    return {(name, "pip"): LicenseInfo(spdx=spdx, raw=raw, risk=risk, is_direct=True)}


# ── Public API ────────────────────────────────────────────────────────────────

def scan_licenses(
    repo_root: Path,
    deps: list,  # list[ParsedDependency] — avoids circular import
) -> dict[tuple[str, str], LicenseInfo]:
    """
    Scan repo_root for licence metadata, returning a dict keyed by
    (package_name, ecosystem). Merges all available sources.
    deps is the list produced by dependency_parser.parse_all().
    """
    result: dict[tuple[str, str], LicenseInfo] = {}
    result.update(_scan_npm(repo_root))
    result.update(_scan_pyproject(repo_root))

    # Ensure every parsed dep has an entry (unknown by default)
    for dep in deps:
        key = (dep.name, dep.ecosystem)
        if key not in result:
            result[key] = LicenseInfo(spdx=None, raw=None, risk="unknown", is_direct=True)

    return result

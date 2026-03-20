from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import re
import urllib.request
import urllib.parse


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

# Trove classifier → SPDX (used by pip and PyPI API)
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

# LICENSE file content patterns for Go vendor detection
_LICENSE_PATTERNS = [
    (re.compile(r"permission is hereby granted.*?without restriction", re.I | re.S), "MIT"),
    (re.compile(r"apache license.*?version 2\.0", re.I | re.S), "Apache-2.0"),
    (re.compile(r"gnu general public license.*?version 3", re.I | re.S), "GPL-3.0-only"),
    (re.compile(r"gnu general public license.*?version 2", re.I | re.S), "GPL-2.0-only"),
    (re.compile(r"gnu lesser general public license.*?version 3", re.I | re.S), "LGPL-3.0-only"),
    (re.compile(r"gnu lesser general public license.*?version 2\.1", re.I | re.S), "LGPL-2.1-only"),
    (re.compile(r"bsd 3-clause|redistribution and use.*?three", re.I | re.S), "BSD-3-Clause"),
    (re.compile(r"bsd 2-clause|redistribution and use.*?two", re.I | re.S), "BSD-2-Clause"),
    (re.compile(r"isc license|permission to use.*?isc", re.I | re.S), "ISC"),
    (re.compile(r"mozilla public license.*?2\.0", re.I | re.S), "MPL-2.0"),
]


def _normalise_spdx(raw: str | None) -> str | None:
    if not raw:
        return None
    cleaned = raw.strip().strip("()")
    looked_up = _SPDX_MAP.get(cleaned.lower())
    if looked_up:
        return looked_up
    # Accept tokens that look like a valid SPDX id (no spaces)
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


def _classify_license_file(text: str) -> str | None:
    sample = text[:3000]
    for pattern, spdx in _LICENSE_PATTERNS:
        if pattern.search(sample):
            return spdx
    return None


# ── Offline: npm via package-lock.json ───────────────────────────────────────

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
        for pkg_key, pkg_info in lock["packages"].items():
            if not pkg_key:
                continue
            if not isinstance(pkg_info, dict):
                continue
            name = pkg_key.removeprefix("node_modules/")
            if "node_modules/" in name:
                name = name.rsplit("node_modules/", 1)[-1]
            raw = pkg_info.get("license") or pkg_info.get("licence")
            if isinstance(raw, dict):
                raw = raw.get("type") or raw.get("name")
            raw = str(raw) if raw is not None else None
            spdx = _normalise_spdx(raw)
            risk = _classify_risk(spdx)
            result[(name, "npm")] = LicenseInfo(spdx=spdx, raw=raw, risk=risk, is_direct=name in direct_names)
    else:
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
                    result[(name, "npm")] = LicenseInfo(spdx=spdx, raw=raw, risk=risk, is_direct=is_direct)
                nested = info.get("dependencies", {})
                if nested:
                    _walk_v1(nested, is_top=False)

        _walk_v1(lock.get("dependencies", {}), is_top=True)

    return result


# ── Offline: pip via pyproject.toml (project self-description) ───────────────

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
                risk = _classify_risk(spdx_val)
                return {(name, "pip"): LicenseInfo(spdx=spdx_val, raw=classifier, risk=risk, is_direct=True)}

    spdx = _normalise_spdx(raw)
    risk = _classify_risk(spdx)
    return {(name, "pip"): LicenseInfo(spdx=spdx, raw=raw, risk=risk, is_direct=True)}


# ── Offline: pip via .venv dist-info METADATA ─────────────────────────────────

def _scan_pip_dist_info(root: Path) -> dict[tuple[str, str], LicenseInfo]:
    result: dict[tuple[str, str], LicenseInfo] = {}
    for venv_name in ("venv", ".venv", "env", ".env"):
        venv = root / venv_name
        if not venv.is_dir():
            continue
        for metadata_path in venv.glob("lib/python*/site-packages/*.dist-info/METADATA"):
            name: str | None = None
            raw_license: str | None = None
            classifiers: list[str] = []
            try:
                for line in metadata_path.read_text(encoding="utf-8", errors="replace").splitlines():
                    if line.startswith("Name:"):
                        name = line.split(":", 1)[1].strip().lower().replace("_", "-").replace(".", "-")
                    elif line.startswith("License:") and not line.startswith("License-Expression:"):
                        raw_license = line.split(":", 1)[1].strip()
                    elif line.startswith("Classifier: License"):
                        classifiers.append(line.split("Classifier:", 1)[1].strip())
                    elif line == "" and name:
                        break
            except Exception:
                continue
            if not name:
                continue
            spdx = None
            for c in classifiers:
                spdx = _TROVE_TO_SPDX.get(c.lower())
                if spdx:
                    break
            if not spdx:
                spdx = _normalise_spdx(raw_license)
            risk = _classify_risk(spdx)
            result[(name, "pip")] = LicenseInfo(spdx=spdx, raw=raw_license, risk=risk, is_direct=True)
    return result


# ── Offline: Rust via vendor/*/Cargo.toml ────────────────────────────────────

def _scan_cargo_vendor(root: Path) -> dict[tuple[str, str], LicenseInfo]:
    vendor = root / "vendor"
    if not vendor.is_dir():
        return {}
    result: dict[tuple[str, str], LicenseInfo] = {}
    for cargo_toml in vendor.glob("*/Cargo.toml"):
        try:
            try:
                import tomllib
            except ImportError:
                import tomli as tomllib  # type: ignore[no-redef]
            data = tomllib.loads(cargo_toml.read_text(encoding="utf-8"))
        except Exception:
            continue
        pkg = data.get("package", {})
        name = pkg.get("name")
        raw = pkg.get("license")
        if not name:
            continue
        spdx = _normalise_spdx(raw)
        risk = _classify_risk(spdx)
        result[(name, "cargo")] = LicenseInfo(spdx=spdx, raw=raw, risk=risk, is_direct=True)
    return result


# ── Offline: Go via vendor/ LICENSE files ────────────────────────────────────

def _scan_go_vendor(root: Path) -> dict[tuple[str, str], LicenseInfo]:
    modules_txt = root / "vendor" / "modules.txt"
    if not modules_txt.exists():
        return {}
    result: dict[tuple[str, str], LicenseInfo] = {}
    try:
        for line in modules_txt.read_text(encoding="utf-8").splitlines():
            if not line.startswith("# "):
                continue
            parts = line[2:].split()
            if not parts:
                continue
            module_path = parts[0]
            vendor_dir = root / "vendor" / module_path
            if not vendor_dir.is_dir():
                continue
            for lic_name in ("LICENSE", "LICENSE.txt", "LICENSE.md", "LICENCE", "COPYING"):
                lic_file = vendor_dir / lic_name
                if lic_file.exists():
                    try:
                        text = lic_file.read_text(encoding="utf-8", errors="replace")
                        spdx = _classify_license_file(text)
                        risk = _classify_risk(spdx)
                        result[(module_path, "go")] = LicenseInfo(spdx=spdx, raw=None, risk=risk, is_direct=True)
                    except Exception:
                        pass
                    break
    except Exception:
        pass
    return result


# ── Offline: Maven via pom.xml files in repo tree ────────────────────────────

def _scan_maven_poms(root: Path) -> dict[tuple[str, str], LicenseInfo]:
    import xml.etree.ElementTree as ET
    result: dict[tuple[str, str], LicenseInfo] = {}
    for pom in root.glob("**/pom.xml"):
        try:
            tree = ET.parse(str(pom))
            ns = {"m": "http://maven.apache.org/POM/4.0.0"}
            group = (
                tree.findtext("m:groupId", namespaces=ns)
                or tree.findtext("m:parent/m:groupId", namespaces=ns)
                or ""
            )
            artifact = tree.findtext("m:artifactId", namespaces=ns) or ""
            if not artifact:
                continue
            name = f"{group}:{artifact}"
            raw = tree.findtext(".//m:licenses/m:license/m:name", namespaces=ns)
            spdx = _normalise_spdx(raw)
            risk = _classify_risk(spdx)
            result[(name, "maven")] = LicenseInfo(spdx=spdx, raw=raw, risk=risk, is_direct=True)
        except Exception:
            continue
    return result


# ── Offline: Ruby via vendor/gems/**/*.gemspec ───────────────────────────────

def _scan_ruby_vendor(root: Path) -> dict[tuple[str, str], LicenseInfo]:
    result: dict[tuple[str, str], LicenseInfo] = {}
    for gemspec in root.glob("vendor/gems/**/*.gemspec"):
        try:
            text = gemspec.read_text(encoding="utf-8", errors="replace")
            name_match = re.search(r'\.name\s*=\s*["\']([^"\']+)["\']', text)
            lic_match = re.search(r'\.license\s*=\s*["\']([^"\']+)["\']', text)
            if not name_match:
                continue
            name = name_match.group(1)
            raw = lic_match.group(1) if lic_match else None
            spdx = _normalise_spdx(raw)
            risk = _classify_risk(spdx)
            result[(name, "bundler")] = LicenseInfo(spdx=spdx, raw=raw, risk=risk, is_direct=True)
        except Exception:
            continue
    return result


# ── Registry API fetchers ─────────────────────────────────────────────────────

_API_TIMEOUT = 5
_USER_AGENT = "CodeRadar-LicenseScanner/1.0 (contact: admin)"


def _http_get_json(url: str) -> dict | None:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": _USER_AGENT, "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=_API_TIMEOUT) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception:
        return None


def _fetch_pypi_license(name: str, version: str | None) -> LicenseInfo | None:
    data = _http_get_json(f"https://pypi.org/pypi/{urllib.parse.quote(name)}/json")
    if not data:
        return None
    info = data.get("info", {})
    raw = info.get("license") or ""
    classifiers = info.get("classifiers", [])
    spdx = None
    for c in classifiers:
        spdx = _TROVE_TO_SPDX.get(c.strip().lower())
        if spdx:
            break
    if not spdx and raw:
        spdx = _normalise_spdx(raw)
    risk = _classify_risk(spdx)
    return LicenseInfo(spdx=spdx, raw=raw or None, risk=risk)


def _fetch_crates_license(name: str, version: str | None) -> LicenseInfo | None:
    data = _http_get_json(f"https://crates.io/api/v1/crates/{urllib.parse.quote(name)}")
    if not data:
        return None
    raw = (data.get("crate") or {}).get("license")
    spdx = _normalise_spdx(raw)
    risk = _classify_risk(spdx)
    return LicenseInfo(spdx=spdx, raw=raw, risk=risk)


def _fetch_rubygems_license(name: str, version: str | None) -> LicenseInfo | None:
    data = _http_get_json(f"https://rubygems.org/api/v1/gems/{urllib.parse.quote(name)}.json")
    if not data:
        return None
    licenses = data.get("licenses") or []
    raw = licenses[0] if licenses else None
    spdx = _normalise_spdx(raw)
    risk = _classify_risk(spdx)
    return LicenseInfo(spdx=spdx, raw=raw, risk=risk)


def _fetch_maven_license(name: str, version: str | None) -> LicenseInfo | None:
    if ":" not in name or not version:
        return None
    group, artifact = name.split(":", 1)
    pom_url = (
        f"https://repo1.maven.org/maven2/"
        f"{group.replace('.', '/')}/{artifact}/{version}/{artifact}-{version}.pom"
    )
    req = urllib.request.Request(pom_url, headers={"User-Agent": _USER_AGENT})
    try:
        import xml.etree.ElementTree as ET
        with urllib.request.urlopen(req, timeout=_API_TIMEOUT) as resp:
            tree = ET.fromstring(resp.read())
            ns = {"m": "http://maven.apache.org/POM/4.0.0"}
            raw = tree.findtext(".//m:licenses/m:license/m:name", namespaces=ns)
            spdx = _normalise_spdx(raw)
            risk = _classify_risk(spdx)
            return LicenseInfo(spdx=spdx, raw=raw, risk=risk)
    except Exception:
        return None


_ECOSYSTEM_FETCHERS: dict[str, object] = {
    "pip":     _fetch_pypi_license,
    "cargo":   _fetch_crates_license,
    "bundler": _fetch_rubygems_license,
    "maven":   _fetch_maven_license,
}


# ── Public API ────────────────────────────────────────────────────────────────

def scan_licenses(
    repo_root: Path,
    deps: list,  # list[ParsedDependency] — avoids circular import
) -> dict[tuple[str, str], LicenseInfo]:
    """
    Hybrid licence scanner. Tries offline sources first, then falls back to
    registry APIs for any dependency whose licence is still unknown.
    deps is the list produced by dependency_parser.parse_all().
    """
    from app.core.config import settings

    result: dict[tuple[str, str], LicenseInfo] = {}

    # ── Offline sources ──────────────────────────────────────────────────────
    result.update(_scan_npm(repo_root))
    result.update(_scan_pip_dist_info(repo_root))
    result.update(_scan_pyproject(repo_root))
    result.update(_scan_cargo_vendor(repo_root))
    result.update(_scan_go_vendor(repo_root))
    result.update(_scan_maven_poms(repo_root))
    result.update(_scan_ruby_vendor(repo_root))

    # ── Fill placeholders for deps not yet found ─────────────────────────────
    for dep in deps:
        key = (dep.name, dep.ecosystem)
        if key not in result:
            result[key] = LicenseInfo(spdx=None, raw=None, risk="unknown", is_direct=True)

    # ── Registry API fallback ────────────────────────────────────────────────
    if settings.enable_license_api_enrichment:
        unknown_deps = [
            dep for dep in deps
            if result[(dep.name, dep.ecosystem)].risk == "unknown"
            and dep.ecosystem in _ECOSYSTEM_FETCHERS
        ]
        if unknown_deps:
            with ThreadPoolExecutor(max_workers=6) as pool:
                futures = {
                    pool.submit(_ECOSYSTEM_FETCHERS[dep.ecosystem], dep.name, dep.version): (dep.name, dep.ecosystem)
                    for dep in unknown_deps
                }
                for future in as_completed(futures):
                    key = futures[future]
                    try:
                        info = future.result()
                        if info:
                            info.is_direct = result[key].is_direct
                            result[key] = info
                    except Exception:
                        pass

    return result

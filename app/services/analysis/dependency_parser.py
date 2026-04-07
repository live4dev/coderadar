from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
import json
import re
import xml.etree.ElementTree as ET


@dataclass
class ParsedDependency:
    name: str
    version: str | None
    dep_type: str               # prod | dev | test | unknown
    manifest_file: str
    ecosystem: str
    is_direct: bool = True
    is_optional: bool = False
    is_private: bool = False
    discovery_mode: str = "declared_only"   # declared_only | locked | resolved | installed
    package_manager: str | None = None      # specific PM when ecosystem is ambiguous (yarn, pnpm, poetry…)


def parse_all(repo_root: Path) -> list[ParsedDependency]:
    """
    Parse all known manifest and lockfile formats in repo_root.
    For each (name, ecosystem) pair, a lockfile entry (discovery_mode="locked")
    supersedes a manifest-only entry (discovery_mode="declared_only").
    """
    deps: list[ParsedDependency] = []

    # ── Manifest parsers (declared_only) ──────────────────────────────────────
    deps.extend(_parse_package_json(repo_root))
    deps.extend(_parse_requirements_txt(repo_root))
    deps.extend(_parse_pyproject_toml(repo_root))
    deps.extend(_parse_go_mod(repo_root))
    deps.extend(_parse_cargo_toml(repo_root))
    deps.extend(_parse_pom_xml(repo_root))
    deps.extend(_parse_gemfile(repo_root))
    deps.extend(_parse_nuget(repo_root))
    deps.extend(_parse_composer_json(repo_root))

    # ── Lockfile parsers (locked) ─────────────────────────────────────────────
    deps.extend(_parse_package_lock_json(repo_root))
    deps.extend(_parse_yarn_lock(repo_root))
    deps.extend(_parse_pnpm_lock(repo_root))
    deps.extend(_parse_poetry_lock(repo_root))
    deps.extend(_parse_pipfile_lock(repo_root))
    deps.extend(_parse_cargo_lock(repo_root))
    deps.extend(_parse_gemfile_lock(repo_root))
    deps.extend(_parse_composer_lock(repo_root))
    deps.extend(_parse_go_sum(repo_root))

    return _deduplicate(deps)


# ── Deduplication ─────────────────────────────────────────────────────────────

def _deduplicate(deps: list[ParsedDependency]) -> list[ParsedDependency]:
    """
    For each (name, ecosystem) key, keep the highest-quality entry.
    Priority: locked > declared_only (higher discovery_mode wins).
    When same priority, keep first occurrence (manifests are parsed first so
    locked files override them correctly).
    """
    _priority = {"installed": 4, "resolved": 3, "locked": 2, "declared_only": 1, "unknown": 0}
    seen: dict[tuple[str, str], ParsedDependency] = {}
    for dep in deps:
        key = (dep.name, dep.ecosystem)
        existing = seen.get(key)
        if existing is None:
            seen[key] = dep
        elif _priority.get(dep.discovery_mode, 0) > _priority.get(existing.discovery_mode, 0):
            seen[key] = dep
    return list(seen.values())


# ── Manifest parsers ──────────────────────────────────────────────────────────

def _parse_package_json(root: Path) -> list[ParsedDependency]:
    path = root / "package.json"
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []

    result = []
    for name, ver in data.get("dependencies", {}).items():
        result.append(ParsedDependency(name, str(ver), "prod", "package.json", "npm"))
    for name, ver in data.get("devDependencies", {}).items():
        result.append(ParsedDependency(name, str(ver), "dev", "package.json", "npm"))
    for name, ver_spec in data.get("peerDependencies", {}).items():
        result.append(ParsedDependency(name, str(ver_spec), "prod", "package.json", "npm"))
    for name, ver in data.get("optionalDependencies", {}).items():
        result.append(ParsedDependency(name, str(ver), "prod", "package.json", "npm", is_optional=True))
    return result


def _parse_requirements_txt(root: Path) -> list[ParsedDependency]:
    results = []
    for filename in ["requirements.txt", "requirements-dev.txt", "requirements-test.txt",
                     "requirements-prod.txt", "requirements/base.txt",
                     "requirements/dev.txt", "requirements/prod.txt"]:
        path = root / filename
        if not path.exists():
            continue
        dep_type = "dev" if "dev" in filename else ("test" if "test" in filename else "prod")
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or line.startswith("-"):
                continue
            match = re.match(r"^([A-Za-z0-9_\-\.]+)\s*([>=<!~^].+)?", line)
            if match:
                results.append(ParsedDependency(
                    name=match.group(1),
                    version=match.group(2).strip() if match.group(2) else None,
                    dep_type=dep_type,
                    manifest_file=filename,
                    ecosystem="pip",
                ))
    return results


def _parse_pyproject_toml(root: Path) -> list[ParsedDependency]:
    path = root / "pyproject.toml"
    if not path.exists():
        return []
    try:
        import tomllib  # Python 3.11+
    except ImportError:
        try:
            import tomli as tomllib  # type: ignore[no-redef]
        except ImportError:
            return []
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []

    results = []
    # poetry style
    poetry = data.get("tool", {}).get("poetry", {})
    for name, ver in poetry.get("dependencies", {}).items():
        if name == "python":
            continue
        version = ver if isinstance(ver, str) else (ver.get("version") if isinstance(ver, dict) else None)
        optional = isinstance(ver, dict) and ver.get("optional", False)
        results.append(ParsedDependency(name, version, "prod", "pyproject.toml", "pip",
                                        is_optional=optional, package_manager="poetry"))
    for name, ver in poetry.get("dev-dependencies", {}).items():
        version = ver if isinstance(ver, str) else None
        results.append(ParsedDependency(name, version, "dev", "pyproject.toml", "pip",
                                        package_manager="poetry"))
    # poetry group deps (poetry >= 1.2)
    for group_name, group_data in poetry.get("group", {}).items():
        dep_type = "dev" if group_name in ("dev", "test", "lint") else "prod"
        for name, ver in group_data.get("dependencies", {}).items():
            version = ver if isinstance(ver, str) else (ver.get("version") if isinstance(ver, dict) else None)
            results.append(ParsedDependency(name, version, dep_type, "pyproject.toml", "pip",
                                            package_manager="poetry"))

    # PEP 621 style
    project = data.get("project", {})
    for dep in project.get("dependencies", []):
        match = re.match(r"^([A-Za-z0-9_\-\.]+)\s*([>=<!~^].+)?", dep)
        if match:
            results.append(ParsedDependency(
                match.group(1),
                match.group(2).strip() if match.group(2) else None,
                "prod", "pyproject.toml", "pip",
            ))
    for group_name, group_deps in project.get("optional-dependencies", {}).items():
        for dep in group_deps:
            match = re.match(r"^([A-Za-z0-9_\-\.]+)\s*([>=<!~^].+)?", dep)
            if match:
                results.append(ParsedDependency(
                    match.group(1),
                    match.group(2).strip() if match.group(2) else None,
                    "prod", "pyproject.toml", "pip", is_optional=True,
                ))
    return results


def _parse_go_mod(root: Path) -> list[ParsedDependency]:
    path = root / "go.mod"
    if not path.exists():
        return []
    results = []
    in_require = False
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("require ("):
            in_require = True
            continue
        if in_require and line == ")":
            in_require = False
            continue
        if in_require or line.startswith("require "):
            line = line.removeprefix("require ")
            # strip inline comments
            line = line.split("//")[0].strip()
            parts = line.split()
            if len(parts) >= 2:
                is_indirect = len(parts) >= 3 and parts[2] == "indirect"
                results.append(ParsedDependency(
                    parts[0], parts[1], "prod", "go.mod", "go",
                    is_direct=not is_indirect,
                ))
    return results


def _parse_cargo_toml(root: Path) -> list[ParsedDependency]:
    path = root / "Cargo.toml"
    if not path.exists():
        return []
    try:
        try:
            import tomllib
        except ImportError:
            import tomli as tomllib  # type: ignore[no-redef]
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []

    results = []
    for name, ver in data.get("dependencies", {}).items():
        version = ver if isinstance(ver, str) else (ver.get("version") if isinstance(ver, dict) else None)
        optional = isinstance(ver, dict) and ver.get("optional", False)
        results.append(ParsedDependency(name, version, "prod", "Cargo.toml", "cargo", is_optional=optional))
    for name, ver in data.get("dev-dependencies", {}).items():
        version = ver if isinstance(ver, str) else (ver.get("version") if isinstance(ver, dict) else None)
        results.append(ParsedDependency(name, version, "dev", "Cargo.toml", "cargo"))
    for name, ver in data.get("build-dependencies", {}).items():
        version = ver if isinstance(ver, str) else (ver.get("version") if isinstance(ver, dict) else None)
        results.append(ParsedDependency(name, version, "prod", "Cargo.toml", "cargo"))
    return results


def _parse_pom_xml(root: Path) -> list[ParsedDependency]:
    path = root / "pom.xml"
    if not path.exists():
        return []
    try:
        tree = ET.parse(str(path))
        ns = {"m": "http://maven.apache.org/POM/4.0.0"}
        results = []
        for dep in tree.findall(".//m:dependency", ns):
            group = dep.findtext("m:groupId", namespaces=ns) or ""
            artifact = dep.findtext("m:artifactId", namespaces=ns) or ""
            version = dep.findtext("m:version", namespaces=ns)
            scope = dep.findtext("m:scope", namespaces=ns) or "compile"
            optional_el = dep.findtext("m:optional", namespaces=ns) or "false"
            name = f"{group}:{artifact}"
            dep_type = "test" if scope == "test" else "dev" if scope in ("provided", "optional") else "prod"
            results.append(ParsedDependency(name, version, dep_type, "pom.xml", "maven",
                                            is_optional=optional_el.lower() == "true"))
        return results
    except Exception:
        return []


def _parse_gemfile(root: Path) -> list[ParsedDependency]:
    path = root / "Gemfile"
    if not path.exists():
        return []
    results = []
    current_groups: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        # detect group blocks
        g_match = re.match(r"group\s+(.+)\s+do", stripped)
        if g_match:
            current_groups = [g.strip().strip(":,") for g in g_match.group(1).split(",")]
            continue
        if stripped == "end":
            current_groups = []
            continue
        if stripped.startswith("gem "):
            parts = re.findall(r"'([^']+)'|\"([^\"]+)\"", stripped)
            if parts:
                name = parts[0][0] or parts[0][1]
                version = (parts[1][0] or parts[1][1]) if len(parts) > 1 else None
                dep_type = "dev" if any(g in ("development", "test") for g in current_groups) else "prod"
                results.append(ParsedDependency(name, version, dep_type, "Gemfile", "bundler"))
    return results


def _parse_nuget(root: Path) -> list[ParsedDependency]:
    """Parse .csproj, .fsproj, .vbproj, and Directory.Packages.props files."""
    results = []
    patterns = list(root.glob("**/*.csproj")) + list(root.glob("**/*.fsproj")) + \
               list(root.glob("**/*.vbproj")) + list(root.glob("**/Directory.Packages.props"))
    for proj_file in patterns:
        try:
            tree = ET.parse(str(proj_file))
            for ref in tree.findall(".//PackageReference"):
                name = ref.get("Include") or ref.get("Update") or ""
                if not name:
                    continue
                version = ref.get("Version") or (ref.findtext("Version") if ref else None)
                private_assets = ref.get("PrivateAssets") or ref.findtext("PrivateAssets") or ""
                dep_type = "dev" if "all" in private_assets.lower() else "prod"
                results.append(ParsedDependency(
                    name, version, dep_type,
                    str(proj_file.relative_to(root)), "nuget",
                ))
        except Exception:
            continue
    return results


def _parse_composer_json(root: Path) -> list[ParsedDependency]:
    path = root / "composer.json"
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    results = []
    for name, ver in data.get("require", {}).items():
        if name == "php" or name.startswith("ext-"):
            continue
        results.append(ParsedDependency(name, str(ver), "prod", "composer.json", "composer"))
    for name, ver in data.get("require-dev", {}).items():
        if name == "php" or name.startswith("ext-"):
            continue
        results.append(ParsedDependency(name, str(ver), "dev", "composer.json", "composer"))
    return results


# ── Lockfile parsers ──────────────────────────────────────────────────────────

def _parse_package_lock_json(root: Path) -> list[ParsedDependency]:
    """Parse package-lock.json (npm, lockfileVersion 1, 2, or 3)."""
    lock_path = root / "package-lock.json"
    pkg_path = root / "package.json"
    if not lock_path.exists():
        return []
    try:
        lock = json.loads(lock_path.read_text(encoding="utf-8"))
    except Exception:
        return []

    direct_names: set[str] = set()
    dev_names: set[str] = set()
    if pkg_path.exists():
        try:
            pkg = json.loads(pkg_path.read_text(encoding="utf-8"))
            direct_names.update(pkg.get("dependencies", {}).keys())
            direct_names.update(pkg.get("peerDependencies", {}).keys())
            dev_names.update(pkg.get("devDependencies", {}).keys())
            direct_names.update(dev_names)
        except Exception:
            pass

    results = []
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
            version = pkg_info.get("version")
            dep_type = "dev" if pkg_info.get("dev") else "prod"
            is_direct = name in direct_names
            results.append(ParsedDependency(
                name, version, dep_type, "package-lock.json", "npm",
                is_direct=is_direct,
                discovery_mode="locked",
                package_manager="npm",
            ))
    else:
        def _walk_v1(deps_dict: dict, is_top: bool = True) -> None:
            for name, info in deps_dict.items():
                if not isinstance(info, dict):
                    continue
                version = info.get("version")
                dep_type = "dev" if info.get("dev") else "prod"
                is_direct = name in direct_names if is_top else False
                results.append(ParsedDependency(
                    name, version, dep_type, "package-lock.json", "npm",
                    is_direct=is_top and name in direct_names,
                    discovery_mode="locked",
                    package_manager="npm",
                ))
                if info.get("dependencies"):
                    _walk_v1(info["dependencies"], is_top=False)
        _walk_v1(lock.get("dependencies", {}))
    return results


def _parse_yarn_lock(root: Path) -> list[ParsedDependency]:
    """Parse yarn.lock (classic yarn v1 format)."""
    lock_path = root / "yarn.lock"
    if not lock_path.exists():
        return []

    pkg_path = root / "package.json"
    direct_names: set[str] = set()
    dev_names: set[str] = set()
    if pkg_path.exists():
        try:
            pkg = json.loads(pkg_path.read_text(encoding="utf-8"))
            direct_names.update(pkg.get("dependencies", {}).keys())
            direct_names.update(pkg.get("peerDependencies", {}).keys())
            dev_names.update(pkg.get("devDependencies", {}).keys())
            direct_names.update(dev_names)
        except Exception:
            pass

    results = []
    try:
        content = lock_path.read_text(encoding="utf-8")
        # yarn.lock block: one or more "name@version:" headers followed by indented body
        current_names: list[str] = []
        current_version: str | None = None
        for line in content.splitlines():
            # Skip comments and blank lines at the block level
            if line.startswith("#") or not line.strip():
                if current_names and current_version:
                    for raw_name in current_names:
                        # raw_name may be "package@^1.0.0" — extract just the package name
                        pkg_name = re.match(r'^"?(@?[^@"]+)', raw_name)
                        if pkg_name:
                            name = pkg_name.group(1).strip()
                            dep_type = "dev" if name in dev_names else "prod"
                            results.append(ParsedDependency(
                                name, current_version, dep_type, "yarn.lock", "npm",
                                is_direct=name in direct_names,
                                discovery_mode="locked",
                                package_manager="yarn",
                            ))
                    current_names = []
                    current_version = None
                continue

            # Block header: "name@version, name@other-version:"
            if not line.startswith(" ") and line.rstrip().endswith(":"):
                if current_names and current_version:
                    for raw_name in current_names:
                        pkg_name = re.match(r'^"?(@?[^@"]+)', raw_name)
                        if pkg_name:
                            name = pkg_name.group(1).strip()
                            dep_type = "dev" if name in dev_names else "prod"
                            results.append(ParsedDependency(
                                name, current_version, dep_type, "yarn.lock", "npm",
                                is_direct=name in direct_names,
                                discovery_mode="locked",
                                package_manager="yarn",
                            ))
                header = line.rstrip().rstrip(":")
                current_names = [h.strip().strip('"') for h in header.split(",")]
                current_version = None
            elif line.startswith("  version "):
                m = re.match(r'\s+version\s+"?([^"]+)"?', line)
                if m:
                    current_version = m.group(1)

        # Flush last block
        if current_names and current_version:
            for raw_name in current_names:
                pkg_name = re.match(r'^"?(@?[^@"]+)', raw_name)
                if pkg_name:
                    name = pkg_name.group(1).strip()
                    dep_type = "dev" if name in dev_names else "prod"
                    results.append(ParsedDependency(
                        name, current_version, dep_type, "yarn.lock", "npm",
                        is_direct=name in direct_names,
                        discovery_mode="locked",
                        package_manager="yarn",
                    ))
    except Exception:
        pass
    return results


def _parse_pnpm_lock(root: Path) -> list[ParsedDependency]:
    """Parse pnpm-lock.yaml."""
    lock_path = root / "pnpm-lock.yaml"
    if not lock_path.exists():
        return []
    try:
        import yaml  # type: ignore[import]
    except ImportError:
        # If PyYAML not available, do basic regex parsing
        return _parse_pnpm_lock_regex(lock_path)
    try:
        data = yaml.safe_load(lock_path.read_text(encoding="utf-8"))
    except Exception:
        return []
    if not isinstance(data, dict):
        return []

    results = []
    # pnpm lockfile v5/v6: top-level "packages" section
    packages = data.get("packages", {})
    importers = data.get("importers", {})
    direct_names: set[str] = set()
    dev_names: set[str] = set()

    # Collect direct dep names from importers
    for imp_data in importers.values() if importers else []:
        for name in (imp_data.get("dependencies") or {}).keys():
            direct_names.add(name)
        for name in (imp_data.get("devDependencies") or {}).keys():
            dev_names.add(name)
            direct_names.add(name)

    for pkg_key, pkg_info in packages.items():
        if not isinstance(pkg_info, dict):
            continue
        # pkg_key looks like "/name/1.0.0" or "name@1.0.0"
        m = re.match(r"^/?(@?[^/@]+(?:/[^/@]+)?)/([^/]+)$", pkg_key)
        if not m:
            m = re.match(r"^(@?[^@]+)@(.+)$", pkg_key)
        if not m:
            continue
        name, version = m.group(1), m.group(2)
        dep_type = "dev" if pkg_info.get("dev") else "prod"
        results.append(ParsedDependency(
            name, version, dep_type, "pnpm-lock.yaml", "npm",
            is_direct=name in direct_names,
            discovery_mode="locked",
            package_manager="pnpm",
        ))
    return results


def _parse_pnpm_lock_regex(lock_path: Path) -> list[ParsedDependency]:
    """Fallback regex-based pnpm lock parser when PyYAML is unavailable."""
    results = []
    try:
        for line in lock_path.read_text(encoding="utf-8").splitlines():
            # Match package entries like "/name/1.0.0:" or "name@1.0.0:"
            m = re.match(r"^  /?(@?[^/@\s]+(?:/[^/@\s]+)?)/([^/:]+):", line)
            if m:
                results.append(ParsedDependency(
                    m.group(1), m.group(2), "prod", "pnpm-lock.yaml", "npm",
                    discovery_mode="locked", package_manager="pnpm",
                ))
    except Exception:
        pass
    return results


def _parse_poetry_lock(root: Path) -> list[ParsedDependency]:
    """Parse poetry.lock."""
    lock_path = root / "poetry.lock"
    if not lock_path.exists():
        return []
    try:
        try:
            import tomllib
        except ImportError:
            import tomli as tomllib  # type: ignore[no-redef]
        data = tomllib.loads(lock_path.read_text(encoding="utf-8"))
    except Exception:
        return []

    results = []
    for pkg in data.get("package", []):
        name = pkg.get("name")
        version = pkg.get("version")
        category = pkg.get("category", "main")  # poetry < 1.2
        optional = pkg.get("optional", False)
        dep_type = "dev" if category in ("dev",) else "prod"
        if not name:
            continue
        results.append(ParsedDependency(
            name, version, dep_type, "poetry.lock", "pip",
            is_optional=optional,
            discovery_mode="locked",
            package_manager="poetry",
        ))
    return results


def _parse_pipfile_lock(root: Path) -> list[ParsedDependency]:
    """Parse Pipfile.lock."""
    lock_path = root / "Pipfile.lock"
    if not lock_path.exists():
        return []
    try:
        data = json.loads(lock_path.read_text(encoding="utf-8"))
    except Exception:
        return []

    results = []
    for name, info in data.get("default", {}).items():
        version = (info.get("version") or "").lstrip("==")
        results.append(ParsedDependency(
            name, version or None, "prod", "Pipfile.lock", "pip",
            discovery_mode="locked",
            package_manager="pipenv",
        ))
    for name, info in data.get("develop", {}).items():
        version = (info.get("version") or "").lstrip("==")
        results.append(ParsedDependency(
            name, version or None, "dev", "Pipfile.lock", "pip",
            discovery_mode="locked",
            package_manager="pipenv",
        ))
    return results


def _parse_cargo_lock(root: Path) -> list[ParsedDependency]:
    """Parse Cargo.lock."""
    lock_path = root / "Cargo.lock"
    if not lock_path.exists():
        return []
    try:
        try:
            import tomllib
        except ImportError:
            import tomli as tomllib  # type: ignore[no-redef]
        data = tomllib.loads(lock_path.read_text(encoding="utf-8"))
    except Exception:
        return []

    results = []
    for pkg in data.get("package", []):
        name = pkg.get("name")
        version = pkg.get("version")
        if not name:
            continue
        # Cargo.lock doesn't distinguish dev deps directly; treat all as prod
        results.append(ParsedDependency(
            name, version, "prod", "Cargo.lock", "cargo",
            discovery_mode="locked",
        ))
    return results


def _parse_gemfile_lock(root: Path) -> list[ParsedDependency]:
    """Parse Gemfile.lock."""
    lock_path = root / "Gemfile.lock"
    if not lock_path.exists():
        return []

    results = []
    try:
        in_gem_section = False
        for line in lock_path.read_text(encoding="utf-8").splitlines():
            if line.strip() in ("GEM", "PATH", "GIT"):
                in_gem_section = False
            elif line.strip() == "specs:":
                in_gem_section = True
            elif in_gem_section and line.startswith("    ") and not line.startswith("      "):
                m = re.match(r"\s{4}(\S+)\s+\(([^)]+)\)", line)
                if m:
                    name, version = m.group(1), m.group(2)
                    results.append(ParsedDependency(
                        name, version, "prod", "Gemfile.lock", "bundler",
                        discovery_mode="locked",
                    ))
    except Exception:
        pass
    return results


def _parse_composer_lock(root: Path) -> list[ParsedDependency]:
    """Parse composer.lock."""
    lock_path = root / "composer.lock"
    if not lock_path.exists():
        return []
    try:
        data = json.loads(lock_path.read_text(encoding="utf-8"))
    except Exception:
        return []

    results = []
    for pkg in data.get("packages", []):
        name = pkg.get("name")
        version = pkg.get("version")
        if not name:
            continue
        results.append(ParsedDependency(
            name, version, "prod", "composer.lock", "composer",
            discovery_mode="locked",
        ))
    for pkg in data.get("packages-dev", []):
        name = pkg.get("name")
        version = pkg.get("version")
        if not name:
            continue
        results.append(ParsedDependency(
            name, version, "dev", "composer.lock", "composer",
            discovery_mode="locked",
        ))
    return results


def _parse_go_sum(root: Path) -> list[ParsedDependency]:
    """Parse go.sum for exact resolved versions."""
    sum_path = root / "go.sum"
    if not sum_path.exists():
        return []

    seen: set[tuple[str, str]] = set()
    results = []
    try:
        for line in sum_path.read_text(encoding="utf-8").splitlines():
            parts = line.split()
            if len(parts) < 2:
                continue
            module = parts[0]
            # versions look like "v1.2.3" or "v1.2.3/go.mod"
            version_raw = parts[1].split("/")[0]
            key = (module, version_raw)
            if key in seen:
                continue
            seen.add(key)
            results.append(ParsedDependency(
                module, version_raw, "prod", "go.sum", "go",
                discovery_mode="locked",
            ))
    except Exception:
        pass
    return results

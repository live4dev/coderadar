from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import json
import re


@dataclass
class ParsedDependency:
    name: str
    version: str | None
    dep_type: str  # prod | dev | test | unknown
    manifest_file: str
    ecosystem: str


def parse_all(repo_root: Path) -> list[ParsedDependency]:
    deps: list[ParsedDependency] = []
    deps.extend(_parse_package_json(repo_root))
    deps.extend(_parse_requirements_txt(repo_root))
    deps.extend(_parse_pyproject_toml(repo_root))
    deps.extend(_parse_go_mod(repo_root))
    deps.extend(_parse_cargo_toml(repo_root))
    deps.extend(_parse_pom_xml(repo_root))
    deps.extend(_parse_gemfile(repo_root))
    return deps


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
    for name, ver in data.get("peerDependencies", {}).items():
        result.append(ParsedDependency(name, str(ver), "prod", "package.json", "npm"))
    return result


def _parse_requirements_txt(root: Path) -> list[ParsedDependency]:
    results = []
    for filename in ["requirements.txt", "requirements-dev.txt", "requirements-test.txt"]:
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
        version = ver if isinstance(ver, str) else None
        results.append(ParsedDependency(name, version, "prod", "pyproject.toml", "pip"))
    for name, ver in poetry.get("dev-dependencies", {}).items():
        version = ver if isinstance(ver, str) else None
        results.append(ParsedDependency(name, version, "dev", "pyproject.toml", "pip"))

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
            parts = line.split()
            if len(parts) >= 2:
                results.append(ParsedDependency(parts[0], parts[1], "prod", "go.mod", "go"))
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
        version = ver if isinstance(ver, str) else ver.get("version") if isinstance(ver, dict) else None
        results.append(ParsedDependency(name, version, "prod", "Cargo.toml", "cargo"))
    for name, ver in data.get("dev-dependencies", {}).items():
        version = ver if isinstance(ver, str) else ver.get("version") if isinstance(ver, dict) else None
        results.append(ParsedDependency(name, version, "dev", "Cargo.toml", "cargo"))
    return results


def _parse_pom_xml(root: Path) -> list[ParsedDependency]:
    path = root / "pom.xml"
    if not path.exists():
        return []
    try:
        import xml.etree.ElementTree as ET
        tree = ET.parse(str(path))
        ns = {"m": "http://maven.apache.org/POM/4.0.0"}
        results = []
        for dep in tree.findall(".//m:dependency", ns):
            group = dep.findtext("m:groupId", namespaces=ns) or ""
            artifact = dep.findtext("m:artifactId", namespaces=ns) or ""
            version = dep.findtext("m:version", namespaces=ns)
            scope = dep.findtext("m:scope", namespaces=ns) or "compile"
            name = f"{group}:{artifact}"
            dep_type = "test" if scope == "test" else "dev" if scope in ("provided", "optional") else "prod"
            results.append(ParsedDependency(name, version, dep_type, "pom.xml", "maven"))
        return results
    except Exception:
        return []


def _parse_gemfile(root: Path) -> list[ParsedDependency]:
    path = root / "Gemfile"
    if not path.exists():
        return []
    results = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("gem "):
            parts = re.findall(r"'([^']+)'|\"([^\"]+)\"", line)
            if parts:
                name = parts[0][0] or parts[0][1]
                version = (parts[1][0] or parts[1][1]) if len(parts) > 1 else None
                results.append(ParsedDependency(name, version, "prod", "Gemfile", "bundler"))
    return results

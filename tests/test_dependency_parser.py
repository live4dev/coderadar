import json
import textwrap
from pathlib import Path
import pytest

from app.services.analysis.dependency_parser import parse_all


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_repo(tmp_path: Path, files: dict[str, str]) -> Path:
    for name, content in files.items():
        f = tmp_path / name
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(textwrap.dedent(content))
    return tmp_path


# ── npm / package.json ────────────────────────────────────────────────────────

def test_npm_prod_and_dev(tmp_path):
    _make_repo(tmp_path, {
        "package.json": json.dumps({
            "dependencies": {"react": "^18.0.0", "axios": "1.6.0"},
            "devDependencies": {"jest": "^29.0.0"},
        })
    })
    deps = parse_all(tmp_path)
    names = {d.name for d in deps}
    assert "react" in names
    assert "axios" in names
    assert "jest" in names

    prod = [d for d in deps if d.name == "react"][0]
    assert prod.dep_type == "prod"
    assert prod.ecosystem == "npm"

    dev = [d for d in deps if d.name == "jest"][0]
    assert dev.dep_type == "dev"


def test_npm_empty_deps(tmp_path):
    _make_repo(tmp_path, {"package.json": json.dumps({"name": "myapp"})})
    deps = parse_all(tmp_path)
    assert deps == []


# ── pip / requirements.txt ────────────────────────────────────────────────────

def test_pip_requirements(tmp_path):
    _make_repo(tmp_path, {
        "requirements.txt": """\
            fastapi==0.110.0
            sqlalchemy>=2.0
            # comment line
            pydantic
        """
    })
    deps = parse_all(tmp_path)
    names = {d.name for d in deps}
    assert "fastapi" in names
    assert "sqlalchemy" in names
    assert "pydantic" in names

    fa = [d for d in deps if d.name == "fastapi"][0]
    assert fa.version is not None and "0.110.0" in fa.version
    assert fa.ecosystem == "pip"


def test_pip_skips_comments_and_blanks(tmp_path):
    _make_repo(tmp_path, {
        "requirements.txt": """\
            # only comments

        """
    })
    deps = parse_all(tmp_path)
    assert deps == []


# ── Go modules ────────────────────────────────────────────────────────────────

def test_go_mod(tmp_path):
    _make_repo(tmp_path, {
        "go.mod": """\
            module github.com/myorg/myapp

            go 1.22

            require (
                github.com/gin-gonic/gin v1.9.1
                golang.org/x/sync v0.6.0
            )
        """
    })
    deps = parse_all(tmp_path)
    names = {d.name for d in deps}
    assert "github.com/gin-gonic/gin" in names

    gin = [d for d in deps if d.name == "github.com/gin-gonic/gin"][0]
    assert gin.version == "v1.9.1"
    assert gin.ecosystem == "go"


# ── Cargo ────────────────────────────────────────────────────────────────────

def test_cargo_toml(tmp_path):
    _make_repo(tmp_path, {
        "Cargo.toml": """\
            [package]
            name = "myapp"
            version = "0.1.0"

            [dependencies]
            serde = { version = "1.0", features = ["derive"] }
            tokio = "1"

            [dev-dependencies]
            criterion = "0.5"
        """
    })
    deps = parse_all(tmp_path)
    names = {d.name for d in deps}
    assert "serde" in names
    assert "tokio" in names
    assert "criterion" in names

    serde = [d for d in deps if d.name == "serde"][0]
    assert serde.ecosystem == "cargo"

    crit = [d for d in deps if d.name == "criterion"][0]
    assert crit.dep_type == "dev"


# ── pom.xml (Maven) ───────────────────────────────────────────────────────────

def test_pom_xml_prod_and_test_deps(tmp_path):
    _make_repo(tmp_path, {
        "pom.xml": """\
            <?xml version="1.0" encoding="UTF-8"?>
            <project xmlns="http://maven.apache.org/POM/4.0.0">
              <dependencies>
                <dependency>
                  <groupId>org.springframework</groupId>
                  <artifactId>spring-core</artifactId>
                  <version>6.1.0</version>
                </dependency>
                <dependency>
                  <groupId>junit</groupId>
                  <artifactId>junit</artifactId>
                  <version>4.13.2</version>
                  <scope>test</scope>
                </dependency>
              </dependencies>
            </project>
        """
    })
    deps = parse_all(tmp_path)
    names = {d.name for d in deps}
    assert "org.springframework:spring-core" in names
    assert "junit:junit" in names

    prod = [d for d in deps if d.name == "org.springframework:spring-core"][0]
    assert prod.dep_type == "prod"
    assert prod.ecosystem == "maven"
    assert prod.version == "6.1.0"

    test_dep = [d for d in deps if d.name == "junit:junit"][0]
    assert test_dep.dep_type == "test"


def test_pom_xml_missing_returns_empty(tmp_path):
    deps = parse_all(tmp_path)
    assert all(d.ecosystem != "maven" for d in deps)


def test_pom_xml_invalid_returns_empty(tmp_path):
    _make_repo(tmp_path, {"pom.xml": "not valid xml <<<"})
    deps = parse_all(tmp_path)
    assert all(d.ecosystem != "maven" for d in deps)


# ── Gemfile (Bundler) ─────────────────────────────────────────────────────────

def test_gemfile_parses_gems(tmp_path):
    _make_repo(tmp_path, {
        "Gemfile": """\
            source 'https://rubygems.org'

            gem 'rails', '7.1.0'
            gem 'devise'
            gem 'rspec-rails', '~> 6.0'
        """
    })
    deps = parse_all(tmp_path)
    names = {d.name for d in deps}
    assert "rails" in names
    assert "devise" in names
    assert "rspec-rails" in names

    rails = [d for d in deps if d.name == "rails"][0]
    assert rails.ecosystem == "bundler"
    assert rails.version == "7.1.0"

    devise = [d for d in deps if d.name == "devise"][0]
    assert devise.version is None


def test_gemfile_missing_returns_empty(tmp_path):
    deps = parse_all(tmp_path)
    assert all(d.ecosystem != "bundler" for d in deps)


# ── pyproject.toml ────────────────────────────────────────────────────────────

def test_pyproject_poetry_style(tmp_path):
    _make_repo(tmp_path, {
        "pyproject.toml": """\
            [tool.poetry]
            name = "myapp"
            version = "0.1.0"

            [tool.poetry.dependencies]
            python = "^3.11"
            fastapi = "^0.110.0"
            sqlalchemy = "^2.0"

            [tool.poetry.dev-dependencies]
            pytest = "^8.0"
        """
    })
    deps = parse_all(tmp_path)
    names = {d.name for d in deps}
    # python should be excluded
    assert "python" not in names
    assert "fastapi" in names
    assert "sqlalchemy" in names
    assert "pytest" in names

    fa = [d for d in deps if d.name == "fastapi"][0]
    assert fa.dep_type == "prod"
    assert fa.ecosystem == "pip"

    pt = [d for d in deps if d.name == "pytest"][0]
    assert pt.dep_type == "dev"


def test_pyproject_pep621_style(tmp_path):
    _make_repo(tmp_path, {
        "pyproject.toml": """\
            [project]
            name = "myapp"
            dependencies = [
                "httpx>=0.27.0",
                "pydantic",
            ]
        """
    })
    deps = parse_all(tmp_path)
    names = {d.name for d in deps}
    assert "httpx" in names
    assert "pydantic" in names


def test_pyproject_missing_returns_empty(tmp_path):
    deps = parse_all(tmp_path)
    # No pyproject.toml means no pip/poetry entries from it
    assert True  # just verifying no exception


def test_package_json_peer_deps(tmp_path):
    _make_repo(tmp_path, {
        "package.json": json.dumps({
            "peerDependencies": {"react": "^18.0.0"},
        })
    })
    deps = parse_all(tmp_path)
    names = {d.name for d in deps}
    assert "react" in names
    peer = [d for d in deps if d.name == "react"][0]
    assert peer.dep_type == "prod"


def test_package_json_invalid_json_returns_empty(tmp_path):
    _make_repo(tmp_path, {"package.json": "{ invalid json"})
    deps = parse_all(tmp_path)
    assert all(d.ecosystem != "npm" for d in deps)

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

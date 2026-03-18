import pytest
from pathlib import Path
import tempfile, os

from app.services.analysis.stack_detector import detect_stack, StackInfo
from app.services.analysis.file_analyzer import LanguageStat


def _make_langs(**kwargs) -> dict:
    return {k: LanguageStat(name=k, loc=v) for k, v in kwargs.items()}


def _make_repo(files: dict[str, str]) -> Path:
    d = Path(tempfile.mkdtemp())
    for name, content in files.items():
        p = d / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)
    return d


def test_detect_docker():
    repo = _make_repo({"Dockerfile": "FROM python:3.12"})
    info = detect_stack(repo, _make_langs(Python=1000))
    assert info.has_docker is True


def test_detect_bitbucket_ci():
    repo = _make_repo({"bitbucket-pipelines.yml": "pipelines:\n  default:\n    - step:\n"})
    info = detect_stack(repo, _make_langs(Python=500))
    assert info.has_ci is True
    assert info.ci_provider == "bitbucket"


def test_detect_gitlab_ci():
    repo = _make_repo({".gitlab-ci.yml": "stages:\n  - test\n"})
    info = detect_stack(repo, _make_langs(Python=500))
    assert info.has_ci is True
    assert info.ci_provider == "gitlab"


def test_detect_npm_package_manager():
    repo = _make_repo({"package-lock.json": "{}"})
    info = detect_stack(repo, _make_langs(JavaScript=2000))
    assert "npm" in info.package_managers


def test_backend_project_type():
    repo = _make_repo({})
    info = detect_stack(repo, _make_langs(Python=5000))
    assert info.project_type == "backend_service"


def test_frontend_project_type():
    repo = _make_repo({})
    info = detect_stack(repo, _make_langs(JavaScript=4000, HTML=500, CSS=300))
    assert info.project_type == "frontend_application"


def test_primary_language():
    repo = _make_repo({})
    info = detect_stack(repo, _make_langs(Python=3000, JavaScript=1000))
    assert info.primary_language == "Python"


def test_detect_github_actions_ci():
    repo = _make_repo({".github/workflows/ci.yml": "on: push"})
    info = detect_stack(repo, _make_langs(Python=500))
    assert info.has_ci is True
    assert info.ci_provider == "github_actions"


def test_detect_jenkins_ci():
    repo = _make_repo({"Jenkinsfile": "pipeline {}"})
    info = detect_stack(repo, _make_langs(Python=500))
    assert info.has_ci is True
    assert info.ci_provider == "jenkins"


def test_monorepo_detection():
    repo = _make_repo({
        "packages/.keep": "",
        "apps/.keep": "",
    })
    info = detect_stack(repo, _make_langs(Python=1000, JavaScript=500))
    assert info.project_type == "monorepo"


def test_cli_project_type():
    repo = _make_repo({"cli.py": "import click"})
    info = detect_stack(repo, _make_langs(Python=2000))
    assert info.project_type == "cli_tool"


def test_monolith_project_type():
    repo = _make_repo({})
    info = detect_stack(repo, _make_langs(Python=3000, JavaScript=2000))
    assert info.project_type == "monolith"


def test_unknown_project_type():
    repo = _make_repo({})
    info = detect_stack(repo, {})
    assert info.project_type == "unknown"


def test_detect_poetry_package_manager():
    repo = _make_repo({"poetry.lock": "# lock file"})
    info = detect_stack(repo, _make_langs(Python=500))
    assert "poetry" in info.package_managers


def test_detect_pip_package_manager():
    repo = _make_repo({"requirements.txt": "fastapi\n"})
    info = detect_stack(repo, _make_langs(Python=500))
    assert "pip" in info.package_managers


def test_detect_docker_compose():
    repo = _make_repo({"docker-compose.yml": "version: '3'"})
    info = detect_stack(repo, _make_langs(Python=500))
    assert info.has_docker is True


def test_detect_react_framework():
    repo = _make_repo({
        "package.json": '{"dependencies": {"react": "^18.0.0"}}'
    })
    info = detect_stack(repo, _make_langs(JavaScript=3000))
    assert "React" in info.frameworks


def test_detect_fastapi_framework():
    repo = _make_repo({"requirements.txt": "fastapi==0.110.0\n"})
    info = detect_stack(repo, _make_langs(Python=2000))
    assert "FastAPI" in info.frameworks


def test_detect_django_framework():
    repo = _make_repo({"requirements.txt": "django==5.0\n"})
    info = detect_stack(repo, _make_langs(Python=2000))
    assert "Django" in info.frameworks


def test_detect_ruff_linter():
    repo = _make_repo({
        "pyproject.toml": "[tool.ruff]\nline-length = 88\n"
    })
    info = detect_stack(repo, _make_langs(Python=1000))
    assert "Ruff" in info.linters


def test_detect_black_formatter():
    repo = _make_repo({
        "pyproject.toml": "[tool.black]\nline-length = 88\n"
    })
    info = detect_stack(repo, _make_langs(Python=1000))
    assert "Black" in info.formatters


def test_detect_eslint():
    repo = _make_repo({".eslintrc.json": '{"rules": {}}'})
    info = detect_stack(repo, _make_langs(JavaScript=2000))
    assert "ESLint" in info.linters


def test_detect_prettier():
    repo = _make_repo({".prettierrc": '{"semi": false}'})
    info = detect_stack(repo, _make_langs(JavaScript=2000))
    assert "Prettier" in info.formatters


def test_detect_kubernetes():
    k8s_manifest = "apiVersion: apps/v1\nkind: Deployment\nmetadata:\n  name: app\n"
    repo = _make_repo({"k8s/deployment.yaml": k8s_manifest})
    info = detect_stack(repo, _make_langs(Python=1000))
    assert info.has_kubernetes is True


def test_detect_go_modules():
    repo = _make_repo({"go.mod": "module example.com/app\ngo 1.22\n"})
    info = detect_stack(repo, _make_langs(Go=2000))
    assert "go modules" in info.package_managers


def test_detect_go_gin_framework():
    repo = _make_repo({
        "go.mod": "module example.com/app\ngo 1.22\nrequire github.com/gin-gonic/gin v1.9.1\n"
    })
    info = detect_stack(repo, _make_langs(Go=2000))
    assert "Gin" in info.frameworks


def test_no_ci_when_none_present():
    repo = _make_repo({})
    info = detect_stack(repo, _make_langs(Python=500))
    assert info.has_ci is False
    assert info.ci_provider is None


def test_detect_mypy_from_pyproject():
    repo = _make_repo({
        "pyproject.toml": "[mypy]\nstrict = true\n"
    })
    info = detect_stack(repo, _make_langs(Python=1000))
    assert "MyPy" in info.linters


def test_detect_flake8_from_setup_cfg():
    repo = _make_repo({"setup.cfg": "[flake8]\nmax-line-length = 120\n"})
    info = detect_stack(repo, _make_langs(Python=1000))
    assert "Flake8" in info.linters

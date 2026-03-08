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

"""Tests for lockfile parsers added in dependency_parser.py"""
from __future__ import annotations
from pathlib import Path
import shutil

import pytest

from app.services.analysis.dependency_parser import (
    _parse_poetry_lock,
    _parse_pipfile_lock,
    _parse_cargo_lock,
    _parse_gemfile_lock,
    _parse_composer_lock,
    _parse_composer_json,
    _parse_nuget,
    _parse_package_lock_json,
    _parse_yarn_lock,
    _deduplicate,
    ParsedDependency,
)

FIXTURES = Path(__file__).parent / "fixtures"


# ── poetry.lock ───────────────────────────────────────────────────────────────

class TestPoetryLock:
    def test_fixture(self):
        deps = _parse_poetry_lock(FIXTURES)
        names = {d.name for d in deps}
        assert "requests" in names
        assert "pytest" in names
        assert "certifi" in names

    def test_discovery_mode(self):
        deps = _parse_poetry_lock(FIXTURES)
        for d in deps:
            assert d.discovery_mode == "locked"
            assert d.package_manager == "poetry"

    def test_dev_category(self):
        deps = _parse_poetry_lock(FIXTURES)
        pytest_dep = next(d for d in deps if d.name == "pytest")
        assert pytest_dep.dep_type == "dev"

    def test_prod_category(self):
        deps = _parse_poetry_lock(FIXTURES)
        req_dep = next(d for d in deps if d.name == "requests")
        assert req_dep.dep_type == "prod"

    def test_no_file(self, tmp_path):
        assert _parse_poetry_lock(tmp_path) == []


# ── Pipfile.lock ──────────────────────────────────────────────────────────────

class TestPipfileLock:
    def test_fixture(self):
        deps = _parse_pipfile_lock(FIXTURES)
        names = {d.name for d in deps}
        assert "flask" in names
        assert "pytest" in names
        assert "black" in names

    def test_discovery_mode(self):
        deps = _parse_pipfile_lock(FIXTURES)
        for d in deps:
            assert d.discovery_mode == "locked"
            assert d.package_manager == "pipenv"

    def test_version_stripped(self):
        deps = _parse_pipfile_lock(FIXTURES)
        flask = next(d for d in deps if d.name == "flask")
        assert flask.version == "2.3.2"

    def test_dev_section(self):
        deps = _parse_pipfile_lock(FIXTURES)
        pytest_dep = next(d for d in deps if d.name == "pytest")
        assert pytest_dep.dep_type == "dev"


# ── Cargo.lock ────────────────────────────────────────────────────────────────

class TestCargoLock:
    def test_fixture(self):
        deps = _parse_cargo_lock(FIXTURES)
        names = {d.name for d in deps}
        assert "serde" in names
        assert "tokio" in names

    def test_discovery_mode(self):
        deps = _parse_cargo_lock(FIXTURES)
        for d in deps:
            assert d.discovery_mode == "locked"
            assert d.ecosystem == "cargo"

    def test_version(self):
        deps = _parse_cargo_lock(FIXTURES)
        serde = next(d for d in deps if d.name == "serde")
        assert serde.version == "1.0.183"


# ── Gemfile.lock ──────────────────────────────────────────────────────────────

class TestGemfileLock:
    def test_fixture(self):
        deps = _parse_gemfile_lock(FIXTURES)
        names = {d.name for d in deps}
        assert "rails" in names
        assert "rspec" in names

    def test_discovery_mode(self):
        deps = _parse_gemfile_lock(FIXTURES)
        for d in deps:
            assert d.discovery_mode == "locked"
            assert d.ecosystem == "bundler"

    def test_version(self):
        deps = _parse_gemfile_lock(FIXTURES)
        rails = next(d for d in deps if d.name == "rails")
        assert rails.version == "7.0.6"


# ── composer.lock ─────────────────────────────────────────────────────────────

class TestComposerLock:
    def test_fixture(self):
        deps = _parse_composer_lock(FIXTURES)
        names = {d.name for d in deps}
        assert "laravel/framework" in names
        assert "symfony/console" in names
        assert "phpunit/phpunit" in names

    def test_discovery_mode(self):
        deps = _parse_composer_lock(FIXTURES)
        for d in deps:
            assert d.discovery_mode == "locked"
            assert d.ecosystem == "composer"

    def test_dev_packages(self):
        deps = _parse_composer_lock(FIXTURES)
        phpunit = next(d for d in deps if d.name == "phpunit/phpunit")
        assert phpunit.dep_type == "dev"


# ── NuGet (.csproj) ───────────────────────────────────────────────────────────

class TestNuget:
    def test_fixture(self):
        deps = _parse_nuget(FIXTURES)
        names = {d.name for d in deps}
        assert "Newtonsoft.Json" in names
        assert "Microsoft.EntityFrameworkCore" in names
        assert "coverlet.collector" in names

    def test_private_assets_is_dev(self):
        deps = _parse_nuget(FIXTURES)
        coverlet = next(d for d in deps if d.name == "coverlet.collector")
        assert coverlet.dep_type == "dev"

    def test_ecosystem(self):
        deps = _parse_nuget(FIXTURES)
        for d in deps:
            assert d.ecosystem == "nuget"


# ── package-lock.json ─────────────────────────────────────────────────────────

class TestPackageLockJson:
    def test_fixture(self):
        deps = _parse_package_lock_json(FIXTURES)
        names = {d.name for d in deps}
        assert "express" in names
        assert "jest" in names
        assert "accepts" in names

    def test_discovery_mode(self):
        deps = _parse_package_lock_json(FIXTURES)
        for d in deps:
            assert d.discovery_mode == "locked"
            assert d.package_manager == "npm"

    def test_direct_vs_transitive(self):
        deps = _parse_package_lock_json(FIXTURES)
        express = next(d for d in deps if d.name == "express")
        accepts = next(d for d in deps if d.name == "accepts")
        assert express.is_direct is True
        assert accepts.is_direct is False

    def test_dev_flag(self):
        deps = _parse_package_lock_json(FIXTURES)
        jest = next(d for d in deps if d.name == "jest")
        assert jest.dep_type == "dev"


# ── Deduplication ─────────────────────────────────────────────────────────────

class TestDeduplicate:
    def test_locked_overrides_declared(self):
        manifest = ParsedDependency("requests", ">=2.0", "prod", "requirements.txt", "pip", discovery_mode="declared_only")
        lockfile = ParsedDependency("requests", "2.31.0", "prod", "poetry.lock", "pip", discovery_mode="locked", package_manager="poetry")
        result = _deduplicate([manifest, lockfile])
        assert len(result) == 1
        assert result[0].version == "2.31.0"
        assert result[0].discovery_mode == "locked"

    def test_same_priority_first_wins(self):
        a = ParsedDependency("flask", "2.3.0", "prod", "requirements.txt", "pip", discovery_mode="declared_only")
        b = ParsedDependency("flask", "2.3.1", "prod", "pyproject.toml", "pip", discovery_mode="declared_only")
        result = _deduplicate([a, b])
        assert len(result) == 1
        assert result[0].version == "2.3.0"

    def test_different_ecosystems_kept_separate(self):
        a = ParsedDependency("yaml", "1.0.0", "prod", "Cargo.toml", "cargo")
        b = ParsedDependency("yaml", "1.0.0", "prod", "requirements.txt", "pip")
        result = _deduplicate([a, b])
        assert len(result) == 2

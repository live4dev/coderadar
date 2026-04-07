"""Tests for app/services/analysis/license_report.py"""
from __future__ import annotations
import csv
import io
from dataclasses import dataclass
from unittest.mock import MagicMock
from datetime import datetime, timezone

import pytest

from app.services.analysis.license_report import (
    _classify_license,
    build_license_report,
    build_license_csv,
    _CSV_COLUMNS,
)


# ── _classify_license ────────────────────────────────────────────────────────

class TestClassifyLicense:
    def test_permissive_mit(self):
        assert _classify_license("MIT") == "permissive"

    def test_permissive_apache(self):
        assert _classify_license("Apache-2.0") == "permissive"

    def test_permissive_bsd(self):
        assert _classify_license("BSD-3-Clause") == "permissive"

    def test_weak_copyleft_lgpl(self):
        assert _classify_license("LGPL-2.1-only") == "weak_copyleft"

    def test_weak_copyleft_mpl(self):
        assert _classify_license("MPL-2.0") == "weak_copyleft"

    def test_strong_copyleft_gpl(self):
        assert _classify_license("GPL-3.0-only") == "strong_copyleft"

    def test_strong_copyleft_agpl(self):
        assert _classify_license("AGPL-3.0-only") == "strong_copyleft"

    def test_unknown_none(self):
        assert _classify_license(None) == "unknown"

    def test_unknown_custom(self):
        assert _classify_license("Proprietary-Corp-1.0") == "unknown"

    def test_gpl_prefix_strong(self):
        assert _classify_license("GPL-2.0-or-later") == "strong_copyleft"


# ── Helpers for building mock Dependency objects ──────────────────────────────

def _make_dep(
    name="requests",
    version="2.31.0",
    dep_type="prod",
    manifest_file="requirements.txt",
    ecosystem="pip",
    package_manager=None,
    license_spdx="MIT",
    license_raw="MIT",
    license_risk="safe",
    is_direct=True,
    license_expression=None,
    license_confidence="high",
    license_source="lockfile",
    license_notes=None,
    discovery_mode="locked",
    is_optional_dependency=False,
    is_private=False,
):
    dep = MagicMock()
    dep.name = name
    dep.version = version
    dep.dep_type = MagicMock()
    dep.dep_type.value = dep_type
    dep.manifest_file = manifest_file
    dep.ecosystem = ecosystem
    dep.package_manager = package_manager
    dep.license_spdx = license_spdx
    dep.license_raw = license_raw
    dep.license_risk = license_risk
    dep.is_direct = is_direct
    dep.license_expression = license_expression
    dep.license_confidence = license_confidence
    dep.license_source = license_source
    dep.license_notes = license_notes
    dep.discovery_mode = discovery_mode
    dep.is_optional_dependency = is_optional_dependency
    dep.is_private = is_private
    return dep


def _make_scan(scan_id=1, branch="main", commit_sha="abc123"):
    scan = MagicMock()
    scan.id = scan_id
    scan.branch = branch
    scan.commit_sha = commit_sha
    scan.completed_at = datetime(2026, 4, 2, 12, 0, 0, tzinfo=timezone.utc)
    scan.started_at = None
    return scan


# ── build_license_report ─────────────────────────────────────────────────────

class TestBuildLicenseReport:
    def test_basic_structure(self):
        scan = _make_scan()
        deps = [_make_dep()]
        report = build_license_report(scan, deps, "my-repo")

        assert report["repository"] == "my-repo"
        assert report["scan_id"] == 1
        assert "scan_time_utc" in report
        assert "scanner_version" in report
        assert "packages" in report
        assert "summary" in report
        assert "problems" in report
        assert "ecosystems" in report

    def test_package_fields(self):
        scan = _make_scan()
        deps = [_make_dep()]
        report = build_license_report(scan, deps, "my-repo")

        pkg = report["packages"][0]
        assert pkg["name"] == "requests"
        assert pkg["version"] == "2.31.0"
        assert pkg["license_normalized"] == "MIT"
        assert pkg["license_classification"] == "permissive"
        assert pkg["discovery_mode"] == "locked"
        assert pkg["is_direct"] is True
        assert pkg["is_transitive"] is False

    def test_summary_counts(self):
        scan = _make_scan()
        deps = [
            _make_dep("pkg1", license_spdx="MIT", license_risk="safe"),
            _make_dep("pkg2", license_spdx="MIT", license_risk="safe"),
            _make_dep("pkg3", license_spdx="GPL-3.0-only", license_risk="risky"),
            _make_dep("pkg4", license_spdx=None, license_raw=None, license_risk="unknown"),
        ]
        report = build_license_report(scan, deps, "repo")
        summary = report["summary"]

        assert summary["total_packages"] == 4
        assert summary["licensed_packages"] == 3
        assert summary["unknown_license_packages"] == 1
        assert summary["risky_count"] == 1
        assert summary["safe_count"] == 2
        assert summary["by_license"]["MIT"] == 2
        assert summary["by_classification"]["permissive"] == 2
        assert summary["by_classification"]["strong_copyleft"] == 1

    def test_missing_license_problem(self):
        scan = _make_scan()
        deps = [_make_dep("mystery", license_spdx=None, license_raw=None, license_risk="unknown")]
        report = build_license_report(scan, deps, "repo")
        problems = report["problems"]
        assert any(p["type"] == "missing_license" and p["package"] == "mystery" for p in problems)

    def test_private_package_problem(self):
        scan = _make_scan()
        deps = [_make_dep("internal-pkg", license_spdx=None, license_raw=None,
                          license_risk="unknown", is_private=True)]
        report = build_license_report(scan, deps, "repo")
        problems = report["problems"]
        assert any(p["type"] == "private_unknown_license" for p in problems)

    def test_ambiguous_license_problem(self):
        scan = _make_scan()
        deps = [_make_dep("ambig", license_spdx=None, license_raw="BSD",
                          license_risk="unknown", license_confidence="low",
                          license_notes="Ambiguous BSD")]
        report = build_license_report(scan, deps, "repo")
        problems = report["problems"]
        assert any(p["type"] == "ambiguous_license" for p in problems)

    def test_ecosystems_list(self):
        scan = _make_scan()
        deps = [
            _make_dep("a", ecosystem="pip"),
            _make_dep("b", ecosystem="npm"),
            _make_dep("c", ecosystem="pip"),
        ]
        report = build_license_report(scan, deps, "repo")
        assert sorted(report["ecosystems"]) == ["npm", "pip"]

    def test_empty_deps(self):
        scan = _make_scan()
        report = build_license_report(scan, [], "empty-repo")
        assert report["summary"]["total_packages"] == 0
        assert report["packages"] == []
        assert report["problems"] == []


# ── build_license_csv ────────────────────────────────────────────────────────

class TestBuildLicenseCsv:
    def test_header_row(self):
        csv_str = build_license_csv([])
        reader = csv.DictReader(io.StringIO(csv_str))
        assert set(reader.fieldnames or []) == set(_CSV_COLUMNS)

    def test_data_row(self):
        deps = [_make_dep("flask", "2.3.2", license_spdx="BSD-3-Clause", license_risk="safe")]
        csv_str = build_license_csv(deps)
        reader = csv.DictReader(io.StringIO(csv_str))
        rows = list(reader)
        assert len(rows) == 1
        assert rows[0]["name"] == "flask"
        assert rows[0]["license_normalized"] == "BSD-3-Clause"
        assert rows[0]["license_classification"] == "permissive"

    def test_multiple_rows(self):
        deps = [
            _make_dep("a"),
            _make_dep("b"),
            _make_dep("c"),
        ]
        csv_str = build_license_csv(deps)
        reader = csv.DictReader(io.StringIO(csv_str))
        rows = list(reader)
        assert len(rows) == 3

    def test_empty_deps(self):
        csv_str = build_license_csv([])
        lines = csv_str.strip().splitlines()
        assert len(lines) == 1  # only header

    def test_special_chars_escaped(self):
        deps = [_make_dep("pkg", license_raw='Has "quotes" and, commas')]
        csv_str = build_license_csv(deps)
        # Should not crash; CSV writer handles quoting
        reader = csv.DictReader(io.StringIO(csv_str))
        rows = list(reader)
        assert len(rows) == 1

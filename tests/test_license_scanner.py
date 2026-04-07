"""Tests for app/services/analysis/license_scanner.py"""
from __future__ import annotations
import json
from pathlib import Path

import pytest

from app.services.analysis.license_scanner import (
    LicenseInfo,
    _normalise_spdx,
    _classify_risk,
    _classify_license_file,
    _scan_npm,
    _scan_pip_dist_info,
    _scan_cargo_vendor,
    _scan_go_vendor,
    _scan_maven_poms,
    _scan_ruby_vendor,
    _scan_gemfile_lock,
)

FIXTURES = Path(__file__).parent / "fixtures"


# ── _normalise_spdx ───────────────────────────────────────────────────────────

class TestNormaliseSpdx:
    def test_well_known_mit(self):
        spdx, expr, notes = _normalise_spdx("MIT")
        assert spdx == "MIT"
        assert expr is None
        assert notes is None

    def test_alias_apache(self):
        spdx, expr, notes = _normalise_spdx("Apache 2.0")
        assert spdx == "Apache-2.0"

    def test_alias_bsd_ambiguous(self):
        spdx, expr, notes = _normalise_spdx("BSD")
        # "BSD" maps to BSD-2-Clause in the SPDX map
        assert spdx == "BSD-2-Clause"

    def test_compound_or_expression(self):
        spdx, expr, notes = _normalise_spdx("MIT OR Apache-2.0")
        assert expr == "MIT OR Apache-2.0"
        assert spdx == "MIT"
        assert notes is not None

    def test_compound_and_expression(self):
        spdx, expr, notes = _normalise_spdx("GPL-2.0-only AND MIT")
        assert expr == "GPL-2.0-only AND MIT"
        assert spdx == "GPL-2.0-only"

    def test_see_license_in_file(self):
        spdx, expr, notes = _normalise_spdx("SEE LICENSE IN LICENSE.txt")
        assert spdx is None
        assert notes is not None and "file" in notes.lower()

    def test_none_input(self):
        spdx, expr, notes = _normalise_spdx(None)
        assert spdx is None
        assert expr is None
        assert notes is None

    def test_spdx_id_passthrough(self):
        spdx, expr, notes = _normalise_spdx("LGPL-2.1-or-later")
        assert spdx == "LGPL-2.1-or-later"


class TestClassifyRisk:
    def test_safe_mit(self):
        assert _classify_risk("MIT") == "safe"

    def test_risky_gpl(self):
        assert _classify_risk("GPL-3.0-only") == "risky"

    def test_risky_agpl(self):
        assert _classify_risk("AGPL-3.0-only") == "risky"

    def test_unknown_none(self):
        assert _classify_risk(None) == "unknown"

    def test_unknown_custom(self):
        assert _classify_risk("Custom-License-1.0") == "unknown"

    def test_safe_apache(self):
        assert _classify_risk("Apache-2.0") == "safe"


class TestLicenseFileHeuristic:
    def test_mit_file(self):
        text = "Permission is hereby granted, free of charge, to any person obtaining a copy without restriction"
        assert _classify_license_file(text) == "MIT"

    def test_apache_file(self):
        text = "Apache License Version 2.0, January 2004"
        assert _classify_license_file(text) == "Apache-2.0"

    def test_unknown_file(self):
        text = "This is a custom proprietary license."
        assert _classify_license_file(text) is None


# ── _scan_npm ────────────────────────────────────────────────────────────────

class TestScanNpm:
    def test_lockfile_v2(self, tmp_path):
        lock = {
            "lockfileVersion": 2,
            "packages": {
                "": {"name": "app"},
                "node_modules/express": {"version": "4.18.2", "license": "MIT"},
                "node_modules/lodash": {"version": "4.17.21", "license": "MIT"},
            }
        }
        pkg = {"dependencies": {"express": "^4.18.2"}}
        (tmp_path / "package-lock.json").write_text(json.dumps(lock))
        (tmp_path / "package.json").write_text(json.dumps(pkg))

        result = _scan_npm(tmp_path)

        assert ("express", "npm") in result
        lic = result[("express", "npm")]
        assert lic.spdx == "MIT"
        assert lic.confidence == "high"
        assert lic.source == "lockfile"
        assert lic.is_direct is True

        assert ("lodash", "npm") in result
        assert result[("lodash", "npm")].is_direct is False

    def test_no_lockfile(self, tmp_path):
        assert _scan_npm(tmp_path) == {}

    def test_list_license_field(self, tmp_path):
        lock = {
            "lockfileVersion": 2,
            "packages": {
                "node_modules/dual": {"version": "1.0.0", "license": ["MIT", "Apache-2.0"]},
            }
        }
        (tmp_path / "package-lock.json").write_text(json.dumps(lock))
        result = _scan_npm(tmp_path)
        lic = result[("dual", "npm")]
        assert "MIT" in (lic.raw or "")
        assert "Apache-2.0" in (lic.raw or "")


# ── _scan_cargo_vendor ───────────────────────────────────────────────────────

class TestScanCargoVendor:
    def test_vendor_toml(self, tmp_path):
        vendor = tmp_path / "vendor" / "serde"
        vendor.mkdir(parents=True)
        (vendor / "Cargo.toml").write_text(
            '[package]\nname = "serde"\nversion = "1.0.0"\nlicense = "MIT OR Apache-2.0"\n'
        )
        result = _scan_cargo_vendor(tmp_path)
        assert ("serde", "cargo") in result
        lic = result[("serde", "cargo")]
        assert lic.spdx == "MIT"
        assert lic.expression == "MIT OR Apache-2.0"
        assert lic.confidence == "high"
        assert lic.source == "vendor_manifest"

    def test_no_vendor(self, tmp_path):
        assert _scan_cargo_vendor(tmp_path) == {}


# ── _scan_go_vendor ───────────────────────────────────────────────────────────

class TestScanGoVendor:
    def test_vendor_license_file(self, tmp_path):
        modules_txt = tmp_path / "vendor" / "modules.txt"
        modules_txt.parent.mkdir(parents=True)
        modules_txt.write_text("# github.com/pkg/errors v0.9.1\n")
        mod_dir = tmp_path / "vendor" / "github.com" / "pkg" / "errors"
        mod_dir.mkdir(parents=True)
        (mod_dir / "LICENSE").write_text(
            "Permission is hereby granted, free of charge, without restriction"
        )
        result = _scan_go_vendor(tmp_path)
        assert ("github.com/pkg/errors", "go") in result
        lic = result[("github.com/pkg/errors", "go")]
        assert lic.spdx == "MIT"
        assert lic.source == "license_file"


# ── _scan_gemfile_lock ────────────────────────────────────────────────────────

class TestScanGemfileLock:
    def test_basic(self, tmp_path):
        content = """\
GEM
  remote: https://rubygems.org/
  specs:
    rails (7.0.6)
    rspec (3.12.0)

PLATFORMS
  ruby
"""
        (tmp_path / "Gemfile.lock").write_text(content)
        result = _scan_gemfile_lock(tmp_path)
        assert ("rails", "bundler") in result
        assert ("rspec", "bundler") in result
        # Gemfile.lock has no license info — should be unknown confidence
        assert result[("rails", "bundler")].confidence == "unknown"

    def test_fixture(self):
        result = _scan_gemfile_lock(FIXTURES)
        assert ("rails", "bundler") in result
        assert ("rspec", "bundler") in result

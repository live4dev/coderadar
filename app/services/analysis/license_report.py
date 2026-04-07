"""
License inventory report builder.

Consumes Dependency ORM rows and produces:
  - A normalized JSON report (build_license_report)
  - A flat CSV export (build_license_csv)
"""
from __future__ import annotations

import csv
import io
from datetime import datetime, timezone
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.dependency import Dependency
    from app.models.scan import Scan

_SCANNER_VERSION = "1.0.0"

# ── License classification ────────────────────────────────────────────────────

_PERMISSIVE: frozenset[str] = frozenset({
    "MIT", "Apache-2.0", "BSD-2-Clause", "BSD-3-Clause", "BSD-4-Clause",
    "ISC", "CC0-1.0", "Unlicense", "WTFPL", "0BSD", "Zlib", "Python-2.0",
    "PSF-2.0", "Artistic-2.0", "EPL-1.0", "EPL-2.0",
})

_WEAK_COPYLEFT: frozenset[str] = frozenset({
    "MPL-2.0", "LGPL-2.0-only", "LGPL-2.0-or-later",
    "LGPL-2.1-only", "LGPL-2.1-or-later",
    "LGPL-3.0-only", "LGPL-3.0-or-later",
    "EUPL-1.1", "EUPL-1.2",
    "CDDL-1.0",
})

_STRONG_COPYLEFT: frozenset[str] = frozenset({
    "GPL-2.0-only", "GPL-2.0-or-later",
    "GPL-3.0-only", "GPL-3.0-or-later",
    "AGPL-3.0-only", "AGPL-3.0-or-later",
    "OSL-3.0", "CPAL-1.0", "RPSL-1.0",
})


def _classify_license(spdx: str | None) -> str:
    """Return one of: permissive | weak_copyleft | strong_copyleft | unknown."""
    if spdx is None:
        return "unknown"
    if spdx in _PERMISSIVE:
        return "permissive"
    if spdx in _WEAK_COPYLEFT:
        return "weak_copyleft"
    if spdx in _STRONG_COPYLEFT:
        return "strong_copyleft"
    # Prefix-based fallback
    if any(spdx.startswith(p) for p in ("GPL-", "AGPL-")):
        return "strong_copyleft"
    if any(spdx.startswith(p) for p in ("LGPL-", "MPL-", "EUPL-")):
        return "weak_copyleft"
    return "unknown"


# ── JSON report builder ───────────────────────────────────────────────────────

def build_license_report(
    scan: "Scan",
    deps: "list[Dependency]",
    repo_name: str,
) -> dict:
    """
    Build a normalized JSON license inventory report.

    Returns a dict matching the schema defined in docs/todo/licences.md §9.
    """
    scan_time = (
        scan.completed_at or scan.started_at or datetime.now(timezone.utc)
    )
    ecosystems = sorted({d.ecosystem for d in deps if d.ecosystem})

    packages = []
    problems = []

    for dep in deps:
        classification = _classify_license(dep.license_spdx)
        is_transitive = not dep.is_direct

        pkg_row = {
            "name": dep.name,
            "version": dep.version,
            "ecosystem": dep.ecosystem,
            "package_manager": dep.package_manager or dep.ecosystem,
            "dependency_type": dep.dep_type.value if hasattr(dep.dep_type, "value") else str(dep.dep_type),
            "is_transitive": is_transitive,
            "is_direct": dep.is_direct,
            "is_dev_dependency": (
                dep.dep_type.value if hasattr(dep.dep_type, "value") else str(dep.dep_type)
            ) in ("dev", "test"),
            "is_optional_dependency": dep.is_optional_dependency,
            "is_private": dep.is_private,
            "source_manifest": dep.manifest_file,
            "discovery_mode": dep.discovery_mode,
            "license_raw": dep.license_raw,
            "license_normalized": dep.license_spdx,
            "license_expression": dep.license_expression,
            "license_confidence": dep.license_confidence,
            "license_source": dep.license_source,
            "license_notes": dep.license_notes,
            "license_classification": classification,
            "license_risk": dep.license_risk,
        }
        packages.append(pkg_row)

        # Collect problems
        if dep.is_private and dep.license_spdx is None:
            problems.append({
                "type": "private_unknown_license",
                "package": dep.name,
                "ecosystem": dep.ecosystem,
                "details": "Private/internal package with no license metadata",
            })
        elif dep.license_spdx is None and dep.license_raw is None:
            problems.append({
                "type": "missing_license",
                "package": dep.name,
                "ecosystem": dep.ecosystem,
                "details": "No license metadata found",
            })
        elif dep.license_confidence == "low":
            problems.append({
                "type": "ambiguous_license",
                "package": dep.name,
                "ecosystem": dep.ecosystem,
                "details": dep.license_notes or "License identification has low confidence",
            })

    # Summary
    total = len(packages)
    licensed = sum(1 for d in deps if d.license_spdx is not None)
    unknown_lic = sum(1 for d in deps if d.license_spdx is None)
    direct_count = sum(1 for d in deps if d.is_direct)

    by_license: dict[str, int] = {}
    by_classification: dict[str, int] = {
        "permissive": 0,
        "weak_copyleft": 0,
        "strong_copyleft": 0,
        "unknown": 0,
    }
    for dep in deps:
        key = dep.license_spdx or "unknown"
        by_license[key] = by_license.get(key, 0) + 1
        cls = _classify_license(dep.license_spdx)
        by_classification[cls] = by_classification.get(cls, 0) + 1

    summary = {
        "total_packages": total,
        "direct_packages": direct_count,
        "transitive_packages": total - direct_count,
        "licensed_packages": licensed,
        "unknown_license_packages": unknown_lic,
        "by_license": dict(sorted(by_license.items(), key=lambda x: -x[1])),
        "by_classification": by_classification,
        "risky_count": sum(1 for d in deps if d.license_risk == "risky"),
        "safe_count": sum(1 for d in deps if d.license_risk == "safe"),
    }

    return {
        "repository": repo_name,
        "scan_id": scan.id,
        "scan_time_utc": scan_time.isoformat(),
        "scanner_version": _SCANNER_VERSION,
        "commit_sha": scan.commit_sha,
        "branch": scan.branch,
        "ecosystems": ecosystems,
        "packages": packages,
        "summary": summary,
        "problems": problems,
    }


# ── CSV export ────────────────────────────────────────────────────────────────

_CSV_COLUMNS = [
    "name", "version", "ecosystem", "package_manager",
    "dependency_type", "is_direct", "is_transitive",
    "is_dev_dependency", "is_optional_dependency", "is_private",
    "source_manifest", "discovery_mode",
    "license_raw", "license_normalized", "license_expression",
    "license_confidence", "license_source", "license_notes",
    "license_classification", "license_risk",
]


def build_license_csv(deps: "list[Dependency]") -> str:
    """Return a UTF-8 CSV string with one row per dependency."""
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=_CSV_COLUMNS, extrasaction="ignore")
    writer.writeheader()
    for dep in deps:
        dep_type_str = dep.dep_type.value if hasattr(dep.dep_type, "value") else str(dep.dep_type)
        classification = _classify_license(dep.license_spdx)
        writer.writerow({
            "name": dep.name,
            "version": dep.version or "",
            "ecosystem": dep.ecosystem or "",
            "package_manager": dep.package_manager or dep.ecosystem or "",
            "dependency_type": dep_type_str,
            "is_direct": dep.is_direct,
            "is_transitive": not dep.is_direct,
            "is_dev_dependency": dep_type_str in ("dev", "test"),
            "is_optional_dependency": dep.is_optional_dependency,
            "is_private": dep.is_private,
            "source_manifest": dep.manifest_file or "",
            "discovery_mode": dep.discovery_mode,
            "license_raw": dep.license_raw or "",
            "license_normalized": dep.license_spdx or "",
            "license_expression": dep.license_expression or "",
            "license_confidence": dep.license_confidence,
            "license_source": dep.license_source or "",
            "license_notes": dep.license_notes or "",
            "license_classification": classification,
            "license_risk": dep.license_risk,
        })
    return buf.getvalue()

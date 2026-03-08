from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta

from app.services.analysis.file_analyzer import FileAnalysisResult
from app.services.analysis.stack_detector import StackInfo
from app.services.analysis.complexity import ComplexityResult
from app.services.git_analytics.contributor_aggregator import DeveloperStats

BUS_FACTOR_THRESHOLD = 0.70       # top contributor > 70% → concentration
BUS_FACTOR_TOP2_THRESHOLD = 0.90  # top 2 > 90% → medium risk
MONO_OWNER_THRESHOLD = 0.80       # one dev > 80% in a module/language → mono-owner


@dataclass
class RiskItem:
    risk_type: str
    severity: str  # low | medium | high | critical
    title: str
    description: str
    entity_type: str | None = None  # project | module | developer | language | file
    entity_ref: str | None = None


def detect_risks(
    file_result: FileAnalysisResult,
    stack: StackInfo,
    complexity: ComplexityResult,
    developers: list[DeveloperStats],
    latest_commit_date: datetime | None = None,
) -> list[RiskItem]:
    risks: list[RiskItem] = []

    risks.extend(_risks_tests(file_result))
    risks.extend(_risks_docs(file_result))
    risks.extend(_risks_ci(stack))
    risks.extend(_risks_lockfile(file_result, stack))
    risks.extend(_risks_oversized(complexity))
    risks.extend(_risks_concentration(developers))
    risks.extend(_risks_bus_factor(developers))
    risks.extend(_risks_mono_owner_language(developers))
    risks.extend(_risks_mono_owner_module(developers))
    risks.extend(_risks_high_complexity_module(complexity))
    risks.extend(_risks_orphan_module(developers, latest_commit_date))

    return risks


# ── Individual risk detectors ─────────────────────────────────────────────────

def _risks_tests(fa: FileAnalysisResult) -> list[RiskItem]:
    if fa.file_count_test == 0:
        return [RiskItem(
            "no_tests", "high",
            "No test files detected",
            "The repository contains no identifiable test files. "
            "This significantly increases the risk of regressions.",
            "project", None,
        )]
    total = fa.file_count_source + fa.file_count_test
    if total > 0 and fa.file_count_test / total < 0.05:
        return [RiskItem(
            "no_tests", "medium",
            "Very low test coverage (< 5% test files)",
            f"Only {fa.file_count_test} test file(s) vs {fa.file_count_source} source file(s).",
            "project", None,
        )]
    return []


def _risks_docs(fa: FileAnalysisResult) -> list[RiskItem]:
    doc_loc = sum(
        s.loc for name, s in fa.languages.items()
        if name in ("Markdown", "reStructuredText")
    )
    if doc_loc == 0:
        return [RiskItem(
            "weak_documentation", "medium",
            "No documentation files detected",
            "No README or other Markdown/RST documentation found in the repository.",
            "project", None,
        )]
    if doc_loc < 30:
        return [RiskItem(
            "weak_documentation", "low",
            "Minimal documentation",
            "Documentation exists but is very sparse (< 30 lines).",
            "project", None,
        )]
    return []


def _risks_ci(stack: StackInfo) -> list[RiskItem]:
    if not stack.has_ci:
        return [RiskItem(
            "no_ci_pipeline", "high",
            "No CI/CD pipeline configuration found",
            "Neither .bitbucket-pipelines.yml nor .gitlab-ci.yml detected. "
            "Automated builds and tests are not configured.",
            "project", None,
        )]
    return []


def _risks_lockfile(fa: FileAnalysisResult, stack: StackInfo) -> list[RiskItem]:
    # Only flag if we have a package manager that typically produces lockfiles
    pm_with_lock = {"npm", "yarn", "pnpm", "poetry", "pipenv", "cargo", "bundler"}
    has_relevant_pm = any(
        any(p in pm for pm in stack.package_managers)
        for p in pm_with_lock
    )
    if has_relevant_pm and not fa.has_lockfile:
        return [RiskItem(
            "no_lockfile", "medium",
            "No dependency lockfile found",
            "Package manager detected but no lockfile (package-lock.json, poetry.lock, etc.). "
            "Dependency versions are not pinned, risking non-reproducible builds.",
            "project", None,
        )]
    return []


def _risks_oversized(cx: ComplexityResult) -> list[RiskItem]:
    risks = []
    if cx.files_above_threshold >= 20:
        risks.append(RiskItem(
            "oversized_file", "high",
            f"{cx.files_above_threshold} files exceed 500 lines",
            "A large number of oversized files indicates poor modularisation.",
            "project", None,
        ))
    elif cx.files_above_threshold >= 5:
        risks.append(RiskItem(
            "oversized_file", "medium",
            f"{cx.files_above_threshold} files exceed 500 lines",
            "Several files are too long and should be split.",
            "project", None,
        ))
    if cx.functions_above_threshold >= 10:
        risks.append(RiskItem(
            "oversized_function", "medium",
            f"{cx.functions_above_threshold} functions exceed 50 lines",
            "Long functions are harder to test and maintain.",
            "project", None,
        ))
    return risks


def _risks_concentration(developers: list[DeveloperStats]) -> list[RiskItem]:
    if not developers:
        return []
    total = sum(d.commit_count for d in developers)
    if total == 0:
        return []

    sorted_devs = sorted(developers, key=lambda d: d.commit_count, reverse=True)
    top1_share = sorted_devs[0].commit_count / total
    top2_share = sum(d.commit_count for d in sorted_devs[:2]) / total

    risks = []
    if top1_share > BUS_FACTOR_THRESHOLD:
        risks.append(RiskItem(
            "knowledge_concentration", "high",
            f"High knowledge concentration: {sorted_devs[0].canonical_username} owns {top1_share:.0%} of commits",
            "One developer dominates the commit history. Key-person dependency risk is critical.",
            "developer", sorted_devs[0].canonical_username,
        ))
    elif top2_share > BUS_FACTOR_TOP2_THRESHOLD and len(sorted_devs) >= 2:
        risks.append(RiskItem(
            "knowledge_concentration", "medium",
            f"Top 2 developers own {top2_share:.0%} of commits",
            "Commit history is heavily concentrated among two developers.",
            "project", None,
        ))
    return risks


def _risks_bus_factor(developers: list[DeveloperStats]) -> list[RiskItem]:
    if len(developers) <= 1:
        return [RiskItem(
            "low_bus_factor", "critical",
            "Bus factor = 1: only one contributor found",
            "The entire codebase knowledge is held by a single developer. "
            "Any absence would severely impact the project.",
            "project", None,
        )]
    if len(developers) == 2:
        return [RiskItem(
            "low_bus_factor", "medium",
            "Bus factor = 2: only two contributors",
            "Low contributor diversity increases key-person risk.",
            "project", None,
        )]
    return []


def _risks_mono_owner_language(developers: list[DeveloperStats]) -> list[RiskItem]:
    """Flag languages where one developer contributes > 80%."""
    lang_totals: dict[str, int] = {}
    lang_top: dict[str, tuple[str, int]] = {}

    for dev in developers:
        for lang, stats in dev.language_stats.items():
            files = stats[1]
            lang_totals[lang] = lang_totals.get(lang, 0) + files
            if lang not in lang_top or stats[1] > lang_top[lang][1]:
                lang_top[lang] = (dev.canonical_username, files)

    risks = []
    for lang, total in lang_totals.items():
        if total == 0:
            continue
        top_dev, top_files = lang_top.get(lang, ("", 0))
        share = top_files / total
        if share > MONO_OWNER_THRESHOLD and total >= 3:
            risks.append(RiskItem(
                "mono_owner_language", "medium",
                f"{top_dev} is sole owner of {lang} ({share:.0%} of changes)",
                f"Language {lang} is almost exclusively changed by one developer.",
                "language", lang,
            ))
    return risks


def _risks_mono_owner_module(developers: list[DeveloperStats]) -> list[RiskItem]:
    """Flag modules where one developer contributes > 80%."""
    mod_totals: dict[str, int] = {}
    mod_top: dict[str, tuple[str, int]] = {}

    for dev in developers:
        for mod, stats in dev.module_stats.items():
            files = stats[1]
            mod_totals[mod] = mod_totals.get(mod, 0) + files
            if mod not in mod_top or stats[1] > mod_top[mod][1]:
                mod_top[mod] = (dev.canonical_username, files)

    risks = []
    for mod, total in mod_totals.items():
        if total == 0:
            continue
        top_dev, top_files = mod_top.get(mod, ("", 0))
        share = top_files / total
        if share > MONO_OWNER_THRESHOLD and total >= 5:
            risks.append(RiskItem(
                "mono_owner_module", "medium",
                f"{top_dev} is sole owner of module '{mod}' ({share:.0%})",
                f"Module '{mod}' changes are almost entirely by one developer.",
                "module", mod,
            ))
    return risks


def _risks_high_complexity_module(cx: ComplexityResult) -> list[RiskItem]:
    """Flag top-level modules where average file LOC > 400 and ≥ 3 files."""
    module_files: dict[str, list[int]] = {}
    for path, loc in cx.top_large_files:
        parts = path.split("/")
        module = parts[0] if len(parts) > 1 else ""
        if module:
            module_files.setdefault(module, []).append(loc)

    risks = []
    for module, locs in module_files.items():
        if len(locs) >= 3 and (sum(locs) / len(locs)) > 400:
            risks.append(RiskItem(
                "high_complexity_module", "high",
                f"Module '{module}' has high average file size ({sum(locs) // len(locs)} LOC avg)",
                f"Module '{module}' contains {len(locs)} large files with average {sum(locs) // len(locs)} LOC. "
                "Consider splitting into smaller, focused modules.",
                "module", module,
            ))
    return risks


def _risks_orphan_module(
    developers: list[DeveloperStats],
    latest_commit_date: datetime | None = None,
) -> list[RiskItem]:
    """Flag modules with no commits in the last 6 months from any active developer."""
    if not developers or latest_commit_date is None:
        return []

    cutoff = latest_commit_date - timedelta(days=180)
    # Ensure cutoff is timezone-aware
    if cutoff.tzinfo is None:
        cutoff = cutoff.replace(tzinfo=timezone.utc)

    # Collect modules touched by developers active after cutoff
    active_modules: set[str] = set()
    for dev in developers:
        last = dev.last_commit_at
        if last is None:
            continue
        if last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)
        if last >= cutoff:
            active_modules.update(dev.module_stats.keys())

    # All modules across all developers
    all_modules: set[str] = set()
    for dev in developers:
        all_modules.update(dev.module_stats.keys())

    risks = []
    for module in all_modules - active_modules:
        if not module:
            continue
        risks.append(RiskItem(
            "orphan_module", "medium",
            f"Module '{module}' has no commits in the last 6 months",
            f"No active developer has touched module '{module}' recently. "
            "It may be abandoned or stale.",
            "module", module,
        ))
    return risks

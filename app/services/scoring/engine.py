from __future__ import annotations
from dataclasses import dataclass, field
import json

from app.services.analysis.file_analyzer import FileAnalysisResult
from app.services.analysis.stack_detector import StackInfo
from app.services.analysis.complexity import ComplexityResult
from app.services.git_analytics.contributor_aggregator import DeveloperStats


@dataclass
class DomainScore:
    domain: str
    score: float  # 0–100
    details: dict = field(default_factory=dict)

    def details_json(self) -> str:
        return json.dumps(self.details)


@dataclass
class ScorecardResult:
    code_quality: DomainScore
    test_quality: DomainScore
    doc_quality: DomainScore
    delivery_quality: DomainScore
    maintainability: DomainScore
    overall: DomainScore

    def all_domains(self) -> list[DomainScore]:
        return [
            self.code_quality,
            self.test_quality,
            self.doc_quality,
            self.delivery_quality,
            self.maintainability,
            self.overall,
        ]


def compute_scorecard(
    file_result: FileAnalysisResult,
    stack: StackInfo,
    complexity: ComplexityResult,
    developers: list[DeveloperStats],
) -> ScorecardResult:
    cq = _score_code_quality(file_result, complexity, stack)
    tq = _score_test_quality(file_result)
    dq = _score_doc_quality(file_result)
    dlq = _score_delivery_quality(stack)
    maint = _score_maintainability(file_result, complexity, developers)

    overall_score = round(
        cq.score * 0.25
        + tq.score * 0.20
        + dq.score * 0.15
        + dlq.score * 0.20
        + maint.score * 0.20,
        1,
    )
    overall = DomainScore("overall", overall_score, {"formula": "weighted average"})

    return ScorecardResult(cq, tq, dq, dlq, maint, overall)


# ── Code Quality ────────────────────────────────────────────────────────────

def _score_code_quality(fa: FileAnalysisResult, cx: ComplexityResult, stack: StackInfo) -> DomainScore:
    score = 100.0
    details: dict = {}

    # Penalty for large files
    if cx.files_above_threshold > 0:
        penalty = min(30, cx.files_above_threshold * 5)
        score -= penalty
        details["large_files_penalty"] = penalty
        details["large_files_count"] = cx.files_above_threshold

    # Penalty for large functions
    if cx.functions_above_threshold > 0:
        penalty = min(20, cx.functions_above_threshold * 3)
        score -= penalty
        details["large_functions_penalty"] = penalty

    # Average LOC bonus/penalty
    avg = fa.avg_file_loc
    if avg > 300:
        score -= 10
        details["avg_loc_penalty"] = 10
    elif avg < 150:
        details["avg_loc_ok"] = True

    # Bonus for linters / formatters
    if stack.linters:
        score += 10
        details["linters"] = stack.linters
    if stack.formatters:
        score += 5
        details["formatters"] = stack.formatters

    score = max(0.0, min(100.0, score))
    return DomainScore("code_quality", round(score, 1), details)


# ── Test Quality ─────────────────────────────────────────────────────────────

def _score_test_quality(fa: FileAnalysisResult) -> DomainScore:
    score = 0.0
    details: dict = {}

    if fa.file_count_test > 0:
        score += 50
        details["has_tests"] = True

        # Ratio bonus
        total_src = fa.file_count_source + fa.file_count_test
        if total_src > 0:
            ratio = fa.file_count_test / total_src
            details["test_ratio"] = round(ratio, 2)
            if ratio >= 0.3:
                score += 30
            elif ratio >= 0.15:
                score += 15
            elif ratio >= 0.05:
                score += 5
    else:
        details["has_tests"] = False

    score = max(0.0, min(100.0, score))
    return DomainScore("test_quality", round(score, 1), details)


# ── Documentation Quality ────────────────────────────────────────────────────

def _score_doc_quality(fa: FileAnalysisResult) -> DomainScore:
    score = 0.0
    details: dict = {}

    docs_lower = [p.lower() for p in fa.doc_files_found]

    # +20: README present
    has_readme = any("readme" in d for d in docs_lower)
    if has_readme:
        score += 20
        details["has_readme"] = True

    # +15: Install / Setup instructions
    has_install = any(
        kw in d for d in docs_lower
        for kw in ("install", "setup")
    )
    if has_install:
        score += 15
        details["has_install_docs"] = True

    # +15: Architecture docs (ARCHITECTURE.md, adr/, docs/architecture*)
    has_arch = any(
        kw in d for d in docs_lower
        for kw in ("architecture", "adr")
    )
    if has_arch:
        score += 15
        details["has_architecture_docs"] = True

    # +15: CHANGELOG / HISTORY
    has_changelog = any(
        kw in d for d in docs_lower
        for kw in ("changelog", "history")
    )
    if has_changelog:
        score += 15
        details["has_changelog"] = True

    # +10: Operational docs (runbook, ops)
    has_runbook = any("runbook" in d for d in docs_lower)
    if has_runbook:
        score += 10
        details["has_runbook"] = True

    if not docs_lower:
        details["has_docs"] = False

    # Normalise 75 → 100
    if score > 0:
        score = min(100.0, score / 75 * 100)

    score = max(0.0, min(100.0, score))
    return DomainScore("doc_quality", round(score, 1), details)


# ── Delivery Quality ─────────────────────────────────────────────────────────

def _score_delivery_quality(stack: StackInfo) -> DomainScore:
    score = 0.0
    details: dict = {}

    if stack.has_ci:
        score += 40
        details["has_ci"] = True
        details["ci_provider"] = stack.ci_provider
    if stack.has_docker:
        score += 30
        details["has_docker"] = True
    if stack.has_kubernetes or stack.has_helm or stack.has_terraform:
        score += 20
        details["has_infra_as_code"] = True

    score = max(0.0, min(100.0, score))
    return DomainScore("delivery_quality", round(score, 1), details)


# ── Maintainability ──────────────────────────────────────────────────────────

def _score_maintainability(
    fa: FileAnalysisResult,
    cx: ComplexityResult,
    devs: list[DeveloperStats],
) -> DomainScore:
    score = 60.0  # base
    details: dict = {}

    # Penalize if single developer
    if len(devs) == 1:
        score -= 20
        details["single_dev"] = True
    elif len(devs) >= 3:
        score += 10
        details["multi_dev"] = True

    # Penalize concentration: if top dev has > 70% commits
    if devs:
        total_commits = sum(d.commit_count for d in devs)
        if total_commits > 0:
            top_share = max(d.commit_count for d in devs) / total_commits
            details["top_dev_share"] = round(top_share, 2)
            if top_share > 0.80:
                score -= 20
            elif top_share > 0.60:
                score -= 10

    # Penalize complexity
    if cx.files_above_threshold > 10:
        score -= 10
        details["high_complexity"] = True

    # Bonus for tests
    if fa.file_count_test > 0:
        score += 10

    score = max(0.0, min(100.0, score))
    return DomainScore("maintainability", round(score, 1), details)

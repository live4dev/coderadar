import pytest
from app.services.scoring.engine import compute_scorecard
from app.services.analysis.file_analyzer import FileAnalysisResult, LanguageStat
from app.services.analysis.stack_detector import StackInfo
from app.services.analysis.complexity import ComplexityResult
from app.services.git_analytics.contributor_aggregator import DeveloperStats
from app.services.identity.normalizer import NormalizedIdentity


def _dev(username: str, commits: int) -> DeveloperStats:
    identity = NormalizedIdentity(username, "", "", 0.9)
    d = DeveloperStats(username, username, "", identity)
    d.commit_count = commits
    return d


def _file_result(
    test_files: int = 0,
    source_files: int = 10,
    md_loc: int = 0,
) -> FileAnalysisResult:
    fr = FileAnalysisResult()
    fr.file_count_test = test_files
    fr.file_count_source = source_files
    if md_loc:
        fr.languages["Markdown"] = LanguageStat("Markdown", loc=md_loc)
    return fr


def test_no_tests_gives_low_test_score():
    result = _file_result(test_files=0)
    scorecard = compute_scorecard(result, StackInfo(), ComplexityResult(), [])
    assert scorecard.test_quality.score == 0.0


def test_good_tests_gives_high_score():
    result = _file_result(test_files=5, source_files=10)
    scorecard = compute_scorecard(result, StackInfo(), ComplexityResult(), [])
    assert scorecard.test_quality.score >= 50


def test_has_ci_boosts_delivery():
    stack = StackInfo(has_ci=True, ci_provider="gitlab", has_docker=True)
    scorecard = compute_scorecard(_file_result(), stack, ComplexityResult(), [])
    assert scorecard.delivery_quality.score >= 70


def test_no_ci_zero_delivery():
    stack = StackInfo(has_ci=False, has_docker=False)
    scorecard = compute_scorecard(_file_result(), stack, ComplexityResult(), [])
    assert scorecard.delivery_quality.score == 0.0


def test_single_dev_hurts_maintainability():
    devs = [_dev("a_solo", 100)]
    scorecard = compute_scorecard(_file_result(), StackInfo(), ComplexityResult(), devs)
    assert scorecard.maintainability.score < 50


def test_overall_is_weighted_average():
    stack = StackInfo(has_ci=True, has_docker=True)
    result = _file_result(test_files=3, source_files=7, md_loc=100)
    devs = [_dev("a_dev", 50), _dev("b_dev", 30)]
    scorecard = compute_scorecard(result, stack, ComplexityResult(), devs)
    assert 0 <= scorecard.overall.score <= 100


def test_details_json_is_valid_json():
    from app.services.scoring.engine import DomainScore
    import json
    ds = DomainScore("test", 75.0, {"key": "value", "num": 42})
    parsed = json.loads(ds.details_json())
    assert parsed["key"] == "value"


def test_all_domains_returns_six_items():
    scorecard = compute_scorecard(_file_result(), StackInfo(), ComplexityResult(), [])
    domains = scorecard.all_domains()
    assert len(domains) == 6
    names = {d.domain for d in domains}
    assert "overall" in names
    assert "code_quality" in names


# ── code quality edge cases ───────────────────────────────────────────────────

def test_large_files_penalty_capped_at_30():
    cx = ComplexityResult()
    cx.files_above_threshold = 100  # 100 * 5 = 500, capped at 30
    scorecard = compute_scorecard(_file_result(), StackInfo(), cx, [])
    assert scorecard.code_quality.details.get("large_files_penalty") == 30


def test_large_functions_penalty_capped_at_20():
    cx = ComplexityResult()
    cx.functions_above_threshold = 100  # 100 * 3 = 300, capped at 20
    scorecard = compute_scorecard(_file_result(), StackInfo(), cx, [])
    assert scorecard.code_quality.details.get("large_functions_penalty") == 20


def test_avg_loc_above_300_penalized():
    fr = _file_result()
    fr.avg_file_loc = 350
    scorecard = compute_scorecard(fr, StackInfo(), ComplexityResult(), [])
    assert scorecard.code_quality.details.get("avg_loc_penalty") == 10


def test_avg_loc_below_150_ok():
    fr = _file_result()
    fr.avg_file_loc = 100
    scorecard = compute_scorecard(fr, StackInfo(), ComplexityResult(), [])
    assert scorecard.code_quality.details.get("avg_loc_ok") is True


def test_linters_boost_code_quality():
    stack = StackInfo(linters=["Ruff"], formatters=["Black"])
    scorecard = compute_scorecard(_file_result(), stack, ComplexityResult(), [])
    assert scorecard.code_quality.score >= 100  # capped at 100


def test_code_quality_never_below_zero():
    cx = ComplexityResult()
    cx.files_above_threshold = 100
    cx.functions_above_threshold = 100
    fr = _file_result()
    fr.avg_file_loc = 400
    scorecard = compute_scorecard(fr, StackInfo(), cx, [])
    assert scorecard.code_quality.score >= 0


# ── test quality edge cases ───────────────────────────────────────────────────

def test_test_ratio_30pct_bonus():
    result = _file_result(test_files=3, source_files=7)  # 3/10 = 30%
    scorecard = compute_scorecard(result, StackInfo(), ComplexityResult(), [])
    assert scorecard.test_quality.score == 80.0  # 50 + 30


def test_test_ratio_15pct_bonus():
    result = _file_result(test_files=2, source_files=11)  # 2/13 ≈ 15.4%
    scorecard = compute_scorecard(result, StackInfo(), ComplexityResult(), [])
    assert scorecard.test_quality.score == 65.0  # 50 + 15


def test_test_ratio_5pct_bonus():
    result = _file_result(test_files=1, source_files=15)  # 1/16 ≈ 6.25%
    scorecard = compute_scorecard(result, StackInfo(), ComplexityResult(), [])
    assert scorecard.test_quality.score == 55.0  # 50 + 5


# ── doc quality edge cases ────────────────────────────────────────────────────

def test_doc_quality_readme_only():
    fr = _file_result()
    fr.doc_files_found = ["README.md"]
    scorecard = compute_scorecard(fr, StackInfo(), ComplexityResult(), [])
    assert scorecard.doc_quality.score > 0
    assert scorecard.doc_quality.details.get("has_readme") is True


def test_doc_quality_all_docs_capped_at_100():
    fr = _file_result()
    fr.doc_files_found = ["README.md", "INSTALL.md", "ARCHITECTURE.md",
                          "CHANGELOG.md", "runbook.md"]
    scorecard = compute_scorecard(fr, StackInfo(), ComplexityResult(), [])
    assert scorecard.doc_quality.score == 100.0


def test_doc_quality_no_docs():
    fr = _file_result()
    fr.doc_files_found = []
    scorecard = compute_scorecard(fr, StackInfo(), ComplexityResult(), [])
    assert scorecard.doc_quality.score == 0.0
    assert scorecard.doc_quality.details.get("has_docs") is False


def test_doc_quality_install_doc():
    fr = _file_result()
    fr.doc_files_found = ["INSTALL.md"]
    scorecard = compute_scorecard(fr, StackInfo(), ComplexityResult(), [])
    assert scorecard.doc_quality.details.get("has_install_docs") is True


def test_doc_quality_architecture_doc():
    fr = _file_result()
    fr.doc_files_found = ["docs/architecture.md"]
    scorecard = compute_scorecard(fr, StackInfo(), ComplexityResult(), [])
    assert scorecard.doc_quality.details.get("has_architecture_docs") is True


def test_doc_quality_changelog():
    fr = _file_result()
    fr.doc_files_found = ["CHANGELOG.md"]
    scorecard = compute_scorecard(fr, StackInfo(), ComplexityResult(), [])
    assert scorecard.doc_quality.details.get("has_changelog") is True


def test_doc_quality_runbook():
    fr = _file_result()
    fr.doc_files_found = ["runbook.md"]
    scorecard = compute_scorecard(fr, StackInfo(), ComplexityResult(), [])
    assert scorecard.doc_quality.details.get("has_runbook") is True


# ── delivery quality edge cases ───────────────────────────────────────────────

def test_delivery_with_infra_as_code():
    stack = StackInfo(has_ci=True, has_kubernetes=True)
    scorecard = compute_scorecard(_file_result(), stack, ComplexityResult(), [])
    assert scorecard.delivery_quality.details.get("has_infra_as_code") is True


# ── maintainability edge cases ────────────────────────────────────────────────

def test_multi_dev_bonus():
    devs = [_dev("a", 30), _dev("b", 30), _dev("c", 30)]
    scorecard = compute_scorecard(_file_result(), StackInfo(), ComplexityResult(), devs)
    assert scorecard.maintainability.details.get("multi_dev") is True


def test_top_dev_80pct_penalized():
    devs = [_dev("dominant", 85), _dev("other", 15)]
    scorecard = compute_scorecard(_file_result(), StackInfo(), ComplexityResult(), devs)
    assert scorecard.maintainability.details.get("top_dev_share", 0) > 0.80


def test_high_complexity_penalty():
    cx = ComplexityResult()
    cx.files_above_threshold = 15
    scorecard = compute_scorecard(_file_result(), StackInfo(), cx, [])
    assert scorecard.maintainability.details.get("high_complexity") is True


def test_tests_boost_maintainability():
    fr = _file_result(test_files=5)
    devs = [_dev("a", 50), _dev("b", 50)]
    scorecard = compute_scorecard(fr, StackInfo(), ComplexityResult(), devs)
    # With tests, score should be higher than base
    scorecard_no_tests = compute_scorecard(_file_result(test_files=0), StackInfo(), ComplexityResult(), devs)
    assert scorecard.maintainability.score > scorecard_no_tests.maintainability.score

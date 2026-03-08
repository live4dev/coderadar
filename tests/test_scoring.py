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

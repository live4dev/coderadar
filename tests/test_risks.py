import pytest
from app.services.risks.engine import detect_risks
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


def _base_file_result() -> FileAnalysisResult:
    fr = FileAnalysisResult()
    fr.file_count_source = 10
    fr.languages["Markdown"] = LanguageStat("Markdown", loc=200)
    fr.has_lockfile = True
    return fr


def test_no_tests_risk():
    fr = _base_file_result()
    fr.file_count_test = 0
    risks = detect_risks(fr, StackInfo(has_ci=True), ComplexityResult(), [_dev("a", 10)])
    types = [r.risk_type for r in risks]
    assert "no_tests" in types


def test_no_ci_risk():
    fr = _base_file_result()
    fr.file_count_test = 5
    risks = detect_risks(fr, StackInfo(has_ci=False), ComplexityResult(), [_dev("a", 10)])
    types = [r.risk_type for r in risks]
    assert "no_ci_pipeline" in types


def test_bus_factor_1_critical():
    fr = _base_file_result()
    fr.file_count_test = 5
    devs = [_dev("solo", 100)]
    risks = detect_risks(fr, StackInfo(has_ci=True), ComplexityResult(), devs)
    bus = [r for r in risks if r.risk_type == "low_bus_factor"]
    assert bus
    assert bus[0].severity == "critical"


def test_knowledge_concentration_high():
    devs = [_dev("dominant", 90), _dev("other", 10)]
    fr = _base_file_result()
    fr.file_count_test = 5
    risks = detect_risks(fr, StackInfo(has_ci=True), ComplexityResult(), devs)
    conc = [r for r in risks if r.risk_type == "knowledge_concentration"]
    assert conc
    assert conc[0].severity == "high"


def test_no_docs_risk():
    fr = FileAnalysisResult()
    fr.file_count_source = 10
    fr.file_count_test = 3
    risks = detect_risks(fr, StackInfo(has_ci=True), ComplexityResult(), [_dev("a", 5), _dev("b", 3)])
    types = [r.risk_type for r in risks]
    assert "weak_documentation" in types


def test_clean_project_no_critical_risks():
    fr = _base_file_result()
    fr.file_count_test = 5
    devs = [_dev("a", 40), _dev("b", 30), _dev("c", 20)]
    risks = detect_risks(fr, StackInfo(has_ci=True, has_docker=True), ComplexityResult(), devs)
    critical = [r for r in risks if r.severity == "critical"]
    assert not critical

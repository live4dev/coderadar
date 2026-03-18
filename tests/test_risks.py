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


def test_low_test_ratio_medium_risk():
    fr = _base_file_result()
    fr.file_count_test = 1
    fr.file_count_source = 100  # ratio < 5%
    risks = detect_risks(fr, StackInfo(has_ci=True), ComplexityResult(), [_dev("a", 10)])
    types = {r.risk_type for r in risks}
    assert "no_tests" in types
    no_test = next(r for r in risks if r.risk_type == "no_tests")
    assert no_test.severity == "medium"


def test_minimal_docs_low_risk():
    fr = FileAnalysisResult()
    fr.file_count_source = 10
    fr.file_count_test = 3
    fr.languages["Markdown"] = LanguageStat("Markdown", loc=15)  # < 30 lines
    fr.has_lockfile = True
    risks = detect_risks(fr, StackInfo(has_ci=True), ComplexityResult(), [_dev("a", 5), _dev("b", 3)])
    doc_risks = [r for r in risks if r.risk_type == "weak_documentation"]
    assert doc_risks
    assert doc_risks[0].severity == "low"


def test_no_lockfile_risk_when_package_manager():
    fr = _base_file_result()
    fr.file_count_test = 5
    fr.has_lockfile = False
    stack = StackInfo(has_ci=True, package_managers=["npm"])
    risks = detect_risks(fr, stack, ComplexityResult(), [_dev("a", 5), _dev("b", 5)])
    types = {r.risk_type for r in risks}
    assert "no_lockfile" in types


def test_no_lockfile_risk_absent_without_package_manager():
    fr = _base_file_result()
    fr.file_count_test = 5
    fr.has_lockfile = False
    stack = StackInfo(has_ci=True, package_managers=["pip"])  # pip doesn't produce lockfiles
    risks = detect_risks(fr, stack, ComplexityResult(), [_dev("a", 5), _dev("b", 5)])
    types = {r.risk_type for r in risks}
    assert "no_lockfile" not in types


def test_many_oversized_files_high_risk():
    fr = _base_file_result()
    fr.file_count_test = 5
    cx = ComplexityResult()
    cx.files_above_threshold = 25
    risks = detect_risks(fr, StackInfo(has_ci=True), cx, [_dev("a", 5), _dev("b", 5)])
    oversized = [r for r in risks if r.risk_type == "oversized_file"]
    assert oversized
    assert oversized[0].severity == "high"


def test_some_oversized_files_medium_risk():
    fr = _base_file_result()
    fr.file_count_test = 5
    cx = ComplexityResult()
    cx.files_above_threshold = 7
    risks = detect_risks(fr, StackInfo(has_ci=True), cx, [_dev("a", 5), _dev("b", 5)])
    oversized = [r for r in risks if r.risk_type == "oversized_file"]
    assert oversized
    assert oversized[0].severity == "medium"


def test_many_oversized_functions_risk():
    fr = _base_file_result()
    fr.file_count_test = 5
    cx = ComplexityResult()
    cx.functions_above_threshold = 15
    risks = detect_risks(fr, StackInfo(has_ci=True), cx, [_dev("a", 5), _dev("b", 5)])
    types = {r.risk_type for r in risks}
    assert "oversized_function" in types


def test_bus_factor_2_medium():
    fr = _base_file_result()
    fr.file_count_test = 5
    devs = [_dev("a", 60), _dev("b", 40)]
    risks = detect_risks(fr, StackInfo(has_ci=True), ComplexityResult(), devs)
    bus = [r for r in risks if r.risk_type == "low_bus_factor"]
    assert bus
    assert bus[0].severity == "medium"


def test_top2_concentration_medium():
    devs = [_dev("a", 50), _dev("b", 45), _dev("c", 5)]
    fr = _base_file_result()
    fr.file_count_test = 5
    risks = detect_risks(fr, StackInfo(has_ci=True), ComplexityResult(), devs)
    conc = [r for r in risks if r.risk_type == "knowledge_concentration"]
    assert conc
    assert conc[0].severity == "medium"


def test_mono_owner_language_risk():
    from app.services.git_analytics.contributor_aggregator import DeveloperStats
    from app.services.identity.normalizer import NormalizedIdentity
    from collections import defaultdict

    identity = NormalizedIdentity("alice", "", "", 0.9)
    dev = DeveloperStats("alice", "Alice", "a@x.com", identity)
    dev.commit_count = 10
    # Alice touched Python 8 times, Bob touched Python 1 time
    dev.language_stats["Python"] = [8, 8, 100, 10]

    identity2 = NormalizedIdentity("bob", "", "", 0.9)
    dev2 = DeveloperStats("bob", "Bob", "b@x.com", identity2)
    dev2.commit_count = 2
    dev2.language_stats["Python"] = [1, 1, 10, 2]

    fr = _base_file_result()
    fr.file_count_test = 5
    risks = detect_risks(fr, StackInfo(has_ci=True), ComplexityResult(), [dev, dev2])
    types = {r.risk_type for r in risks}
    assert "mono_owner_language" in types


def test_mono_owner_module_risk():
    from app.services.git_analytics.contributor_aggregator import DeveloperStats
    from app.services.identity.normalizer import NormalizedIdentity

    identity = NormalizedIdentity("alice", "", "", 0.9)
    dev = DeveloperStats("alice", "Alice", "a@x.com", identity)
    dev.commit_count = 10
    dev.module_stats["payments"] = [9, 9, 100]

    identity2 = NormalizedIdentity("bob", "", "", 0.9)
    dev2 = DeveloperStats("bob", "Bob", "b@x.com", identity2)
    dev2.commit_count = 2
    dev2.module_stats["payments"] = [1, 1, 10]

    fr = _base_file_result()
    fr.file_count_test = 5
    risks = detect_risks(fr, StackInfo(has_ci=True), ComplexityResult(), [dev, dev2])
    types = {r.risk_type for r in risks}
    assert "mono_owner_module" in types


def test_high_complexity_module_risk():
    cx = ComplexityResult()
    cx.top_large_files = [
        ("payments/billing.py", 800),
        ("payments/invoice.py", 600),
        ("payments/refund.py", 550),
    ]
    fr = _base_file_result()
    fr.file_count_test = 5
    risks = detect_risks(fr, StackInfo(has_ci=True), cx, [_dev("a", 5), _dev("b", 5)])
    types = {r.risk_type for r in risks}
    assert "high_complexity_module" in types


def test_orphan_module_risk():
    from datetime import datetime, timezone, timedelta
    from app.services.git_analytics.contributor_aggregator import DeveloperStats
    from app.services.identity.normalizer import NormalizedIdentity

    now = datetime.now(timezone.utc)
    old_date = now - timedelta(days=200)

    identity = NormalizedIdentity("alice", "", "", 0.9)
    dev = DeveloperStats("alice", "Alice", "a@x.com", identity)
    dev.commit_count = 10
    dev.last_commit_at = old_date
    dev.module_stats["legacy_module"] = [5, 5, 50]

    fr = _base_file_result()
    fr.file_count_test = 5
    risks = detect_risks(fr, StackInfo(has_ci=True), ComplexityResult(), [dev], latest_commit_date=now)
    types = {r.risk_type for r in risks}
    assert "orphan_module" in types


def test_orphan_module_not_triggered_without_date():
    from app.services.git_analytics.contributor_aggregator import DeveloperStats
    from app.services.identity.normalizer import NormalizedIdentity

    identity = NormalizedIdentity("alice", "", "", 0.9)
    dev = DeveloperStats("alice", "Alice", "a@x.com", identity)
    dev.commit_count = 10
    dev.module_stats["some_module"] = [5, 5, 50]

    fr = _base_file_result()
    fr.file_count_test = 5
    risks = detect_risks(fr, StackInfo(has_ci=True), ComplexityResult(), [dev], latest_commit_date=None)
    types = {r.risk_type for r in risks}
    assert "orphan_module" not in types

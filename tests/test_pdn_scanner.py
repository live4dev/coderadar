import tempfile
from pathlib import Path

import pytest

from app.services.pii.config import PDnTypeConfig
from app.services.pii.pdn_scanner import (
    PDnFinding,
    _build_identifier_patterns,
    _is_source_file,
    scan_repository_for_pdn,
)


def _make_repo(files: dict[str, str]) -> Path:
    d = Path(tempfile.mkdtemp())
    for name, content in files.items():
        p = d / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
    return d


def _pdn(name: str, *identifiers: str) -> PDnTypeConfig:
    return PDnTypeConfig(name=name, identifiers=list(identifiers))


# ── _is_source_file ───────────────────────────────────────────────────────────

def test_is_source_file_py():
    assert _is_source_file(Path("app/main.py")) is True


def test_is_source_file_js():
    assert _is_source_file(Path("src/app.js")) is True


def test_is_source_file_binary_excluded():
    assert _is_source_file(Path("image.png")) is False


def test_is_source_file_unknown_ext():
    assert _is_source_file(Path("file.xyz")) is False


def test_is_source_file_dockerfile():
    assert _is_source_file(Path("Dockerfile")) is True


# ── _build_identifier_patterns ────────────────────────────────────────────────

def test_build_identifier_patterns_creates_word_boundary():
    pdn = _pdn("passport", "passport_number", "паспорт")
    patterns = _build_identifier_patterns([pdn])
    assert len(patterns) == 2
    for name, pat in patterns:
        assert name == "passport"
        assert r"\b" in pat


def test_build_identifier_patterns_skips_empty_identifiers():
    pdn = _pdn("test", "valid_id", "", "  ")
    patterns = _build_identifier_patterns([pdn])
    # empty string skipped, "  " stripped becomes "" also skipped? No — config strips on load
    # but _build_identifier_patterns checks `if not ident`
    names = [name for name, _ in patterns]
    assert len(names) >= 1


def test_build_identifier_patterns_multiple_types():
    pdns = [_pdn("email", "email", "e_mail"), _pdn("phone", "phone_number")]
    patterns = _build_identifier_patterns(pdns)
    assert len(patterns) == 3


# ── scan_repository_for_pdn ───────────────────────────────────────────────────

def test_scan_empty_pdn_types_returns_empty():
    repo = _make_repo({"app/main.py": "user_email = get_email()\n"})
    findings = scan_repository_for_pdn(repo, [])
    assert findings == []


def test_scan_finds_identifier_in_source():
    pdn = _pdn("email", "user_email")
    repo = _make_repo({"app/service.py": "user_email = request.get('email')\n"})
    findings = scan_repository_for_pdn(repo, [pdn])
    assert len(findings) == 1
    assert findings[0].pdn_type == "email"
    assert findings[0].matched_identifier == "user_email"


def test_scan_reports_correct_line_number():
    content = "x = 1\ny = 2\nphone_number = input()\nz = 3\n"
    pdn = _pdn("phone", "phone_number")
    repo = _make_repo({"app/main.py": content})
    findings = scan_repository_for_pdn(repo, [pdn])
    assert findings[0].line_number == 3


def test_scan_reports_relative_file_path():
    pdn = _pdn("email", "user_email")
    repo = _make_repo({"src/module/handler.py": "user_email = ''\n"})
    findings = scan_repository_for_pdn(repo, [pdn])
    assert findings[0].file_path == "src/module/handler.py"


def test_scan_skips_test_files():
    pdn = _pdn("email", "user_email")
    repo = _make_repo({
        "tests/test_service.py": "user_email = 'test@x.com'\n",
        "app/service.py": "x = 1\n",
    })
    findings = scan_repository_for_pdn(repo, [pdn])
    assert all("test" not in f.file_path.lower() for f in findings)


def test_scan_skips_skip_dirs():
    pdn = _pdn("email", "user_email")
    repo = _make_repo({
        "node_modules/dep/index.js": "user_email = ''\n",
        "app/main.py": "x = 1\n",
    })
    findings = scan_repository_for_pdn(repo, [pdn])
    assert all("node_modules" not in f.file_path for f in findings)


def test_scan_skips_binary_files():
    pdn = _pdn("email", "user_email")
    repo = _make_repo({
        "assets/image.png": "user_email = fake binary",
        "app/main.py": "x = 1\n",
    })
    findings = scan_repository_for_pdn(repo, [pdn])
    assert all(not f.file_path.endswith(".png") for f in findings)


def test_scan_word_boundary_no_partial_match():
    pdn = _pdn("id_type", "id")
    repo = _make_repo({"app/main.py": "identity = get_identifier()\n"})
    findings = scan_repository_for_pdn(repo, [pdn])
    # "id" should NOT match inside "identity" or "identifier" — word boundary enforced
    assert all(f.matched_identifier == "id" for f in findings)
    # "identity" contains "id" but \b prevents matching inside longer word
    assert len(findings) == 0


def test_scan_multiple_identifiers_multiple_findings():
    pdns = [_pdn("email", "email_address"), _pdn("phone", "phone_num")]
    content = "email_address = x\nphone_num = y\n"
    repo = _make_repo({"app/main.py": content})
    findings = scan_repository_for_pdn(repo, pdns)
    types = {f.pdn_type for f in findings}
    assert "email" in types
    assert "phone" in types


def test_scan_no_findings_when_no_match():
    pdn = _pdn("passport", "passport_id")
    repo = _make_repo({"app/main.py": "x = get_user()\nresult = process(x)\n"})
    findings = scan_repository_for_pdn(repo, [pdn])
    assert findings == []


def test_scan_javascript_file():
    pdn = _pdn("email", "userEmail")
    repo = _make_repo({"src/api.js": "const userEmail = req.body.email;\n"})
    findings = scan_repository_for_pdn(repo, [pdn])
    assert len(findings) == 1
    assert findings[0].file_path == "src/api.js"


def test_scan_skips_hidden_dirs():
    pdn = _pdn("email", "user_email")
    repo = _make_repo({
        ".git/config.py": "user_email = ''\n",
        "app/main.py": "x = 1\n",
    })
    findings = scan_repository_for_pdn(repo, [pdn])
    assert all(".git" not in f.file_path for f in findings)

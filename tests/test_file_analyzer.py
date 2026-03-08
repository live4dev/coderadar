from pathlib import Path
import pytest

from app.services.analysis.file_analyzer import analyze_files, SKIP_DIRS


# ── Helpers ───────────────────────────────────────────────────────────────────

def _write(path: Path, content: str = "x\n") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


# ── Basic counts ──────────────────────────────────────────────────────────────

def test_counts_source_files(tmp_path):
    _write(tmp_path / "main.py", "a\nb\nc\n")
    _write(tmp_path / "utils.py", "d\ne\n")
    fr = analyze_files(tmp_path)
    assert fr.file_count_source == 2
    assert fr.total_loc == 5


def test_counts_test_files(tmp_path):
    _write(tmp_path / "app.py")
    _write(tmp_path / "tests" / "test_app.py")
    fr = analyze_files(tmp_path)
    assert fr.file_count_test == 1
    assert fr.file_count_source == 1


def test_counts_config_files(tmp_path):
    _write(tmp_path / "src" / "main.py")
    _write(tmp_path / "config.yaml")
    fr = analyze_files(tmp_path)
    assert fr.file_count_config == 1


# ── Exclusions ────────────────────────────────────────────────────────────────

def test_skips_node_modules(tmp_path):
    _write(tmp_path / "node_modules" / "lib" / "index.js")
    _write(tmp_path / "src" / "app.js")
    fr = analyze_files(tmp_path)
    assert fr.file_count_source == 1


def test_skips_venv(tmp_path):
    _write(tmp_path / ".venv" / "lib" / "python3.12" / "os.py")
    _write(tmp_path / "app.py")
    fr = analyze_files(tmp_path)
    assert fr.file_count_source == 1


def test_skips_hidden_dirs(tmp_path):
    _write(tmp_path / ".hidden" / "secret.py")
    _write(tmp_path / "visible.py")
    fr = analyze_files(tmp_path)
    assert fr.file_count_source == 1


# ── Binary files ─────────────────────────────────────────────────────────────

def test_binary_extensions_ignored(tmp_path):
    (tmp_path / "image.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    _write(tmp_path / "app.py")
    fr = analyze_files(tmp_path)
    assert fr.file_count_source == 1
    assert "Python" in fr.languages


# ── Lockfile detection ────────────────────────────────────────────────────────

def test_detects_lockfile(tmp_path):
    _write(tmp_path / "package-lock.json")
    _write(tmp_path / "app.js")
    fr = analyze_files(tmp_path)
    assert fr.has_lockfile is True
    assert "package-lock.json" in fr.lockfiles_found


def test_no_lockfile(tmp_path):
    _write(tmp_path / "app.py")
    fr = analyze_files(tmp_path)
    assert fr.has_lockfile is False


# ── Doc file detection ────────────────────────────────────────────────────────

def test_detects_readme(tmp_path):
    _write(tmp_path / "README.md", "# My project\n")
    fr = analyze_files(tmp_path)
    assert any("readme" in p.lower() for p in fr.doc_files_found)


def test_detects_changelog(tmp_path):
    _write(tmp_path / "CHANGELOG.md", "## v1.0\n")
    fr = analyze_files(tmp_path)
    assert any("changelog" in p.lower() for p in fr.doc_files_found)


def test_no_doc_files(tmp_path):
    _write(tmp_path / "app.py")
    fr = analyze_files(tmp_path)
    assert fr.doc_files_found == []


# ── Language stats ────────────────────────────────────────────────────────────

def test_multi_language(tmp_path):
    _write(tmp_path / "app.py", "a\n" * 10)
    _write(tmp_path / "index.ts", "b\n" * 5)
    fr = analyze_files(tmp_path)
    assert "Python" in fr.languages
    assert "TypeScript" in fr.languages
    assert fr.languages["Python"].loc == 10
    assert fr.languages["TypeScript"].loc == 5


def test_language_percentages_sum_to_100(tmp_path):
    _write(tmp_path / "a.py", "x\n" * 50)
    _write(tmp_path / "b.js", "y\n" * 50)
    fr = analyze_files(tmp_path)
    total_pct = sum(s.percentage for s in fr.languages.values())
    assert abs(total_pct - 100.0) < 0.1

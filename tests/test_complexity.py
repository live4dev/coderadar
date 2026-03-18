import tempfile
from pathlib import Path

import pytest

from app.services.analysis.complexity import (
    _ext_to_lang,
    analyze_complexity,
)


def _make_repo(files: dict[str, str]) -> Path:
    d = Path(tempfile.mkdtemp())
    for name, content in files.items():
        p = d / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)
    return d


# ── _ext_to_lang ──────────────────────────────────────────────────────────────

def test_ext_to_lang_known_and_available():
    assert _ext_to_lang(".py", {"Python"}) == "Python"


def test_ext_to_lang_known_but_not_available():
    assert _ext_to_lang(".py", {"JavaScript"}) is None


def test_ext_to_lang_unknown_extension():
    assert _ext_to_lang(".xyz", {"Python"}) is None


def test_ext_to_lang_empty_available():
    assert _ext_to_lang(".go", set()) is None


# ── analyze_complexity — basics ───────────────────────────────────────────────

def test_empty_repo_returns_zero():
    repo = _make_repo({})
    result = analyze_complexity(repo, {"Python": object()})
    assert result.files_above_threshold == 0
    assert result.functions_above_threshold == 0
    assert result.approximate_fan_out == 0
    assert result.top_large_files == []


def test_no_languages_skips_all_files():
    repo = _make_repo({"main.py": "x = 1\n"})
    result = analyze_complexity(repo, {})
    assert result.files_above_threshold == 0


def test_non_matching_extension_skipped():
    repo = _make_repo({"file.xyz": "line\n" * 600})
    result = analyze_complexity(repo, {"Python": object()})
    assert result.files_above_threshold == 0


# ── large file detection ──────────────────────────────────────────────────────

def test_large_file_detected():
    content = "\n".join(f"x_{i} = {i}" for i in range(600))
    repo = _make_repo({"big.py": content})
    result = analyze_complexity(repo, {"Python": object()})
    assert result.files_above_threshold == 1
    assert result.top_large_files[0][0] == "big.py"
    assert result.top_large_files[0][1] >= 500


def test_small_file_not_flagged():
    content = "x = 1\n" * 10
    repo = _make_repo({"small.py": content})
    result = analyze_complexity(repo, {"Python": object()})
    assert result.files_above_threshold == 0


def test_top_large_files_sorted_descending():
    files = {
        "medium.py": "x = 1\n" * 510,
        "large.py": "x = 1\n" * 700,
    }
    repo = _make_repo(files)
    result = analyze_complexity(repo, {"Python": object()})
    sizes = [s for _, s in result.top_large_files]
    assert sizes == sorted(sizes, reverse=True)


def test_top_large_files_capped_at_10():
    files = {f"file_{i}.py": "x = 1\n" * (510 + i) for i in range(15)}
    repo = _make_repo(files)
    result = analyze_complexity(repo, {"Python": object()})
    assert len(result.top_large_files) == 10


# ── large function detection ──────────────────────────────────────────────────

def test_large_python_function_flagged():
    lines = ["def big_func():"] + ["    x = 1"] * 55 + ["def small():"] + ["    pass"]
    repo = _make_repo({"main.py": "\n".join(lines)})
    result = analyze_complexity(repo, {"Python": object()})
    assert result.functions_above_threshold >= 1


def test_small_python_function_not_flagged():
    lines = ["def small():"] + ["    x = 1"] * 10
    repo = _make_repo({"main.py": "\n".join(lines)})
    result = analyze_complexity(repo, {"Python": object()})
    assert result.functions_above_threshold == 0


def test_large_javascript_function_flagged():
    lines = ["function bigFunc() {"] + ["    let x = 1;"] * 55 + ["}"]
    repo = _make_repo({"app.js": "\n".join(lines)})
    result = analyze_complexity(repo, {"JavaScript": object()})
    assert result.functions_above_threshold >= 1


def test_go_function_detected():
    lines = ["func bigFunc() {"] + ["    x := 1"] * 55 + ["}"]
    repo = _make_repo({"main.go": "\n".join(lines)})
    result = analyze_complexity(repo, {"Go": object()})
    assert result.functions_above_threshold >= 1


# ── fan-out / import counting ─────────────────────────────────────────────────

def test_fan_out_counts_unique_python_imports():
    content = "import os\nimport sys\nfrom pathlib import Path\nimport os\n"
    repo = _make_repo({"main.py": content})
    result = analyze_complexity(repo, {"Python": object()})
    # 3 unique import lines (duplicate `import os` same after strip[:80])
    assert result.approximate_fan_out >= 2


def test_fan_out_counts_js_imports():
    content = 'import { foo } from "bar";\nimport { baz } from "qux";\n'
    repo = _make_repo({"app.js": content})
    result = analyze_complexity(repo, {"JavaScript": object()})
    assert result.approximate_fan_out >= 2


# ── skip directories ──────────────────────────────────────────────────────────

def test_git_dir_skipped():
    files = {
        ".git/large.py": "x = 1\n" * 600,
        "src/main.py": "x = 1\n",
    }
    repo = _make_repo(files)
    result = analyze_complexity(repo, {"Python": object()})
    assert result.files_above_threshold == 0


def test_node_modules_skipped():
    files = {
        "node_modules/dep.py": "x = 1\n" * 600,
        "app.py": "x = 1\n",
    }
    repo = _make_repo(files)
    result = analyze_complexity(repo, {"Python": object()})
    assert result.files_above_threshold == 0


def test_venv_skipped():
    files = {
        ".venv/lib/module.py": "x = 1\n" * 600,
        "main.py": "x = 1\n",
    }
    repo = _make_repo(files)
    result = analyze_complexity(repo, {"Python": object()})
    assert result.files_above_threshold == 0

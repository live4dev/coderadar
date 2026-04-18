# Plan: Split Python 2 and Python 3 as Distinct Languages

## Context
CodeRadar currently maps all `.py` files to a single language name `"Python"`. This todo item asks for Python 2 and Python 3 to be tracked as separate languages so scans accurately reflect which Python version a project uses. No DB migration is needed — language names are created dynamically on first scan.

## Detection Strategy
Detection happens at the **project level** (not per-file) in priority order:
1. `.python-version` file — content starting with "2" → Python 2
2. `pyproject.toml` — `python = "^2..."` or `"~2.7"` pattern
3. `setup.py` / `setup.cfg` — `python_requires` with `<3` upper bound
4. Shebang lines in first ≤10 `.py` files — `python2` in shebang
5. Default → Python 3

## Files to Modify

### 1. `app/services/analysis/file_analyzer.py`
- Add `import re` at top
- Add `detect_python_version(repo_root: Path) -> str` after `detect_language()`
- In `analyze_files()`, before percentage computation, rename `"Python"` key to versioned name

### 2. `app/services/analysis/stack_detector.py`
- In `_detect_project_type()`, add `"Python 2"` and `"Python 3"` to the `has_backend` check

### 3. `app/services/analysis/complexity.py`
- Add `"Python 2"` and `"Python 3"` entries to `_FUNC_PATTERNS` and `_IMPORT_PATTERNS`
- Add fallback in `_ext_to_lang()` for versioned Python names

### 4. `app/services/git_analytics/git_parser.py`
- Add `python_lang_name: str = "Python"` parameter to `parse_git_log_v2()`
- Substitute when `detect_language()` returns `"Python"`

### 5. `app/services/git_analytics/contributor_aggregator.py`
- Add `python_lang_name: str = "Python"` parameter to `aggregate_contributions()`
- Pass through to `parse_git_log_v2()`

### 6. `app/services/scanning/orchestrator.py`
- After `analyze_files()`, resolve `python_lang_name` from `file_result.languages`
- Pass to `aggregate_contributions()`

## Verification
1. Scan a Python 3 repo → languages shows "Python 3", not "Python"
2. Scan a Python 2 repo (`.python-version: 2.7.18`) → shows "Python 2"
3. Non-Python repos unaffected
4. `scan.primary_language` set correctly
5. Developer language contributions show versioned name
6. `pytest tests/` passes with no regressions

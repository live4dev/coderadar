from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
import re

LARGE_FILE_THRESHOLD = 500      # lines
LARGE_FUNCTION_THRESHOLD = 50   # lines


@dataclass
class ComplexityResult:
    files_above_threshold: int = 0
    functions_above_threshold: int = 0
    top_large_files: list[tuple[str, int]] = field(default_factory=list)
    approximate_fan_out: int = 0  # unique imports/requires across codebase


# Simple regex-based function detectors per language
_FUNC_PATTERNS: dict[str, re.Pattern] = {
    "Python": re.compile(r"^\s{0,4}(async\s+)?def\s+\w+"),
    "Python 2": re.compile(r"^\s{0,4}(async\s+)?def\s+\w+"),
    "Python 3": re.compile(r"^\s{0,4}(async\s+)?def\s+\w+"),
    "JavaScript": re.compile(r"(function\s+\w+|\w+\s*[:=]\s*(async\s*)?(function|\([^)]*\)\s*=>))"),
    "TypeScript": re.compile(r"(function\s+\w+|\w+\s*[:=]\s*(async\s*)?(function|\([^)]*\)\s*=>))"),
    "Java": re.compile(r"(public|private|protected|static|final|\s)+[\w<>\[\]]+\s+\w+\s*\("),
    "Go": re.compile(r"^func\s+"),
    "Kotlin": re.compile(r"^\s*(override\s+)?fun\s+\w+"),
    "Rust": re.compile(r"^\s*(pub\s+)?(async\s+)?fn\s+\w+"),
    "Ruby": re.compile(r"^\s*def\s+\w+"),
    "C#": re.compile(r"(public|private|protected|internal|static|virtual|override|async|\s)+[\w<>\[\]?]+\s+\w+\s*\("),
}

_IMPORT_PATTERNS: dict[str, re.Pattern] = {
    "Python": re.compile(r"^\s*(import|from)\s+\w+"),
    "Python 2": re.compile(r"^\s*(import|from)\s+\w+"),
    "Python 3": re.compile(r"^\s*(import|from)\s+\w+"),
    "JavaScript": re.compile(r"(import .+ from|require\s*\()"),
    "TypeScript": re.compile(r"(import .+ from|require\s*\()"),
    "Go": re.compile(r'^\s*"[\w./-]+"'),
    "Java": re.compile(r"^import\s+[\w.]+"),
}


def analyze_complexity(repo_root: Path, languages: dict[str, object]) -> ComplexityResult:
    result = ComplexityResult()
    lang_names = set(languages.keys()) if languages else set()
    imports_seen: set[str] = set()

    for path in repo_root.rglob("*"):
        if not path.is_file():
            continue
        # Skip noise dirs
        parts = path.relative_to(repo_root).parts
        if any(p in {".git", "node_modules", ".venv", "venv", "__pycache__", "dist", "build"} for p in parts):
            continue

        suffix = path.suffix.lower()
        lang = _ext_to_lang(suffix, lang_names)
        if not lang:
            continue

        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue

        total_lines = len(lines)
        rel_path = str(path.relative_to(repo_root))

        if total_lines >= LARGE_FILE_THRESHOLD:
            result.files_above_threshold += 1
            result.top_large_files.append((rel_path, total_lines))

        # Count functions and measure their rough length
        if lang in _FUNC_PATTERNS:
            pattern = _FUNC_PATTERNS[lang]
            func_starts: list[int] = []
            for i, line in enumerate(lines):
                if pattern.search(line):
                    func_starts.append(i)

            for j, start in enumerate(func_starts):
                end = func_starts[j + 1] if j + 1 < len(func_starts) else total_lines
                if end - start >= LARGE_FUNCTION_THRESHOLD:
                    result.functions_above_threshold += 1

        # Collect imports for fan-out
        if lang in _IMPORT_PATTERNS:
            imp_pat = _IMPORT_PATTERNS[lang]
            for line in lines:
                if imp_pat.search(line):
                    imports_seen.add(line.strip()[:80])

    result.top_large_files.sort(key=lambda x: x[1], reverse=True)
    result.top_large_files = result.top_large_files[:10]
    result.approximate_fan_out = len(imports_seen)

    return result


_SUFFIX_LANG: dict[str, str] = {
    ".py": "Python", ".js": "JavaScript", ".ts": "TypeScript",
    ".jsx": "JavaScript", ".tsx": "TypeScript",
    ".java": "Java", ".kt": "Kotlin", ".go": "Go",
    ".rs": "Rust", ".rb": "Ruby", ".cs": "C#",
}


def _ext_to_lang(suffix: str, available: set[str]) -> str | None:
    lang = _SUFFIX_LANG.get(suffix)
    if lang is None:
        return None
    if lang in available:
        return lang
    if lang == "Python":
        for versioned in ("Python 2", "Python 3"):
            if versioned in available:
                return versioned
    return None

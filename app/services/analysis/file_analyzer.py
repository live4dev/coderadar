from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
from collections import defaultdict
import re

# Directories to skip entirely
SKIP_DIRS = {
    ".git", "node_modules", ".venv", "venv", "__pycache__",
    "dist", "build", ".next", ".nuxt", "target", "vendor",
    ".gradle", ".idea", ".vscode", "coverage", ".pytest_cache",
    ".mypy_cache", ".tox", "eggs", ".eggs", "htmlcov", ".cache",
}

# Extensions → language name
EXTENSION_LANG_MAP: dict[str, str] = {
    ".py": "Python",
    ".js": "JavaScript",
    ".ts": "TypeScript",
    ".jsx": "JavaScript",
    ".tsx": "TypeScript",
    ".java": "Java",
    ".kt": "Kotlin",
    ".go": "Go",
    ".rs": "Rust",
    ".rb": "Ruby",
    ".php": "PHP",
    ".cs": "C#",
    ".cpp": "C++",
    ".cc": "C++",
    ".cxx": "C++",
    ".c": "C",
    ".h": "C",
    ".scala": "Scala",
    ".swift": "Swift",
    ".sh": "Shell",
    ".bash": "Shell",
    ".zsh": "Shell",
    ".sql": "SQL",
    ".html": "HTML",
    ".css": "CSS",
    ".scss": "SCSS",
    ".sass": "SCSS",
    ".vue": "Vue",
    ".svelte": "Svelte",
    ".ex": "Elixir",
    ".exs": "Elixir",
    ".erl": "Erlang",
    ".lua": "Lua",
    ".r": "R",
    ".R": "R",
    ".dart": "Dart",
    ".tf": "Terraform",
    ".hcl": "HCL",
    ".yaml": "YAML",
    ".yml": "YAML",
    ".json": "JSON",
    ".toml": "TOML",
    ".xml": "XML",
    ".proto": "Protobuf",
    ".graphql": "GraphQL",
    ".gql": "GraphQL",
    ".md": "Markdown",
    ".rst": "reStructuredText",
    ".dockerfile": "Dockerfile",
}

# Known filenames that map to languages regardless of extension
FILENAME_LANG_MAP: dict[str, str] = {
    "Dockerfile": "Dockerfile",
    "Makefile": "Makefile",
    "Jenkinsfile": "Groovy",
    "Gemfile": "Ruby",
    "Rakefile": "Ruby",
}

BINARY_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".ico", ".svg",
    ".pdf", ".zip", ".tar", ".gz", ".bz2", ".7z", ".rar",
    ".exe", ".dll", ".so", ".dylib", ".bin", ".wasm",
    ".mp3", ".mp4", ".wav", ".avi", ".mov", ".ttf", ".woff", ".woff2",
    ".lock",  # lock files — counted separately, not as source
}

TEST_PATTERNS = {"test", "tests", "spec", "specs", "__tests__", "_test"}
CONFIG_EXTENSIONS = {".yaml", ".yml", ".json", ".toml", ".ini", ".cfg", ".conf", ".env"}

LARGE_FILE_LOC_THRESHOLD = 500


@dataclass
class LanguageStat:
    name: str
    file_count: int = 0
    loc: int = 0
    percentage: float = 0.0


@dataclass
class FileAnalysisResult:
    total_files: int = 0
    total_loc: int = 0
    size_bytes: int = 0
    file_count_source: int = 0
    file_count_test: int = 0
    file_count_config: int = 0
    dir_count: int = 0
    large_files_count: int = 0
    avg_file_loc: float = 0.0
    languages: dict[str, LanguageStat] = field(default_factory=dict)
    top_large_files: list[tuple[str, int]] = field(default_factory=list)  # (path, loc)
    has_lockfile: bool = False
    lockfiles_found: list[str] = field(default_factory=list)
    doc_files_found: list[str] = field(default_factory=list)


LOCKFILES = {
    "package-lock.json", "yarn.lock", "pnpm-lock.yaml",
    "poetry.lock", "Pipfile.lock", "Gemfile.lock",
    "go.sum", "Cargo.lock", "composer.lock",
}

# Doc filenames/prefixes to track for scoring
_DOC_STEMS = {"readme", "changelog", "history", "architecture", "adr", "install", "setup", "runbook", "contributing"}


def _is_doc_file(path: Path) -> bool:
    stem = path.stem.lower()
    return stem in _DOC_STEMS or any(stem.startswith(d) for d in _DOC_STEMS)


def count_lines(path: Path) -> int:
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            return sum(1 for _ in f)
    except OSError:
        return 0


def detect_language(path: Path) -> str | None:
    if path.name in FILENAME_LANG_MAP:
        return FILENAME_LANG_MAP[path.name]
    ext = path.suffix.lower()
    if ext in BINARY_EXTENSIONS:
        return None
    return EXTENSION_LANG_MAP.get(ext)


def detect_python_version(repo_root: Path) -> str:
    """
    Inspect project-level config to determine Python 2 vs Python 3.
    Returns "Python 2" or "Python 3". Defaults to "Python 3".
    """
    # 1. .python-version
    pv = repo_root / ".python-version"
    if pv.is_file():
        try:
            content = pv.read_text(encoding="utf-8", errors="replace").strip()
            if content.startswith("2"):
                return "Python 2"
            return "Python 3"
        except OSError:
            pass

    # 2. pyproject.toml — python = "^2..." or "~2.7..."
    pyproject = repo_root / "pyproject.toml"
    if pyproject.is_file():
        try:
            text = pyproject.read_text(encoding="utf-8", errors="replace")
            if re.search(r'python\s*=\s*"[\^~]?2', text):
                return "Python 2"
        except OSError:
            pass

    # 3. setup.py / setup.cfg — python_requires with upper bound < 3
    for cfg_name in ("setup.py", "setup.cfg"):
        cfg = repo_root / cfg_name
        if cfg.is_file():
            try:
                text = cfg.read_text(encoding="utf-8", errors="replace")
                if re.search(r"python_requires\s*=\s*['\"][^'\"]*<\s*3", text):
                    return "Python 2"
            except OSError:
                pass

    # 4. Shebang lines in the first few .py files
    py_files_checked = 0
    for path in repo_root.rglob("*.py"):
        parts = path.relative_to(repo_root).parts
        if any(p in SKIP_DIRS or p.startswith(".") for p in parts[:-1]):
            continue
        try:
            with open(path, encoding="utf-8", errors="replace") as fh:
                first_line = fh.readline()
            if re.search(r"python2", first_line):
                return "Python 2"
        except OSError:
            pass
        py_files_checked += 1
        if py_files_checked >= 10:
            break

    return "Python 3"


def is_test_file(path: Path) -> bool:
    parts_lower = {p.lower() for p in path.parts}
    if parts_lower & TEST_PATTERNS:
        return True
    stem = path.stem.lower()
    return stem.startswith("test_") or stem.endswith("_test") or stem.endswith(".test") or stem.endswith(".spec")


def is_config_file(path: Path) -> bool:
    return path.suffix.lower() in CONFIG_EXTENSIONS


def analyze_files(repo_root: Path) -> FileAnalysisResult:
    result = FileAnalysisResult()
    lang_counts: dict[str, LanguageStat] = defaultdict(lambda: LanguageStat(name=""))
    loc_per_file: list[tuple[str, int]] = []
    total_locs: list[int] = []

    for item in repo_root.rglob("*"):
        # Skip hidden dirs and known noise dirs
        parts = item.relative_to(repo_root).parts
        if any(p in SKIP_DIRS or p.startswith(".") for p in parts[:-1]):
            continue
        if item.is_dir():
            if item.name not in SKIP_DIRS and not item.name.startswith("."):
                result.dir_count += 1
            continue

        if not item.is_file():
            continue

        result.total_files += 1
        result.size_bytes += item.stat().st_size

        # Lockfiles
        if item.name in LOCKFILES:
            result.has_lockfile = True
            result.lockfiles_found.append(item.name)
            continue

        # Doc files
        if _is_doc_file(item):
            result.doc_files_found.append(str(item.relative_to(repo_root)))

        lang = detect_language(item)
        if lang is None:
            continue

        loc = count_lines(item)
        result.total_loc += loc
        total_locs.append(loc)

        stat = lang_counts[lang]
        stat.name = lang
        stat.file_count += 1
        stat.loc += loc

        if loc >= LARGE_FILE_LOC_THRESHOLD:
            result.large_files_count += 1
            loc_per_file.append((str(item.relative_to(repo_root)), loc))

        if is_test_file(item):
            result.file_count_test += 1
        elif is_config_file(item):
            result.file_count_config += 1
        else:
            result.file_count_source += 1

    # Rename generic "Python" to versioned name
    if "Python" in lang_counts:
        python_lang_name = detect_python_version(repo_root)
        stat = lang_counts.pop("Python")
        stat.name = python_lang_name
        lang_counts[python_lang_name] = stat

    # Compute percentages
    total_lang_loc = sum(s.loc for s in lang_counts.values())
    for name, stat in lang_counts.items():
        stat.percentage = (stat.loc / total_lang_loc * 100) if total_lang_loc else 0
    result.languages = dict(lang_counts)

    # Top 10 largest files
    loc_per_file.sort(key=lambda x: x[1], reverse=True)
    result.top_large_files = loc_per_file[:10]

    # Average LOC per file
    if total_locs:
        result.avg_file_loc = sum(total_locs) / len(total_locs)

    return result

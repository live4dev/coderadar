"""Scan repository source files for personal data (PDn) identifiers from config."""
from __future__ import annotations
import re
from dataclasses import dataclass
from pathlib import Path

from app.core.logging import get_logger
from app.services.analysis.file_analyzer import (
    SKIP_DIRS,
    BINARY_EXTENSIONS,
    EXTENSION_LANG_MAP,
    FILENAME_LANG_MAP,
)
from app.services.pii.config import PDnTypeConfig

logger = get_logger(__name__)

# Skip files larger than this (bytes) to avoid reading huge generated/binary-like files
MAX_FILE_BYTES = 1 * 1024 * 1024  # 1 MB
# Max lines to scan per file
MAX_LINES_PER_FILE = 100_000


class _CommentStripper:
    """Stateful per-file comment splitter. Maintains block-comment / docstring state
    across successive calls to ``scan_line``.

    Splits each line into (code_part, comment_part):
    - Python/Ruby/Shell/YAML (hash-style): ``#`` to EOL, ``\"\"\"``/``'''`` docstrings
    - C-style (JS/TS/Java/Go/C/Rust/…): ``//`` to EOL, ``/* … */`` blocks
    - SQL: ``--`` to EOL, ``/* … */`` blocks
    - Other (Markdown, RST, plain text): full line returned as code, no comment part
    """

    _HASH_EXTS = frozenset({
        ".py", ".rb", ".sh", ".bash", ".zsh", ".yml", ".yaml", ".toml",
        ".r", ".coffee",
    })
    _C_STYLE_EXTS = frozenset({
        ".js", ".ts", ".jsx", ".tsx", ".java", ".go", ".c", ".cpp", ".cc",
        ".cxx", ".h", ".hpp", ".cs", ".rs", ".swift", ".kt", ".scala",
        ".php", ".dart", ".m",
    })
    _SQL_EXTS = frozenset({".sql"})

    def __init__(self, extension: str) -> None:
        ext = extension.lower()
        if ext in self._HASH_EXTS:
            self._style = "hash"
        elif ext in self._C_STYLE_EXTS:
            self._style = "c_style"
        elif ext in self._SQL_EXTS:
            self._style = "sql"
        else:
            self._style = "none"
        self._in_block_comment = False
        self._in_py_docstring: str | None = None

    def code_portion(self, line: str) -> str:
        """Return only the code part of *line* (comment stripped)."""
        return self.scan_line(line)[0]

    def scan_line(self, line: str) -> tuple[str, str]:
        """Return ``(code_part, comment_part)`` for *line*.

        For ``none``-style files (Markdown, RST, plain text, unknown) the
        full line is returned as code and comment is empty — the caller will
        scan it as a documentation line without any stripping.
        """
        raw = line.rstrip("\n")
        if self._style == "hash":
            return self._split_hash(raw)
        if self._style == "c_style":
            return self._split_c_style(raw)
        if self._style == "sql":
            return self._split_sql(raw)
        return raw, ""

    # ── hash-style (Python et al.) ────────────────────────────────────────────

    def _split_hash(self, s: str) -> tuple[str, str]:
        # Continuation of a multi-line docstring — whole line is comment/doc
        if self._in_py_docstring:
            end = s.find(self._in_py_docstring)
            if end != -1:
                self._in_py_docstring = None
                return s[end + 3:], s[:end + 3]
            return "", s

        i = 0
        while i < len(s):
            found_triple = False
            for q3 in ('"""', "'''"):
                if s[i:i + 3] == q3:
                    close = s.find(q3, i + 3)
                    if close != -1:
                        # Inline triple-quoted string — remove it and re-scan
                        s = s[:i] + s[close + 3:]
                        found_triple = True
                        break
                    else:
                        # Docstring opens here; rest of line is not code
                        self._in_py_docstring = q3
                        return s[:i], s[i:]
            if found_triple:
                continue  # re-check same index after the splice
            if s[i] == "#":
                return s[:i], s[i + 1:]
            i += 1
        return s, ""

    # ── C-style ───────────────────────────────────────────────────────────────

    def _split_c_style(self, s: str) -> tuple[str, str]:
        if self._in_block_comment:
            end = s.find("*/")
            if end == -1:
                return "", s
            self._in_block_comment = False
            tail_code, tail_comment = self._split_c_style(s[end + 2:])
            return tail_code, s[:end + 2] + tail_comment

        code: list[str] = []
        comment: list[str] = []
        i = 0
        while i < len(s):
            if s[i:i + 2] == "//":
                comment.append(s[i + 2:])
                break
            if s[i:i + 2] == "/*":
                end = s.find("*/", i + 2)
                if end == -1:
                    self._in_block_comment = True
                    comment.append(s[i + 2:])
                    break
                comment.append(s[i + 2:end])
                i = end + 2
                continue
            code.append(s[i])
            i += 1
        return "".join(code), "".join(comment)

    # ── SQL ───────────────────────────────────────────────────────────────────

    def _split_sql(self, s: str) -> tuple[str, str]:
        if self._in_block_comment:
            end = s.find("*/")
            if end == -1:
                return "", s
            self._in_block_comment = False
            s = s[end + 2:]

        comment_parts: list[str] = []

        bc = s.find("/*")
        if bc != -1:
            end = s.find("*/", bc + 2)
            if end == -1:
                self._in_block_comment = True
                comment_parts.append(s[bc + 2:])
                return s[:bc], "".join(comment_parts)
            comment_parts.append(s[bc + 2:end])
            s = s[:bc] + s[end + 2:]

        lc = s.find("--")
        if lc != -1:
            comment_parts.append(s[lc + 2:])
            return s[:lc], "".join(comment_parts)
        return s, "".join(comment_parts)


@dataclass
class PDnFinding:
    """A single PDn identifier match in source code."""
    pdn_type: str
    file_path: str
    line_number: int
    matched_identifier: str


# Documentation file extensions — skip entirely (scan variables, not docs)
_SKIP_DOC_EXTENSIONS = frozenset({".md", ".rst", ".txt", ".adoc", ".wiki"})


def _is_source_file(path: Path) -> bool:
    """True if file is a text source we should scan (same logic as file_analyzer)."""
    if path.name in FILENAME_LANG_MAP:
        return True
    ext = path.suffix.lower()
    if ext in BINARY_EXTENSIONS:
        return False
    return ext in EXTENSION_LANG_MAP


def _is_pdn_target(path: Path) -> bool:
    """True for source files, excluding documentation formats."""
    if path.suffix.lower() in _SKIP_DOC_EXTENSIONS:
        return False
    return _is_source_file(path)


def _build_identifier_patterns(
    pdn_types: list[PDnTypeConfig],
) -> list[tuple[str, str]]:
    """Build (pdn_type_name, regex_pattern) for each identifier. Word boundary."""
    result: list[tuple[str, str]] = []
    for t in pdn_types:
        for ident in t.identifiers:
            if not ident:
                continue
            escaped = re.escape(ident)
            # Word boundary: \b on both sides so "user_id" doesn't match "id" alone
            pattern = r"\b" + escaped + r"\b"
            result.append((t.name, pattern))
    return result


def scan_repository_for_pdn(
    repo_path: Path,
    pdn_types: list[PDnTypeConfig],
) -> list[PDnFinding]:
    """
    Scan repo_path for PDn identifiers. Uses same skip rules as file_analyzer.
    Returns list of findings (pdn_type, file_path relative to repo, line_number, matched_identifier).
    """
    if not pdn_types:
        logger.info("pdn_scan_skipped", reason="no_pdn_types_configured")
        return []

    patterns = _build_identifier_patterns(pdn_types)
    # Pre-compile regexes: (pdn_type, compiled_regex)
    compiled: list[tuple[str, re.Pattern[str]]] = []
    for name, pat in patterns:
        try:
            compiled.append((name, re.compile(pat)))
        except re.error:
            continue

    logger.info(
        "pdn_scan_started",
        repo_path=str(repo_path),
        pdn_types=len(pdn_types),
        patterns=len(compiled),
    )

    findings: list[PDnFinding] = []
    repo_path = repo_path.resolve()
    files_scanned = 0

    for item in repo_path.rglob("*"):
        parts = item.relative_to(repo_path).parts
        if any(p in SKIP_DIRS or p.startswith(".") for p in parts[:-1]):
            continue
        if item.is_dir() or not item.is_file():
            continue
        if not _is_pdn_target(item):
            continue
        try:
            if item.stat().st_size > MAX_FILE_BYTES:
                continue
        except OSError:
            continue

        rel_path = str(item.relative_to(repo_path))
        if "test" in rel_path.lower():
            continue
        try:
            stripper = _CommentStripper(item.suffix)
            with open(item, encoding="utf-8", errors="replace") as f:
                line_num = 0
                for line in f:
                    line_num += 1
                    if line_num > MAX_LINES_PER_FILE:
                        break
                    code_part, _comment_part = stripper.scan_line(line)
                    if not code_part.strip():
                        continue
                    for pdn_type, regex in compiled:
                        m = regex.search(code_part)
                        if m:
                            findings.append(
                                PDnFinding(
                                    pdn_type=pdn_type,
                                    file_path=rel_path,
                                    line_number=line_num,
                                    matched_identifier=m.group(0),
                                )
                            )
            files_scanned += 1
        except OSError:
            continue

    logger.info(
        "pdn_scan_finished",
        repo_path=str(repo_path),
        files_scanned=files_scanned,
        findings_count=len(findings),
    )
    return findings

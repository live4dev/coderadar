from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
import subprocess
import re

from app.core.config import settings
from app.services.analysis.file_analyzer import detect_language, SKIP_DIRS

# Unique ASCII separator — safe to use in git --format
_SEP = "CODERADAR_COMMIT_SEP"


@dataclass
class FileChange:
    path: str
    insertions: int
    deletions: int
    language: str | None


@dataclass
class CommitRecord:
    sha: str
    author_name: str
    author_email: str
    timestamp: datetime
    file_changes: list[FileChange] = field(default_factory=list)


def _run_git(repo_path: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo_path), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return result.stdout


def _clean_filepath(raw: str) -> str | None:
    """
    Normalise filepath from git numstat output.
    Handles rename patterns: `{old => new}/file.py` → `new/file.py`
    Returns None if filepath is unusable (contains null bytes, etc.)
    """
    if "\x00" in raw or "\ufffd" in raw:
        return None

    # Handle git rename: `src/{old_dir => new_dir}/file.py`
    raw = re.sub(r"\{[^}]* => ([^}]*)\}", r"\1", raw)
    # Handle simple rename: `old_file.py => new_file.py`
    if " => " in raw:
        raw = raw.split(" => ")[-1]

    raw = raw.strip()
    if not raw:
        return None
    return raw


def parse_git_log_v2(repo_path: Path) -> list[CommitRecord]:
    """
    Parse git log with --numstat.
    Each commit block is separated by _SEP on its own line.
    Format: SEP\\nSHA\\nAuthorName\\nAuthorEmail\\nISO-timestamp
    followed by blank line then numstat lines.
    Respects settings.git_history_scan_limit (0 = unlimited).
    """
    fmt = f"--format={_SEP}%n%H%n%aN%n%aE%n%aI"
    args: list[str] = ["log", fmt, "--numstat", "--no-merges"]
    limit = settings.git_history_scan_limit or 0
    if limit > 0:
        args.extend(["-n", str(limit)])
    raw = _run_git(repo_path, *args)

    commits: list[CommitRecord] = []
    blocks = raw.split(_SEP + "\n")

    for block in blocks:
        block = block.strip()
        if not block:
            continue

        lines = block.splitlines()
        # First 4 lines are header: sha, name, email, timestamp
        if len(lines) < 4:
            continue

        sha = lines[0].strip()
        author_name = lines[1].strip()
        author_email = lines[2].strip()
        ts_str = lines[3].strip()

        if not sha or len(sha) < 7:
            continue

        try:
            timestamp = datetime.fromisoformat(ts_str)
        except ValueError:
            continue

        commit = CommitRecord(sha, author_name, author_email, timestamp)

        for line in lines[4:]:
            line = line.strip()
            if not line:
                continue

            parts = line.split("\t")
            if len(parts) < 3:
                continue

            try:
                ins = int(parts[0]) if parts[0] != "-" else 0
                dels = int(parts[1]) if parts[1] != "-" else 0
            except ValueError:
                continue

            filepath = _clean_filepath(parts[2])
            if filepath is None:
                continue

            # Skip noise directories
            if any(segment in filepath.split("/") for segment in SKIP_DIRS):
                continue

            try:
                lang = detect_language(Path(filepath))
            except (ValueError, OSError):
                lang = None

            commit.file_changes.append(FileChange(filepath, ins, dels, lang))

        commits.append(commit)

    return commits


def get_head_sha(repo_path: Path) -> str:
    return _run_git(repo_path, "rev-parse", "HEAD").strip()

# Plan: Personal Data Scanner — Skip Documentation Files and Docstrings

## Context

The personal data scanner (`pdn_scanner.py`) currently scans all text-like files including Markdown, RST, plain-text docs, and similar documentation formats. It also explicitly adds `.txt`, `.adoc`, `.wiki` via `_DOC_EXTENSIONS`. The user wants findings to come only from actual source code variables, not from documentation files or docstrings.

Docstrings in Python are already excluded from the `code_part` by `_CommentStripper._split_hash` (they go to `comment_part`). The gap is documentation file types being scanned at all.

## Critical File

- [app/services/pii/pdn_scanner.py](app/services/pii/pdn_scanner.py)

## Changes

### 1. Define a set of documentation extensions to skip

In `pdn_scanner.py`, replace the current `_DOC_EXTENSIONS` (which *adds* doc files) with a `_SKIP_DOC_EXTENSIONS` set that *excludes* them:

```python
# Documentation file extensions — skip entirely (scan variables, not docs)
_SKIP_DOC_EXTENSIONS = frozenset({
    ".md", ".rst", ".txt", ".adoc", ".wiki",
})
```

### 2. Update `_is_pdn_target` to exclude documentation files

Change the function from:
```python
def _is_pdn_target(path: Path) -> bool:
    """True for source files AND plain documentation files."""
    return _is_source_file(path) or path.suffix.lower() in _DOC_EXTENSIONS
```

To:
```python
def _is_pdn_target(path: Path) -> bool:
    """True for source files, excluding documentation formats."""
    if path.suffix.lower() in _SKIP_DOC_EXTENSIONS:
        return False
    return _is_source_file(path)
```

This ensures `.md` and `.rst` (which are present in `EXTENSION_LANG_MAP`) are also excluded, in addition to the formerly-added `.txt`, `.adoc`, `.wiki`.

## What stays the same

- Python/Ruby/YAML docstrings: already stripped by `_CommentStripper._split_hash` — no change needed.
- C-style block comments (JSDoc, Javadoc): already stripped by `_split_c_style` — no change needed.
- SQL block/line comments: already stripped by `_split_sql` — no change needed.

## Verification

1. Run existing test suite: `pytest tests/test_pdn_scanner.py -v`
2. Manually verify: a `.md` file containing `email = "x"` should produce zero findings; a `.py` file with `email = "x"` outside a docstring should still produce a finding.

# Plan: Capture Commits from All Git Branches for Analytics

## Context

Currently, `parse_git_log_v2()` runs `git log --numstat --no-merges` without the `--all` flag. This means only commits reachable from the currently checked-out branch HEAD are captured during a scan. If a repo is scanned on `main`, feature-branch-only commits (not yet merged) are invisible to analytics.

The fix: add `--all` to the git log command. Git deduplicates by commit SHA across all refs automatically — no double-counting. After a `git clone`, all remote branches are already present as remote-tracking refs (`origin/*`), and `origin.fetch()` in `base.py` keeps them current. So `--all` immediately covers every branch without any additional fetching logic.

## Change

### `app/services/git_analytics/git_parser.py` — line 73

```python
# Before:
args: list[str] = ["log", fmt, "--numstat", "--no-merges"]

# After:
args: list[str] = ["log", fmt, "--numstat", "--no-merges", "--all"]
```

That is the only production code change.

## Notes on edge cases

- **`git_history_scan_limit`**: Already appends `-n <limit>`. With `--all`, the limit caps the N most recent commits across *all* branches — correct behavior, no change needed.
- **Duplicates**: Git deduplicates by SHA internally. A commit reachable from multiple branches appears exactly once in the output.
- **Re-scan safety**: `_persist_developers()` and `_persist_repo_daily_activity()` in `orchestrator.py` already use upsert-with-max-count, so re-scanning after this change is safe and additive.
- **Existing scan data**: Not retroactively changed. Only new/re-scans will reflect all branches.

## Test added

`tests/test_git_parser.py` — `test_parse_git_log_v2_uses_all_flag`

## Verification

1. Find a repo with feature branches containing commits not merged to `main`.
2. Scan it (branch: `main`).
3. Check `DeveloperContribution.commit_count` for a developer with feature-branch-only commits — it should now include those commits.
4. Alternatively: `git log --all --no-merges | wc -l` on the cloned repo should match the commit count stored after scanning.

"""
Unit tests for the pure inactivity-score helpers in:
  - scripts/tag_inactive_developers.py  (uses datetime objects)
  - scripts/tag_inactive_repositories.py (uses date objects)

Both scripts expose a `compute_inactivity_score` function with the same conceptual
formula:

    avg_interval  = span_days / max(active_days - 1, 1)
    recent_ratio  = recent_commits / max(avg_daily * WINDOW_DAYS, 1)  [clamped 0..1]
    score         = (days_since_last / avg_interval) * (1 - recent_ratio)

No database or network access is required.
"""
from datetime import date, datetime, timedelta, timezone

import pytest

from scripts.tag_inactive_developers import compute_inactivity_score as dev_score
from scripts.tag_inactive_repositories import compute_inactivity_score as repo_score


# ===========================================================================
# tag_inactive_developers — compute_inactivity_score(datetime, datetime, ...)
# ===========================================================================

def _dt(days_ago: int) -> datetime:
    """Return a timezone-aware datetime that is `days_ago` days before now."""
    return datetime.now(timezone.utc) - timedelta(days=days_ago)


class TestDevInactivityScore:
    def test_recently_active_developer_scores_below_2(self):
        # Last commit yesterday, first commit 365 days ago, active every ~2 days
        score, days = dev_score(
            first_commit_at=_dt(365),
            last_commit_at=_dt(1),
            active_days=180,
            commit_count=360,
            recent_commits=40,
        )
        assert score < 2.0
        assert days == 1

    def test_long_inactive_developer_scores_above_threshold(self):
        # Last commit 300 days ago, used to commit regularly, nothing recent
        score, days = dev_score(
            first_commit_at=_dt(730),
            last_commit_at=_dt(300),
            active_days=200,
            commit_count=400,
            recent_commits=0,
        )
        assert score >= 4.0
        assert days == 300

    def test_single_commit_developer_does_not_raise(self):
        # active_days=1 triggers the avg_interval < 1 fallback path
        score, days = dev_score(
            first_commit_at=_dt(90),
            last_commit_at=_dt(90),
            active_days=1,
            commit_count=1,
            recent_commits=0,
        )
        assert score >= 0.0
        assert days == 90

    def test_score_is_non_negative(self):
        # recent_ratio clamped at 1.0 ensures (1 - recent_ratio) >= 0
        score, _ = dev_score(
            first_commit_at=_dt(30),
            last_commit_at=_dt(1),
            active_days=30,
            commit_count=200,   # high commit count → avg_daily high
            recent_commits=500,  # more than avg predicts → clamped to 1.0
        )
        assert score >= 0.0

    def test_days_since_last_matches_expectation(self):
        _, days = dev_score(
            first_commit_at=_dt(500),
            last_commit_at=_dt(50),
            active_days=100,
            commit_count=200,
            recent_commits=0,
        )
        # Allow ±1 for wall-clock drift during test execution
        assert abs(days - 50) <= 1

    def test_naive_datetimes_handled_gracefully(self):
        # The function adds UTC tzinfo to naive datetimes internally
        naive_first = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=365)
        naive_last = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=200)
        score, days = dev_score(
            first_commit_at=naive_first,
            last_commit_at=naive_last,
            active_days=100,
            commit_count=200,
            recent_commits=0,
        )
        assert score >= 0.0
        assert abs(days - 200) <= 1

    def test_returns_two_element_tuple(self):
        result = dev_score(
            first_commit_at=_dt(100),
            last_commit_at=_dt(10),
            active_days=50,
            commit_count=100,
            recent_commits=5,
        )
        assert len(result) == 2

    def test_score_rounded_to_two_decimal_places(self):
        score, _ = dev_score(
            first_commit_at=_dt(200),
            last_commit_at=_dt(100),
            active_days=50,
            commit_count=100,
            recent_commits=0,
        )
        # round() to 2 dp means the score string has at most 2 decimal digits
        assert score == round(score, 2)


# ===========================================================================
# tag_inactive_repositories — compute_inactivity_score(date, date, ...)
# ===========================================================================

def _d(days_ago: int) -> date:
    """Return a date that is `days_ago` days before today."""
    return date.today() - timedelta(days=days_ago)


class TestRepoInactivityScore:
    def test_repository_with_recent_commits_scores_near_zero(self):
        # max_date == today → days_since_last == 0 → score == 0
        score, days = repo_score(
            max_date=date.today(),
            min_date=_d(365),
            active_days=180,
            total_commits=360,
            recent_commits=40,
        )
        assert score == 0.0
        assert days == 0

    def test_long_inactive_repo_scores_above_threshold(self):
        score, days = repo_score(
            max_date=_d(365),
            min_date=_d(730),
            active_days=200,
            total_commits=400,
            recent_commits=0,
        )
        assert score >= 4.0
        assert days == 365

    def test_single_active_day_does_not_raise(self):
        # active_days=1 → avg_interval < 1 → fallback to 1.0
        score, days = repo_score(
            max_date=_d(100),
            min_date=_d(100),
            active_days=1,
            total_commits=1,
            recent_commits=0,
        )
        assert score >= 0.0
        assert days == 100

    def test_score_is_non_negative(self):
        # recent_commits much higher than average → recent_ratio clamped at 1.0
        score, _ = repo_score(
            max_date=_d(1),
            min_date=_d(30),
            active_days=30,
            total_commits=30,
            recent_commits=9999,
        )
        assert score >= 0.0

    def test_days_since_last_correct(self):
        _, days = repo_score(
            max_date=_d(45),
            min_date=_d(500),
            active_days=100,
            total_commits=200,
            recent_commits=0,
        )
        assert days == 45

    def test_returns_two_element_tuple(self):
        result = repo_score(
            max_date=_d(50),
            min_date=_d(200),
            active_days=80,
            total_commits=160,
            recent_commits=5,
        )
        assert len(result) == 2

    def test_score_rounded_to_two_decimal_places(self):
        score, _ = repo_score(
            max_date=_d(100),
            min_date=_d(300),
            active_days=60,
            total_commits=120,
            recent_commits=0,
        )
        assert score == round(score, 2)

    def test_inactive_repo_above_developer_default_threshold(self):
        # Validate that a clearly stale repo would be caught with default threshold=4.0, min_days=90
        score, days = repo_score(
            max_date=_d(180),
            min_date=_d(1000),
            active_days=100,
            total_commits=200,
            recent_commits=0,
        )
        threshold = 4.0
        min_days = 90
        assert score >= threshold
        assert days >= min_days

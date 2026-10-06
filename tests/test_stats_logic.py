"""
Unit tests: pure logic, no database, no web server.

These are the fastest tests and cover the trickiest code (streaks and time zones), where bugs would quietly produce wrong metrics.
"""

from datetime import date, datetime, timezone

from stats import calculate_streaks, to_local_date

# Streaks
def test_no_activity_means_no_streaks():
    assert calculate_streaks(set(), date(2026, 10, 4)) == (0, 0)
    
def test_consecutive_days_form_a_streak():
    days = {date(2026, 10, 2), date(2026, 10, 3), date(2026, 10, 4)}
    assert calculate_streaks(days, today=date(2026, 10, 4)) == (3, 3)
    
def test_gap_reserts_the_streak():
    days = {
        date(2026, 9, 1), date(2026, 9, 2), date(2026, 9, 3), # 3-day run
        date(2026, 10, 3), date(2026, 10, 4), # 2-day run
    }
    current, longest = calculate_streaks(days, today=date(2026, 10, 4))
    assert current == 2
    assert longest == 3
    
def test_streak_survives_until_you_log_today():
    # Active yesterday and the day before, nothing yet today: current streak is 2, not 0.
    days = {date(2026, 10, 2), date(2026, 10, 3)}
    current, _ = calculate_streaks(days, today=date(2026, 10, 4))
    assert current == 2
    
def test_streak_breaks_after_a_missed_day():
    # Last activity was 2 days ago, so the current streak is broken.
    days = {date(2026, 10, 1), date(2026, 10, 2)}
    current, longest = calculate_streaks(days, today=date(2026, 10, 4))
    assert current == 0
    assert longest == 2
    
# Time zones (set to America/New_York in conftest.py)
def test_late_night_utc_counts_as_previous_local_day():
    # The real case from my data: 02:36 UTC on Oct 2 is 10:36 PM on Oct 1 in New York. It must count toward Oct 1.
    moment = datetime(2026, 10, 2, 2, 36, tzinfo=timezone.utc)
    assert to_local_date(moment) == date(2026, 10, 1)
    
def test_naive_datetime_is_treated_as_utc():
    # Some databases return timestamps without a time zone. They're stored as UTC, so they must be converted the same way as aware ones.
    naive = datetime(2026, 10, 2, 2, 36)
    assert to_local_date(naive) == date(2026, 10, 1)
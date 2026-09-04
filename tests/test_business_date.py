"""Phase 33 (DATE-01..DATE-04, DATE-08): the shared business-date primitives.

Covers the plan-33-06 foundation of VA-10 (timezone-independent period
bucketing), VA-11 (`business_date` never reaches the sync transport) and
VA-14 (a future date is refused in Russian, writing nothing).

No freezegun / time-machine (rejected in `.planning/research/STACK.md`):
every helper under test takes its timezone as an explicit argument, so the
fixtures are literal ISO strings and an explicit tz name, exactly the idiom
`tests/test_core.py:108-151` already uses for `local_day_bounds_utc`.
"""

from datetime import date
from pathlib import Path

from app.core import business_date_bounds, local_day_bounds_utc, local_today_iso

# The three timezones the bounds contract must behave identically under:
# one positive offset, one negative offset, and plain UTC.
_TIMEZONES = ("Europe/Moscow", "America/New_York", "UTC")

# The three modules `business_date` must never appear in (Pitfall 16 / VA-11).
_SYNC_MODULES = (
    "app/services/sync.py",
    "app/services/sync_client.py",
    "app/routes/sync.py",
)


def test_business_date_bounds_is_closed_inclusive():
    """The CLOSED contract: the LAST day of the range is INCLUDED.

    Every switched predicate reads `>= start` AND `<= end`. If one of them
    keeps the half-open `<` it inherited from `local_day_bounds_utc`, the
    range silently loses its final day — a one-day off-by-one across nine
    reports at once.
    """
    start, end = business_date_bounds(date(2026, 9, 1), date(2026, 9, 30))
    assert (start, end) == ("2026-09-01", "2026-09-30")
    # The upper bound is the last INCLUDED day, not the day after it.
    assert start <= "2026-09-30" <= end
    assert start <= "2026-09-01" <= end
    assert not (start <= "2026-10-01" <= end)
    assert not (start <= "2026-08-31" <= end)


def test_business_date_bounds_single_day():
    """A single-day period is a degenerate closed range: start == end."""
    assert business_date_bounds(date(2026, 9, 1), date(2026, 9, 1)) == (
        "2026-09-01",
        "2026-09-01",
    )


def test_business_date_bounds_ignores_timezone():
    """VA-10: a date-only value buckets identically at UTC+3, UTC−4 and UTC+0.

    The contrast is the whole point (Pitfall 14, sharpened). Comparing the
    same String(10) business date against `local_day_bounds_utc`'s UTC
    *timestamp* bounds happens to work at Europe/Moscow purely as a
    lexicographic accident, and DROPS THE ROW at America/New_York and at
    plain UTC. UTC is included explicitly: a UTC-only CI runner is otherwise
    the thing that would catch this, in production.
    """
    business_day = "2026-09-01"
    day = date(2026, 9, 1)

    start, end = business_date_bounds(day, day)
    for tz_name in _TIMEZONES:
        assert start <= business_day <= end, f"business_date_bounds broke at {tz_name}"

    # The old helper, on the same value, is not tz-independent at all.
    old_results = []
    for tz_name in _TIMEZONES:
        old_start, old_end = local_day_bounds_utc(day, day, tz_name)
        old_results.append(old_start <= business_day < old_end)
    assert old_results == [True, False, False], (
        "Pitfall 14 baseline changed: comparing a date-only value against "
        f"local_day_bounds_utc gave {old_results} for {_TIMEZONES}"
    )


def test_local_day_bounds_utc_still_half_open():
    """Guard: the created_at-only helper's contract did NOT change under us.

    36 test call sites across 6 files build `created_at` fixtures with it and
    pin its half-open upper bound. This phase adds a sibling; it does not
    touch this one.
    """
    start, end = local_day_bounds_utc(date(2026, 7, 10), date(2026, 7, 10), "Europe/Moscow")
    assert start == "2026-07-09T21:00:00+00:00"
    assert end == "2026-07-10T21:00:00+00:00"
    # 00:30 local on the NEXT day is excluded — half-open, never closed.
    assert not (start <= "2026-07-10T21:00:00+00:00" < end)


def test_local_today_iso_is_a_ten_char_iso_day():
    """The one definition of «today»: a bare ISO calendar day, no time part."""
    value = local_today_iso("Europe/Moscow")
    assert len(value) == 10
    assert date.fromisoformat(value).isoformat() == value


def test_local_today_iso_follows_the_timezone():
    """Different zones can legitimately disagree by one day — the tz is an argument.

    Whichever pair of zones is being compared, each result must be a valid
    calendar day and the two must never differ by more than a day.
    """
    moscow = date.fromisoformat(local_today_iso("Europe/Moscow"))
    new_york = date.fromisoformat(local_today_iso("America/New_York"))
    assert 0 <= (moscow - new_york).days <= 1


def test_business_date_absent_from_sync_layer():
    """VA-11 / Pitfall 16: `business_date` appears in NO sync module.

    The push cursor is `synced_at IS NULL` and the pull cursor covers the
    reference kinds only. If `business_date` ever appears in one of these
    three modules, someone has wired the ledger's MEANING into its
    TRANSPORT — which silently re-orders the sync queue by a value the
    operator can back-date at will.
    """
    offenders = []
    for rel_path in _SYNC_MODULES:
        path = Path(rel_path)
        assert path.exists(), f"sync module missing: {rel_path}"
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if "business_date" in line:
                offenders.append(f"{rel_path}:{lineno}: {line.strip()}")
    assert not offenders, "business_date leaked into the sync transport:\n" + "\n".join(
        offenders
    )

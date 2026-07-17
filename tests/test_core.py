"""Unit tests for app.core money helpers (WR-02/WR-03) and period math (D-02).

to_cents is the ONLY sanctioned conversion point for money input, so its
error contract (ValueError on any garbage) and rounding policy are pinned
here as executable documentation. local_day_bounds_utc is the ONLY helper
any report in Phase 6 uses for period math — its half-open contract is
pinned here too (D-02's mandatory correctness rule).
"""

from datetime import date

import pytest

from app.core import format_cents, local_day_bounds_utc, to_cents


def test_to_cents_accepts_comma_and_dot():
    assert to_cents("12,50") == 1250
    assert to_cents("12.50") == 1250
    assert to_cents("7") == 700
    assert to_cents("0") == 0


def test_to_cents_rounds_half_up():
    """WR-03: deliberate ROUND_HALF_UP policy — ties round away from zero."""
    assert to_cents("12,505") == 1251  # banker's rounding would give 1250
    assert to_cents("12,515") == 1252
    assert to_cents("-12,505") == -1251


@pytest.mark.parametrize(
    "bad",
    ["", "abc", "12,5,0", "inf", "-inf", "Infinity", "nan", "1e100000"],
)
def test_to_cents_raises_value_error_on_any_garbage(bad):
    """WR-02: documented contract — ValueError, never decimal.InvalidOperation."""
    with pytest.raises(ValueError):
        to_cents(bad)


def test_format_cents_display():
    assert format_cents(1250) == "12,50"
    assert format_cents(-305) == "-3,05"
    assert format_cents(0) == "0,00"


# --- Phase 22 Plan 02 (SALE-02/D-08/D-09): pin the accept-set sale-total.js
# must mirror. Characterization tests, NOT xfail — they assert already-
# shipped behavior, so the untestable JS parser has a stable, frozen
# contract to mirror (22-RESEARCH.md Pattern 2, verified by execution
# 2026-07-17; 22-UI-SPEC.md Interaction 15).


@pytest.mark.parametrize(
    ("text", "expected_cents"),
    [
        # Accepted by BOTH server and the JS mirror.
        ("7", 700),
        ("12,50", 1250),
        ("12.50", 1250),
        (".5", 50),
        ("5.", 500),
        (" 12,5 ", 1250),
        # WR-03: ROUND_HALF_UP ties away from zero, not banker's rounding.
        ("12.505", 1251),
    ],
)
def test_to_cents_accept_set_boundaries(text, expected_cents):
    assert to_cents(text) == expected_cents


@pytest.mark.parametrize(
    "bad",
    ["1 000", "12abc", "", "inf", "nan", "Infinity", "12,5,0"],
)
def test_to_cents_accept_set_rejects_both(bad):
    """Rejected by BOTH the server and the JS mirror."""
    with pytest.raises(ValueError):
        to_cents(bad)


def test_to_cents_accepts_more_than_the_js_mirror():
    """22-UI-SPEC.md Interaction 15: a deliberate, bounded divergence.

    `to_cents` accepts more than D-08's "comma-decimal, no space-thousands"
    characterisation implies — Decimal(str) also takes exponents, PEP-515
    underscores, signs, and Unicode digit scripts. `sale-total.js`'s regex
    deliberately rejects these into D-09's «итог неполный» marker bucket
    instead. A false «итог неполный» on one of these is harmless (advisory
    display only; no operator types an exponent into a price field) —
    whereas a WRONG NUMBER would not be. Byte-exact JS parity is not
    achievable in a regex and must not be attempted.
    """
    assert to_cents("1e3") == 100000
    assert to_cents("1_000") == 100000
    assert to_cents("+12.5") == 1250
    assert to_cents("１２") == 1200  # fullwidth "12"


def test_format_cents_mirror_contract():
    """The exact display shape the JS `formatCents` must reproduce."""
    assert format_cents(1250) == "12,50"
    assert format_cents(0) == "0,00"
    assert format_cents(5) == "0,05"
    assert format_cents(-1250) == "-12,50"


def test_local_day_bounds_utc_single_day_moscow():
    """D-02: single-day bounds are local midnight-to-midnight, converted to UTC.

    Moscow is UTC+3 with no DST, so local midnight of 2026-07-10 is
    2026-07-09T21:00:00+00:00, and the (half-open) upper bound is local
    midnight of the day AFTER, 2026-07-10T21:00:00+00:00.
    """
    start_iso, end_iso = local_day_bounds_utc(date(2026, 7, 10), date(2026, 7, 10), "Europe/Moscow")
    assert start_iso == "2026-07-09T21:00:00+00:00"
    assert end_iso == "2026-07-10T21:00:00+00:00"


def test_local_day_bounds_utc_evening_sale_within_local_day():
    """D-02: 23:30 local time on 2026-07-10 (20:30 UTC) is WITHIN that day's bounds.

    This is the exact evening-sale-near-midnight case D-02 exists to get
    right — also covers RESEARCH.md's Validation Architecture
    "test_local_day_bounds_utc_dst_boundary" entry (named for the
    UTC-rollover edge case it guards, even though Europe/Moscow does not
    currently observe DST).
    """
    start_iso, end_iso = local_day_bounds_utc(date(2026, 7, 10), date(2026, 7, 10), "Europe/Moscow")
    evening_sale_utc = "2026-07-10T20:30:00+00:00"
    assert start_iso <= evening_sale_utc < end_iso


def test_local_day_bounds_utc_next_local_day_excluded():
    """D-02: 00:30 local on 2026-07-11 (21:30 UTC the 10th) belongs to July 11, NOT July 10."""
    start_iso, end_iso = local_day_bounds_utc(date(2026, 7, 10), date(2026, 7, 10), "Europe/Moscow")
    next_local_day_sale_utc = "2026-07-10T21:30:00+00:00"
    assert not (start_iso <= next_local_day_sale_utc < end_iso)


def test_local_day_bounds_utc_week_range_is_half_open():
    """D-02: a 7-day Mon-Sun range's end_iso is local midnight of the day AFTER — never closed."""
    monday = date(2026, 7, 6)
    sunday = date(2026, 7, 12)
    start_iso, end_iso = local_day_bounds_utc(monday, sunday, "Europe/Moscow")
    next_monday_start_iso, _ = local_day_bounds_utc(
        date(2026, 7, 13), date(2026, 7, 13), "Europe/Moscow"
    )
    assert end_iso == next_monday_start_iso
    monday_start_iso, _ = local_day_bounds_utc(monday, monday, "Europe/Moscow")
    assert start_iso == monday_start_iso

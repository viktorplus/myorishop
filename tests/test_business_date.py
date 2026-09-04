"""Phase 33 (DATE-01..DATE-04, DATE-08): the shared business-date primitives.

Covers the plan-33-06 foundation of VA-10 (timezone-independent period
bucketing), VA-11 (`business_date` never reaches the sync transport) and
VA-14 (a future date is refused in Russian, writing nothing).

No freezegun / time-machine (rejected in `.planning/research/STACK.md`):
every helper under test takes its timezone as an explicit argument, so the
fixtures are literal ISO strings and an explicit tz name, exactly the idiom
`tests/test_core.py:108-151` already uses for `local_day_bounds_utc`.
"""

import json
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from app.config import settings
from app.core import business_date_bounds, local_day_bounds_utc, local_today_iso
from app.models import Operation
from app.services import merge
from app.services.ledger import (
    OP_DATE_FORMAT_ERROR,
    OP_DATE_FUTURE_ERROR,
    parse_op_date,
    record_operation,
)

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


# --- DATE-02 / VA-14: parse_op_date -------------------------------------------


def _days_from_today(offset: int) -> str:
    """An ISO day `offset` days away from today's LOCAL day (the server's own «today»)."""
    today = date.fromisoformat(local_today_iso(settings.display_tz))
    return (today + timedelta(days=offset)).isoformat()


def test_parse_op_date_accepts_past():
    """A back-dated day is the whole point of the phase: accepted, normalised, no error."""
    errors: dict[str, str] = {}
    past = _days_from_today(-20)
    assert parse_op_date(past, errors) == past
    assert errors == {}


def test_parse_op_date_accepts_today():
    """Today's LOCAL day is the boundary and it is INSIDE the allowed range."""
    errors: dict[str, str] = {}
    today = local_today_iso(settings.display_tz)
    assert parse_op_date(today, errors) == today
    assert errors == {}


def test_parse_op_date_rejects_future():
    """VA-14: tomorrow is refused in Russian under `op_date`, and nothing is returned."""
    errors: dict[str, str] = {}
    assert parse_op_date(_days_from_today(1), errors) is None
    assert errors["op_date"] == OP_DATE_FUTURE_ERROR


def test_parse_op_date_rejects_malformed():
    """D-12: a malformed date gets its OWN message, distinct from the future one."""
    for raw in ("31.12.2026", "2026-13-01", "не дата", "2026-02-30"):
        errors: dict[str, str] = {}
        assert parse_op_date(raw, errors) is None, raw
        assert errors["op_date"] == OP_DATE_FORMAT_ERROR, raw
    assert OP_DATE_FORMAT_ERROR != OP_DATE_FUTURE_ERROR


def test_parse_op_date_empty_is_not_an_error():
    """An empty value means «today» — the caller's default supplies it, no error is set."""
    for raw in ("", "   "):
        errors: dict[str, str] = {}
        assert parse_op_date(raw, errors) is None
        assert errors == {}


def test_parse_op_date_honours_the_key_argument():
    """The error key is a parameter, mirroring parse_optional_expiry."""
    errors: dict[str, str] = {}
    assert parse_op_date("нет", errors, key="withdraw_op_date") is None
    assert errors == {"withdraw_op_date": OP_DATE_FORMAT_ERROR}


# --- DATE-01 / DATE-04 / DATE-08: the write paths -----------------------------


def test_record_operation_stamps_local_today_by_default(session, product, batch):
    """A row written with no business_date gets today's LOCAL day — not NULL, not UTC."""
    op = record_operation(
        session,
        type_="receipt",
        product_id=product.id,
        qty_delta=5,
        batch_id=batch.id,
    )
    assert op.business_date is not None
    assert op.business_date == local_today_iso(settings.display_tz)
    # The stamp is the LOCAL day of the row's own created_at, never its UTC
    # prefix — the two differ for every row entered in the 21:00–24:00 UTC
    # window at Europe/Moscow.
    local_day_of_created_at = (
        datetime.fromisoformat(op.created_at)
        .astimezone(ZoneInfo(settings.display_tz))
        .date()
        .isoformat()
    )
    assert op.business_date == local_day_of_created_at


def test_record_operation_accepts_explicit_business_date(session, product, batch):
    """DATE-04: the supplied day lands verbatim and created_at is still «now»."""
    back_dated = _days_from_today(-45)
    before = datetime.now(ZoneInfo("UTC"))
    op = record_operation(
        session,
        type_="receipt",
        product_id=product.id,
        qty_delta=3,
        batch_id=batch.id,
        business_date=back_dated,
    )
    assert op.business_date == back_dated
    # created_at keeps all three of its jobs: it is the ENTRY timestamp and is
    # never moved by the operator's date.
    created_at = datetime.fromisoformat(op.created_at)
    assert created_at >= before - timedelta(seconds=5)
    assert created_at <= datetime.now(ZoneInfo("UTC")) + timedelta(seconds=5)
    assert op.created_at[:10] != back_dated


def test_record_cash_movement_stamps_local_today_by_default(session):
    """The second sanctioned write path stamps identically (finance.py mirrors ledger.py)."""
    from app.services.finance import record_cash_movement

    mv = record_cash_movement(session, category="sale", amount_cents=1000)
    assert mv.business_date == local_today_iso(settings.display_tz)

    back_dated = _days_from_today(-7)
    mv2 = record_cash_movement(
        session, category="sale", amount_cents=1000, business_date=back_dated
    )
    assert mv2.business_date == back_dated
    assert mv2.created_at[:10] != back_dated


def test_merge_inserted_row_keeps_null_business_date(session, product, batch):
    """VA-12 foundation (DATE-08): the bulk sync path must still land a genuine NULL.

    `merge._ledger_row` builds its column dict with `data.get(column)`, so a
    record from a client that predates the column arrives with
    `business_date: None`. That None must survive to the database as NULL —
    it is the sentinel every read-time COALESCE depends on. If the fallback
    had been declared as a column `default=` instead of stamped in Python
    inside `record_operation`, SQLAlchemy would substitute the default here
    and silently turn the sentinel into a date.
    """
    header = {
        "kind": "header",
        "format_version": merge.FORMAT_VERSION,
        "schema_version": "0027",
        "source_device_id": "device-OLD",
        "generated_at": "2026-07-19T10:00:00+00:00",
        "counts": {},
    }
    record = {
        "kind": "operation",
        "id": "op-no-business-date",
        "type": "receipt",
        "product_id": product.id,
        "qty_delta": 10,
        "unit_cost_cents": 1000,
        "unit_price_cents": None,
        "payload": None,
        "sale_id": None,
        "batch_id": batch.id,
        "author_id": None,
        "device_id": "device-OLD",
        "seq": 1,
        "created_at": "2026-07-19T10:00:00+00:00",
        "created_by": "operator",
        "synced_at": None,
        # `business_date` is DELIBERATELY absent: this is what a client that
        # predates migration 0027 puts on the wire.
    }
    lines = [json.dumps(header, ensure_ascii=False), json.dumps(record, ensure_ascii=False)]
    merge.apply_merge(session, merge.parse_exchange(lines), server_now="2026-07-19T12:00:00+00:00")
    session.commit()

    op = session.get(Operation, "op-no-business-date")
    assert op is not None
    assert op.business_date is None

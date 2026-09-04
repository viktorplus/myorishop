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


# --- VA-9 / DATE-07: byte-identity of a CLOSED past period across 0027 --------
#
# "Before and after the migration" is ONE deterministic test, not the suite run
# twice: a database is built at revision 0026 (no business_date column exists at
# all), the pre-Phase-33 report is taken over it, the REAL migration is then run
# on the SAME file, and the current report is taken over the result.

_VA9_DAY = date(2026, 9, 1)
_VA9_TZ = "Europe/Moscow"

# Every fixture is a literal, and the FIRST one is the load-bearing row: at
# Europe/Moscow, 21:30 UTC on Aug 31 is 00:30 local on Sep 1. Its tz-correct
# business date is 2026-09-01 while `substr(created_at, 1, 10)` says 2026-08-31.
# Without it the test passes against a NAIVE prefix backfill and proves nothing.
_VA9_ROWS = (
    # (op_id, product_key, created_at, qty, price_cents, cost_cents)
    ("va9-straddle", "A", "2026-08-31T21:30:00+00:00", 2, 1500, 900),
    ("va9-midday", "A", "2026-09-01T10:00:00+00:00", 3, 1500, 900),
    ("va9-cost-unknown", "B", "2026-09-01T12:00:00+00:00", 1, 2000, None),
    # Local Sep 2 00:30 — outside the period on BOTH sides of the migration.
    ("va9-next-local-day", "B", "2026-09-01T21:30:00+00:00", 9, 2000, 100),
    # Local Aug 31 23:00 — before the period on BOTH sides.
    ("va9-prev-local-day", "A", "2026-08-31T20:00:00+00:00", 7, 1500, 900),
)

_OPERATION_COLUMNS_AT_0026 = (
    "id", "type", "product_id", "qty_delta", "unit_cost_cents", "unit_price_cents",
    "payload", "sale_id", "batch_id", "author_id", "device_id", "seq", "created_at",
    "created_by", "synced_at",
)


def _comparable(report: dict) -> dict:
    """The FULL sales_profit_report dict with ORM Products replaced by their ids.

    Not a narrowing of the assertion: `totals`, `cost_unknown_count` and every
    per-product line (qty / revenue / cost / profit) are compared verbatim, which
    is what catches a per-row bucketing error that nets out in the grand total.
    Only the one value that CANNOT survive the comparison is projected — the
    `product` key holds a live ORM instance, and the before/after reports are
    necessarily read through two different Sessions (the engine is disposed so
    Alembic can migrate the file), so those are distinct objects for the same row.
    """
    return {
        "totals": report["totals"],
        "cost_unknown_count": report["cost_unknown_count"],
        "by_product": [
            {**entry, "product": entry["product"].id} for entry in report["by_product"]
        ],
    }


def _seed_va9_ledger(engine) -> None:
    """INSERT the fixture products and sale operations with LITERAL created_at.

    The OPERATIONS go in as raw SQL with an explicit column list, not through the
    ORM: at revision 0026 that table has no `business_date` column and the mapped
    class would emit it. The PRODUCTS go through the ORM, because `products` is
    byte-identical between 0026 and head — 0027 touches only the two ledger
    tables — so the mapped class is exactly right there and hand-listing its
    NOT NULL columns would only invite drift.

    `batch_id` stays NULL so every row resolves to RUB through
    operation_currency_clause's outer-join fallback, keeping the currency scoping
    out of what this test measures.
    """
    from sqlalchemy import text
    from sqlalchemy.orm import sessionmaker

    from app.models import Product

    with sessionmaker(bind=engine)() as seed_session:
        for key, code in (("A", "VA9-A"), ("B", "VA9-B")):
            seed_session.add(
                Product(id=f"va9-product-{key}", code=code, name=f"Товар {key}", quantity=0)
            )
        seed_session.commit()

    with engine.begin() as connection:
        placeholders = ", ".join(f":{name}" for name in _OPERATION_COLUMNS_AT_0026)
        insert_sql = text(
            f"INSERT INTO operations ({', '.join(_OPERATION_COLUMNS_AT_0026)}) "
            f"VALUES ({placeholders})"
        )
        for seq, (op_id, product_key, created_at, qty, price, cost) in enumerate(_VA9_ROWS, 1):
            connection.execute(
                insert_sql,
                {
                    "id": op_id,
                    "type": "sale",
                    "product_id": f"va9-product-{product_key}",
                    "qty_delta": -qty,
                    "unit_cost_cents": cost,
                    "unit_price_cents": price,
                    "payload": None,
                    "sale_id": None,
                    "batch_id": None,
                    "author_id": None,
                    "device_id": "va9-device",
                    "seq": seq,
                    "created_at": created_at,
                    "created_by": "operator",
                    "synced_at": None,
                },
            )


def test_sales_profit_byte_identical_across_migration(tmp_path, run_alembic, monkeypatch):
    """DATE-07 (VA-9): a fixed PAST period's report is unchanged by the migration.

    The whole point of Phase 33 is that no historical number moves. The proof:

      1. build the database at 0026 — one revision BEFORE 0027, so
         `operations.business_date` does not exist at all — and seed
         literal-timestamped sales, one of them straddling local midnight;
      2. snapshot the raw ledger through the 0026 column set;
      3. run the REAL migration to head on the SAME file — real tz-correct
         backfill, real trigger rebuild;
      4. re-snapshot those same columns and assert they are BYTE-IDENTICAL: the
         migration is purely additive and moved no historical value (DATE-04);
      5. take the PRE-Phase-33 report (bucketing expression restored to
         `Operation.created_at`, UTC timestamp bounds from `local_day_bounds_utc`)
         and the CURRENT report (`business_date_expr`, `business_date_bounds`),
         and assert the two dicts are equal.

    Why BOTH reads happen after step 3, which is the one non-obvious thing here:
    the mapped `Operation` class is ahead of revision 0026 — it names
    `business_date` and `reverses_op_id`, so any ORM entity load against a 0026
    schema fails with `no such column` before it can aggregate anything. The
    "before" read is therefore taken over the post-0027 schema, and step 4 is
    what makes that sound rather than assumed: it asserts, column by column and
    row by row, that every value the old read consumes is exactly what it was
    before the migration ran. The rows were still WRITTEN pre-0027, so their
    business dates come from the migration's backfill, not from a write-time
    stamp — which is the property under test.

    Step 5 monkeypatches `business_date_expr` rather than re-deriving the old
    query, so what runs is the real aggregation, not a copy of it that could
    drift. The one behavioural difference between the old and new predicates —
    the upper bound moved from `<` to `<=` — is neutralised by construction: no
    fixture sits EXACTLY on `end_iso` (the nearest is 30 minutes past it), so the
    two comparisons select the same rows and the equality is about BUCKETING.
    """
    from sqlalchemy import text
    from sqlalchemy.orm import sessionmaker

    import app.services.reports as reports_module
    from app.db import build_engine
    from app.services.reports import sales_profit_report

    db_file = tmp_path / "va9.db"
    url = f"sqlite:///{db_file}"
    snapshot_sql = text(
        f"SELECT {', '.join(_OPERATION_COLUMNS_AT_0026)} FROM operations ORDER BY id"
    )

    # 1. one revision before 0027.
    run_alembic(url, "upgrade", "0026")
    engine = build_engine(str(db_file))
    _seed_va9_ledger(engine)

    with engine.connect() as connection:
        assert "business_date" not in {
            row[1] for row in connection.exec_driver_sql("PRAGMA table_info(operations)")
        }, "the seed must land on a schema that predates the column"
        # 2. the raw ledger as it stood before the migration.
        ledger_before = connection.execute(snapshot_sql).all()
    engine.dispose()
    assert len(ledger_before) == len(_VA9_ROWS)

    # 3. the REAL migration, on the SAME database file.
    run_alembic(url, "upgrade", "head")

    engine = build_engine(str(db_file))
    session_factory = sessionmaker(bind=engine)
    try:
        with engine.connect() as connection:
            # 4. DATE-04: the migration ADDED columns and moved no existing value.
            assert connection.execute(snapshot_sql).all() == ledger_before

        with session_factory() as session:
            # The straddling row's backfilled business date is its LOCAL day,
            # NOT the 10-character UTC prefix of its own created_at.
            straddler = session.get(Operation, "va9-straddle")
            assert straddler.business_date == "2026-09-01"
            assert straddler.created_at[:10] == "2026-08-31"

            # 5a. the report as it read BEFORE this phase.
            monkeypatch.setattr(
                reports_module, "business_date_expr", lambda model: model.created_at
            )
            before = _comparable(
                sales_profit_report(session, *local_day_bounds_utc(_VA9_DAY, _VA9_DAY, _VA9_TZ))
            )
            monkeypatch.undo()

            # 5b. the report as it reads NOW.
            after = _comparable(
                sales_profit_report(session, *business_date_bounds(_VA9_DAY, _VA9_DAY))
            )

            # 6. THE TEETH. Everything above would also pass against a naive
            # `substr(created_at, 1, 10)` backfill unless the straddling row
            # actually moves under it — so run exactly that counterfactual and
            # assert it DIVERGES. Without this, "tz-correct" is an unverified
            # adjective and the equality in step 5 proves only that two identical
            # rules agree.
            from sqlalchemy import func

            monkeypatch.setattr(
                reports_module,
                "business_date_expr",
                lambda model: func.substr(model.created_at, 1, 10),
            )
            naive = _comparable(
                sales_profit_report(session, *business_date_bounds(_VA9_DAY, _VA9_DAY))
            )
            monkeypatch.undo()
    finally:
        engine.dispose()

    # Measured, and it diverges in BOTH directions: the naive cut drops the
    # straddling row (2 units, local Sep 1 but UTC Aug 31) AND pulls in the
    # next-local-day row (9 units, local Sep 2 but UTC Sep 1) — 3 + 1 + 9 = 13
    # against the correct 6. A backfill that sliced instead of converting would
    # therefore be caught here twice over.
    assert naive["totals"]["units_sold"] == 13
    assert naive != before

    # The fixture is only meaningful if the period is non-trivial.
    assert before["totals"]["units_sold"] == 6  # 2 straddling + 3 mid-day + 1 cost-unknown
    assert before["cost_unknown_count"] == 1
    assert len(before["by_product"]) == 2

    assert after == before


def test_migration_backfill_is_timezone_correct_not_a_naive_prefix():
    """VA-10, second half: the backfill converts, it does not slice.

    Pins migration 0027's `_local_business_date` as a TEST rather than a comment,
    at a positive AND a negative UTC offset, with the executed reference values:

        Europe/Moscow     2026-08-31T21:30:00+00:00 -> 2026-09-01 (naive: 2026-08-31)
        America/New_York  2026-09-01T02:00:00+00:00 -> 2026-08-31 (naive: 2026-09-01)

    Both directions matter: east of Greenwich the naive cut is a day EARLY, west
    of it a day LATE. A test at one offset only would pass against a backfill
    that added a fixed shift.
    """
    import importlib.util

    path = (
        Path(__file__).resolve().parent.parent
        / "alembic" / "versions" / "0027_ledger_business_date_and_reversal_links.py"
    )
    spec = importlib.util.spec_from_file_location("migration_0027", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    # The revision ships configured for the deployment measured in 33-ROLLOUT §1.
    assert module._DISPLAY_TZ == "Europe/Moscow"

    moscow_input = "2026-08-31T21:30:00+00:00"
    assert module._local_business_date(moscow_input) == "2026-09-01"
    assert module._local_business_date(moscow_input) != moscow_input[:10] == "2026-08-31"

    module._DISPLAY_TZ = "America/New_York"
    ny_input = "2026-09-01T02:00:00+00:00"
    assert module._local_business_date(ny_input) == "2026-08-31"
    assert module._local_business_date(ny_input) != ny_input[:10] == "2026-09-01"

    # UTC: the one zone where converting and slicing agree — asserted so the
    # test states the boundary of the claim instead of implying it never holds.
    module._DISPLAY_TZ = "UTC"
    assert module._local_business_date(moscow_input) == moscow_input[:10]


def test_null_business_date_still_reported(session, product, past_sale, customer):
    """VA-12 / DATE-08: a NULL-business_date row does not VANISH from a report.

    The row is inserted the way `merge` does — bypassing `record_operation`, so
    nothing stamps the column — and must still be bucketed, by
    `substr(created_at, 1, 10)` through business_date_expr's COALESCE. This is
    the property that keeps an un-upgraded client's pushed rows visible: they
    arrive NULL forever, not just until a one-off backfill runs.
    """
    from app.services.reports import sales_profit_report, top_selling_products, writeoff_report

    day = date(2026, 7, 10)
    _sale, op = past_sale(
        customer, product, created_at="2026-07-10T10:00:00+00:00", qty=4, unit_price_cents=1000
    )
    assert op.business_date is None

    start, end = business_date_bounds(day, day)
    assert sales_profit_report(session, start, end)["totals"]["units_sold"] == 4
    assert top_selling_products(session, start, end)[0]["units_sold"] == 4

    # ...and the same row is absent from the day AFTER, i.e. the fallback buckets
    # it, it does not simply match everything.
    later_start, later_end = business_date_bounds(day + timedelta(days=1), day + timedelta(days=1))
    assert sales_profit_report(session, later_start, later_end)["totals"]["units_sold"] == 0
    assert writeoff_report(session, start, end)["total_qty"] == 0  # it is a sale, not a write-off

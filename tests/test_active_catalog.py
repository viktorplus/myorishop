"""DASH-02 (D-01/D-02) executable contract: ActiveCatalog model, migration
0016, service layer, and the /catalogs active-catalog form.
"""

from app.services.active_catalog import (
    CLOSE_DATE_ERROR,
    NUMBER_TOO_LONG_ERROR,
    _row_count,
    get_active_catalog,
    set_active_catalog,
)

# --- Service layer (Task 2) ---


def test_get_active_catalog_empty_table_returns_none(session):
    assert get_active_catalog(session) is None


def test_set_active_catalog_then_get_round_trips_both_fields(session):
    row, errors = set_active_catalog(session, number="05", close_date="2026-08-31")

    assert errors == {}
    assert row is not None
    assert row.number == "05"
    assert row.close_date == "2026-08-31"

    fetched = get_active_catalog(session)
    assert fetched.id == row.id
    assert fetched.number == "05"
    assert fetched.close_date == "2026-08-31"


def test_set_active_catalog_blank_fields_store_null(session):
    row, errors = set_active_catalog(session, number="", close_date="")

    assert errors == {}
    assert row is not None
    assert row.number is None
    assert row.close_date is None


def test_set_active_catalog_overlong_number_rejected_zero_writes(session):
    row, errors = set_active_catalog(session, number="X" * 21, close_date="")

    assert row is None
    assert errors == {"number": NUMBER_TOO_LONG_ERROR}
    assert get_active_catalog(session) is None


def test_set_active_catalog_malformed_close_date_rejected_zero_writes(session):
    row, errors = set_active_catalog(session, number="05", close_date="not-a-date")

    assert row is None
    assert errors == {"close_date": CLOSE_DATE_ERROR}
    assert get_active_catalog(session) is None


def test_set_active_catalog_second_call_updates_same_row(session):
    first, _ = set_active_catalog(session, number="05", close_date="2026-08-31")
    second, errors = set_active_catalog(session, number="06", close_date="2026-09-30")

    assert errors == {}
    assert second.id == first.id
    assert _row_count(session) == 1
    fetched = get_active_catalog(session)
    assert fetched.number == "06"
    assert fetched.close_date == "2026-09-30"

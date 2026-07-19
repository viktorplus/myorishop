"""SYNC-04 exchange-format tests: NDJSON factory + round-trip / rejection suite.

Plan 27-01 owns the wire format only (parse/serialize). The idempotency,
conflict-resolution and recompute dimensions arrive with apply_merge in Plans
02-03; this module's factory (``build_ndjson`` + ``record_line``) is the shared
NDJSON helper those later plans reuse.
"""

import json

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.models import Batch, CashMovement, Operation, Product, User
from app.services import merge
from app.services.auth import hash_password
from app.services.finance import compute_balance
from app.services.ledger import (
    compute_batch_stock,
    compute_stock,
    recompute_derived,
    record_operation,
)


def record_line(kind: str, **fields) -> dict:
    """Build one NDJSON record dict: a ``kind`` discriminator + explicit fields.

    Values are plain JSON-native scalars/containers (str/int/None/list/dict) so
    the dict serializes verbatim — mirroring the column set each kind carries.
    """
    return {"kind": kind, **fields}


def record_from_orm(kind: str, obj, **overrides) -> dict:
    """Build a record dict from an ORM row's mapper columns, plus any overrides."""
    data = {column.key: getattr(obj, column.key) for column in obj.__mapper__.columns}
    data.update(overrides)
    return {"kind": kind, **data}


def build_ndjson(*, header_overrides: dict | None = None, records: list[dict]) -> list[str]:
    """Return NDJSON lines (header first, then one line per record dict).

    ``records`` are ``{"kind": ..., ...field...}`` dicts (e.g. from
    ``record_line``). ``header_overrides`` patches the default header envelope
    (e.g. ``{"format_version": 999}`` for the rejection tests).
    """
    header = {
        "kind": "header",
        "format_version": merge.FORMAT_VERSION,
        "schema_version": "0017",
        "source_device_id": "device-A",
        "generated_at": "2026-07-19T10:00:00+00:00",
        "counts": {},
    }
    if header_overrides:
        header.update(header_overrides)
    lines = [json.dumps(header, ensure_ascii=False)]
    lines.extend(json.dumps(rec, ensure_ascii=False) for rec in records)
    return lines


def test_module_imports():
    """The format contract is importable and internally consistent."""
    assert merge.FORMAT_VERSION == 1
    assert len(merge.RECORD_KINDS) == 9
    assert "header" in merge.RECORD_KINDS
    # Every non-header kind maps to an app.models ORM class.
    assert set(merge.KIND_TO_MODEL) == merge.RECORD_KINDS - {"header"}
    for model in merge.KIND_TO_MODEL.values():
        assert model.__module__ == "app.models"
    # The four value-object dataclasses exist and are constructible.
    assert merge.ExchangeRecord(kind="product", data={}).kind == "product"
    empty_batch = merge.ExchangeBatch(
        format_version=1, schema_version="0017", source_device_id=None
    )
    assert empty_batch.records == []
    assert not merge.MergeReport().conflicts
    assert merge.Conflict(
        kind="product_code",
        product_id="p-1",
        original_code="12345",
        resolved_code="12345~a1b2",
        incumbent_id="p-0",
    ).incumbent_id == "p-0"


# --- Sample records used across the round-trip / rejection suite -------------

_PRODUCT = record_line(
    "product",
    id="p-1",
    code="12345",
    name="Крем",
    name_lc="крем",
    category=None,
    cost_cents=50000,
    sale_cents=79900,
    min_sale_cents=None,
    low_stock_threshold=None,
    stale_days=None,
    quantity=0,
    created_at="2026-07-19T10:00:00+00:00",
    updated_at="2026-07-19T10:00:00+00:00",
    deleted_at=None,
)

_OPERATION = record_line(
    "operation",
    id="op-1",
    type="receipt",
    product_id="p-1",
    qty_delta=10,
    unit_cost_cents=50000,
    unit_price_cents=None,
    payload={"reason_code": None},
    sale_id=None,
    batch_id="b-1",
    author_id="u-1",
    device_id="dev-1",
    seq=17,
    created_at="2026-07-19T10:00:00+00:00",
    created_by="operator",
    synced_at=None,
)

_CASH = record_line(
    "cash_movement",
    id="cm-1",
    category="sale",
    amount_cents=79900,
    note=None,
    sale_id="s-1",
    author_id="u-1",
    device_id="dev-1",
    seq=9,
    created_at="2026-07-19T10:00:00+00:00",
    created_by="operator",
    synced_at=None,
)


def _to_exchange_records(record_dicts: list[dict]) -> list[merge.ExchangeRecord]:
    """Turn factory record dicts into ExchangeRecord objects (drops ``kind``)."""
    return [
        merge.ExchangeRecord(
            kind=rec["kind"],
            data={key: value for key, value in rec.items() if key != "kind"},
        )
        for rec in record_dicts
    ]


def test_round_trip():
    """serialize -> parse is identity for the record list AND the envelope."""
    originals = _to_exchange_records([_PRODUCT, _OPERATION, _CASH])
    lines = list(
        merge.serialize_exchange(
            originals,
            schema_version="0017",
            source_device_id="dev-1",
            generated_at="2026-07-19T10:00:00+00:00",
        )
    )
    # Header first, then one line per record.
    assert json.loads(lines[0])["kind"] == "header"
    assert len(lines) == 1 + len(originals)

    batch = merge.parse_exchange(lines)
    assert batch.records == originals  # field-for-field verbatim
    assert batch.format_version == merge.FORMAT_VERSION
    assert batch.schema_version == "0017"
    assert batch.source_device_id == "dev-1"

    # Origin provenance survives verbatim on the ledger records (DD-6 / SYNC-02).
    parsed_op = next(r for r in batch.records if r.kind == "operation")
    assert parsed_op.data["id"] == "op-1"
    assert parsed_op.data["device_id"] == "dev-1"
    assert parsed_op.data["seq"] == 17
    assert parsed_op.data["author_id"] == "u-1"
    assert parsed_op.data["created_by"] == "operator"


def test_format_version_rejected():
    """A header carrying an unsupported format_version is rejected."""
    lines = build_ndjson(header_overrides={"format_version": 999}, records=[_PRODUCT])
    with pytest.raises(ValueError, match="format_version"):
        merge.parse_exchange(lines)


def test_malformed_line_rejected():
    """A non-JSON / non-object line raises before any record is built."""
    header = build_ndjson(records=[])[0]
    with pytest.raises(ValueError, match="malformed NDJSON line"):
        merge.parse_exchange([header, "{not json"])
    with pytest.raises(ValueError, match="malformed NDJSON line"):
        merge.parse_exchange([header, "[1, 2, 3]"])  # JSON array, not an object


def test_unknown_kind_rejected():
    """A line with an out-of-vocabulary kind is rejected."""
    lines = build_ndjson(records=[record_line("bogus", id="x-1")])
    with pytest.raises(ValueError, match="unknown record kind"):
        merge.parse_exchange(lines)


def test_missing_header_rejected():
    """A batch whose first line is a record (no header) is rejected."""
    line = json.dumps(_PRODUCT, ensure_ascii=False)
    with pytest.raises(ValueError, match="missing header"):
        merge.parse_exchange([line])


def test_duplicate_header_rejected():
    """A second header line mid-batch is rejected."""
    header = build_ndjson(records=[])[0]
    with pytest.raises(ValueError, match="duplicate header"):
        merge.parse_exchange([header, header])


def test_record_missing_id_rejected():
    """A record without a non-empty string id is rejected."""
    lines = build_ndjson(records=[record_line("product", name="no id")])
    with pytest.raises(ValueError, match="non-empty string id"):
        merge.parse_exchange(lines)


def test_ledger_missing_provenance_rejected():
    """A ledger record missing device_id/seq/created_at/created_by is rejected."""
    op = dict(_OPERATION)
    del op["device_id"]
    lines = build_ndjson(records=[op])
    with pytest.raises(ValueError, match="device_id"):
        merge.parse_exchange(lines)


def test_float_money_rejected():
    """A float money value (type confusion) is rejected — integer cents only."""
    bad = record_line("product", id="p-2", code="99", name="X", cost_cents=500.5)
    lines = build_ndjson(records=[bad])
    with pytest.raises(ValueError, match="int cents"):
        merge.parse_exchange(lines)


def test_synced_at_not_trusted():
    """A ledger line carrying synced_at parses with data['synced_at'] is None."""
    op = dict(_OPERATION)
    op["synced_at"] = "2026-07-19T11:00:00+00:00"
    lines = build_ndjson(records=[op])
    batch = merge.parse_exchange(lines)
    parsed_op = next(r for r in batch.records if r.kind == "operation")
    assert parsed_op.data["synced_at"] is None


def test_blank_lines_skipped():
    """Blank / whitespace-only lines between records are ignored."""
    lines = build_ndjson(records=[_PRODUCT])
    padded = [lines[0], "", "   ", lines[1], ""]
    batch = merge.parse_exchange(padded)
    assert len(batch.records) == 1


# --- SYNC-03 building block: recompute_derived is non-committing --------------


def test_recompute_derived_does_not_commit(session, product, batch):
    """recompute_derived repairs the cache in-session but NEVER commits.

    Seed a real ledger receipt, then commit a DELIBERATELY WRONG cached
    Product.quantity. recompute_derived must repair it in-session (proving it
    recomputes) yet a rollback must revert to the wrong committed value
    (proving it did not persist the repair — the merge owns the transaction).
    """
    record_operation(
        session,
        type_="receipt",
        product_id=product.id,
        qty_delta=10,
        unit_cost_cents=1000,
        batch_id=batch.id,
    )
    # Persist a corrupted cache value (products are not append-only guarded).
    product.quantity = 999
    session.commit()

    recompute_derived(session)
    assert product.quantity == 10  # repaired in-session from the ledger

    session.rollback()
    assert product.quantity == 999  # repair was NOT committed by recompute_derived


# --- SYNC-02 / SYNC-03: apply_merge ledger append + recompute -----------------

_NOW = "2026-07-19T12:00:00+00:00"


def _op(op_id, *, product_id, batch_id, seq, device_id="dev-A", qty_delta=10,
        author_id=None, created_at="2026-07-19T10:00:00+00:00"):
    """Build a verbatim `operation` NDJSON record (bypasses the write path)."""
    return record_line(
        "operation",
        id=op_id,
        type="receipt",
        product_id=product_id,
        qty_delta=qty_delta,
        unit_cost_cents=1000,
        unit_price_cents=None,
        payload=None,
        sale_id=None,
        batch_id=batch_id,
        author_id=author_id,
        device_id=device_id,
        seq=seq,
        created_at=created_at,
        created_by="operator",
        synced_at=None,
    )


def _cash(cm_id, *, amount_cents, seq, device_id="dev-A", author_id=None,
          created_at="2026-07-19T10:00:00+00:00"):
    """Build a verbatim `cash_movement` NDJSON record."""
    return record_line(
        "cash_movement",
        id=cm_id,
        category="sale",
        amount_cents=amount_cents,
        note=None,
        sale_id=None,
        author_id=author_id,
        device_id=device_id,
        seq=seq,
        created_at=created_at,
        created_by="operator",
        synced_at=None,
    )


def _apply(session, records):
    """Parse `records` into a batch and apply_merge it (no commit inside)."""
    batch = merge.parse_exchange(build_ndjson(records=records))
    return merge.apply_merge(session, batch, server_now=_NOW)


def _seed_user(session, *, user_id="u-1", login="dev-user"):
    user = User(
        id=user_id,
        login=login,
        display_name="Dev",
        role="operator",
        password_hash=hash_password("pw"),
        is_active=1,
    )
    session.add(user)
    session.commit()
    return user


def _snapshot(session):
    """A byte-stable snapshot of the merged ledger + derived state + balance."""
    ops = session.scalars(select(Operation).order_by(Operation.id)).all()
    cash = session.scalars(select(CashMovement).order_by(CashMovement.id)).all()
    products = session.scalars(select(Product).order_by(Product.id)).all()
    batches = session.scalars(select(Batch).order_by(Batch.id)).all()
    return (
        [(o.id, o.device_id, o.seq, o.qty_delta, o.batch_id) for o in ops],
        [(c.id, c.device_id, c.seq, c.amount_cents) for c in cash],
        [(p.id, p.quantity) for p in products],
        [(b.id, b.quantity) for b in batches],
        compute_balance(session),
    )


def test_merge_twice_equals_once(session, product, batch):
    """SYNC-02: replaying the same batch inserts 0 rows and changes nothing."""
    records = [
        _op("op-1", product_id=product.id, batch_id=batch.id, seq=1, qty_delta=10),
        _cash("cm-1", amount_cents=5000, seq=1),
    ]
    r1 = _apply(session, records)
    session.commit()
    assert r1.operations_inserted == 1 and r1.cash_inserted == 1

    snap = _snapshot(session)

    r2 = _apply(session, records)
    session.commit()
    assert r2.operations_inserted == 0 and r2.cash_inserted == 0
    assert r2.operations_skipped == 1 and r2.cash_skipped == 1
    assert _snapshot(session) == snap  # byte-identical: merge-twice == merge-once


def test_ledger_row_inserted_verbatim(session, product, batch):
    """SYNC-02: origin id/device_id/seq/author_id/created_by/created_at survive."""
    user = _seed_user(session)
    _apply(
        session,
        [
            _op(
                "op-42",
                product_id=product.id,
                batch_id=batch.id,
                device_id="dev-Z",
                seq=99,
                author_id=user.id,
                created_at="2026-01-02T03:04:05+00:00",
            )
        ],
    )
    session.commit()

    op = session.get(Operation, "op-42")
    assert op.device_id == "dev-Z"
    assert op.seq == 99
    assert op.author_id == user.id
    assert op.created_by == "operator"
    assert op.created_at == "2026-01-02T03:04:05+00:00"
    assert op.synced_at is None  # never trusted from the wire


def test_duplicate_uuid_skipped(session, product, batch):
    """SYNC-02: a batch whose UUID is already present inserts nothing."""
    records = [_op("op-1", product_id=product.id, batch_id=batch.id, seq=1)]
    _apply(session, records)
    session.commit()

    report = _apply(session, records)
    session.commit()
    assert report.operations_inserted == 0
    assert report.operations_skipped == 1
    assert session.scalar(select(func.count()).select_from(Operation)) == 1


def test_stock_recomputed_after_merge(session, product, batch):
    """SYNC-03: Product.quantity == compute_stock, Batch.quantity == batch stock."""
    _apply(session, [_op("op-1", product_id=product.id, batch_id=batch.id, seq=1, qty_delta=7)])
    session.commit()

    session.refresh(product)
    session.refresh(batch)
    assert product.quantity == compute_stock(session, product.id) == 7
    assert batch.quantity == compute_batch_stock(session, batch) == 7


def test_cash_balance_after_merge(session):
    """SYNC-03: compute_balance equals the signed sum of merged cash rows."""
    _apply(
        session,
        [
            _cash("cm-1", amount_cents=5000, seq=1),
            _cash("cm-2", amount_cents=-2000, seq=2),
        ],
    )
    session.commit()
    assert compute_balance(session) == 3000


def test_two_device_stock_union(session, product, batch):
    """SYNC-03: two devices' ledgers sum, order-independently."""
    dev_a = [
        _op("op-a", product_id=product.id, batch_id=batch.id, device_id="dev-A", seq=1, qty_delta=10),  # noqa: E501
    ]
    dev_b = [
        _op("op-b", product_id=product.id, batch_id=batch.id, device_id="dev-B", seq=1, qty_delta=5),  # noqa: E501
    ]
    # Apply B first, then A — the recompute is a commutative sum, so order is moot.
    _apply(session, dev_b)
    session.commit()
    _apply(session, dev_a)
    session.commit()

    session.refresh(product)
    assert product.quantity == 15 == compute_stock(session, product.id)


def test_bad_record_rolls_back(session, product, batch):
    """SYNC-04: a poisoned record mid-batch → caller rollback leaves DB unchanged."""
    good = _op("op-good", product_id=product.id, batch_id=batch.id, seq=1, qty_delta=10)
    bad = _op("op-bad", product_id="ghost-product", batch_id=None, seq=2, qty_delta=1)
    batch_obj = merge.parse_exchange(build_ndjson(records=[good, bad]))

    with pytest.raises(IntegrityError):
        merge.apply_merge(session, batch_obj, server_now=_NOW)
    session.rollback()

    # All-or-nothing: not even the good row survived.
    assert session.scalar(select(func.count()).select_from(Operation)) == 0
    session.refresh(product)
    assert product.quantity == 0

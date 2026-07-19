"""SYNC-04 exchange-format tests: NDJSON factory + round-trip / rejection suite.

Plan 27-01 owns the wire format only (parse/serialize). The idempotency,
conflict-resolution and recompute dimensions arrive with apply_merge in Plans
02-03; this module's factory (``build_ndjson`` + ``record_line``) is the shared
NDJSON helper those later plans reuse.
"""

import json

import pytest

from app.services import merge


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

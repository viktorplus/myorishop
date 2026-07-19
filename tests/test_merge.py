"""SYNC-04 exchange-format tests: NDJSON factory + round-trip / rejection suite.

Plan 27-01 owns the wire format only (parse/serialize). The idempotency,
conflict-resolution and recompute dimensions arrive with apply_merge in Plans
02-03; this module's factory (``build_ndjson`` + ``record_line``) is the shared
NDJSON helper those later plans reuse.
"""

import json

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

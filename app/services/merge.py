"""Shared merge engine + NDJSON exchange format (SYNC-02/03/04/05): PURE functions.

This is the milestone's single correctness core. It defines the ONE wire schema
(NDJSON: one JSON object per line, one header line first, per-line ``kind``
discriminator) that both later transports reuse without a second implementation:
Phase 28 (online sync) and Phase 30 (offline self-upload). It stays PURE — no
HTTP, no file I/O, no FastAPI — so both transports are thin callers.

Governing decisions realized here (from 27-RESEARCH.md):
- DD-4 (Format): NDJSON, per-line ``kind`` + one header envelope line first; the
  header carries ``format_version`` (engine compatibility) and ``schema_version``
  (Alembic head, for OFF-07 later).
- DD-6 (Verbatim carriage): every ledger record carries origin
  ``id``/``device_id``/``seq``/``author_id``/``created_by``/``created_at``
  unchanged; money stays integer cents; timestamps stay ISO-8601 UTC text;
  ``synced_at`` is emitted null and never read from the wire (server-owned).

This plan (27-01) lands the format constants, the ``kind``->model map, the four
value-object dataclasses, and ``parse_exchange``/``serialize_exchange``. The
``apply_merge`` engine (reference upsert + idempotent ledger append + recompute)
arrives in Plans 02-03; the dataclasses ``Conflict``/``MergeReport`` are declared
now so the contract is stable for those plans.
"""

import json
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field

from app.models import (
    Batch,
    CashMovement,
    Customer,
    Dictionary,
    Operation,
    Product,
    Sale,
    Warehouse,
)

# The engine-understood wire version (header ``format_version``); a mismatch is
# rejected by parse_exchange (feeds OFF-07's schema-version gate in Phase 30).
FORMAT_VERSION: int = 1

# The whole wire vocabulary: one "header" envelope kind + eight record kinds.
RECORD_KINDS: frozenset[str] = frozenset(
    {
        "header",
        "warehouse",
        "product",
        "customer",
        "dictionary",
        "batch",
        "sale",
        "operation",
        "cash_movement",
    }
)

# Map each non-header ``kind`` to its ORM model (FK-dependency order preserved
# for readability: warehouses->products->customers->dictionary->batches->sales
# ->operations->cash_movements — the order Plan 02's apply_merge inserts in).
KIND_TO_MODEL: dict[str, type] = {
    "warehouse": Warehouse,
    "product": Product,
    "customer": Customer,
    "dictionary": Dictionary,
    "batch": Batch,
    "sale": Sale,
    "operation": Operation,
    "cash_movement": CashMovement,
}

# Allowed field set per kind, derived from the model mapper columns so the wire
# format auto-tracks the schema — no hand-maintained column list can drift.
KIND_TO_FIELDS: dict[str, frozenset[str]] = {
    kind: frozenset(column.key for column in model.__mapper__.columns)
    for kind, model in KIND_TO_MODEL.items()
}

# Ledger kinds carry the full append-only provenance set (verbatim, DD-6).
_LEDGER_KINDS: frozenset[str] = frozenset({"operation", "cash_movement"})

# Origin fields every ledger record MUST carry (validated before any DB touch).
_LEDGER_REQUIRED: tuple[str, ...] = ("device_id", "seq", "created_at", "created_by")


@dataclass(frozen=True)
class ExchangeRecord:
    """One wire record: a ``kind`` discriminator + its verbatim column ``data``."""

    kind: str
    data: dict


@dataclass
class ExchangeBatch:
    """A parsed exchange payload: the header envelope fields + the record list."""

    format_version: int
    schema_version: str
    source_device_id: str | None
    records: list[ExchangeRecord] = field(default_factory=list)


@dataclass
class Conflict:
    """A resolved ``Product.code`` cross-device collision (populated in Plan 03)."""

    kind: str
    product_id: str
    original_code: str
    resolved_code: str
    incumbent_id: str


@dataclass
class MergeReport:
    """Per-merge outcome counts (populated by apply_merge in Plans 02-03)."""

    operations_inserted: int = 0
    operations_skipped: int = 0
    cash_inserted: int = 0
    cash_skipped: int = 0
    reference_inserted: dict[str, int] = field(default_factory=dict)
    reference_server_wins: dict[str, int] = field(default_factory=dict)
    conflicts: list[Conflict] = field(default_factory=list)


def _money_fields(kind: str) -> frozenset[str]:
    """Schema-derived money columns for a kind (integer cents only, never float)."""
    return frozenset(f for f in KIND_TO_FIELDS.get(kind, frozenset()) if f.endswith("_cents"))


def parse_exchange(lines: Iterable[str]) -> ExchangeBatch:
    """Parse NDJSON lines into an ExchangeBatch (PURE — no DB/file/network).

    The first non-blank line MUST be the ``{"kind":"header", ...}`` envelope
    carrying ``format_version``; every later line is one record typed by its
    ``kind``. Rejects (ValueError, before any DB touch) a malformed/non-object
    line, an unsupported ``format_version``, an unknown/duplicate ``kind``, a
    missing header, and a float money value. ``synced_at`` is forced to None
    (server-owned, never trusted from the wire).
    """
    non_header_kinds = RECORD_KINDS - {"header"}
    header: dict | None = None
    records: list[ExchangeRecord] = []

    for index, raw in enumerate(lines):
        if raw is None or not str(raw).strip():
            continue  # skip blank / whitespace-only lines
        try:
            obj = json.loads(raw)
        except (json.JSONDecodeError, TypeError) as exc:
            raise ValueError(f"malformed NDJSON line: {index}") from exc
        if not isinstance(obj, dict):
            raise ValueError(f"malformed NDJSON line: {index} (not a JSON object)")

        kind = obj.get("kind")

        # The FIRST non-blank line MUST be the header envelope.
        if header is None:
            if kind != "header":
                raise ValueError("missing header: first line must be a header record")
            version = obj.get("format_version")
            if version != FORMAT_VERSION:
                raise ValueError(f"unsupported format_version: {version!r}")
            header = obj
            continue

        # Every subsequent line is a typed record (never a second header).
        if kind == "header":
            raise ValueError("duplicate header record")
        if kind not in non_header_kinds:
            raise ValueError(f"unknown record kind: {kind!r}")

        data = {key: value for key, value in obj.items() if key != "kind"}

        # Required identity: every record carries a non-empty string id.
        record_id = data.get("id")
        if not isinstance(record_id, str) or not record_id:
            raise ValueError(f"{kind} record missing a non-empty string id")

        # Ledger records also carry the full append-only provenance set.
        if kind in _LEDGER_KINDS:
            for required in _LEDGER_REQUIRED:
                if data.get(required) is None:
                    raise ValueError(f"{kind} record missing required field {required!r}")
            if not isinstance(data["seq"], int) or isinstance(data["seq"], bool):
                raise ValueError(f"{kind} record seq must be an integer")

        # Money is integer cents only — a float value is a type-confusion attack (V5).
        for money_key in _money_fields(kind):
            if isinstance(data.get(money_key), float):
                raise ValueError(f"money field {money_key!r} must be int cents, not float")

        # synced_at is server-owned — never trusted from the wire (DD-6).
        if "synced_at" in data:
            data["synced_at"] = None

        records.append(ExchangeRecord(kind=kind, data=data))

    if header is None:
        raise ValueError("missing header: empty or headerless batch")

    return ExchangeBatch(
        format_version=header["format_version"],
        schema_version=header.get("schema_version") or "",
        source_device_id=header.get("source_device_id"),
        records=records,
    )


def serialize_exchange(
    records: Iterable[ExchangeRecord],
    *,
    schema_version: str,
    source_device_id: str | None,
    generated_at: str,
) -> Iterator[str]:
    """Serialize records to NDJSON lines, header FIRST (PURE — no DB/file/network).

    Yields the header envelope (``kind`` == "header", ``format_version`` ==
    FORMAT_VERSION, the envelope fields, and a ``counts`` map) then one
    ``{"kind": rec.kind, **rec.data}`` line per record. Round-trip identity: for
    any record list ``R``, ``parse_exchange(serialize_exchange(R, ...)).records``
    equals ``R`` field-for-field.
    """
    materialized = list(records)

    counts: dict[str, int] = {}
    for record in materialized:
        counts[record.kind] = counts.get(record.kind, 0) + 1

    header = {
        "kind": "header",
        "format_version": FORMAT_VERSION,
        "schema_version": schema_version,
        "source_device_id": source_device_id,
        "generated_at": generated_at,
        "counts": counts,
    }
    yield json.dumps(header, ensure_ascii=False)

    for record in materialized:
        yield json.dumps({"kind": record.kind, **record.data}, ensure_ascii=False)

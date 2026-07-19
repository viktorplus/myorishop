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

from sqlalchemy import insert, select
from sqlalchemy.orm import Session

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
from app.services.ledger import recompute_derived

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


# SQLite caps a statement at ~999 bound parameters; chunk id-membership probes
# well under it so a large upload's WHERE id IN (...) never overflows (Pitfall 3).
_IN_CHUNK: int = 500

# The two append-only ledgers, inserted in this order (both after the Plan 03
# reference-upsert stage). Cash has no FK on operations, so order is a courtesy.
_LEDGER_INSERT_ORDER: tuple[str, ...] = ("operation", "cash_movement")


def _insert_new(session: Session, model: type, rows: list[dict]) -> tuple[int, int]:
    """Portable idempotent bulk insert-if-new by UUID PK (SYNC-02 core).

    ``rows`` are full column dicts keyed incl. ``id``. Pre-select the ids
    already present (chunked for SQLite's bound-param cap), filter them out as a
    Python set-difference, and bulk-insert the remainder with a generic Core
    ``insert(model)`` — portable across SQLite and PostgreSQL. Returns
    ``(inserted, skipped)``. Re-running the same rows finds every id present, so
    ``inserted == 0`` — replay is a true no-op (idempotency). NO dialect SQL, NO
    upsert clause, NO raw SQL (Pitfall 2, CLAUDE.md portability rule).
    """
    if not rows:
        return 0, 0
    incoming_ids = [row["id"] for row in rows]
    existing: set = set()
    for start in range(0, len(incoming_ids), _IN_CHUNK):
        chunk = incoming_ids[start : start + _IN_CHUNK]
        existing.update(session.scalars(select(model.id).where(model.id.in_(chunk))).all())
    new_rows = [row for row in rows if row["id"] not in existing]
    if new_rows:
        session.execute(insert(model), new_rows)
    return len(new_rows), len(rows) - len(new_rows)


def _ledger_row(kind: str, data: dict) -> dict:
    """Build a verbatim column dict for a ledger record (DD-6).

    Restrict to the model's own columns (schema-derived) so a stray wire field
    can't reach the insert, carry every origin value unchanged
    (``id``/``device_id``/``seq``/``author_id``/``created_by``/``created_at`` +
    the type-specific fields), and force ``synced_at`` to None — the sync cursor
    is server-owned and never trusted from the wire (Phase 28 territory).
    """
    row = {column: data.get(column) for column in KIND_TO_FIELDS[kind]}
    row["synced_at"] = None
    return row


def apply_merge(session: Session, batch: ExchangeBatch, *, server_now: str) -> MergeReport:
    """Merge a parsed batch into the DB: idempotent ledger append + recompute.

    PURE w.r.t. HTTP/disk and — critically — NEVER commits: the caller wraps the
    whole call in one transaction so a mid-batch failure rolls back cleanly
    (all-or-nothing, OFF-05 groundwork). This plan (27-02) handles the two
    append-only ledgers; the FK-ordered reference-upsert stage slots in ahead of
    the ledger appends in Plan 03 (see the seam below).

    Ledger rows are inserted verbatim by their origin UUID via the portable
    set-difference (:func:`_insert_new`) — never re-minting identity through the
    interactive write path (Pitfall 1). After the appends, derived stock is
    recomputed from the merged ledger (:func:`recompute_derived`); cash balance
    is a live SUM (``finance.compute_balance``) and needs nothing stored. The
    recompute's invariant ValueError propagates so an internally inconsistent
    batch is rejected (Pitfall 6) — the caller's rollback undoes the appends.
    """
    report = MergeReport()

    # --- (1) Reference-upsert stage — Plan 03 -------------------------------
    # Plan 03 inserts the FK-ordered, insert-if-new + server-wins reference
    # upserts (warehouses -> products -> customers -> dictionary -> batches ->
    # sales) HERE, BEFORE the ledger appends, plus the Product.code collision
    # rename. This plan assumes referenced rows already exist (tests seed them
    # via fixtures) and leaves this seam empty on purpose. ``server_now`` is
    # threaded through for that stage (unused by the pure ledger append).

    # --- (2) Ledger append stage (SYNC-02) ----------------------------------
    buckets: dict[str, list[dict]] = {kind: [] for kind in _LEDGER_INSERT_ORDER}
    for record in batch.records:
        if record.kind in buckets:
            buckets[record.kind].append(_ledger_row(record.kind, record.data))

    report.operations_inserted, report.operations_skipped = _insert_new(
        session, Operation, buckets["operation"]
    )
    report.cash_inserted, report.cash_skipped = _insert_new(
        session, CashMovement, buckets["cash_movement"]
    )

    # --- (3) Derived-state recompute (SYNC-03) ------------------------------
    recompute_derived(session)

    return report


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

"""Pull-cursor query + reference record assembly (SYNC-09 / SRV-03): PURE.

This module is the read side of the sync surface — the query the Phase 29 client
calls to pull server-authoritative REFERENCE data down. It mirrors the
``app/services/merge.py`` contract: PURE functions, no HTTP, no file I/O, no
web-framework import, no wire-serialization here — the route
(``app/routes/sync.py``) is the thin caller that turns a :class:`PullPage` into
NDJSON via the UNMODIFIED Phase 27 serializer and exposes the two cursor halves
as HTTP headers.

Four LOCKED semantics for the Phase 29 reader who lands here first:

1. **Reference data only, never ledger rows.** :data:`PULL_KINDS` is exactly the
   six reference kinds. The two ledger kinds (operations and cash movements) are
   deliberately EXCLUDED: the offline path is upload-only and SYNC-01 specifies
   pulling server-authoritative REFERENCE data down, not the ledger.

2. **The server never writes ``synced_at``.** On the server ``synced_at`` stays
   NULL forever — it means "this row has never been pushed FROM here". Only the
   client stamps its own cursor (Phase 29). Pull is strictly read-only: it opens
   no write transaction and mutates nothing.

3. **The cursor is COMPOSITE ``(cursor_column, id)`` and inclusive on the
   timestamp alone.** ``next_since`` is the cursor value of the LAST record on the
   page; because the timestamp comparison is inclusive, a client that sends back
   ONLY ``since`` (ignoring ``after_id``) loops forever across a run of identical
   timestamps — the documented bulk-edit case, where one write stamps many rows
   with an identical timestamp. The client MUST send BOTH ``since`` and
   ``after_id`` back. The primary-key tie-break is what guarantees forward
   progress.

4. **The two cursor halves reach the client as the headers ``X-Sync-Next-Since``
   and ``X-Sync-Next-After-Id``**, NOT inside the NDJSON header envelope: the
   envelope emitted by ``merge.serialize_exchange`` has a fixed field set and this
   phase does not modify the Phase 27 engine.

Portability (CLAUDE.md): portable ORM constructs only — ``select()``, ``or_``,
``and_`` and ``getattr(Model, column_name)``. No dialect SQL, no raw SQL, no
``strftime``, no ``func.now()``, no row-value comparison syntax (its IN/
comparison support is uneven across dialects) — the two-branch ``or_``/``and_``
form is used instead.
"""

from dataclasses import dataclass

from alembic.migration import MigrationContext
from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.services import merge
from app.services.merge import ExchangeRecord

# The six REFERENCE kinds, in FK-dependency order (a client applying the file
# top-to-bottom never hits a missing parent). Deliberately EXCLUDES the two
# ledger kinds (operations, cash movements) — pull is reference-only (locked
# semantic 1). Models are derived from ``merge.KIND_TO_MODEL`` so the two modules
# cannot drift.
PULL_KINDS: tuple[str, ...] = (
    "warehouse",
    "product",
    "customer",
    "dictionary",
    "batch",
    "sale",
)

# Per-kind cursor column. Every reference model carries ``updated_at`` EXCEPT
# ``Sale``, which has only ``created_at`` — a uniform ``updated_at`` query would
# raise on sales (Pitfall 8).
CURSOR_COLUMN: dict[str, str] = {
    "warehouse": "updated_at",
    "product": "updated_at",
    "customer": "updated_at",
    "dictionary": "updated_at",
    "batch": "updated_at",
    "sale": "created_at",  # Sale has no updated_at column (Pitfall 8)
}

DEFAULT_PULL_LIMIT: int = 500
MAX_PULL_LIMIT: int = 2000


@dataclass(frozen=True)
class PullPage:
    """One page of reference records + the composite cursor to resume from.

    A named object (not a bare tuple) so the two cursor halves can never be
    unpacked in the wrong order. ``next_since``/``next_after_id`` are the cursor
    value and ``id`` of the LAST record on the page, or None when the page is
    empty — the client re-requests with ``since=next_since&after_id=next_after_id``
    until it receives fewer than ``limit`` records.
    """

    records: list[ExchangeRecord]
    next_since: str | None
    next_after_id: str | None


def _row_to_record(kind: str, row) -> ExchangeRecord:
    """Build an :class:`ExchangeRecord` from an ORM reference row (schema-derived).

    The data dict is built from ``merge.KIND_TO_FIELDS[kind]`` (the model's own
    mapper columns) so a newly added column ships automatically — no hand-kept
    column list can drift from the schema.
    """
    data = {field: getattr(row, field) for field in merge.KIND_TO_FIELDS[kind]}
    return ExchangeRecord(kind=kind, data=data)


def _clamp_limit(limit: int | None) -> int:
    """Clamp ``limit`` into ``1..MAX_PULL_LIMIT`` (DEFAULT when None or <= 0)."""
    if limit is None or limit <= 0:
        return DEFAULT_PULL_LIMIT
    return min(limit, MAX_PULL_LIMIT)


def _resume_kind(session: Session, after_id: str) -> str | None:
    """Which PULL kind owns ``after_id`` (a globally-unique UUID PK), or None.

    The composite cursor carries only ``(since, after_id)`` — no kind. Because
    the paging loop advances to the next kind ONLY once the current kind is
    exhausted, the resume kind is recovered here by an indexed PK membership
    probe, so the loop can apply the strictly-greater ``id`` comparison to the
    right kind, plainly re-scan the kinds AFTER it, and skip the fully-drained
    kinds BEFORE it. At most six tiny indexed lookups; typically one.
    """
    for kind in PULL_KINDS:
        model = merge.KIND_TO_MODEL[kind]
        if session.scalar(select(model.id).where(model.id == after_id)) is not None:
            return kind
    return None


def collect_reference_records(
    session: Session,
    *,
    since: str | None,
    after_id: str | None,
    limit: int,
) -> PullPage:
    """Collect one page of reference records after the composite cursor (PURE-DB).

    **The cursor is COMPOSITE ``(cursor_column, id)``.** A single-column timestamp
    cursor cannot terminate: ``next_since`` is inclusive so no boundary row is
    dropped, so a run of identical timestamps longer than ``limit`` would return
    the same page forever. The ``id`` tie-break is what guarantees forward
    progress (RESEARCH cites the bulk edit that stamps many rows with one
    identical timestamp as the reason the comparison is inclusive).

    Kinds are processed in :data:`PULL_KINDS` (FK-dependency) order. The loop
    advances to the next kind only once the current one is exhausted, so a resume
    position is fully described by ``(since, resume_kind, after_id)`` where
    ``resume_kind`` is recovered from ``after_id`` (:func:`_resume_kind`):

    * kinds BEFORE the resume kind were already fully delivered → SKIPPED (never
      re-scanned, so paging cannot loop between kinds);
    * the resume kind gets the strictly-greater COMPOSITE predicate
      ``or_(col > since, and_(col == since, id > after_id))`` — strictly greater on
      the composite key while inclusive on the timestamp alone;
    * kinds AFTER the resume kind have not started → full scan (no lower bound).

    First-page shapes:

    * ``since`` is None → no ``where`` clause (deliver from the top of every kind);
    * ``since`` set, ``after_id`` None → ``where(col >= since)`` on every kind
      (INCLUSIVE, so a row sharing the boundary timestamp is never dropped; the
      client's Phase 27 reference upsert is idempotent, so a small overlap is
      free). A lone ``after_id`` with no ``since`` is meaningless and is ignored.

    Soft-deleted rows are INCLUDED (no ``deleted_at IS NULL`` filter): a tombstone
    is exactly what the client needs to learn about a deletion, and the Phase 27
    upsert carries an inline ``deleted_at`` through already.
    """
    limit = _clamp_limit(limit)

    resume_kind: str | None = None
    if since is not None and after_id is not None:
        resume_kind = _resume_kind(session, after_id)
    is_paging = resume_kind is not None  # continuation request, not a first page

    records: list[ExchangeRecord] = []
    next_since: str | None = None
    next_after_id: str | None = None
    remaining = limit
    # True once we are at or past the resume kind (or immediately, when there is
    # no resume kind — a first page or an unresolved/ignored after_id).
    passed_resume = resume_kind is None

    for kind in PULL_KINDS:
        if remaining <= 0:
            break
        model = merge.KIND_TO_MODEL[kind]
        column = getattr(model, CURSOR_COLUMN[kind])
        stmt = select(model).order_by(column, model.id).limit(remaining)

        if not passed_resume:
            if kind != resume_kind:
                continue  # fully drained on an earlier page — skip
            # The resume kind: strictly greater on the composite key, inclusive on
            # the timestamp. Portable two-branch or_/and_ form, no row-value syntax.
            stmt = stmt.where(
                or_(column > since, and_(column == since, model.id > after_id))
            )
            passed_resume = True
        elif since is not None and not is_paging:
            # FIRST incremental page only: lower-bound every kind by `since`.
            # On a paging continuation, kinds after the resume kind have not started
            # and must be full-scanned (no lower bound) — the advanced `since` belongs
            # to the resume kind's timeline, not theirs. Over-delivery of already-known
            # reference rows is safe: the Phase 27 reference upsert is idempotent.
            stmt = stmt.where(column >= since)

        rows = session.scalars(stmt).all()
        for row in rows:
            records.append(_row_to_record(kind, row))
            next_since = getattr(row, CURSOR_COLUMN[kind])
            next_after_id = row.id
        remaining -= len(rows)

    if not records:
        return PullPage(records=[], next_since=None, next_after_id=None)
    return PullPage(records=records, next_since=next_since, next_after_id=next_after_id)


def current_schema_version(session: Session) -> str:
    """The live Alembic revision, or "" when the schema was built by create_all.

    Derived from the DB (never a hardcoded revision) so Phase 30's OFF-07
    schema-version gate reads a truthful value. Test fixtures build the schema
    with ``Base.metadata.create_all`` and therefore have no ``alembic_version``
    table, so ``get_current_revision`` returns None — ``parse_exchange`` accepts an
    empty ``schema_version``, so the "" fallback is safe.
    """
    context = MigrationContext.configure(session.connection())
    return context.get_current_revision() or ""

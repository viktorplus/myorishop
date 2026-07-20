"""Pure state + presentation layer for the online sync client (Phase 29, Plan 02).

Everything here is a plain function over a SQLAlchemy `Session` — NO network, NO
httpx. The Plan-03 network driver consumes these helpers so its own code only has
to wire push/pull:

- `SyncResult` — the value object the driver returns and the formatter renders.
- `get_or_create_sync_state` / `record_sync_result` — the single-row `sync_state`
  (id=1) persistence (D-10). The result is written from ONE exit point after every
  attempt, so a failure is recorded as reliably as a success and survives an app
  restart. Portable SELECT-then-INSERT — no dialect upsert.
- `read_autosync_config` — reads the D-15 auto-sync toggle + interval FRESH from
  the row (so flipping the toggle takes effect on the next tick, D-08) and clamps
  the interval into `MIN_INTERVAL_SECONDS..MAX_INTERVAL_SECONDS`.
- `unsynced_count` — the D-11 badge: `COUNT(*) WHERE synced_at IS NULL` across
  `Operation` + `CashMovement` (the caller hides the badge at 0).
- `format_sync_message` — the LOCKED D-12 Russian result strings, with the
  last-sync line rendered in `settings.display_tz` (Europe/Moscow).

Security (T-29-07): `format_sync_message` renders ONLY the fixed D-12 strings plus
integer counts — never raw server error bytes and never the sync token. Callers
must pass a fixed RU string as `last_result`, never raw exception text.
"""

import threading
from dataclasses import dataclass

import httpx
from sqlalchemy import func, insert, select, update
from sqlalchemy.orm import Session

from app.config import settings
from app.core import iso_to_local, utcnow_iso
from app.db import SessionLocal
from app.models import (
    Batch,
    CashMovement,
    Customer,
    Operation,
    Product,
    Sale,
    SyncState,
    Warehouse,
)
from app.services import merge
from app.services.ledger import recompute_derived
from app.services.sync import DEFAULT_PULL_LIMIT, current_schema_version

# D-15: the interval is clamped into this range in the service (a single reseller
# needs neither sub-minute sync nor an unbounded gap). 300s (5 min) is the default.
MIN_INTERVAL_SECONDS = 60
MAX_INTERVAL_SECONDS = 3600
DEFAULT_INTERVAL_SECONDS = 300

# Defensive truncation width for last_result — mirrors SyncState.last_result
# String(300) so an over-long RU string can never overflow the column.
_LAST_RESULT_MAX = 300


@dataclass(frozen=True)
class SyncResult:
    """The outcome of one sync attempt — returned by the Plan-03 driver, rendered
    by `format_sync_message`.

    `status` is one of: ``ok`` | ``partial`` | ``offline`` | ``error`` |
    ``locked`` | ``not_configured``.
    """

    status: str
    pushed: int = 0
    pushed_total: int = 0
    pulled: int = 0


def get_or_create_sync_state(session: Session) -> SyncState:
    """Return the id=1 `sync_state` singleton, inserting it with defaults if absent.

    Portable SELECT-then-INSERT (no `INSERT OR REPLACE`) — this is the D-10
    single-row bookkeeping row. Flushes (not commits) the new row so the caller's
    transaction stays in charge.
    """
    row = session.get(SyncState, 1)
    if row is None:
        row = SyncState(
            id=1,
            auto_enabled=0,
            auto_interval_seconds=DEFAULT_INTERVAL_SECONDS,
        )
        session.add(row)
        session.flush()
    return row


def record_sync_result(
    session: Session,
    *,
    status: str,
    last_result: str,
    last_sync_at: str | None,
) -> None:
    """Upsert the D-10 result columns (last_status / last_result / last_sync_at)
    onto the id=1 row.

    Does NOT commit — the driver (Plan 03) owns the transaction around its single
    exit point (D-10 "written in a finally"), so a failure is recorded as reliably
    as a success. `last_result` MUST already be a fixed RU string (never raw
    exception text, T-29-07); it is defensively truncated to the column width.
    """
    row = get_or_create_sync_state(session)
    row.last_status = status
    row.last_result = last_result[:_LAST_RESULT_MAX]
    row.last_sync_at = last_sync_at


def _clamp_interval(value: int | None) -> int:
    """Force an interval into `MIN_INTERVAL_SECONDS..MAX_INTERVAL_SECONDS` (D-15).

    A None/invalid value falls back to `DEFAULT_INTERVAL_SECONDS`.
    """
    if value is None:
        return DEFAULT_INTERVAL_SECONDS
    try:
        seconds = int(value)
    except (TypeError, ValueError):
        return DEFAULT_INTERVAL_SECONDS
    return max(MIN_INTERVAL_SECONDS, min(MAX_INTERVAL_SECONDS, seconds))


def read_autosync_config(session: Session) -> tuple[bool, int]:
    """Return `(enabled, interval_seconds)` read FRESH from the `sync_state` row.

    Read fresh each call (D-08 — flipping the toggle / changing the interval takes
    effect on the next tick) and clamp the interval into 60..3600 (D-15).
    """
    row = get_or_create_sync_state(session)
    return bool(row.auto_enabled), _clamp_interval(row.auto_interval_seconds)


def unsynced_count(session: Session) -> int:
    """The D-11 badge: `COUNT(*) WHERE synced_at IS NULL` across the ledger.

    Sums the unsynced `Operation` + `CashMovement` rows. Backed by the Plan-01
    `ix_operations_unsynced` / `ix_cash_movements_unsynced` partial indexes so the
    count stays cheap as history grows (T-29-09). The caller hides the badge at 0.
    """
    ops = (
        session.scalar(
            select(func.count())
            .select_from(Operation)
            .where(Operation.synced_at.is_(None))
        )
        or 0
    )
    cash = (
        session.scalar(
            select(func.count())
            .select_from(CashMovement)
            .where(CashMovement.synced_at.is_(None))
        )
        or 0
    )
    return ops + cash


def format_sync_message(
    result: SyncResult, sync_state: SyncState | None, tz: str
) -> tuple[str, str]:
    """Render the LOCKED D-12 Russian `(status_message, last_sync_line)` pair.

    `status_message` is chosen from `result.status` + the integer counts, using the
    D-12 strings VERBATIM. `last_sync_line` renders the stored UTC ISO
    `sync_state.last_sync_at` in `tz` (Europe/Moscow), or "Ещё не синхронизировано"
    when it is None.

    T-29-07 / V7: ONLY these fixed strings + integer counts ever cross this
    boundary — raw server error bytes and the sync token can never be interpolated.
    """
    status = result.status
    if status == "ok":
        if result.pushed == 0 and result.pulled == 0:
            message = "Синхронизировано, изменений нет"
        else:
            message = (
                f"Синхронизировано: отправлено {result.pushed}, "
                f"получено {result.pulled}"
            )
    elif status == "partial":
        message = (
            f"Синхронизировано частично: отправлено {result.pushed} "
            f"из {result.pushed_total}"
        )
    elif status == "offline":
        message = "Нет связи с сервером"
    elif status == "locked":
        # D-09: a manual click landed while a tick is already running.
        message = "Синхронизация уже выполняется"
    elif status == "not_configured":
        # SRV-03: blank server URL / token — a fresh install is a no-op.
        message = "Синхронизация не настроена"
    else:
        # `error` and any unexpected status collapse to the generic D-12 error.
        message = "Ошибка сервера, попробуйте позже"

    last_sync_at = sync_state.last_sync_at if sync_state is not None else None
    if last_sync_at:
        last_sync_line = f"Последняя синхронизация: {iso_to_local(last_sync_at, tz)}"
    else:
        last_sync_line = "Ещё не синхронизировано"
    return message, last_sync_line


# ---------------------------------------------------------------------------
# Plan 03: the network driver (push + pull) reused by the manual button (Plan
# 04) and the background tick (Plan 05). The algorithms — wire format, merge,
# cursor — already exist and are tested (Phases 27-28); this only wires the
# outbound half plus the two client-side topology decisions D-13 and D-14.
# ---------------------------------------------------------------------------

# D-09: the ONE single-run guard shared by the manual click and the background
# tick — acquired non-blocking so a second caller skips instead of stacking.
_run_lock = threading.Lock()

# D-05 / RESEARCH A1: a strict timeout so an unreachable server can only stall
# for this window (short connect fails fast offline; longer read tolerates a
# larger pull page). The whole sync is bounded by (connect + read) × pages.
SYNC_TIMEOUT = httpx.Timeout(connect=3.0, read=10.0, write=10.0, pool=3.0)

# The two append-only ledger kinds this driver pushes, in FK-insert order.
_LEDGER: tuple[tuple[str, type], ...] = (
    ("operation", Operation),
    ("cash_movement", CashMovement),
)


def build_sync_client() -> httpx.Client:
    """Build the outbound sync `httpx.Client` (base URL + strict timeout).

    The Bearer `sync_token` is NOT baked in here — it travels per-request in the
    `Authorization` header only (never a query string, never logged — T-29-04).
    """
    return httpx.Client(base_url=settings.sync_server_url, timeout=SYNC_TIMEOUT)


def _load_by_ids(session: Session, model: type, ids: set[str]) -> list:
    """Load rows whose UUID PK is in `ids` (chunked under SQLite's ~999 cap)."""
    if not ids:
        return []
    id_list = list(ids)
    rows: list = []
    for start in range(0, len(id_list), merge._IN_CHUNK):
        chunk = id_list[start : start + merge._IN_CHUNK]
        rows.extend(session.scalars(select(model).where(model.id.in_(chunk))).all())
    return rows


def _collect_push_records(
    session: Session,
) -> tuple[list[merge.ExchangeRecord], dict[str, list[str]]]:
    """Collect the unsynced ledger rows + their D-13 reference closure to push.

    Selects every `Operation` / `CashMovement` with `synced_at IS NULL`, records
    their ids per kind (to stamp after the server accepts), then builds the D-13
    transitive FK closure: the `product`/`batch`/`sale` parents of those
    operations, the `sale` parents of those cash movements, each sale's
    `customer`, and each batch's `product` + `warehouse`. Every row is projected
    to an `ExchangeRecord` restricted to `merge.KIND_TO_FIELDS[kind]`, emitted in
    FK-dependency order (`merge._REFERENCE_INSERT_ORDER` then the two ledger
    kinds). Over-including reference rows is safe — the server upsert is
    idempotent/server-wins (D-13). Users are NOT a sync kind, so `author_id` is
    carried verbatim but no `user` record is ever emitted.
    """
    ids: dict[str, list[str]] = {"operation": [], "cash_movement": []}
    unsynced_ops = session.scalars(
        select(Operation).where(Operation.synced_at.is_(None))
    ).all()
    unsynced_cash = session.scalars(
        select(CashMovement).where(CashMovement.synced_at.is_(None))
    ).all()
    ids["operation"] = [row.id for row in unsynced_ops]
    ids["cash_movement"] = [row.id for row in unsynced_cash]

    product_ids: set[str] = set()
    batch_ids: set[str] = set()
    sale_ids: set[str] = set()
    warehouse_ids: set[str] = set()
    customer_ids: set[str] = set()
    for op in unsynced_ops:
        if op.product_id:
            product_ids.add(op.product_id)
        if op.batch_id:
            batch_ids.add(op.batch_id)
        if op.sale_id:
            sale_ids.add(op.sale_id)
    for cash in unsynced_cash:
        if cash.sale_id:
            sale_ids.add(cash.sale_id)

    sales = _load_by_ids(session, Sale, sale_ids)
    for sale in sales:
        if sale.customer_id:
            customer_ids.add(sale.customer_id)
    batches = _load_by_ids(session, Batch, batch_ids)
    for batch in batches:
        product_ids.add(batch.product_id)
        warehouse_ids.add(batch.warehouse_id)
    warehouses = _load_by_ids(session, Warehouse, warehouse_ids)
    products = _load_by_ids(session, Product, product_ids)
    customers = _load_by_ids(session, Customer, customer_ids)

    rows_by_kind: dict[str, list] = {
        "warehouse": warehouses,
        "product": products,
        "customer": customers,
        "dictionary": [],
        "batch": batches,
        "sale": sales,
    }

    records: list[merge.ExchangeRecord] = []

    def _emit(kind: str, rows: list) -> None:
        for row in rows:
            data = {field: getattr(row, field) for field in merge.KIND_TO_FIELDS[kind]}
            records.append(merge.ExchangeRecord(kind=kind, data=data))

    for kind in merge._REFERENCE_INSERT_ORDER:
        _emit(kind, rows_by_kind.get(kind, []))
    _emit("operation", unsynced_ops)
    _emit("cash_movement", unsynced_cash)

    return records, ids


def run_sync_once(session: Session, *, client: httpx.Client) -> SyncResult:
    """One full push+pull sync — the ONE driver (reused by manual + tick).

    Steps: (1) collect unsynced ledger rows + the D-13 reference closure; (2)
    serialize via `merge.serialize_exchange`; (3) POST to `/api/sync/push` with
    the Bearer token; (4) stamp `synced_at` ONLY after `raise_for_status()`
    (Pitfall 3); (5) paginate `/api/sync/pull` applying the D-14 client upsert.

    Offline-safe (SYNC-06 / SRV-03): a blank server URL/token short-circuits to
    `not_configured`; a transport error (offline/timeout) maps to `offline`; a
    non-2xx push maps to `error`; a push that landed but a pull that failed maps
    to `partial`. It NEVER re-raises `httpx` errors to the caller. The `_run_lock`
    is held by the CALLER (`run_sync_tick` / the Plan-04 handler), not here.
    """
    if not settings.sync_server_url or not settings.sync_token:
        return SyncResult(status="not_configured")

    records, ids = _collect_push_records(session)
    pushed_total = len(ids["operation"]) + len(ids["cash_movement"])
    body = "\n".join(
        merge.serialize_exchange(
            records,
            schema_version=current_schema_version(session),
            source_device_id=settings.device_id,
            generated_at=utcnow_iso(),
        )
    ).encode("utf-8")
    auth = {"Authorization": f"Bearer {settings.sync_token}"}

    try:
        response = client.post(
            "/api/sync/push",
            content=body,
            headers={"Content-Type": "application/x-ndjson", **auth},
        )
        response.raise_for_status()
    except httpx.HTTPStatusError:
        # A non-2xx: rows stay unsynced (Pitfall 3), retried next sync.
        return SyncResult(status="error", pushed=0, pushed_total=pushed_total)
    except httpx.HTTPError:
        # Offline / timeout / transport error: never raised out (SYNC-06).
        return SyncResult(status="offline", pushed=0, pushed_total=pushed_total)

    # Stamp synced_at ONLY after the 2xx (migration 0018 permits SET synced_at).
    stamp = utcnow_iso()
    pushed = 0
    for kind, model in _LEDGER:
        if ids[kind]:
            session.execute(
                update(model).where(model.id.in_(ids[kind])).values(synced_at=stamp)
            )
            pushed += len(ids[kind])
    session.commit()

    # (5) Pull server-authoritative reference data down (D-14 client upsert). A
    # push that landed but a pull that failed is `partial` — the push is durable.
    try:
        pulled = _pull_all(session, client)
    except httpx.HTTPError:
        return SyncResult(status="partial", pushed=pushed, pushed_total=pushed_total)

    return SyncResult(
        status="ok", pushed=pushed, pushed_total=pushed_total, pulled=pulled
    )


def _apply_pull_page(session: Session, batch: merge.ExchangeBatch) -> int:
    """Apply one pulled page with the D-14 client reference upsert (server-wins).

    For each reference kind in FK-dependency order, split the page's records into
    (new by UUID) and (existing by UUID). NEW rows insert via the quantity-zeroing
    projection (`merge._reference_row`). EXISTING rows are UPDATED with the
    server's values for every column EXCEPT `id` and the cached `quantity` — the
    server wins on master data, while stock stays LOCAL-ledger-derived (Pitfall
    2 / D-14). This is the OPPOSITE of `merge._upsert_reference` (which discards
    existing rows) and is the one genuinely new algorithm in the phase. After the
    upserts, `recompute_derived` rebuilds Product/Batch quantity from the LOCAL
    ledger. Ledger rows are never touched on pull (pull is reference-only).
    """
    buckets: dict[str, list[dict]] = {
        kind: [] for kind in merge._REFERENCE_INSERT_ORDER
    }
    for record in batch.records:
        if record.kind in buckets:
            buckets[record.kind].append(record.data)

    applied = 0
    for kind in merge._REFERENCE_INSERT_ORDER:
        rows = buckets[kind]
        if not rows:
            continue
        model = merge.KIND_TO_MODEL[kind]
        new_rows, _ = merge._partition_new(session, model, rows)
        new_ids = {row["id"] for row in new_rows}
        existing_rows = [row for row in rows if row["id"] not in new_ids]

        if new_rows:
            session.execute(
                insert(model), [merge._reference_row(kind, row) for row in new_rows]
            )
            applied += len(new_rows)

        if existing_rows:
            # Server wins on master data; never overwrite the local-derived
            # `quantity` cache nor the immutable `id` (D-14).
            update_fields = merge.KIND_TO_FIELDS[kind] - {"id", "quantity"}
            for row in existing_rows:
                values = {field: row.get(field) for field in update_fields}
                session.execute(
                    update(model).where(model.id == row["id"]).values(**values)
                )
                applied += 1

    # Rebuild derived stock from the LOCAL ledger (never the server's cache).
    recompute_derived(session)
    return applied


def _pull_all(session: Session, client: httpx.Client) -> int:
    """Paginate `/api/sync/pull` with the composite cursor, applying each page.

    The cursor is COMPOSITE `(since, after_id)`: BOTH the `X-Sync-Next-Since` and
    `X-Sync-Next-After-Id` response headers are echoed back as query params —
    sending only `since` loops forever across a run of identical timestamps
    (RESEARCH Pattern 3). Each page is applied in ONE owned transaction (mirroring
    the push route) so a poisoned page rolls back cleanly (T-29-05). Stops when a
    page returns fewer than `DEFAULT_PULL_LIMIT` records or there is no next cursor.
    """
    since: str | None = None
    after_id: str | None = None
    pulled = 0
    auth = {"Authorization": f"Bearer {settings.sync_token}"}
    while True:
        params = {
            key: value
            for key, value in (("since", since), ("after_id", after_id))
            if value
        }
        response = client.get("/api/sync/pull", params=params or None, headers=auth)
        response.raise_for_status()
        batch = merge.parse_exchange(response.text.splitlines())
        if batch.records:
            session.rollback()  # discard any autobegun read txn
            with session.begin():
                _apply_pull_page(session, batch)
            pulled += len(batch.records)
        next_since = response.headers.get("x-sync-next-since")
        next_after_id = response.headers.get("x-sync-next-after-id")
        if len(batch.records) < DEFAULT_PULL_LIMIT or not next_since:
            break
        since, after_id = next_since, next_after_id
    return pulled


def run_sync_tick() -> None:
    """Background-tick entry point: lock + fresh Session + client + record result.

    Acquires `_run_lock` non-blocking; if a manual click / another tick already
    holds it, returns immediately (D-09). Otherwise opens a FRESH `SessionLocal()`
    session, and — when auto-sync is enabled (read fresh, D-15) — builds a client,
    runs one sync, and records the result via the D-10 single exit point in a
    `finally`. Never raises: an offline sync is swallowed into the recorded result.
    """
    if not _run_lock.acquire(blocking=False):
        return  # D-09: another run is already in progress.
    try:
        with SessionLocal() as session:
            enabled, _ = read_autosync_config(session)
            if not enabled:
                return  # D-15: auto-sync disabled — this tick is a no-op.
            client = build_sync_client()
            try:
                result = run_sync_once(session, client=client)
            finally:
                client.close()
            row = get_or_create_sync_state(session)
            last_sync_at = (
                utcnow_iso() if result.status in ("ok", "partial") else row.last_sync_at
            )
            message, _ = format_sync_message(result, row, settings.display_tz)
            record_sync_result(
                session,
                status=result.status,
                last_result=message,
                last_sync_at=last_sync_at,
            )
            session.commit()
    finally:
        _run_lock.release()

"""SQLAlchemy 2.0 models (D-05..D-10): sync-ready conventions locked here.

UUID4 TEXT primary keys, integer *_cents money, UTC ISO-8601 TEXT timestamps.
Schema source of truth is Alembic migration 0001 — create_all is for test
fixtures only.
"""

from sqlalchemy import (
    JSON,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.core import new_id, utcnow_iso

# Pitfall 4: SQLite allows unnamed constraints; future batch migrations
# cannot target them for drop. Name everything from day one.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

# Phase 1 shipped "correction"; Phase 2 adds the qty_delta=0 audit types
# (RESEARCH Finding 5 — no CHECK constraint on operations.type, no migration).
OPERATION_TYPES = (
    "receipt",
    "sale",
    "writeoff",
    "return",
    "correction",
    "price_change",
    "product_created",
    "product_edited",
)

# Phase 5 (D-02/D-03): latin reason_code -> RU label for write-offs. Stored in
# Operation.payload["reason_code"]; "other" is the free-text-note escape hatch.
# This is also the exact server-side allow-list write-offs validate against.
WRITEOFF_REASONS = {
    "damaged": "Брак",
    "expired": "Просрочка",
    "lost": "Потеря",
    "personal": "Личное использование",
    "gift": "Подарок",
    "other": "Прочее",
}

# Phase 5 (D-16): latin operation type -> RU label for the /history "Тип" column.
# Covers every OPERATION_TYPES member.
OPERATION_TYPE_LABELS = {
    "receipt": "Приход",
    "sale": "Продажа",
    "writeoff": "Списание",
    "return": "Возврат",
    "correction": "Корректировка",
    "price_change": "Изменение цены",
    "product_created": "Создан",
    "product_edited": "Изменён",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class Product(Base):
    __tablename__ = "products"
    # WR-04 / D-19: code unique among ACTIVE products only — a partial unique
    # index is the DB backstop for the SELECT-then-INSERT check in the
    # catalog service (double-submit / two-tab race). Deleted products may
    # share codes, hence the WHERE clause. Portable to PostgreSQL.
    __table_args__ = (
        Index(
            "uq_products_code_active",
            "code",
            unique=True,
            sqlite_where=text("deleted_at IS NULL"),
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    code: Mapped[str | None] = mapped_column(String(20), index=True)
    name: Mapped[str] = mapped_column(String(200))
    # D-19: optional free-text category (datalist suggestions in UI).
    category: Mapped[str | None] = mapped_column(String(100))
    # D-19: three optional prices, integer cents only (conventions test).
    cost_cents: Mapped[int | None] = mapped_column(Integer)
    sale_cents: Mapped[int | None] = mapped_column(Integer)
    catalog_cents: Mapped[int | None] = mapped_column(Integer)
    # D-06 (Phase 7): optional minimum sale price guardrail; NULL = no floor
    # set (NO global-settings fallback, unlike low_stock_threshold/stale_days).
    # Checked with is not None, never a bare "or".
    min_sale_cents: Mapped[int | None] = mapped_column(Integer)
    # D-04/D-05 (Phase 6): per-product report thresholds; NULL = use
    # settings.{low_stock_threshold,stale_days}.
    low_stock_threshold: Mapped[int | None] = mapped_column(Integer)
    stale_days: Mapped[int | None] = mapped_column(Integer)
    # D-27: lowercase shadow of name, maintained by the SERVICE layer via
    # Python str.lower() — SQLite lower()/LIKE cannot fold Cyrillic.
    name_lc: Mapped[str | None] = mapped_column(String(200), index=True)
    # D-09: cached projection of SUM(operations.qty_delta); recomputable.
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[str] = mapped_column(String(32), default=utcnow_iso)
    updated_at: Mapped[str] = mapped_column(String(32), default=utcnow_iso, onupdate=utcnow_iso)
    # D-10: soft delete only; no hard deletes.
    deleted_at: Mapped[str | None] = mapped_column(String(32))


class Warehouse(Base):
    """Physical stock location (WH-01): standalone table, no FK wiring yet.

    D-01/D-02: this table has no FK to/from `products`/`operations` in
    Phase 8 — `Batch.warehouse_id` (Phase 9) is the real stock link.
    D-03: the migration's seeded default row is the stable identity
    Phase 9's legacy-batch migration will point at. D-04: no unique
    constraint on `name` — duplicate names are allowed.
    """

    __tablename__ = "warehouses"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    address: Mapped[str | None] = mapped_column(String(300))
    created_at: Mapped[str] = mapped_column(String(32), default=utcnow_iso)
    updated_at: Mapped[str] = mapped_column(String(32), default=utcnow_iso, onupdate=utcnow_iso)
    # D-05: soft delete only; no hard deletes (matches Product convention).
    deleted_at: Mapped[str | None] = mapped_column(String(32))


class Batch(Base):
    """Stock-holding unit (LOT-01): one product x one warehouse x one lot.

    D-03: NO deleted_at and NO standalone CRUD — a batch simply leaves the
    pickers when its remaining quantity hits 0 (no soft-delete lifecycle,
    unlike Product/Warehouse). is_legacy=1 is set ONLY by migration 0008's
    seed (D-13/D-14) and marks the per-product "Остаток до внедрения партий"
    batch, so returns fallback (D-08) and the rebuild_stock NULL-bucket pass
    can find it without fragile string matching.
    """

    __tablename__ = "batches"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    product_id: Mapped[str] = mapped_column(
        ForeignKey("products.id"), nullable=False, index=True
    )
    warehouse_id: Mapped[str] = mapped_column(
        ForeignKey("warehouses.id"), nullable=False
    )
    # LOT-03: optional ISO yyyy-mm-dd expiry; TEXT sorts lexicographically ==
    # chronologically (input type=date always posts ISO regardless of locale).
    expiry: Mapped[str | None] = mapped_column(String(10))
    # D-02: sale-price snapshot frozen at batch creation; NULL for legacy.
    price_cents: Mapped[int | None] = mapped_column(Integer)
    location: Mapped[str | None] = mapped_column(String(100))  # WH-02 free-text tag
    comment: Mapped[str | None] = mapped_column(String(200))  # LOT-04
    # UAT test 1 symptom 3: auto-generated «{product.name} — {creation date}»
    # label, snapshotted at batch creation; NULL for legacy/pre-0009 batches.
    name: Mapped[str | None] = mapped_column(String(200))
    # D-11: cached projection of SUM(operations.qty_delta WHERE batch_id=...);
    # recomputable (mirror Product.quantity).
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # D-13/D-14: 1 only for the migration-seeded per-product legacy batch.
    is_legacy: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[str] = mapped_column(String(32), default=utcnow_iso)
    updated_at: Mapped[str] = mapped_column(String(32), default=utcnow_iso, onupdate=utcnow_iso)


class Dictionary(Base):
    """Code -> name reference (CAT-02), helper only; products stay the truth.

    PD-1: UUID String(36) surrogate PK + UNIQUE(code) — NOT code-as-PK.
    The frozen Phase 1 conventions test requires every PK to be a 36-char
    UUID string, and D-05 sync-readiness wants UUID rows everywhere.
    """

    __tablename__ = "dictionary"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    code: Mapped[str] = mapped_column(String(20), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[str] = mapped_column(String(32), default=utcnow_iso)
    updated_at: Mapped[str] = mapped_column(String(32), default=utcnow_iso, onupdate=utcnow_iso)


class Operation(Base):
    """Append-only ledger row (D-08) — immutability enforced by DB triggers."""

    __tablename__ = "operations"
    __table_args__ = (UniqueConstraint("device_id", "seq"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    type: Mapped[str] = mapped_column(String(20), nullable=False)
    product_id: Mapped[str] = mapped_column(
        ForeignKey("products.id"), nullable=False, index=True
    )
    qty_delta: Mapped[int] = mapped_column(Integer, nullable=False)  # signed
    unit_cost_cents: Mapped[int | None] = mapped_column(Integer)
    unit_price_cents: Mapped[int | None] = mapped_column(Integer)
    payload: Mapped[dict | None] = mapped_column(JSON)  # type-specific fields
    # D-03: nullable link to the sales header this line belongs to. Set at
    # INSERT time only (via record_operation) — the operations_no_update
    # trigger ABORTs any later UPDATE, so this can never be attached after
    # the fact. Non-sale ops leave this NULL.
    sale_id: Mapped[str | None] = mapped_column(
        ForeignKey("sales.id", name="fk_operations_sale_id_sales"), index=True
    )
    # D-10/D-15: nullable link to the Batch this ledger line touched. Set at
    # INSERT time only (via record_operation) — the operations_no_update
    # trigger ABORTs any later UPDATE. NULL means a pre-Phase-9 (legacy) row,
    # resolved display-side. Bare native column in migration 0008 (no inline
    # FK — the sale_id precedent); the ORM ForeignKey here gives insert
    # ordering + PostgreSQL portability.
    batch_id: Mapped[str | None] = mapped_column(
        ForeignKey("batches.id", name="fk_operations_batch_id_batches"), index=True
    )
    device_id: Mapped[str] = mapped_column(String(36), nullable=False)
    seq: Mapped[int] = mapped_column(Integer, nullable=False)  # per-device counter
    created_at: Mapped[str] = mapped_column(String(32), nullable=False)  # UTC ISO text
    created_by: Mapped[str] = mapped_column(String(100), nullable=False)  # FND-03
    synced_at: Mapped[str | None] = mapped_column(String(32))  # v2 sync cursor


class Customer(Base):
    """Customer profile (CST-01): optional link target for a sale header.

    A2: no unique constraint — walk-in quick-create tolerates duplicate
    names/consultant numbers. search_lc is a Cyrillic-safe shadow of
    "name surname consultant", maintained by the SERVICE layer via Python
    str.lower() — SQLite lower()/LIKE cannot fold Cyrillic (mirrors
    Product.name_lc).
    """

    __tablename__ = "customers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    surname: Mapped[str | None] = mapped_column(String(200))
    consultant_number: Mapped[str | None] = mapped_column(String(50))
    search_lc: Mapped[str | None] = mapped_column(String(400), index=True)
    created_at: Mapped[str] = mapped_column(String(32), default=utcnow_iso)
    updated_at: Mapped[str] = mapped_column(String(32), default=utcnow_iso, onupdate=utcnow_iso)


class Sale(Base):
    """Sale header (D-03): groups N `sale` operations for one basket.

    The header carries NO qty/price — stock is computed ONLY from ledger
    sale operations. customer_id is nullable (D-04: walk-in sale is valid).
    device_id is nullable sync provenance (RESEARCH Open Q1, resolved).
    """

    __tablename__ = "sales"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    customer_id: Mapped[str | None] = mapped_column(
        ForeignKey("customers.id", name="fk_sales_customer_id_customers"), index=True
    )
    created_at: Mapped[str] = mapped_column(String(32), nullable=False)
    created_by: Mapped[str] = mapped_column(String(100), nullable=False)
    device_id: Mapped[str | None] = mapped_column(String(36))

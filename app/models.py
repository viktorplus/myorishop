"""SQLAlchemy 2.0 models (D-05..D-10): sync-ready conventions locked here.

UUID4 TEXT primary keys, integer *_cents money, UTC ISO-8601 TEXT timestamps.
Schema source of truth is Alembic migration 0001 — create_all is for test
fixtures only.
"""

from sqlalchemy import (
    JSON,
    CheckConstraint,
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
    "transfer",
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

# Phase 15 (D-00a/D-03): system cash categories used by the auto sale-credit /
# return-debit write paths. "return" is kept distinct from Phase 16's
# manual-withdrawal categories so the Phase 16/17 history/report views can
# separate system-generated movements from operator-entered ones.
# Phase 16 (D-01/D-01a/D-01b): manual movements are modeled by EXTENDING this
# dict — no new `type` column, no migration. Direction lives in the
# amount_cents sign (withdrawal negative, deposit positive); kind lives in the
# category-key prefix so the 4 coarse history buckets derive trivially
# (CASH_BUCKETS below). Every key MUST be <= 20 chars (CashMovement.category
# is String(20); "withdrawal_utilities" is exactly 20). This is also the exact
# server-side allow-list record_cash_movement / record_manual_movement gate on.
CASH_CATEGORIES = {
    "sale": "Продажа",
    "return": "Возврат",
    # Withdrawals (снятие) — amount_cents stored negative.
    "withdrawal_supplier": "Оплата поставщику",
    "withdrawal_salary": "Зарплата",
    "withdrawal_rent": "Аренда",
    "withdrawal_utilities": "Коммунальные",
    "withdrawal_other": "Прочее",
    # Deposits (внесение) — amount_cents stored positive.
    "deposit_opening": "Начальный остаток",
    "deposit_correction": "Корректировка",
}

# Phase 16 (D-01a): coarse history buckets → the CASH_CATEGORIES keys they
# group. The «Тип» history filter maps one bucket to a SET of categories, so
# the read service uses `category.in_(CASH_BUCKETS[bucket])` — a single
# `== bucket` cannot express «Снятие» (5 categories). Mirrors how history_view
# gates on OPERATION_TYPES membership. Server-side only — never a Jinja global.
CASH_BUCKETS: dict[str, tuple[str, ...]] = {
    "sale": ("sale",),
    "return": ("return",),
    "withdrawal": (
        "withdrawal_supplier",
        "withdrawal_salary",
        "withdrawal_rent",
        "withdrawal_utilities",
        "withdrawal_other",
    ),
    "deposit": ("deposit_opening", "deposit_correction"),
}

# Phase 16 (D-01a/D-07a): coarse bucket key → RU label for the history «Тип»
# filter. Registered as a Jinja global alongside CASH_CATEGORIES.
CASH_BUCKET_LABELS = {
    "sale": "Продажа",
    "return": "Возврат",
    "withdrawal": "Снятие",
    "deposit": "Внесение",
}

# Phase 21 (D-01): latin kind -> RU label for CustomerContact.kind. This is
# also the exact server-side allow-list the customer service validates `kind`
# against — same shape as WRITEOFF_REASONS above. Keys are latin/internal; the
# RU values are operator-facing labels shown on the customer detail page.
CONTACT_KINDS = {
    "phone": "Телефон",
    "telegram": "Telegram",
    "email": "Email",
    "social": "Соцсеть",
}

# Phase 5 (D-16): latin operation type -> RU label for the /history "Тип" column.
# Covers every OPERATION_TYPES member.
OPERATION_TYPE_LABELS = {
    "receipt": "Приход",
    "sale": "Продажа",
    "writeoff": "Списание",
    "return": "Возврат",
    "correction": "Корректировка",
    "transfer": "Перемещение",
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
    # D-19/D-01 (Phase 18, PROD-05): two optional prices (ДЦ cost_cents /
    # ПЦ sale_cents) + the min_sale_cents guardrail, integer cents only
    # (conventions test). The third stored price field (dropped via
    # migration 0014, Pitfall 4) was a write-once stale copy of the
    # Oriflame list price, superseded by the live catalog_prices reference.
    cost_cents: Mapped[int | None] = mapped_column(Integer)
    sale_cents: Mapped[int | None] = mapped_column(Integer)
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
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id"), nullable=False, index=True)
    warehouse_id: Mapped[str] = mapped_column(ForeignKey("warehouses.id"), nullable=False)
    # LOT-03: optional ISO yyyy-mm-dd expiry; TEXT sorts lexicographically ==
    # chronologically (input type=date always posts ISO regardless of locale).
    expiry: Mapped[str | None] = mapped_column(String(10))
    # D-02: sale-price snapshot frozen at batch creation; NULL for legacy.
    price_cents: Mapped[int | None] = mapped_column(Integer)
    location: Mapped[str | None] = mapped_column(String(100))  # WH-02 free-text tag
    comment: Mapped[str | None] = mapped_column(String(200))  # LOT-04
    # UAT test 1 symptom 3: auto-generated «{product.name} — {creation date}»
    # label, snapshotted at batch creation; NULL for legacy/pre-0009 batches.
    # WR-02: 220 = product.name String(200) + " — dd.mm.yyyy" (13) suffix, so a
    # max-length product name never overflows the column on PostgreSQL.
    name: Mapped[str | None] = mapped_column(String(220))
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
    # CAT-04: catalog membership imported from catalogs/products.json — the
    # list of catalog codes (e.g. ["01_26", "03_26"]) this product appears in.
    # NULL/[] = not present in any imported catalog. Helper data only (D-24).
    catalogs: Mapped[list | None] = mapped_column(JSON)
    # Phase 14 (LIST-02): lowercase shadow of name — SQLite lower()/LIKE
    # cannot fold Cyrillic.
    name_lc: Mapped[str | None] = mapped_column(String(200), index=True)
    created_at: Mapped[str] = mapped_column(String(32), default=utcnow_iso)
    updated_at: Mapped[str] = mapped_column(String(32), default=utcnow_iso, onupdate=utcnow_iso)


class CatalogPrice(Base):
    """Per-catalog price row (CAT-05), imported from the xlsx price lists.

    One row per (catalog year, catalog number, product code): the full price
    history across every catalog issue. Helper data only (like Dictionary,
    D-24) — never feeds stock or the ledger. Prices are integer cents; the
    source xlsx lists whole-ruble prices, converted on import.

    Columns mirror the Oriflame price-list columns:
      * consumer_cents   — ПЦ, the catalog / retail price a customer pays
      * consultant_cents — ОП, the consultant (purchase) price
      * points           — ББ, catalog bonus points
    """

    __tablename__ = "catalog_prices"
    __table_args__ = (
        UniqueConstraint("year", "number", "code", name="uq_catalog_prices_year_number_code"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    number: Mapped[int] = mapped_column(Integer, nullable=False)
    code: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    name: Mapped[str | None] = mapped_column(String(200))
    consumer_cents: Mapped[int | None] = mapped_column(Integer)
    consultant_cents: Mapped[int | None] = mapped_column(Integer)
    points: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[str] = mapped_column(String(32), default=utcnow_iso)
    updated_at: Mapped[str] = mapped_column(String(32), default=utcnow_iso, onupdate=utcnow_iso)


class Operation(Base):
    """Append-only ledger row (D-08) — immutability enforced by DB triggers."""

    __tablename__ = "operations"
    __table_args__ = (UniqueConstraint("device_id", "seq"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    type: Mapped[str] = mapped_column(String(20), nullable=False)
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id"), nullable=False, index=True)
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
    # D-02 (Phase 21): singular physical address -> plain column, not a
    # CustomerContact row. Byte-identical copy of Warehouse.address (:190).
    # Not folded into search_lc — search stays "name surname consultant".
    address: Mapped[str | None] = mapped_column(String(300))
    search_lc: Mapped[str | None] = mapped_column(String(400), index=True)
    created_at: Mapped[str] = mapped_column(String(32), default=utcnow_iso)
    updated_at: Mapped[str] = mapped_column(String(32), default=utcnow_iso, onupdate=utcnow_iso)


class CustomerContact(Base):
    """Multi-value customer contact row (D-01): phone/telegram/email/social.

    One generic table with a `kind` discriminator — all four kinds share an
    identical label+value shape (CUST-01..04). The CHECK constraint below is
    defence-in-depth only; the PRIMARY gate is the CONTACT_KINDS Python
    allow-list validated in the service, matching the models.py:32-33
    decision not to CHECK operations.type.
    """

    __tablename__ = "customer_contacts"
    __table_args__ = (
        # name= is MANDATORY: NAMING_CONVENTION's ck_%(table_name)s_%(constraint_name)s
        # raises InvalidRequestError at import of app.models without it, which
        # breaks collection of the entire test suite, not just new tests.
        CheckConstraint("kind IN ('phone', 'telegram', 'email', 'social')", name="kind_valid"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    # No relationship()/back_populates — there are ZERO in app/ and the FK is
    # joined manually in the service (house rule, per Sale.customer_id /
    # Operation.sale_id).
    customer_id: Mapped[str] = mapped_column(
        ForeignKey("customers.id", name="fk_customer_contacts_customer_id_customers"),
        nullable=False,
        index=True,
    )
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    value: Mapped[str] = mapped_column(String(300), nullable=False)
    # Nullable, ships unused this phase — no form field, no template renders
    # it (RESEARCH Open Question 1, decided).
    label: Mapped[str | None] = mapped_column(String(100))
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


class CashMovement(Base):
    """Append-only cash ledger row (D-00a): sibling to Operation, cash-only.

    Mirrors Operation's sync-ready shape (UUID PK, device_id/seq, created_at/
    created_by, nullable sale_id FK) but drops every stock-specific column
    (product_id, qty_delta, unit_cost_cents, unit_price_cents, payload,
    batch_id) — cash has no cached balance (D-00b: balance is always a live
    SUM(amount_cents), never a projection column). Immutability enforced by
    DB-level triggers (see app.db.APPEND_ONLY_TRIGGERS and migration 0013).
    """

    __tablename__ = "cash_movements"
    __table_args__ = (UniqueConstraint("device_id", "seq"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    # A CASH_CATEGORIES key ("sale", "return", plus Phase 16's manual ones).
    category: Mapped[str] = mapped_column(String(20), nullable=False)
    # SIGNED integer cents: positive = приход, negative = расход. Integer
    # cents ONLY, never Float/Numeric (D-00a, CLAUDE.md money rule).
    amount_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    note: Mapped[str | None] = mapped_column(String(300))
    # Nullable link to the sale this auto-credit/auto-debit movement
    # originated from. Set at INSERT time only — the cash_movements_no_update
    # trigger ABORTs any later UPDATE. Manual movements (Phase 16) leave NULL.
    sale_id: Mapped[str | None] = mapped_column(
        ForeignKey("sales.id", name="fk_cash_movements_sale_id_sales"), index=True
    )
    device_id: Mapped[str] = mapped_column(String(36), nullable=False)
    seq: Mapped[int] = mapped_column(Integer, nullable=False)  # per-device counter
    created_at: Mapped[str] = mapped_column(String(32), nullable=False)  # UTC ISO text
    created_by: Mapped[str] = mapped_column(String(100), nullable=False)
    synced_at: Mapped[str | None] = mapped_column(String(32))  # v2 sync cursor

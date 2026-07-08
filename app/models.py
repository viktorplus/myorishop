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
    # D-27: lowercase shadow of name, maintained by the SERVICE layer via
    # Python str.lower() — SQLite lower()/LIKE cannot fold Cyrillic.
    name_lc: Mapped[str | None] = mapped_column(String(200), index=True)
    # D-09: cached projection of SUM(operations.qty_delta); recomputable.
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[str] = mapped_column(String(32), default=utcnow_iso)
    updated_at: Mapped[str] = mapped_column(String(32), default=utcnow_iso, onupdate=utcnow_iso)
    # D-10: soft delete only; no hard deletes.
    deleted_at: Mapped[str | None] = mapped_column(String(32))


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
    device_id: Mapped[str] = mapped_column(String(36), nullable=False)
    seq: Mapped[int] = mapped_column(Integer, nullable=False)  # per-device counter
    created_at: Mapped[str] = mapped_column(String(32), nullable=False)  # UTC ISO text
    created_by: Mapped[str] = mapped_column(String(100), nullable=False)  # FND-03
    synced_at: Mapped[str | None] = mapped_column(String(32))  # v2 sync cursor

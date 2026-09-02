"""Import a warehouse inventory sheet as a GOODS RECEIPT (quick task 260902-eyv).

Run (dry run — nothing is written):
    uv run python scripts/import_inventory_receipt.py
Run (writes):
    uv run python scripts/import_inventory_receipt.py --apply

The sheet is a list of goods TO ADD, not a stock-take: whatever already lies in
the destination warehouse stays, the sheet is added on top. Rules are frozen in
`.planning/quick/260902-eyv-import-office-inventory-receipt-into-s1/260902-eyv-SPEC.md`
and summarised here:

  * a batch is keyed by code + YEAR-MONTH of the expiry (the day is ignored —
    the ledger stores «2018-01-14», the sheet expands «01/18» to «2018-01-31»,
    and those are one lot) plus the condition marker (rule 2);
  * a non-empty leftover in the «Комментарий» column after the placement
    («полка NN» / «под зеркалом») is a condition marker: such a row ALWAYS gets
    a fresh batch, a top-up is forbidden, and the marker is stored in the new
    batch's comment next to the shelf (rule 2.2);
  * the shelf goes to the new batch's `location`; on a top-up `register_receipt`
    ignores it, so it is appended to `batch.comment` afterwards (rule 3);
  * prices travel ONLY for codes with no active card yet — otherwise
    `register_receipt` would write `price_change` and overwrite the card's own
    price with the catalog one (rule 4). A code missing from `catalog_prices`
    is imported with EMPTY prices (NULL, not zero).

Dialect-aware (SQLite locally, PostgreSQL on the server — taken from
app.config.settings, like scripts/reset_business_data.py). Every write goes
through app.services.receipts.register_receipt; the ONLY direct database write
is `batch.comment` / `batch.expiry` on the top-up path (rules 3 and 2.1) —
`batches` is not append-only, unlike `operations`.

NOT IDEMPOTENT: the ledger is append-only, so running --apply twice adds the
quantities twice. There is no undo.
"""

import argparse
import csv
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select  # noqa: E402
from sqlalchemy.engine import Engine  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.config import settings  # noqa: E402
from app.core import format_cents  # noqa: E402
from app.db import SessionLocal, engine  # noqa: E402
from app.models import Batch, Product, Warehouse  # noqa: E402
from app.services.batches import active_warehouses  # noqa: E402
from app.services.pricing import latest_price_for_code  # noqa: E402
from app.services.receipts import register_receipt  # noqa: E402

CSV_DEFAULT = "reports/оприходование-офис-2026-08-31.csv"
WAREHOUSE_DEFAULT = "Офис"
SKIP_CODES = frozenset({"???"})
COMMENT_MAX_LEN = 200  # = Batch.comment String(200), hard on PostgreSQL

REQUIRED_COLUMNS = (
    "Полка",
    "Код",
    "Наименование (из справочника)",
    "Кол-во",
    "Срок годности",
    "Комментарий",
)

# Rule 2.2: the placement vocabulary of the sheet. Anything left after it is
# the condition marker.
_PLACEMENT_RE = re.compile(r"^\s*(полка\s*\d+|под\s+зеркалом)", re.IGNORECASE)
_LEADING_SEPARATORS = " \t;,.-—–"


@dataclass(frozen=True)
class Row:
    """One physical CSV line, already split into placement + condition marker."""

    line_no: int  # PHYSICAL csv line number (the header is line 1)
    shelf: str
    code: str
    name: str
    qty: str
    expiry: str  # ISO yyyy-mm-dd as written in the sheet, or ""
    note: str  # raw «Комментарий»
    placement: str  # «полка 47» / «под зеркалом» / ""
    condition: str  # leftover of «Комментарий» = condition marker
    skip_reason: str | None  # None = the row is imported


@dataclass(frozen=True)
class Decision:
    """What one row would do — computed read-only, used by BOTH modes (D-1)."""

    action: str  # "new_batch" | "topup"
    product_exists: bool
    batch_id: str | None  # None for "new_batch" and for a dry-run prediction
    cost_raw: str  # "" when the card already exists or there is no price
    sale_raw: str
    placement: str
    comment: str  # "" unless the row carries a condition marker
    warnings: tuple[str, ...] = ()


@dataclass
class Pending:
    """Run-scoped memory so a dry run predicts exactly what --apply would do.

    D-2: `new_codes`/`new_batches` are filled in DRY-RUN mode only — under
    --apply `register_receipt` commits, so the database itself is the truth.
    `condition_batches` is the mirror image: filled under --apply only, because
    a condition row must never top up a batch that existed BEFORE this run, yet
    two rows sharing code + month + marker must land in the same new batch
    (rule 2.2). `condition_batch_ids` keeps those batches out of the ordinary
    month lookup, so both modes agree.
    """

    new_codes: set[str] = field(default_factory=set)
    new_batches: set[tuple[str, str | None, str]] = field(default_factory=set)
    condition_batches: dict[tuple[str, str | None, str], str] = field(
        default_factory=dict
    )
    condition_batch_ids: set[str] = field(default_factory=set)


def split_note(note: str, shelf: str) -> tuple[str, str]:
    """Split «Комментарий» into (placement, condition marker) — rule 2.2/3.

    The placement is «полка NN» or «под зеркалом»; whatever follows it is the
    condition marker («упаковка повреждена», «пробник», …). When the comment
    carries no recognisable placement, the «Полка» column supplies it and the
    whole comment is treated as the marker.
    """
    text = (note or "").strip()
    match = _PLACEMENT_RE.match(text)
    if match:
        placement = _normalize(match.group(1))
        condition = text[match.end() :].lstrip(_LEADING_SEPARATORS).strip()
    else:
        placement = _shelf_placement(shelf)
        condition = text
    return placement, condition


def _normalize(value: str) -> str:
    """Collapse whitespace and casefold — «Полка  59» and «полка 59» are one."""
    return " ".join(value.split()).lower()


def _shelf_placement(shelf: str) -> str:
    """Fallback placement built from the «Полка» column."""
    text = (shelf or "").strip()
    if not text:
        return ""
    if text.isdigit():
        return f"полка {text}"
    return _normalize(text)


def _year_month(expiry: str) -> str | None:
    """«2018-01-31» -> «2018-01»; empty stays empty (matches only empty, rule 2.1)."""
    return expiry[:7] if expiry else None


def _key(row: Row) -> tuple[str, str | None, str]:
    return row.code, _year_month(row.expiry), row.condition


def read_rows(path: Path | str) -> list[Row]:
    """Parse the sheet; every physical line becomes a Row (skips included)."""
    path = Path(path)
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle, delimiter=";")
        missing = [c for c in REQUIRED_COLUMNS if c not in (reader.fieldnames or [])]
        if missing:
            raise RuntimeError(
                "В файле нет обязательных колонок: " + ", ".join(missing)
            )
        rows: list[Row] = []
        # The header is physical line 1, so data starts at 2.
        for line_no, raw in enumerate(reader, start=2):
            code = (raw.get("Код") or "").strip()
            shelf = (raw.get("Полка") or "").strip()
            note = (raw.get("Комментарий") or "").strip()
            placement, condition = split_note(note, shelf)
            if not code:
                skip_reason: str | None = "пустой код"
            elif code in SKIP_CODES:
                skip_reason = f"код «{code}»"
            else:
                skip_reason = None
            rows.append(
                Row(
                    line_no=line_no,
                    shelf=shelf,
                    code=code,
                    name=(raw.get("Наименование (из справочника)") or "").strip(),
                    qty=(raw.get("Кол-во") or "").strip(),
                    expiry=(raw.get("Срок годности") or "").strip(),
                    note=note,
                    placement=placement,
                    condition=condition,
                    skip_reason=skip_reason,
                )
            )
    return rows


def find_warehouse(session: Session, name: str) -> Warehouse | None:
    """Active warehouse by name, case- and whitespace-insensitive (rule 7).

    D-27: the fold happens in PYTHON over active_warehouses(), never via SQL
    lower()/LIKE — SQLite does not fold Cyrillic.
    """
    wanted = _normalize(name or "")
    if not wanted:
        return None
    for warehouse in active_warehouses(session):
        if _normalize(warehouse.name or "") == wanted:
            return warehouse
    return None


def _month_batches(
    session: Session,
    product_id: str,
    warehouse_id: str,
    year_month: str | None,
    excluded: set[str],
) -> list[Batch]:
    """Batches of this product in this warehouse whose expiry falls in `year_month`.

    D-3: a direct query, NOT open_batches — that one filters quantity > 0 and
    would create a duplicate lot next to an emptied batch. Earliest expiry
    first (rule 2.1), created_at as the tie-break.
    """
    stmt = select(Batch).where(
        Batch.product_id == product_id, Batch.warehouse_id == warehouse_id
    )
    if year_month is None:
        stmt = stmt.where(Batch.expiry.is_(None))
    else:
        stmt = stmt.where(Batch.expiry.like(f"{year_month}-%"))
    stmt = stmt.order_by(Batch.expiry.asc(), Batch.created_at.asc())
    return [b for b in session.scalars(stmt) if b.id not in excluded]


def resolve_row(
    session: Session, row: Row, warehouse_id: str, pending: Pending
) -> Decision:
    """Decide what this row does. READ-ONLY — shared by the dry run and --apply."""
    warnings: list[str] = []
    key = _key(row)
    product = session.scalars(
        select(Product).where(Product.code == row.code, Product.deleted_at.is_(None))
    ).first()
    product_exists = product is not None or row.code in pending.new_codes

    action = "new_batch"
    batch_id: str | None = None
    if row.condition:
        # Rule 2.2: never merge into a batch that predates this run.
        known = pending.condition_batches.get(key)
        if known is not None:
            action, batch_id = "topup", known
        elif key in pending.new_batches:
            action = "topup"
    else:
        if product is not None:
            candidates = _month_batches(
                session,
                product.id,
                warehouse_id,
                _year_month(row.expiry),
                pending.condition_batch_ids,
            )
            if candidates:
                action, batch_id = "topup", candidates[0].id
                if len(candidates) > 1:
                    warnings.append(
                        f"строка {row.line_no}: у товара {row.code} несколько партий "
                        f"за {_year_month(row.expiry) or 'без срока'} — "
                        f"долив в самую раннюю ({candidates[0].expiry or 'без срока'})"
                    )
                if candidates[0].is_legacy:
                    warnings.append(
                        f"строка {row.line_no}: долив в legacy-партию "
                        f"{candidates[0].id} (остаток до внедрения партий)"
                    )
        if action == "new_batch" and key in pending.new_batches:
            action = "topup"

    # Rule 4: an existing card keeps its own prices — never send catalog ones.
    cost_raw = sale_raw = ""
    if not product_exists:
        price = latest_price_for_code(session, row.code)
        if price is not None:
            if price.consultant_cents is not None:
                cost_raw = format_cents(price.consultant_cents)
            if price.consumer_cents is not None:
                sale_raw = format_cents(price.consumer_cents)

    # Rule 2.2: the marker is stored next to the shelf on the new batch.
    comment = ""
    if row.condition:
        comment = "; ".join(p for p in (row.placement, row.condition) if p)
        if len(comment) > COMMENT_MAX_LEN:
            comment = comment[:COMMENT_MAX_LEN]
            warnings.append(
                f"строка {row.line_no}: примечание обрезано до {COMMENT_MAX_LEN} символов"
            )

    return Decision(
        action=action,
        product_exists=product_exists,
        batch_id=batch_id,
        cost_raw=cost_raw,
        sale_raw=sale_raw,
        placement=row.placement,
        comment=comment,
        warnings=tuple(warnings),
    )


def _apply_topup_notes(session: Session, batch: Batch, row: Row) -> list[str]:
    """Post-top-up fixes register_receipt cannot do (rules 2.1 and 3).

    `register_receipt` ignores expiry/location/comment on the top-up path, so
    the expiry is normalised to the sheet's shape here and the shelf is appended
    to the batch comment. Comparison is by "; "-separated PARTS, never by
    substring — «полка 4» is a substring of «полка 47».
    """
    warnings: list[str] = []
    changed = False
    if row.expiry and batch.expiry != row.expiry:
        batch.expiry = row.expiry
        changed = True
    if row.placement:
        parts = [p.strip() for p in (batch.comment or "").split(";") if p.strip()]
        if row.placement not in parts:
            merged = "; ".join(parts + [row.placement])
            if len(merged) > COMMENT_MAX_LEN:
                warnings.append(
                    f"строка {row.line_no}: примечание партии {batch.id} переполнено, "
                    f"полка не дописана"
                )
            else:
                batch.comment = merged
                changed = True
    if changed:
        session.commit()
    return warnings


def run_import(
    session: Session, rows: list[Row], warehouse: Warehouse, *, apply: bool
) -> dict:
    """Walk the sheet; return the summary. Writes only when `apply` is True."""
    summary: dict = {
        "rows_read": len(rows),
        "skipped": [(r.line_no, r.skip_reason) for r in rows if r.skip_reason],
        "to_receipt": 0,
        "qty_total": 0,
        "new_products": 0,
        "new_batches": 0,
        "topups": 0,
        "condition_rows": 0,
        "codes_without_price": 0,
        "rows_written": 0,
        "stopped_at_line": None,
        "error_code": None,
        "error": None,
        "warnings": [],
    }
    pending = Pending()
    priceless: set[str] = set()

    for row in rows:
        if row.skip_reason:
            continue
        summary["to_receipt"] += 1
        summary["qty_total"] += int(row.qty) if row.qty.isdigit() else 0
        if row.condition:
            summary["condition_rows"] += 1

        decision = resolve_row(session, row, warehouse.id, pending)
        summary["warnings"].extend(decision.warnings)
        if not decision.product_exists:
            summary["new_products"] += 1
            if not decision.cost_raw and not decision.sale_raw:
                priceless.add(row.code)
        if decision.action == "new_batch":
            summary["new_batches"] += 1
        else:
            summary["topups"] += 1

        if not apply:
            # D-2: remember the prediction so intra-file repeats are not
            # counted as fresh cards/batches.
            if not decision.product_exists:
                pending.new_codes.add(row.code)
            if decision.action == "new_batch":
                pending.new_batches.add(_key(row))
            continue

        if decision.action == "topup" and decision.batch_id is None:
            raise RuntimeError(
                f"строка {row.line_no}: цель долива не определена — внутренняя ошибка"
            )
        result, errors = register_receipt(
            session,
            code=row.code,
            name=row.name,
            qty_raw=row.qty,
            cost_raw=decision.cost_raw,
            sale_raw=decision.sale_raw,
            warehouse_id=warehouse.id,
            batch_choice="new" if decision.action == "new_batch" else decision.batch_id,
            expiry_raw=row.expiry,
            location_raw=decision.placement if decision.action == "new_batch" else "",
            comment_raw=decision.comment if decision.action == "new_batch" else "",
        )
        if result is None:
            summary["stopped_at_line"] = row.line_no
            summary["error_code"] = row.code
            summary["error"] = "; ".join(f"{k}: {v}" for k, v in errors.items())
            break
        summary["rows_written"] += 1
        batch = result["batch"]
        if decision.action == "new_batch":
            if row.condition:
                pending.condition_batches[_key(row)] = batch.id
                pending.condition_batch_ids.add(batch.id)
        else:
            summary["warnings"].extend(_apply_topup_notes(session, batch, row))

    summary["codes_without_price"] = len(priceless)
    return summary


def _target_label(target: Engine) -> str:
    """Human-readable target identity, PASSWORD-REDACTED (never print engine.url)."""
    if target.dialect.name == "postgresql":
        return f"PostgreSQL: {target.url.host}/{target.url.database}"
    return f"SQLite file: {settings.db_path}"


def _print_summary(summary: dict, *, apply: bool) -> None:
    skipped = summary["skipped"]
    detail = "; ".join(f"строка {n}: {reason}" for n, reason in skipped)
    print()
    print(f"Прочитано строк: {summary['rows_read']}")
    print(f"Пропущено: {len(skipped)}" + (f" ({detail})" if detail else ""))
    print(
        f"К оприходованию: {summary['to_receipt']} строк, "
        f"{summary['qty_total']} шт."
    )
    print()
    print(f"Новых карточек товара: {summary['new_products']}")
    print(f"Новых партий: {summary['new_batches']}")
    print(f"Доливов в существующие партии: {summary['topups']}")
    print(f"Строк с признаком состояния (долив запрещён): {summary['condition_rows']}")
    print(f"Кодов без цены в catalog_prices: {summary['codes_without_price']}")
    if apply:
        print(f"Записано строк: {summary['rows_written']}")
    print()
    print(
        "ВНИМАНИЕ: импорт НЕ идемпотентен — повторный запуск с --apply добавит\n"
        "количество ещё раз."
    )
    if summary["warnings"]:
        print()
        print("Предупреждения:")
        for line in summary["warnings"]:
            print(f"  {line}")
    if summary["error"]:
        print()
        print(
            f"Строка {summary['stopped_at_line']} "
            f"(код {summary['error_code']}): {summary['error']}"
        )
        print(f"Остановлено. Записано строк: {summary['rows_written']}.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Оприходовать опись склада как приход (по умолчанию — сухой прогон)."
    )
    parser.add_argument(
        "--apply", action="store_true", help="записать в базу (по умолчанию — нет)"
    )
    parser.add_argument("--file", default=CSV_DEFAULT, help="путь к CSV описи")
    parser.add_argument(
        "--warehouse", default=WAREHOUSE_DEFAULT, help="имя склада назначения"
    )
    args = parser.parse_args()

    dialect = engine.dialect.name
    if dialect not in ("sqlite", "postgresql"):
        raise RuntimeError(f"unsupported dialect: {dialect!r}")

    path = Path(args.file)
    print(f"Целевая база: {_target_label(engine)}")
    print(f"Файл: {path}")
    if not path.exists():
        print(f"Файл не найден: {path}")
        sys.exit(1)

    session = SessionLocal()
    try:
        warehouse = find_warehouse(session, args.warehouse)
        if warehouse is None:
            print(f"Не найден активный склад «{args.warehouse}».")
            sys.exit(1)
        print(f"Склад назначения: «{warehouse.name}»")
        print(
            "Режим: ЗАПИСЬ (--apply)."
            if args.apply
            else "Режим: СУХОЙ ПРОГОН — записи не будет."
        )
        summary = run_import(session, read_rows(path), warehouse, apply=args.apply)
        _print_summary(summary, apply=args.apply)
        if summary["error"]:
            sys.exit(1)
    finally:
        session.close()


if __name__ == "__main__":
    main()

"""Convention helpers (D-05/D-06/D-07): UUID4 ids, UTC ISO timestamps, integer cents.

These are the ONLY sanctioned conversion points for ids, money and time.
Never use float for money (Pitfall 3) and never store naive datetimes.
"""

import uuid
from datetime import UTC, date, datetime, time, timedelta
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from zoneinfo import ZoneInfo

_CENTS = Decimal("0.01")


def new_id() -> str:
    """Return a random UUID4 as a 36-char string (sync-safe primary key)."""
    return str(uuid.uuid4())


def utcnow_iso() -> str:
    """Return current UTC time as ISO-8601 text, e.g. '2026-07-08T12:00:00+00:00'.

    ISO-8601 UTC strings sort lexicographically == chronologically.
    """
    return datetime.now(UTC).isoformat(timespec="seconds")


def to_cents(value: str) -> int:
    """Parse a money string ('12,50', '12.50', '7') into integer cents.

    Accepts the Russian comma decimal separator. Raises ValueError on ANY
    invalid input, including non-finite values ('inf', 'nan') and huge
    exponents — callers may rely on catching ValueError alone (WR-02).

    Rounding policy (WR-03): ROUND_HALF_UP — ties round away from zero,
    the predictable retail behaviour ('12,505' -> 1251), NOT the Decimal
    default banker's rounding.
    """
    text = str(value).strip().replace(",", ".")
    try:
        amount = Decimal(text)
        if not amount.is_finite():
            raise InvalidOperation
        return int(amount.quantize(_CENTS, rounding=ROUND_HALF_UP) * 100)
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"invalid money value: {value!r}") from exc


def format_cents(cents: int) -> str:
    """Render integer cents as a display string with comma separator: 1250 -> '12,50'."""
    sign = "-" if cents < 0 else ""
    whole, frac = divmod(abs(cents), 100)
    return f"{sign}{whole},{frac:02d}"


# Per-warehouse currency (CUR-01): a FIXED set — money is stored as integer minor
# units exactly as before, and the code only says which currency those units are
# in. There is no conversion and no exchange rate anywhere in the app, so amounts
# in different currencies are never summed.
CURRENCIES: dict[str, str] = {
    "RUB": "₽",
    "UAH": "₴",
    "EUR": "€",
}
DEFAULT_CURRENCY = "RUB"


def currency_symbol(currency: str | None) -> str:
    """Display symbol for a currency code; unknown/empty falls back to the code.

    Never raises — display code must not blow up on a row written by a newer
    client that knows a currency this build does not.
    """
    if not currency:
        return CURRENCIES[DEFAULT_CURRENCY]
    return CURRENCIES.get(currency, currency)


def format_money(cents: int, currency: str | None = None) -> str:
    """Render integer cents WITH its currency symbol: (1250, 'EUR') -> '12,50 €'.

    `format_cents` stays the bare-number filter (totals inside a column already
    labelled with a currency); this is the one to use wherever an amount stands
    on its own and the reader must know which currency it is.
    """
    return f"{format_cents(cents)} {currency_symbol(currency)}"


def format_ru_date(iso: str | None) -> str:
    """Render a stored ISO date ('2026-07-12') as RU display 'dd.mm.yyyy'.

    LOT-03 batch expiry is stored as ISO yyyy-mm-dd text; this is the display
    filter for every batch surface. Empty/None -> "" (expiry is optional).
    Locale-independent: `date.fromisoformat` validates, then reformats.

    NEVER RAISES (CR-01, 33-REVIEW) — same rule as `currency_symbol` above.
    This filter renders STORED data (`batch.expiry`, `operations.business_date`)
    on /history, /warehouses, the customer tile and both CSV exports, and the
    ledger is append-only: a single unparseable value written by some other
    write path would otherwise turn every one of those pages into a permanent
    500 that the application cannot repair. An unrecognised value is shown
    as-is instead. `merge.parse_exchange` is the gate that stops such a value
    reaching the DB in the first place; this is the second layer, not the first.
    """
    if not iso:
        return ""
    try:
        return date.fromisoformat(iso).strftime("%d.%m.%Y")
    except (TypeError, ValueError):
        return str(iso)


def iso_to_local(iso_str: str | None, tz_name: str) -> str:
    """Convert a UTC ISO-8601 string to local display time: '08.07.2026 15:00'.

    NEVER RAISES (CR-01, 33-REVIEW iteration 2) — the same rule
    `format_ru_date` above states, applied to the sibling column. This filter
    renders `operations.created_at` / `cash_movements.created_at` on /history,
    /m/history, the home page, the customer purchase tab and BOTH CSV exports,
    and `merge._LEDGER_REQUIRED` only checks that `created_at` is not None, so
    a merged row can carry an unparseable value. The ledger is append-only, so
    such a row cannot be repaired: raising here would turn every one of those
    surfaces into a permanent 500. An unrecognised value is shown as-is.
    `merge.parse_exchange` is the gate that stops it reaching the DB; this is
    the second layer, not the first.

    A NAIVE value is read as UTC, never as the machine's OS zone. That is the
    rule `alembic/versions/0027…::_local_business_date` and
    `operations._is_backdated` already apply to this same column, and this
    filter renders two lines away from that marker — `astimezone()` on a naive
    datetime assumes the SERVER's zone, so on a non-UTC host the «внесено»
    timestamp could contradict the business date printed directly above it.
    """
    if not iso_str:
        return ""
    try:
        moment = datetime.fromisoformat(iso_str)
    except (TypeError, ValueError):
        return str(iso_str)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=UTC)
    return moment.astimezone(ZoneInfo(tz_name)).strftime("%d.%m.%Y %H:%M")


def local_day_bounds_utc(start_day: date, end_day: date, tz_name: str) -> tuple[str, str]:
    """UTC ISO bounds for the LOCAL half-open range [start_day, end_day] inclusive.

    This is the `created_at`-only helper: it produces UTC *timestamp* bounds
    for the technical entry timestamp. Its business-date sibling is
    `business_date_bounds` below, which produces date-only bounds for the
    `business_date` column and must never be replaced by this one (Phase 33).

    IN-01 (33-REVIEW): as of Phase 33 this helper has NO caller under `app/` —
    all 14 switched to `business_date_bounds`, and every remaining `app/`
    mention (`core.py`, `export.py`) is a docstring cross-reference. It is kept
    DELIBERATELY, on two grounds: `tests/` uses it as the sanctioned way to
    BUILD `created_at` fixtures and to pin the half-open contract — MEASURED,
    not copied from a plan: `test_core.py`, `test_export.py`,
    `test_dashboard.py`, `test_attribution.py`, `test_business_date.py` (the
    33-CONTEXT list also named `test_finance_reports.py` and `test_reports.py`;
    they no longer reference it — re-grep, do not re-copy) — and the contrast
    drawn in `business_date_bounds`
    below is load-bearing documentation that needs both halves present. Do not
    delete it as dead code; do not "revive" it by pointing a reader at it
    either.

    end_day is the LAST included local calendar day; the returned upper
    bound is local midnight of the day AFTER end_day, converted to UTC —
    so callers filter created_at >= start AND created_at < end (never a
    closed range, which would double-count a row landing exactly on a
    UTC-midnight boundary). This is the ONLY sanctioned way to turn a
    local calendar day/range into a UTC filter range (D-02): never slice
    the UTC created_at string by date directly, or an evening sale near
    local midnight shifts into the wrong day's report.
    """
    tz = ZoneInfo(tz_name)
    start_local = datetime.combine(start_day, time.min, tzinfo=tz)
    end_local = datetime.combine(end_day, time.min, tzinfo=tz) + timedelta(days=1)
    return (
        start_local.astimezone(UTC).isoformat(timespec="seconds"),
        end_local.astimezone(UTC).isoformat(timespec="seconds"),
    )


def business_date_bounds(start_day: date, end_day: date) -> tuple[str, str]:
    """Date-only ISO bounds for the CLOSED local range [start_day, end_day].

    CONTRACT (state it before using it): the range is **closed / inclusive on
    both ends**. Callers filter `business_date_expr(M) >= start` AND
    `business_date_expr(M) <= end` — never `<`. `local_day_bounds_utc` above is
    half-open on purpose (a row landing exactly on UTC midnight would otherwise
    double-count); a date-string comparison has no such hazard, so closed is
    both correct and free of the `+1 day` arithmetic. Turning one switched
    predicate's `<=` back into `<` is a silent one-day off-by-one.

    No timezone argument and no conversion happen here: `business_date` IS
    already the operator's local calendar day (Phase 33, DATE-01), so there is
    nothing left to convert.

    WHY THIS IS A SEPARATE HELPER and not a flag on `local_day_bounds_utc`:
    comparing the date-only string '2026-09-01' against that helper's UTC
    timestamp bounds is a lexicographic accident, not a comparison —

        Europe/Moscow     ('2026-08-31T21:00:00+00:00', '2026-09-01T21:00:00+00:00')
                          '2026-09-01' passes  -> True, by accident: it sorts
                          after the lower bound and is a literal prefix of the
                          upper one
        America/New_York  ('2026-09-01T04:00:00+00:00', '2026-09-02T04:00:00+00:00')
                          '2026-09-01' passes  -> False: the row VANISHES
        UTC               ('2026-09-01T00:00:00+00:00', '2026-09-02T00:00:00+00:00')
                          '2026-09-01' passes  -> False: the row VANISHES

    Sharpening of Pitfall 14 (`.planning/research/PITFALLS.md` calls it "off by
    a day at any UTC− offset"): the executed result is worse — it is broken at
    **every offset <= 0, including plain UTC itself**. It only appears to work
    east of Greenwich. A CI runner on UTC would therefore be the thing that
    caught this, in production, instead of a test.
    """
    return (start_day.isoformat(), end_day.isoformat())


def local_today_iso(tz_name: str) -> str:
    """Today's LOCAL calendar day as ISO 'yyyy-mm-dd' — the ONE definition of «today».

    Two of its consumers must agree, and that agreement is the point (D-15):
    the `today_iso()` Jinja global (which supplies both `value=` and `max=` on
    every date input) and `ledger.parse_op_date`'s future check. If those two
    ever computed «today» differently, a date typed at 23:30 local would be
    pre-filled by the form and then REFUSED by the server — an operator-visible
    contradiction with no way to work around it. Every business-date write path
    (`ledger`, `receipts`, `sales`, `returns`, `transfers`, `finance`) then
    falls back to the same helper for an unspecified date.

    Known, deliberate, unconverged debt — MEASURED at app version 1.101, not
    carried forward from a plan: FIVE sites still inline
    `datetime.now(ZoneInfo(settings.display_tz)).date()` instead of calling
    this —
        app/routes/reports.py:185        (+ .isoformat() — identical value)
        app/routes/mobile_reports.py:21  (+ .isoformat() — identical value)
        app/services/reports.py:300      (wants a `date` object, not the string)
        app/services/customers.py:450    (wants a `date` object)
        app/services/customers.py:474    (wants a `date` object)
    `app/services/dashboard.py:119,178` compute the same local today from a
    `tz_name` PARAMETER rather than from `settings.display_tz`, so they are a
    related but distinct shape. `app/services/receipts.py` is NOT on this list
    any more: Phase 33 converted it, and `receipts.py:158` now calls this
    helper (the docstring previously claimed four sites and named the
    already-converted receipts one — do not re-copy stale counts, re-grep).

    They are NOT converted here (additive-change rule: they are outside this
    phase's task), and converging them is not a pure substitution — three of
    the five want a `date`, so they need `date.fromisoformat(...)` or a sibling
    helper. Whoever converges them must not shift this function's result in the
    process: `parse_op_date` compares against it, so any shift at the day
    boundary silently turns valid dates into refusals.
    """
    return datetime.now(ZoneInfo(tz_name)).date().isoformat()

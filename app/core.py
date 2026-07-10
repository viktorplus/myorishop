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


def iso_to_local(iso_str: str, tz_name: str) -> str:
    """Convert a UTC ISO-8601 string to local display time: '08.07.2026 15:00'."""
    moment = datetime.fromisoformat(iso_str)
    return moment.astimezone(ZoneInfo(tz_name)).strftime("%d.%m.%Y %H:%M")


def local_day_bounds_utc(start_day: date, end_day: date, tz_name: str) -> tuple[str, str]:
    """UTC ISO bounds for the LOCAL half-open range [start_day, end_day] inclusive.

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

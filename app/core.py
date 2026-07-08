"""Convention helpers (D-05/D-06/D-07): UUID4 ids, UTC ISO timestamps, integer cents.

These are the ONLY sanctioned conversion points for ids, money and time.
Never use float for money (Pitfall 3) and never store naive datetimes.
"""

import uuid
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
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
    """
    text = str(value).strip().replace(",", ".")
    try:
        amount = Decimal(text)
        if not amount.is_finite():
            raise InvalidOperation
        return int(amount.quantize(_CENTS) * 100)
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

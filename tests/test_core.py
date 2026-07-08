"""Unit tests for app.core money helpers (WR-02/WR-03).

to_cents is the ONLY sanctioned conversion point for money input, so its
error contract (ValueError on any garbage) and rounding policy are pinned
here as executable documentation.
"""

import pytest

from app.core import format_cents, to_cents


def test_to_cents_accepts_comma_and_dot():
    assert to_cents("12,50") == 1250
    assert to_cents("12.50") == 1250
    assert to_cents("7") == 700
    assert to_cents("0") == 0


def test_to_cents_rounds_half_up():
    """WR-03: deliberate ROUND_HALF_UP policy — ties round away from zero."""
    assert to_cents("12,505") == 1251  # banker's rounding would give 1250
    assert to_cents("12,515") == 1252
    assert to_cents("-12,505") == -1251


@pytest.mark.parametrize(
    "bad",
    ["", "abc", "12,5,0", "inf", "-inf", "Infinity", "nan", "1e100000"],
)
def test_to_cents_raises_value_error_on_any_garbage(bad):
    """WR-02: documented contract — ValueError, never decimal.InvalidOperation."""
    with pytest.raises(ValueError):
        to_cents(bad)


def test_format_cents_display():
    assert format_cents(1250) == "12,50"
    assert format_cents(-305) == "-3,05"
    assert format_cents(0) == "0,00"

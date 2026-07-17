"""Shared template environment for all routers (avoids main.py circular import)."""

from fastapi.templating import Jinja2Templates

from app.config import settings as _config_settings
from app.core import format_cents, format_ru_date, iso_to_local
from app.models import (
    CASH_BUCKET_LABELS,
    CASH_CATEGORIES,
    CONTACT_KINDS,
    OPERATION_TYPE_LABELS,
    WRITEOFF_REASONS,
)

templates = Jinja2Templates(directory="app/templates")
# D-07: store UTC, display local; D-06: cents rendered only via helper.
# Aliased to _config_settings (not `settings`) so this package's own
# `settings` attribute-name namespace doesn't collide with the sibling
# route submodule app/routes/settings.py (D-06) — `from app.routes import
# settings` in app/main.py must resolve to that router module, not to this
# config instance (Python package attribute shadowing).
templates.env.filters["local_dt"] = lambda iso: iso_to_local(
    iso, _config_settings.display_tz
)
templates.env.filters["cents"] = format_cents
# LOT-03: batch expiry stored as ISO text; rendered dd.mm.yyyy in every surface.
templates.env.filters["ru_date"] = format_ru_date
# Phase 5 (D-16): expose RU-label constants to every template without every
# route re-passing them into its render context.
templates.env.globals["WRITEOFF_REASONS"] = WRITEOFF_REASONS
templates.env.globals["OPERATION_TYPE_LABELS"] = OPERATION_TYPE_LABELS
# Phase 16 (Pitfall 2): the manual-entry forms + cash history render category
# and bucket labels; expose them as globals so no template raises UndefinedError
# or blank-renders. CASH_BUCKETS stays server-side only (never rendered).
templates.env.globals["CASH_CATEGORIES"] = CASH_CATEGORIES
templates.env.globals["CASH_BUCKET_LABELS"] = CASH_BUCKET_LABELS
# Phase 21 (CUST-01..04): expose the RU contact-kind labels for
# customer_contacts.html the same established way as the constants above.
templates.env.globals["CONTACT_KINDS"] = CONTACT_KINDS

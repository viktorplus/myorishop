"""Shared template environment for all routers (avoids main.py circular import)."""

from fastapi.templating import Jinja2Templates

from app.config import settings
from app.core import format_cents, iso_to_local
from app.models import OPERATION_TYPE_LABELS, WRITEOFF_REASONS

templates = Jinja2Templates(directory="app/templates")
# D-07: store UTC, display local; D-06: cents rendered only via helper.
templates.env.filters["local_dt"] = lambda iso: iso_to_local(iso, settings.display_tz)
templates.env.filters["cents"] = format_cents
# Phase 5 (D-16): expose RU-label constants to every template without every
# route re-passing them into its render context.
templates.env.globals["WRITEOFF_REASONS"] = WRITEOFF_REASONS
templates.env.globals["OPERATION_TYPE_LABELS"] = OPERATION_TYPE_LABELS

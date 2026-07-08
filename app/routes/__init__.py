"""Shared template environment for all routers (avoids main.py circular import)."""

from fastapi.templating import Jinja2Templates

from app.config import settings
from app.core import format_cents, iso_to_local

templates = Jinja2Templates(directory="app/templates")
# D-07: store UTC, display local; D-06: cents rendered only via helper.
templates.env.filters["local_dt"] = lambda iso: iso_to_local(iso, settings.display_tz)
templates.env.filters["cents"] = format_cents

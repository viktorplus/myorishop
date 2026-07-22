"""Public GET /health — liveness + installed-version probe (Phase 32, UPD-04).

A tiny, auth-free, DB-free endpoint the launcher polls AFTER a swap to confirm
the NEW code actually serves: it returns the installed ``__version__`` so the
launcher's ``health_ok(expected_version=...)`` can require a version match (a
stale/wrong staged dir serving the OLD version fails the check and triggers the
shipped matched-pair rollback). ``/health`` is listed in
``security.PUBLIC_PATHS`` so the anonymous launcher probe gets a 200, not a 303
redirect to /login.
"""

from fastapi import APIRouter

from app import __version__ as APP_VERSION

router = APIRouter()


@router.get("/health")
def health() -> dict:
    """Return the installed version + liveness marker (no auth, no session, no DB)."""
    return {"version": APP_VERSION, "status": "ok"}

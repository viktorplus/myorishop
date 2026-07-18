"""Per-install local identity persistence (RESEARCH A2 / Pitfall 6).

These values live OUTSIDE the synced DB so copying `myorishop.db` does NOT
clone the device identity or signing key. Used by `app.config` to resolve a
stable `secret_key` and a per-install `device_id`.
"""

from pathlib import Path

from app.core import new_id


def get_or_create_local_id(path: str | Path) -> str:
    """Return a stable id persisted at ``path``, creating it on first use.

    If the file exists and is non-empty, return its stripped contents.
    Otherwise generate a fresh UUID4 via :func:`app.core.new_id`, create the
    parent directory, write the value and return it. Pure filesystem access —
    no DB, so the identity cannot travel inside a copied database file.
    """
    p = Path(path)
    if p.exists():
        existing = p.read_text(encoding="utf-8").strip()
        if existing:
            return existing
    value = new_id()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(value, encoding="utf-8")
    return value

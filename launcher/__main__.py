"""Launcher entry point: start app, open browser, watch marker, drive swap (PKG-04).

Runs as ``python -m launcher`` (or the compiled ``launcher.exe`` stub). The
launcher lives OUTSIDE the swappable ``app\\`` directory: it derives the install
root from its own location (``launcher\\``'s parent) and treats ``app\\``,
``app.prev\\``, ``app.failed\\``, ``staged\\`` and ``data\\`` as siblings
(RESEARCH install-root layout). It never imports ``app.*`` — that would lock the
directory the swap renames (RESEARCH Pitfall 3).

Phase 31 implements ONLY the hand-placed-marker drive path; the full IPC /
controlled-shutdown contract is DEFERRED to Phase 32 (RESEARCH Open Question 4).
"""

from __future__ import annotations

import threading
import time
import webbrowser
from pathlib import Path

from launcher import adapters
from launcher.swap import Paths, apply_update, parse_pending

_URL = "http://127.0.0.1:8000"
_MARKER_NAME = "pending.json"
_DB_NAME = "myorishop.db"
_WATCH_INTERVAL = 2.0
_BROWSER_DELAY = 2.0


def build_paths(launcher_dir: Path | None = None) -> Paths:
    """Derive the install-root layout from the launcher's own directory.

    ``install_root`` is the parent of ``launcher\\``; ``app\\``, ``app.prev\\``,
    ``app.failed\\``, ``staged\\`` and ``data\\`` are its siblings — so the
    launcher sits OUTSIDE ``app\\`` and never locks the swap target.
    """
    launcher_dir = Path(launcher_dir or Path(__file__).resolve().parent)
    install_root = launcher_dir.parent
    return Paths(
        app=install_root / "app",
        app_prev=install_root / "app.prev",
        staged=install_root / "staged",
        app_failed=install_root / "app.failed",
        install_root=install_root,
        data=install_root / "data",
    )


def run_once(
    paths: Paths,
    app_process,
    *,
    migrate=adapters.migrate,
    health_ok=adapters.health_ok,
    backup_restore=adapters.backup_restore,
) -> bool:
    """Check ``data\\pending.json`` and drive ONE apply_update cycle if valid.

    Integration hook for tests: hand-place a fake staged dir + a valid marker,
    then call ``run_once`` with fake ``app_process``/``migrate``/``health_ok``/
    ``backup_restore`` to drive a single real ``os.replace`` swap on tmp dirs.

    Refuses to swap on a missing or invalid marker (T-31-04): an unparseable
    marker is discarded without touching ``app\\``. On success the marker is
    deleted. Returns True iff a swap cycle ran.
    """
    marker = Path(paths.data) / _MARKER_NAME
    if not marker.exists():
        return False

    raw = marker.read_text(encoding="utf-8")
    try:
        pending = parse_pending(raw, paths.install_root)
    except ValueError:
        # Invalid marker: never act on it — discard and keep the app running.
        marker.unlink(missing_ok=True)
        return False

    db_path = Path(paths.data) / _DB_NAME
    apply_update(
        paths,
        pending,
        stop_app=app_process.stop,
        start_app=app_process.start,
        migrate=lambda: migrate(paths),
        # UPD-04: bind the marker's expected_version so the post-swap health check
        # confirms the NEW code actually serves (a stale/wrong swap -> rollback).
        health_ok=lambda: health_ok(expected_version=pending.expected_version),
        backup_restore=lambda backup: backup_restore(backup, db_path),
    )
    marker.unlink(missing_ok=True)
    return True


def _open_browser_soon(url: str = _URL, delay: float = _BROWSER_DELAY) -> None:
    """Open the default browser shortly after the app starts (run.bat parity)."""
    threading.Timer(delay, lambda: webbrowser.open(url)).start()


def main() -> None:
    paths = build_paths()
    app_process = adapters.AppProcess(paths)
    app_process.start()
    _open_browser_soon()
    try:
        while True:
            run_once(paths, app_process)
            time.sleep(_WATCH_INTERVAL)
    except KeyboardInterrupt:
        pass
    finally:
        app_process.stop()


if __name__ == "__main__":
    main()

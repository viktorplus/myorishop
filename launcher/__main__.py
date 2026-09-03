"""Launcher entry point: start app, open browser, watch marker, drive swap (PKG-04).

Runs as ``launcher\\python.exe -m launcher`` — the Start-Menu shortcut's target —
on its OWN embeddable runtime shipped inside ``launcher\\``
(``build_release.assemble_launcher_runtime``). There is no compiled ``.exe`` stub
and none is planned. It must NOT run on ``app\\python.exe``: a running
interpreter image cannot be deleted, so the post-swap
``shutil.rmtree(app.prev)`` would silently fail and leak a full copy of the
previous bundle on every successful update. The launcher therefore lives OUTSIDE
the swappable ``app\\`` directory: it derives the install root from its own
location (``launcher\\``'s parent) and treats ``app\\``,
``app.prev\\``, ``app.failed\\``, ``staged\\`` and ``data\\`` as siblings
(RESEARCH install-root layout). It never imports ``app.*`` — that would lock the
directory the swap renames (RESEARCH Pitfall 3).

Phase 31 implements ONLY the hand-placed-marker drive path; the full IPC /
controlled-shutdown contract is DEFERRED to Phase 32 (RESEARCH Open Question 4).
"""

from __future__ import annotations

import os
import sys
import threading
import time
import webbrowser
from pathlib import Path

from launcher import adapters
from launcher.swap import Paths, apply_update, parse_pending

_URL = "http://127.0.0.1:8000"
_MARKER_NAME = "pending.json"
_FAILED_MARKER_NAME = "pending.failed.json"
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


def _quarantine_marker(marker: Path) -> None:
    """Move a failed ``pending.json`` aside so the watch loop cannot replay it.

    ``os.replace`` atomically overwrites any previous quarantine. A failure here
    must never mask the real update error, so it is swallowed — the worst case is
    a marker that the next tick refuses again (its staged dir is gone by then).
    """
    try:
        os.replace(marker, marker.with_name(_FAILED_MARKER_NAME))
    except OSError:
        pass


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
    marker is discarded without touching ``app\\``. It also refuses to BEGIN the
    cycle when the staged code is gone — both ``pending.staged_dir`` (what the
    marker names and ``parse_pending`` confines) and ``paths.staged`` (what
    ``apply_update`` actually renames) must exist. They are NOT the same path:
    they coincide only when the marker literally names ``staged``, which is what
    Phase 31 hand-places and what Phase 32's ``update.stage_pending`` writes — so
    both are checked rather than one being assumed to imply the other.

    The marker is ALWAYS consumed: deleted on success, moved to
    ``data\\pending.failed.json`` on any failure. A failed update can therefore
    never be replayed by ``main()``'s 2-second watch loop — the 31-UAT blocker
    where a stuck marker destroyed the install on the next tick. The READ itself
    is inside that guard: a non-UTF-8 marker raises ``UnicodeDecodeError`` (a
    ``ValueError``), and with the read outside the guard it escaped ``run_once``
    uncaught, so the marker was neither consumed nor quarantined and the watch
    loop replayed the same bytes every 2 s forever (T-31-04: the marker is
    attacker-controlled input).

    An ``OSError`` on that read is the ONE case that does NOT consume the marker:
    it means a transient sharing violation while the app is writing it, so the
    next tick retries instead of destroying a marker that is simply in flight.

    Returns True iff a swap cycle ran.
    """
    marker = Path(paths.data) / _MARKER_NAME
    if not marker.exists():
        return False

    try:
        pending = parse_pending(marker.read_text(encoding="utf-8"), paths.install_root)
    except ValueError:
        # Invalid or undecodable marker: never act on it — QUARANTINE rather than
        # delete. `update.stage_pending` writes the marker atomically, but a
        # hand-placed or half-written one must leave evidence behind instead of
        # vanishing silently with the staged update it named.
        _quarantine_marker(marker)
        return False
    except OSError:
        # Transient (the marker is being written right now): do not consume it —
        # the next tick reads it whole.
        return False

    if not Path(pending.staged_dir).exists() or not Path(paths.staged).exists():
        # Unsatisfiable marker (usually one an earlier rollback already consumed):
        # quarantine it BEFORE any side effect instead of replaying it forever.
        _quarantine_marker(marker)
        return False

    db_path = Path(paths.data) / _DB_NAME
    try:
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
    except BaseException:
        # BaseException mirrors apply_update's rollback guard (WR-06): a Ctrl+C
        # or console-close mid-swap must consume the marker too, or the next
        # launch replays a cycle whose staged dir is already gone. The rollback
        # already restored the install; the caller logs the re-raised error.
        _quarantine_marker(marker)
        raise
    marker.unlink(missing_ok=True)
    return True


def _open_browser_soon(url: str = _URL, delay: float = _BROWSER_DELAY) -> None:
    """Open the default browser shortly after the app starts (run.bat parity)."""
    threading.Timer(delay, lambda: webbrowser.open(url)).start()


def boot(paths: Paths, app_process, *, migrate=adapters.migrate) -> None:
    """Migrate the schema, THEN start the app — run.bat's contract, packaged.

    ``run.bat`` runs ``alembic upgrade head`` before uvicorn and, on failure,
    prints a message and does NOT start the server. The packaged path had no
    equivalent: ``main()`` called ``app_process.start()`` directly and
    ``adapters.migrate`` was reachable only from ``apply_update`` — i.e. the
    update-swap path — so a FIRST launch of an installed copy never migrated. The
    DB file was created without a schema and every page answered HTTP 500
    (``no such table: users``), which is the Phase-31 UAT blocker this closes
    (PKG-01 «the operator launches the distribution and reaches a working UI»,
    PKG-04 boot/migrate/restart).

    No second migration mechanism is introduced: the already-shipped
    ``adapters.migrate`` is reused as-is. It carries no exception handling here on
    purpose — a ``CalledProcessError`` from ``alembic`` propagates and
    ``start()`` is never reached, so the app can never serve traffic on an
    unmigrated or half-migrated schema (T-31-06); ``main()`` turns that into a
    visible message plus a non-zero exit (T-31-07).

    No ``mkdir`` belongs here: ``alembic/env.py`` already creates a missing
    parent directory for the sqlite URL, so the migration itself materialises
    ``data\\``.
    """
    migrate(paths)
    app_process.start()


def main() -> None:
    paths = build_paths()
    app_process = adapters.AppProcess(paths)
    try:
        boot(paths, app_process)
    except Exception as exc:
        # run.bat parity: report and exit non-zero WITHOUT starting the server.
        print(f"Migration failed - server not started: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
    _open_browser_soon()
    try:
        while True:
            try:
                run_once(paths, app_process)
            except Exception as exc:
                # apply_update's rollback already restarted the app on the previous
                # version — keep watching instead of exiting and stopping it.
                print(
                    f"Обновление не применено, приложение работает на прежней "
                    f"версии: {exc}",
                    file=sys.stderr,
                )
            time.sleep(_WATCH_INTERVAL)
    except KeyboardInterrupt:
        pass
    finally:
        app_process.stop()


if __name__ == "__main__":
    main()

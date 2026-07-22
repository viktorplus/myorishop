"""Windows side-effect adapters for the launcher swap state machine (PKG-04).

These thin adapters supply the real process/HTTP/file side effects that
``launcher.swap.apply_update`` takes as injected callbacks. They are stdlib-only
and import NO ``app.*`` code (the launcher must not lock ``app\\`` — RESEARCH
Pitfall 3, WinError 32).

CLIENT-only note: the launcher never runs against the central PostgreSQL server.
The server is the update TARGET, dialect-gated out of the packaging/update path
(RESEARCH Responsibility Map / Phase 32 UPD-06). Everything here targets the
local SQLite client install.
"""

from __future__ import annotations

import http.client
import os
import shutil
import subprocess
import time
from pathlib import Path

# The app listens here (byte-identical to run.bat's uvicorn --host/--port).
_HOST = "127.0.0.1"
_PORT = 8000


class AppProcess:
    """Owns the app's child process so stop is by handle, never by port.

    ``run.bat`` kills a stale server by scanning ``netstat`` for the listening
    PID — an ANTI-pattern the launcher replaces: it OWNS the child it spawned and
    stops THAT process, waiting on the handle (RESEARCH Pattern 4 step 2). Port
    scanning races and can kill the wrong process.
    """

    def __init__(self, paths):
        self.paths = paths
        self.proc: subprocess.Popen | None = None

    def _env(self) -> dict:
        env = os.environ.copy()
        # The Plan-02 contract: absolute data dir so the app's DB/backups live in
        # the sibling data\ that survives an app\ swap (PKG-03).
        env["MYORISHOP_DATA_DIR"] = str(Path(self.paths.data).resolve())
        return env

    def start(self) -> None:
        """Spawn ``app\\python.exe -m uvicorn app.main:app`` and retain the PID."""
        python = Path(self.paths.app) / "python.exe"
        self.proc = subprocess.Popen(
            [
                str(python),
                "-m",
                "uvicorn",
                "app.main:app",
                "--host",
                _HOST,
                "--port",
                str(_PORT),
            ],
            cwd=str(self.paths.app),
            env=self._env(),
        )

    def stop(self, timeout: float = 30.0) -> None:
        """Terminate the OWNED child and WAIT on its handle (no port kill).

        Graceful ``terminate()`` then ``wait(timeout)``; on timeout, hard
        ``kill()`` and wait again so the app\\ directory is unlocked before the
        rename swap (Windows will not rename a dir holding a running process).
        """
        if self.proc is None:
            return
        self.proc.terminate()
        try:
            self.proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            self.proc.kill()
            self.proc.wait()
        finally:
            self.proc = None


def migrate(paths) -> None:
    """Run ``app\\python.exe -m alembic upgrade head`` on the swapped layout.

    CWD is ``app\\`` and ``MYORISHOP_DATA_DIR`` points at the sibling data dir so
    migrations apply to the operator's real DB. Raises ``CalledProcessError`` on
    a non-zero exit (check=True) — apply_update turns that into a rollback.
    """
    python = Path(paths.app) / "python.exe"
    env = os.environ.copy()
    env["MYORISHOP_DATA_DIR"] = str(Path(paths.data).resolve())
    subprocess.run(
        [str(python), "-m", "alembic", "upgrade", "head"],
        cwd=str(paths.app),
        env=env,
        check=True,
    )


def health_ok(timeout: float = 30.0, interval: float = 0.5) -> bool:
    """Poll ``http://127.0.0.1:8000/`` and treat ANY response as alive.

    There is no ``/health`` route; an anonymous request redirects
    ``302/303 -> /login`` (app/services/security.py PUBLIC_PATHS). Any HTTP
    status (including the login redirect) means the server is up. Returns False
    only if the connection is still refused after ``timeout`` seconds.
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        conn = http.client.HTTPConnection(_HOST, _PORT, timeout=interval * 4)
        try:
            conn.request("GET", "/")
            resp = conn.getresponse()
            resp.read()
            # Any status line — including 302/303 -> /login — means "alive".
            if resp.status:
                return True
        except (OSError, http.client.HTTPException):
            pass
        finally:
            conn.close()
        time.sleep(interval)
    return False


def backup_restore(backup_path, db_path) -> None:
    """Restore the pre-update DB and DELETE its stale WAL sidecars (Pitfall 4).

    Copies ``backup_path`` over ``db_path`` then unlinks ``db_path`` + ``-wal``
    and ``-shm`` — restore.bat parity. Without deleting the sidecars, SQLite
    replays the newer run's stale WAL into the restored file and corrupts it.
    This is the DB half of the matched-pair rollback (T-31-06).
    """
    db_path = Path(db_path)
    shutil.copy(backup_path, db_path)
    for suffix in ("-wal", "-shm"):
        sidecar = db_path.with_name(db_path.name + suffix)
        sidecar.unlink(missing_ok=True)

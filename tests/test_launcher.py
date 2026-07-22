"""Wave-0 RED validation scaffold for Phase 31 PKG-04 (stable launcher swap/rollback).

Contract note (Nyquist Wave 0): RED-by-design. The launcher.swap / launcher.adapters
symbols (Paths, Pending, apply_update, parse_pending, backup_restore) are built in
Plan 03 and imported INSIDE each test body so Wave-0 collection stays green. The
callbacks (stop_app / start_app / migrate / health_ok / backup_restore) are INJECTED
so the swap+rollback sequencing is unit-testable on ANY OS with fake dirs — no
Windows / process specifics (RESEARCH Code Examples 'apply_update').

Threats pinned here: T-31-04 (swap runs attacker-staged code — refuse to act without
a valid marker), T-31-05 (path-traversal via staged / pending.json escaping the
install root, ASVS V12), T-31-06 (half-applied update / data loss — matched-pair
code+DB rollback with WAL-sidecar delete). PKG-04.
"""

import json
import os
from pathlib import Path

import pytest


def _install_layout(tmp_path: Path, app_marker: str = "v1", staged_marker: str = "v2"):
    """Build a fake install root with app/, staged/ and data/ dirs + markers."""
    root = tmp_path / "MyOriShop"
    app_dir = root / "app"
    staged = root / "staged"
    data = root / "data"
    for directory in (app_dir, staged, data):
        directory.mkdir(parents=True)
    (app_dir / "marker.txt").write_text(app_marker, encoding="utf-8")
    (staged / "marker.txt").write_text(staged_marker, encoding="utf-8")
    return root, app_dir, staged, data


# --- PKG-04: swap / rollback state machine ----------------------------------


def test_apply_update_happy_path(tmp_path):
    """PKG-04: happy path stops the app, renames app/→app.prev/ then staged/→app/,
    migrates on the swapped layout, health-checks, and deletes app.prev/ on
    success. RED until Plan 03 builds launcher.swap.apply_update."""
    from launcher.swap import Paths, Pending, apply_update  # noqa: PLC0415

    root, app_dir, staged, data = _install_layout(tmp_path)
    backup = data / "backup.db"
    backup.write_text("BACKUP", encoding="utf-8")
    paths = Paths(
        app=app_dir,
        app_prev=root / "app.prev",
        staged=staged,
        app_failed=root / "app.failed",
    )
    pending = Pending(
        staged_dir=staged, expected_version="1.2", db_backup_path=backup
    )

    events: list = []
    seen: dict = {}

    def stop_app():
        events.append("stop")

    def start_app():
        events.append("start")

    def migrate():
        events.append("migrate")
        # By migrate time both os.replace calls are done: app/ holds the staged
        # content and app.prev/ still exists (kept until health passes).
        seen["app_marker_at_migrate"] = (app_dir / "marker.txt").read_text()
        seen["prev_exists_at_migrate"] = (root / "app.prev").exists()

    def health_ok():
        events.append("health")
        return True

    def backup_restore(path):
        events.append(("restore", path))

    apply_update(
        paths,
        pending,
        stop_app=stop_app,
        start_app=start_app,
        migrate=migrate,
        health_ok=health_ok,
        backup_restore=backup_restore,
    )

    # Staged content is now live at app/; app.prev/ removed on success.
    assert (app_dir / "marker.txt").read_text() == "v2"
    assert not (root / "app.prev").exists()
    # migrate ran AFTER both renames (saw the swapped layout).
    assert seen["app_marker_at_migrate"] == "v2"
    assert seen["prev_exists_at_migrate"] is True
    # Happy path never rolled back.
    assert events[0] == "stop"
    assert not any(isinstance(e, tuple) and e[0] == "restore" for e in events)


def test_apply_update_rolls_back_on_migrate_failure(tmp_path):
    """PKG-04 (T-31-06): when migrate raises, app/ is restored to the ORIGINAL
    content, the staged code is moved aside to app.failed/, the pre-update DB is
    restored via backup_restore(pending.db_backup_path), the app is restarted,
    and apply_update re-raises. RED until Plan 03."""
    from launcher.swap import Paths, Pending, apply_update  # noqa: PLC0415

    root, app_dir, staged, data = _install_layout(tmp_path)
    backup = data / "backup.db"
    backup.write_text("BACKUP", encoding="utf-8")
    paths = Paths(
        app=app_dir,
        app_prev=root / "app.prev",
        staged=staged,
        app_failed=root / "app.failed",
    )
    pending = Pending(
        staged_dir=staged, expected_version="1.2", db_backup_path=backup
    )

    restored: list = []
    starts: list = []

    def stop_app():
        pass

    def start_app():
        starts.append(1)

    def migrate():
        raise RuntimeError("alembic upgrade head failed")

    def health_ok():
        return True

    def backup_restore(path):
        restored.append(path)

    with pytest.raises(RuntimeError):
        apply_update(
            paths,
            pending,
            stop_app=stop_app,
            start_app=start_app,
            migrate=migrate,
            health_ok=health_ok,
            backup_restore=backup_restore,
        )

    assert (app_dir / "marker.txt").read_text() == "v1", "app/ not restored"
    assert (root / "app.failed" / "marker.txt").read_text() == "v2", (
        "staged code not moved aside to app.failed/"
    )
    assert restored == [backup], "matched-pair DB restore not invoked"
    assert starts, "start_app must run again after rollback"


def test_apply_update_rolls_back_on_failed_health_check(tmp_path):
    """PKG-04 (T-31-06): a failing post-update health check triggers the SAME
    matched-pair rollback path as a migrate failure. RED until Plan 03."""
    from launcher.swap import Paths, Pending, apply_update  # noqa: PLC0415

    root, app_dir, staged, data = _install_layout(tmp_path)
    backup = data / "backup.db"
    backup.write_text("BACKUP", encoding="utf-8")
    paths = Paths(
        app=app_dir,
        app_prev=root / "app.prev",
        staged=staged,
        app_failed=root / "app.failed",
    )
    pending = Pending(
        staged_dir=staged, expected_version="1.2", db_backup_path=backup
    )

    restored: list = []
    starts: list = []

    def stop_app():
        pass

    def start_app():
        starts.append(1)

    def migrate():
        pass

    def health_ok():
        return False

    def backup_restore(path):
        restored.append(path)

    with pytest.raises(Exception):
        apply_update(
            paths,
            pending,
            stop_app=stop_app,
            start_app=start_app,
            migrate=migrate,
            health_ok=health_ok,
            backup_restore=backup_restore,
        )

    assert (app_dir / "marker.txt").read_text() == "v1"
    assert (root / "app.failed" / "marker.txt").read_text() == "v2"
    assert restored == [backup]
    assert starts


def test_backup_restore_deletes_wal_sidecars(tmp_path):
    """PKG-04 / RESEARCH Pitfall 4 (T-31-06): the backup_restore adapter copies
    the backup over data/myorishop.db then DELETES the -wal/-shm sidecars,
    mirroring restore.bat — else SQLite replays a stale WAL and corrupts the
    restored DB. RED until Plan 03's launcher.adapters."""
    from launcher.adapters import backup_restore  # noqa: PLC0415

    data = tmp_path / "data"
    data.mkdir()
    db = data / "myorishop.db"
    db.write_text("OLD", encoding="utf-8")
    (data / "myorishop.db-wal").write_text("stale-wal", encoding="utf-8")
    (data / "myorishop.db-shm").write_text("stale-shm", encoding="utf-8")
    backup = tmp_path / "backup.db"
    backup.write_text("GOOD", encoding="utf-8")

    backup_restore(backup, db)

    assert db.read_text() == "GOOD"
    assert not (data / "myorishop.db-wal").exists()
    assert not (data / "myorishop.db-shm").exists()


# --- PKG-04 security V12: marker validation ---------------------------------


def test_parse_pending_rejects_path_traversal(tmp_path):
    """PKG-04 / ASVS V12 (T-31-05): parse_pending rejects a staged_dir or
    db_backup_path that escapes the install root via '..' or an absolute path.
    RED until Plan 03."""
    from launcher.swap import parse_pending  # noqa: PLC0415

    install_root = tmp_path / "MyOriShop"
    install_root.mkdir()

    escaping = [
        {"staged_dir": "../evil", "expected_version": "1.2", "db_backup_path": "data/backup.db"},
        {"staged_dir": "staged", "expected_version": "1.2", "db_backup_path": "../../etc/passwd"},
        {"staged_dir": "C:\\Windows\\Temp\\evil", "expected_version": "1.2", "db_backup_path": "data/backup.db"},
        {"staged_dir": "/abs/evil", "expected_version": "1.2", "db_backup_path": "data/backup.db"},
    ]
    for payload in escaping:
        with pytest.raises(ValueError):
            parse_pending(json.dumps(payload), install_root)


def test_parse_pending_requires_valid_marker(tmp_path):
    """PKG-04 / ASVS V5+V10 (T-31-04): malformed or missing-field pending.json is
    rejected BEFORE any swap — the launcher never acts on an invalid marker. RED
    until Plan 03."""
    from launcher.swap import parse_pending  # noqa: PLC0415

    install_root = tmp_path / "MyOriShop"
    install_root.mkdir()

    bad = [
        "{ not valid json",  # malformed JSON (json.JSONDecodeError is a ValueError)
        json.dumps({"expected_version": "1.2"}),  # missing staged_dir + db_backup_path
        json.dumps({"staged_dir": "staged"}),  # missing version + backup path
        json.dumps([]),  # not a JSON object
    ]
    for payload in bad:
        with pytest.raises(ValueError):
            parse_pending(payload, install_root)


# --- Phase 32 UPD-04: app-marker -> launcher integration + version-match health


def test_apply_rolls_back(tmp_path):
    """UPD-04 (T-32-08): the named Phase-32 anchor for the matched-pair rollback.

    Ties the shipped launcher rollback (restore original app/, move staged aside
    to app.failed/, restore the pre-update DB via backup_restore(db_backup_path),
    restart, re-raise) to the Phase-32 update service: the app-side
    ``update.stage_pending`` is the marker author the launcher consumes. RED until
    Wave 03 builds ``app.services.update``; the launcher invariants already hold
    (mirrors ``test_apply_update_rolls_back_on_migrate_failure``).
    """
    from app.services import update  # noqa: PLC0415 — RED gate until Wave 03
    from launcher.swap import Paths, Pending, apply_update  # noqa: PLC0415

    # The app side must expose the marker-writer the launcher's contract depends on.
    assert hasattr(update, "stage_pending")

    root, app_dir, staged, data = _install_layout(tmp_path)
    backup = data / "backup.db"
    backup.write_text("BACKUP", encoding="utf-8")
    paths = Paths(
        app=app_dir,
        app_prev=root / "app.prev",
        staged=staged,
        app_failed=root / "app.failed",
    )
    pending = Pending(
        staged_dir=staged, expected_version="1.16", db_backup_path=backup
    )

    restored: list = []
    starts: list = []

    def stop_app():
        pass

    def start_app():
        starts.append(1)

    def migrate():
        raise RuntimeError("alembic upgrade head failed")

    def health_ok():
        return True

    def backup_restore(path):
        restored.append(path)

    with pytest.raises(RuntimeError):
        apply_update(
            paths,
            pending,
            stop_app=stop_app,
            start_app=start_app,
            migrate=migrate,
            health_ok=health_ok,
            backup_restore=backup_restore,
        )

    assert (app_dir / "marker.txt").read_text() == "v1", "app/ not restored"
    assert (root / "app.failed" / "marker.txt").read_text() == "v2", (
        "staged code not moved aside to app.failed/"
    )
    assert restored == [backup], "matched-pair DB restore not invoked"
    assert starts, "start_app must run again after rollback"


def test_run_once_applies_app_written_marker(tmp_path, monkeypatch):
    """UPD-04 integration: the APP writes ``data/pending.json`` via
    ``update.stage_pending`` and the launcher's ``run_once`` consumes it — one
    real swap runs, the staged content goes live at app/, and the marker is
    deleted. Proves the app-writes / launcher-consumes contract end to end. RED
    until Wave 03 builds ``stage_pending``.
    """
    from app.services import update  # noqa: PLC0415
    from launcher import __main__ as launcher_main  # noqa: PLC0415
    from launcher.swap import Paths  # noqa: PLC0415

    root = tmp_path / "MyOriShop"
    app_dir = root / "app"
    staged = root / "staged"
    data = root / "data"
    for directory in (app_dir, staged, data):
        directory.mkdir(parents=True)
    (app_dir / "marker.txt").write_text("v1", encoding="utf-8")
    (staged / "marker.txt").write_text("v2", encoding="utf-8")
    backup = data / "backups" / "b.db"
    backup.parent.mkdir(parents=True)
    backup.write_text("BACKUP", encoding="utf-8")
    (data / "myorishop.db").write_text("DB", encoding="utf-8")

    paths = Paths(
        app=app_dir,
        app_prev=root / "app.prev",
        staged=staged,
        app_failed=root / "app.failed",
        install_root=root,
        data=data,
    )

    # The APP side writes the marker (RED until Wave 03 builds stage_pending).
    update.stage_pending(root, "staged", "1.16", "data/backups/b.db")
    assert (data / "pending.json").exists()

    swaps: list = []
    real_replace = os.replace

    def counting_replace(src, dst):
        swaps.append((str(src), str(dst)))
        real_replace(src, dst)

    monkeypatch.setattr(os, "replace", counting_replace)

    class _FakeProc:
        def start(self):
            pass

        def stop(self, *args, **kwargs):
            pass

    ran = launcher_main.run_once(
        paths,
        _FakeProc(),
        migrate=lambda *_a, **_k: None,
        health_ok=lambda *_a, **_k: True,
        backup_restore=lambda *_a, **_k: None,
    )

    assert ran is True
    assert swaps, "no real os.replace swap ran"
    # Staged content is now live at app/, and the consumed marker is deleted.
    assert (app_dir / "marker.txt").read_text() == "v2"
    assert not (data / "pending.json").exists()


def test_health_ok_requires_version_match(tmp_path):
    """UPD-04 stronger health (OQ-3/OQ-6): ``health_ok(expected_version=...)``
    returns True only when ``GET /health`` answers ``{"version": expected}``, and
    False on a stale version or a refused connection; ``expected_version=None``
    keeps the legacy "any status = alive" back-compat. Launcher stays stdlib-only
    (a tiny ``http.server`` stub, no ``app.*`` import). RED until Wave 04 adds the
    ``expected_version`` parameter.
    """
    import http.server  # noqa: PLC0415
    import threading  # noqa: PLC0415

    from launcher.adapters import health_ok  # noqa: PLC0415

    def _serve(version_payload: str):
        class _Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):  # noqa: N802 — BaseHTTPRequestHandler API
                body = ('{"version": "%s"}' % version_payload).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *args):  # silence the stub server
                pass

        try:
            httpd = http.server.HTTPServer(("127.0.0.1", 8000), _Handler)
        except OSError as exc:
            # Some sandboxed/dev boxes forbid binding 127.0.0.1:8000 (WinError
            # 10013). health_ok targets 8000 by contract (adapters._PORT), so skip
            # rather than fail spuriously — mirrors the minisign binary skip-gate.
            pytest.skip(f"cannot bind 127.0.0.1:8000 in this environment: {exc}")
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        return httpd

    httpd = _serve("1.16")
    try:
        assert health_ok(expected_version="1.16", timeout=3.0) is True
        # Stale swap: the server still reports the OLD version ⇒ not a match.
        assert health_ok(expected_version="1.15", timeout=3.0) is False
        # Legacy back-compat: no expected version ⇒ any status = alive.
        assert health_ok(expected_version=None, timeout=3.0) is True
    finally:
        httpd.shutdown()

    # Connection refused ⇒ False even with an expected version.
    assert health_ok(expected_version="1.16", timeout=1.0) is False

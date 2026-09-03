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
import shutil
import subprocess
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


# --- PKG-04 GAP-3: a failed update must never brick the install -------------


def _swap_fixture(tmp_path):
    """Fake install layout + the Paths/Pending pair the swap state machine takes."""
    from launcher.swap import Paths, Pending  # noqa: PLC0415

    root, app_dir, staged, data = _install_layout(tmp_path)
    backup = data / "backup.db"
    backup.write_text("BACKUP", encoding="utf-8")
    paths = Paths(
        app=app_dir,
        app_prev=root / "app.prev",
        staged=staged,
        app_failed=root / "app.failed",
        install_root=root,
        data=data,
    )
    pending = Pending(staged_dir=staged, expected_version="1.2", db_backup_path=backup)
    return root, app_dir, staged, data, paths, pending


def test_apply_update_refuses_when_staged_dir_is_missing(tmp_path):
    """PKG-04 (T-31-06), 31-UAT blocker: with staged\\ gone the cycle is refused
    BEFORE stop_app and before any rename — app\\ is never renamed away with
    nothing to put back. Today the first os.replace sits outside the try, so the
    app dir is destroyed and the install is bricked."""
    from launcher.swap import apply_update  # noqa: PLC0415

    root, app_dir, staged, _data, paths, pending = _swap_fixture(tmp_path)
    shutil.rmtree(staged)

    events: list = []

    with pytest.raises(FileNotFoundError):
        apply_update(
            paths,
            pending,
            stop_app=lambda: events.append("stop"),
            start_app=lambda: events.append("start"),
            migrate=lambda: events.append("migrate"),
            health_ok=lambda: True,
            backup_restore=lambda path: events.append(("restore", path)),
        )

    assert events == [], "the cycle must not begin — not even stop_app"
    assert (app_dir / "marker.txt").read_text() == "v1", "app/ was renamed away"
    assert not (root / "app.prev").exists()
    assert not (root / "app.failed").exists()


def test_rollback_leaves_db_untouched_when_no_swap_happened(tmp_path, monkeypatch):
    """PKG-04 (T-31-06b): when the FIRST rename fails nothing was swapped and no
    migration ran, so the rollback must NOT restore the DB — that would silently
    discard every operator write made since the backup was taken. app/ stays
    intact and the app is restarted."""
    from launcher.swap import apply_update  # noqa: PLC0415

    _root, app_dir, _staged, _data, paths, pending = _swap_fixture(tmp_path)

    restored: list = []
    starts: list = []
    real_replace = os.replace
    calls: list = []

    def failing_replace(src, dst):
        calls.append((src, dst))
        if len(calls) == 1:
            raise OSError(32, "The process cannot access the file")
        real_replace(src, dst)

    monkeypatch.setattr(os, "replace", failing_replace)

    with pytest.raises(OSError):
        apply_update(
            paths,
            pending,
            stop_app=lambda: None,
            start_app=lambda: starts.append(1),
            migrate=lambda: restored.append("migrate-ran"),
            health_ok=lambda: True,
            backup_restore=lambda path: restored.append(path),
        )

    assert restored == [], "nothing was swapped or migrated — the DB must not be rolled back"
    assert (app_dir / "marker.txt").read_text() == "v1"
    assert starts, "start_app must run again so the install is left serving"


def test_rollback_succeeds_when_app_failed_already_exists(tmp_path):
    """PKG-04 (T-31-06c): a previous rollback leaves app.failed\\ behind and
    Windows os.replace CANNOT replace an existing directory (WinError 5, empty or
    not). The rollback therefore clears its destination first; app/ is restored
    and the ORIGINAL migrate error propagates, never a PermissionError raised by
    the rollback's own rename."""
    from launcher.swap import apply_update  # noqa: PLC0415

    root, app_dir, _staged, _data, paths, pending = _swap_fixture(tmp_path)
    stale = root / "app.failed"
    stale.mkdir()
    (stale / "marker.txt").write_text("v0-stale", encoding="utf-8")

    starts: list = []
    restored: list = []

    def migrate():
        raise RuntimeError("alembic upgrade head failed")

    with pytest.raises(RuntimeError, match="alembic upgrade head failed"):
        apply_update(
            paths,
            pending,
            stop_app=lambda: None,
            start_app=lambda: starts.append(1),
            migrate=migrate,
            health_ok=lambda: True,
            backup_restore=lambda path: restored.append(path),
        )

    assert (app_dir / "marker.txt").read_text() == "v1", "app/ not restored"
    assert (stale / "marker.txt").read_text() == "v2", "stale app.failed/ not rotated out"
    assert restored == [pending.db_backup_path], "matched-pair DB restore not invoked"
    assert starts


def test_apply_update_rotates_a_stale_app_prev(tmp_path):
    """PKG-04 (T-31-06c): a stale app.prev\\ left by a partially failed cleanup
    must not block the forward swap — without clearing the destination the first
    os.replace raises WinError 5 and no update could ever apply again."""
    from launcher.swap import apply_update  # noqa: PLC0415

    root, app_dir, _staged, _data, paths, pending = _swap_fixture(tmp_path)
    stale_prev = root / "app.prev"
    stale_prev.mkdir()
    (stale_prev / "marker.txt").write_text("v0-stale", encoding="utf-8")

    apply_update(
        paths,
        pending,
        stop_app=lambda: None,
        start_app=lambda: None,
        migrate=lambda: None,
        health_ok=lambda: True,
        backup_restore=lambda path: None,
    )

    assert (app_dir / "marker.txt").read_text() == "v2"
    assert not stale_prev.exists()


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


# --- PKG-04 GAP-3: the marker is ALWAYS consumed, the watch loop survives ----


def _write_marker(data: Path, staged_dir: str = "staged") -> Path:
    """Hand-place a valid data/pending.json (what Phase 31 drives the swap with)."""
    marker = data / "pending.json"
    marker.write_text(
        json.dumps(
            {
                "staged_dir": staged_dir,
                "expected_version": "1.2",
                "db_backup_path": "data/backup.db",
            }
        ),
        encoding="utf-8",
    )
    return marker


class _NoopProc:
    """Fake AppProcess for the run_once integration ticks."""

    def start(self):
        pass

    def stop(self, *args, **kwargs):
        pass


def _tick(paths, *, migrate):
    """One run_once tick with fake adapters (real os.replace on tmp dirs)."""
    from launcher import __main__ as launcher_main  # noqa: PLC0415

    return launcher_main.run_once(
        paths,
        _NoopProc(),
        migrate=migrate,
        health_ok=lambda *_a, **_k: True,
        backup_restore=lambda *_a, **_k: None,
    )


def test_two_ticks_with_one_failing_update_keep_app_dir(tmp_path):
    """PKG-04 (T-31-04/T-31-06), THE 31-UAT regression: a failed update must not
    be replayed. Tick 1 fails and rolls back; the marker is quarantined to
    data/pending.failed.json. Tick 2 is a no-op and app\\ is still there.

    Today tick 2 renames app\\ away and dies with FileNotFoundError — one failed
    update bricks the install."""
    _root, app_dir, _staged, data, paths, _pending = _swap_fixture(tmp_path)
    _write_marker(data)

    def failing_migrate(*_a, **_k):
        raise RuntimeError("alembic upgrade head failed")

    # TICK 1 — the update fails and rolls back.
    with pytest.raises(RuntimeError):
        _tick(paths, migrate=failing_migrate)

    assert (app_dir / "marker.txt").read_text() == "v1", "app/ not restored"
    assert (paths.app_failed / "marker.txt").read_text() == "v2"
    assert not (data / "pending.json").exists(), "failed marker left for replay"
    assert (data / "pending.failed.json").exists(), "failed marker not quarantined"

    # TICK 2 — the very next watch-loop tick, identical arguments.
    assert _tick(paths, migrate=failing_migrate) is False
    assert (app_dir / "marker.txt").read_text() == "v1", "app/ destroyed by the replay"
    assert not paths.app_prev.exists()


def test_run_once_refuses_marker_whose_staged_dir_is_gone(tmp_path):
    """PKG-04 (T-31-04): a valid marker whose staged\\ no longer exists is refused
    at the marker level — before any side effect — and quarantined."""
    _root, app_dir, staged, data, paths, _pending = _swap_fixture(tmp_path)
    _write_marker(data)
    shutil.rmtree(staged)

    def never_called(*_a, **_k):  # pragma: no cover - must never run
        raise AssertionError("apply_update was entered on an unsatisfiable marker")

    assert _tick(paths, migrate=never_called) is False
    assert (app_dir / "marker.txt").read_text() == "v1"
    assert not (data / "pending.json").exists()
    assert (data / "pending.failed.json").exists()


def test_run_once_quarantines_an_undecodable_marker(tmp_path):
    """CR-02 (T-31-04): a non-UTF-8 pending.json is consumed, never replayed.

    ``UnicodeDecodeError`` IS a ``ValueError``, but the read sat OUTSIDE the
    guard, so it escaped ``run_once`` entirely: the marker was neither deleted
    nor quarantined and ``main()``'s 2-second watch loop re-read the same bytes
    forever. The marker is attacker-controlled input (T-31-04) and Phase 31's
    documented workflow hand-places it, so a cp1251-saved file was enough to
    wedge the update channel permanently and flood stderr."""
    _root, app_dir, _staged, data, paths, _pending = _swap_fixture(tmp_path)
    (data / "pending.json").write_bytes(b"\xff\xfe{ not utf-8 }")

    def never_called(*_a, **_k):  # pragma: no cover - must never run
        raise AssertionError("apply_update was entered on an undecodable marker")

    assert _tick(paths, migrate=never_called) is False
    assert not (data / "pending.json").exists(), "undecodable marker left for replay"
    assert (data / "pending.failed.json").exists(), "undecodable marker not quarantined"
    assert (app_dir / "marker.txt").read_text() == "v1"


def test_run_once_quarantines_a_torn_marker_instead_of_deleting_it(tmp_path):
    """WR-03: a truncated read must leave evidence, not silently destroy the
    staged update. The old handler called ``marker.unlink()``, so a read landing
    inside a non-atomic write deleted the marker the app had just staged — the
    operator clicked «Обновить и перезапустить», a VACUUM backup was taken,
    staged\\ was populated, and then nothing happened, with no record of why."""
    _root, _app_dir, _staged, data, paths, _pending = _swap_fixture(tmp_path)
    (data / "pending.json").write_text('{"staged_dir": "sta', encoding="utf-8")

    assert _tick(paths, migrate=lambda *_a, **_k: None) is False
    assert not (data / "pending.json").exists()
    assert (data / "pending.failed.json").read_text() == '{"staged_dir": "sta'


def test_run_once_quarantines_marker_after_failed_apply(tmp_path):
    """PKG-04: the quarantine overwrites atomically — two failing ticks leave
    exactly ONE pending.failed.json and the quarantine itself never raises."""
    root, app_dir, _staged, data, paths, _pending = _swap_fixture(tmp_path)

    def failing_migrate(*_a, **_k):
        raise RuntimeError("alembic upgrade head failed")

    for _attempt in range(2):
        staged = root / "staged"
        staged.mkdir(exist_ok=True)
        (staged / "marker.txt").write_text("v2", encoding="utf-8")
        _write_marker(data)
        with pytest.raises(RuntimeError, match="alembic upgrade head failed"):
            _tick(paths, migrate=failing_migrate)

    assert [p.name for p in data.glob("pending.failed*.json")] == ["pending.failed.json"]
    assert not (data / "pending.json").exists()
    assert (app_dir / "marker.txt").read_text() == "v1"


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


# --- PKG-01/PKG-04 GAP-1: first-run boot migration --------------------------


class _RecordingProc:
    """Fake AppProcess recording start/stop so boot ordering is observable."""

    def __init__(self, events: list):
        self.events = events

    def start(self):
        self.events.append("start")

    def stop(self, *args, **kwargs):
        self.events.append("stop")


def test_boot_migrates_before_starting_the_app(tmp_path):
    """PKG-01 (T-31-06): ``boot`` runs the migration STRICTLY before the app is
    started, mirroring run.bat's «migrate, then serve» contract. Without this the
    packaged first run creates an empty DB file with no schema and every page is
    HTTP 500 (`no such table: users`) — the 31-UAT blocker."""
    from launcher import __main__ as launcher_main  # noqa: PLC0415
    from launcher.swap import Paths  # noqa: PLC0415

    root = tmp_path / "MyOriShop"
    paths = Paths(
        app=root / "app",
        app_prev=root / "app.prev",
        staged=root / "staged",
        app_failed=root / "app.failed",
        install_root=root,
        data=root / "data",
    )

    events: list = []
    seen: list = []

    def fake_migrate(given_paths):
        events.append("migrate")
        seen.append(given_paths)

    launcher_main.boot(paths, _RecordingProc(events), migrate=fake_migrate)

    assert events == ["migrate", "start"], "the app must not start before migrating"
    assert seen == [paths], "migrate takes the launcher-derived paths"


def test_boot_aborts_when_migration_fails(tmp_path):
    """PKG-01 (T-31-07): a failing ``alembic upgrade head`` aborts the boot — the
    exception propagates and ``start()`` is NEVER called, so the app can never
    serve traffic against an unmigrated / half-migrated schema."""
    from launcher import __main__ as launcher_main  # noqa: PLC0415
    from launcher.swap import Paths  # noqa: PLC0415

    root = tmp_path / "MyOriShop"
    paths = Paths(
        app=root / "app",
        app_prev=root / "app.prev",
        staged=root / "staged",
        app_failed=root / "app.failed",
        install_root=root,
        data=root / "data",
    )

    events: list = []

    def failing_migrate(_paths):
        raise subprocess.CalledProcessError(1, "alembic")

    with pytest.raises(subprocess.CalledProcessError):
        launcher_main.boot(paths, _RecordingProc(events), migrate=failing_migrate)

    assert "start" not in events, "app started on an unmigrated schema"


def test_main_boots_through_migration_before_the_watch_loop(tmp_path, monkeypatch):
    """PKG-01 wiring: ``main()`` goes through ``boot`` (migrate-then-start) BEFORE
    the watch loop — the gap the UAT found was that main() called
    ``app_process.start()`` directly and ``adapters.migrate`` was reachable only
    from the update-swap path.

    The patched ``boot`` raises ``SystemExit(0)`` (a BaseException, so main()'s
    ``except Exception`` boot guard does not swallow it) which stops main() before
    ``_open_browser_soon`` — this test must never open a browser window.
    """
    from launcher import __main__ as launcher_main  # noqa: PLC0415
    from launcher.swap import Paths  # noqa: PLC0415

    root = tmp_path / "MyOriShop"
    paths = Paths(
        app=root / "app",
        app_prev=root / "app.prev",
        staged=root / "staged",
        app_failed=root / "app.failed",
        install_root=root,
        data=root / "data",
    )

    calls: list = []

    def guard_browser(*_a, **_k):  # pragma: no cover - must never run
        raise AssertionError("main() opened a browser before/without booting")

    class _NoopProc:
        def __init__(self, _paths):
            pass

        def start(self):
            raise AssertionError("main() must start the app through boot(), not directly")

        def stop(self, *args, **kwargs):
            pass

    def fake_boot(given_paths, _proc, **_kwargs):
        calls.append(given_paths)
        raise SystemExit(0)

    monkeypatch.setattr(launcher_main, "build_paths", lambda *a, **k: paths)
    monkeypatch.setattr(launcher_main.adapters, "AppProcess", _NoopProc)
    monkeypatch.setattr(launcher_main, "_open_browser_soon", guard_browser)
    monkeypatch.setattr(launcher_main, "boot", fake_boot)

    with pytest.raises(SystemExit) as excinfo:
        launcher_main.main()

    assert excinfo.value.code == 0
    assert calls == [paths], "main() did not boot through the migration step"

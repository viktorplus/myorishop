"""Pure, callback-injected swap/rollback state machine + marker parsing (PKG-04).

This module contains NO Windows/process specifics — the stop/start/migrate/
health/restore side effects are INJECTED as callbacks so the swap and rollback
sequencing is unit-testable on any OS with fake directories (RESEARCH Code
Examples ``apply_update``; tests/test_launcher.py). The launcher imports only
the stdlib and never ``app.*`` (importing the app would lock ``app\\`` and break
the rename swap — RESEARCH Pitfall 3).

Threats mitigated here:
- T-31-04 (swap runs attacker-staged code): the entry point refuses to swap
  without a valid ``pending.json``; ``parse_pending`` is the strict gate.
- T-31-05 (path traversal via the marker, ASVS V12): ``parse_pending`` resolves
  and confines ``staged_dir``/``db_backup_path`` under the install root and
  rejects ``..``/absolute escapes BEFORE any ``os.replace``.
- T-31-06 (half-applied update / data loss): ``apply_update`` performs a
  matched-pair rollback — it restores the previous ``app\\`` AND the pre-update
  DB together on any failure. The rollback is SCOPED TO THE STEPS THAT ACTUALLY
  RAN: both renames now sit inside the guarded region, a missing ``staged\\`` is
  refused before anything is touched, and the DB is restored only when the
  migration was attempted (T-31-06b). Every directory rename clears its
  destination first, because Windows ``os.replace`` cannot replace an existing
  directory — empty or not (WinError 5, T-31-06c).
"""

from __future__ import annotations

import json
import os
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path

# Exact set of keys a valid pending.json marker must carry (no more, no less).
_REQUIRED_KEYS = frozenset({"staged_dir", "expected_version", "db_backup_path"})


@dataclass(frozen=True)
class Paths:
    """The install-root directory layout the launcher swaps between.

    ``app``/``app_prev``/``staged``/``app_failed`` are the four dirs the swap
    renames; ``install_root`` and ``data`` are optional (the entry point fills
    them, the pure state machine does not need them) so the surface matches the
    Plan-01 test contract ``Paths(app, app_prev, staged, app_failed)``.
    """

    app: Path
    app_prev: Path
    staged: Path
    app_failed: Path
    install_root: Path | None = None
    data: Path | None = None


@dataclass(frozen=True)
class Pending:
    """A parsed, path-confined ``pending.json`` marker (PKG-04 schema)."""

    staged_dir: Path
    expected_version: str
    db_backup_path: Path


def apply_update(
    paths: Paths,
    pending: Pending,
    *,
    stop_app,
    start_app,
    migrate,
    health_ok,
    backup_restore,
) -> None:
    """Transactionally swap ``staged\\`` into ``app\\`` and migrate/restart.

    Happy path (RESEARCH skeleton, verbatim ordering):
      stop_app -> os.replace(app -> app_prev) -> os.replace(staged -> app) ->
      migrate -> start_app -> health_ok True -> rmtree(app_prev).

    ``migrate`` therefore runs strictly AFTER both renames (it sees the swapped
    layout) and BEFORE the previous dir is deleted (``app_prev`` is kept until
    the health check passes — it is half of the matched-pair rollback anchor).

    PRE-FLIGHT (T-31-06): a missing ``staged\\`` is refused BEFORE ``stop_app``
    and before the first rename, so ``app\\`` can never be renamed away with
    nothing to put back. The 31-UAT blocker was exactly this: a replayed marker
    whose staged dir had already been consumed renamed ``app\\`` to ``app.prev\\``
    and then died on the second rename, outside any rollback handler.

    On ANY failure the matched-pair rollback (T-31-06) fires, PROPORTIONALLY —
    it undoes only the steps that actually ran: stop the app; if the staged code
    was swapped in, park it at ``app_failed``; restore the previous ``app\\``;
    restore the pre-update DB via ``backup_restore(pending.db_backup_path)``
    (copy + delete -wal/-shm) ONLY when the migration was attempted (a failure
    before that point cannot have touched the schema, and restoring an older
    backup there would discard operator writes made since it was taken); restart
    the app on the restored code; re-raise the ORIGINAL exception. Code and DB
    revert together.

    Every rollback step is best-effort so no secondary failure can prevent the
    restoration or mask the real error. ONE double-fault branch does not keep the
    "code and DB revert together" promise: if parking the bad code fails AND the
    fallback rmtree of ``app\\`` also fails, the restoration is SKIPPED (leaving
    the present-but-bad ``app\\`` beats deleting the operator's only runnable
    copy) while the DB is still reverted — new code on an old schema. A distinct
    stderr line then tells the operator that ``app.prev\\`` is the recovery copy.

    ``app.failed\\`` is deliberately RETAINED for forensics until the NEXT
    rollback rotates it — it is cleared at write time, not after a successful
    update.
    """
    if not Path(paths.staged).exists():
        raise FileNotFoundError(
            f"staged directory is missing: {paths.staged} — update cycle refused "
            "before stopping the app and before any rename, so app\\ is never "
            "renamed away with nothing to put back (PKG-04, T-31-06)"
        )

    stop_app()
    prev_renamed = False
    staged_swapped = False
    migrate_attempted = False
    try:
        # Clear the destination first: Windows os.replace CANNOT replace an
        # existing directory (WinError 5 — measured, for an EMPTY one too). A
        # stale app.prev\ left by an earlier cycle whose cleanup rmtree partially
        # failed would otherwise block every future update. It MAY be the recovery
        # copy an incomplete rollback deliberately retained (see the skip branch
        # below); clearing it here is the accepted tradeoff for keeping the swap
        # repeatable — the operator's recovery window for that state is the failed
        # cycle itself, not the next one. The rollback anchor used below is the
        # one created BY the next rename, so this is safe (T-31-06c).
        shutil.rmtree(paths.app_prev, ignore_errors=True)
        os.replace(paths.app, paths.app_prev)
        prev_renamed = True
        os.replace(paths.staged, paths.app)
        staged_swapped = True
        migrate_attempted = True
        migrate()
        start_app()
        if not health_ok():
            raise RuntimeError("post-update health check failed")
    except Exception:
        # Proportional matched-pair rollback: code + DB revert together (T-31-06).
        _best_effort(stop_app)
        if staged_swapped:
            # Park the bad code for forensics; clear the destination first.
            shutil.rmtree(paths.app_failed, ignore_errors=True)
            try:
                os.replace(paths.app, paths.app_failed)
            except OSError:
                # Parking must never block the restoration — discard the failed
                # update's code instead (that is all app\ holds at this point).
                shutil.rmtree(paths.app, ignore_errors=True)
        if prev_renamed:
            restored = False
            if not Path(paths.app).exists():
                try:
                    os.replace(paths.app_prev, paths.app)
                    restored = True
                except OSError:
                    pass
            if not restored:
                # Double fault: leave the present app\ rather than delete the only
                # runnable copy, and tell the operator where the good one is.
                print(
                    "Откат неполный: app\\ не восстановлен, предыдущая версия "
                    "сохранена в app.prev\\",
                    file=sys.stderr,
                )
        if migrate_attempted:
            _best_effort(lambda: backup_restore(pending.db_backup_path))
        _best_effort(start_app)
        raise
    else:
        shutil.rmtree(paths.app_prev, ignore_errors=True)


def _best_effort(action) -> None:
    """Run a rollback step, swallowing its failure so the ORIGINAL error wins."""
    try:
        action()
    except Exception:  # noqa: BLE001 — a rollback step must never mask the cause
        pass


def parse_pending(raw: str, install_root: Path) -> Pending:
    """Strictly parse + path-confine a ``pending.json`` marker (T-31-04/05).

    Rejects (raises ``ValueError``) BEFORE returning a ``Pending``:
      - malformed JSON (``json.JSONDecodeError`` is a ``ValueError`` subclass),
      - a top-level value that is not a JSON object,
      - a key set that is not exactly {staged_dir, expected_version,
        db_backup_path} (missing OR extra fields),
      - any ``staged_dir``/``db_backup_path`` that contains ``..``, is absolute,
        or resolves outside ``install_root`` (ASVS V12 confinement).

    The launcher never acts on an invalid marker — this is the T-31-04 gate.
    """
    data = json.loads(raw)  # json.JSONDecodeError is a ValueError subclass
    if not isinstance(data, dict):
        raise ValueError("pending.json must be a JSON object")
    if set(data.keys()) != _REQUIRED_KEYS:
        raise ValueError(
            f"pending.json keys must be exactly {sorted(_REQUIRED_KEYS)}, "
            f"got {sorted(data.keys())}"
        )

    root = Path(install_root).resolve()
    staged_dir = _confine(str(data["staged_dir"]), root)
    db_backup_path = _confine(str(data["db_backup_path"]), root)

    return Pending(
        staged_dir=staged_dir,
        expected_version=str(data["expected_version"]),
        db_backup_path=db_backup_path,
    )


def _confine(raw_path: str, root: Path) -> Path:
    """Resolve ``raw_path`` under ``root`` or raise ``ValueError`` (ASVS V12).

    Rejects ``..`` components, absolute paths (drive- or root-anchored), and any
    path whose resolved location escapes ``root``.
    """
    candidate = Path(raw_path)
    if ".." in candidate.parts:
        raise ValueError(f"path traversal ('..') rejected: {raw_path!r}")
    if candidate.is_absolute():
        raise ValueError(f"absolute path rejected: {raw_path!r}")
    resolved = (root / candidate).resolve()
    if not resolved.is_relative_to(root):
        raise ValueError(f"path escapes install root: {raw_path!r}")
    return resolved

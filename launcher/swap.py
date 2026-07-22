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
  DB together on any failure.
"""

from __future__ import annotations

import json
import os
import shutil
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

    On ANY failure (migrate raises, or health_ok returns False) the matched-pair
    rollback (T-31-06) fires: stop the app, move the staged code aside to
    ``app_failed``, restore the previous ``app\\``, restore the pre-update DB via
    ``backup_restore(pending.db_backup_path)`` (copy + delete -wal/-shm), restart
    the app on the restored code, and re-raise. Code and DB revert together.
    """
    stop_app()
    os.replace(paths.app, paths.app_prev)
    os.replace(paths.staged, paths.app)
    try:
        migrate()
        start_app()
        if not health_ok():
            raise RuntimeError("post-update health check failed")
    except Exception:
        # Matched-pair rollback: code + DB revert together (T-31-06).
        stop_app()
        os.replace(paths.app, paths.app_failed)
        os.replace(paths.app_prev, paths.app)
        backup_restore(pending.db_backup_path)
        start_app()
        raise
    else:
        shutil.rmtree(paths.app_prev, ignore_errors=True)


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

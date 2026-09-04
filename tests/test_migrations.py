"""Migration tripwires (SYNC-13 / D-04): the checks nothing else in the suite makes.

`tests/test_append_only_cursor.py` already carries two lockstep tripwires — one
comparing the ORM models against its own frozen column sets (`:246-258`), one
comparing those sets against the `app/db.py` trigger DDL (`:261-290`). Neither
of them ever executes `alembic/versions/`, and every other fixture in the suite
builds its schema with `create_all`. So the DDL production actually runs has,
until now, been compared against nothing at all — which is exactly the drift
migration 0026 had to patch after the fact.

All three tests below pass at HEAD on purpose: they are a tripwire for migration
0027 (and every migration after it), not a bug report about today.
"""

import re
from pathlib import Path

from sqlalchemy import text

from app.db import APPEND_ONLY_TRIGGERS

_VERSIONS_DIR = Path(__file__).resolve().parent.parent / "alembic" / "versions"

# The four append-only guards the ledger invariant depends on. A ledger table
# that loses its triggers fails OPEN and silently (app/db.py:24-29).
_TRIGGER_NAMES = frozenset(
    {
        "operations_no_update",
        "operations_no_delete",
        "cash_movements_no_update",
        "cash_movements_no_delete",
    }
)


def _normalise(sql: str | None) -> str:
    """Collapse all whitespace so indentation differences never fail a diff."""
    return re.sub(r"\s+", " ", sql or "").strip()


def _live_triggers(engine) -> dict[str, str]:
    """`{trigger name: normalised DDL}` as the database itself reports it."""
    with engine.connect() as connection:
        rows = connection.execute(
            text("SELECT name, sql FROM sqlite_master WHERE type='trigger'")
        ).all()
    return {name: _normalise(sql) for name, sql in rows}


def _declared_triggers() -> dict[str, str]:
    """`{trigger name: normalised DDL}` as `app/db.py` declares it."""
    return {
        re.search(r"CREATE TRIGGER (\w+)", trigger).group(1): _normalise(trigger)
        for trigger in APPEND_ONLY_TRIGGERS
    }


def test_alembic_head_triggers_match_app_db(alembic_engine):
    """VA-5 (SYNC-13): `alembic upgrade head` produces exactly `APPEND_ONLY_TRIGGERS`.

    This is the ONLY check in the suite spanning `app/db.py` <-> the migrations.
    The two tripwires in `tests/test_append_only_cursor.py` compare
    models <-> constants and constants <-> `app/db.py` DDL, so a migration that
    forgets to move with the constant is invisible to both — which is precisely
    what happened between 0024 and 0026 (`currency` was added to the column but
    not to the trigger guard, leaving it silently mutable on an already-synced
    cash row until 0026 repaired it).

    Compared as a whole map, not a name set: a trigger present under the right
    name but guarding the wrong column list is the failure mode that matters.
    """
    declared = _declared_triggers()
    assert set(declared) == set(_TRIGGER_NAMES)  # the constant itself is intact
    assert _live_triggers(alembic_engine) == declared


def test_downgrade_upgrade_roundtrip_preserves_triggers(alembic_engine, run_alembic):
    """VA-6 (SYNC-13): head -> downgrade -1 -> head still leaves all four triggers.

    WHY this exists, recorded from an executed run: `alembic downgrade 0026 ->
    0023` SILENTLY DESTROYS both `cash_movements_no_update` and
    `cash_movements_no_delete`. Cause is
    `alembic/versions/0024_cash_movement_currency.py:50-52`, whose `downgrade()`
    drops the column inside `op.batch_alter_table`; Alembic 1.18.5's
    `SQLiteImpl.requires_recreate_in_batch` returns True for every batch
    operation except `add_column`, `create_index` and `drop_index`, so the batch
    becomes a move-and-copy table rebuild. SQLite drops a table's triggers with
    the table, and Alembic does not put them back. The ledger comes back
    unguarded and nothing says a word.

    Fixing `0024` itself is explicitly OUT OF SCOPE: an applied migration is
    historical fact and is never edited retroactively (the same rule 0018 and
    0026 state in their own docstrings). This test is the guard from now on — a
    future migration whose downgrade silently strips a trigger reddens here.

    WR-08 (33-REVIEW): the DOWNGRADED state is now inspected BEFORE the
    re-upgrade. It previously was not, and the single assertion compared NAMES
    ONLY — after re-upgrading — so the state it looked at was produced by
    `_SQLITE_DDL`, never by `_SQLITE_DOWNGRADE_DDL`. That left 0027's ~80 lines
    of hand-copied downgrade DDL, the half that has to reproduce 0018's and
    0026's exact `WHEN` enumerations, covered by NO assertion at all: a dropped
    `OR NEW.currency` would leave a downgraded DB with a silently weaker cash
    guard and every test would stay green. That is the same class of drift
    migration 0026 exists to fix, which is exactly what this file is about.
    """
    url = str(alembic_engine.url)
    run_alembic(url, "downgrade", "-1")

    # (1) The downgraded state — the half nothing used to look at.
    downgraded = _live_triggers(alembic_engine)
    assert set(downgraded) == set(_TRIGGER_NAMES)
    # The 0027 columns must be GONE from the guards (they are dropped next).
    assert "business_date" not in downgraded["operations_no_update"]
    assert "reverses_op_id" not in downgraded["operations_no_update"]
    assert "business_date" not in downgraded["cash_movements_no_update"]
    assert "reverses_movement_id" not in downgraded["cash_movements_no_update"]
    # ...and every PRE-0027 column must still be named. `NEW.currency` is the
    # load-bearing one: it is the exact column 0026 had to add after 0024 left
    # it silently mutable, so it is the drift this file was written for.
    assert "NEW.currency" in downgraded["cash_movements_no_update"]
    assert "NEW.sale_id" in downgraded["cash_movements_no_update"]
    assert "NEW.batch_id" in downgraded["operations_no_update"]
    assert "NEW.qty_delta" in downgraded["operations_no_update"]

    # (2) Back to head: the whole map, not just the names (same discipline as
    # `test_alembic_head_triggers_match_app_db`).
    run_alembic(url, "upgrade", "head")
    assert _live_triggers(alembic_engine) == _declared_triggers()


def test_revision_ids_are_fixed_width():
    """VA-7 (D-04): every revision / down_revision literal is a 4-digit string.

    `app.services.sync.push_schema_ok` compares two Alembic revision ids
    LEXICOGRAPHICALLY (D-01/D-04). That is only sound while every id is
    fixed-width numeric — the moment one revision is named `9` or `0027a` or
    `abc123`, the ordering silently stops meaning "newer than" and a client that
    is genuinely AHEAD of the server slips through the 409 push gate, which is
    the exact silent-data-loss window plan 33-01 exists to close. Nothing else
    in the repo enforces the shape, so this regex is the enforcement.

    Baseline today: 26 revision files, `0001` ... `0026`. Migration 0027 and
    everything after it are covered automatically by the glob.
    """
    paths = sorted(_VERSIONS_DIR.glob("[0-9]*.py"))
    assert len(paths) >= 26, f"revision glob found only {len(paths)} files"

    for path in paths:
        source = path.read_text(encoding="utf-8")

        revision = re.search(r'^revision = "(.*)"$', source, re.MULTILINE)
        assert revision is not None, f"{path.name}: no quoted `revision` literal"
        assert re.fullmatch(r"\d{4}", revision.group(1)), (
            f"{path.name}: revision {revision.group(1)!r} is not a fixed-width "
            "4-digit id — push_schema_ok's lexicographic comparison would break"
        )

        down = re.search(r"^down_revision = (.+)$", source, re.MULTILINE)
        assert down is not None, f"{path.name}: no `down_revision` literal"
        literal = down.group(1).strip()
        if literal == "None":
            continue  # 0001 is the root of the chain
        assert re.fullmatch(r'"\d{4}"', literal), (
            f"{path.name}: down_revision {literal} is not a fixed-width "
            "4-digit string literal"
        )

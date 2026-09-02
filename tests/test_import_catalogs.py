"""Executable contract for scripts/import_catalogs.py (quick task 260902-g1q).

Three things are pinned here and nowhere else:

1. Every dictionary row the importer writes carries `rubric` (CAT-06) and
   `name_lc` (LIST-02). Before this task both were left NULL, so every
   bulk-imported row was invisible to the /dictionary name filter.
2. ``--export`` round-trips: the file it writes is read back by this same
   script with no loss, and it is ACCUMULATIVE — a code that lives only in the
   target file survives the export (SPEC «выгрузка накопительная, а не
   замещающая»).
3. ``--only-missing`` never touches an existing row, so the hand-written s1
   names (34473 & co) cannot be overwritten by the older local ones.

The importer is NEVER run against the operator's data/myorishop.db: everything
below is synthetic data on the `session` fixture or a tmp_path file.
"""

import json

from sqlalchemy import func, select

from app.models import Dictionary
from app.services.rubrics import RUBRIC_OVERRIDES
from scripts.import_catalogs import (
    apply_dictionary_import,
    build_dictionary_row,
    export_dictionary,
    merge_dictionary_export,
    read_previous_export,
    write_export,
)

# A synthetic code that is deliberately NOT in RUBRIC_OVERRIDES, so an
# assertion about its name proves export/import fidelity and not override
# precedence.
FAKE_CODE = "999999"
FAKE_NAME = "Тестовый шампунь для волос"

# The real conflict case of the SPEC: the s1 name was typed by hand in August
# and is NEWER than the machine-imported local one. The additive path must not
# overwrite it.
CONFLICT_CODE = "34473"
S1_NAME = "Женская туалетная вода Sunkiss Garden объем 50 мл"
LOCAL_NAME = "Туалетная вода sunkiss garden"


def test_build_dictionary_row_fills_rubric_and_name_lc():
    assert FAKE_CODE not in RUBRIC_OVERRIDES, "the fake code must not be an override"

    ordinary = build_dictionary_row(FAKE_CODE, FAKE_NAME, ["01_26"])
    assert ordinary.name == FAKE_NAME
    assert ordinary.name_lc == FAKE_NAME.lower()
    assert ordinary.rubric == "Уход за волосами"
    assert ordinary.catalogs == ["01_26"]

    # An override code gets the web-verified name and rubric instead.
    override = build_dictionary_row("0305", "Чайная роза", [])
    assert override.name == "Не опознан (код 0305)"
    assert override.name_lc == "не опознан (код 0305)"
    assert override.rubric == "Прочее"


def test_apply_dictionary_import_creates_rows_with_rubric_and_sorted_catalogs(session):
    data = {FAKE_CODE: {"name": FAKE_NAME, "catalogs": ["03_26", "01_25", "01_26"]}}

    counts = apply_dictionary_import(session, data)
    session.commit()

    row = session.scalar(select(Dictionary).where(Dictionary.code == FAKE_CODE))
    assert row.rubric is not None
    assert row.name_lc == row.name.lower()
    assert row.catalogs == ["01_25", "01_26", "03_26"], "catalogs sort chronologically"
    assert counts == {"created": 1, "updated": 0, "skipped": 0, "present": 0}


def test_apply_dictionary_import_skips_blank_code_or_name(session):
    data = {
        "  ": {"name": FAKE_NAME, "catalogs": []},
        FAKE_CODE: {"name": "   ", "catalogs": []},
    }

    counts = apply_dictionary_import(session, data)
    session.commit()

    assert counts["skipped"] == 2
    assert session.scalar(select(func.count()).select_from(Dictionary)) == 0


def test_apply_dictionary_import_refreshes_an_existing_row(session):
    session.add(Dictionary(code=FAKE_CODE, name="Старое имя", catalogs=["09_20"]))
    session.commit()

    counts = apply_dictionary_import(
        session, {FAKE_CODE: {"name": FAKE_NAME, "catalogs": ["01_26"]}}
    )
    session.commit()

    row = session.scalar(select(Dictionary).where(Dictionary.code == FAKE_CODE))
    assert row.name == FAKE_NAME
    assert row.name_lc == FAKE_NAME.lower()
    assert row.rubric == "Уход за волосами", "the update path backfills the rubric too"
    assert row.catalogs == ["01_26"]
    assert counts["updated"] == 1 and counts["created"] == 0


def test_only_missing_never_overwrites_an_existing_name(session):
    """The 34473 case: the newer s1 name survives the older local one."""
    session.add(
        Dictionary(code=CONFLICT_CODE, name=S1_NAME, name_lc=S1_NAME.lower(), catalogs=["05_25"])
    )
    session.commit()

    data = {
        CONFLICT_CODE: {"name": LOCAL_NAME, "catalogs": ["01_19"]},
        FAKE_CODE: {"name": FAKE_NAME, "catalogs": ["01_26"]},
    }
    counts = apply_dictionary_import(session, data, only_missing=True)
    session.commit()

    kept = session.scalar(select(Dictionary).where(Dictionary.code == CONFLICT_CODE))
    assert kept.name == S1_NAME
    assert kept.name_lc == S1_NAME.lower()
    assert kept.catalogs == ["05_25"]
    assert counts["created"] == 1
    assert counts["present"] == 1
    assert counts["updated"] == 0

    # Second run is a no-op.
    again = apply_dictionary_import(session, data, only_missing=True)
    session.commit()
    assert again["created"] == 0 and again["present"] == 2
    assert session.scalar(select(func.count()).select_from(Dictionary)) == 2


def test_export_dictionary_shape_and_order(session):
    session.add(Dictionary(code="46413", name="Бэ", catalogs=["01_26"]))
    session.add(Dictionary(code="10001", name="А", catalogs=None))
    session.commit()

    exported = export_dictionary(session)

    assert list(exported) == ["10001", "46413"], "codes are exported in ascending order"
    assert set(exported["46413"]) == {"name", "catalogs"}
    assert exported["10001"]["catalogs"] == [], "a NULL catalogs column exports as []"


def test_export_round_trips_through_json_with_no_loss(session):
    seeded = {
        FAKE_CODE: {"name": FAKE_NAME, "catalogs": ["01_25", "01_26"]},
        "888888": {"name": "Тестовый крем для лица", "catalogs": []},
    }
    apply_dictionary_import(session, seeded)
    session.commit()

    restored = json.loads(json.dumps(export_dictionary(session), ensure_ascii=False))
    session.query(Dictionary).delete()
    session.commit()
    apply_dictionary_import(session, restored)
    session.commit()

    after = export_dictionary(session)
    assert after == seeded


def test_merge_export_keeps_codes_the_database_no_longer_has():
    """SPEC: выгрузка накопительная — the file can only grow."""
    previous = {"11111": {"name": "Посторонний код", "catalogs": ["01_20"]}}
    fresh = {FAKE_CODE: {"name": FAKE_NAME, "catalogs": []}}

    merged, stats = merge_dictionary_export(previous, fresh)

    assert "11111" in merged, "a code absent from the database must survive the export"
    assert merged["11111"] == previous["11111"]
    assert stats == {"before": 1, "added": 1, "updated": 0, "after": 2}
    assert stats["after"] >= stats["before"]


def test_write_export_into_an_existing_file_preserves_a_foreign_code(tmp_path):
    """The file-level proof of the accumulative rule, end to end."""
    dest = tmp_path / "products.json"
    foreign = {"11111": {"name": "Посторонний код", "catalogs": ["01_20"]}}
    dest.write_text(json.dumps(foreign, ensure_ascii=False), encoding="utf-8")

    stats = write_export(
        dest,
        {
            "11111": {"name": "Посторонний код обновлён", "catalogs": ["01_20"]},
            FAKE_CODE: {"name": FAKE_NAME, "catalogs": ["01_26"]},
        },
    )

    on_disk = read_previous_export(dest)
    assert set(on_disk) == {"11111", FAKE_CODE}
    assert on_disk["11111"]["name"] == "Посторонний код обновлён"
    assert stats == {"before": 1, "added": 1, "updated": 1, "after": 2}
    assert list(on_disk) == sorted(on_disk), "the file stays key-sorted"

    # A second export from a database that knows NOTHING cannot shrink the file.
    shrunk = write_export(dest, {})
    assert shrunk == {"before": 2, "added": 0, "updated": 0, "after": 2}
    assert set(read_previous_export(dest)) == {"11111", FAKE_CODE}

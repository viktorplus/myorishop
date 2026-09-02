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

import pytest
from sqlalchemy import func, select

from app.models import Dictionary, Product
from app.services.rubrics import RUBRIC_OVERRIDES
from scripts.import_catalogs import (
    ShadeNameWouldShrink,
    apply_dictionary_import,
    apply_product_name_updates,
    apply_shade_name_updates,
    build_dictionary_row,
    dictionary_names_after,
    export_dictionary,
    merge_dictionary_export,
    plan_product_name_updates,
    plan_shade_name_updates,
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


def test_write_export_never_opens_its_destination_directly(tmp_path, monkeypatch):
    """CR-03 (quick task 260902-tev): products.json is written through the shared
    atomic_write of scripts/import_prices.py, never truncated in place.

    The helper resolves `_open_export` from its OWN module globals, so patching
    it there covers this cross-script caller too.
    """
    from pathlib import Path

    from scripts import import_prices

    dest = tmp_path / "products.json"
    recorded = []
    real = import_prices._open_export

    def spy(path, mode, **kwargs):
        recorded.append(Path(path))
        return real(path, mode, **kwargs)

    monkeypatch.setattr("scripts.import_prices._open_export", spy)

    fresh = {
        FAKE_CODE: {"name": FAKE_NAME, "catalogs": ["01_26"]},
        "11111": {"name": "Посторонний код", "catalogs": ["01_20"]},
    }
    write_export(dest, fresh)

    assert recorded, "the writer never went through _open_export"
    assert recorded[0] != dest, "the destination itself must not be opened for writing"

    on_disk = read_previous_export(dest)
    assert on_disk == {code: fresh[code] for code in sorted(fresh)}
    assert list(on_disk) == sorted(fresh), "the file stays key-sorted"


# ---------------------------------------------------------------------------
# --restore-shade-names (quick task 260902-k2i)
#
# The only mode in this project that UPDATES the name of an existing dictionary
# row — and the one the orchestrator will run unattended on s1. Its whole
# safety story is `is_shade_tail`: a name that already carries a product type
# cannot be the shade tail of anything, so it is out of reach by construction.
# ---------------------------------------------------------------------------

SHADE_CODE = "33155"
SHADE_ONLY = "Фарфоровый"
RESTORED = "Увлажняющая тональная основа the one aqua boost - фарфоровый"
ORPHAN_CODE = "33157"

SHADE_OVERRIDES = {
    SHADE_CODE: {"conf": "series", "name": RESTORED, "rubric": "Макияж"},
    CONFLICT_CODE: {"conf": "series", "name": "Парфюмерия - духи", "rubric": "Парфюмерия"},
    ORPHAN_CODE: {"conf": "series", "name": "Тональная основа - розовый нюд", "rubric": "Макияж"},
}


def _seed_dictionary(session, code, name, **extra):
    row = Dictionary(code=code, name=name, name_lc=name.lower(), **extra)
    session.add(row)
    session.commit()
    return row


def test_plan_shade_name_updates_selects_only_a_bare_shade_row(session):
    _seed_dictionary(session, SHADE_CODE, SHADE_ONLY, catalogs=["01_18"], rubric="Макияж")

    plan = plan_shade_name_updates(session, SHADE_OVERRIDES)

    assert [item["code"] for item in plan] == [SHADE_CODE]
    assert plan[0]["old"] == SHADE_ONLY
    assert plan[0]["new"] == RESTORED
    assert plan[0]["old_rubric"] == "Макияж"
    assert plan[0]["new_rubric"], "the new rubric is carried, never left blank"
    # Read-only: nothing was written.
    session.expire_all()
    row = session.scalar(select(Dictionary).where(Dictionary.code == SHADE_CODE))
    assert row.name == SHADE_ONLY


def test_a_name_that_already_carries_a_product_type_is_never_planned(session):
    """The 34473 hand-written-name case: an override exists, the row is safe."""
    _seed_dictionary(session, CONFLICT_CODE, S1_NAME, catalogs=["05_25"])

    assert plan_shade_name_updates(session, SHADE_OVERRIDES) == []


def test_an_override_with_no_dictionary_row_is_never_planned_or_inserted(session):
    """ORPHAN_CODE has an override but no row — the mode cannot grow the table."""
    _seed_dictionary(session, SHADE_CODE, SHADE_ONLY)

    plan = plan_shade_name_updates(session, SHADE_OVERRIDES)
    assert [item["code"] for item in plan] == [SHADE_CODE]

    apply_shade_name_updates(session, plan)
    session.commit()
    assert session.scalar(select(func.count()).select_from(Dictionary)) == 1


def test_a_code_with_no_override_is_never_planned(session):
    _seed_dictionary(session, FAKE_CODE, "Медовый")

    assert plan_shade_name_updates(session, SHADE_OVERRIDES) == []


def test_apply_writes_name_name_lc_and_rubric_and_leaves_catalogs_alone(session):
    _seed_dictionary(session, SHADE_CODE, SHADE_ONLY, catalogs=["01_18", "01_19"], rubric="Прочее")

    plan = plan_shade_name_updates(session, SHADE_OVERRIDES)
    updated = apply_shade_name_updates(session, plan)
    session.commit()

    row = session.scalar(select(Dictionary).where(Dictionary.code == SHADE_CODE))
    assert updated == 1
    assert row.name == RESTORED
    assert row.name_lc == RESTORED.lower()
    assert row.rubric == plan[0]["new_rubric"]
    assert row.catalogs == ["01_18", "01_19"], "catalogs are not this mode's business"


def test_apply_refuses_a_candidate_that_is_not_strictly_longer(session):
    """«Ни одно имя не стало короче» — enforced at write time, not hoped for."""
    _seed_dictionary(session, SHADE_CODE, SHADE_ONLY)
    forged = [
        {
            "code": SHADE_CODE,
            "old": SHADE_ONLY,
            "new": "Фарфор",
            "old_rubric": None,
            "new_rubric": "Макияж",
        }
    ]

    with pytest.raises(ShadeNameWouldShrink):
        apply_shade_name_updates(session, forged)


def test_the_second_run_plans_nothing(session):
    _seed_dictionary(session, SHADE_CODE, SHADE_ONLY)

    apply_shade_name_updates(session, plan_shade_name_updates(session, SHADE_OVERRIDES))
    session.commit()

    assert plan_shade_name_updates(session, SHADE_OVERRIDES) == [], "idempotent"


def test_plan_defaults_to_the_shipped_overrides(session):
    """Called without a table it consults the real rubric_overrides.json."""
    code, entry = next(
        (c, e)
        for c, e in RUBRIC_OVERRIDES.items()
        if " - " in (e.get("name") or "") and len(e["name"]) <= 200
    )
    shade = entry["name"].rsplit(" - ", 1)[1]
    _seed_dictionary(session, code, shade)
    _seed_dictionary(session, FAKE_CODE, FAKE_NAME)  # no override -> untouched

    plan = plan_shade_name_updates(session)

    assert [item["code"] for item in plan] == [code]
    assert plan[0]["new"] == entry["name"]
    assert plan[0]["new_rubric"] == entry["rubric"], "the override's own rubric is applied"


# ---------------------------------------------------------------------------
# --restore-shade-names, the product-card half
#
# Same mode, same predicate, one extra pass: a card the inventory import
# created from a CSV that held only the shade gets its product type back from
# the (already restored) dictionary row.
#
# This is NOT «sync the cards from the dictionary». On s1 there are 17 name
# mismatches and only 5 of them run in that direction; the other 12 are cards
# the operator typed BY HAND, richer than the справочник. A blanket sync would
# destroy those 12, which is exactly what the tests below forbid.
# ---------------------------------------------------------------------------

# The two real s1 reversals, verbatim from the SPEC.
RICH_CARD_CODE = "25048"
RICH_CARD = "Мужская туалетная вода Tycoon75 мл"
THIN_DICT = "Туалетная вода tycoon"
RICH_CARD_CODE_2 = "21566"
RICH_CARD_2 = "Женские туалетные духи Volare Magnolia объем 50 мл"
THIN_DICT_2 = "Туалетные духи volare magnolia"


def _seed_product(session, code, name, **extra):
    product = Product(code=code, name=name, name_lc=(name or "").lower(), quantity=0, **extra)
    session.add(product)
    session.commit()
    return product


def _card_plan(session, dict_plan=()):
    """Plan the cards the way the runner does — against the RESTORED names."""
    return plan_product_name_updates(session, dictionary_names_after(session, list(dict_plan)))


def test_plan_product_name_updates_selects_only_a_bare_shade_card(session):
    _seed_dictionary(session, SHADE_CODE, RESTORED)
    card = _seed_product(session, SHADE_CODE, SHADE_ONLY)

    plan = _card_plan(session)

    assert [item["code"] for item in plan] == [SHADE_CODE]
    assert plan[0]["id"] == card.id
    assert plan[0]["old"] == SHADE_ONLY
    assert plan[0]["new"] == RESTORED
    # Read-only: nothing was written.
    session.expire_all()
    assert session.get(Product, card.id).name == SHADE_ONLY


def test_a_card_richer_than_the_dictionary_is_never_planned(session):
    """The 12 s1 reversals: the operator's hand-written card wins, untouched.

    `is_shade_tail` is directional — it demands the REPLACEMENT be strictly
    longer — so a card that already names the product, its gender and its
    volume can never be rewritten with the thinner dictionary name. Without
    this the mode would silently overwrite 12 hand-typed names on the server.
    """
    _seed_dictionary(session, RICH_CARD_CODE, THIN_DICT)
    _seed_dictionary(session, RICH_CARD_CODE_2, THIN_DICT_2)
    rich = _seed_product(session, RICH_CARD_CODE, RICH_CARD)
    rich_2 = _seed_product(session, RICH_CARD_CODE_2, RICH_CARD_2)

    assert _card_plan(session) == []

    # And applying the (empty) plan leaves both names byte-identical.
    apply_product_name_updates(session, _card_plan(session))
    session.commit()
    session.expire_all()
    assert session.get(Product, rich.id).name == RICH_CARD
    assert session.get(Product, rich_2.id).name == RICH_CARD_2


def test_a_card_equal_to_the_dictionary_name_is_never_planned(session):
    """Nothing to restore is not «restore nothing to it» — it is no plan."""
    _seed_dictionary(session, SHADE_CODE, SHADE_ONLY)
    _seed_product(session, SHADE_CODE, SHADE_ONLY)

    assert _card_plan(session) == []


def test_a_card_with_no_dictionary_row_or_no_code_is_never_planned(session):
    _seed_product(session, FAKE_CODE, "Медовый")  # no dictionary row at all
    _seed_product(session, None, SHADE_ONLY)  # a hand-made card without a code
    _seed_dictionary(session, SHADE_CODE, RESTORED)  # a row with no card

    assert _card_plan(session) == []


def test_the_card_pass_reads_the_RESTORED_dictionary_name(session):
    """The «Офис» case end to end: the row is shade-only until the row pass.

    Planning the cards against the CURRENT dictionary would select nothing —
    both sides read «Фарфоровый». The card plan has to see the dictionary as it
    will be after the row pass, which is what makes the dry run honest.
    """
    _seed_dictionary(session, SHADE_CODE, SHADE_ONLY)
    card = _seed_product(session, SHADE_CODE, SHADE_ONLY)

    assert plan_product_name_updates(session, {SHADE_CODE: SHADE_ONLY}) == []

    dict_plan = plan_shade_name_updates(session, SHADE_OVERRIDES)
    plan = _card_plan(session, dict_plan)

    assert [item["new"] for item in plan] == [RESTORED]

    apply_shade_name_updates(session, dict_plan)
    apply_product_name_updates(session, plan)
    session.commit()

    session.expire_all()
    assert session.get(Product, card.id).name == RESTORED
    assert session.scalar(select(Dictionary).where(Dictionary.code == SHADE_CODE)).name == RESTORED


def test_apply_writes_card_name_and_name_lc_and_leaves_the_rest_alone(session):
    """LIST-02: without name_lc the card disappears from the name search."""
    _seed_dictionary(session, SHADE_CODE, RESTORED)
    card = _seed_product(session, SHADE_CODE, SHADE_ONLY, category="Макияж", sale_cents=1234)

    updated = apply_product_name_updates(session, _card_plan(session))
    session.commit()

    row = session.get(Product, card.id)
    assert updated == 1
    assert row.name == RESTORED
    assert row.name_lc == RESTORED.lower()
    assert row.name_lc == row.name.lower(), "the shadow column tracks the new name"
    assert row.category == "Макияж", "category has its own rules; this mode never touches it"
    assert row.sale_cents == 1234 and row.code == SHADE_CODE and row.quantity == 0


def test_apply_refuses_a_card_name_that_would_shrink(session):
    """«Ни одно имя карточки не стало короче» — enforced at write time."""
    card = _seed_product(session, SHADE_CODE, RESTORED)
    forged = [{"id": card.id, "code": SHADE_CODE, "old": RESTORED, "new": SHADE_ONLY}]

    with pytest.raises(ShadeNameWouldShrink):
        apply_product_name_updates(session, forged)


def test_the_second_card_run_plans_nothing_and_creates_no_card(session):
    _seed_dictionary(session, SHADE_CODE, RESTORED)
    _seed_product(session, SHADE_CODE, SHADE_ONLY)
    _seed_product(session, RICH_CARD_CODE, RICH_CARD)

    apply_product_name_updates(session, _card_plan(session))
    session.commit()

    assert _card_plan(session) == [], "idempotent"
    assert session.scalar(select(func.count()).select_from(Product)) == 2

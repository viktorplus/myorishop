"""CAT-04: catalog PDF section + dictionary catalog membership.

Covers the code-shape bridge (JSON "MM_YY" <-> URL "YYYY-MM"), the messy
filename normalization, the folder-scan service, and the /catalogs routes.
"""

import pytest

from app.config import settings
from app.core import new_id
from app.models import Dictionary
from app.services import catalogs as svc


def _make_catalog_dir(tmp_path, names):
    """Create empty PDF files with the given names; return the folder Path."""
    folder = tmp_path / "catalogs"
    folder.mkdir()
    for name in names:
        (folder / name).write_bytes(b"%PDF-1.4 fake\n")
    return folder


# --- code-shape helpers -----------------------------------------------------


def test_json_and_url_code_roundtrip():
    assert svc.parse_json_code("01_26") == (2026, 1)
    assert svc.parse_json_code("15_25") == (2025, 15)
    assert svc.parse_url_code("2026-01") == (2026, 1)
    assert svc.to_json_code(2026, 1) == "01_26"
    assert svc.to_url_code(2026, 1) == "2026-01"
    assert svc.parse_json_code("nonsense") is None
    assert svc.parse_url_code("2026/01") is None


@pytest.mark.parametrize(
    "filename,expected",
    [
        ("2025-01.pdf", (2025, 1)),  # dash format
        ("2025005.pdf", (2025, 5)),  # no-dash format
        ("2026-04_ru.pdf", (2026, 4)),  # locale suffix
        ("2025016.pdf", (2025, 16)),
        ("2025-17.pdf", (2025, 17)),
    ],
)
def test_file_key_handles_all_filename_shapes(filename, expected):
    assert svc._file_key(filename) == expected


# --- folder scan + membership ----------------------------------------------


def test_list_catalogs_sorted_newest_first_with_counts(tmp_path, monkeypatch, session):
    folder = _make_catalog_dir(tmp_path, ["2025-01.pdf", "2026-03.pdf", "2026005.pdf"])
    monkeypatch.setattr(settings, "catalogs_dir", str(folder))

    session.add_all(
        [
            Dictionary(id=new_id(), code="100", name="Помада", catalogs=["01_25", "03_26"]),
            Dictionary(id=new_id(), code="200", name="Тушь", catalogs=["03_26"]),
            Dictionary(id=new_id(), code="300", name="Крем", catalogs=[]),
        ]
    )
    session.commit()

    result = svc.list_catalogs(session)
    codes = [c["url_code"] for c in result["catalogs"]]
    # newest first: 2026-05, 2026-03, 2025-01
    assert codes == ["2026-05", "2026-03", "2025-01"]
    counts = {c["url_code"]: c["product_count"] for c in result["catalogs"]}
    assert counts["2026-03"] == 2
    assert counts["2025-01"] == 1
    assert counts["2026-05"] == 0


def test_list_catalogs_filters_by_year(tmp_path, monkeypatch, session):
    folder = _make_catalog_dir(tmp_path, ["2025-01.pdf", "2026-03.pdf", "2026-05.pdf"])
    monkeypatch.setattr(settings, "catalogs_dir", str(folder))

    result = svc.list_catalogs(session, year="2026")
    codes = [c["url_code"] for c in result["catalogs"]]
    assert codes == ["2026-05", "2026-03"]

    # non-digit year value is treated as no filter, never raises
    result_all = svc.list_catalogs(session, year="not-a-year")
    assert len(result_all["catalogs"]) == 3


def test_list_catalogs_sort_oldest(tmp_path, monkeypatch, session):
    folder = _make_catalog_dir(tmp_path, ["2025-01.pdf", "2026-03.pdf"])
    monkeypatch.setattr(settings, "catalogs_dir", str(folder))

    result = svc.list_catalogs(session, sort="oldest")
    codes = [c["url_code"] for c in result["catalogs"]]
    assert codes == ["2025-01", "2026-03"]

    # default (sort="") is unchanged: newest first
    default_result = svc.list_catalogs(session)
    assert [c["url_code"] for c in default_result["catalogs"]] == ["2026-03", "2025-01"]


def test_list_catalogs_paginates_flat_list_before_grouping(tmp_path, monkeypatch, session):
    # 25 PDFs across 2 years — the 20/5 split must be the SAME regardless of
    # how the years are distributed across that boundary (flat-list slice,
    # not per-year groups).
    names = [f"2025-{n:02d}.pdf" for n in range(1, 16)] + [
        f"2026-{n:02d}.pdf" for n in range(1, 11)
    ]
    folder = _make_catalog_dir(tmp_path, names)
    monkeypatch.setattr(settings, "catalogs_dir", str(folder))

    result = svc.list_catalogs(session, page=0)
    assert result["total"] == 25
    assert result["total_pages"] == 2
    assert len(result["catalogs"]) == 20

    result_page2 = svc.list_catalogs(session, page=1)
    assert len(result_page2["catalogs"]) == 5


def test_catalog_year_options_returns_all_years_regardless_of_filter(tmp_path, monkeypatch, session):
    folder = _make_catalog_dir(tmp_path, ["2024-01.pdf", "2025-01.pdf", "2026-03.pdf"])
    monkeypatch.setattr(settings, "catalogs_dir", str(folder))

    assert svc.catalog_year_options(session) == [2026, 2025, 2024]


def test_products_in_catalog_ordered_by_name(tmp_path, monkeypatch, session):
    folder = _make_catalog_dir(tmp_path, ["2026-03.pdf"])
    monkeypatch.setattr(settings, "catalogs_dir", str(folder))
    session.add_all(
        [
            Dictionary(id=new_id(), code="1", name="Яблоко", catalogs=["03_26"]),
            Dictionary(id=new_id(), code="2", name="Апельсин", catalogs=["03_26"]),
            Dictionary(id=new_id(), code="3", name="Груша", catalogs=["01_26"]),
        ]
    )
    session.commit()

    rows = svc.products_in_catalog(session, "2026-03")
    assert [r.name for r in rows] == ["Апельсин", "Яблоко"]


def test_catalogs_for_code_only_returns_existing_pdfs(tmp_path, monkeypatch, session):
    folder = _make_catalog_dir(tmp_path, ["2026-03.pdf"])
    monkeypatch.setattr(settings, "catalogs_dir", str(folder))
    session.add(
        # "01_26" has no PDF on disk -> must be filtered out.
        Dictionary(id=new_id(), code="9", name="Товар", catalogs=["03_26", "01_26"])
    )
    session.commit()

    result = svc.catalogs_for_code(session, "9")
    assert [c["url_code"] for c in result] == ["2026-03"]


# --- routes -----------------------------------------------------------------


def test_catalogs_routes_end_to_end(tmp_path, monkeypatch, session, client):
    folder = _make_catalog_dir(tmp_path, ["2026-03.pdf"])
    monkeypatch.setattr(settings, "catalogs_dir", str(folder))
    session.add(
        Dictionary(id=new_id(), code="500", name="Крем для рук", catalogs=["03_26"])
    )
    session.commit()

    # list page
    r = client.get("/catalogs")
    assert r.status_code == 200
    assert "Каталог 3 · 2026" in r.text

    # detail page shows the member product
    r = client.get("/catalogs/2026-03")
    assert r.status_code == 200
    assert "Крем для рук" in r.text

    # PDF served inline
    r = client.get("/catalogs/2026-03/file")
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert "inline" in r.headers["content-disposition"]

    # unknown catalog -> 404 on both surfaces
    assert client.get("/catalogs/1999-01").status_code == 404
    assert client.get("/catalogs/1999-01/file").status_code == 404


def test_web_catalogs_pagination_bar_shows_correct_total(tmp_path, monkeypatch, session, client):
    names = [f"2025-{n:02d}.pdf" for n in range(1, 16)] + [
        f"2026-{n:02d}.pdf" for n in range(1, 11)
    ]
    folder = _make_catalog_dir(tmp_path, names)
    monkeypatch.setattr(settings, "catalogs_dir", str(folder))

    r = client.get("/catalogs")
    assert r.status_code == 200
    assert "Страница 1 из 2" in r.text


def test_web_catalogs_filter_by_year(tmp_path, monkeypatch, session, client):
    folder = _make_catalog_dir(tmp_path, ["2025-01.pdf", "2026-03.pdf"])
    monkeypatch.setattr(settings, "catalogs_dir", str(folder))

    r = client.get("/catalogs?year=2026")
    assert r.status_code == 200
    assert "Каталог 3 · 2026" in r.text
    assert "Каталог 1 · 2025" not in r.text


def test_web_catalogs_year_filter_lives_in_header_row(tmp_path, monkeypatch, session, client):
    folder = _make_catalog_dir(tmp_path, ["2026-03.pdf"])
    monkeypatch.setattr(settings, "catalogs_dir", str(folder))

    r = client.get("/catalogs")
    assert r.status_code == 200
    assert 'class="filter-row"' in r.text
    assert 'class="filter-bar"' not in r.text


def test_web_catalogs_table_tags_balanced_on_paginated_page(tmp_path, monkeypatch, session, client):
    # Seed enough catalogs across 2 years that a page boundary (20 rows)
    # falls mid-year, so the year-grouping loop would leave an unclosed
    # </table> if pagination happened after grouping instead of before it.
    names = [f"2025-{n:02d}.pdf" for n in range(1, 16)] + [
        f"2026-{n:02d}.pdf" for n in range(1, 11)
    ]
    folder = _make_catalog_dir(tmp_path, names)
    monkeypatch.setattr(settings, "catalogs_dir", str(folder))

    r = client.get("/catalogs")
    assert r.status_code == 200
    assert r.text.count("<table") == r.text.count("</table>")

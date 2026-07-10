"""BCK-02 executable contract: full-table CSV export (products/sales/customers).

Covers D-06 (dedicated /export page with three static download links, plain
<a href> never hx-get) and D-07 (utf-8-sig BOM-once encoding so Cyrillic
survives an Excel double-click open), RESEARCH Pitfall 4 (";" row delimiter
so a comma-decimal money field like "12,50" is never itself split), and
security T-06-09/T-06-10 (zero client-supplied filename/path params on any
export route; CSV-formula-injection hardening via a leading apostrophe on
any free-text cell starting with =, +, -, or @).

Naming convention: route-level tests are test_web_export_* / test_web_nav_*;
service-level tests (Task 1) must NOT contain those prefixes.
"""

import csv
import io

from app.services.export import _csv_rows, _csv_safe, _encode_once

# --- service-level: BOM-once + delimiter correctness (Task 1) ---------------


def test_csv_bom_appears_once():
    chunks = list(
        _encode_once(_csv_rows(["A", "B"], [["1", "2"], ["3", "4"], ["5", "6"]]))
    )
    joined = b"".join(chunks)
    assert joined.startswith(b"\xef\xbb\xbf")
    # The BOM bytes must not appear a second time anywhere later in the stream.
    assert joined.count(b"\xef\xbb\xbf") == 1


def test_money_field_not_split_by_delimiter():
    chunks = list(
        _encode_once(_csv_rows(["Товар", "Цена"], [["Тестовый товар", "12,50"]]))
    )
    text = b"".join(chunks).decode("utf-8-sig")
    reader = csv.reader(io.StringIO(text), delimiter=";")
    rows = list(reader)
    assert rows[0] == ["Товар", "Цена"]
    # The comma-decimal money value stays ONE field — never split by ";".
    assert rows[1] == ["Тестовый товар", "12,50"]
    assert len(rows[1]) == 2


def test_csv_safe_prefixes_formula_injection_chars():
    for prefix in ("=", "+", "-", "@"):
        assert _csv_safe(f"{prefix}cmd") == f"'{prefix}cmd"


def test_csv_safe_leaves_normal_values_untouched():
    assert _csv_safe("Обычное имя") == "Обычное имя"
    assert _csv_safe("") == ""


# --- route-level: /export page + three download routes (Task 2) ------------


def test_web_export_page_has_three_download_links(client):
    response = client.get("/export")
    assert response.status_code == 200
    body = response.text
    assert 'href="/export/products.csv"' in body
    assert 'href="/export/sales.csv"' in body
    assert 'href="/export/customers.csv"' in body
    # UI-SPEC hard rule: plain anchors only — htmx would break the native
    # Content-Disposition download by trying to swap the CSV into the DOM.
    assert 'hx-get="/export' not in body


def test_products_csv_roundtrip(client, product):
    response = client.get("/export/products.csv")
    assert response.status_code == 200
    assert "products.csv" in response.headers["content-disposition"]
    text = response.content.decode("utf-8-sig")
    reader = csv.reader(io.StringIO(text), delimiter=";")
    rows = list(reader)
    assert rows[0] == ["Код", "Название", "Категория", "Закупка", "Продажа", "Каталог", "Остаток"]
    # Exactly one seeded product from the `product` fixture.
    assert len(rows) == 2
    assert rows[1][0] == product.code
    assert rows[1][1] == product.name


def test_web_export_ignores_client_params(client, product):
    baseline = client.get("/export/products.csv").content
    response = client.get("/export/products.csv?path=..%5Cevil&filename=x.csv")
    assert response.status_code == 200
    assert response.content == baseline
    assert "evil" not in response.text


def test_web_nav_has_export_link(client):
    response = client.get("/")
    assert response.status_code == 200
    assert 'href="/export"' in response.text
    assert "Экспорт" in response.text

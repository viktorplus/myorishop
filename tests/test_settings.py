"""Settings hub (D-06/D-08): /settings composes warehouse + backup summaries.

Naming convention: route-level tests are test_web_settings_*.
"""

from app.config import settings
from app.services.warehouses import add_warehouse


def test_web_settings_page_renders(client):
    response = client.get("/settings")

    assert response.status_code == 200
    assert "<h1>Настройки</h1>" in response.text
    assert 'href="/warehouses"' in response.text
    assert 'href="/backup"' in response.text
    assert 'href="/finance/report"' in response.text


def test_web_settings_shows_warehouse_count(client, session, warehouse):
    add_warehouse(session, name="Запасной склад", address="")

    response = client.get("/settings")

    assert response.status_code == 200
    assert "2 складов" in response.text


def test_web_settings_shows_last_backup_date(client, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "backup_dir", str(tmp_path / "backups"))
    client.post("/backup")

    response = client.get("/settings")

    assert response.status_code == 200
    assert "Последняя копия:" in response.text


def test_web_settings_shows_no_backups_yet(client, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "backup_dir", str(tmp_path / "backups"))

    response = client.get("/settings")

    assert response.status_code == 200
    assert "Резервных копий пока нет" in response.text

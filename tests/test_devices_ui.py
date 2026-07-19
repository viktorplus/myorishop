"""Admin device-token surface tests (Plan 28-05, SYNC-09).

This module covers the ADMIN UI surface at /settings/devices — the page render,
the mint show-once rule, the show-once regression on reload, the never-render of
stored credential material, validation re-render, revoke-not-delete, and the
server-side operator 403 on EVERY verb. `tests/test_devices.py` covers the
service tier and `tests/test_sync_api.py` covers endpoint authentication.

CLAUDE.md safety: no plaintext token is asserted to persist — the show-once
tests assert its ABSENCE after the single mint response.
"""

import re

from app.core import new_id
from app.models import User
from app.services import auth
from app.services.devices import list_device_tokens

# Marker the service prepends to every plaintext (app/services/devices.py).
TOKEN_MARKER = "myos_"


def _mint(client, *, label="Ноутбук Ольги", device_id=None):
    """POST a mint through the admin client and return the response."""
    return client.post(
        "/settings/devices",
        data={"label": label, "device_id": device_id or new_id()},
    )


def _extract_plaintext(body: str) -> str:
    """Pull the minted plaintext (myos_...) out of the <code> element."""
    match = re.search(r"(myos_[A-Za-z0-9_-]+)", body)
    assert match, "mint response must render the plaintext token once"
    return match.group(1)


def test_devices_page_renders(client):
    resp = client.get("/settings/devices")
    assert resp.status_code == 200
    assert "Устройства" in resp.text
    assert 'id="devices-table"' in resp.text


def test_mint_shows_plaintext_once(client):
    resp = _mint(client, label="Планшет")
    assert resp.status_code == 200
    assert TOKEN_MARKER in resp.text
    # The copy-now warning must accompany the one-time reveal.
    assert "Скопируйте токен сейчас" in resp.text


def test_plaintext_not_shown_on_reload(client):
    minted = _mint(client, label="Телефон")
    plaintext = _extract_plaintext(minted.text)

    reload = client.get("/settings/devices")
    assert reload.status_code == 200
    # The show-once regression guard: the exact plaintext must be gone forever.
    assert plaintext not in reload.text


def test_stored_hash_never_rendered(client, session):
    _mint(client, label="Касса")
    tokens = list_device_tokens(session)
    assert len(tokens) == 1
    row = tokens[0]

    body = client.get("/settings/devices").text
    assert row.token_hash not in body
    assert row.token_prefix not in body


def test_mint_validation_error_rerenders_422(client, session):
    resp = client.post("/settings/devices", data={"label": "", "device_id": "dev-1"})
    assert resp.status_code == 422
    assert "Укажите название устройства." in resp.text
    # ZERO writes on a validation failure.
    assert list_device_tokens(session) == []


def test_revoke_marks_row_revoked_not_deleted(client, session):
    _mint(client, label="Ноутбук")
    before = list_device_tokens(session)
    assert len(before) == 1
    token_id = before[0].id

    resp = client.post(f"/settings/devices/{token_id}/revoke")
    assert resp.status_code == 200
    assert "Токен устройства отозван." in resp.text

    after = list_device_tokens(session)
    # Row count unchanged — revocation is a soft-disable, never a delete.
    assert len(after) == 1
    row = after[0]
    assert row.id == token_id
    assert row.is_active == 0
    assert row.revoked_at


def test_revoke_unknown_id_returns_422(client):
    resp = client.post(f"/settings/devices/{new_id()}/revoke")
    assert resp.status_code == 422
    assert "Токен устройства не найден." in resp.text


def _seed_operator(session, login_value="op", password="pw"):
    user = User(
        id=new_id(),
        login=login_value,
        display_name="Оператор",
        role="operator",
        password_hash=auth.hash_password(password),
        is_active=1,
    )
    session.add(user)
    session.commit()
    return user


def _csrf(anon_client) -> str:
    html = anon_client.get("/login").text
    match = re.search(r'name="csrf_token" value="([^"]+)"', html)
    assert match, "login page must render a csrf_token hidden field"
    return match.group(1)


def test_operator_cannot_reach_devices_page(anon_client, session, login):
    # ROLE-03 / T-28-24: the server-side admin boundary must hold on EVERY verb.
    _seed_operator(session)
    assert login(anon_client, "op", "pw").status_code == 303

    # GET
    assert (
        anon_client.get("/settings/devices", follow_redirects=False).status_code == 403
    )

    # POST create — with a VALID CSRF token so the 403 is the ROLE gate, not CSRF.
    token = _csrf(anon_client)
    created = anon_client.post(
        "/settings/devices",
        data={"label": "X", "device_id": "y"},
        headers={"X-CSRF-Token": token},
        follow_redirects=False,
    )
    assert created.status_code == 403

    # POST revoke
    revoked = anon_client.post(
        f"/settings/devices/{new_id()}/revoke",
        headers={"X-CSRF-Token": token},
        follow_redirects=False,
    )
    assert revoked.status_code == 403

    # No operator-minted token exists — the boundary held.
    assert list_device_tokens(session) == []


def test_settings_index_links_to_devices(client):
    resp = client.get("/settings")
    assert resp.status_code == 200
    assert "/settings/devices" in resp.text


def test_active_token_shows_revoke_control(client):
    # Sanity: an active token exposes the revoke control (the only mitigation for
    # a stolen token), and there is no delete control.
    minted = _mint(client, label="Витрина")
    assert "/revoke" in minted.text
    assert "hx-confirm" in minted.text

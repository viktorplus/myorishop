"""Device-token service tests (Plan 28-02, SYNC-09): mint/verify/revoke.

Service-level only (the plain `session` fixture, no HTTP) — the Phase 25
Plan 03 precedent. Endpoint-level bearer auth is covered separately in
`tests/test_sync_api.py` (Plan 03).

Proves the SYNC-09 lifecycle: a mint-once plaintext, hash-only storage,
correct/wrong/unknown/revoked verification, and delete-free revocation.

CLAUDE.md safety: token plaintexts here are freshly generated per test and are
asserted on structurally (prefix, length, hash relationship) — never as fixed
literal secrets.
"""

import hashlib

from sqlalchemy import func, select

from app.models import DeviceToken, User
from app.services import devices, users

DEVICE_ID = "11111111-2222-3333-4444-555555555555"
LABEL = "Ноутбук Ольги"


def _mint(session, *, device_id=DEVICE_ID, label=LABEL, user_id=None):
    result, errors = devices.mint_token(
        session, device_id=device_id, label=label, user_id=user_id
    )
    assert errors == {}
    assert result is not None
    return result


def _token_count(session) -> int:
    return session.scalar(select(func.count()).select_from(DeviceToken)) or 0


# --- mint (SYNC-09, T-28-07/T-28-17) ----------------------------------------


def test_mint_returns_plaintext_once_and_stores_only_a_hash(session):
    row, plaintext = _mint(session)

    assert plaintext.startswith(devices.TOKEN_PLAINTEXT_PREFIX)
    assert len(plaintext) > 30
    assert row.token_prefix == plaintext[: devices.TOKEN_PREFIX_LEN]
    assert row.token_hash == hashlib.sha256(plaintext.encode()).hexdigest()
    assert row.is_active == 1

    # The plaintext must appear in NO column of the stored row.
    session.expire_all()
    stored = session.get(DeviceToken, row.id)
    stored_values = [
        getattr(stored, column.key) for column in DeviceToken.__mapper__.columns
    ]
    assert plaintext not in stored_values
    for value in stored_values:
        assert value != plaintext


def test_two_mints_produce_distinct_tokens(session):
    first_row, first_plain = _mint(session)
    second_row, second_plain = _mint(session)

    assert first_plain != second_plain
    assert first_row.token_prefix != second_row.token_prefix
    assert first_row.token_hash != second_row.token_hash


def test_mint_validation_errors(session):
    for bad_label in ("", "   "):
        result, errors = devices.mint_token(
            session, device_id=DEVICE_ID, label=bad_label
        )
        assert result is None
        assert errors == {"label": devices.LABEL_REQUIRED_ERROR}
        assert _token_count(session) == 0

    result, errors = devices.mint_token(session, device_id="  ", label=LABEL)
    assert result is None
    assert errors == {"device_id": devices.DEVICE_ID_REQUIRED_ERROR}
    assert _token_count(session) == 0


def test_mint_links_user_id_when_given(session):
    user, errors = users.create_user(
        session,
        display_name="Ольга",
        login="olga",
        role="operator",
        password="pw",
    )
    assert errors == {}
    assert user is not None

    row, _plaintext = _mint(session, user_id=user.id)

    session.expire_all()
    stored = session.get(DeviceToken, row.id)
    assert stored.user_id == user.id
    assert session.get(User, user.id) is not None


# --- lookup (T-28-10) --------------------------------------------------------


def test_lookup_accepts_the_correct_token(session):
    row, plaintext = _mint(session)

    found = devices.lookup_active_token(session, plaintext)

    assert found is not None
    assert found.id == row.id


def test_lookup_rejects_a_wrong_token(session):
    _row, plaintext = _mint(session)
    # Same 12-char prefix, different tail — the exact case a prefix-only
    # lookup would wrongly accept.
    forged = plaintext[: devices.TOKEN_PREFIX_LEN] + "X" * (
        len(plaintext) - devices.TOKEN_PREFIX_LEN
    )
    assert forged != plaintext
    assert forged[: devices.TOKEN_PREFIX_LEN] == plaintext[: devices.TOKEN_PREFIX_LEN]

    assert devices.lookup_active_token(session, forged) is None


def test_lookup_rejects_unknown_and_empty(session):
    _mint(session)

    assert devices.lookup_active_token(session, "myos_totallyunknowntokenvalue") is None
    assert devices.lookup_active_token(session, "") is None
    assert devices.lookup_active_token(session, "myos") is None


def test_lookup_rejects_a_revoked_token(session):
    row, plaintext = _mint(session)

    revoked, errors = devices.revoke_token(session, row.id)
    assert errors == {}
    assert revoked is not None

    assert devices.lookup_active_token(session, plaintext) is None


# --- revoke (T-28-01, T-28-18) ----------------------------------------------


def test_revoke_soft_disables_and_never_deletes(session):
    row, _plaintext = _mint(session)
    before = _token_count(session)

    revoked, errors = devices.revoke_token(session, row.id)

    assert errors == {}
    assert revoked is not None
    assert _token_count(session) == before

    session.expire_all()
    stored = session.get(DeviceToken, row.id)
    assert stored is not None
    assert stored.is_active == 0
    assert isinstance(stored.revoked_at, str) and stored.revoked_at
    # The audit trail survives revocation.
    assert stored.device_id == DEVICE_ID


def test_revoke_unknown_id_returns_error_without_writes(session):
    _mint(session)
    before = _token_count(session)

    row, errors = devices.revoke_token(session, "no-such-token-id")

    assert row is None
    assert errors == {"token": devices.TOKEN_NOT_FOUND_ERROR}
    assert _token_count(session) == before


# --- touch / list ------------------------------------------------------------


def test_touch_last_used_stamps(session):
    row, _plaintext = _mint(session)
    assert row.last_used_at is None

    devices.touch_last_used(session, row)

    session.expire_all()
    stored = session.get(DeviceToken, row.id)
    assert isinstance(stored.last_used_at, str) and stored.last_used_at


def test_list_device_tokens_includes_revoked(session):
    active_row, _p1 = _mint(session, label="Активный")
    revoked_row, _p2 = _mint(session, label="Отозванный")
    devices.revoke_token(session, revoked_row.id)

    listed = devices.list_device_tokens(session)

    assert [token.label for token in listed] == ["Активный", "Отозванный"]
    ids = {token.id for token in listed}
    assert active_row.id in ids
    # An admin must still see a revoked device.
    assert revoked_row.id in ids

"""Wave-0 RED validation scaffold for Phase 32 UPD-01..07 (in-app secure self-update).

Contract note (Nyquist Wave 0): RED-by-design. The update service
(``app.services.update``) and the pure-Python minisign verifier
(``app.services.minisign_verify``) are built in Waves 02-05 and are imported
INSIDE each test body so Wave-0 collection stays green while execution is RED —
exactly the pattern of ``tests/test_release_verify.py`` / ``tests/test_packaging.py``.

The synthetic-release fixture reproduces the shipped ``build_release.write_manifest``
schema (``version=…\narchive=…\nsha256=…``) so the later waves verify against the
real Phase-31 release contract. The real-minisign round-trip is skip-gated on the
``minisign`` binary (mirrors ``tests/test_release_verify.py`` + ci.yml PG auto-skip);
it uses a THROWAWAY tmp keypair and NEVER touches ``app/minisign.pub`` (the offline
secret key, threat T-32-01).

Threats pinned here: T-32-01 (verify-before-unpack hard gate), T-32-02 (anti-
downgrade integer compare incl. the 9→10 boundary), T-32-05 (zip-slip: NOTHING is
staged on a failed gate), T-32-10 (offline ⇒ silent no-op, never raises). The
UPD-04 matched-pair rollback anchor lives in ``tests/test_launcher.py``.
"""

import hashlib
import io
import shutil
import subprocess
import zipfile
from pathlib import Path

import pytest

minisign_available = shutil.which("minisign") is not None


def fake_release_json() -> dict:
    """A dict shaped like GitHub ``/repos/viktorplus/myorishop/releases/latest``.

    Only the three fields the update service reads are populated: ``tag_name``
    (locates the release), ``body`` (release notes for the notify-and-confirm
    surface, UPD-03), and ``assets[].browser_download_url`` for the manifest,
    its ``.minisig`` signature, and the onedir archive.
    """
    base = "https://github.com/viktorplus/myorishop/releases/download/v1.16"
    objects = "https://objects.githubusercontent.com/github-production-release-asset"
    return {
        "tag_name": "v1.16",
        "body": "release notes text",
        "assets": [
            {
                "name": "manifest.txt",
                "browser_download_url": f"{base}/manifest.txt",
            },
            {
                "name": "manifest.txt.minisig",
                "browser_download_url": f"{objects}/manifest.txt.minisig",
            },
            {
                "name": "MyOriShop-1.16.zip",
                "browser_download_url": f"{base}/MyOriShop-1.16.zip",
            },
        ],
    }


@pytest.fixture()
def synthetic_release(tmp_path):
    """Build a real tiny onedir zip + a ``manifest.txt`` binding its REAL sha256.

    Reuses ``build_release.write_manifest`` (Phase 31, shipped) so the fixture is
    byte-for-byte the real release contract Waves 03/04 verify against. Returns a
    dict of ``archive``/``manifest``/``good_sha``/``version``.
    """
    import build_release  # noqa: PLC0415 — in-body import keeps collection green

    # A real (tiny) zip standing in for the embeddable onedir bundle.
    archive = tmp_path / "MyOriShop-1.16.zip"
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("app/__init__.py", '__version__ = "1.16"\n')
        zf.writestr("app/marker.txt", "staged-1.16")
    archive.write_bytes(buf.getvalue())

    manifest = build_release.write_manifest(
        archive_path=archive, version="1.16", dest=tmp_path / "manifest.txt"
    )
    good_sha = hashlib.sha256(archive.read_bytes()).hexdigest()
    return {
        "archive": archive,
        "manifest": Path(manifest),
        "good_sha": good_sha,
        "version": "1.16",
    }


@pytest.fixture()
def throwaway_keypair(tmp_path):
    """A THROWAWAY tmp minisign keypair + a signed manifest (skip-gated on binary).

    Mirrors ``tests/test_release_verify.py`` exactly: ``minisign -G -W`` keygens
    non-interactively (unencrypted secret so no prompt), ``minisign -S`` signs
    ``manifest.txt``. NEVER touches ``app/minisign.pub`` — the production secret
    key is offline-only (threat T-32-01). Returns the pubkey text, the manifest
    path, and the ``.minisig`` signature text.
    """
    if not minisign_available:
        pytest.skip("minisign binary not installed (mirrors ci.yml PG auto-skip)")

    seckey = tmp_path / "test.key"
    pubkey = tmp_path / "test.pub"
    manifest = tmp_path / "manifest.txt"
    manifest.write_text(
        "version=1.16\narchive=MyOriShop-1.16.zip\nsha256=deadbeef\n",
        encoding="utf-8",
    )
    subprocess.run(
        ["minisign", "-G", "-W", "-p", str(pubkey), "-s", str(seckey)],
        check=True,
        capture_output=True,
        timeout=60,
    )
    subprocess.run(
        ["minisign", "-S", "-s", str(seckey), "-m", str(manifest)],
        check=True,
        capture_output=True,
        timeout=60,
    )
    sig = manifest.with_name(manifest.name + ".minisig")
    return {
        "pubkey": pubkey.read_text(encoding="utf-8"),
        "manifest": manifest,
        "sig_text": sig.read_text(encoding="utf-8"),
    }


# --- UPD-01: startup/manual check, offline = silent no-op -------------------


def test_check_detects_newer(monkeypatch):
    """UPD-01 (T-32-10): a newer signed release is reported ``available`` with its
    version + notes; offline (fetch returns None) is a silent no-op that NEVER
    raises. RED until Wave 02 builds ``app.services.update``."""
    from app import __version__ as current_version  # noqa: PLC0415
    from app.services import update  # noqa: PLC0415

    # Derive "newer" from the CURRENT app version instead of hard-coding it:
    # pinning a literal (it was "1.16") makes every routine __version__ bump a
    # false failure. Versions here are 1.N, not semver.
    major, minor = current_version.split(".")
    newer_version = f"{major}.{int(minor) + 1}"

    monkeypatch.setattr(update, "fetch_latest_release", lambda: fake_release_json())
    # The manifest fetch/verify seam yields a signature-verified version + notes.
    monkeypatch.setattr(
        update,
        "verified_manifest_version",
        lambda release: (newer_version, "release notes text"),
        raising=False,
    )

    status = update.check_for_update()
    assert status.state == "available"
    assert status.latest == newer_version
    assert "release notes text" in (status.notes or "")

    # Offline: fetch returns None ⇒ silent no-op, NOTHING raises (UPD-01/T-32-10).
    monkeypatch.setattr(update, "fetch_latest_release", lambda: None)
    offline = update.check_for_update()
    assert offline.state == "offline"


# --- UPD-06: hard no-op on the PostgreSQL server ----------------------------


def test_server_noop(monkeypatch):
    """UPD-06: on the central PostgreSQL server the entire update path is a hard
    no-op and NEVER performs a network fetch. RED until Wave 02."""
    from app.services import update  # noqa: PLC0415

    class _FakeDialect:
        name = "postgresql"

    class _FakeEngine:
        dialect = _FakeDialect()

    import app.db  # noqa: PLC0415

    monkeypatch.setattr(app.db, "engine", _FakeEngine(), raising=False)

    def _fetch_must_not_run():
        raise AssertionError("network fetch must not run on the PostgreSQL server")

    monkeypatch.setattr(update, "fetch_latest_release", _fetch_must_not_run)

    status = update.check_for_update()
    assert status.state == "noop"


# --- UPD-02: verify-before-unpack (SHA-256 AND Ed25519) hard gate -----------


def test_verify_gate(synthetic_release, tmp_path, monkeypatch):
    """UPD-02 (T-32-01/T-32-05): ``sha256_matches`` is True for the good archive
    and False after a single flipped byte; ``update.apply`` ABORTS and stages
    NOTHING when the gate fails (bad SHA-256 OR bad Ed25519). RED until Waves
    03/04."""
    from app.services import minisign_verify, update  # noqa: PLC0415

    archive = synthetic_release["archive"]
    good_sha = synthetic_release["good_sha"]

    assert minisign_verify.sha256_matches(archive, good_sha) is True
    tampered = bytearray(archive.read_bytes())
    tampered[0] ^= 0xFF
    archive.write_bytes(bytes(tampered))
    assert minisign_verify.sha256_matches(archive, good_sha) is False

    # A failed gate ⇒ apply aborts and NOTHING is unpacked into staged/.
    monkeypatch.setattr(update, "verify_release", lambda *a, **k: False, raising=False)
    with pytest.raises(Exception):
        update.apply(fake_release_json(), install_root=tmp_path)
    assert not (tmp_path / "staged").exists()


@pytest.mark.skipif(
    not minisign_available,
    reason="minisign binary not installed (mirrors ci.yml PG auto-skip)",
)
def test_minisign_pure_python_verify(throwaway_keypair):
    """UPD-02 (T-32-01): the pure-Python ``verify_minisign`` matches the real
    minisign binary — True for a validly-signed manifest, False for a tampered
    one — proving the ``cryptography`` Ed25519 verify is correct. Skip-gated on
    the binary. RED until Wave 03."""
    from app.services import minisign_verify  # noqa: PLC0415

    manifest_bytes = throwaway_keypair["manifest"].read_bytes()
    sig_text = throwaway_keypair["sig_text"]
    pubkey_text = throwaway_keypair["pubkey"]

    assert (
        minisign_verify.verify_minisign(manifest_bytes, sig_text, pubkey_text) is True
    )
    # Tamper the signed payload ⇒ the pure-Python verify must reject it.
    assert (
        minisign_verify.verify_minisign(manifest_bytes + b"x", sig_text, pubkey_text)
        is False
    )


# --- UPD-05: integer anti-downgrade compare ---------------------------------


def test_anti_downgrade(monkeypatch):
    """UPD-05 (T-32-02): ``is_strictly_newer`` compares the integer ``"1.<N>"``
    counter (incl. the 9→10 boundary STATE.md flags); a signed-manifest version
    that is NOT strictly newer than the installed one yields ``up_to_date``. RED
    until Wave 02."""
    from app.services import update  # noqa: PLC0415

    assert update.is_strictly_newer("1.16", "1.15") is True
    assert update.is_strictly_newer("1.10", "1.9") is True  # 9→10 boundary
    assert update.is_strictly_newer("1.15", "1.15") is False
    assert update.is_strictly_newer("1.14", "1.15") is False

    # A verified-manifest version that is not strictly newer ⇒ up_to_date.
    monkeypatch.setattr(update, "fetch_latest_release", lambda: fake_release_json())
    monkeypatch.setattr(
        update,
        "verified_manifest_version",
        lambda release: ("1.0", "notes"),
        raising=False,
    )
    status = update.check_for_update()
    assert status.state == "up_to_date"


# --- UPD-03: notify-and-confirm surface (confirm applies / «Позже» dismisses)


def test_confirm_and_defer(client, monkeypatch):
    """UPD-03: the authenticated admin confirms with ``POST /settings/update/apply``
    (200, applying partial with release notes AUTOESCAPED, never ``|safe``) and
    dismisses with ``POST /settings/update/dismiss`` (200, notice gone). RED until
    Wave 05 builds the routes."""
    from app.services import update  # noqa: PLC0415

    # An available update whose notes carry an HTML metacharacter.
    monkeypatch.setattr(
        update,
        "get_cached_status",
        lambda *a, **k: update.UpdateStatus(
            state="available", latest="1.16", current="1.0", notes="<b>bold</b> notes"
        ),
        raising=False,
    )

    applied = client.post("/settings/update/apply")
    assert applied.status_code == 200
    # Release notes are autoescaped: the raw tag must NOT appear, the escaped form must.
    assert "<b>bold</b>" not in applied.text
    assert "&lt;b&gt;bold&lt;/b&gt;" in applied.text

    dismissed = client.post("/settings/update/dismiss")
    assert dismissed.status_code == 200


# --- UPD-07: manual «Проверить обновления» ----------------------------------


def test_manual_check(client, monkeypatch):
    """UPD-07: ``POST /settings/update/check`` returns 200 with a ``#update-panel``
    partial (up-to-date / available / offline caption) — NEVER a 5xx, even when
    the fetch fails offline. RED until Wave 05 builds the route."""
    from app.services import update  # noqa: PLC0415

    # Even when the fetch fails (offline), the manual check must never 5xx.
    monkeypatch.setattr(update, "fetch_latest_release", lambda: None)

    resp = client.post("/settings/update/check")
    assert resp.status_code == 200
    assert "update-panel" in resp.text

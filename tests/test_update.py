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


def _newer_version() -> str:
    """One counter above the INSTALLED ``__version__`` (versions are ``1.<N>``).

    Derived, never literal: the app version is bumped on every commit, so a
    hard-coded "1.16" would turn the next routine bump into a false failure.
    """
    from app import __version__  # noqa: PLC0415

    major, minor = __version__.split(".")
    return f"{major}.{int(minor) + 1}"


def _release_with_hosts(host: str, version: str = "1.99") -> dict:
    """A release JSON whose three asset URLs all live on ``host``."""
    base = f"https://{host}/viktorplus/myorishop/releases/download/v{version}"
    return {
        "tag_name": f"v{version}",
        "body": "release notes text",
        "assets": [
            {"name": "manifest.txt", "browser_download_url": f"{base}/manifest.txt"},
            {
                "name": "manifest.txt.minisig",
                "browser_download_url": f"{base}/manifest.txt.minisig",
            },
            {
                "name": f"MyOriShop-{version}.zip",
                "browser_download_url": f"{base}/MyOriShop-{version}.zip",
            },
        ],
    }


# --- T-32-03 / V5: the asset-host allowlist (SEC-A3) ------------------------


def test_offhost_asset_url_is_refused_before_any_download(tmp_path, monkeypatch):
    """UPD-02 (T-32-03, V5): a release whose assets are served off an
    unexpected host is refused by BOTH trust entry points, and the refusal
    happens BEFORE a single byte is fetched. The tripwire RECORDS instead of
    raising on purpose: both entry points swallow every exception into
    ``return None``, so a raising stub would make this test vacuous."""
    from app.services import update  # noqa: PLC0415

    fetched: list[str] = []

    def _download_must_not_run(url):
        fetched.append(url)
        return b""

    monkeypatch.setattr(update, "_download", _download_must_not_run)

    evil = _release_with_hosts("evil.example.com", _newer_version())
    assert update.verify_release(evil, tmp_path) is None
    assert update.verified_manifest_version(evil) is None

    # A look-alike host (suffix of an allowed one) must not slip through either.
    lookalike = _release_with_hosts("github.com.evil.example.com", _newer_version())
    assert update.verify_release(lookalike, tmp_path) is None
    assert update.verified_manifest_version(lookalike) is None

    assert fetched == []  # not one off-host byte was requested


# --- T-32-05: adversarial zip-slip member (SEC-A4) --------------------------


def test_extract_guarded_rejects_zip_slip_member(tmp_path):
    """UPD-02 (T-32-05, ASVS V12): an archive carrying a ``../`` member raises
    ``ValueError`` and NOTHING is written outside the staged dir — the whole
    namelist is pre-scanned before ``extractall`` ever runs. The drive-absolute
    member half runs on Windows only (on POSIX ``C:\\`` is a legal relative name)."""
    import os  # noqa: PLC0415

    from app.services import update  # noqa: PLC0415

    staged = tmp_path / "staged"
    escaped = tmp_path / "evil.txt"

    slip = tmp_path / "slip.zip"
    with zipfile.ZipFile(slip, "w") as zf:
        zf.writestr("app/ok.txt", "harmless")
        zf.writestr("../evil.txt", "pwned")

    with pytest.raises(ValueError):
        update._extract_guarded(slip, staged)
    assert not escaped.exists()  # nothing escaped the staged dir
    assert not (staged / "app" / "ok.txt").exists()  # and nothing was extracted

    if os.name == "nt":
        absolute = tmp_path / "absolute.zip"
        outside = tmp_path / "outside" / "evil.txt"
        with zipfile.ZipFile(absolute, "w") as zf:
            zf.writestr(str(outside).replace("\\", "/"), "pwned")
        with pytest.raises(ValueError):
            update._extract_guarded(absolute, staged)
        assert not outside.exists()


# --- T-32-01/T-32-03: the REAL verify_release gate ordering (SEC-A1/A9) -----


def test_verify_release_gate_ordering_is_real(tmp_path, monkeypatch):
    """UPD-02 (T-32-01/T-32-03): the REAL ``verify_release`` (not a stub) (a)
    refuses and NEVER downloads the big archive when the Ed25519 signature
    fails — proving verify precedes the download; (b) refuses when the archive
    bytes do not match the SHA-256 in the signed manifest; (c) on a clean gate
    returns the version read from the SIGNED MANIFEST, not from the git tag."""
    from app.services import minisign_verify, update  # noqa: PLC0415

    trusted = _newer_version()
    release = _release_with_hosts("github.com", trusted)
    # The tag deliberately LIES: a far-higher version than the signed manifest.
    release["tag_name"] = "v1.999"

    archive_bytes = io.BytesIO()
    with zipfile.ZipFile(archive_bytes, "w") as zf:
        zf.writestr("app/marker.txt", f"staged-{trusted}")
    archive_bytes = archive_bytes.getvalue()
    good_sha = hashlib.sha256(archive_bytes).hexdigest()

    urls = {a["name"]: a["browser_download_url"] for a in release["assets"]}
    arc_url = urls[f"MyOriShop-{trusted}.zip"]
    served = {
        urls["manifest.txt"]: (
            f"version={trusted}\narchive=MyOriShop-{trusted}.zip\n"
            f"sha256={good_sha}\n"
        ).encode(),
        urls["manifest.txt.minisig"]: b"untrusted comment\nZmFrZXNpZw==\n",
        arc_url: archive_bytes,
    }
    fetched: list[str] = []

    def _fake_download(url):
        fetched.append(url)
        return served[url]

    monkeypatch.setattr(update, "_download", _fake_download)

    # (a) bad signature ⇒ None, and the ARCHIVE was never fetched.
    monkeypatch.setattr(minisign_verify, "verify_minisign", lambda *a, **k: False)
    assert update.verify_release(release, tmp_path) is None
    # Ordering proof: the manifest+sig WERE fetched, the multi-MB archive was NOT.
    assert urls["manifest.txt"] in fetched
    assert urls["manifest.txt.minisig"] in fetched
    assert arc_url not in fetched

    # (b) good signature but tampered archive bytes ⇒ checksum mismatch ⇒ None.
    monkeypatch.setattr(minisign_verify, "verify_minisign", lambda *a, **k: True)
    served[arc_url] = archive_bytes + b"tampered"
    assert update.verify_release(release, tmp_path) is None

    # (c) clean gate ⇒ (trusted_version, archive_path); version from the MANIFEST.
    served[arc_url] = archive_bytes
    verified = update.verify_release(release, tmp_path)
    assert verified is not None
    version, archive_path = verified
    assert version == trusted  # NOT "1.999" from the mutable tag (T-32-04)
    assert Path(archive_path).read_bytes() == archive_bytes


# --- UPD-06: apply() dialect gate on the PostgreSQL server ------------------


def test_apply_is_noop_on_postgresql(monkeypatch):
    """UPD-06 (T-32-09): on the central PostgreSQL server ``apply`` returns a
    hard ``noop`` before resolving or verifying anything — both the fetch and
    the verify seams are tripwires that fail the test if reached."""
    from app.services import update  # noqa: PLC0415

    class _FakeEngine:
        class dialect:  # noqa: N801 — mirrors the SQLAlchemy attribute shape
            name = "postgresql"

    def _must_not_run(*args, **kwargs):
        raise AssertionError("the server must never fetch or verify a release")

    monkeypatch.setattr(update, "fetch_latest_release", _must_not_run)
    monkeypatch.setattr(update, "verify_release", _must_not_run)

    result = update.apply(release=fake_release_json(), engine=_FakeEngine())
    assert result.state == "noop"
    assert result.staged_version is None


# --- UPD-04: the apply() happy path (staged + backup + marker) --------------


def test_apply_stages_backup_and_marker(engine, tmp_path, monkeypatch):
    """UPD-04 (T-32-08/T-32-06): a clean gate unpacks into ``staged/``, takes a
    pre-update ``VACUUM INTO`` backup that really exists on disk, and writes
    ``data/pending.json`` with EXACTLY the 3 launcher keys and RELATIVE paths."""
    import json  # noqa: PLC0415

    from app.config import settings  # noqa: PLC0415
    from app.services import update  # noqa: PLC0415

    trusted = _newer_version()
    install_root = tmp_path / "install"
    install_root.mkdir()
    monkeypatch.setattr(settings, "backup_dir", str(install_root / "backups"))

    archive = tmp_path / f"MyOriShop-{trusted}.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("app/__init__.py", f'__version__ = "{trusted}"\n')
        zf.writestr("app/marker.txt", f"staged-{trusted}")

    monkeypatch.setattr(
        update, "verify_release", lambda *a, **k: (trusted, archive), raising=False
    )

    result = update.apply(
        release=fake_release_json(), engine=engine, install_root=install_root
    )
    assert result.state == "staged"
    assert result.staged_version == trusted

    # (1) the archive is really unpacked into staged/
    staged = install_root / "staged"
    assert (staged / "app" / "marker.txt").read_text(encoding="utf-8") == (
        f"staged-{trusted}"
    )

    # (2) a real pre-update backup file exists on disk
    backups = sorted((install_root / "backups").glob("myorishop-*.db"))
    assert len(backups) == 1
    assert backups[0].stat().st_size > 0

    # (3) the launcher marker: EXACTLY 3 keys, RELATIVE paths (T-32-06)
    marker = json.loads(
        (install_root / "data" / "pending.json").read_text(encoding="utf-8")
    )
    assert set(marker) == {"staged_dir", "expected_version", "db_backup_path"}
    assert marker["expected_version"] == trusted
    assert marker["staged_dir"] == "staged"
    assert marker["db_backup_path"] == f"backups/{backups[0].name}"
    assert not Path(marker["staged_dir"]).is_absolute()
    assert not Path(marker["db_backup_path"]).is_absolute()
    assert not (install_root / "data" / "pending.json.partial").exists()


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

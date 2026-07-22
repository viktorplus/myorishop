"""Wave-0 RED validation scaffold for Phase 31 PKG-05 (signed-release manifest + verify).

Contract note (Nyquist Wave 0): RED-by-design. `build_release` (Plan 04) is imported
INSIDE each pure-Python test body so Wave-0 collection stays green. The pure-Python
checksum/version half ALWAYS runs (no external tool). The minisign round-trip is
skip-gated on the binary being present (mirrors ci.yml's DATABASE_URL-absent PG
auto-skip); the vendored-pubkey test is skip-gated on app/minisign.pub existing — the
OFFLINE operator supplies that key with `minisign -G`, never CI (threat T-31-02).

Threats pinned here: T-31-02 (signing-key exfiltration — the production secret key
never enters CI; only a THROWAWAY tmp keypair is generated here), T-31-03 (tampered
release archive / manifest — SHA-256 tamper-detection + minisign tamper-fail). PKG-05.
"""

import hashlib
import shutil
import subprocess
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
minisign_available = shutil.which("minisign") is not None


def _read_version() -> str:
    """The single source of truth for the '1.<N>' version (app/__init__.py)."""
    import app  # noqa: PLC0415 — cheap: __init__ only sets __version__

    return app.__version__


# --- PKG-05: pure-Python manifest + SHA-256 (always runs) -------------------


def test_manifest_binds_version_and_sha256(tmp_path):
    """PKG-05: build_release.write_manifest binds version + archive filename +
    the archive's REAL hashlib.sha256 into manifest.txt. RED until Plan 04."""
    import build_release  # noqa: PLC0415 — in-body import keeps collection green

    archive = tmp_path / "MyOriShop-1.1.zip"
    payload = b"pretend onedir zip bytes"
    archive.write_bytes(payload)
    expected_sha = hashlib.sha256(payload).hexdigest()
    version = _read_version()

    manifest = build_release.write_manifest(
        archive_path=archive, version=version, dest=tmp_path / "manifest.txt"
    )
    text = Path(manifest).read_text(encoding="utf-8")

    assert f"version={version}" in text
    assert archive.name in text
    assert expected_sha in text


def test_manifest_tamper_is_detected(tmp_path):
    """PKG-05 (T-31-03): flipping one archive byte AFTER the manifest is written
    makes the verify helper re-hash the archive and return False. RED until
    Plan 04."""
    import build_release  # noqa: PLC0415

    archive = tmp_path / "MyOriShop-1.1.zip"
    archive.write_bytes(b"good archive bytes")
    manifest = build_release.write_manifest(
        archive_path=archive, version=_read_version(), dest=tmp_path / "manifest.txt"
    )
    assert build_release.verify_manifest(archive, manifest) is True

    tampered = bytearray(archive.read_bytes())
    tampered[0] ^= 0xFF
    archive.write_bytes(bytes(tampered))
    assert build_release.verify_manifest(archive, manifest) is False


def test_build_asserts_tag_matches_version(tmp_path):
    """PKG-05 tag↔version contract: assert_tag_matches_version accepts a tag
    'v<__version__>' and rejects a mismatch (feeds UPD-05 anti-downgrade). RED
    until Plan 04."""
    import build_release  # noqa: PLC0415

    version = _read_version()  # e.g. "1.1"
    # Matching tag is accepted (does not raise).
    build_release.assert_tag_matches_version(f"v{version}")
    # A mismatched tag is rejected.
    with pytest.raises(ValueError):
        build_release.assert_tag_matches_version("v1.999999")


# --- PKG-05: minisign signature half (skip-gated on the binary) -------------


@pytest.mark.skipif(
    not minisign_available,
    reason="minisign binary not installed (mirrors ci.yml PG auto-skip)",
)
def test_minisign_roundtrip_verifies_and_tamper_fails(tmp_path):
    """PKG-05 (T-31-02/T-31-03): a THROWAWAY keypair (never app/minisign.pub,
    whose secret is offline-only) signs manifest.txt; `minisign -Vm` passes, then
    a corrupted manifest FAILS verification. Skip-gated on the binary."""
    seckey = tmp_path / "test.key"
    pubkey = tmp_path / "test.pub"
    manifest = tmp_path / "manifest.txt"
    manifest.write_text(
        "version=1.1\narchive=MyOriShop-1.1.zip\nsha256=deadbeef\n", encoding="utf-8"
    )

    # -W: unencrypted secret key so keygen/sign never prompt (non-interactive).
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
    ok = subprocess.run(
        ["minisign", "-Vm", str(manifest), "-p", str(pubkey)],
        capture_output=True,
        timeout=60,
    )
    assert ok.returncode == 0, "minisign failed to verify a validly-signed manifest"

    manifest.write_text(
        "version=1.1\narchive=MyOriShop-1.1.zip\nsha256=tampered\n", encoding="utf-8"
    )
    bad = subprocess.run(
        ["minisign", "-Vm", str(manifest), "-p", str(pubkey)],
        capture_output=True,
        timeout=60,
    )
    assert bad.returncode != 0, "minisign must reject a tampered manifest"


@pytest.mark.skipif(
    not (_REPO_ROOT / "app" / "minisign.pub").exists(),
    reason="app/minisign.pub is supplied OFFLINE by the operator with `minisign -G` "
    "(threat T-31-02), never by CI/dev — SKIP until it exists",
)
def test_vendored_pubkey_present_and_bundled():
    """PKG-05: WHEN the operator has vendored app/minisign.pub, its base64 key
    line starts 'RW' (minisign public-key marker) and build_release bundles it
    into the onedir. Otherwise this test SKIPS so the suite stays green in
    CI/dev. RED (build_release absent) only once the key exists."""
    pub = _REPO_ROOT / "app" / "minisign.pub"
    lines = [line for line in pub.read_text(encoding="utf-8").splitlines() if line.strip()]
    key_line = lines[-1]  # first line is the untrusted comment; last is the key
    assert key_line.startswith("RW")

    import build_release  # noqa: PLC0415

    assert "minisign.pub" in build_release.VENDORED_APP_ASSETS

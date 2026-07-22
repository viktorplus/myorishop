"""In-app secure self-update service — the READ (check) half (Phase 32, Wave 2).

This module concentrates the *trust logic* of the self-update feature: detect a
newer release, but only ever offer one whose signed manifest authenticates and
whose integer version is strictly newer than the installed one. The APPLY half
(download archive, verify SHA-256 + Ed25519, VACUUM backup, unpack) is added by
Plan 04; this plan fixes the ``UpdateStatus`` interface Waves 03/04/05 build on.

Composed from four shipped idioms:
- UPD-06 dialect no-op gate — copied from ``backup.startup_backup`` (the whole
  path exists only for the SQLite client; the PostgreSQL server never fetches).
- UPD-01 offline-safe httpx posture — ``httpx.HTTPError`` ⇒ silent no-op, mirroring
  ``sync_client``; a check NEVER raises into the caller.
- UPD-05 integer anti-downgrade compare on the ``"1.<N>"`` counter (9→10 boundary).
- Verify-before-trust: the offered version is read from the SIGNATURE-VERIFIED
  manifest, never from the mutable git ``tag_name`` (UPD-02).
"""

import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

import httpx

from app import __version__
from app.services import minisign_verify

# GitHub repo the releases are published to; tag_name only LOCATES a release.
_REPO = "viktorplus/myorishop"

# Same strict timeout as sync_client (RESEARCH A1): a short connect fails fast
# offline, a longer read tolerates the tiny manifest/sig download.
UPDATE_TIMEOUT = httpx.Timeout(connect=3.0, read=10.0, write=10.0, pool=3.0)

# V5 asset-host allowlist: a release asset URL must live on GitHub's own hosts.
_ALLOWED_ASSET_HOSTS = {"github.com", "objects.githubusercontent.com"}

# The trusted version shape ("1.<N>") and the tag shape ("v1.<N>").
_VERSION_RE = re.compile(r"^1\.\d+$")
_TAG_RE = re.compile(r"^v1\.\d+$")

# Vendored minisign public key (offline-signed releases verify against this).
_PUBKEY_PATH = Path(__file__).resolve().parent.parent / "minisign.pub"


@dataclass(frozen=True)
class UpdateStatus:
    """The immutable result of a check — the interface Waves 03/04/05 consume.

    ``state`` is one of ``"available" | "up_to_date" | "offline" | "noop" |
    "error"``. ``latest``/``notes``/``tag``/``assets`` are populated only when a
    signature-verified newer release is available.
    """

    state: str
    current: str = __version__
    latest: str | None = None
    notes: str | None = None
    tag: str | None = None
    assets: dict[str, str] | None = None


# The last check result — populated by the startup check (Plan 05) and read by
# the settings page on first paint (get_cached_status).
_LAST_CHECK: UpdateStatus | None = None


def _counter(version: str) -> int:
    """The integer counter after the dot in a ``"1.<N>"`` version string."""
    return int(version.split(".", 1)[1])


def is_strictly_newer(remote: str, local: str) -> bool:
    """True iff ``remote``'s integer counter is strictly greater than ``local``'s.

    Integer compare (UPD-05) so ``"1.10" > "1.9"`` (the 9→10 boundary) — never a
    string compare. A malformed input returns False rather than raising.
    """
    try:
        return _counter(remote) > _counter(local)
    except Exception:
        return False


def _parse_manifest(manifest_bytes: bytes) -> dict[str, str]:
    """Parse the ``key=value`` lines of a manifest into a dict (build_release shape)."""
    fields: dict[str, str] = {}
    for raw in manifest_bytes.decode("utf-8").splitlines():
        line = raw.strip()
        if not line or "=" not in line:
            continue
        key, _, value = line.partition("=")
        fields[key.strip()] = value.strip()
    return fields


def _download(url: str) -> bytes:
    """GET a small asset with the update timeout/User-Agent; raise on HTTP error."""
    resp = httpx.get(
        url,
        headers={"User-Agent": f"MyOriShop/{__version__}"},
        timeout=UPDATE_TIMEOUT,
        follow_redirects=True,
    )
    resp.raise_for_status()
    return resp.content


def fetch_latest_release() -> dict | None:
    """Fetch the GitHub ``/releases/latest`` JSON, or None offline (UPD-01).

    Any ``httpx.HTTPError`` (unreachable, timeout, rate-limited 4xx/5xx) is a
    silent no-op — the caller treats None as "offline" and never sees an
    exception (Pitfall 5: a User-Agent header keeps GitHub from 403-ing us).
    """
    try:
        resp = httpx.get(
            f"https://api.github.com/repos/{_REPO}/releases/latest",
            headers={
                "User-Agent": f"MyOriShop/{__version__}",
                "Accept": "application/vnd.github+json",
            },
            timeout=UPDATE_TIMEOUT,
        )
        resp.raise_for_status()
        return resp.json()
    except httpx.HTTPError:
        return None


def verified_manifest_version(release: dict) -> tuple[str, str] | None:
    """Download + Ed25519-verify the release manifest; return ``(version, notes)``.

    The trust gate: locate ``manifest.txt`` + ``manifest.txt.minisig`` by asset
    name, enforce the host allowlist (V5), download both, and only if
    ``verify_minisign`` returns True read the ``version=`` field from the verified
    manifest (validated against ``^1\\.\\d+$``). The version is NEVER read from the
    mutable ``tag_name`` (T-32-04). Returns None on ANY failure (a release we
    cannot authenticate is not offered).
    """
    try:
        assets = {
            a.get("name"): a.get("browser_download_url")
            for a in release.get("assets", [])
        }
        man_url = assets.get("manifest.txt")
        sig_url = assets.get("manifest.txt.minisig")
        if not man_url or not sig_url:
            return None
        for url in (man_url, sig_url):
            if urlparse(url).hostname not in _ALLOWED_ASSET_HOSTS:
                return None  # V5: reject an asset served off an unexpected host
        manifest_bytes = _download(man_url)
        sig_text = _download(sig_url).decode("utf-8")
        # Verify BEFORE reading any field from the manifest (T-32-01/T-32-04).
        if not minisign_verify.verify_minisign(
            manifest_bytes, sig_text, _PUBKEY_PATH.read_text(encoding="utf-8")
        ):
            return None
        version = _parse_manifest(manifest_bytes).get("version", "")
        if not _VERSION_RE.match(version):
            return None
        return version, release.get("body")
    except Exception:
        return None


def check_for_update(engine=None) -> UpdateStatus:
    """Detect a newer signed release; silent no-op offline and on PostgreSQL.

    Caches and returns the result in ``_LAST_CHECK``. The whole body is broadly
    guarded so a check NEVER raises into the caller (UPD-01/T-32-10).
    """
    global _LAST_CHECK
    current = __version__
    try:
        # 1. Dialect gate FIRST — no network fetch on the PostgreSQL server (UPD-06).
        if engine is None:
            from app import db

            engine = db.engine
        if engine.dialect.name != "sqlite":
            _LAST_CHECK = UpdateStatus(state="noop", current=current)
            return _LAST_CHECK

        # 2. Fetch — None ⇒ offline (silent).
        release = fetch_latest_release()
        if release is None:
            _LAST_CHECK = UpdateStatus(state="offline", current=current)
            return _LAST_CHECK

        # 3. tag_name only LOCATES the release; a malformed tag ⇒ error, no trust.
        tag = release.get("tag_name", "")
        if not _TAG_RE.match(tag):
            _LAST_CHECK = UpdateStatus(state="error", current=current)
            return _LAST_CHECK

        # 4. Download + signature-verify the manifest; read the TRUSTED version.
        verified = verified_manifest_version(release)
        if verified is None:
            _LAST_CHECK = UpdateStatus(state="error", current=current, tag=tag)
            return _LAST_CHECK
        latest, notes = verified

        # 5. Anti-downgrade: offer only a strictly-newer signed version (UPD-05).
        if is_strictly_newer(latest, current):
            assets = {
                a.get("name"): a.get("browser_download_url")
                for a in release.get("assets", [])
            }
            _LAST_CHECK = UpdateStatus(
                state="available",
                current=current,
                latest=latest,
                notes=notes,
                tag=tag,
                assets=assets,
            )
        else:
            _LAST_CHECK = UpdateStatus(
                state="up_to_date", current=current, latest=latest, tag=tag
            )
        return _LAST_CHECK
    except Exception:
        _LAST_CHECK = UpdateStatus(state="offline", current=current)
        return _LAST_CHECK


def get_cached_status() -> UpdateStatus | None:
    """Return the last check result (populated by the startup check, Plan 05)."""
    return _LAST_CHECK

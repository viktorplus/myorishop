"""Repeatable Windows onedir build assembler for MyOriShop (Phase 31, PKG-01/02/05).

Turns the git+uv dev checkout into a self-contained, launchable Windows
distributable: the official Python 3.13 *embeddable* runtime (genuine
Microsoft-recognized ``python.exe`` + stdlib zip — NOT PyInstaller, NOT a
single-file exe, RESEARCH Pattern 1 / Anti-Patterns) plus the locked wheels
vendored into ``Lib\\site-packages``, the app source, the whole ``alembic\\``
migration tree, ``alembic.ini`` and the stable launcher.

Design for testability (Nyquist): the heavy, network-bound
``fetch_embeddable`` (download + SHA-256 verify against python.org) is kept
separate from the pure filesystem ``assemble_onedir``, which accepts an
injected embeddable zip + a pre-built wheel dir so a unit test can drive it
with tiny synthetic inputs (see tests/test_packaging.py, tests/test_release_verify.py).

This module is stdlib-only and MUST NOT import ``app`` — the version is parsed
out of ``app/__init__.py`` without importing the dependency graph
(assert_tag_matches_version). It runs under uv on the build box / CI runner.

Requirements: PKG-01 (onedir layout), PKG-02 (per-user .iss), PKG-05
(manifest + SHA-256 + tag<->version contract).
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import re
import shutil
import sys
import urllib.request
import zipfile
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent

# The install-root layout the launcher (Plan 03) and the .iss (PKG-02) assume:
#   <root>\app\      <- SWAPPABLE embeddable bundle (this is `dest`)
#   <root>\launcher\ <- STABLE PID owner, OUTSIDE app\ (never swapped)
#   <root>\data\     <- SIBLING operator state (created on first run, NOT shipped)

# RESEARCH Pattern 1 / Pitfall 1 — the #1 embeddable gotcha. The stock
# embeddable ._pth restricts sys.path and omits site-packages + site, so
# vendored wheels are un-importable. These five lines fix it.
_PTH_LINES = ("python313.zip", ".", "app", "Lib\\site-packages", "import site")

# App-tree assets vendored read-only into the bundle (offline convention,
# PATTERNS "Vendored-offline asset"). The minisign public key (Phase 32 verify)
# is committed by the OFFLINE operator; absent on dev/CI so it is optional here.
VENDORED_APP_ASSETS: tuple[str, ...] = ("minisign.pub",)

# Pinned Python embeddable releases. The SHA-256 MUST be the value published on
# python.org for the amd64 embeddable zip of that exact release. It is left
# empty on purpose: an UNVERIFIED hash would silently defeat the supply-chain
# guard (T-31-SC). Add an entry only after verifying the digest against
# https://www.python.org/downloads/release/ — fetch_embeddable refuses to
# download a version whose digest is not pinned (or passed in explicitly).
EMBEDDABLE_SHA256: dict[str, str] = {
    # Verified via python.org: the published MD5 for python-3.13.1-embed-amd64.zip
    # (d5c8030976b5eaf55ed6b321c073dda7) was confirmed against the downloaded file,
    # then this SHA-256 was computed from that same authenticated download.
    "3.13.1": "7b7923ff0183a8b8fca90f6047184b419b108cb437f75fc1c002f9d2f8bcec16",
}

_EMBEDDABLE_URL = "https://www.python.org/ftp/python/{version}/python-{version}-embed-amd64.zip"


def fetch_embeddable(
    version: str, cache_dir: Path, *, expected_sha256: str | None = None
) -> Path:
    """Download the pinned python-<version>-embed-amd64.zip, SHA-256 verified.

    Heavy / network-bound — never exercised by the unit tests (they inject a
    synthetic zip). Verifies the download against the python.org-published
    digest (T-31-SC); refuses any version whose digest is not pinned so a build
    can never assemble an unverified runtime.
    """
    sha = expected_sha256 or EMBEDDABLE_SHA256.get(version)
    if not sha:
        raise ValueError(
            f"No verified SHA-256 pinned for python-{version}-embed-amd64.zip. "
            "Verify the digest against python.org and add it to EMBEDDABLE_SHA256 "
            "(or pass expected_sha256=) before building — refusing to download an "
            "unpinned runtime (T-31-SC)."
        )
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    target = cache_dir / f"python-{version}-embed-amd64.zip"
    if not target.exists():
        url = _EMBEDDABLE_URL.format(version=version)
        # Delete-partial-on-failure (backup.py idiom): a truncated download must
        # never masquerade as a valid, hash-checked runtime.
        try:
            with urllib.request.urlopen(url) as resp:  # noqa: S310 — pinned python.org URL
                target.write_bytes(resp.read())
        except Exception:
            target.unlink(missing_ok=True)
            raise
    actual = hashlib.sha256(target.read_bytes()).hexdigest()
    if actual.lower() != sha.lower():
        target.unlink(missing_ok=True)
        raise ValueError(
            f"Embeddable SHA-256 mismatch for {target.name}: expected {sha}, got {actual}"
        )
    return target


def vendor_wheels(target: Path, *, repo_root: Path, requirements: Path | None = None) -> Path:
    """Vendor the uv.lock-locked deps into <target> via pip install --target.

    Build-time only (the embeddable dist ships no pip). Pitfall 7: this MUST run
    on Windows so the cp313 win_amd64 wheels (pydantic-core, argon2-cffi, cffi,
    psycopg) match the operator box — the unit tests inject a fake wheel dir
    instead of calling this. Exports the frozen requirements from uv.lock first.
    """
    import subprocess  # noqa: PLC0415 — local: keeps import surface small for tests

    target = Path(target)
    target.mkdir(parents=True, exist_ok=True)
    if requirements is None:
        requirements = Path(repo_root) / "requirements-locked.txt"
        subprocess.run(  # noqa: S603 — fixed argv, no shell
            ["uv", "export", "--frozen", "--no-dev", "--no-hashes", "-o", str(requirements)],
            check=True,
            cwd=str(repo_root),
        )
    subprocess.run(  # noqa: S603 — fixed argv, no shell
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--target",
            str(target),
            "--no-deps",
            "-r",
            str(requirements),
        ],
        check=True,
    )
    return target


def _write_pth(dest_app: Path) -> None:
    """Overwrite the extracted embeddable ._pth with the site-packages-enabled one."""
    (dest_app / "python313._pth").write_text("\n".join(_PTH_LINES) + "\n", encoding="utf-8")


def assemble_onedir(
    *,
    embeddable_zip: Path,
    wheel_dir: Path,
    dest: Path,
    repo_root: Path,
) -> Path:
    """Assemble the self-contained onedir bundle at <dest> (the swappable app\\).

    Extracts the embeddable runtime, fixes ``python313._pth`` (Lib\\site-packages
    + import site, Pattern 1), vendors <wheel_dir> into ``Lib\\site-packages``,
    copies app/, alembic/ (incl. versions/), alembic.ini and the vendored assets
    verbatim, and drops the launcher/ tree next to <dest> (OUTSIDE app\\). Asserts
    every repo alembic migration is bundled (Pitfall 5). Delete-partial-on-failure:
    a half-written bundle is removed so it can never pass for a valid one.

    Returns the bundle dir (<dest>).
    """
    embeddable_zip = Path(embeddable_zip)
    wheel_dir = Path(wheel_dir)
    dest = Path(dest)
    repo_root = Path(repo_root)

    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)

    try:
        # 1. Embeddable runtime -> dest (python.exe, python313.zip, python313._pth).
        with zipfile.ZipFile(embeddable_zip) as zf:
            zf.extractall(dest)
        # 2. Fix the search path so vendored wheels import (Pitfall 1).
        _write_pth(dest)

        # 3. Vendor the (pre-built) wheels into Lib\site-packages.
        site_packages = dest / "Lib" / "site-packages"
        site_packages.mkdir(parents=True, exist_ok=True)
        for entry in wheel_dir.iterdir():
            _copy(entry, site_packages / entry.name)

        # 4. App source + migration tree + config, copied verbatim (no --add-data
        #    archaeology — the whole point of the embeddable choice).
        _copy(repo_root / "app", dest / "app")
        _copy(repo_root / "alembic", dest / "alembic")
        _copy(repo_root / "alembic.ini", dest / "alembic.ini")

        # 4b. Vendored read-only assets (e.g. minisign.pub) if the operator has
        #     placed them; optional on dev/CI.
        for asset in VENDORED_APP_ASSETS:
            src = repo_root / "app" / asset
            if src.exists():
                _copy(src, dest / asset)

        # 5. Launcher -> sibling of the swappable app\ (STABLE PID owner). Must
        #    live outside app\ or it would lock the rename target (Pitfall 3).
        launcher_src = repo_root / "launcher"
        if launcher_src.exists():
            _copy(launcher_src, dest.parent / "launcher")

        # 6. Pitfall 5 gate: every repo migration MUST be bundled, or
        #    `alembic upgrade head` no-ops on the operator box. Compare the
        #    bundled count against the repo count (currently 22, 0001-0022).
        repo_versions = _version_files(repo_root / "alembic" / "versions")
        bundled_versions = _version_files(dest / "alembic" / "versions")
        if not repo_versions:
            raise RuntimeError("no alembic migrations found in the repo — cannot build")
        if len(bundled_versions) != len(repo_versions):
            raise RuntimeError(
                "alembic migration count mismatch: bundled "
                f"{len(bundled_versions)} != repo {len(repo_versions)} — "
                "the onedir would ship an incomplete migration history (Pitfall 5)"
            )
    except Exception:
        # Delete-partial-on-failure (backup.py:45-47 idiom).
        shutil.rmtree(dest, ignore_errors=True)
        raise

    return dest


def _version_files(versions_dir: Path) -> list[Path]:
    """The numbered alembic migration modules (0001_.py ... 0022_.py)."""
    if not versions_dir.exists():
        return []
    return list(versions_dir.glob("[0-9]*.py"))


def _copy(src: Path, dst: Path) -> None:
    """Copy a file or directory tree verbatim (dirs merged, __pycache__ skipped)."""
    if src.is_dir():
        shutil.copytree(
            src,
            dst,
            dirs_exist_ok=True,
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
        )
    else:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)


# --- PKG-02: per-user Inno Setup installer script ---------------------------


def generate_iss(*, dist_dir: Path, version: str, dest: Path) -> Path:
    """Emit the per-user Inno Setup script MyOriShop.iss (RESEARCH Pattern 2).

    LOCKED directives: PrivilegesRequired=lowest (per-user, no admin/UAC),
    DefaultDirName={localappdata}\\MyOriShop, an {autoprograms} Start-Menu
    shortcut at the launcher, the auto-registered uninstaller
    (UninstallDisplayIcon), and AppVersion synced to __version__/the tag. Ships
    launcher\\ and app\\ but NOT data\\ — operator state is created on first run
    beside app\\ (PKG-03). [Files] Source paths are relative to the script dir
    (Inno's SourceDir default), so the .iss is generated INTO dist\\ and compiled
    with `iscc dist\\MyOriShop.iss` (Plan 05).
    """
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    iss = f"""; Generated by build_release.py — do NOT edit by hand (PKG-02).
; Per-user install under %LOCALAPPDATA%; shipped unsigned (documented SmartScreen step).
[Setup]
AppName=MyOriShop
AppVersion={version}
PrivilegesRequired=lowest
DefaultDirName={{localappdata}}\\MyOriShop
DisableProgramGroupPage=yes
UninstallDisplayIcon={{app}}\\launcher\\launcher.exe
OutputBaseFilename=MyOriShop-Setup-{version}

[Files]
; SourceDir defaults to this script's directory (dist\\), so paths are relative to it.
Source: "launcher\\*"; DestDir: "{{app}}\\launcher"; Flags: recursesubdirs
Source: "app\\*"; DestDir: "{{app}}\\app"; Flags: recursesubdirs
; NOTE: data\\ is NOT shipped — created on first run under {{app}}\\data (PKG-03).

[Icons]
Name: "{{autoprograms}}\\MyOriShop"; Filename: "{{app}}\\launcher\\launcher.exe"
"""
    dest.write_text(iss, encoding="utf-8")
    return dest


# --- PKG-05: manifest + SHA-256 + tag<->version contract --------------------

# V5 input validation: the release tag is an untrusted input. It must be exactly
# `v1.<N>` (integer-comparable trailing counter, MEMORY versioning-scheme) — the
# same shape as __version__ prefixed with 'v'. This feeds Phase 32 anti-downgrade.
_TAG_RE = re.compile(r"^v1\.\d+$")


def write_manifest(*, archive_path: Path, version: str, dest: Path) -> Path:
    """Bind version + archive filename + the archive's real SHA-256 into manifest.txt.

    One small signed blob (Phase 05 minisign signs THIS, not the multi-hundred-MB
    archive — RESEARCH "Why sign the manifest, not the archive") so Phase 32
    verifies one signature then checks the archive digest against it, with the
    version inside the signed payload (UPD-05 anti-downgrade). Also emits the
    sibling SHA256SUMS the CI release publishes.
    """
    archive_path = Path(archive_path)
    dest = Path(dest)
    sha = hashlib.sha256(archive_path.read_bytes()).hexdigest()
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(
        f"version={version}\narchive={archive_path.name}\nsha256={sha}\n",
        encoding="utf-8",
    )
    (dest.parent / "SHA256SUMS").write_text(
        f"{sha}  {archive_path.name}\n", encoding="utf-8"
    )
    return dest


def _parse_manifest(manifest_path: Path) -> dict[str, str]:
    """Parse the `key=value` lines of a manifest.txt into a dict."""
    fields: dict[str, str] = {}
    for raw in Path(manifest_path).read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or "=" not in line:
            continue
        key, _, value = line.partition("=")
        fields[key.strip()] = value.strip()
    return fields


def verify_manifest(archive_path: Path, manifest_path: Path) -> bool:
    """Re-hash <archive_path> and compare against the manifest's sha256 (T-31-03).

    Returns False on any mismatch (a single flipped archive byte) or a manifest
    missing its sha256 field — the tamper guard.
    """
    expected = _parse_manifest(manifest_path).get("sha256")
    if not expected:
        return False
    actual = hashlib.sha256(Path(archive_path).read_bytes()).hexdigest()
    return actual == expected


def _read_version(repo_root: Path | None = None) -> str:
    """Extract __version__ from app/__init__.py WITHOUT importing the app.

    Importing `app` would pull the whole FastAPI/SQLAlchemy dependency graph
    (and its site-packages); parsing the AST reads the single source of truth
    cheaply and side-effect-free (PATTERNS "Version single-source-of-truth").
    """
    root = Path(repo_root) if repo_root is not None else _REPO_ROOT
    source = (root / "app" / "__init__.py").read_text(encoding="utf-8")
    for node in ast.parse(source).body:
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == "__version__" for t in node.targets
        ):
            return ast.literal_eval(node.value)
    raise ValueError("__version__ not found in app/__init__.py")


def assert_tag_matches_version(tag: str, *, repo_root: Path | None = None) -> None:
    """Fail the build unless the git tag `v1.<N>` equals __version__ `1.<N>`.

    Validates the tag shape first (V5) then the equality — a malformed tag OR a
    tag/version drift raises ValueError, so CI cannot publish a release whose
    advertised version disagrees with the shipped code (RESEARCH Stage A).
    """
    if not _TAG_RE.match(tag):
        raise ValueError(
            f"malformed release tag {tag!r}: expected v1.<N> (regex ^v1\\.\\d+$)"
        )
    version = _read_version(repo_root)
    if tag[1:] != version:
        raise ValueError(
            f"release tag {tag!r} does not match app __version__ {version!r} — "
            "bump app/__init__.py or fix the tag before releasing"
        )


def _zip_onedir(dist_dir: Path, version: str) -> Path:
    """Zip the assembled app\\ + launcher\\ into dist/MyOriShop-<version>.zip."""
    dist_dir = Path(dist_dir)
    archive = dist_dir / f"MyOriShop-{version}.zip"
    tmp = archive.with_suffix(".zip.partial")
    try:
        with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zf:
            for sub in ("app", "launcher"):
                root = dist_dir / sub
                if not root.exists():
                    continue
                for path in sorted(root.rglob("*")):
                    if path.is_file():
                        zf.write(path, path.relative_to(dist_dir).as_posix())
        tmp.replace(archive)
    except Exception:
        tmp.unlink(missing_ok=True)
        raise
    return archive


def _build_cli(argv: list[str] | None = None) -> int:
    """CLI: `--version v1.<N>` builds the onedir; add `--manifest` for checksums.

    Both paths first assert the tag<->__version__ contract so a drifted release
    fails fast (RESEARCH Stage A). The heavy build fetches the embeddable +
    vendors wheels (Windows-native in CI); `--manifest` runs after the archive
    exists to emit SHA256SUMS + manifest.txt.
    """
    parser = argparse.ArgumentParser(description="MyOriShop Windows onedir build assembler")
    parser.add_argument(
        "--version", required=True, help="release tag, e.g. v1.42 (must equal __version__)"
    )
    parser.add_argument(
        "--manifest",
        action="store_true",
        help="write SHA256SUMS + manifest.txt over the already-built archive",
    )
    parser.add_argument(
        "--python-version",
        default="3.13.1",
        help="Python embeddable release to bundle (must be SHA-pinned in EMBEDDABLE_SHA256)",
    )
    args = parser.parse_args(argv)

    # tag<->version contract — fail the build on any drift (both paths).
    assert_tag_matches_version(args.version)
    version = args.version[1:]
    dist_dir = _REPO_ROOT / "dist"

    if args.manifest:
        archive = dist_dir / f"MyOriShop-{version}.zip"
        if not archive.exists():
            parser.error(f"archive {archive} not found — run the build (without --manifest) first")
        write_manifest(archive_path=archive, version=version, dest=dist_dir / "manifest.txt")
        return 0

    embed_zip = fetch_embeddable(args.python_version, _REPO_ROOT / ".build-cache")
    # Vendor into a staging dir FIRST — assemble_onedir wipes dest\, so the wheels
    # must live outside the bundle until it copies them into Lib\site-packages.
    wheel_staging = dist_dir / ".wheels"
    vendor_wheels(wheel_staging, repo_root=_REPO_ROOT)
    assemble_onedir(
        embeddable_zip=embed_zip,
        wheel_dir=wheel_staging,
        dest=dist_dir / "app",
        repo_root=_REPO_ROOT,
    )
    _zip_onedir(dist_dir, version)
    generate_iss(dist_dir=dist_dir, version=version, dest=dist_dir / "MyOriShop.iss")
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry
    raise SystemExit(_build_cli())

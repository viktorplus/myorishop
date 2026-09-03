"""Wave-0 RED validation scaffold for Phase 31 (Packaging & data separation).

Contract note (Nyquist Wave 0): the tests below are RED-by-design, mirroring
`tests/test_offline.py`'s convention. Their module-level imports touch ONLY
already-existing symbols; the not-yet-built `build_release` module (Plan 04) is
imported INSIDE each test body so collection stays green in Wave 0. The PKG-03
data-separation gate reloads `app.config` under a chosen `MYORISHOP_DATA_DIR` —
the seam is resolved at IMPORT time (RESEARCH Pattern 3), so it is only
observable through `importlib.reload`. Until Plan 02 roots every operator path at
that absolute data dir, the PKG-03 gates are RED; until Plan 04 builds
`build_release`, the PKG-01 onedir + PKG-02 `.iss` gates raise at call time
(never a collection ERROR).

Requirements pinned here: PKG-03 (DB/.env/secret_key/device_id/backups are
siblings of the swappable app dir, never children), PKG-01 (embeddable onedir
layout with a correct `python313._pth` + all 22 alembic migrations bundled),
PKG-02 (per-user Inno Setup `.iss` installer).
"""

import importlib
import zipfile
from pathlib import Path

import pytest

import app.config

_REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture()
def reload_config(monkeypatch):
    """Reload `app.config` under a chosen MYORISHOP_DATA_DIR, restore afterwards.

    RESEARCH Pattern 3: the data-dir root is resolved at IMPORT time, so the
    Plan-02 seam is only visible through `importlib.reload` with the env var
    already set. Until Plan 02 lands, the reload yields today's CWD-relative
    settings and these gates are RED by design.
    """

    # Snapshot the live `settings` object every other module (conftest fixtures,
    # app.db, app.main, app.sync_client) already holds a reference to. Reloading
    # app.config rebinds `app.config.settings` to a NEW object; consumers that read
    # it dynamically would then see the wrong (real ./data) config, poisoning
    # unrelated tests collected after this one. Restoring the original identity at
    # teardown keeps `app.config.settings` stable across the reload.
    _original_settings = app.config.settings

    def _reload(data_dir: Path):
        monkeypatch.setenv("MYORISHOP_DATA_DIR", str(data_dir))
        importlib.reload(app.config)
        return app.config.settings

    yield _reload
    # Restore the module to its unpatched state for the rest of the session.
    monkeypatch.delenv("MYORISHOP_DATA_DIR", raising=False)
    importlib.reload(app.config)
    app.config.settings = _original_settings


def _data_paths(settings) -> list[Path]:
    """Every operator-state path that MUST live in the sibling data dir (PKG-03)."""
    identity_dir = Path(settings.db_path).parent  # secret_key + device_id root here
    return [
        Path(settings.db_path).resolve(),
        Path(settings.backup_dir).resolve(),
        Path(settings.model_config["env_file"]).resolve(),
        (identity_dir / "secret_key").resolve(),
        (identity_dir / "device_id").resolve(),
    ]


def _fake_embeddable_zip(tmp_path: Path) -> Path:
    """A stand-in for the python-3.13-embed-amd64.zip the onedir assembler unpacks."""
    zip_path = tmp_path / "python-3.13-embed-amd64.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("python.exe", b"MZ fake exe")
        zf.writestr("python313.zip", b"fake stdlib")
        # The stock embeddable ._pth omits site-packages / import site — that is
        # exactly the gotcha the assembler must fix (RESEARCH Pattern 1).
        zf.writestr("python313._pth", "python313.zip\n.\n")
    return zip_path


def _fake_wheel_dir(tmp_path: Path) -> Path:
    """A stand-in vendored-wheels dir the assembler copies into Lib\\site-packages."""
    wheel_dir = tmp_path / "wheels"
    (wheel_dir / "fastapi").mkdir(parents=True)
    (wheel_dir / "fastapi" / "__init__.py").write_text("", encoding="utf-8")
    return wheel_dir


# --- PKG-03: data separation ------------------------------------------------


def test_data_paths_are_siblings(tmp_path, reload_config):
    """PKG-03: under MYORISHOP_DATA_DIR EVERY operator data path (db_path,
    backup_dir, the resolved env_file, secret_key/device_id) resolves UNDER the
    data dir and NONE under a simulated sibling app dir. RED until Plan 02 roots
    them at the absolute data dir (RESEARCH Pattern 3)."""
    data_dir = (tmp_path / "data").resolve()
    app_dir = (tmp_path / "app").resolve()
    settings = reload_config(data_dir)

    for path in _data_paths(settings):
        assert path == data_dir or path.is_relative_to(data_dir), (
            f"{path} escaped the data dir {data_dir}"
        )
        assert not path.is_relative_to(app_dir), (
            f"{path} landed under the swappable app dir {app_dir}"
        )


def test_backup_dir_is_absolute_not_cwd_relative(tmp_path, reload_config):
    """PKG-03 / RESEARCH Pitfall 2 — the single wipe-risk line. backup_dir MUST
    be absolute so it never lands inside the swappable app dir (CWD under
    packaging). RED until Plan 02 sets backup_dir = _DATA_DIR / 'backups'."""
    settings = reload_config((tmp_path / "data").resolve())
    assert Path(settings.backup_dir).is_absolute()


def test_swap_of_app_dir_cannot_reach_data(tmp_path, reload_config):
    """PKG-03 swap-safety invariant: with a sibling app/ + data/ install layout,
    every operator-data path lives UNDER data/ and NONE under app/ — so an
    os.replace() swap of app/ physically cannot touch operator state. RED until
    Plan 02 honors MYORISHOP_DATA_DIR."""
    install_root = tmp_path / "MyOriShop"
    app_dir = (install_root / "app").resolve()
    data_dir = (install_root / "data").resolve()
    app_dir.mkdir(parents=True)
    data_dir.mkdir(parents=True)

    settings = reload_config(data_dir)

    for path in _data_paths(settings):
        assert path.is_relative_to(data_dir), (
            f"{path} is not under the sibling data dir {data_dir}"
        )
        assert not path.is_relative_to(app_dir), (
            f"{path} is reachable from the swappable app dir {app_dir}"
        )


# --- PKG-01: embeddable onedir layout ---------------------------------------


def test_onedir_layout_has_pth_and_site_packages(tmp_path):
    """PKG-01: the assembled onedir ships a python313._pth that adds
    'Lib\\site-packages' and 'import site' — the #1 embeddable gotcha
    (RESEARCH Pattern 1 / Pitfall 1). Imports build_release INSIDE the body
    (module arrives Plan 04) so Wave-0 collection stays green."""
    import build_release  # noqa: PLC0415 — in-body import keeps collection green

    dist_app = build_release.assemble_onedir(
        embeddable_zip=_fake_embeddable_zip(tmp_path),
        wheel_dir=_fake_wheel_dir(tmp_path),
        dest=tmp_path / "dist" / "app",
        repo_root=_REPO_ROOT,
    )
    pth = (Path(dist_app) / "python313._pth").read_text(encoding="utf-8")
    assert "Lib\\site-packages" in pth
    assert "import site" in pth


def test_onedir_bundles_all_alembic_versions(tmp_path):
    """PKG-01 / RESEARCH Pitfall 5: every alembic/versions/*.py migration
    (currently 22, 0001-0022) MUST be bundled or 'alembic upgrade head' no-ops
    on the operator box. RED until Plan 04's assemble_onedir."""
    import build_release  # noqa: PLC0415

    dist_app = build_release.assemble_onedir(
        embeddable_zip=_fake_embeddable_zip(tmp_path),
        wheel_dir=_fake_wheel_dir(tmp_path),
        dest=tmp_path / "dist" / "app",
        repo_root=_REPO_ROOT,
    )
    repo_versions = list((_REPO_ROOT / "alembic" / "versions").glob("[0-9]*.py"))
    bundled = list((Path(dist_app) / "alembic" / "versions").glob("[0-9]*.py"))
    # The contract is "every repo migration is bundled", not a fixed count — a
    # hard-coded number turns each new migration into a false failure (it did,
    # when 0023 added warehouses.currency). The floor keeps the original guard
    # against an empty/na-glob directory silently passing.
    assert len(repo_versions) >= 22, "alembic/versions lost migrations"
    assert {p.name for p in bundled} == {p.name for p in repo_versions}


def test_launcher_runtime_is_bundled_outside_app(tmp_path):
    """PKG-02/PKG-04: the launcher ships its OWN embeddable runtime in a SIBLING
    ``launcher\\`` dir, never inside the swappable ``app\\``.

    The Start-Menu shortcut targets ``launcher\\python.exe``, so that file must
    actually exist in the shipped tree (31-UAT GAP-2). Its ``._pth`` is the
    launcher variant — ``python313.zip`` / ``.`` / ``..`` — because a ``._pth``
    puts the interpreter in isolated mode (cwd and PYTHONPATH are ignored), so
    only the ``..`` entry (the install root) makes the sibling ``launcher``
    package importable. ``Lib\\site-packages`` and ``app`` are deliberately
    absent: the launcher is stdlib-only and must not depend on the bundle it
    swaps."""
    import build_release  # noqa: PLC0415

    dist_app = build_release.assemble_onedir(
        embeddable_zip=_fake_embeddable_zip(tmp_path),
        wheel_dir=_fake_wheel_dir(tmp_path),
        dest=tmp_path / "dist" / "app",
        repo_root=_REPO_ROOT,
    )
    dist_launcher = Path(dist_app).parent / "launcher"

    assert (dist_launcher / "python.exe").exists(), (
        "the launcher has no runtime — the Start-Menu shortcut would target nothing"
    )

    pth_text = (dist_launcher / "python313._pth").read_text(encoding="utf-8")
    pth_lines = [line.strip() for line in pth_text.splitlines() if line.strip()]
    assert pth_lines == ["python313.zip", ".", ".."], (
        f"launcher ._pth must be exactly python313.zip / . / .. — got {pth_lines}"
    )
    assert "Lib\\site-packages" not in pth_text
    assert "\napp\n" not in "\n" + pth_text

    for module in ("__main__.py", "swap.py", "adapters.py"):
        assert (dist_launcher / module).exists(), f"launcher/{module} not shipped"

    assert not (Path(dist_app) / "launcher").exists(), (
        "the launcher landed INSIDE the swappable app dir — a running launcher "
        "there would leave app.prev undeletable after a successful update"
    )


# Skip-gated (same convention as the first-run gate below): every other assertion
# in this file runs against `_fake_embeddable_zip`, whose `python.exe` is 11 bytes
# of `MZ fake exe` and can execute nothing. Only a real local build produces a
# runtime that can prove the `..` search-path entry actually resolves.


@pytest.mark.skipif(
    not (_REPO_ROOT / "dist" / "launcher" / "python.exe").exists(),
    reason="needs the real assembled launcher runtime — build it with "
    "`uv run python build_release.py --version v1.<N>` (CI does not build it)",
)
def test_real_launcher_runtime_resolves_the_sibling_package(tmp_path):
    """PKG-02/PKG-04: the SHIPPED ``launcher\\python.exe`` can import the sibling
    ``launcher`` package from an unrelated working directory.

    That is the whole mechanism behind the Start-Menu shortcut
    (``launcher\\python.exe -m launcher``): isolated mode ignores the cwd, so the
    import can only succeed through the ``..`` line of the launcher's own
    ``._pth``. Imports the package rather than running ``-m launcher`` on
    purpose — the latter would start the app and open a browser window."""
    import subprocess  # noqa: PLC0415

    runtime = _REPO_ROOT / "dist" / "launcher" / "python.exe"
    result = subprocess.run(  # noqa: S603 — fixed argv, no shell
        [str(runtime), "-c", "import launcher; print(launcher.__file__)"],
        capture_output=True,
        text=True,
        cwd=str(tmp_path),
    )
    assert result.returncode == 0, (
        f"the shipped launcher runtime cannot import its sibling package: {result.stderr}"
    )
    printed = Path(result.stdout.strip()).resolve()
    assert printed == (_REPO_ROOT / "dist" / "launcher" / "__init__.py").resolve(), (
        f"imported the wrong launcher package: {printed}"
    )


def test_assemble_onedir_removes_both_halves_on_failure(tmp_path, monkeypatch):
    """WR-08: delete-partial-on-failure must cover the launcher it just built.

    ``assemble_launcher_runtime`` runs at step 5, inside the try, and the
    migration-count gate at step 6 — the most likely failure in this block —
    fires AFTER it. The handler only wiped ``dist\\app``, so a failed build left
    a fully assembled ``dist\\launcher\\`` behind and the documented invariant
    ("a half-written bundle is removed so it can never pass for a valid one")
    was false for the launcher half. A rerun of ``iscc dist\\MyOriShop.iss``
    against that residue packages a launcher with no app."""
    import build_release  # noqa: PLC0415

    dest = tmp_path / "dist" / "app"
    real_version_files = build_release._version_files

    def short_bundled_count(versions_dir):
        found = real_version_files(versions_dir)
        # Only the BUNDLED count comes up short — the step-6 gate's real shape.
        if Path(versions_dir).is_relative_to(dest):
            return found[:-1]
        return found

    monkeypatch.setattr(build_release, "_version_files", short_bundled_count)

    with pytest.raises(RuntimeError, match="migration count mismatch"):
        build_release.assemble_onedir(
            embeddable_zip=_fake_embeddable_zip(tmp_path),
            wheel_dir=_fake_wheel_dir(tmp_path),
            dest=dest,
            repo_root=_REPO_ROOT,
        )

    assert not dest.exists(), "the partial app bundle survived"
    assert not (dest.parent / "launcher").exists(), (
        "the launcher assembled at step 5 survived a step-6 failure — iscc would "
        "package it with no app"
    )


# --- PKG-01/PKG-04: the release archive IS the future app\ ------------------


def test_release_archive_extracts_into_a_runnable_app_dir(tmp_path):
    """CR-01: the published archive's ROOT must be what ``staged\\`` becomes.

    Drives the REAL shipping chain instead of a hand-built fixture:
    ``assemble_onedir`` -> ``_zip_onedir`` -> extract the archive verbatim into
    ``install_root\\staged`` (what Phase 32's ``update.apply`` does) ->
    ``apply_update`` (``os.replace(staged, app)``). The swapped ``app\\`` must
    then hold ``python.exe`` at its top level.

    Hand-building ``staged\\`` in the app-root shape — which every other launcher
    test does — is exactly why the two-top-level-dir archive shipped undetected:
    the real zip carried ``app/`` and ``launcher/`` members, so the swap produced
    ``app\\app\\python.exe`` and no self-update could ever succeed."""
    import build_release  # noqa: PLC0415

    from launcher.swap import Paths, Pending, apply_update  # noqa: PLC0415

    dist_dir = tmp_path / "dist"
    build_release.assemble_onedir(
        embeddable_zip=_fake_embeddable_zip(tmp_path),
        wheel_dir=_fake_wheel_dir(tmp_path),
        dest=dist_dir / "app",
        repo_root=_REPO_ROOT,
    )
    archive = build_release._zip_onedir(dist_dir, "1.42")

    names = zipfile.ZipFile(archive).namelist()
    assert "python.exe" in names, (
        "the archive root is not the app dir — the swap renames staged\\ ONTO "
        f"app\\, so python.exe must be a top-level member; got {names[:5]}"
    )
    assert not any(n.startswith("launcher/") for n in names), (
        "launcher\\ is installer-only payload; a launcher/ member lands at "
        "app\\launcher\\ after the swap"
    )

    # Phase 32's update.apply: extract the archive VERBATIM into staged\.
    install_root = tmp_path / "MyOriShop"
    staged = install_root / "staged"
    app_dir = install_root / "app"
    data = install_root / "data"
    for directory in (app_dir, data):
        directory.mkdir(parents=True)
    (app_dir / "python.exe").write_bytes(b"MZ old exe")
    backup = data / "backup.db"
    backup.write_text("BACKUP", encoding="utf-8")
    staged.mkdir(parents=True)
    zipfile.ZipFile(archive).extractall(staged)

    apply_update(
        Paths(
            app=app_dir,
            app_prev=install_root / "app.prev",
            staged=staged,
            app_failed=install_root / "app.failed",
            install_root=install_root,
            data=data,
        ),
        Pending(staged_dir=staged, expected_version="1.42", db_backup_path=backup),
        stop_app=lambda: None,
        start_app=lambda: None,
        migrate=lambda: None,
        health_ok=lambda: True,
        backup_restore=lambda _path: None,
    )

    assert (app_dir / "python.exe").exists(), (
        "the swapped app\\ has no top-level python.exe — adapters.migrate and "
        "AppProcess.start both resolve app\\python.exe and would raise "
        "FileNotFoundError, so every self-update rolls back"
    )
    # app\app\ IS the FastAPI package (app\app\main.py) — but a nested RUNTIME
    # there is the CR-01 signature: it means the archive carried an app/ prefix.
    assert not (app_dir / "app" / "python.exe").exists(), (
        "the archive nested a second runtime at app\\app\\python.exe — its root "
        "carried an app/ prefix instead of BEING the app dir"
    )
    assert (app_dir / "app" / "main.py").exists(), "the app package is not swapped in"
    assert (app_dir / "alembic" / "versions").is_dir(), "the migration tree is not swapped in"


# --- PKG-02: per-user Inno Setup installer ----------------------------------


def test_generate_iss_is_per_user_with_shortcut_and_uninstaller(tmp_path):
    """PKG-02: generate_iss emits a per-user Inno Setup script —
    PrivilegesRequired=lowest, DefaultDirName={localappdata}\\MyOriShop, a
    {autoprograms} Start-Menu shortcut at the launcher, an uninstaller icon,
    AppVersion pinned to the tag, and NO data\\ source line (PKG-03: data is not
    shipped, created on first run). RED until Plan 04. Imports build_release
    INSIDE the body."""
    import build_release  # noqa: PLC0415

    dist_dir = tmp_path / "dist"
    (dist_dir / "app").mkdir(parents=True)
    (dist_dir / "launcher").mkdir(parents=True)

    # dest MUST be inside dist_dir — [Files] Source paths are relative to the
    # script's own directory, so a mismatch points the installer at the wrong
    # tree (this call used to pass tmp_path/MyOriShop.iss and still succeed).
    iss = build_release.generate_iss(
        dist_dir=dist_dir, version="1.42", dest=dist_dir / "MyOriShop.iss"
    )
    text = Path(iss).read_text(encoding="utf-8")

    assert "PrivilegesRequired=lowest" in text
    assert r"DefaultDirName={localappdata}\MyOriShop" in text
    assert "{autoprograms}" in text
    assert "launcher" in text.lower()
    assert "UninstallDisplayIcon" in text
    assert "AppVersion=1.42" in text

    source_lines = [
        line for line in text.splitlines() if line.strip().startswith("Source:")
    ]
    assert source_lines, "installer must ship at least the app and launcher"
    assert not any("data\\" in line for line in source_lines), (
        "data\\ must NOT be shipped by the installer (PKG-03)"
    )


def test_iss_pins_appid_ignoreversion_and_sweeps_swap_residue(tmp_path):
    """WR-09: three under-specifications in a script whose job is a correct install.

    1. No ``[UninstallDelete]``: Inno removes only what it installed, so an
       uninstall left ``app.prev\\``, ``app.failed\\`` and ``staged\\`` behind —
       each a full ~30 MB bundle copy, and ``app.failed\\`` is retained by design
       until the NEXT rollback rotates it, i.e. forever on a healthy install.
       ``data\\`` must NOT be swept: it is the operator's DB and backups.
    2. No ``AppId``: Inno falls back to ``AppName``, so any future rename creates
       a SECOND uninstall entry instead of upgrading in place.
    3. No ``ignoreversion``: Inno's default skips replacing a file whose installed
       copy has an equal-or-higher version resource, so a repair/reinstall over an
       install whose ``app\\`` had already self-updated could keep stale binaries."""
    import build_release  # noqa: PLC0415

    dist_dir = tmp_path / "dist"
    dist_dir.mkdir()
    text = Path(
        build_release.generate_iss(
            dist_dir=dist_dir, version="1.42", dest=dist_dir / "MyOriShop.iss"
        )
    ).read_text(encoding="utf-8")

    # Inno escapes a literal '{' as '{{', so the emitted line is `AppId={{GUID}`.
    assert "AppId={{1BF2D689-291E-4E44-B502-BC4EAEBE4C32}\n" in text, (
        "AppId is missing or not Inno-escaped as {{GUID}"
    )

    source_lines = [line for line in text.splitlines() if line.startswith("Source:")]
    assert source_lines, "the installer ships nothing"
    for line in source_lines:
        assert "ignoreversion" in line, f"[Files] entry without ignoreversion: {line}"

    assert "[UninstallDelete]" in text
    swept = [
        line.split('Name:')[1].strip().strip('"')
        for line in text.splitlines()
        if line.startswith("Type: ")
    ]
    assert swept == [r"{app}\app.prev", r"{app}\app.failed", r"{app}\staged"], (
        f"the uninstaller sweeps the wrong set of paths: {swept}"
    )
    assert not any("data" in path for path in swept), (
        "the uninstaller would delete the operator's DB, backups and identity"
    )


def test_generate_iss_refuses_a_dest_outside_dist_dir(tmp_path):
    """WR-07: ``dist_dir`` is authoritative, not a dead parameter.

    ``generate_iss`` never referenced ``dist_dir``: the emitted ``[Files]
    Source:`` paths are relative to the .iss file's OWN directory (Inno's
    ``SourceDir`` default), so correctness silently depended on
    ``dest.parent == dist_dir``. A mismatched pair produced a normal-looking
    script pointing at a tree that need not even exist — and the unit test above
    passed exactly such a pair, which is how the dead parameter survived."""
    import build_release  # noqa: PLC0415

    dist_dir = tmp_path / "dist"
    dist_dir.mkdir()

    with pytest.raises(ValueError, match="generated INTO dist_dir"):
        build_release.generate_iss(
            dist_dir=dist_dir, version="1.42", dest=tmp_path / "MyOriShop.iss"
        )
    assert not (tmp_path / "MyOriShop.iss").exists(), "a misplaced .iss was written anyway"

    with pytest.raises(ValueError, match="generated INTO dist_dir"):
        build_release.generate_iss(
            dist_dir=tmp_path / "nowhere", version="1.42", dest=dist_dir / "MyOriShop.iss"
        )


def test_iss_referenced_paths_exist_in_dist(tmp_path):
    """PKG-02 / T-31-08: EVERY path the generated .iss names must exist in the
    assembled dist — the [Files] Source patterns (relative to the script dir),
    the [Icons] Filename targets and UninstallDisplayIcon.

    31-UAT GAP-2: the shortcut pointed at ``{app}\\launcher\\launcher.exe``,
    which nothing ever built. Besides being a dead shortcut, a missing target
    inside a user-writable per-user install root is a plant-and-hijack surface —
    whoever can create that file owns the operator's click."""
    import build_release  # noqa: PLC0415

    dist_app = build_release.assemble_onedir(
        embeddable_zip=_fake_embeddable_zip(tmp_path),
        wheel_dir=_fake_wheel_dir(tmp_path),
        dest=tmp_path / "dist" / "app",
        repo_root=_REPO_ROOT,
    )
    dist_dir = Path(dist_app).parent
    iss = build_release.generate_iss(
        dist_dir=dist_dir, version="1.42", dest=dist_dir / "MyOriShop.iss"
    )
    text = Path(iss).read_text(encoding="utf-8")

    assert "launcher.exe" not in text, (
        "the .iss still promises a launcher.exe stub that nothing builds"
    )
    assert 'Parameters: "-m launcher"' in text, (
        "the shortcut target is an interpreter — without -m launcher it opens a REPL"
    )
    # Inno reads ONE [Icons] entry per line: a wrapped entry would silently drop
    # Parameters/WorkingDir (the source uses a backslash line-continuation).
    icon_lines = [line for line in text.splitlines() if line.startswith("Name: ")]
    assert len(icon_lines) == 1 and icon_lines[0].endswith('WorkingDir: "{app}"'), (
        f"the [Icons] entry must be a single line — got {icon_lines}"
    )

    def _under_app(value: str) -> Path:
        assert value.startswith("{app}\\"), f"unexpected non-{{app}} target {value!r}"
        return dist_dir.joinpath(*value[len("{app}\\") :].split("\\"))

    referenced: list[Path] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith(";"):
            continue
        if line.startswith("Source:"):
            pattern = line.split(";")[0].partition(":")[2].strip().strip('"')
            matches = list(dist_dir.glob(pattern.replace("\\", "/")))
            assert matches, f"[Files] Source {pattern!r} matches nothing under {dist_dir}"
            referenced.extend(matches)
        elif line.startswith("UninstallDisplayIcon="):
            referenced.append(_under_app(line.partition("=")[2].strip()))
        elif line.startswith("Name:") and "Filename:" in line:
            referenced.append(
                _under_app(line.split("Filename:")[1].split(";")[0].strip().strip('"'))
            )

    assert len(referenced) >= 3, "parsed nothing to check — the .iss shape changed"
    for path in referenced:
        assert path.exists(), f"the .iss references {path}, which the build does not ship"


# --- PKG-01: first run of the REAL assembled dist ---------------------------

# Skip-gated (same convention as the minisign / vendored-pubkey gates in
# tests/test_release_verify.py): this test needs a real ~27 MB assembled onedir
# with a bundled python.exe, which CI never builds — only a local
# `uv run python build_release.py --version v1.<N>` produces it.


@pytest.mark.skipif(
    not (_REPO_ROOT / "dist" / "app" / "python.exe").exists(),
    reason="needs the real assembled onedir — build it with "
    "`uv run python build_release.py --version v1.<N>` (CI does not build it)",
)
def test_assembled_dist_boots_against_empty_data_dir(tmp_path, monkeypatch):
    """PKG-01 first-run gate: the REAL bundled runtime, booted through the
    launcher against an EMPTY data dir, must serve ``GET /`` with a non-500
    status.

    This automates the 31-UAT reproduction: the built distribution answered
    ``/health`` 200 but every page 500 (``no such table: users``) because nothing
    on the first-run path ran ``alembic upgrade head``. Only ``boot()``'s
    migrate-then-start makes it green — a launcher that merely starts the app
    fails here exactly as the operator's install did.
    """
    import http.client  # noqa: PLC0415
    import socket  # noqa: PLC0415
    import time  # noqa: PLC0415

    from launcher import __main__ as launcher_main  # noqa: PLC0415
    from launcher import adapters  # noqa: PLC0415
    from launcher.swap import Paths  # noqa: PLC0415

    # A FREE ephemeral port — never 8000, where the operator's own instance runs.
    # AppProcess.start() reads adapters._PORT at call time, so patching the module
    # attribute retargets the child process.
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    assert port != 8000
    monkeypatch.setattr(adapters, "_PORT", port)

    dist = _REPO_ROOT / "dist"
    data = tmp_path / "data"  # deliberately EMPTY: the migration must create the DB
    paths = Paths(
        app=dist / "app",
        app_prev=dist / "app.prev",
        staged=dist / "staged",
        app_failed=dist / "app.failed",
        install_root=dist,
        data=data,
    )

    proc = adapters.AppProcess(paths)
    launcher_main.boot(paths, proc)
    try:
        # A LOCAL poll helper on purpose: adapters.health_ok treats ANY status —
        # including the 500 this test exists to catch — as "alive".
        status = None
        deadline = time.monotonic() + 60.0
        while time.monotonic() < deadline:
            conn = http.client.HTTPConnection("127.0.0.1", port, timeout=2.0)
            try:
                conn.request("GET", "/")
                response = conn.getresponse()
                response.read()
                status = response.status
                break
            except (OSError, http.client.HTTPException):
                pass
            finally:
                conn.close()
            time.sleep(0.5)

        returncode = proc.proc.returncode if proc.proc is not None else "no child"
        assert status is not None, (
            f"the bundled app never answered on 127.0.0.1:{port} "
            f"(child returncode={returncode})"
        )
        assert status != 500, "fresh install serves 500 — the schema was never migrated"
        assert status in (200, 302, 303, 307), f"unexpected first-run status {status}"
    finally:
        proc.stop()

    assert (data / "myorishop.db").exists(), "the boot migration created no DB"

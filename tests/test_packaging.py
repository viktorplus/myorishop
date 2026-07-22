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
    assert len(repo_versions) == 22, "repo migration count drifted from 22"
    assert len(bundled) == len(repo_versions)


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

    iss = build_release.generate_iss(
        dist_dir=dist_dir, version="1.42", dest=tmp_path / "MyOriShop.iss"
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

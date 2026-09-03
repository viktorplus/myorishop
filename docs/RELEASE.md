# MyOriShop — Release Runbook (PKG-05, PKG-02)

This is the operator runbook for cutting a signed MyOriShop release. It reconciles
two hard constraints:

- The release **pipeline** publishes an Ed25519 signature (PKG-05), **but**
- The signing **secret key is OFFLINE** and must never enter GitHub Actions
  (threat **T-31-02** — signing-key exfiltration).

The resolution is a **two-stage flow**: CI builds and **drafts** everything; a
human on the offline machine **signs `manifest.txt`** and **publishes**. The
secret key never becomes a repo/CI secret.

> Why sign `manifest.txt`, not the archive? The manifest binds `version` +
> archive filename + the archive's SHA-256 into one small signed blob. Phase 32's
> self-update verifies **one** tiny signature, then checks the (large) archive's
> SHA-256 against the signed manifest — fast, no mix-and-match, and the version
> is inside the signed payload (feeds UPD-05 anti-downgrade).

---

## Section 1 — One-time, OFFLINE (HUMAN): generate the signing keypair

Do this **once**, on a machine that is **not** the CI runner and ideally kept
offline. It produces the Ed25519 keypair minisign uses.

```bash
# On the OFFLINE machine only:
minisign -G
# => minisign.pub  (public key — SAFE to commit)
# => minisign.key  (SECRET key — NEVER commit, NEVER a repo/CI secret)
```

Then:

1. **Store `minisign.key` OFFLINE**, outside this repository (e.g. an encrypted
   USB drive or a password manager). It must never be committed and never
   uploaded to GitHub Actions secrets (T-31-02). `.gitignore` blocks the
   `*.key` / `minisign.key` filenames so it can never be committed by accident.
2. **Commit ONLY the public key** to the client at `app/minisign.pub`:

   ```bash
   cp minisign.pub app/minisign.pub
   git add app/minisign.pub
   git commit -m "chore(31-05): vendor operator minisign public key"
   ```

   The public key is a vendored-offline asset, exactly like
   `app/static/htmx.min.js` — read-only inside `app\`, verified by Phase 32.
   Its base64 key line begins with `RW` (the minisign public-key marker).

> **This is a HUMAN step.** The automated build/CI never generates the production
> keypair and never writes `app/minisign.pub`. minisign is not installed on the
> dev box or in CI by default, and the secret key lives only on the offline
> machine.

Once `app/minisign.pub` is present, the vendored-pubkey acceptance test
(`tests/test_release_verify.py::test_vendored_pubkey_present_and_bundled`) stops
skipping and runs green (asserts `RW` + bundled), and `build_release` copies the
key into the onedir automatically (`VENDORED_APP_ASSETS`).

---

## Section 2 — Per release: build (CI) → sign (offline) → publish (human)

### 2a. Bump the version and push the tag (Stage A — CI)

The tag and `app/__init__.py __version__` **must** match, or the build fails the
`assert_tag_matches_version` contract.

```bash
# 1. Bump app/__init__.py __version__ to the new "1.<N>" (e.g. 1.42).
# 2. Commit, then push a matching tag:
git tag v1.42
git push origin v1.42
```

> **The launcher is NOT self-updating — a launcher change means "re-install".**
> The in-app update swaps `app\` only; `launcher\` is written exclusively by the
> installer. So a fix in `launcher/swap.py`, `launcher/adapters.py` or
> `launcher/__main__.py` reaches operators ONLY through a new
> `MyOriShop-Setup-1.<N>.exe` run — never through the self-update. Check
> `git log -- launcher/` before writing the release notes and, if anything there
> changed, say in the notes that this release requires running the installer.
>
> For the same reason `dist\MyOriShop-1.<N>.zip` contains the contents of
> `dist\app` at its ROOT and no `launcher/` member: the launcher renames the
> extracted `staged\` directly onto `app\`, so every member of that archive lands
> inside the operator's `app\`.

`.github/workflows/release.yml` runs on the `v1.*` tag and, on a Windows runner:

- builds the onedir (`dist\app` + `dist\launcher` + `dist\MyOriShop-1.42.zip`,
  the zip carrying `dist\app`'s contents at its root),
- compiles the per-user installer (`dist\MyOriShop-Setup-1.42.exe`) with Inno Setup,
- writes `dist\SHA256SUMS` + `dist\manifest.txt`,
- creates a **DRAFT** GitHub Release with those four assets.

The workflow uses **no repo secrets** and cannot sign — that is deliberate.

> Dry run: you can trigger the same workflow via **Actions → release →
> Run workflow** and pass a `version` input (e.g. `v1.42`) without pushing a tag.

### 2b. Sign the manifest (Stage B — OFFLINE human)

On the **offline machine** (the one holding `minisign.key`):

```bash
# 1. Download manifest.txt from the DRAFT release.
# 2. Sign it (the trusted comment is part of the signed data):
minisign -S -m manifest.txt -t "MyOriShop 1.42"
# => manifest.txt.minisig
```

Verify your own signature before uploading (sanity check):

```bash
minisign -Vm manifest.txt -p minisign.pub
```

### 2c. Attach and publish (human)

1. Upload `manifest.txt.minisig` to the **draft** release.
2. Click **Publish release**.

The secret key never left the offline machine and never appears in any repo or CI
log (T-31-02). The published `.minisig` over `manifest.txt` binds version +
archive SHA-256 — the tamper gate (**T-31-03**) Phase 32's self-update verifies
against `app/minisign.pub` before unpacking.

---

## Section 3 — Operator: the one-time SmartScreen step (PKG-02, RU)

Установщик `MyOriShop-Setup-1.<N>.exe` распространяется **без сертификата
подписи кода** (сертификат отложён — PKG-02). При первом запуске Windows
SmartScreen покажет предупреждение «Windows защитила ваш компьютер».

Один раз выполните следующее:

1. Нажмите **«Подробнее»** (More info).
2. Нажмите **«Выполнить в любом случае»** (Run anyway).

Это ожидаемое поведение для неподписанного установщика (угроза **T-31-01**,
принята). AV-поверхность намеренно минимизирована: приложение использует
официальную встраиваемую сборку Python (onedir), а не самораспаковывающийся
PyInstaller-exe. Сертификат подписи кода планируется добавить позже.

---

## Threats addressed

| Threat   | Where |
|----------|-------|
| T-31-02  | Secret key stays offline (Sections 1 & 2b); `.gitignore` blocks `*.key`; never a repo/CI secret |
| T-31-03  | Signed `manifest.txt` binds version + archive SHA-256; verified before unpack (Phase 32) |
| T-31-01  | Documented one-time RU SmartScreen «Выполнить в любом случае» (Section 3); cert deferred |

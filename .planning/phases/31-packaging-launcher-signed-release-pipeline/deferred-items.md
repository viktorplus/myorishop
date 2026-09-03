# Deferred Items — Phase 31

Out-of-scope discoveries logged during execution. NOT fixed by the plan that found them.

## Pre-existing ruff findings in tests/test_launcher.py

**Found during:** Plan 31-06, Task 1 (`uv run ruff check launcher tests`)
**Owner:** whoever next touches `tests/test_launcher.py` in refactor mode
**Status:** deferred (pre-existing, authored by Plan 31-01's Wave-0 scaffold)

`uv run ruff check tests/test_launcher.py` reports 3 errors, all on pre-existing lines:

| Rule | Line | Detail |
|------|------|--------|
| `B017` | 196 | `with pytest.raises(Exception):` — blind exception assert in `test_apply_update_rolls_back_on_failed_health_check` |
| `E501` | 251 | line too long (113 > 100) in the `parse_pending` traversal payload table |
| `UP031` | 432 | percent-format `('{"version": "%s"}' % version_payload)` in the `http.server` stub |

The lines Plan 31-06 added are clean (`ruff check launcher tests/test_packaging.py app/__init__.py` → `All checks passed!`). Fixing these three would touch code unrelated to the GAP-1 boot-migration change, so they were left alone per the executor scope boundary.

## The launcher cannot be updated in the field (WR-11)

**Found during:** `/gsd-code-review 31` (WR-11), documented by `/gsd-code-review --fix`
**Owner:** roadmap — needs a milestone decision, not a bug fix
**Status:** deferred (constraint documented in code + `docs/RELEASE.md`; no roadmap item written)

By design the swap replaces `app\` and never touches `launcher\`, and the `.iss`
is the only thing that ever writes `launcher\`. So a bug in `launcher/swap.py`,
`launcher/adapters.py` or `launcher/__main__.py` is **permanent for every
installed copy** — the only remedy is a full re-install of the setup exe. That is
exactly the situation this phase was in: three launcher blockers, all of which
would have been unshippable to an existing install.

Written down (this review-fix): `launcher/__init__.py`'s module docstring and a
`docs/RELEASE.md` callout telling the release author to check `git log --
launcher/` and mark the release re-install-required.

**Still open:** whether to make the launcher updatable at all. The design change
is to teach `apply_update` a two-subdir staged shape (`staged\app` → `app\`,
`staged\launcher` → a launcher swap performed on the NEXT boot, since the running
launcher cannot replace its own image). That is a milestone-level decision and
was deliberately NOT taken inside a bug fix. A roadmap item was not written
because roadmap edits belong to the planning workflow, not the code fixer.

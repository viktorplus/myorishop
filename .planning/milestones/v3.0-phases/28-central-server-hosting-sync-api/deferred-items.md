# Deferred Items — Phase 28

Out-of-scope discoveries logged during execution (SCOPE BOUNDARY rule). Not fixed
because they are pre-existing and unrelated to the current task's changes.

## Pre-existing ruff E501 (line-too-long) violations

Discovered during Plan 28-03 (verification step `uv run ruff check app` expected
exit 0, but these three lines already exceed the 100-char limit at HEAD, before
any 28-03 change — confirmed by stashing the working tree and re-running ruff):

- `app/routes/dictionary.py:73` — E501 line too long (>100)
- `app/routes/products.py:133` — E501 line too long (>100)
- `app/routes/transfers.py:64` — E501 line too long (>100)

These are in routers untouched by Plan 28-03. Fixing them is a mechanical
line-wrap but is out of scope for the sync-API plan. Address in a dedicated
lint-cleanup task or when next editing those files.

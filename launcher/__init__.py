"""MyOriShop stable launcher package (PKG-04).

A stdlib-only process that lives OUTSIDE the swappable ``app\\`` directory. It
owns the app's child process directly and, on a valid ``data\\pending.json``
marker, performs the transactional stop -> swap -> ``alembic upgrade head`` ->
restart with a matched-pair (code + pre-update DB) rollback on any failure.

The launcher must import NO ``app.*`` code — importing the app would load
modules from inside ``app\\`` and lock the very directory the swap renames
(RESEARCH Pitfall 3, WinError 32).
"""

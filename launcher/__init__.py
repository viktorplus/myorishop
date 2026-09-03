"""MyOriShop stable launcher package (PKG-04).

A stdlib-only process that lives OUTSIDE the swappable ``app\\`` directory. It
owns the app's child process directly and, on a valid ``data\\pending.json``
marker, performs the transactional stop -> swap -> ``alembic upgrade head`` ->
restart with a matched-pair (code + pre-update DB) rollback on any failure.

The launcher must import NO ``app.*`` code — importing the app would load
modules from inside ``app\\`` and lock the very directory the swap renames
(RESEARCH Pitfall 3, WinError 32).

THE LAUNCHER IS NOT SELF-UPDATING. The swap replaces ``app\\`` only, and the
``.iss`` installer is the only thing that ever writes ``launcher\\``. A bug in
``swap.py``, ``adapters.py`` or ``__main__.py`` is therefore PERMANENT for every
installed copy until the operator runs a new setup exe — treat every change in
this package as a re-install-required change and say so in the release notes.
This is why ``build_release._zip_onedir`` excludes ``launcher\\`` from the
release archive: shipping a copy nothing ever applies only reads as if updates
covered it.
"""

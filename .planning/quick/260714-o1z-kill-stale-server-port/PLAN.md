---
quick_id: 260714-o1z
slug: kill-stale-server-port
date: 2026-07-14
---

Fix run.bat so a stale uvicorn process left listening on 127.0.0.1:8000 from a
previous run cannot silently keep serving old code after new commits/pulls.

## Problem

run.bat has no --reload and does not stop any process already bound to port
8000 before starting a new uvicorn. If an old run.bat window was left open
(or the process detached from its console), a fresh run.bat launch fails to
bind (or a stray old process keeps answering on 127.0.0.1:8000), so the
operator keeps hitting stale code — observed as /dictionary returning 500 on
code that works fine when tested directly.

## Fix

In run.bat, before `uv run alembic upgrade head`, detect any PID with a
LISTENING socket on 127.0.0.1:8000 via `netstat -ano` and, if found,
`taskkill /F /PID` it with a console message. Windows batch only (project is
Windows-only per CLAUDE.md tech stack).

## Task

1. Edit run.bat: add a stale-process-kill step for port 8000 before the
   alembic migration step.

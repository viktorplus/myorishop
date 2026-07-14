---
quick_id: 260714-o1z
slug: kill-stale-server-port
status: complete
---

## What happened

`/dictionary` was returning 500. Root cause: `run.bat` has no `--reload` and
never stops a previously running server, so a stale uvicorn process from an
earlier `run.bat` launch (started before the latest commits) kept answering
on 127.0.0.1:8000 while the checked-out code had already moved on.
`TestClient` against the current code returned 200, confirming the app code
was fine and the problem was the stale process.

## Fix

`run.bat` now finds any PID with a LISTENING socket on 127.0.0.1:8000 via
`netstat -ano | findstr ... | findstr LISTENING` and `taskkill /F /PID`s it
before running Alembic migrations and starting the new uvicorn instance.

First attempt used `echo Stopping stale server on port 8000 (PID %%P)...`
inside the `for /f ... do ( ... )` block — the literal parentheses in the
echo text broke cmd.exe's batch parser ("was unexpected at this time").
Fixed by rewording the message to avoid parentheses.

## Verified

- Killed the running stale server manually, ran `run.bat` — new server came
  up, `/dictionary` returned 200.
- Started a server, then ran `run.bat` again with a live process already on
  port 8000 — console printed `Stopping stale server on port 8000, PID
  55448 ...`, old process was killed, new uvicorn bound cleanly, `/dictionary`
  returned 200.

## Changed files

- `run.bat`

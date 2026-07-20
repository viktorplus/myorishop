#!/bin/sh
# Container entrypoint: run migrations to head, then start the ASGI server.
#
# Same contract as run.bat / the systemd ExecStartPre: a failed migration MUST
# abort startup (set -e) — better to not come up than to serve on a half-migrated
# schema. Binds 0.0.0.0 so the shared host Caddy can reach it over the docker
# network; the port is never published to the host (see docker-compose.prod.yml).
set -e

uv run alembic upgrade head

exec uv run uvicorn app.main:app --host 0.0.0.0 --port 8000

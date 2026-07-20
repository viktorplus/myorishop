# MyOriShop — production image for the shared s1 server (Docker + shared Caddy).
#
# Mirrors the local run.bat workflow (uv + `alembic upgrade head` then uvicorn),
# but binds 0.0.0.0 INSIDE the container only — no host port is published; the
# shared host Caddy reaches this container by name over wgdashboard_default
# (`reverse_proxy ori-app:8000`). See docker-compose.prod.yml.
FROM python:3.13-slim

# uv from the official distroless image (same tool as local dev).
COPY --from=ghcr.io/astral-sh/uv:0.11.28 /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Dependency layer first (cached until the lockfile changes). No project code
# yet, so --no-install-project; --no-dev keeps pytest/ruff out of the image.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# Application code (data/ and backups/ are .dockerignore'd — never baked in).
COPY . .
RUN uv sync --frozen --no-dev

# data/ persists the per-install device_id / secret_key fallback files
# (app/config.py) and backups/ is created by the backup service; make both
# writable by a non-root user. A named volume mounts over data/ at runtime.
RUN mkdir -p data backups catalogs \
    && useradd --system --create-home --uid 10001 appuser \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

# Fail-closed migrations then serve (see deploy/docker-entrypoint.sh).
ENTRYPOINT ["/app/deploy/docker-entrypoint.sh"]

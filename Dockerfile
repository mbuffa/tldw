# syntax=docker/dockerfile:1
# Multi-stage build: uv installs deps in builder, slim runtime image carries only .venv + app code.
#
# pyproject.toml sets `package = false`, so we do a deps-only install (no project install step).

FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim AS builder

WORKDIR /app

# Compile bytecode and use copy mode so the venv is self-contained
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

# Install deps from lockfile — no project install needed (package = false)
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project --no-dev


# --- Runtime image ---
FROM python:3.13-slim-bookworm

WORKDIR /app

# Non-root user + persistent data dir for SQLite
RUN useradd -m app && mkdir -p /data && chown app:app /data

# Bring in the pre-built venv
COPY --from=builder /app/.venv /app/.venv

# App source (includes templates at app/templates/)
COPY app ./app

# Alembic migration files (init_db() needs these to apply schema changes on startup)
COPY alembic.ini alembic.ini
COPY alembic ./alembic

ENV PATH="/app/.venv/bin:$PATH" \
    DATABASE_URL="sqlite:////data/tldw.db"

USER app

EXPOSE 8000

# Drop --reload from run.sh; that's dev-only
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

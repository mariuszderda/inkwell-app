FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS builder

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app

# Install dependencies first for better layer caching
COPY app/pyproject.toml app/uv.lock ./
RUN uv sync --frozen --no-install-project --no-dev

# Copy application source
COPY app/ ./

# Collect static files at biuld time
WORKDIR /app/my_medium
RUN DATABASE_URL="" REDIS_URL="" /app/.venv/bin/python manage.py collectstatic --no-input

FROM python:3.12-slim-bookworm AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH"

RUN groupadd --system --gid 10001 appgroup && \
    useradd --system --uid 10001 --gid appgroup --home-dir /app --no-create-home appuser

WORKDIR /app/my_medium

COPY --from=builder --chown=appuser:appgroup /app /app

USER appuser

EXPOSE 8000

CMD ["gunicorn", "my_medium.wsgi:application", "--bind", "0.0.0.0:8000", "--access-logfile", "-", "--error-logfile", "-"]

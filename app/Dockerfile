# syntax=docker/dockerfile:1

FROM python:3.12-slim-bookworm@sha256:4766d8b510c428e595d74b9cc5bbb2fae8e26316fffb4adc89908d79aacd58a2 AS base
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

FROM base AS builder
COPY --from=ghcr.io/astral-sh/uv:0.12.3@sha256:2d890623d310b57771ce840f0da5eed5fc6d657da05ffaa45d82797b53fa3abc /uv /bin/uv
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never
WORKDIR /app

# Install dependencies against the lockfile before the source is present, so
# this layer is reused whenever only application code changes.
COPY app/pyproject.toml app/uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project

COPY app/ ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

FROM base AS runtime
# Fixed, non-zero UID so the runtime user is stable across rebuilds and matches
# the Kubernetes securityContext later.
RUN useradd --system --uid 10001 --create-home --home-dir /home/app app
WORKDIR /app
COPY --from=builder --chown=10001:10001 /app /app
ENV PATH="/app/.venv/bin:${PATH}"

ARG VERSION=0.0.0-dev
ARG GIT_SHA=unknown
ARG BUILT_AT=unknown
ENV VERSION=${VERSION} \
    GIT_SHA=${GIT_SHA} \
    BUILT_AT=${BUILT_AT}

USER 10001
EXPOSE 8000

HEALTHCHECK --interval=10s --timeout=3s --start-period=20s --retries=3 \
    CMD ["python", "-c", "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8000/health').status==200 else 1)"]

# Default command runs the API; the worker service overrides this in compose so
# one image covers both roles.
CMD ["uvicorn", "dropme.main:app", "--host", "0.0.0.0", "--port", "8000"]

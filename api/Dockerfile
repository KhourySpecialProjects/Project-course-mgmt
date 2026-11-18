# syntax=docker/dockerfile:1
#
# API image. Two targets:
#   dev  - used by docker-compose.yml; source code is mounted in and the server
#          reloads on every save.
#   prod - a smaller image with the code baked in and no dev tools.

FROM python:3.13-slim AS base
# uv is a fast Python package manager (https://docs.astral.sh/uv/).
RUN pip install --no-cache-dir "uv==0.11.32"
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH="/opt/venv/bin:$PATH"
WORKDIR /app

# ---------------------------------------------------------------- dev
FROM base AS dev
# Install dependencies first (cached unless pyproject.toml / uv.lock change).
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv uv sync --frozen --no-install-project
COPY . .
EXPOSE 8000
CMD ["./scripts/start.sh", "--reload"]

# ---------------------------------------------------------------- prod
FROM base AS prod
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv uv sync --frozen --no-install-project --no-dev
COPY . .
RUN useradd --create-home appuser
USER appuser
EXPOSE 8000
CMD ["./scripts/start.sh"]

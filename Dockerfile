# syntax=docker/dockerfile:1
# multi-stage build: builder installs deps, runtime runs app
FROM python:3.13-slim-bookworm AS builder

WORKDIR /build

RUN apt-get update -qq && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/* \
    && curl -LsSf https://astral.sh/uv/install.sh | sh \
    && mv /root/.local/bin/uv /usr/local/bin/uv

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY src/ ./src/

FROM python:3.13-slim-bookworm AS runtime

WORKDIR /app

RUN apt-get update -qq && apt-get install -y --no-install-recommends gosu \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd --gid 1000 app \
    && useradd --uid 1000 --gid app --shell /bin/sh --create-home app

COPY --from=builder /build/.venv /app/.venv
COPY --from=builder /build/src/. /app/
COPY entrypoint.sh /app/entrypoint.sh

RUN chmod +x /app/entrypoint.sh && chown -R app:app /app

ENV PATH="/app/.venv/bin:$PATH"

ENTRYPOINT ["/app/entrypoint.sh"]

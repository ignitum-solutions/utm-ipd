###############################################################################
# 1) Builder – installs deps into a Poetry .venv
###############################################################################
FROM python:3.13-slim-bookworm AS builder

RUN pip install --upgrade pip && pip install --no-cache-dir poetry

ENV POETRY_VIRTUALENVS_IN_PROJECT=1 \
    POETRY_NO_INTERACTION=1 \
    POETRY_CACHE_DIR=/tmp/poetry_cache

WORKDIR /app

# 1-a  install *dependencies only*  (no source yet: cache-friendly)
COPY pyproject.toml poetry.lock* ./
RUN poetry install --without dev --no-root --no-interaction \
    && rm -rf $POETRY_CACHE_DIR

# 1-b  copy source and install our own package
COPY utm       ./utm
COPY strategies ./strategies
COPY tournaments ./tournaments
RUN poetry install --only-root --no-interaction

###############################################################################
# 2) Runtime – copies ready-made .venv and source, runs as non-root
###############################################################################
FROM python:3.13-slim-bookworm AS runtime

ARG GIT_SHA=dev
ENV GIT_SHA=${GIT_SHA}
LABEL org.opencontainers.image.revision="${GIT_SHA}"

RUN groupadd -r appuser && useradd -r -g appuser appuser
ENV VIRTUAL_ENV=/app/.venv \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app
COPY --from=builder /app/.venv ${VIRTUAL_ENV}

# copy source so stack-traces & hot-reload see real files
COPY docker_entrypoint.sh .
COPY utm         ./utm
COPY config      ./config
COPY strategies  ./strategies
COPY tournaments ./tournaments
COPY dash        ./dash

RUN chmod +x docker_entrypoint.sh && chown -R appuser:appuser /app
USER appuser
ENTRYPOINT ["./docker_entrypoint.sh"]

EXPOSE 8501 8080

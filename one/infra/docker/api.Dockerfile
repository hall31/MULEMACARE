# syntax=docker/dockerfile:1.7
# Image de l'API MulemaCare One (L10). Contexte de build : la racine de `one/`.
#   docker build -f infra/docker/api.Dockerfile -t mulemacare-one-api .
# Aucun secret dans l'image : tout vient de l'environnement de l'instance (docs/DEPLOYMENT.md).
# Utilisateur non root, dépendances figées par uv.lock (sans le groupe de développement).

ARG PYTHON_IMAGE=python:3.12-slim-bookworm
ARG UV_IMAGE=ghcr.io/astral-sh/uv:0.9

FROM ${UV_IMAGE} AS uv

FROM ${PYTHON_IMAGE} AS build
COPY --from=uv /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/app/.venv
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project

FROM ${PYTHON_IMAGE} AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/apps \
    PATH=/app/.venv/bin:$PATH \
    MULEMA_HTTP_HOST=0.0.0.0 \
    MULEMA_HTTP_PORT=8000
RUN groupadd --system --gid 10001 mulema \
 && useradd --system --uid 10001 --gid mulema --home-dir /nonexistent --shell /usr/sbin/nologin mulema
WORKDIR /app
COPY --from=build /app/.venv /app/.venv
# Code de l'API, migrations, configuration réseau par pays : rien d'autre (ni web, ni specs
# hors graines de démo, ni tests).
COPY alembic.ini ./
COPY infra/egress-allowlist.txt infra/egress-allowlist.txt
COPY infra/deploy infra/deploy
COPY specs/seeds specs/seeds
COPY apps/api apps/api
RUN find apps/api -type d -name tests -prune -exec rm -rf {} + \
 && rm -f apps/api/conftest.py \
 && python -m compileall -q apps/api
USER 10001:10001
EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=3s --start-period=20s --retries=3 \
  CMD ["python", "-c", "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=2).status == 200 else 1)"]
STOPSIGNAL SIGTERM
CMD ["python", "-m", "api.main"]

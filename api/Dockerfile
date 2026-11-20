# Image MulemaCare Mutuelle OS (API).
#
# ⚠ Le contexte de build est la **racine du monorepo**, pas ce dossier :
# requirements.txt déclare le tronc IA (`packages/cybernecs-agent-core`,
# `packages/cybernecs-ai-gateway[online]`) en chemins relatifs. Depuis la racine :
#
#   docker build -f APPS/PUBLIC/HEALTH/MULEMACARE/api/Dockerfile \
#     -t cybernecs/mulemacare-api:local .
#
# Le compose le fait via `context: ../../../..`. Ignore dédié :
# `Dockerfile.dockerignore` (BuildKit le lit en priorité sur celui de la racine).

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1

ARG APP=APPS/PUBLIC/HEALTH/MULEMACARE/api

# pip résout les `-e ../../../../../packages/...` depuis le répertoire courant :
# on reproduit la disposition du monorepo sous /monorepo pour que la même ligne
# serve au poste de dev et à l'image. Les deux paquets référencent les licences
# CYBERCLAW (`license-files`), copiées à leur place.
COPY APPS/ENTREPRISES/CYBERCLAW/LICENSE APPS/ENTREPRISES/CYBERCLAW/NOTICE \
     /monorepo/APPS/ENTREPRISES/CYBERCLAW/
COPY packages/cybernecs-agent-core /monorepo/packages/cybernecs-agent-core
COPY packages/cybernecs-ai-gateway /monorepo/packages/cybernecs-ai-gateway

COPY ${APP}/requirements.txt /monorepo/${APP}/requirements.txt
WORKDIR /monorepo/${APP}
RUN pip install --no-cache-dir -r requirements.txt

WORKDIR /app
COPY ${APP}/app ./app

EXPOSE 8080
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]

# Production image: the API plus the built web app, served from one address (see docs/DEPLOY.md).
# Build from the repository root:  docker build -t money-budget --build-arg VITE_GOOGLE_CLIENT_ID=... .
# Development uses back-end/Dockerfile and front-end/Dockerfile through docker compose instead.

# --- 1. Build the web app ----------------------------------------------------------------------------------------
FROM node:22-slim AS web
WORKDIR /web
COPY front-end/package.json front-end/package-lock.json ./
RUN npm ci
COPY front-end/ ./
# Baked into the files at build time (the public Google sign-in id, not a secret). No VITE_API_URL: the web app
# talks to the address it is served from.
ARG VITE_GOOGLE_CLIENT_ID=""
ENV VITE_GOOGLE_CLIENT_ID=$VITE_GOOGLE_CLIENT_ID
RUN npm run build

# --- 2. The API --------------------------------------------------------------------------------------------------
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    STATIC_DIR=/app/static \
    PORT=8080
WORKDIR /app

# Only what runs in production: no test tools (requirements-dev.txt)
COPY back-end/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY back-end/ ./
COPY --from=web /web/dist /app/static

# No root inside the container
RUN useradd --system --no-create-home app
USER app

EXPOSE 8080
# No --reload; the host (Cloud Run) says which port with $PORT. Migrations are NOT run here: they are a separate step
# of the deploy (python -m db.upgrade), so a failed one stops the release before it gets traffic.
CMD ["sh", "-c", "exec uvicorn api.app:app --host 0.0.0.0 --port ${PORT}"]

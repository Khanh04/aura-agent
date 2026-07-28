# Build the React UI (frontend/dist) in a throwaway Node stage.
FROM node:20-slim AS ui
WORKDIR /ui
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build


FROM python:3.11-slim

# uv for dependency management.
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Install deps first for layer caching.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY . /app

# The built React UI, served by FastAPI at / (same origin as the API -- no CORS).
COPY --from=ui /ui/dist /app/frontend/dist

RUN uv sync --frozen --no-dev

EXPOSE 8200
CMD uv run uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8200}

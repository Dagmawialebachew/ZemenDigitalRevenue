# Zemen Digital — single-service production image.
# Frontends are built once and served by the same FastAPI origin.
FROM node:24-alpine AS miniapp-build
WORKDIR /build/miniapp
COPY miniapp/package.json ./
RUN npm install --no-audit --no-fund
COPY miniapp/ ./
ENV VITE_BASE_PATH=/store/
ENV VITE_API_BASE_URL=/api/miniapp
RUN npm run build

FROM node:24-alpine AS dashboard-build
WORKDIR /build/dashboard
COPY dashboard/package.json ./
RUN npm install --no-audit --no-fund
COPY dashboard/ ./
ENV VITE_BASE_PATH=/control/
ENV VITE_API_BASE=
RUN npm run build

FROM python:3.13-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    APP_HOST=0.0.0.0 \
    STATIC_APPS_ENABLED=true
WORKDIR /app
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl postgresql-client ca-certificates \
    && rm -rf /var/lib/apt/lists/*
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
COPY --from=miniapp-build /build/miniapp/dist ./miniapp/dist
COPY --from=dashboard-build /build/dashboard/dist ./dashboard/dist
RUN find . -type d -name __pycache__ -prune -exec rm -rf {} + \
    && rm -rf .pytest_cache
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 CMD curl -fsS http://127.0.0.1:8000/health/live || exit 1
CMD ["sh", "scripts/start-production.sh"]

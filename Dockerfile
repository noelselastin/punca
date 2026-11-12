# Punca as one container (used for the free Render web service).
# Stage 1 builds the React front end; stage 2 runs FastAPI, which also serves the built pages.

FROM node:20-slim AS web
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

FROM python:3.13-slim
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1
WORKDIR /app
COPY backend/requirements.txt backend/requirements.txt
RUN pip install -r backend/requirements.txt

RUN useradd -m -u 1000 user
COPY --chown=user backend/ backend/
COPY --chown=user data/ data/
COPY --from=web --chown=user /web/dist frontend/dist
RUN mkdir -p /app/logs /app/backend/var && chown -R user /app/logs /app/backend/var

# Saved data lives inside the container, so it starts again from the demo data after every
# restart or redeploy. GEMINI_API_KEY comes from the host's environment settings; with no key
# Punca runs in offline mode.
ENV PUNCA_STORE=/app/backend/var/store.json \
    PUNCA_TIMEZONE=Asia/Kuala_Lumpur

USER user
WORKDIR /app/backend
# Render passes the port in $PORT (10000 by default).
EXPOSE 10000
CMD ["sh", "-c", "exec uvicorn api.main:app --host 0.0.0.0 --port ${PORT:-10000} --proxy-headers --forwarded-allow-ips '*'"]

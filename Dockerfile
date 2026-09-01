# syntax=docker/dockerfile:1
# ---------------------------------------------------------------------------
# Stage 1 - build the React frontend
# ---------------------------------------------------------------------------
FROM node:20-slim AS frontend
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build          # -> /build/dist

# ---------------------------------------------------------------------------
# Stage 2 - Python runtime (serves API + the built frontend)
# ---------------------------------------------------------------------------
FROM python:3.11-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    STATIC_DIR=/app/static \
    STORAGE_DIR=/data \
    SAMPLE_TEMPLATE=/app/samples/template.xlsx \
    SAMPLE_REQUIREMENTS="/app/samples/OA_DLD_RERA_Interim Audit_Requirements_PROA_30 June 2026.xlsx"

WORKDIR /app

# Python deps first for layer caching
COPY backend/requirements.txt ./requirements.txt
RUN pip install --upgrade pip && pip install -r requirements.txt

# Backend source
COPY backend/ ./

# Built frontend + demo sample workbooks
COPY --from=frontend /build/dist ./static
COPY template.xlsx "./samples/template.xlsx"
COPY "OA_DLD_RERA_Interim Audit_Requirements_PROA_30 June 2026.xlsx" "./samples/OA_DLD_RERA_Interim Audit_Requirements_PROA_30 June 2026.xlsx"

RUN mkdir -p /data
EXPOSE 8000

# One worker: the session store lives in process memory.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1"]

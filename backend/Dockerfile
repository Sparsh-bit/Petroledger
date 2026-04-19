# syntax=docker/dockerfile:1.6
# ── Stage 1: Builder ────────────────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /build

# System deps for WeasyPrint (cairo, pango, gdk-pixbuf, libffi) + psycopg build
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libcairo2-dev \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libgdk-pixbuf-2.0-0 \
    libffi-dev \
    shared-mime-info \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
RUN pip install --upgrade pip \
    && pip install --no-cache-dir hatchling \
    && pip install --no-cache-dir -e ".[dev]" 2>/dev/null || pip install --no-cache-dir -e .


# ── Stage 2: Runtime ─────────────────────────────────────────────────────
FROM python:3.11-slim AS runtime

WORKDIR /app

# Runtime system libs only (no build tools)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libcairo2 \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libgdk-pixbuf-2.0-0 \
    libffi8 \
    shared-mime-info \
    libglib2.0-0 \
    tesseract-ocr \
    tesseract-ocr-eng \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application source
COPY . .

# Create reports directory
RUN mkdir -p /app/reports

# Non-root user for security (with home dir so gunicorn/tooling has a writable $HOME)
RUN useradd --create-home --home-dir /home/appuser --shell /bin/false appuser \
    && chown -R appuser:appuser /app /home/appuser
USER appuser

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    REPORTS_DIR=/app/reports \
    HOME=/home/appuser \
    PORT=8000

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD curl -fsS "http://127.0.0.1:${PORT}/health" || exit 1

# Production: run Alembic migrations, then start gunicorn managing uvicorn workers.
# Set SKIP_MIGRATIONS=true to skip migrations (useful for debugging or re-deploys).
CMD ["sh", "-c", "if [ \"$SKIP_MIGRATIONS\" != 'true' ]; then alembic upgrade head; fi && gunicorn app.main:app -k uvicorn.workers.UvicornWorker -w ${WEB_CONCURRENCY:-4} -b 0.0.0.0:${PORT} --access-logfile - --error-logfile -"]

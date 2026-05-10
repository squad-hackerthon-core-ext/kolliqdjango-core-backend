# ══════════════════════════════════════════════════════════════════
# Kolliq — Django Backend
# Multi-stage build: builder installs deps, final image is lean
# ══════════════════════════════════════════════════════════════════

# ── Stage 1: Builder ─────────────────────────────────────────────
FROM python:3.11-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /build

# System deps needed to compile psycopg2 and other C extensions
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies into a separate directory
# so we can copy only them into the final image
COPY requirements.txt .
RUN pip install --prefix=/install -r requirements.txt

# ── Stage 2: Final image ──────────────────────────────────────────
FROM python:3.11-slim AS final

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    DJANGO_SETTINGS_MODULE=kolliq.settings

WORKDIR /app

# Runtime system deps only (no build tools)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Create non-root user for security
RUN groupadd --gid 1001 kolliq && \
    useradd --uid 1001 --gid kolliq --shell /bin/bash --create-home kolliq

# Copy application code
COPY --chown=kolliq:kolliq . .

# Create directories Django needs
RUN mkdir -p /app/staticfiles /app/mediafiles && \
    chown -R kolliq:kolliq /app/staticfiles /app/mediafiles

USER kolliq

# Collect static files (non-fatal — will warn if SECRET_KEY not set)
RUN python manage.py collectstatic --noinput --clear 2>/dev/null || true

EXPOSE 8000

# Health check — Docker will mark container unhealthy if this fails
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/api/health/ || exit 1

# Default command — gunicorn with 2 workers per CPU core
# Override in docker-compose for local dev (runserver)
CMD ["gunicorn", "kolliq.wsgi:application", \
     "--bind", "0.0.0.0:8000", \
     "--workers", "2", \
     "--threads", "2", \
     "--worker-class", "gthread", \
     "--worker-tmp-dir", "/dev/shm", \
     "--timeout", "30", \
     "--keep-alive", "5", \
     "--log-level", "info", \
     "--access-logfile", "-", \
     "--error-logfile", "-"]
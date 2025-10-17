# ---- Builder: create a wheel from pyproject.toml ----
FROM python:3.11-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /build

# Build tools for native deps (adjust if you need extra system libs)
RUN apt-get update && apt-get install -y --no-install-recommends \
      build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy project and build a wheel using PEP-517
COPY . .
RUN python -m pip install --upgrade pip build \
 && python -m build --wheel -o /dist

# ---- Runtime: minimal image with your package installed ----
FROM python:3.11-slim AS runtime

# (Optional) install curl for healthchecks
RUN apt-get update && apt-get install -y --no-install-recommends curl \
 && rm -rf /var/lib/apt/lists/*

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000 \
    LOG_LEVEL=info

WORKDIR /app

# Non-root user
RUN useradd -r -u 10001 appuser

# Install built wheel
COPY --from=builder /dist/*.whl /tmp/
RUN python -m pip install --no-cache-dir /tmp/*.whl \
 && rm -rf /tmp/*.whl

USER appuser

# Expose your service port
EXPOSE 8000

ENV RUN_CMD="uvicorn ai_dial_interceptor_google.__main__:main --host 0.0.0.0 --port ${PORT} --log-level ${LOG_LEVEL}"
CMD ["sh", "-c", "$RUN_CMD"]

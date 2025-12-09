FROM python:3.11-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /build
RUN apt-get update && apt-get install -y --no-install-recommends \
      build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY . .
RUN python -m pip install --upgrade pip build \
 && python -m build --wheel -o /dist

FROM python:3.11-slim AS runtime

RUN apt-get update && apt-get install -y --no-install-recommends curl \
 && rm -rf /var/lib/apt/lists/*

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000 \
    LOG_LEVEL=info

WORKDIR /app

RUN useradd -r -u 10001 appuser

COPY --from=builder /dist/*.whl /tmp/
RUN python -m pip install --no-cache-dir /tmp/*.whl \
 && rm -rf /tmp/*.whl

USER appuser

# Expose your service port
EXPOSE 8000

ENV RUN_CMD="uvicorn ai_dial_interceptor_google.__main__:main --host 0.0.0.0 --port ${PORT} --log-level ${LOG_LEVEL}"
CMD ["sh", "-c", "$RUN_CMD"]

FROM python:3.11-slim-bookworm

# Runtime libs Pillow's wheel links against (libjpeg, zlib).
# tini gives us a real PID 1 so SIGTERM from `docker stop` reaches the app.
RUN apt-get update && apt-get install -y --no-install-recommends \
        libjpeg62-turbo \
        zlib1g \
        tini \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install deps first so source-only changes don't bust the layer cache.
COPY pyproject.toml ./
COPY pogo_scout ./pogo_scout
RUN pip install --no-cache-dir .

# Non-root user. Bind-mounted /data must be writable by uid 1000 on the host.
RUN useradd --create-home --uid 1000 pogo \
    && mkdir -p /data \
    && chown -R pogo:pogo /data
USER pogo

ENV POGO_CONFIG_YAML=/data/config.yaml \
    POGO_DB_PATH=/data/pogo_scout.db \
    POGO_HTTP_HOST=0.0.0.0 \
    PYTHONUNBUFFERED=1

EXPOSE 8000

ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["python", "-m", "pogo_scout.main"]

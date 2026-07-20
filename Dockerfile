FROM python:3.12-slim-bookworm

LABEL org.opencontainers.image.title="Talamus" \
      org.opencontainers.image.description="Local-first, source-grounded memory for AI agents" \
      org.opencontainers.image.source="https://github.com/ampres-ai/talamus" \
      org.opencontainers.image.licenses="Apache-2.0"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN groupadd --system talamus \
    && useradd --system --gid talamus --home-dir /home/talamus --create-home talamus

COPY pyproject.toml README.md LICENSE ./
COPY src ./src

RUN python -m pip install ".[mcp]" \
    && mkdir -p /data \
    && chown talamus:talamus /data

USER talamus
WORKDIR /data

VOLUME ["/data"]

ENTRYPOINT ["talamus-mcp"]
CMD ["--root", "/data"]

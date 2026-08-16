FROM python:3.12-slim AS builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    VIRTUAL_ENV=/opt/venv

RUN python -m venv "$VIRTUAL_ENV"
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

WORKDIR /build
COPY pyproject.toml README.md LICENSE ./
COPY app ./app
RUN pip install .

FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    APP_HOST=0.0.0.0 \
    APP_PORT=8000

RUN groupadd --system app && useradd --system --gid app --home-dir /app app

WORKDIR /app
COPY --from=builder /opt/venv /opt/venv
COPY --chown=app:app app ./app
COPY --chown=app:app migrations ./migrations
COPY --chown=app:app alembic.ini ./alembic.ini

RUN mkdir -p /data/uploads && chown -R app:app /data

USER app

EXPOSE 8000
VOLUME ["/data/uploads"]

HEALTHCHECK --interval=10s --timeout=3s --start-period=10s --retries=5 \
    CMD python -c "import os, urllib.request; port = os.getenv('APP_PORT', '8000'); urllib.request.urlopen(f'http://127.0.0.1:{port}/health/ready', timeout=2)"

CMD ["sh", "-c", "alembic upgrade head && exec uvicorn app.main:app --host \"$APP_HOST\" --port \"$APP_PORT\""]

FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /workspace

RUN python -m pip install --upgrade pip setuptools wheel

COPY api/pyproject.toml api/README.md ./api/
COPY api/app ./api/app
COPY workers/pyproject.toml workers/README.md ./workers/
COPY workers/src ./workers/src

RUN python -m pip wheel --wheel-dir /tmp/wheels ./api ./workers

FROM python:3.12-slim AS runner

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY --from=builder /tmp/wheels /tmp/wheels
RUN python -m pip install --no-cache-dir /tmp/wheels/*.whl && rm -rf /tmp/wheels

CMD ["ukde-worker", "run"]

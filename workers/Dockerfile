FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN python -m pip install --upgrade pip setuptools wheel

COPY pyproject.toml README.md ./
COPY src ./src

RUN python -m pip wheel --wheel-dir /tmp/wheels .

FROM python:3.12-slim AS runner

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY --from=builder /tmp/wheels /tmp/wheels
RUN python -m pip install --no-cache-dir /tmp/wheels/*.whl && rm -rf /tmp/wheels

CMD ["ukde-worker", "status"]


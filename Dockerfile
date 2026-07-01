# syntax=docker/dockerfile:1

FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        curl \
        iputils-ping \
        netcat-openbsd \
    && rm -rf /var/lib/apt/lists/*

ARG INSTALL_DEV=true

COPY backend/requirements.txt /app/backend/requirements.txt
COPY backend/requirements-dev.txt /app/backend/requirements-dev.txt
RUN pip install --upgrade pip \
    && pip install -r /app/backend/requirements.txt \
    && if [ "$INSTALL_DEV" = "true" ]; then pip install -r /app/backend/requirements-dev.txt; fi

COPY . /app

RUN groupadd --gid 10001 app \
    && useradd --uid 10001 --gid app --create-home app \
    && chmod +x /app/docker/entrypoint.sh /app/docker/wait-for-service.sh

ENTRYPOINT ["/app/docker/entrypoint.sh"]

"""Cliente Redis compartilhado pela infraestrutura assincrona."""

from __future__ import annotations

import os

from redis import Redis


_redis_client: Redis | None = None


def get_redis_client() -> Redis:
    """Retorna uma conexao Redis lazy e reutilizavel por processo."""
    global _redis_client
    if _redis_client is None:
        _redis_client = Redis.from_url(
            os.getenv("REDIS_URL", "redis://redis:6379/0"),
            decode_responses=True,
            socket_connect_timeout=2,
            socket_timeout=2,
        )
    return _redis_client

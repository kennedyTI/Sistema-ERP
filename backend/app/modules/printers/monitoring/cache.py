"""Estado transitorio de conectividade armazenado no Redis."""

from __future__ import annotations

import json
from typing import Any

from redis import Redis

from backend.app.core.redis_client import get_redis_client


def connectivity_cache_key(machine_id: int) -> str:
    return f"printers:connectivity:{machine_id}"


def read_connectivity_state(
    machine_id: int,
    *,
    client: Redis | None = None,
) -> dict[str, Any] | None:
    redis_client = client or get_redis_client()
    raw_value = redis_client.get(connectivity_cache_key(machine_id))
    if not raw_value:
        return None
    if isinstance(raw_value, bytes):
        raw_value = raw_value.decode("utf-8")
    try:
        value = json.loads(raw_value)
    except (TypeError, ValueError):
        return None
    return value if isinstance(value, dict) else None


def write_connectivity_state(
    machine_id: int,
    payload: dict[str, Any],
    ttl_seconds: int,
    *,
    client: Redis | None = None,
) -> None:
    redis_client = client or get_redis_client()
    redis_client.set(
        connectivity_cache_key(machine_id),
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
        ex=ttl_seconds,
    )

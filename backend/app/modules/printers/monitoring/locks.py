"""Locks Redis com token e liberacao atomica."""

from __future__ import annotations

from uuid import uuid4

from redis import Redis

from backend.app.core.redis_client import get_redis_client


RELEASE_LOCK_SCRIPT = """
if redis.call("get", KEYS[1]) == ARGV[1] then
    return redis.call("del", KEYS[1])
end
return 0
"""


def acquire_lock(key: str, ttl_seconds: int, *, client: Redis | None = None) -> str | None:
    redis_client = client or get_redis_client()
    token = uuid4().hex
    acquired = redis_client.set(key, token, nx=True, ex=ttl_seconds)
    return token if acquired else None


def release_lock(key: str, token: str, *, client: Redis | None = None) -> bool:
    redis_client = client or get_redis_client()
    return bool(redis_client.eval(RELEASE_LOCK_SCRIPT, 1, key, token))

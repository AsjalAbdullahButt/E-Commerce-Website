"""Phase 4 (production readiness, 2026-07-21): utils/cache.py's optional Redis backend
(settings.redis_enabled). No real Redis server is available in this test environment, so these
tests patch utils.cache._get_redis_client with a small fake that mimics the redis.asyncio surface
this module actually calls (get/set/delete/scan_iter) — enough to prove cache_get/cache_set/
cache_delete/cache_clear_prefix correctly delegate to Redis instead of the in-memory dict when
the flag is on, and that the in-memory path stays exactly as before when it's off (already
covered elsewhere, e.g. test_cache_invalidation.py, none of which sets this flag).
"""
import asyncio
import time

import pytest

import utils.cache as cache_module
from config import settings


class _FakeRedis:
    """In-memory stand-in for redis.asyncio.Redis, covering only what utils/cache.py calls."""

    def __init__(self):
        self._store = {}  # key -> (expires_at monotonic time or None, json-encoded str)

    async def get(self, key):
        entry = self._store.get(key)
        if entry is None:
            return None
        expires_at, value = entry
        if expires_at is not None and expires_at <= time.monotonic():
            self._store.pop(key, None)
            return None
        return value

    async def set(self, key, value, ex=None):
        expires_at = time.monotonic() + ex if ex is not None else None
        self._store[key] = (expires_at, value)

    async def delete(self, *keys):
        for key in keys:
            self._store.pop(key, None)

    async def scan_iter(self, match=None):
        prefix = (match or "*").rstrip("*")
        for key in list(self._store.keys()):
            if key.startswith(prefix):
                yield key

    async def aclose(self):
        pass


@pytest.fixture
def fake_redis(monkeypatch):
    fake = _FakeRedis()
    monkeypatch.setattr(settings, "redis_enabled", True)
    monkeypatch.setattr(cache_module, "_get_redis_client", lambda: fake)
    return fake


def test_cache_set_and_get_round_trip_via_redis(fake_redis, client):
    asyncio.run(cache_module.cache_set("redis:test:key", {"hello": "world"}, ttl_seconds=60))
    result = asyncio.run(cache_module.cache_get("redis:test:key"))
    assert result == {"hello": "world"}
    # Proves it actually went through the fake Redis client, not the in-memory dict.
    assert "redis:test:key" in fake_redis._store


def test_cache_get_missing_key_returns_none_via_redis(fake_redis, client):
    result = asyncio.run(cache_module.cache_get("redis:missing:key"))
    assert result is None


def test_cache_delete_removes_key_via_redis(fake_redis, client):
    asyncio.run(cache_module.cache_set("redis:delete:key", "value", ttl_seconds=60))
    asyncio.run(cache_module.cache_delete("redis:delete:key"))
    assert asyncio.run(cache_module.cache_get("redis:delete:key")) is None


def test_cache_clear_prefix_via_redis(fake_redis, client):
    asyncio.run(cache_module.cache_set("redis:prefix:a", "1", ttl_seconds=60))
    asyncio.run(cache_module.cache_set("redis:prefix:b", "2", ttl_seconds=60))
    asyncio.run(cache_module.cache_set("redis:other:c", "3", ttl_seconds=60))

    asyncio.run(cache_module.cache_clear_prefix("redis:prefix:"))

    assert asyncio.run(cache_module.cache_get("redis:prefix:a")) is None
    assert asyncio.run(cache_module.cache_get("redis:prefix:b")) is None
    assert asyncio.run(cache_module.cache_get("redis:other:c")) == "3"


def test_cache_sweeper_does_not_start_when_redis_enabled(fake_redis, client):
    cache_module.start_cache_sweeper()
    assert cache_module._sweep_task is None


def test_check_single_worker_deployment_allows_multi_worker_with_redis(monkeypatch):
    import main
    monkeypatch.setattr(settings, "redis_enabled", True)
    monkeypatch.setattr(settings, "web_concurrency", 4)
    monkeypatch.setattr(settings, "environment", "production")
    main.check_single_worker_deployment()  # must not raise


def test_limiter_selects_redis_storage_when_given_a_redis_uri():
    """utils/limiter.py wires storage_uri=settings.redis_url only when redis_enabled -- this
    confirms slowapi/limits actually honors that URI (construction doesn't need a live
    connection, only parses the scheme), independent of the already-constructed module-level
    `limiter` singleton which can't be re-parameterized after import."""
    from limits.storage.redis import RedisStorage
    from slowapi import Limiter
    from slowapi.util import get_remote_address

    test_limiter = Limiter(key_func=get_remote_address, storage_uri="redis://localhost:6399/0")
    assert isinstance(test_limiter._storage, RedisStorage)

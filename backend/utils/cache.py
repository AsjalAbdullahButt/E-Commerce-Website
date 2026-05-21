import asyncio
import time
from typing import Any, Optional


_cache: dict[str, tuple[float, Any]] = {}
_lock = asyncio.Lock()


async def cache_get(key: str) -> Optional[Any]:
    async with _lock:
        entry = _cache.get(key)
        if not entry:
            return None

        expires_at, value = entry
        if expires_at <= time.time():
            _cache.pop(key, None)
            return None

        return value


async def cache_set(key: str, value: Any, ttl_seconds: int = 60) -> None:
    async with _lock:
        _cache[key] = (time.time() + ttl_seconds, value)


async def cache_delete(key: str) -> None:
    async with _lock:
        _cache.pop(key, None)


async def cache_clear_prefix(prefix: str) -> None:
    async with _lock:
        stale_keys = [key for key in _cache if key.startswith(prefix)]
        for key in stale_keys:
            _cache.pop(key, None)
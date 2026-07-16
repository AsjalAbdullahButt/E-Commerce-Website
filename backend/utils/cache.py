import asyncio
import time
from typing import Any, Optional

# Process-local in-memory cache — no Redis or other shared backend. Safe only for a
# single-worker deployment (see config/settings.py::web_concurrency and main.py's startup
# check); with multiple worker processes, each has its own independent cache, so a write in one
# worker does not invalidate stale entries cached by another. See NOTES_schema_audit.md §7.
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
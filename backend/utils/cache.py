import asyncio
import time
from typing import Any, Optional

from config import settings

# Process-local in-memory cache — no Redis or other shared backend. Safe only for a
# single-worker deployment (see config/settings.py::web_concurrency and main.py's startup
# check); with multiple worker processes, each has its own independent cache, so a write in one
# worker does not invalidate stale entries cached by another.
#
# Bounded two ways so it can't grow without limit:
#   1. cache_set() evicts the least-recently-used entry once settings.cache_max_entries is
#      exceeded (cache_get() moves a hit to the end of _cache, so eviction order tracks actual
#      access, not just insertion).
#   2. A background sweep task (started in main.py's startup event, cancelled on shutdown) walks
#      the cache periodically and drops entries whose TTL has already expired — without this, a
#      key that's set once and never read again would sit in memory forever, since the TTL check
#      in cache_get() only fires on access.
#
# To swap in Redis: replace the dict/lock below with an aioredis client. cache_get/cache_set/
# cache_delete/cache_clear_prefix already have Redis-compatible async signatures — cache_set's
# ttl_seconds maps directly to SETEX, and cache_clear_prefix would become a SCAN+DEL. The sweep
# task and eviction logic would no longer be needed (Redis expires keys natively).
_cache: dict[str, tuple[float, Any]] = {}
_lock = asyncio.Lock()

CACHE_SWEEP_INTERVAL_SECONDS = 60

_sweep_task: Optional[asyncio.Task] = None


async def cache_get(key: str) -> Optional[Any]:
    async with _lock:
        entry = _cache.get(key)
        if not entry:
            return None

        expires_at, value = entry
        if expires_at <= time.time():
            _cache.pop(key, None)
            return None

        # Re-insert to mark as most-recently-used (dicts preserve insertion order in Python
        # 3.7+), so cache_set()'s eviction drops the true least-recently-used entry first.
        _cache.pop(key, None)
        _cache[key] = entry
        return value


async def cache_set(key: str, value: Any, ttl_seconds: int = 60) -> None:
    async with _lock:
        _cache.pop(key, None)
        _cache[key] = (time.time() + ttl_seconds, value)
        while len(_cache) > settings.cache_max_entries:
            oldest_key = next(iter(_cache))
            _cache.pop(oldest_key, None)


async def cache_delete(key: str) -> None:
    async with _lock:
        _cache.pop(key, None)


async def cache_clear_prefix(prefix: str) -> None:
    async with _lock:
        stale_keys = [key for key in _cache if key.startswith(prefix)]
        for key in stale_keys:
            _cache.pop(key, None)


async def _sweep_expired_forever() -> None:
    """Background loop: drop expired entries that nobody ever reads again. cache_get()'s TTL
    check is lazy (only runs when a key is looked up), so a set-and-forget key would otherwise
    outlive its TTL indefinitely — this is what actually bounds memory over time, independent of
    the LRU cap in cache_set()."""
    while True:
        await asyncio.sleep(CACHE_SWEEP_INTERVAL_SECONDS)
        now = time.time()
        async with _lock:
            expired = [key for key, (expires_at, _) in _cache.items() if expires_at <= now]
            for key in expired:
                _cache.pop(key, None)


def start_cache_sweeper() -> None:
    """Call once from FastAPI's startup event."""
    global _sweep_task
    if _sweep_task is None:
        _sweep_task = asyncio.create_task(_sweep_expired_forever())


async def stop_cache_sweeper() -> None:
    """Call once from FastAPI's shutdown event."""
    global _sweep_task
    if _sweep_task is not None:
        _sweep_task.cancel()
        try:
            await _sweep_task
        except asyncio.CancelledError:
            pass
        _sweep_task = None

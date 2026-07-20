import asyncio
import json
import time
from typing import Any, Optional

from config import settings

# Two backends behind the same async cache_get/cache_set/cache_delete/cache_clear_prefix API:
#
#   - In-memory dict (default, settings.redis_enabled=False): process-local, safe only for a
#     single-worker deployment (see config/settings.py::web_concurrency and main.py's startup
#     check) — with multiple worker processes, each has its own independent cache, so a write in
#     one worker does not invalidate stale entries cached by another.
#   - Redis (settings.redis_enabled=True): shared across every worker process, so
#     WEB_CONCURRENCY > 1 becomes safe. Values are JSON-encoded (every current caller stores
#     JSON-serializable dicts/lists/strings — see routes/products.py, routes/seo.py,
#     services/google_auth.py); TTL and prefix-clear map directly to Redis's own SETEX/SCAN.
#
# The in-memory path is bounded two ways so it can't grow without limit:
#   1. cache_set() evicts the least-recently-used entry once settings.cache_max_entries is
#      exceeded (cache_get() moves a hit to the end of _cache, so eviction order tracks actual
#      access, not just insertion).
#   2. A background sweep task (started in main.py's startup event, cancelled on shutdown) walks
#      the cache periodically and drops entries whose TTL has already expired — without this, a
#      key that's set once and never read again would sit in memory forever, since the TTL check
#      in cache_get() only fires on access. Redis needs neither of these — it expires and evicts
#      natively — so the sweep task is a no-op when redis_enabled.
_cache: dict[str, tuple[float, Any]] = {}
_lock = asyncio.Lock()

CACHE_SWEEP_INTERVAL_SECONDS = 60

_sweep_task: Optional[asyncio.Task] = None

_redis_client = None


def _get_redis_client():
    """Lazily constructs a single shared redis.asyncio client. Deferred import: redis is a real
    dependency (requirements.txt) but only ever touched when redis_enabled=True, so an
    environment that never turns this on doesn't need a reachable Redis at import time."""
    global _redis_client
    if _redis_client is None:
        import redis.asyncio as redis
        _redis_client = redis.Redis.from_url(settings.redis_url, decode_responses=True)
    return _redis_client


async def cache_get(key: str) -> Optional[Any]:
    if settings.redis_enabled:
        raw = await _get_redis_client().get(key)
        return json.loads(raw) if raw is not None else None

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
    if settings.redis_enabled:
        await _get_redis_client().set(key, json.dumps(value), ex=ttl_seconds)
        return

    async with _lock:
        _cache.pop(key, None)
        _cache[key] = (time.time() + ttl_seconds, value)
        while len(_cache) > settings.cache_max_entries:
            oldest_key = next(iter(_cache))
            _cache.pop(oldest_key, None)


async def cache_delete(key: str) -> None:
    if settings.redis_enabled:
        await _get_redis_client().delete(key)
        return

    async with _lock:
        _cache.pop(key, None)


async def cache_clear_prefix(prefix: str) -> None:
    if settings.redis_enabled:
        client = _get_redis_client()
        # SCAN, not KEYS: KEYS blocks the whole Redis server on a large keyspace; SCAN walks it
        # incrementally instead. Fine to iterate to completion here since this is an
        # infrequent, admin/test-triggered operation, not a hot request path.
        async for match in client.scan_iter(match=f"{prefix}*"):
            await client.delete(match)
        return

    async with _lock:
        stale_keys = [key for key in _cache if key.startswith(prefix)]
        for key in stale_keys:
            _cache.pop(key, None)


async def _sweep_expired_forever() -> None:
    """Background loop: drop expired entries that nobody ever reads again. cache_get()'s TTL
    check is lazy (only runs when a key is looked up), so a set-and-forget key would otherwise
    outlive its TTL indefinitely — this is what actually bounds memory over time, independent of
    the LRU cap in cache_set(). Not needed (or started) when redis_enabled — Redis expires keys
    natively."""
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
    if settings.redis_enabled:
        return
    if _sweep_task is None:
        _sweep_task = asyncio.create_task(_sweep_expired_forever())


async def stop_cache_sweeper() -> None:
    """Call once from FastAPI's shutdown event."""
    global _sweep_task, _redis_client
    if _sweep_task is not None:
        _sweep_task.cancel()
        try:
            await _sweep_task
        except asyncio.CancelledError:
            pass
        _sweep_task = None
    if _redis_client is not None:
        await _redis_client.aclose()
        _redis_client = None

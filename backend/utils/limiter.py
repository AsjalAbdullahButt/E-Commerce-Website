from slowapi import Limiter
from slowapi.util import get_remote_address

from config import settings

# Defaults to slowapi's in-memory storage — same single-worker constraint as utils/cache.py: with
# multiple worker processes, each has its own independent rate-limit counters, so a client can
# exceed the intended limit by roughly (worker count)x. When settings.redis_enabled, slowapi (via
# the `limits` package) stores counters in Redis instead, shared across every worker process —
# same requirements.txt `redis` dependency utils/cache.py uses, same REDIS_URL. See
# main.py::check_single_worker_deployment, which only enforces the single-worker guard when this
# is off.
limiter = Limiter(
    key_func=get_remote_address,
    storage_uri=settings.redis_url if settings.redis_enabled else None,
)

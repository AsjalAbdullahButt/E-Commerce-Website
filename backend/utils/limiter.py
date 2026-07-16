from slowapi import Limiter
from slowapi.util import get_remote_address

# Uses slowapi's default in-memory storage — no Redis backend. Same single-worker constraint as
# utils/cache.py: with multiple worker processes, each has its own independent rate-limit
# counters, so a client can exceed the intended limit by roughly (worker count)x. See
# NOTES_schema_audit.md §7.
limiter = Limiter(key_func=get_remote_address)

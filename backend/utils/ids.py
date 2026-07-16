import os
import re
import threading
import time

_ID_RE = re.compile(r"^[0-9a-f]{24}$")
_lock = threading.Lock()
_counter = int.from_bytes(os.urandom(3), "big")


def new_id() -> str:
    """24-hex-char, roughly time-ordered, collision-resistant primary key.

    Deliberately the same 24-hex-char shape as a MongoDB ObjectId (4-byte timestamp + 5 random
    bytes + 3-byte counter, hex-encoded) so every route's existing `if not is_valid_id(x): raise
    HTTPException(400, ...)` validation keeps working unchanged, and IDs stay roughly
    monotonically increasing (good InnoDB insert locality) — generated here with the stdlib only,
    no third-party driver dependency.
    """
    global _counter
    ts = int(time.time()).to_bytes(4, "big")
    rand = os.urandom(5)
    with _lock:
        _counter = (_counter + 1) % 0xFFFFFF
        counter_bytes = _counter.to_bytes(3, "big")
    return (ts + rand + counter_bytes).hex()


def is_valid_id(value) -> bool:
    return bool(value) and isinstance(value, str) and bool(_ID_RE.fullmatch(value))

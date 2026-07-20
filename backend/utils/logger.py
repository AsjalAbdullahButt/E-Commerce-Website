import contextvars
import json
import logging
import logging.handlers
from pathlib import Path
from database import AsyncSessionLocal
from db.admin import AuditLog
from datetime import datetime, timezone

from config import settings

LOG_DIR = Path(__file__).parent.parent / "logs"
LOG_DIR.mkdir(exist_ok=True)

# Set by main.py's add_request_id middleware at the start of every request; read back by
# _RequestIdFilter below so every log line emitted while handling that request carries the same
# ID as its X-Request-ID response header, without threading request_id through every function
# signature that might log something. contextvars propagate correctly across `await` within the
# same asyncio task (one per request under ASGI), so this stays request-scoped for free.
request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="-")


class _RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get()
        return True


class _JsonFormatter(logging.Formatter):
    """One JSON object per line — settings.log_format == "json" (default "text" keeps the
    existing human-readable format). Meant for environments that feed logs to an aggregator
    (CloudWatch, Loki, Datadog, ...) where structured fields matter more than readability."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": getattr(record, "request_id", "-"),
        }
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload)


def _make_formatter(*, console: bool) -> logging.Formatter:
    if settings.log_format == "json":
        return _JsonFormatter()
    fmt = "%(levelname)s | %(name)s | %(message)s" if console else "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
    return logging.Formatter(fmt)


# File handler — rotates daily, keeps 30 days
file_handler = logging.handlers.TimedRotatingFileHandler(
    str(LOG_DIR / "app.log"),
    when="midnight",
    backupCount=30,
    encoding="utf-8"
)
file_handler.setFormatter(_make_formatter(console=False))
file_handler.addFilter(_RequestIdFilter())

# Console handler
console_handler = logging.StreamHandler()
console_handler.setFormatter(_make_formatter(console=True))
console_handler.addFilter(_RequestIdFilter())


def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)
    return logger

async def log_to_db(level: str, module: str, message: str, meta: dict = None):
    """Write a log entry to the audit_logs table for admin viewing.

    Opens its own independent session rather than the current request's — this must keep
    working even when the request's own transaction has already failed/rolled back, matching
    its original "never let logging crash the app" contract.
    """
    try:
        async with AsyncSessionLocal() as session:
            session.add(AuditLog(
                entry_type="system_log",
                level=level,
                module=module,
                message=message,
                meta=meta or {},
                timestamp=datetime.now(timezone.utc),
            ))
            await session.commit()
    except Exception:
        pass  # Never let logging crash the app

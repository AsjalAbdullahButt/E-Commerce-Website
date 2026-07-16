import logging
import logging.handlers
from pathlib import Path
from database import AsyncSessionLocal
from db.admin import AuditLog
from datetime import datetime

LOG_DIR = Path(__file__).parent.parent / "logs"
LOG_DIR.mkdir(exist_ok=True)

# File handler — rotates daily, keeps 30 days
file_handler = logging.handlers.TimedRotatingFileHandler(
    str(LOG_DIR / "app.log"),
    when="midnight",
    backupCount=30,
    encoding="utf-8"
)
file_handler.setFormatter(logging.Formatter(
    "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
))

# Console handler
console_handler = logging.StreamHandler()
console_handler.setFormatter(logging.Formatter(
    "%(levelname)s | %(name)s | %(message)s"
))


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
                timestamp=datetime.utcnow(),
            ))
            await session.commit()
    except Exception:
        pass  # Never let logging crash the app

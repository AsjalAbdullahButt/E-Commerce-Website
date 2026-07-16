from datetime import datetime
from typing import Optional

from sqlalchemy import JSON, Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base, IDMixin, TimestampMixin


class AdminUser(Base, IDMixin, TimestampMixin):
    __tablename__ = "admin_users"

    name: Mapped[str] = mapped_column(String(200))
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20))  # super_admin | admin | manager | support
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_locked: Mapped[bool] = mapped_column(Boolean, default=False)
    failed_login_attempts: Mapped[int] = mapped_column(Integer, default=0)
    last_locked_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    last_login: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class AuditLog(Base, IDMixin):
    """Single unified table backing the admin Logs page — two independent writers
    (utils/logger.py::log_to_db and AdminAuditService.log_action) share it via the
    `entry_type` discriminator rather than two tables, since the Logs page needs one
    time-sorted feed across both (see NOTES_schema_audit.md)."""
    __tablename__ = "audit_logs"

    entry_type: Mapped[str] = mapped_column(String(20), index=True)  # system_log | admin_action
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    # system_log fields (utils/logger.py::log_to_db)
    level: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, index=True)
    module: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    meta: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # admin_action fields (services/admin_auth.py::AdminAuditService.log_action)
    admin_id: Mapped[Optional[str]] = mapped_column(String(24), nullable=True, index=True)
    admin_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    action: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    entity_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, index=True)
    entity_id: Mapped[Optional[str]] = mapped_column(String(24), nullable=True)
    changes: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    ip_address: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

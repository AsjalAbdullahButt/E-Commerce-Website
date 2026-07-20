from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base, IDMixin, TimestampMixin


class User(Base, IDMixin, TimestampMixin):
    __tablename__ = "users"

    name: Mapped[str] = mapped_column(String(200))
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    # Nullable: Google Sign-In accounts (auth_provider="google") have no local password at all.
    password: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    address: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    role: Mapped[str] = mapped_column(String(20), default="customer", index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    is_banned: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    ban_reason: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    banned_by: Mapped[Optional[str]] = mapped_column(String(24), nullable=True)
    banned_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    reset_token_hash: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    reset_token_expires: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    # Set only by utils/token_revocation.py when a rotated-out refresh token jti is replayed
    # (evidence of a leaked token) — any refresh token with an `iat` before this timestamp is
    # rejected, killing every other live session at once, not just the one that got replayed.
    tokens_invalidated_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)

    # ── Google Sign-In (services/google_auth.py) ──────────────────────────
    # "local" (password-based) or "google". A local account that later signs in with Google
    # under the same (Google-verified) email gets google_sub linked but stays auth_provider
    # "local" — see routes/auth.py::google_login — since it still has a real password.
    auth_provider: Mapped[str] = mapped_column(String(20), default="local", server_default="local")
    google_sub: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, unique=True)
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    avatar_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

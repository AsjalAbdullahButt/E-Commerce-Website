from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base


class RevokedToken(Base):
    """A refresh token's `jti` recorded here is permanently rejected by /auth/refresh and
    /admin/auth/refresh, even though the JWT signature itself is still otherwise valid until
    `exp`. Two writers: explicit logout (revokes just the current session's jti) and normal
    rotation (revokes the just-used jti the moment a newer one is issued — see
    utils/token_revocation.py). `expires_at` mirrors the JWT's own `exp` so the cleanup sweep
    can drop rows that are already unusable via natural expiry, keeping this table from growing
    without bound."""
    __tablename__ = "revoked_tokens"

    jti: Mapped[str] = mapped_column(String(24), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(24), index=True)
    role: Mapped[str] = mapped_column(String(20))
    expires_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    revoked_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

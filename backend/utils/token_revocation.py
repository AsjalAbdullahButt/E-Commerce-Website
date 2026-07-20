"""Refresh-token revocation (db/revoked_token.py). Two independent writers:

1. Explicit logout (/auth/logout, /admin/auth/logout) revokes just the current session's jti.
2. Rotation (routes/auth.py::refresh, services/admin_auth.py::refresh_token) revokes the jti
   that was just presented the instant a newer one is issued — a refresh token is single-use.
   If that same (already-revoked) jti is ever presented again, it means a copy of the token
   leaked (e.g. stolen from a proxy log or a compromised device) and got used out of sequence
   with the legitimate client, so `enforce_refresh_rotation` treats it as a breach: it stamps
   `tokens_invalidated_at` on the user/admin/rider row, which kills every other still-live
   refresh token for that account too (checked via each token's `iat`), not just the replayed one.
"""
import asyncio
from datetime import datetime, timedelta
from typing import Optional

from fastapi import HTTPException
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.revoked_token import RevokedToken
from utils.logger import get_logger, log_to_db

logger = get_logger(__name__)

REVOCATION_SWEEP_INTERVAL_SECONDS = 3600

_sweep_task: Optional[asyncio.Task] = None


async def revoke_jti(db: AsyncSession, jti: str, user_id: str, role: str, expires_at: datetime) -> None:
    db.add(RevokedToken(jti=jti, user_id=user_id, role=role, expires_at=expires_at))


async def is_jti_revoked(db: AsyncSession, jti: str) -> bool:
    result = await db.execute(select(RevokedToken).where(RevokedToken.jti == jti))
    return result.scalar_one_or_none() is not None


async def enforce_refresh_rotation(db: AsyncSession, user_obj, payload: dict) -> None:
    """Call after the user/admin/rider row has been loaded and its is_active/is_banned/is_locked
    checks have already passed, but before minting the new access+refresh token pair. Raises
    HTTPException(401) on any reuse/staleness; otherwise revokes the presented jti so it can
    never be redeemed a second time."""
    jti = payload.get("jti")
    iat = payload.get("iat")
    exp = payload.get("exp")
    user_id = payload.get("sub")
    role = payload.get("role")

    if not jti or iat is None or exp is None:
        # Tokens minted before this feature shipped have no jti/iat — treat as untrusted rather
        # than crash, so an old refresh token just fails closed instead of 500ing.
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")

    if await is_jti_revoked(db, jti):
        # Commit explicitly here: this is about to raise HTTPException, and database.py::get_db()
        # rolls back the whole request's session on any exception — the mass-invalidation must
        # durably persist *because* a breach was detected, not in spite of it (same precedent as
        # services/admin_auth.py's failed-login counter).
        user_obj.tokens_invalidated_at = datetime.utcnow()
        await db.commit()
        await log_to_db(
            "SECURITY_ALERT", "utils.token_revocation", "REFRESH_TOKEN_REUSE_DETECTED",
            {"user_id": user_id, "role": role, "jti": jti},
        )
        logger.warning(f"REFRESH_TOKEN_REUSE_DETECTED for {role} {user_id} (jti={jti})")
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")

    invalidated_at = getattr(user_obj, "tokens_invalidated_at", None)
    if invalidated_at is not None and datetime.utcfromtimestamp(iat) < invalidated_at:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")

    await revoke_jti(db, jti, user_id, role, datetime.utcfromtimestamp(exp))


async def purge_expired_revocations(db: AsyncSession) -> None:
    """Drop rows whose underlying JWT has already expired naturally — once a token's `exp` has
    passed it can never be redeemed anyway, revoked or not, so keeping the row serves no purpose
    and would otherwise grow this table forever."""
    await db.execute(delete(RevokedToken).where(RevokedToken.expires_at <= datetime.utcnow()))
    await db.commit()


async def _sweep_expired_revocations_forever() -> None:
    """Background loop mirroring utils/cache.py's sweeper — periodically clears out rows that
    natural JWT expiry has already made irrelevant, independent of whether anyone ever looks
    them up again."""
    import database  # deferred: avoids a circular import at module load time

    while True:
        await asyncio.sleep(REVOCATION_SWEEP_INTERVAL_SECONDS)
        try:
            async with database.AsyncSessionLocal() as db:
                await purge_expired_revocations(db)
        except Exception as e:
            logger.error(f"revoked_tokens cleanup sweep failed: {e}")


def start_revocation_sweeper() -> None:
    """Call once from FastAPI's startup event."""
    global _sweep_task
    if _sweep_task is None:
        _sweep_task = asyncio.create_task(_sweep_expired_revocations_forever())


async def stop_revocation_sweeper() -> None:
    """Call once from FastAPI's shutdown event."""
    global _sweep_task
    if _sweep_task is not None:
        _sweep_task.cancel()
        try:
            await _sweep_task
        except asyncio.CancelledError:
            pass
        _sweep_task = None

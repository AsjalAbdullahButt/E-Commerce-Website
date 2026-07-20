from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

import database
from config import settings
from db.admin import AdminUser, AuditLog
from utils.helpers import create_access_token, create_refresh_token, decode_token, hash_password, verify_password
from utils.logger import get_logger, log_to_db
from utils.token_revocation import enforce_refresh_rotation, revoke_jti

logger = get_logger(__name__)

class AdminAuthService:
    """Authentication service for admin users"""

    @staticmethod
    async def create_admin_user(name: str, email: str, password: str, role: str) -> dict:
        """Create new admin user.

        Never called from a live route (only backend/seed/seed_admin.py and test setup code,
        confirmed via repo-wide grep) — always opens its own session rather than taking `db`,
        since there's no surrounding request transaction to join. `database.AsyncSessionLocal`
        is looked up dynamically (via `import database`, not `from database import
        AsyncSessionLocal`) so tests' monkey-patched session factory is honored.
        """
        async with database.AsyncSessionLocal() as db:
            existing = await db.execute(select(AdminUser).where(AdminUser.email == email))
            if existing.scalar_one_or_none():
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Admin with this email already exists"
                )

            password_hash = hash_password(password)
            admin = AdminUser(name=name, email=email, password_hash=password_hash, role=role)
            db.add(admin)
            await db.flush()
            await db.commit()

            logger.info(f"Admin user created: {email} with role {role}")
            return {"id": admin.id, "email": email, "role": role}

    @staticmethod
    async def authenticate(db: AsyncSession, email: str, password: str, ip_address: str) -> dict:
        """Authenticate admin user"""
        result = await db.execute(select(AdminUser).where(AdminUser.email == email))
        admin = result.scalar_one_or_none()

        if not admin:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials"
            )

        # Check if locked. Time-based, not permanent: auto-clears once admin_lockout_minutes has
        # elapsed since the lock, so anyone who knows an admin's email can't brick that account
        # (or every admin, including the only super_admin who could otherwise unlock it early via
        # unlock_account) forever with 25 requests.
        if admin.is_locked:
            lockout_expired = (
                admin.last_locked_at is not None
                and datetime.now(timezone.utc) >= admin.last_locked_at + timedelta(minutes=settings.admin_lockout_minutes)
            )
            if lockout_expired:
                admin.is_locked = False
                admin.failed_login_attempts = 0
                admin.last_locked_at = None
                await db.commit()
            else:
                raise HTTPException(
                    status_code=status.HTTP_423_LOCKED,
                    detail="Account is locked due to multiple failed login attempts"
                )

        # Verify password
        if not verify_password(password, admin.password_hash):
            # Increment failed attempts
            failed_attempts = admin.failed_login_attempts + 1
            is_locked = failed_attempts >= 5

            admin.failed_login_attempts = failed_attempts
            admin.is_locked = is_locked
            admin.last_locked_at = datetime.now(timezone.utc) if is_locked else None
            # Commit explicitly here: this method is about to raise HTTPException, and
            # database.py::get_db() rolls back the whole request's session on any exception
            # (deliberately, so e.g. a failed checkout doesn't leave a partial stock decrement
            # committed). The failed-attempt counter is different — it must durably persist
            # *because* the login failed, not in spite of it, so it can't ride on that same
            # commit-on-success path.
            await db.commit()

            logger.warning(f"Failed login attempt for {email} (attempt {failed_attempts})")

            if is_locked:
                raise HTTPException(
                    status_code=status.HTTP_423_LOCKED,
                    detail="Account locked after 5 failed attempts"
                )

            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials"
            )

        # Reset failed attempts on successful login
        admin.failed_login_attempts = 0
        admin.last_login = datetime.now(timezone.utc)

        # Create tokens
        access_token = create_access_token(admin.id, admin.role or "admin")
        refresh_token = create_refresh_token(admin.id, admin.role or "admin")

        logger.info(f"Admin {email} logged in successfully")

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "admin": {
                "id": admin.id,
                "name": admin.name,
                "email": admin.email,
                "role": admin.role,
            }
        }

    @staticmethod
    async def refresh_token(db: AsyncSession, refresh_token_str: str) -> dict:
        """Refresh access token using refresh token"""
        try:
            payload = decode_token(refresh_token_str)
            if payload.get("type") != "refresh":
                raise ValueError("Invalid token type. Expected refresh")
            admin_id = payload.get("sub")

            admin = await db.get(AdminUser, admin_id)
            if not admin or not admin.is_active:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Admin not found"
                )
            if admin.is_locked:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Account is locked"
                )

            await enforce_refresh_rotation(db, admin, payload)

            # Create new access token, and rotate the refresh token (same pattern as
            # routes/auth.py's customer /auth/refresh) so a leaked refresh token has a limited
            # window before it's superseded.
            access_token = create_access_token(admin.id, admin.role or "admin")
            new_refresh_token = create_refresh_token(admin.id, admin.role or "admin")

            return {
                "access_token": access_token,
                "refresh_token": new_refresh_token,
                "token_type": "bearer",
            }
        except HTTPException:
            raise
        except Exception as e:
            await log_to_db("ERROR", __name__, f"Token refresh error: {e}")
            logger.error(f"Token refresh error: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token"
            )

    @staticmethod
    async def logout(admin_id: str, ip_address: str) -> bool:
        """Logout admin (can implement token blacklist if needed)"""
        # For now, just log the logout
        logger.info(f"Admin {admin_id} logged out from {ip_address}")
        return True

    @staticmethod
    async def change_password(db: AsyncSession, admin_id: str, old_password: str, new_password: str) -> bool:
        """Change admin password"""
        admin = await db.get(AdminUser, admin_id)

        if not admin or not verify_password(old_password, admin.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Old password is incorrect"
            )

        admin.password_hash = hash_password(new_password)
        admin.updated_at = datetime.now(timezone.utc)

        logger.info(f"Password changed for admin {admin_id}")
        return True

    @staticmethod
    async def unlock_account(db: AsyncSession, admin_id: str, super_admin_id: str) -> bool:
        """Unlock locked admin account (super admin only)"""
        admin = await db.get(AdminUser, admin_id)
        if not admin:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Admin not found")

        admin.is_locked = False
        admin.failed_login_attempts = 0
        admin.updated_at = datetime.now(timezone.utc)

        # Log this action
        await AdminAuditService.log_action(
            admin_id=super_admin_id,
            admin_name="System",
            action="unlock_account",
            entity_type="admin_user",
            entity_id=admin_id,
            changes={"is_locked": {"old": True, "new": False}},
            ip_address="0.0.0.0"
        )

        logger.info(f"Account unlocked for admin {admin_id} by {super_admin_id}")
        return True


class AdminAuditService:
    """Audit logging service"""

    @staticmethod
    async def log_action(
        admin_id: str,
        admin_name: str,
        action: str,
        entity_type: str,
        entity_id: str,
        changes: dict,
        ip_address: str,
    ) -> str:
        """Log admin action for audit trail.

        Always opens its own session (see create_admin_user's docstring for why) — this also
        matches this write's original behavior under Mongo, where it was never atomic with
        whatever operation triggered it anyway (a separate insert_one call, same as here).
        """
        async with database.AsyncSessionLocal() as db:
            entry = AuditLog(
                entry_type="admin_action",
                admin_id=admin_id,
                admin_name=admin_name,
                action=action,
                entity_type=entity_type,
                entity_id=entity_id,
                changes=changes,
                ip_address=ip_address,
                timestamp=datetime.now(timezone.utc),
            )
            db.add(entry)
            await db.flush()
            await db.commit()
            return entry.id

    @staticmethod
    async def get_logs(
        db: AsyncSession,
        entity_type: Optional[str] = None,
        admin_id: Optional[str] = None,
        limit: int = 100,
        skip: int = 0,
    ) -> tuple:
        """Get audit logs with optional filtering"""
        query = select(AuditLog)
        count_query = select(func.count()).select_from(AuditLog)

        if entity_type:
            query = query.where(AuditLog.entity_type == entity_type)
            count_query = count_query.where(AuditLog.entity_type == entity_type)
        if admin_id:
            query = query.where(AuditLog.admin_id == admin_id)
            count_query = count_query.where(AuditLog.admin_id == admin_id)

        query = query.order_by(AuditLog.timestamp.desc()).offset(skip).limit(limit)

        result = await db.execute(query)
        entries = result.scalars().all()

        logs = [
            {
                "_id": e.id, "id": e.id, "entry_type": e.entry_type, "level": e.level,
                "module": e.module, "message": e.message, "meta": e.meta,
                "admin_id": e.admin_id, "admin_name": e.admin_name, "action": e.action,
                "entity_type": e.entity_type, "entity_id": e.entity_id, "changes": e.changes,
                "ip_address": e.ip_address, "timestamp": e.timestamp,
            }
            for e in entries
        ]

        total = (await db.execute(count_query)).scalar_one()

        return logs, total

from fastapi import HTTPException, status
from core.security import Security
from database import admin_users_col, audit_logs_col
from models.admin import admin_user_document, audit_log_document
from bson import ObjectId
from datetime import datetime
import logging

logger = logging.getLogger("admin_auth_service")

class AdminAuthService:
    """Authentication service for admin users"""

    @staticmethod
    async def create_admin_user(name: str, email: str, password: str, role: str) -> dict:
        """Create new admin user"""
        # Check if admin with email already exists
        existing = await admin_users_col.find_one({"email": email})
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Admin with this email already exists"
            )
        
        # Hash password
        password_hash = Security.hash_password(password)
        
        # Create document
        doc = admin_user_document(name, email, password_hash, role)
        result = await admin_users_col.insert_one(doc)
        
        logger.info(f"Admin user created: {email} with role {role}")
        return {"id": str(result.inserted_id), "email": email, "role": role}

    @staticmethod
    async def authenticate(email: str, password: str, ip_address: str) -> dict:
        """Authenticate admin user"""
        admin = await admin_users_col.find_one({"email": email})
        
        if not admin:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials"
            )
        
        # Check if locked
        if admin.get("is_locked", False):
            raise HTTPException(
                status_code=status.HTTP_423_LOCKED,
                detail="Account is locked due to multiple failed login attempts"
            )
        
        # Verify password
        if not Security.verify_password(password, admin["password_hash"]):
            # Increment failed attempts
            failed_attempts = admin.get("failed_login_attempts", 0) + 1
            is_locked = failed_attempts >= 5
            
            update_data = {
                "failed_login_attempts": failed_attempts,
                "is_locked": is_locked,
                "last_locked_at": datetime.utcnow() if is_locked else None,
            }
            
            await admin_users_col.update_one(
                {"_id": admin["_id"]},
                {"$set": update_data}
            )
            
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
        await admin_users_col.update_one(
            {"_id": admin["_id"]},
            {
                "$set": {
                    "failed_login_attempts": 0,
                    "last_login": datetime.utcnow(),
                }
            }
        )
        
        # Create tokens
        access_token = Security.create_access_token({"sub": str(admin["_id"])})
        refresh_token = Security.create_refresh_token({"sub": str(admin["_id"])})
        
        logger.info(f"Admin {email} logged in successfully")
        
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "admin": {
                "id": str(admin["_id"]),
                "name": admin["name"],
                "email": admin["email"],
                "role": admin["role"],
            }
        }

    @staticmethod
    async def refresh_token(refresh_token_str: str) -> dict:
        """Refresh access token using refresh token"""
        try:
            payload = Security.verify_token_type(refresh_token_str, "refresh")
            admin_id = payload.get("sub")
            
            admin = await admin_users_col.find_one(
                {"_id": ObjectId(admin_id), "is_active": True}
            )
            if not admin:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Admin not found"
                )
            
            # Create new access token
            access_token = Security.create_access_token({"sub": str(admin["_id"])})
            
            return {
                "access_token": access_token,
                "token_type": "bearer",
            }
        except Exception as e:
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
    async def change_password(admin_id: str, old_password: str, new_password: str) -> bool:
        """Change admin password"""
        admin = await admin_users_col.find_one({"_id": ObjectId(admin_id)})
        
        if not admin or not Security.verify_password(old_password, admin["password_hash"]):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Old password is incorrect"
            )
        
        new_hash = Security.hash_password(new_password)
        await admin_users_col.update_one(
            {"_id": ObjectId(admin_id)},
            {"$set": {"password_hash": new_hash, "updated_at": datetime.utcnow()}}
        )
        
        logger.info(f"Password changed for admin {admin_id}")
        return True

    @staticmethod
    async def unlock_account(admin_id: str, super_admin_id: str) -> bool:
        """Unlock locked admin account (super admin only)"""
        await admin_users_col.update_one(
            {"_id": ObjectId(admin_id)},
            {
                "$set": {
                    "is_locked": False,
                    "failed_login_attempts": 0,
                    "updated_at": datetime.utcnow(),
                }
            }
        )
        
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
        """Log admin action for audit trail"""
        doc = audit_log_document(
            admin_id=admin_id,
            admin_name=admin_name,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            changes=changes,
            ip_address=ip_address,
        )
        
        result = await audit_logs_col.insert_one(doc)
        return str(result.inserted_id)

    @staticmethod
    async def get_logs(
        entity_type: Optional[str] = None,
        admin_id: Optional[str] = None,
        limit: int = 100,
        skip: int = 0,
    ) -> tuple:
        """Get audit logs with optional filtering"""
        from typing import Optional
        
        query = {}
        if entity_type:
            query["entity_type"] = entity_type
        if admin_id:
            query["admin_id"] = admin_id
        
        cursor = audit_logs_col.find(query).sort("timestamp", -1).skip(skip).limit(limit)
        logs = await cursor.to_list(length=limit)
        
        # Convert ObjectId to string
        for log in logs:
            log["_id"] = str(log["_id"])
        
        total = await audit_logs_col.count_documents(query)
        
        return logs, total

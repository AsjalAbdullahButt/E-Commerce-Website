from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from jose import JWTError, jwt
from passlib.context import CryptContext
from config import settings

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

class Security:
    """JWT and password handling"""

    @staticmethod
    def hash_password(password: str) -> str:
        """Hash password using bcrypt"""
        return pwd_context.hash(password)

    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """Verify password"""
        return pwd_context.verify(plain_password, hashed_password)

    @staticmethod
    def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
        """Create JWT access token"""
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=settings.jwt_expire_minutes)
        
        to_encode.update({"exp": expire, "type": "access"})
        encoded_jwt = jwt.encode(to_encode, settings.jwt_secret, algorithm=settings.jwt_algorithm)
        return encoded_jwt

    @staticmethod
    def create_refresh_token(data: Dict[str, Any]) -> str:
        """Create JWT refresh token"""
        to_encode = data.copy()
        expire = datetime.utcnow() + timedelta(minutes=settings.jwt_refresh_expire_minutes)
        to_encode.update({"exp": expire, "type": "refresh"})
        encoded_jwt = jwt.encode(to_encode, settings.jwt_secret, algorithm=settings.jwt_algorithm)
        return encoded_jwt

    @staticmethod
    def decode_token(token: str) -> Dict[str, Any]:
        """Decode JWT token"""
        try:
            payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
            return payload
        except JWTError:
            raise ValueError("Invalid token")

    @staticmethod
    def verify_token_type(token: str, expected_type: str) -> Dict[str, Any]:
        """Verify token type (access or refresh)"""
        payload = Security.decode_token(token)
        if payload.get("type") != expected_type:
            raise ValueError(f"Invalid token type. Expected {expected_type}")
        return payload


# Role-based permissions mapping
ROLE_PERMISSIONS: Dict[str, list] = {
    "super_admin": [
        "product:create", "product:read", "product:update", "product:delete",
        "order:read", "order:update", "order:delete",
        "user:read", "user:update", "user:delete", "user:ban",
        "admin:read", "admin:create", "admin:update", "admin:delete",
        "audit:read", "inventory:read", "inventory:update",
        "promo:create", "promo:read", "promo:update", "promo:delete",
        "dashboard:read", "settings:update"
    ],
    "admin": [
        "product:create", "product:read", "product:update",
        "order:read", "order:update",
        "user:read", "user:update",
        "audit:read", "inventory:read", "inventory:update",
        "promo:create", "promo:read", "promo:update",
        "dashboard:read"
    ],
    "manager": [
        "product:read", "product:update",
        "order:read", "order:update",
        "user:read", "inventory:read",
        "dashboard:read", "promo:read"
    ],
    "support": [
        "order:read", "user:read",
        "dashboard:read"
    ]
}

def has_permission(role: str, permission: str) -> bool:
    """Check if role has permission"""
    permissions = ROLE_PERMISSIONS.get(role, [])
    return permission in permissions

from passlib.context import CryptContext
from jose import jwt, JWTError
from datetime import datetime, timedelta
from config import settings
import re

pwd_context = CryptContext(schemes=["bcrypt"], bcrypt__rounds=12, deprecated="auto")

def hash_password(password: str) -> str:
    """Hash a password using bcrypt (12 salt rounds)"""
    return pwd_context.hash(password)

def verify_password(plain: str, hashed: str) -> bool:
    """Verify a plain password against hashed version using constant-time comparison"""
    return pwd_context.verify(plain, hashed)

def create_access_token(user_id: str, role: str) -> str:
    """Create a JWT access token (15 minute expiry)"""
    expire = datetime.utcnow() + timedelta(minutes=settings.jwt_expire_minutes)
    payload = {
        "sub": user_id,
        "role": role,
        "exp": expire,
        "type": "access"
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)

def create_refresh_token(user_id: str, role: str) -> str:
    """Create a JWT refresh token (7 days expiry)"""
    expire = datetime.utcnow() + timedelta(days=7)
    payload = {
        "sub": user_id,
        "role": role,
        "exp": expire,
        "type": "refresh"
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict:
    """Decode JWT token."""
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except JWTError as exc:
        raise ValueError("Invalid token") from exc

def sanitize_input(value: str) -> str:
    """Prevent NoSQL injection by rejecting MongoDB operators"""
    if not isinstance(value, str):
        return value
    
    # Reject strings containing MongoDB operators
    dangerous_patterns = [
        r'\$where', r'\$regex', r'\$ne', r'\$gt', r'\$gte', r'\$lt', r'\$lte',
        r'\$in', r'\$nin', r'\$and', r'\$or', r'\$not', r'\$nor', r'\$exists',
        r'\$type', r'\$text'
    ]
    
    for pattern in dangerous_patterns:
        if re.search(pattern, value, re.IGNORECASE):
            raise ValueError("Input contains forbidden MongoDB operators")
    
    return value.strip()


class Security:
    """Backward-compatible wrapper for JWT/password helpers."""

    @staticmethod
    def hash_password(password: str) -> str:
        return hash_password(password)

    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        return verify_password(plain_password, hashed_password)

    @staticmethod
    def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
        payload = data.copy()
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=settings.jwt_expire_minutes)
        payload.update({"exp": expire, "type": "access"})
        return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)

    @staticmethod
    def create_refresh_token(data: dict) -> str:
        payload = data.copy()
        expire = datetime.utcnow() + timedelta(minutes=settings.jwt_refresh_expire_minutes)
        payload.update({"exp": expire, "type": "refresh"})
        return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)

    @staticmethod
    def decode_token(token: str) -> dict:
        return decode_token(token)

    @staticmethod
    def verify_token_type(token: str, expected_type: str) -> dict:
        payload = decode_token(token)
        if payload.get("type") != expected_type:
            raise ValueError(f"Invalid token type. Expected {expected_type}")
        return payload

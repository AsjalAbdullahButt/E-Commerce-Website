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
    expire = datetime.utcnow() + timedelta(minutes=settings.jwt_access_expire_minutes)
    payload = {
        "sub": user_id,
        "role": role,
        "exp": expire,
        "type": "access"
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)

def create_refresh_token(user_id: str, role: str) -> str:
    """Create a JWT refresh token (7 days expiry)"""
    expire = datetime.utcnow() + timedelta(minutes=settings.jwt_refresh_expire_minutes)
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

def sanitize_input(value: str, max_length: int = 500) -> str:
    """Prevent NoSQL injection by rejecting MongoDB operators, strip control characters, and
    enforce a maximum length. Used on every free-text field accepted from a client (names,
    addresses, review comments, admin notes/reasons) beyond whatever type-level validation
    Pydantic already does."""
    if not isinstance(value, str):
        return value

    value = value.strip()

    # Strip control characters (keep \n and \t, which are legitimate in multi-line free text)
    value = ''.join(ch for ch in value if ch in '\n\t' or ord(ch) >= 32)

    if len(value) > max_length:
        raise ValueError(f"Input exceeds maximum length of {max_length} characters")

    # Reject strings containing MongoDB operators
    dangerous_patterns = [
        r'\$where', r'\$regex', r'\$ne', r'\$gt', r'\$gte', r'\$lt', r'\$lte',
        r'\$in', r'\$nin', r'\$and', r'\$or', r'\$not', r'\$nor', r'\$exists',
        r'\$type', r'\$text'
    ]

    for pattern in dangerous_patterns:
        if re.search(pattern, value, re.IGNORECASE):
            raise ValueError("Input contains forbidden MongoDB operators")

    return value

from passlib.context import CryptContext
from jose import jwt
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

def create_refresh_token(user_id: str) -> str:
    """Create a JWT refresh token (7 days expiry)"""
    expire = datetime.utcnow() + timedelta(days=7)
    payload = {
        "sub": user_id,
        "exp": expire,
        "type": "refresh"
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)

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

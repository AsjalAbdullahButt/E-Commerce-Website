from passlib.context import CryptContext
from jose import jwt
from datetime import datetime, timedelta
from config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(password: str) -> str:
    """Hash a password using bcrypt"""
    return pwd_context.hash(password)

def verify_password(plain: str, hashed: str) -> bool:
    """Verify a plain password against hashed version"""
    return pwd_context.verify(plain, hashed)

def create_access_token(user_id: str, role: str) -> str:
    """Create a JWT access token"""
    expire = datetime.utcnow() + timedelta(minutes=settings.jwt_expire_minutes)
    payload = {
        "sub": user_id,
        "role": role,
        "exp": expire
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)

from passlib.context import CryptContext
from jose import jwt, JWTError
from datetime import datetime, timedelta, timezone
from config import settings
from utils.ids import new_id
import unicodedata

pwd_context = CryptContext(schemes=["bcrypt"], bcrypt__rounds=12, deprecated="auto")

def hash_password(password: str) -> str:
    """Hash a password using bcrypt (12 salt rounds)"""
    return pwd_context.hash(password)

def verify_password(plain: str, hashed: str) -> bool:
    """Verify a plain password against hashed version using constant-time comparison"""
    return pwd_context.verify(plain, hashed)

def create_access_token(user_id: str, role: str) -> str:
    """Create a JWT access token (15 minute expiry)"""
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_access_expire_minutes)
    payload = {
        "sub": user_id,
        "role": role,
        "exp": expire,
        "type": "access"
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)

def create_refresh_token(user_id: str, role: str) -> str:
    """Create a JWT refresh token (7 days expiry). `jti` + `iat` back the revocation/reuse-
    detection scheme in utils/token_revocation.py — a refresh token is meant to be single-use,
    and without a stable per-token identifier there'd be no way to record "this one was already
    redeemed" short of tracking the whole signed string."""
    issued_at = datetime.now(timezone.utc)
    expire = issued_at + timedelta(minutes=settings.jwt_refresh_expire_minutes)
    payload = {
        "sub": user_id,
        "role": role,
        "iat": issued_at,
        "exp": expire,
        "jti": new_id(),
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
    """Strip control characters, normalize Unicode (NFKC) so visually-identical characters
    compare/store consistently, reject null bytes, and enforce a maximum length. Used on every
    free-text field accepted from a client (names, addresses, review comments, admin
    notes/reasons) beyond whatever type-level validation Pydantic already does.

    This used to also reject any string containing a MongoDB query operator ($where, $ne, $gt,
    ...) — a leftover from this app's pre-migration Mongo backend. SQLAlchemy's parameter
    binding already prevents SQL injection on this MySQL app regardless of what characters a
    string contains, so that blacklist provided zero real protection while rejecting legitimate
    text that happened to contain one of those substrings (a review mentioning "$100 and
    worth it", a note with "qty $lte 5").
    """
    if not isinstance(value, str):
        return value

    # Null bytes are rejected outright rather than silently stripped like other control
    # characters below — they're a classic string-truncation/injection primitive (e.g. against
    # C-based libraries or filesystem APIs further down the stack) with no legitimate use in
    # free text, so failing loudly here is safer than quietly dropping them.
    if '\x00' in value:
        raise ValueError("Input contains a null byte")

    value = value.strip()
    value = unicodedata.normalize("NFKC", value)

    # Strip remaining control characters (keep \n and \t, which are legitimate in multi-line
    # free text).
    value = ''.join(ch for ch in value if ch in '\n\t' or ord(ch) >= 32)

    if len(value) > max_length:
        raise ValueError(f"Input exceeds maximum length of {max_length} characters")

    return value

"""Google Sign-In — ID-token verification flow.

The frontend (Google Identity Services button/one-tap) gets a signed ID token directly from
Google and POSTs it once to POST /auth/google; this module verifies it server-side against
Google's own public signing keys. No client secret, no authorization-code exchange, no
redirect URI, no server-side OAuth session — this app's existing JWT layer issues the real
session the moment the ID token checks out (routes/auth.py::google_login).

Never trust the token's claims before the signature check passes: `verify_id_token` always
validates signature -> issuer -> audience -> expiry -> email_verified, in that order, and
raises on the first failure.
"""
from typing import Any

import httpx
from fastapi import HTTPException
from jose import jwt

from config import settings
from utils.cache import cache_delete, cache_get, cache_set
from utils.logger import get_logger, log_to_db

logger = get_logger(__name__)

GOOGLE_JWKS_URL = "https://www.googleapis.com/oauth2/v3/certs"
# Google's tokens use either form depending on token type/age — both are legitimate.
GOOGLE_ISSUERS = {"accounts.google.com", "https://accounts.google.com"}
_JWKS_CACHE_KEY = "google_oauth:jwks"
_JWKS_DEFAULT_TTL_SECONDS = 3600


async def _fetch_jwks() -> dict:
    """Cached in utils/cache.py, honoring the endpoint's own Cache-Control: max-age so we refetch
    no more often than Google says is necessary (falls back to a 1-hour TTL if that header is
    ever missing)."""
    cached = await cache_get(_JWKS_CACHE_KEY)
    if cached is not None:
        return cached

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(GOOGLE_JWKS_URL)
    resp.raise_for_status()
    keys = resp.json()

    ttl = _JWKS_DEFAULT_TTL_SECONDS
    for directive in resp.headers.get("cache-control", "").split(","):
        directive = directive.strip()
        if directive.startswith("max-age="):
            try:
                ttl = max(60, int(directive.split("=", 1)[1]))
            except ValueError:
                pass

    await cache_set(_JWKS_CACHE_KEY, keys, ttl_seconds=ttl)
    return keys


async def verify_id_token(id_token: str) -> dict[str, Any]:
    """Returns the decoded claims (sub, email, email_verified, name, picture, ...) on success.
    Raises HTTPException(401) on any signature/issuer/audience/expiry/verification failure."""
    try:
        header = jwt.get_unverified_header(id_token)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid Google ID token")

    kid = header.get("kid")
    if not kid:
        raise HTTPException(status_code=401, detail="Invalid Google ID token")

    jwks = await _fetch_jwks()
    matching_key = next((k for k in jwks.get("keys", []) if k.get("kid") == kid), None)
    if not matching_key:
        # Google rotates signing keys periodically -- refetch once in case our cached set is
        # just stale, before giving up.
        await cache_delete(_JWKS_CACHE_KEY)
        jwks = await _fetch_jwks()
        matching_key = next((k for k in jwks.get("keys", []) if k.get("kid") == kid), None)
        if not matching_key:
            raise HTTPException(status_code=401, detail="Invalid Google ID token")

    try:
        claims = jwt.decode(
            id_token,
            matching_key,
            algorithms=["RS256"],
            audience=settings.google_client_id,
            options={"verify_iss": False},  # issuer checked manually below (two valid forms)
        )
    except Exception as e:
        await log_to_db("GOOGLE_OAUTH_TOKEN_REJECTED", __name__, f"ID token verification failed: {e}")
        raise HTTPException(status_code=401, detail="Invalid Google ID token")

    if claims.get("iss") not in GOOGLE_ISSUERS:
        raise HTTPException(status_code=401, detail="Invalid Google ID token issuer")

    if not claims.get("email_verified"):
        raise HTTPException(status_code=401, detail="Google account email is not verified")

    return claims

"""Double-submit-cookie CSRF protection for the two truly cookie-only-authenticated
endpoints: POST /auth/refresh and POST /admin/auth/refresh. Every other state-changing
endpoint (including /auth/logout and /admin/auth/logout) already requires a bearer
access token in the Authorization header, which a cross-site request cannot forge without
already having compromised the page via XSS — so CSRF tokens would be redundant there.

The refresh_token/admin_refresh_token cookies are already httpOnly + Secure + SameSite=Strict,
which alone blocks the cookie from being attached to any cross-site request in modern browsers.
This is defense-in-depth on top of that: a server-verified token protects against any future
weakening of the SameSite setting (e.g. a subdomain misconfiguration) or a browser that doesn't
enforce SameSite=Strict correctly.
"""
import secrets
from fastapi import HTTPException, Request, Response

CSRF_HEADER_NAME = "X-CSRF-Token"


def generate_csrf_token() -> str:
    return secrets.token_urlsafe(32)


def set_csrf_cookie(response: Response, cookie_name: str, token: str, secure: bool, max_age: int) -> None:
    # Deliberately NOT httponly — the frontend JS must read this value to echo it back in the
    # X-CSRF-Token header. It carries no authentication power on its own (an attacker who can
    # read this cookie could already read the page via XSS, at which point CSRF is moot).
    response.set_cookie(
        key=cookie_name,
        value=token,
        httponly=False,
        secure=secure,
        samesite="strict",
        max_age=max_age,
    )


def verify_csrf(request: Request, cookie_name: str) -> None:
    cookie_token = request.cookies.get(cookie_name)
    header_token = request.headers.get(CSRF_HEADER_NAME)
    if not cookie_token or not header_token or not secrets.compare_digest(cookie_token, header_token):
        raise HTTPException(status_code=403, detail="Missing or invalid CSRF token")

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from sqlalchemy import text
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from config import settings
from database import engine
from utils.limiter import limiter
from utils.logger import get_logger, log_to_db
from utils.cache import start_cache_sweeper, stop_cache_sweeper
from routes import auth, products, orders, reviews, wishlist, promos, rider, admin, payments
from middleware.admin_auth import AdminAuthMiddleware
import time

logger = get_logger(__name__)

app = FastAPI(
    title="E-Commerce API",
    description="Full-Stack E-Commerce Platform",
    version="2.0.0",
    docs_url="/docs" if settings.docs_enabled else None,
    redoc_url=None,
)

# ── Rate Limiting ──────────────────────────────────────────────────────────────
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ── Trusted Hosts (prevents Host-header injection) ────────────────────────────
# Only enforced in production — settings.trusted_hosts must be set to the real production
# hostname(s) via env var (comma-separated). Left off in development since local hostnames vary
# (localhost, 127.0.0.1, LAN IPs) and there's no attacker-reachable surface to protect.
if settings.is_production:
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=[h.strip() for h in settings.trusted_hosts.split(",") if h.strip()],
    )

# ── Admin Auth Middleware ─────────────────────────────────────────────────────
app.add_middleware(AdminAuthMiddleware)

# ── CORS ───────────────────────────────────────────────────────────────────────
origins = [o.strip() for o in settings.allowed_origins.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Requested-With"],
)

# ── Security Headers ───────────────────────────────────────────────────────────
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    start    = time.time()
    try:
        response = await call_next(request)
    except Exception as e:
        # Ensure middleware chain always returns a response
        await log_to_db("ERROR", __name__, f"Security headers middleware error: {e}")
        logger.exception(f"Security headers middleware error: {e}")
        return JSONResponse(status_code=500, content={"detail": "Server middleware error"})
    response.headers["X-Content-Type-Options"]    = "nosniff"
    response.headers["X-Frame-Options"]           = "DENY"
    response.headers["X-XSS-Protection"]          = "1; mode=block"
    if settings.cookie_secure:
        response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
    response.headers["Referrer-Policy"]           = "strict-origin-when-cross-origin"
    response.headers["Cache-Control"]             = "no-store"
    # Content Security Policy — allow trusted CDNs used by frontend
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' https://cdnjs.cloudflare.com; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://cdnjs.cloudflare.com; "
        "font-src https://fonts.gstatic.com; "
        "img-src 'self' data: https:; "
        "connect-src 'self' https: ws:;"
    )
    response.headers["X-Response-Time"]           = f"{round((time.time()-start)*1000,2)}ms"
    return response


@app.middleware("http")
async def add_request_id(request: Request, call_next):
    request.state.request_id = str(__import__('uuid').uuid4())[:8]
    try:
        response = await call_next(request)
    except Exception as e:
        await log_to_db("ERROR", __name__, f"Request ID middleware error: {e}")
        logger.exception(f"Request ID middleware error: {e}")
        return JSONResponse(status_code=500, content={"detail": "Server middleware error"})
    try:
        response.headers["X-Request-ID"] = request.state.request_id
    except Exception:
        pass
    return response

# ── Startup ────────────────────────────────────────────────────────────────────
def check_single_worker_deployment() -> None:
    """utils/cache.py and utils/limiter.py are process-local in-memory stores (no Redis or other
    shared backend). Running more than one worker process means each worker has its own
    independent cache and rate-limit counters, so cache invalidation and rate limits silently
    stop being consistent across requests. Fail fast in production rather than degrade silently;
    warn loudly elsewhere so local perf testing with multiple workers isn't blocked outright."""
    if settings.web_concurrency <= 1:
        return
    message = (
        f"web_concurrency={settings.web_concurrency} but utils/cache.py and utils/limiter.py "
        "are process-local (no Redis backend) — cache invalidation and rate limits will be "
        "inconsistent across workers. Set WEB_CONCURRENCY=1 (single worker) or wire up a shared "
        "Redis-backed cache/limiter before scaling horizontally."
    )
    if settings.is_production:
        raise RuntimeError(message)
    print(f"    ⚠️  {message}\n")


@app.on_event("startup")
async def startup_db_check():
    check_single_worker_deployment()
    start_cache_sweeper()
    print("\n    ╔════════════════════════════════════╗")
    print("    ║   🛍️  E-COMMERCE API v2.0  🛍️      ║")
    print("    ╠════════════════════════════════════╣")
    print("    ║  📊 Connecting to Database...     ║")
    print("    ╚════════════════════════════════════╝\n")
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        print("    ✅  MySQL connected — server ready on :8000\n")
        print("    ✅  Schema managed by Alembic (see backend/alembic/) — indexes/constraints")
        print("        are declared on the SQLAlchemy models, not created at runtime.")
    except Exception as e:
        print(f"    ❌  MySQL FAILED: {e}\n")
        raise RuntimeError(f"Cannot connect to MySQL: {e}")

# ── Routes ─────────────────────────────────────────────────────────────────────
app.include_router(auth.router,     prefix="/auth",     tags=["Auth"])
app.include_router(products.router, prefix="/products", tags=["Products"])
app.include_router(orders.router,   prefix="/orders",   tags=["Orders"])
app.include_router(reviews.router,  prefix="/reviews",  tags=["Reviews"])
app.include_router(wishlist.router, prefix="/wishlist", tags=["Wishlist"])
app.include_router(promos.router,   prefix="/promos",   tags=["Promos"])
app.include_router(rider.router,    prefix="/rider",    tags=["Rider"])
app.include_router(admin.router,    prefix="/admin",    tags=["Admin"])
app.include_router(payments.router, prefix="/payments", tags=["Payments"])
# Note: admin_new merged into admin.py — only the canonical admin router is mounted.
# Note: routes/users.py (duplicate ban/unban/delete gated only by role membership, not the
# granular permission matrix) was deleted — /admin/users/* is the single path for user
# management.

@app.get("/", tags=["Health"])
async def root():
    return {"status": "ok", "version": "2.0.0"}

@app.on_event("shutdown")
async def shutdown_db():
    await stop_cache_sweeper()
    try:
        await engine.dispose()
        print("MySQL connection pool closed.")
    except Exception:
        pass


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)


@app.exception_handler(Exception)
async def handle_uncaught_exceptions(request: Request, exc: Exception):
    try:
        await log_to_db("ERROR", __name__, f"Unhandled exception: {exc}", {"path": str(request.url)})
    except Exception:
        logger.exception('Failed to write uncaught exception to audit log')
    logger.exception('Unhandled exception')
    return JSONResponse(status_code=500, content={"detail": "Internal Server Error"})

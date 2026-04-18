from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from config import settings
from database import client
from utils.limiter import limiter
from routes import auth, products, orders, reviews, wishlist, promos, users, rider
import time

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
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["localhost", "127.0.0.1", "*.yourdomain.com"]
)

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
    response = await call_next(request)
    response.headers["X-Content-Type-Options"]    = "nosniff"
    response.headers["X-Frame-Options"]           = "DENY"
    response.headers["X-XSS-Protection"]          = "1; mode=block"
    response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
    response.headers["Referrer-Policy"]           = "strict-origin-when-cross-origin"
    response.headers["Cache-Control"]             = "no-store"
    response.headers["X-Response-Time"]           = f"{round((time.time()-start)*1000,2)}ms"
    return response

# ── Startup ────────────────────────────────────────────────────────────────────
@app.on_event("startup")
async def startup_db_check():
    print("\n    ╔════════════════════════════════════╗")
    print("    ║   🛍️  E-COMMERCE API v2.0  🛍️      ║")
    print("    ╠════════════════════════════════════╣")
    print("    ║  📊 Connecting to Database...     ║")
    print("    ╚════════════════════════════════════╝\n")
    try:
        await client.admin.command("ping")
        print("    ✅  MongoDB connected — server ready on :8000\n")
    except Exception as e:
        print(f"    ❌  MongoDB FAILED: {e}\n")
        raise RuntimeError(f"Cannot connect to MongoDB: {e}")

# ── Routes ─────────────────────────────────────────────────────────────────────
app.include_router(auth.router,     prefix="/auth",     tags=["Auth"])
app.include_router(products.router, prefix="/products", tags=["Products"])
app.include_router(orders.router,   prefix="/orders",   tags=["Orders"])
app.include_router(reviews.router,  prefix="/reviews",  tags=["Reviews"])
app.include_router(wishlist.router, prefix="/wishlist", tags=["Wishlist"])
app.include_router(promos.router,   prefix="/promos",   tags=["Promos"])
app.include_router(users.router,    prefix="/users",    tags=["Users"])
app.include_router(rider.router,    prefix="/rider",    tags=["Rider"])

@app.get("/", tags=["Health"])
async def root():
    return {"status": "ok", "version": "2.0.0"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

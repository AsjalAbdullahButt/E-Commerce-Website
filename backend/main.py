from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from config import settings
from database import client
from utils.limiter import limiter
from routes import auth, products, orders, reviews, wishlist, promos, users, rider

app = FastAPI(
    title="E-Commerce API",
    description="Full-Stack E-Commerce Platform",
    version="1.0.0"
)

# Rate Limiting
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS Configuration
origins = [o.strip() for o in settings.allowed_origins.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Startup event - MongoDB connection check
@app.on_event("startup")
async def startup_db_check():
    # Display E-Commerce banner
    banner = """
    ╔════════════════════════════════════╗
    ║   🛍️  E-COMMERCE API  🛍️          ║
    ╠════════════════════════════════════╣
    ║  📊 Connecting to Database...     ║
    ╚════════════════════════════════════╝
    """
    print(banner)
    
    try:
        await client.admin.command('ping')
        success_msg = """
    ╔════════════════════════════════════╗
    ║  ✅ Database Connected            ║
    ║  🚀 Server Ready!                  ║    ╠════════════════════════════════════╣
    ║  🔌 Backend: 127.0.0.1:8000       ║
    ║  🌐 Frontend: 127.0.0.1:5500      ║    ║  📝 Docs: 127.0.0.1:8000/docs     ║
    ╚════════════════════════════════════╝
        """
        print(success_msg)
    except Exception as e:
        print(f"❌ MongoDB connection FAILED: {e}")
        raise RuntimeError(f"Cannot connect to MongoDB. Check MONGODB_URI in .env — {e}")

# Routes
app.include_router(auth.router,     prefix="/auth",     tags=["Auth"])
app.include_router(products.router, prefix="/products", tags=["Products"])
app.include_router(orders.router,   prefix="/orders",   tags=["Orders"])
app.include_router(reviews.router,  prefix="/reviews",  tags=["Reviews"])
app.include_router(wishlist.router, prefix="/wishlist", tags=["Wishlist"])
app.include_router(promos.router,   prefix="/promos",   tags=["Promos"])
app.include_router(users.router,    prefix="/users",    tags=["Users"])
app.include_router(rider.router,    prefix="/rider",    tags=["Rider"])

@app.get("/")
async def root():
    """Health check"""
    return {
        "status": "ok",
        "message": "E-Commerce API running",
        "docs": "http://127.0.0.1:8000/docs"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

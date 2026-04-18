from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from config import settings
from routes import auth, products, orders, reviews, wishlist, promos, users, rider

app = FastAPI(
    title="Tribe of 5 API",
    description="Premium Pakistani E-Commerce Platform",
    version="1.0.0"
)

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        settings.frontend_url,
        "http://127.0.0.1:5500",
        "http://localhost:5500",
        "http://localhost:3000"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
        "message": "Tribe of 5 API running",
        "docs": "http://localhost:8000/docs"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

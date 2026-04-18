import asyncio
import os
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv
from passlib.context import CryptContext
from datetime import datetime

load_dotenv()

pwd = CryptContext(schemes=["bcrypt"])
client = AsyncIOMotorClient(os.getenv("MONGODB_URI"))
db = client.E_Commerce

# ═══════════════════════════════════════════════════════════
# GENERAL E-COMMERCE PRODUCTS (6 categories, 12 products)
# ═══════════════════════════════════════════════════════════
PRODUCTS = [
    # ━━━━━ CLOTHING (2 products) ━━━━━
    {
        "name": "Premium Cotton Oversized Tee",
        "price": 1499,
        "category": "clothing",
        "subcategory": "t-shirts",
        "brand": "E-COM Originals",
        "description": "Ultra-soft 100% cotton oversized t-shirt. Perfect for everyday wear. Premium quality, comfortable fit.",
        "images": ["https://via.placeholder.com/600x600/1a1a1a/FFD700?text=Tee"],
        "sizes": ["S", "M", "L", "XL", "XXL"],
        "colors": [{"name": "Black", "hex": "#1a1a1a"}, {"name": "White", "hex": "#ffffff"}],
        "stock": 50,
        "tags": ["cotton", "oversized", "casual"],
        "rating": 4.5,
        "review_count": 12,
        "is_active": True,
        "created_at": datetime.utcnow().isoformat()
    },
    {
        "name": "Slim Fit Chinos",
        "price": 2499,
        "category": "clothing",
        "subcategory": "pants",
        "brand": "E-COM Originals",
        "description": "Comfortable slim-fit chinos for office and casual wear. Premium cotton blend.",
        "images": ["https://via.placeholder.com/600x600/2a2a2a/FFD700?text=Chinos"],
        "sizes": ["28", "30", "32", "34", "36"],
        "colors": [{"name": "Khaki", "hex": "#c3a882"}, {"name": "Navy", "hex": "#1a2a4a"}],
        "stock": 30,
        "tags": ["slim", "office", "casual"],
        "rating": 4.2,
        "review_count": 8,
        "is_active": True,
        "created_at": datetime.utcnow().isoformat()
    },
    
    # ━━━━━ ELECTRONICS (2 products) ━━━━━
    {
        "name": "Wireless Bluetooth Earbuds",
        "price": 3999,
        "category": "electronics",
        "subcategory": "audio",
        "brand": "SoundPro",
        "description": "True wireless earbuds with 24hr battery life and active noise cancellation. Premium sound quality.",
        "images": ["https://via.placeholder.com/600x600/111111/FFD700?text=Earbuds"],
        "sizes": [],
        "colors": [{"name": "Black", "hex": "#111111"}, {"name": "White", "hex": "#f5f5f5"}],
        "stock": 20,
        "tags": ["wireless", "audio", "earbuds"],
        "rating": 4.7,
        "review_count": 35,
        "is_active": True,
        "created_at": datetime.utcnow().isoformat()
    },
    {
        "name": "Fast Charging Power Bank 20000mAh",
        "price": 2999,
        "category": "electronics",
        "subcategory": "accessories",
        "brand": "ChargeMate",
        "description": "20000mAh capacity, 65W fast charging, dual USB-C ports. Perfect for travel.",
        "images": ["https://via.placeholder.com/600x600/1a1a2a/FFD700?text=PowerBank"],
        "sizes": [],
        "colors": [{"name": "Black", "hex": "#1a1a1a"}],
        "stock": 15,
        "tags": ["charging", "powerbank", "travel"],
        "rating": 4.4,
        "review_count": 22,
        "is_active": True,
        "created_at": datetime.utcnow().isoformat()
    },
    
    # ━━━━━ BOOKS (2 products) ━━━━━
    {
        "name": "Atomic Habits — James Clear",
        "price": 899,
        "category": "books",
        "subcategory": "self-help",
        "brand": "Penguin",
        "description": "The #1 New York Times bestseller. Transform your life with tiny changes. Read about building better habits.",
        "images": ["https://via.placeholder.com/600x600/0a0a1a/FFD700?text=AtomicHabits"],
        "sizes": [],
        "colors": [],
        "stock": 100,
        "tags": ["habits", "self-help", "bestseller"],
        "rating": 4.9,
        "review_count": 88,
        "is_active": True,
        "created_at": datetime.utcnow().isoformat()
    },
    {
        "name": "Deep Work — Cal Newport",
        "price": 799,
        "category": "books",
        "subcategory": "productivity",
        "brand": "Grand Central",
        "description": "Rules for focused success in a distracted world. Master the art of deep work.",
        "images": ["https://via.placeholder.com/600x600/1a0a0a/FFD700?text=DeepWork"],
        "sizes": [],
        "colors": [],
        "stock": 75,
        "tags": ["focus", "productivity", "career"],
        "rating": 4.8,
        "review_count": 54,
        "is_active": True,
        "created_at": datetime.utcnow().isoformat()
    },
    
    # ━━━━━ HOME & LIVING (2 products) ━━━━━
    {
        "name": "Aromatherapy Diffuser",
        "price": 1799,
        "category": "home",
        "subcategory": "decor",
        "brand": "ZenHome",
        "description": "Ultrasonic essential oil diffuser with 7-color LED light. Create a relaxing atmosphere.",
        "images": ["https://via.placeholder.com/600x600/1a1510/FFD700?text=Diffuser"],
        "sizes": [],
        "colors": [{"name": "White", "hex": "#f5f5f5"}],
        "stock": 25,
        "tags": ["aromatherapy", "home", "relaxation"],
        "rating": 4.3,
        "review_count": 19,
        "is_active": True,
        "created_at": datetime.utcnow().isoformat()
    },
    {
        "name": "Ceramic Coffee Mug Set (4 pcs)",
        "price": 1299,
        "category": "home",
        "subcategory": "kitchen",
        "brand": "CeramicArt",
        "description": "Handcrafted ceramic mugs, dishwasher safe, 350ml each. Perfect for coffee lovers.",
        "images": ["https://via.placeholder.com/600x600/201a10/FFD700?text=MugSet"],
        "sizes": [],
        "colors": [{"name": "Terracotta", "hex": "#c06040"}],
        "stock": 40,
        "tags": ["mug", "kitchen", "coffee"],
        "rating": 4.6,
        "review_count": 31,
        "is_active": True,
        "created_at": datetime.utcnow().isoformat()
    },
    
    # ━━━━━ SPORTS & FITNESS (2 products) ━━━━━
    {
        "name": "Resistance Bands Set (5 levels)",
        "price": 999,
        "category": "sports",
        "subcategory": "fitness",
        "brand": "FitPro",
        "description": "5-pack latex resistance bands for home gym workout. Different resistance levels.",
        "images": ["https://via.placeholder.com/600x600/0a1a0a/FFD700?text=ResistanceBands"],
        "sizes": [],
        "colors": [],
        "stock": 60,
        "tags": ["fitness", "gym", "resistance"],
        "rating": 4.5,
        "review_count": 47,
        "is_active": True,
        "created_at": datetime.utcnow().isoformat()
    },
    {
        "name": "Yoga Mat Non-Slip 6mm",
        "price": 1599,
        "category": "sports",
        "subcategory": "yoga",
        "brand": "FlexZone",
        "description": "Eco-friendly TPE yoga mat with alignment lines, 183x61cm. Non-slip surface for safety.",
        "images": ["https://via.placeholder.com/600x600/0a180a/FFD700?text=YogaMat"],
        "sizes": [],
        "colors": [{"name": "Purple", "hex": "#6b21a8"}, {"name": "Teal", "hex": "#0d9488"}],
        "stock": 35,
        "tags": ["yoga", "fitness", "mat"],
        "rating": 4.4,
        "review_count": 28,
        "is_active": True,
        "created_at": datetime.utcnow().isoformat()
    },
    
    # ━━━━━ BEAUTY & GROOMING (2 products) ━━━━━
    {
        "name": "Vitamin C Face Serum 30ml",
        "price": 1199,
        "category": "beauty",
        "subcategory": "skincare",
        "brand": "GlowLab",
        "description": "Brightening 20% Vitamin C serum with hyaluronic acid. Boost your skin radiance.",
        "images": ["https://via.placeholder.com/600x600/1a0f0a/FFD700?text=VitCSerum"],
        "sizes": [],
        "colors": [],
        "stock": 45,
        "tags": ["skincare", "vitamin-c", "brightening"],
        "rating": 4.7,
        "review_count": 63,
        "is_active": True,
        "created_at": datetime.utcnow().isoformat()
    },
    {
        "name": "Beard Grooming Kit",
        "price": 1899,
        "category": "beauty",
        "subcategory": "grooming",
        "brand": "ManCraft",
        "description": "Complete beard kit: oil, balm, comb, and scissors. Gift-ready box included.",
        "images": ["https://via.placeholder.com/600x600/10100a/FFD700?text=BeardKit"],
        "sizes": [],
        "colors": [],
        "stock": 20,
        "tags": ["beard", "grooming", "gift"],
        "rating": 4.6,
        "review_count": 41,
        "is_active": True,
        "created_at": datetime.utcnow().isoformat()
    },
]

async def seed():
    print("🔧 Clearing existing data...")
    await db.products.delete_many({})
    await db.users.delete_many({"role": "admin"})
    await db.users.delete_many({"role": "rider"})
    await db.users.delete_many({"email": "customer@ecommerce.com"})

    # Insert products
    await db.products.insert_many(PRODUCTS)
    print(f"✅ {len(PRODUCTS)} products inserted across 6 categories")

    # Insert admin (with hashed password)
    await db.users.insert_one({
        "name": "Admin User",
        "email": "admin@ecommerce.com",
        "password": pwd.hash("admin123"),
        "role": "admin",
        "phone": "03001234567",
        "created_at": datetime.utcnow().isoformat()
    })
    print("✅ Admin → admin@ecommerce.com / admin123")

    # Insert rider (with hashed password)
    if not await db.users.find_one({"email": "rider@ecommerce.com"}):
        await db.users.insert_one({
            "name": "Rider Ali",
            "email": "rider@ecommerce.com",
            "password": pwd.hash("rider123"),
            "role": "rider",
            "phone": "03111234567",
            "created_at": datetime.utcnow().isoformat()
        })
        print("✅ Rider → rider@ecommerce.com / rider123")

    # Insert test customer (with hashed password)
    if not await db.users.find_one({"email": "customer@ecommerce.com"}):
        await db.users.insert_one({
            "name": "Test Customer",
            "email": "customer@ecommerce.com",
            "password": pwd.hash("test123"),
            "role": "customer",
            "phone": "03211234567",
            "created_at": datetime.utcnow().isoformat()
        })
        print("✅ Customer → customer@ecommerce.com / test123")

    print("\n🎉 Seed complete!")
    print("Run: uvicorn main:app --reload --port 8000")

asyncio.run(seed())


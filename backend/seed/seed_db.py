import asyncio
import os
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv
from passlib.context import CryptContext
from datetime import datetime

load_dotenv()

pwd = CryptContext(schemes=["bcrypt"])
client = AsyncIOMotorClient(os.getenv("MONGODB_URI"))
db = client.tribeOf5

PRODUCTS = [
    {
        "name": "Plain Black",
        "price": 1999.0,
        "category": "t-shirts",
        "description": "Embrace the shadows. Premium soft cotton drop-shoulder tee.",
        "images": ["./images/Shirt_01.jpg"],
        "sizes": ["S", "M", "L", "XL"],
        "colors": [{"name": "Black", "hex": "#000000"}, {"name": "White", "hex": "#FFFFFF"}],
        "stock": 50
    },
    {
        "name": "Plain Turquoise",
        "price": 2199.0,
        "category": "t-shirts",
        "description": "Step into elegance. Vibrant turquoise oversized fit.",
        "images": ["./images/Shirt_02.jpg"],
        "sizes": ["M", "L", "XL"],
        "colors": [{"name": "Turquoise", "hex": "#40E0D0"}, {"name": "Dark Grey", "hex": "#36454F"}],
        "stock": 40
    },
    {
        "name": "Plain White",
        "price": 1999.0,
        "category": "t-shirts",
        "description": "Clean and classic. The essential white drop-shoulder tee.",
        "images": ["./images/Shirt_03.jpg"],
        "sizes": ["S", "M", "L", "XL"],
        "colors": [{"name": "White", "hex": "#FFFFFF"}, {"name": "Black", "hex": "#000000"}],
        "stock": 60
    },
    {
        "name": "Black Design",
        "price": 2199.0,
        "category": "t-shirts",
        "description": "Bold graphic on a dark base. Urban streetwear statement.",
        "images": ["./images/Shirt_04.jpg"],
        "sizes": ["M", "L"],
        "colors": [{"name": "Black", "hex": "#000000"}],
        "stock": 30
    },
    {
        "name": "Multi Color",
        "price": 1999.0,
        "category": "t-shirts",
        "description": "Retro-futuristic vibes. Gradient multicolor oversized fit.",
        "images": ["./images/Shirt_05.jpg"],
        "sizes": ["M", "L", "XL"],
        "colors": [{"name": "White", "hex": "#FFFFFF"}],
        "stock": 45
    },
    {
        "name": "Blue Animated",
        "price": 2499.0,
        "category": "t-shirts",
        "description": "Electric blue with animated print. Stand out everywhere.",
        "images": ["./images/Shirt_06.jpg"],
        "sizes": ["M", "L", "XL"],
        "colors": [{"name": "Blue", "hex": "#0000FF"}],
        "stock": 25
    },
    {
        "name": "Orange Black Mix",
        "price": 2499.0,
        "category": "t-shirts",
        "description": "Bold contrast of orange and black. Power statement.",
        "images": ["./images/Shirt_07.jpg"],
        "sizes": ["M", "L", "XL"],
        "colors": [{"name": "Orange", "hex": "#FFA500"}, {"name": "Black", "hex": "#000000"}],
        "stock": 20
    },
    {
        "name": "Plain Blue",
        "price": 1999.0,
        "category": "t-shirts",
        "description": "Simple and clean. Pure blue drop-shoulder comfort.",
        "images": ["./images/Shirt_08.jpg"],
        "sizes": ["M", "L", "XL"],
        "colors": [{"name": "Blue", "hex": "#0047AB"}],
        "stock": 55
    },
    {
        "name": "Royal Blue",
        "price": 2499.0,
        "category": "t-shirts",
        "description": "A classy royal blue reflecting elegance and charm. Stitched to perfection.",
        "images": ["./images/Shirt_09.jpg"],
        "sizes": ["M", "L", "XL"],
        "colors": [{"name": "Royal Blue", "hex": "#4169E1"}],
        "stock": 35
    },
]

async def seed():
    print("🔧 Clearing existing data...")
    await db.products.delete_many({})
    await db.users.delete_many({"role": "admin"})
    await db.users.delete_many({"role": "rider"})
    await db.users.delete_many({"email": "customer@test.com"})

    # Add metadata to products
    for p in PRODUCTS:
        p.update({
            "rating": 0.0,
            "review_count": 0,
            "is_active": True,
            "created_at": datetime.utcnow().isoformat()
        })

    # Insert products
    await db.products.insert_many(PRODUCTS)
    print(f"✅ {len(PRODUCTS)} products inserted")

    # Insert admin
    await db.users.insert_one({
        "name": "Admin",
        "email": "admin@tribeof5.com",
        "password": pwd.hash("admin123"),
        "role": "admin",
        "phone": "03001234567",
        "created_at": datetime.utcnow().isoformat()
    })
    print("✅ Admin → admin@tribeof5.com / admin123")

    # Insert rider
    if not await db.users.find_one({"email": "rider@tribeof5.com"}):
        await db.users.insert_one({
            "name": "Test Rider",
            "email": "rider@tribeof5.com",
            "password": pwd.hash("rider123"),
            "role": "rider",
            "phone": "03001112233",
            "created_at": datetime.utcnow().isoformat()
        })
        print("✅ Rider → rider@tribeof5.com / rider123")

    # Insert test customer
    if not await db.users.find_one({"email": "customer@test.com"}):
        await db.users.insert_one({
            "name": "Test Customer",
            "email": "customer@test.com",
            "password": pwd.hash("test123"),
            "role": "customer",
            "phone": "03009876543",
            "created_at": datetime.utcnow().isoformat()
        })
        print("✅ Customer → customer@test.com / test123")

    print("\n🎉 Seed complete!")
    print("Run: uvicorn main:app --reload --port 8000")

asyncio.run(seed())

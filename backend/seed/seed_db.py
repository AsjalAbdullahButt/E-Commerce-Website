"""
Seed script for E-Commerce database
Inserts: 20 products (12 clothing + 8 accessories), 3 users, 3 sample orders
"""

import asyncio
import os
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv
from passlib.context import CryptContext
from datetime import datetime
from bson import ObjectId

load_dotenv()

pwd = CryptContext(schemes=["bcrypt"], rounds=12)

MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
DB_NAME = os.getenv("DATABASE_NAME", "E_Commerce")

client = AsyncIOMotorClient(MONGODB_URI)
db = client[DB_NAME]

# ═════════════════════════════════════════════════════════════════════════════
# PRODUCTS: 20 Items (12 Clothing + 8 Accessories) - All prices in PKR
# ═════════════════════════════════════════════════════════════════════════════

PRODUCTS = [
    # ━━━━━ CLOTHING (12 items) ━━━━━
    {"name": "Classic White T-Shirt", "price": 1200, "category": "clothing", "description": "Premium 100% cotton classic white t-shirt.", "images": ["https://via.placeholder.com/600x600/ffffff/000000?text=WhiteTee"], "sizes": ["S", "M", "L", "XL"], "colors": [{"name": "White", "hex": "#ffffff"}, {"name": "Black", "hex": "#000000"}], "stock": 100, "rating": 4.5, "review_count": 0, "is_active": True, "created_at": datetime.utcnow().isoformat()},
    {"name": "Oversized Black Hoodie", "price": 3500, "category": "clothing", "description": "Comfortable oversized hoodie in premium fabric.", "images": ["https://via.placeholder.com/600x600/1a1a1a/ffffff?text=Hoodie"], "sizes": ["M", "L", "XL", "XXL"], "colors": [{"name": "Black", "hex": "#000000"}, {"name": "Grey", "hex": "#808080"}], "stock": 75, "rating": 4.7, "review_count": 0, "is_active": True, "created_at": datetime.utcnow().isoformat()},
    {"name": "Slim Fit Jeans", "price": 4200, "category": "clothing", "description": "Classic slim fit jeans with premium denim.", "images": ["https://via.placeholder.com/600x600/1a3a7a/ffffff?text=Jeans"], "sizes": ["30", "32", "34", "36"], "colors": [{"name": "Blue", "hex": "#0000ff"}, {"name": "Black", "hex": "#000000"}], "stock": 80, "rating": 4.6, "review_count": 0, "is_active": True, "created_at": datetime.utcnow().isoformat()},
    {"name": "Striped Polo Shirt", "price": 1800, "category": "clothing", "description": "Classic striped polo shirt for casual and formal occasions.", "images": ["https://via.placeholder.com/600x600/1a2a4a/ffffff?text=Polo"], "sizes": ["S", "M", "L"], "colors": [{"name": "Navy", "hex": "#001a4d"}, {"name": "White", "hex": "#ffffff"}], "stock": 60, "rating": 4.4, "review_count": 0, "is_active": True, "created_at": datetime.utcnow().isoformat()},
    {"name": "Graphic Tee - Urban", "price": 1500, "category": "clothing", "description": "Urban style graphic t-shirt with unique design.", "images": ["https://via.placeholder.com/600x600/2a2a2a/ffff00?text=GraphicTee"], "sizes": ["S", "M", "L", "XL"], "colors": [{"name": "White", "hex": "#ffffff"}, {"name": "Grey", "hex": "#808080"}], "stock": 90, "rating": 4.3, "review_count": 0, "is_active": True, "created_at": datetime.utcnow().isoformat()},
    {"name": "Cargo Pants", "price": 3800, "category": "clothing", "description": "Durable cargo pants with multiple pockets for functionality.", "images": ["https://via.placeholder.com/600x600/8b8b5a/ffffff?text=Cargo"], "sizes": ["30", "32", "34"], "colors": [{"name": "Khaki", "hex": "#c3b091"}, {"name": "Black", "hex": "#000000"}], "stock": 50, "rating": 4.2, "review_count": 0, "is_active": True, "created_at": datetime.utcnow().isoformat()},
    {"name": "Denim Jacket", "price": 5500, "category": "clothing", "description": "Premium denim jacket perfect for layering in any season.", "images": ["https://via.placeholder.com/600x600/1a3a7a/ffffff?text=DenimJacket"], "sizes": ["S", "M", "L", "XL"], "colors": [{"name": "Blue", "hex": "#0000ff"}, {"name": "Black", "hex": "#000000"}], "stock": 40, "rating": 4.8, "review_count": 0, "is_active": True, "created_at": datetime.utcnow().isoformat()},
    {"name": "Tracksuit Set", "price": 4800, "category": "clothing", "description": "Comfortable matching tracksuit for casual and active wear.", "images": ["https://via.placeholder.com/600x600/1a1a1a/ffffff?text=Tracksuit"], "sizes": ["M", "L", "XL"], "colors": [{"name": "Black", "hex": "#000000"}, {"name": "Navy", "hex": "#001a4d"}], "stock": 55, "rating": 4.5, "review_count": 0, "is_active": True, "created_at": datetime.utcnow().isoformat()},
    {"name": "Linen Summer Shirt", "price": 2200, "category": "clothing", "description": "Breathable linen shirt perfect for summer. Cool and comfortable.", "images": ["https://via.placeholder.com/600x600/f5f5dc/000000?text=Linen"], "sizes": ["S", "M", "L", "XL"], "colors": [{"name": "White", "hex": "#ffffff"}, {"name": "Beige", "hex": "#f5f5dc"}], "stock": 70, "rating": 4.3, "review_count": 0, "is_active": True, "created_at": datetime.utcnow().isoformat()},
    {"name": "Printed Shorts", "price": 1600, "category": "clothing", "description": "Colorful printed shorts for casual summer wear.", "images": ["https://via.placeholder.com/600x600/4a7c59/ffffff?text=Shorts"], "sizes": ["S", "M", "L"], "colors": [{"name": "Blue", "hex": "#0000ff"}, {"name": "Green", "hex": "#008000"}], "stock": 85, "rating": 4.2, "review_count": 0, "is_active": True, "created_at": datetime.utcnow().isoformat()},
    {"name": "Zip-up Sweatshirt", "price": 3200, "category": "clothing", "description": "Cozy zip-up sweatshirt for layering. Perfect for all seasons.", "images": ["https://via.placeholder.com/600x600/808080/ffffff?text=Sweatshirt"], "sizes": ["M", "L", "XL"], "colors": [{"name": "Grey", "hex": "#808080"}, {"name": "Black", "hex": "#000000"}], "stock": 65, "rating": 4.4, "review_count": 0, "is_active": True, "created_at": datetime.utcnow().isoformat()},
    {"name": "Plain Crew Neck Sweatshirt", "price": 2800, "category": "clothing", "description": "Classic crew neck sweatshirt in premium fabric. Timeless style.", "images": ["https://via.placeholder.com/600x600/ffffff/000000?text=CrewNeck"], "sizes": ["S", "M", "L", "XL"], "colors": [{"name": "White", "hex": "#ffffff"}, {"name": "Navy", "hex": "#001a4d"}], "stock": 95, "rating": 4.6, "review_count": 0, "is_active": True, "created_at": datetime.utcnow().isoformat()},
    
    # ━━━━━ ACCESSORIES (8 items) ━━━━━
    {"name": "Leather Belt", "price": 900, "category": "accessories", "description": "Premium leather belt with classic buckle design.", "images": ["https://via.placeholder.com/600x600/8b6914/ffffff?text=Belt"], "sizes": [], "colors": [{"name": "Brown", "hex": "#8b4513"}, {"name": "Black", "hex": "#000000"}], "stock": 120, "rating": 4.5, "review_count": 0, "is_active": True, "created_at": datetime.utcnow().isoformat()},
    {"name": "Canvas Backpack", "price": 2500, "category": "accessories", "description": "Durable canvas backpack with multiple compartments.", "images": ["https://via.placeholder.com/600x600/3a3a3a/ffffff?text=Backpack"], "sizes": [], "colors": [{"name": "Black", "hex": "#000000"}, {"name": "Grey", "hex": "#808080"}], "stock": 45, "rating": 4.7, "review_count": 0, "is_active": True, "created_at": datetime.utcnow().isoformat()},
    {"name": "Baseball Cap", "price": 800, "category": "accessories", "description": "Classic baseball cap in premium material.", "images": ["https://via.placeholder.com/600x600/1a1a1a/ffffff?text=Cap"], "sizes": [], "colors": [{"name": "Black", "hex": "#000000"}, {"name": "White", "hex": "#ffffff"}, {"name": "Navy", "hex": "#001a4d"}], "stock": 150, "rating": 4.3, "review_count": 0, "is_active": True, "created_at": datetime.utcnow().isoformat()},
    {"name": "Aviator Sunglasses", "price": 1200, "category": "accessories", "description": "Classic aviator style sunglasses with UV protection.", "images": ["https://via.placeholder.com/600x600/2a2a2a/ffffff?text=Sunglasses"], "sizes": [], "colors": [{"name": "Gold", "hex": "#ffd700"}, {"name": "Silver", "hex": "#c0c0c0"}], "stock": 60, "rating": 4.6, "review_count": 0, "is_active": True, "created_at": datetime.utcnow().isoformat()},
    {"name": "Leather Wallet", "price": 1500, "category": "accessories", "description": "Slim leather wallet with card slots and coin compartment.", "images": ["https://via.placeholder.com/600x600/8b4513/ffffff?text=Wallet"], "sizes": [], "colors": [{"name": "Brown", "hex": "#8b4513"}, {"name": "Black", "hex": "#000000"}], "stock": 100, "rating": 4.4, "review_count": 0, "is_active": True, "created_at": datetime.utcnow().isoformat()},
    {"name": "Woven Bracelet Set", "price": 600, "category": "accessories", "description": "Set of colorful woven bracelets for casual wear.", "images": ["https://via.placeholder.com/600x600/ff69b4/ffffff?text=Bracelets"], "sizes": [], "colors": [{"name": "Multi", "hex": "#ff69b4"}], "stock": 200, "rating": 4.2, "review_count": 0, "is_active": True, "created_at": datetime.utcnow().isoformat()},
    {"name": "Knit Beanie", "price": 700, "category": "accessories", "description": "Warm and cozy knit beanie for winter.", "images": ["https://via.placeholder.com/600x600/4a4a4a/ffffff?text=Beanie"], "sizes": [], "colors": [{"name": "Black", "hex": "#000000"}, {"name": "Grey", "hex": "#808080"}, {"name": "Red", "hex": "#ff0000"}], "stock": 110, "rating": 4.5, "review_count": 0, "is_active": True, "created_at": datetime.utcnow().isoformat()},
    {"name": "Canvas Tote Bag", "price": 950, "category": "accessories", "description": "Large canvas tote bag for shopping and daily use.", "images": ["https://via.placeholder.com/600x600/e8d4b8/000000?text=Tote"], "sizes": [], "colors": [{"name": "Natural", "hex": "#e8d4b8"}, {"name": "Black", "hex": "#000000"}], "stock": 130, "rating": 4.3, "review_count": 0, "is_active": True, "created_at": datetime.utcnow().isoformat()},
]

async def seed():
    try:
        print("\n" + "="*70)
        print("🌱 SEEDING E-COMMERCE DATABASE")
        print("="*70)
        
        await client.admin.command("ping")
        print("✅ MongoDB connected successfully\n")
        
        # ──────────────────────────────────────────────────────────────────────
        # PRODUCTS
        # ──────────────────────────────────────────────────────────────────────
        print("📦 Processing products...")
        existing_products = await db.products.count_documents({})
        if existing_products > 0:
            print(f"   ⚠️  Found {existing_products} existing products. Clearing...")
            await db.products.delete_many({})
        
        result = await db.products.insert_many(PRODUCTS)
        print(f"✅ Inserted {len(PRODUCTS)} products\n")
        
        # ──────────────────────────────────────────────────────────────────────
        # USERS  
        # ──────────────────────────────────────────────────────────────────────
        print("👥 Processing users...")
        
        users_data = [
            {"name": "Admin User", "email": "admin@ecommerce.com", "password": pwd.hash("Admin@123"), "role": "admin", "phone": "03001234567"},
            {"name": "Customer One", "email": "customer1@test.com", "password": pwd.hash("Test@123"), "role": "customer", "phone": "03101234567"},
            {"name": "Customer Two", "email": "customer2@test.com", "password": pwd.hash("Test@123"), "role": "customer", "phone": "03201234567"},
        ]
        
        for user_data in users_data:
            existing = await db.users.find_one({"email": user_data["email"]})
            if existing:
                print(f"   ⚠️  User {user_data['email']} exists. Skipping...")
            else:
                user_data["is_active"] = True
                user_data["created_at"] = datetime.utcnow().isoformat()
                await db.users.insert_one(user_data)
                print(f"✅ Created {user_data['role']}: {user_data['email']}")
        
        # ──────────────────────────────────────────────────────────────────────
        # SAMPLE ORDERS
        # ──────────────────────────────────────────────────────────────────────
        print("\n📋 Processing sample orders...")
        
        customer1 = await db.users.find_one({"email": "customer1@test.com"})
        customer2 = await db.users.find_one({"email": "customer2@test.com"})
        white_tee = await db.products.find_one({"name": "Classic White T-Shirt"})
        black_hoodie = await db.products.find_one({"name": "Oversized Black Hoodie"})
        backpack = await db.products.find_one({"name": "Canvas Backpack"})
        cap = await db.products.find_one({"name": "Baseball Cap"})
        
        if customer1 and white_tee:
            order1 = {
                "user_id": str(customer1["_id"]),
                "items": [
                    {
                        "product_id": str(white_tee["_id"]),
                        "name": white_tee["name"],
                        "price": white_tee["price"],
                        "quantity": 2,
                        "size": "M",
                        "color": "White",
                        "image": white_tee["images"][0]
                    }
                ],
                "shipping_address": {
                    "full_name": customer1["name"],
                    "phone": customer1["phone"],
                    "address": "123 Main Street",
                    "city": "Karachi",
                    "postal_code": "75000"
                },
                "subtotal": white_tee["price"] * 2,
                "discount": 0,
                "tax": round((white_tee["price"] * 2) * 0.10, 2),
                "delivery_fee": 250,
                "total": round((white_tee["price"] * 2) * 1.10 + 250, 2),
                "status": "delivered",
                "payment_method": "cod",
                "status_history": [
                    {"status": "pending", "timestamp": datetime.utcnow().isoformat(), "note": "Order placed"},
                    {"status": "confirmed", "timestamp": datetime.utcnow().isoformat(), "note": "Order confirmed"},
                    {"status": "shipped", "timestamp": datetime.utcnow().isoformat(), "note": "Out for delivery"},
                    {"status": "delivered", "timestamp": datetime.utcnow().isoformat(), "note": "Delivered"}
                ],
                "created_at": datetime.utcnow().isoformat()
            }
            await db.orders.insert_one(order1)
            print("✅ Order 1: customer1 - delivered")
        
        if customer1 and black_hoodie:
            order2 = {
                "user_id": str(customer1["_id"]),
                "items": [
                    {
                        "product_id": str(black_hoodie["_id"]),
                        "name": black_hoodie["name"],
                        "price": black_hoodie["price"],
                        "quantity": 1,
                        "size": "L",
                        "color": "Black",
                        "image": black_hoodie["images"][0]
                    }
                ],
                "shipping_address": {
                    "full_name": customer1["name"],
                    "phone": customer1["phone"],
                    "address": "123 Main Street",
                    "city": "Karachi",
                    "postal_code": "75000"
                },
                "subtotal": black_hoodie["price"],
                "discount": 0,
                "tax": round(black_hoodie["price"] * 0.10, 2),
                "delivery_fee": 250,
                "total": round(black_hoodie["price"] * 1.10 + 250, 2),
                "status": "shipped",
                "payment_method": "cod",
                "status_history": [
                    {"status": "pending", "timestamp": datetime.utcnow().isoformat(), "note": "Order placed"},
                    {"status": "confirmed", "timestamp": datetime.utcnow().isoformat(), "note": "Order confirmed"},
                    {"status": "shipped", "timestamp": datetime.utcnow().isoformat(), "note": "Out for delivery"}
                ],
                "created_at": datetime.utcnow().isoformat()
            }
            await db.orders.insert_one(order2)
            print("✅ Order 2: customer1 - shipped")
        
        if customer2 and backpack and cap:
            order3 = {
                "user_id": str(customer2["_id"]),
                "items": [
                    {
                        "product_id": str(backpack["_id"]),
                        "name": backpack["name"],
                        "price": backpack["price"],
                        "quantity": 1,
                        "size": "",
                        "color": "Black",
                        "image": backpack["images"][0]
                    },
                    {
                        "product_id": str(cap["_id"]),
                        "name": cap["name"],
                        "price": cap["price"],
                        "quantity": 1,
                        "size": "",
                        "color": "Black",
                        "image": cap["images"][0]
                    }
                ],
                "shipping_address": {
                    "full_name": customer2["name"],
                    "phone": customer2["phone"],
                    "address": "456 Oak Avenue",
                    "city": "Lahore",
                    "postal_code": "54000"
                },
                "subtotal": backpack["price"] + cap["price"],
                "discount": 0,
                "tax": round((backpack["price"] + cap["price"]) * 0.10, 2),
                "delivery_fee": 250,
                "total": round((backpack["price"] + cap["price"]) * 1.10 + 250, 2),
                "status": "pending",
                "payment_method": "cod",
                "status_history": [
                    {"status": "pending", "timestamp": datetime.utcnow().isoformat(), "note": "Order placed"}
                ],
                "created_at": datetime.utcnow().isoformat()
            }
            await db.orders.insert_one(order3)
            print("✅ Order 3: customer2 - pending")
        
        # ──────────────────────────────────────────────────────────────────────
        # SUMMARY
        # ──────────────────────────────────────────────────────────────────────
        total_products = await db.products.count_documents({})
        total_users = await db.users.count_documents({})
        total_orders = await db.orders.count_documents({})
        
        print("\n" + "="*70)
        print("✅ SEED COMPLETED SUCCESSFULLY")
        print("="*70)
        print(f"📊 Database: {DB_NAME}")
        print(f"   • Products: {total_products}")
        print(f"   • Users: {total_users}")
        print(f"   • Orders: {total_orders}")
        print("\n🔐 Test Credentials:")
        print("   Admin:      admin@ecommerce.com / Admin@123")
        print("   Customer 1: customer1@test.com / Test@123")
        print("   Customer 2: customer2@test.com / Test@123")
        print("\n▶️  Run: python -m uvicorn main:app --reload --port 8000")
        print("="*70 + "\n")
        
    except Exception as e:
        print(f"\n❌ SEED FAILED: {e}\n")
        raise
    finally:
        client.close()

if __name__ == "__main__":
    asyncio.run(seed())


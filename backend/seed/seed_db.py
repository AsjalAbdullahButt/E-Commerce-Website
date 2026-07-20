"""
Seed script for E-Commerce database
Inserts: 20 products (12 clothing + 8 accessories), 3 users, 3 sample orders
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime, timezone

sys.path.append(str(Path(__file__).resolve().parents[1]))

from dotenv import load_dotenv
load_dotenv()

from sqlalchemy import select

import database
from config import settings
from db.order import Order, OrderItem, OrderStatusHistory
from db.product import Product, ProductVariant
from db.user import User
from utils.helpers import hash_password

# ═════════════════════════════════════════════════════════════════════════════
# PRODUCTS: 20 Items (12 Clothing + 8 Accessories) - All prices in PKR
#
# Authored here in a flat sizes/colors/stock shorthand for readability, then converted to the
# canonical variants[] shape by build_variants_from_flat() before insertion — the `products`
# table itself only ever stores variants (as product_variants rows) and total_stock.
# ═════════════════════════════════════════════════════════════════════════════

PRODUCTS_AUTHORED = [
    # ━━━━━ CLOTHING (12 items) ━━━━━
    {"name": "Classic White T-Shirt", "price": 1200, "category": "clothing", "description": "Premium 100% cotton classic white t-shirt.", "images": ["https://picsum.photos/seed/WhiteTee/600/600"], "sizes": ["S", "M", "L", "XL"], "colors": [{"name": "White", "hex": "#ffffff"}, {"name": "Black", "hex": "#000000"}], "stock": 100, "rating": 4.5},
    {"name": "Oversized Black Hoodie", "price": 3500, "category": "clothing", "description": "Comfortable oversized hoodie in premium fabric.", "images": ["https://picsum.photos/seed/Hoodie/600/600"], "sizes": ["M", "L", "XL", "XXL"], "colors": [{"name": "Black", "hex": "#000000"}, {"name": "Grey", "hex": "#808080"}], "stock": 75, "rating": 4.7},
    {"name": "Slim Fit Jeans", "price": 4200, "category": "clothing", "description": "Classic slim fit jeans with premium denim.", "images": ["https://picsum.photos/seed/Jeans/600/600"], "sizes": ["30", "32", "34", "36"], "colors": [{"name": "Blue", "hex": "#0000ff"}, {"name": "Black", "hex": "#000000"}], "stock": 80, "rating": 4.6},
    {"name": "Striped Polo Shirt", "price": 1800, "category": "clothing", "description": "Classic striped polo shirt for casual and formal occasions.", "images": ["https://picsum.photos/seed/Polo/600/600"], "sizes": ["S", "M", "L"], "colors": [{"name": "Navy", "hex": "#001a4d"}, {"name": "White", "hex": "#ffffff"}], "stock": 60, "rating": 4.4},
    {"name": "Graphic Tee - Urban", "price": 1500, "category": "clothing", "description": "Urban style graphic t-shirt with unique design.", "images": ["https://picsum.photos/seed/GraphicTee/600/600"], "sizes": ["S", "M", "L", "XL"], "colors": [{"name": "White", "hex": "#ffffff"}, {"name": "Grey", "hex": "#808080"}], "stock": 90, "rating": 4.3},
    {"name": "Cargo Pants", "price": 3800, "category": "clothing", "description": "Durable cargo pants with multiple pockets for functionality.", "images": ["https://picsum.photos/seed/Cargo/600/600"], "sizes": ["30", "32", "34"], "colors": [{"name": "Khaki", "hex": "#c3b091"}, {"name": "Black", "hex": "#000000"}], "stock": 50, "rating": 4.2},
    {"name": "Denim Jacket", "price": 5500, "category": "clothing", "description": "Premium denim jacket perfect for layering in any season.", "images": ["https://picsum.photos/seed/DenimJacket/600/600"], "sizes": ["S", "M", "L", "XL"], "colors": [{"name": "Blue", "hex": "#0000ff"}, {"name": "Black", "hex": "#000000"}], "stock": 40, "rating": 4.8},
    {"name": "Tracksuit Set", "price": 4800, "category": "clothing", "description": "Comfortable matching tracksuit for casual and active wear.", "images": ["https://picsum.photos/seed/Tracksuit/600/600"], "sizes": ["M", "L", "XL"], "colors": [{"name": "Black", "hex": "#000000"}, {"name": "Navy", "hex": "#001a4d"}], "stock": 55, "rating": 4.5},
    {"name": "Linen Summer Shirt", "price": 2200, "category": "clothing", "description": "Breathable linen shirt perfect for summer. Cool and comfortable.", "images": ["https://picsum.photos/seed/Linen/600/600"], "sizes": ["S", "M", "L", "XL"], "colors": [{"name": "White", "hex": "#ffffff"}, {"name": "Beige", "hex": "#f5f5dc"}], "stock": 70, "rating": 4.3},
    {"name": "Printed Shorts", "price": 1600, "category": "clothing", "description": "Colorful printed shorts for casual summer wear.", "images": ["https://picsum.photos/seed/Shorts/600/600"], "sizes": ["S", "M", "L"], "colors": [{"name": "Blue", "hex": "#0000ff"}, {"name": "Green", "hex": "#008000"}], "stock": 85, "rating": 4.2},
    {"name": "Zip-up Sweatshirt", "price": 3200, "category": "clothing", "description": "Cozy zip-up sweatshirt for layering. Perfect for all seasons.", "images": ["https://picsum.photos/seed/Sweatshirt/600/600"], "sizes": ["M", "L", "XL"], "colors": [{"name": "Grey", "hex": "#808080"}, {"name": "Black", "hex": "#000000"}], "stock": 65, "rating": 4.4},
    {"name": "Plain Crew Neck Sweatshirt", "price": 2800, "category": "clothing", "description": "Classic crew neck sweatshirt in premium fabric. Timeless style.", "images": ["https://picsum.photos/seed/CrewNeck/600/600"], "sizes": ["S", "M", "L", "XL"], "colors": [{"name": "White", "hex": "#ffffff"}, {"name": "Navy", "hex": "#001a4d"}], "stock": 95, "rating": 4.6},

    # ━━━━━ ACCESSORIES (8 items) ━━━━━
    {"name": "Leather Belt", "price": 900, "category": "accessories", "description": "Premium leather belt with classic buckle design.", "images": ["https://picsum.photos/seed/Belt/600/600"], "sizes": [], "colors": [{"name": "Brown", "hex": "#8b4513"}, {"name": "Black", "hex": "#000000"}], "stock": 120, "rating": 4.5},
    {"name": "Canvas Backpack", "price": 2500, "category": "accessories", "description": "Durable canvas backpack with multiple compartments.", "images": ["https://picsum.photos/seed/Backpack/600/600"], "sizes": [], "colors": [{"name": "Black", "hex": "#000000"}, {"name": "Grey", "hex": "#808080"}], "stock": 45, "rating": 4.7},
    {"name": "Baseball Cap", "price": 800, "category": "accessories", "description": "Classic baseball cap in premium material.", "images": ["https://picsum.photos/seed/Cap/600/600"], "sizes": [], "colors": [{"name": "Black", "hex": "#000000"}, {"name": "White", "hex": "#ffffff"}, {"name": "Navy", "hex": "#001a4d"}], "stock": 150, "rating": 4.3},
    {"name": "Aviator Sunglasses", "price": 1200, "category": "accessories", "description": "Classic aviator style sunglasses with UV protection.", "images": ["https://picsum.photos/seed/Sunglasses/600/600"], "sizes": [], "colors": [{"name": "Gold", "hex": "#ffd700"}, {"name": "Silver", "hex": "#c0c0c0"}], "stock": 60, "rating": 4.6},
    {"name": "Leather Wallet", "price": 1500, "category": "accessories", "description": "Slim leather wallet with card slots and coin compartment.", "images": ["https://picsum.photos/seed/Wallet/600/600"], "sizes": [], "colors": [{"name": "Brown", "hex": "#8b4513"}, {"name": "Black", "hex": "#000000"}], "stock": 100, "rating": 4.4},
    {"name": "Woven Bracelet Set", "price": 600, "category": "accessories", "description": "Set of colorful woven bracelets for casual wear.", "images": ["https://picsum.photos/seed/Bracelets/600/600"], "sizes": [], "colors": [{"name": "Multi", "hex": "#ff69b4"}], "stock": 200, "rating": 4.2},
    {"name": "Knit Beanie", "price": 700, "category": "accessories", "description": "Warm and cozy knit beanie for winter.", "images": ["https://picsum.photos/seed/Beanie/600/600"], "sizes": [], "colors": [{"name": "Black", "hex": "#000000"}, {"name": "Grey", "hex": "#808080"}, {"name": "Red", "hex": "#ff0000"}], "stock": 110, "rating": 4.5},
    {"name": "Canvas Tote Bag", "price": 950, "category": "accessories", "description": "Large canvas tote bag for shopping and daily use.", "images": ["https://picsum.photos/seed/Tote/600/600"], "sizes": [], "colors": [{"name": "Natural", "hex": "#e8d4b8"}, {"name": "Black", "hex": "#000000"}], "stock": 130, "rating": 4.3},
]


def slugify(value: str) -> str:
    """Turn a name into a URL/SKU-safe slug (lowercase, hyphen-separated)."""
    return "-".join("".join(c.lower() if c.isalnum() else " " for c in str(value)).split())


def build_variants_from_flat(doc: dict) -> list[dict]:
    """Convert the flat sizes/colors/stock shorthand above into the canonical variants[] shape."""
    sizes = doc.get("sizes") or [""]
    colors = doc.get("colors") or [{"name": "Default"}]
    color_names = [c.get("name", "Default") if isinstance(c, dict) else str(c) for c in colors] or ["Default"]
    size_labels = sizes or [""]

    combos = [(s, c) for s in size_labels for c in color_names]
    total_stock = int(doc.get("stock", 0) or 0)
    base_name = doc.get("name", "product")

    n = len(combos) or 1
    per_variant = total_stock // n
    remainder = total_stock - per_variant * n

    variants = []
    for i, (size, color) in enumerate(combos):
        stock = per_variant + (1 if i < remainder else 0)
        size_label = size or "One Size"
        sku = f"{slugify(base_name)}-{slugify(size_label)}-{slugify(color)}-{i + 1}".replace("--", "-")
        variants.append({"size": size_label, "color": color, "sku": sku, "stock": stock})
    return variants


async def seed():
    print("\n" + "=" * 70)
    print("SEEDING E-COMMERCE DATABASE")
    print("=" * 70)

    async with database.engine.connect():
        pass
    print("MySQL connected successfully\n")

    async with database.AsyncSessionLocal() as db:
        # ──────────────────────────────────────────────────────────────────
        # PRODUCTS
        # ──────────────────────────────────────────────────────────────────
        print("Processing products...")
        existing_products = (await db.execute(select(Product))).scalars().all()
        if existing_products:
            print(f"   Found {len(existing_products)} existing products. Clearing...")
            for p in existing_products:
                await db.delete(p)
            await db.flush()

        products_by_name: dict[str, Product] = {}
        for authored in PRODUCTS_AUTHORED:
            variants = build_variants_from_flat(authored)
            product = Product(
                name=authored["name"],
                description=authored["description"],
                category=authored["category"],
                price=authored["price"],
                discount_percentage=0.0,
                tags=[],
                images=authored["images"],
                total_stock=sum(v["stock"] for v in variants),
                is_active=True,
                rating=authored["rating"],
                review_count=0,
            )
            db.add(product)
            await db.flush()  # populate product.id before referencing it in variants
            for v in variants:
                db.add(ProductVariant(product_id=product.id, size=v["size"], color=v["color"], sku=v["sku"], stock=v["stock"]))
            products_by_name[product.name] = product

        await db.flush()
        print(f"Inserted {len(products_by_name)} products\n")

        # ──────────────────────────────────────────────────────────────────
        # USERS
        # ──────────────────────────────────────────────────────────────────
        print("Processing users...")

        users_data = [
            {"name": "Admin User", "email": "admin@ecommerce.com", "password": hash_password("Admin@123"), "role": "admin", "phone": "03001234567"},
            {"name": "Customer One", "email": "customer1@test.com", "password": hash_password("Test@123"), "role": "customer", "phone": "03101234567"},
            {"name": "Customer Two", "email": "customer2@test.com", "password": hash_password("Test@123"), "role": "customer", "phone": "03201234567"},
        ]

        users_by_email: dict[str, User] = {}
        for user_data in users_data:
            existing = (await db.execute(select(User).where(User.email == user_data["email"]))).scalar_one_or_none()
            if existing:
                print(f"   User {user_data['email']} exists. Skipping...")
                users_by_email[user_data["email"]] = existing
            else:
                user = User(is_active=True, **user_data)
                db.add(user)
                await db.flush()
                users_by_email[user.email] = user
                print(f"Created {user_data['role']}: {user_data['email']}")

        # ──────────────────────────────────────────────────────────────────
        # SAMPLE ORDERS
        # ──────────────────────────────────────────────────────────────────
        print("\nProcessing sample orders...")

        customer1 = users_by_email.get("customer1@test.com")
        customer2 = users_by_email.get("customer2@test.com")
        white_tee = products_by_name.get("Classic White T-Shirt")
        black_hoodie = products_by_name.get("Oversized Black Hoodie")
        backpack = products_by_name.get("Canvas Backpack")
        cap = products_by_name.get("Baseball Cap")

        def make_order(customer: User, items: list[dict], status: str, history_statuses: list[str]) -> Order:
            subtotal = sum(i["price"] * i["quantity"] for i in items)
            tax = round(subtotal * 0.10, 2)
            delivery_fee = 250
            order = Order(
                user_id=customer.id,
                status=status,
                subtotal=subtotal,
                discount=0,
                tax=tax,
                delivery_fee=delivery_fee,
                total=round(subtotal + tax + delivery_fee, 2),
                payment_method="cod",
                full_name=customer.name,
                phone=customer.phone,
                address="123 Main Street" if customer is customer1 else "456 Oak Avenue",
                city="Karachi" if customer is customer1 else "Lahore",
                postal_code="75000" if customer is customer1 else "54000",
            )
            db.add(order)
            return order

        if customer1 and white_tee:
            order1 = make_order(
                customer1,
                [{"product_id": white_tee.id, "name": white_tee.name, "price": white_tee.price,
                  "quantity": 2, "size": "M", "color": "White", "image": white_tee.images[0]}],
                "delivered", ["pending", "confirmed", "shipped", "delivered"],
            )
            await db.flush()
            db.add(OrderItem(order_id=order1.id, product_id=white_tee.id, name=white_tee.name,
                              price=white_tee.price, quantity=2, size="M", color="White", image=white_tee.images[0]))
            for s, note in [("pending", "Order placed"), ("confirmed", "Order confirmed"),
                             ("shipped", "Out for delivery"), ("delivered", "Delivered")]:
                db.add(OrderStatusHistory(order_id=order1.id, status=s, timestamp=datetime.now(timezone.utc), note=note))
            print("Order 1: customer1 - delivered")

        if customer1 and black_hoodie:
            order2 = make_order(
                customer1,
                [{"product_id": black_hoodie.id, "name": black_hoodie.name, "price": black_hoodie.price,
                  "quantity": 1, "size": "L", "color": "Black", "image": black_hoodie.images[0]}],
                "shipped", ["pending", "confirmed", "shipped"],
            )
            await db.flush()
            db.add(OrderItem(order_id=order2.id, product_id=black_hoodie.id, name=black_hoodie.name,
                              price=black_hoodie.price, quantity=1, size="L", color="Black", image=black_hoodie.images[0]))
            for s, note in [("pending", "Order placed"), ("confirmed", "Order confirmed"),
                             ("shipped", "Out for delivery")]:
                db.add(OrderStatusHistory(order_id=order2.id, status=s, timestamp=datetime.now(timezone.utc), note=note))
            print("Order 2: customer1 - shipped")

        if customer2 and backpack and cap:
            order3 = make_order(
                customer2,
                [{"product_id": backpack.id, "name": backpack.name, "price": backpack.price,
                  "quantity": 1, "size": "", "color": "Black", "image": backpack.images[0]},
                 {"product_id": cap.id, "name": cap.name, "price": cap.price,
                  "quantity": 1, "size": "", "color": "Black", "image": cap.images[0]}],
                "pending", ["pending"],
            )
            await db.flush()
            db.add(OrderItem(order_id=order3.id, product_id=backpack.id, name=backpack.name,
                              price=backpack.price, quantity=1, size="", color="Black", image=backpack.images[0]))
            db.add(OrderItem(order_id=order3.id, product_id=cap.id, name=cap.name,
                              price=cap.price, quantity=1, size="", color="Black", image=cap.images[0]))
            db.add(OrderStatusHistory(order_id=order3.id, status="pending", timestamp=datetime.now(timezone.utc), note="Order placed"))
            print("Order 3: customer2 - pending")

        await db.commit()

        # ──────────────────────────────────────────────────────────────────
        # SUMMARY
        # ──────────────────────────────────────────────────────────────────
        total_products = (await db.execute(select(Product))).scalars().all()
        total_users = (await db.execute(select(User))).scalars().all()
        total_orders = (await db.execute(select(Order))).scalars().all()

    print("\n" + "=" * 70)
    print("SEED COMPLETED SUCCESSFULLY")
    print("=" * 70)
    print(f"Database: {settings.mysql_database}")
    print(f"   - Products: {len(total_products)}")
    print(f"   - Users: {len(total_users)}")
    print(f"   - Orders: {len(total_orders)}")
    print("\nTest Credentials:")
    print("   Admin:      admin@ecommerce.com / Admin@123")
    print("   Customer 1: customer1@test.com / Test@123")
    print("   Customer 2: customer2@test.com / Test@123")
    print("\nRun: python -m uvicorn main:app --reload --port 8000")
    print("=" * 70 + "\n")

    # Dispose the engine's pooled connections before the event loop closes — otherwise aiomysql's
    # Connection.__del__ fires during interpreter/GC shutdown after the loop is already gone,
    # producing a harmless but noisy "Event loop is closed" RuntimeError on exit.
    await database.engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed())

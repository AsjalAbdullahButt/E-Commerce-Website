from motor.motor_asyncio import AsyncIOMotorClient
from config import settings

# MongoDB Client
client = AsyncIOMotorClient(settings.mongodb_uri)
db = client[settings.database_name]

# Collections - Customer Side
users_col      = db["users"]
products_col   = db["products"]
orders_col     = db["orders"]
reviews_col    = db["reviews"]
wishlist_col   = db["wishlist"]
promos_col     = db["promos"]

# Collections - Admin Side
admin_users_col     = db["admin_users"]
inventory_history_col = db["inventory_history"]
audit_logs_col      = db["audit_logs"]
discounts_col       = db["discounts"]
notifications_col   = db["notifications"]

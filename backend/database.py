from motor.motor_asyncio import AsyncIOMotorClient
from config import settings

# MongoDB Client
client = AsyncIOMotorClient(settings.mongodb_uri)
db = client[settings.database_name]

# Collections
users_col      = db["users"]
products_col   = db["products"]
orders_col     = db["orders"]
reviews_col    = db["reviews"]
wishlist_col   = db["wishlist"]
promos_col     = db["promos"]

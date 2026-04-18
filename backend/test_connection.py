import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
import os
from dotenv import load_dotenv

load_dotenv()

async def test_connection():
    try:
        client = AsyncIOMotorClient(os.getenv('MONGODB_URI'))
        db = client.E_Commerce
        
        # Test connection
        await client.admin.command('ping')
        print('✅ MongoDB Connection: SUCCESS')
        
        # Check collections
        collections = await db.list_collection_names()
        print(f'✅ Collections found: {len(collections)}')
        for col in collections:
            print(f'   - {col}')
        
        # Count documents
        user_count = await db.users.count_documents({})
        product_count = await db.products.count_documents({})
        print(f'\n✅ Users in database: {user_count}')
        print(f'✅ Products in database: {product_count}')
        
        # List test users
        users = await db.users.find({}, {'name': 1, 'email': 1, 'role': 1}).to_list(10)
        print(f'\n✅ Test Users:')
        for user in users:
            print(f"   - {user['name']} ({user['email']}) - Role: {user['role']}")
        
        client.close()
        print('\n🎉 All systems operational!')
    except Exception as e:
        print(f'❌ Error: {str(e)}')

asyncio.run(test_connection())

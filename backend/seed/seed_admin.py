"""
Seed script to create initial admin users for the system
Run: python backend/seed/seed_admin.py
"""

import asyncio
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

sys.path.append(str(Path(__file__).resolve().parents[1]))
load_dotenv()

from services.admin_auth import AdminAuthService

REQUIRED_PASSWORD_VARS = [
    'SEED_SUPERADMIN_PASSWORD',
    'SEED_ADMIN_PASSWORD',
    'SEED_MANAGER_PASSWORD',
    'SEED_SUPPORT_PASSWORD',
]


async def main():
    print("\n" + "="*60)
    print("  🌱 ADMIN USER SEED SCRIPT")
    print("="*60 + "\n")

    missing = [var for var in REQUIRED_PASSWORD_VARS if not os.getenv(var)]
    if missing:
        print("❌ Missing required environment variables:")
        for var in missing:
            print(f"   {var}")
        print("\nSet these in your .env file before running the seed script.\n")
        return

    # Admin users to create
    admins = [
        {
            'name': 'Super Administrator',
            'email': 'superadmin@example.com',
            'password': os.getenv('SEED_SUPERADMIN_PASSWORD'),
            'role': 'super_admin',
            'description': 'Full system access'
        },
        {
            'name': 'Operations Manager',
            'email': 'admin@example.com',
            'password': os.getenv('SEED_ADMIN_PASSWORD'),
            'role': 'admin',
            'description': 'Products, Orders, Users'
        },
        {
            'name': 'Inventory Manager',
            'email': 'manager@example.com',
            'password': os.getenv('SEED_MANAGER_PASSWORD'),
            'role': 'manager',
            'description': 'Inventory & order read/update'
        },
        {
            'name': 'Support Staff',
            'email': 'support@example.com',
            'password': os.getenv('SEED_SUPPORT_PASSWORD'),
            'role': 'support',
            'description': 'Orders & users read-only'
        },
    ]

    created = 0
    for admin in admins:
        try:
            result = await AdminAuthService.create_admin_user(
                name=admin['name'],
                email=admin['email'],
                password=admin['password'],
                role=admin['role']
            )
            print(f"✅ {admin['role'].upper()}")
            print(f"   Email: {admin['email']}")
            print(f"   Password: {admin['password']}")
            print(f"   Access: {admin['description']}\n")
            created += 1
        except Exception as e:
            print(f"❌ Failed to create {admin['role']}: {str(e)}\n")

    print("="*60)
    print(f"✨ Successfully created {created}/{len(admins)} admin users")
    print("="*60)
    print("\n🔐 Login Credentials:")
    print("   URL: http://localhost:8080/admin/login.html")
    print("   Try any of the above email/password combinations\n")

if __name__ == '__main__':
    asyncio.run(main())

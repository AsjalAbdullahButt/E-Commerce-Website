"""
Seed script to create initial admin users for the system
Run: python backend/seed/seed_admin.py
"""

import asyncio
import sys
sys.path.append('..')

from services.admin_auth import AdminAuthService

async def main():
    print("\n" + "="*60)
    print("  🌱 ADMIN USER SEED SCRIPT")
    print("="*60 + "\n")

    # Admin users to create
    admins = [
        {
            'name': 'Super Administrator',
            'email': 'superadmin@ecom.local',
            'password': 'SuperAdmin@123',
            'role': 'super_admin',
            'description': 'Full system access'
        },
        {
            'name': 'Operations Manager',
            'email': 'admin@ecom.local',
            'password': 'Admin@123456',
            'role': 'admin',
            'description': 'Products, Orders, Users'
        },
        {
            'name': 'Inventory Manager',
            'email': 'manager@ecom.local',
            'password': 'Manager@123456',
            'role': 'manager',
            'description': 'Inventory & order read/update'
        },
        {
            'name': 'Support Staff',
            'email': 'support@ecom.local',
            'password': 'Support@123456',
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

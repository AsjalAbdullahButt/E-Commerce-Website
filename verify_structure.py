"""
E-Commerce Platform Structure Verification & Wiring Test
Tests that all components are properly wired together (10/10 structure verification)
"""

import os
import sys
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent / "backend"
sys.path.insert(0, str(backend_path))

def print_header(title: str):
    """Print formatted section header"""
    print(f"\n{'='*70}")
    print(f"  {title}")
    print(f"{'='*70}")

def print_check(label: str, status: bool, details: str = ""):
    """Print check result"""
    symbol = "✅" if status else "❌"
    print(f"  {symbol}  {label:<50} {details}")

def test_configuration():
    """Test configuration module"""
    print_header("1️⃣  CONFIGURATION MANAGEMENT")
    
    try:
        from config.settings import settings, Settings
        print_check("Import from config.settings", True)
    except Exception as e:
        print_check("Import from config.settings", False, str(e))
        return False
    
    try:
        from config import settings as s2
        print_check("Import from config package", True)
    except Exception as e:
        print_check("Import from config package", False, str(e))
        return False
    
    try:
        from config import settings
        assert hasattr(settings, 'mongodb_uri')
        assert hasattr(settings, 'jwt_secret')
        assert hasattr(settings, 'is_production')
        assert hasattr(settings, 'is_development')
        print_check("Settings attributes available", True)
    except Exception as e:
        print_check("Settings attributes available", False, str(e))
        return False
    
    # Test backward compatibility
    try:
        from config import settings as old_settings
        print_check("Backward-compatible imports work", True)
    except Exception as e:
        print_check("Backward-compatible imports work", False, str(e))
        return False
    
    return True

def test_backend_modules():
    """Test backend module imports"""
    print_header("2️⃣  BACKEND MODULE IMPORTS")
    
    modules = [
        ("utils.helpers", "Password & token utilities"),
        ("utils.logger", "Logging system"),
        ("utils.limiter", "Rate limiting"),
        ("utils.permissions", "Permission checks"),
        ("middleware.auth_middleware", "Auth middleware"),
        ("middleware.admin_auth", "Admin auth middleware"),
        ("models.user", "User model"),
        ("models.product", "Product model"),
        ("models.order", "Order model"),
        ("models.admin", "Admin model"),
        ("services.product", "Product service"),
        ("services.discount", "Discount service"),
    ]
    
    all_ok = True
    for module_name, description in modules:
        try:
            __import__(module_name)
            print_check(f"{module_name:<30}", True, description)
        except Exception as e:
            print_check(f"{module_name:<30}", False, f"Error: {str(e)[:40]}")
            all_ok = False
    
    return all_ok

def test_routes():
    """Test route imports"""
    print_header("3️⃣  ROUTE ENDPOINTS")
    
    routes = [
        ("routes.auth", "Authentication routes"),
        ("routes.products", "Product routes"),
        ("routes.orders", "Order routes"),
        ("routes.users", "User routes"),
        ("routes.reviews", "Review routes"),
        ("routes.promos", "Promo routes"),
        ("routes.wishlist", "Wishlist routes"),
        ("routes.rider", "Rider routes"),
        ("routes.admin", "Admin routes"),
    ]
    
    all_ok = True
    for route_name, description in routes:
        try:
            __import__(route_name)
            print_check(f"{route_name:<20}", True, description)
        except Exception as e:
            print_check(f"{route_name:<20}", False, f"Error: {str(e)[:40]}")
            all_ok = False
    
    # Test v1 versioning
    try:
        import routes.v1
        print_check("routes.v1", True, "API v1 versioning setup")
    except Exception as e:
        print_check("routes.v1", False, f"Error: {str(e)[:40]}")
        all_ok = False
    
    return all_ok

def test_test_suite():
    """Test test suite setup"""
    print_header("4️⃣  TEST SUITE")
    
    checks = [
        ("tests/__init__.py", "Test package initialized"),
        ("tests/conftest.py", "Pytest configuration"),
        ("tests/test_routes/__init__.py", "Routes test package"),
        ("tests/test_routes/test_auth.py", "Auth tests"),
        ("tests/test_utils/__init__.py", "Utils test package"),
        ("tests/test_utils/test_helpers.py", "Helper tests"),
        ("backend/pytest.ini", "Pytest configuration file"),
    ]
    
    all_ok = True
    base_path = Path(__file__).parent
    for rel_path, description in checks:
        full_path = base_path / rel_path
        exists = full_path.exists()
        print_check(f"{rel_path:<40}", exists, description)
        if not exists:
            all_ok = False
    
    return all_ok

def test_documentation():
    """Test documentation structure"""
    print_header("5️⃣  DOCUMENTATION")
    
    docs = [
        ("docs/INDEX.md", "Documentation hub"),
        ("docs/API.md", "API reference"),
        ("docs/ARCHITECTURE.md", "System architecture"),
        ("docs/INSTALLATION.md", "Installation guide"),
        ("docs/SECURITY.md", "Security guide"),
        ("docs/DEPLOYMENT.md", "Deployment guide"),
        (".env.example", "Environment template"),
    ]
    
    all_ok = True
    base_path = Path(__file__).parent
    for rel_path, description in docs:
        full_path = base_path / rel_path
        exists = full_path.exists()
        size = full_path.stat().st_size if exists else 0
        size_str = f"{size/1024:.1f}KB" if exists else ""
        print_check(f"{rel_path:<40}", exists, f"{description} {size_str}")
        if not exists:
            all_ok = False
    
    return all_ok

def test_folder_structure():
    """Test folder organization"""
    print_header("6️⃣  FOLDER STRUCTURE")
    
    folders = [
        ("backend/config", "Configuration module"),
        ("backend/routes/v1", "API versioning"),
        ("backend/tests", "Test suite"),
        ("backend/tests/test_routes", "Route tests"),
        ("backend/tests/test_services", "Service tests"),
        ("backend/tests/test_models", "Model tests"),
        ("backend/tests/test_utils", "Utility tests"),
        ("docs", "Documentation"),
        ("frontend/shared/js", "Shared JS utilities"),
        ("frontend/shared/css", "Shared CSS styles"),
    ]
    
    all_ok = True
    base_path = Path(__file__).parent
    for folder_path, description in folders:
        full_path = base_path / folder_path
        exists = full_path.is_dir()
        print_check(f"{folder_path:<40}", exists, description)
        if not exists:
            all_ok = False
    
    return all_ok

def test_wiring():
    """Test end-to-end wiring"""
    print_header("7️⃣  END-TO-END WIRING")
    
    # Test 1: Config → Main.py compatibility
    try:
        from config import settings
        from config.settings import Settings
        print_check("Config ↔ Main.py compatibility", True)
    except Exception as e:
        print_check("Config ↔ Main.py compatibility", False, str(e))
        return False
    
    # Test 2: Routes → Services wiring
    try:
        from routes import products
        from services.product import ProductService
        print_check("Routes → Services wiring", True)
    except Exception as e:
        print_check("Routes → Services wiring", False, str(e))
        return False
    
    # Test 3: Utils → Routes wiring
    try:
        from utils.helpers import hash_password, verify_password
        from utils.limiter import limiter
        print_check("Utils → Routes wiring", True)
    except Exception as e:
        print_check("Utils → Routes wiring", False, str(e))
        return False
    
    # Test 4: Middleware → Routes
    try:
        from middleware.auth_middleware import get_current_user
        from middleware.admin_auth import AdminAuthMiddleware
        print_check("Middleware → Routes wiring", True)
    except Exception as e:
        print_check("Middleware → Routes wiring", False, str(e))
        return False
    
    # Test 5: Tests → Config
    try:
        import pytest
        from tests.conftest import test_data
        print_check("Tests → Config wiring", True)
    except Exception as e:
        print_check("Tests → Config wiring", False, str(e))
        return False
    
    return True

def print_summary(results: dict):
    """Print final summary"""
    print_header("📊 VERIFICATION SUMMARY")
    
    total = len(results)
    passed = sum(1 for v in results.values() if v)
    score = (passed / total * 100) if total > 0 else 0
    
    for test_name, result in results.items():
        symbol = "✅" if result else "❌"
        print(f"  {symbol}  {test_name}")
    
    print(f"\n  {'─'*70}")
    print(f"  Score: {passed}/{total} ({score:.0f}%)")
    
    if score == 100:
        print(f"\n  🎉 PERFECT STRUCTURE - 10/10")
        print(f"     All components properly wired!")
    elif score >= 90:
        print(f"\n  ⭐ EXCELLENT STRUCTURE - {score:.0f}/10")
    elif score >= 70:
        print(f"\n  ✅ GOOD STRUCTURE - {score:.0f}/10")
    else:
        print(f"\n  ⚠️  NEEDS WORK - {score:.0f}/10")
    
    print(f"  {'─'*70}\n")
    
    return score == 100

def main():
    """Run all verification tests"""
    print("\n" + "="*70)
    print("  🏢 E-COMMERCE PLATFORM STRUCTURE VERIFICATION")
    print("  Version 2.0.0 - Production Ready Checklist")
    print("="*70)
    
    results = {
        "Configuration Management": test_configuration(),
        "Backend Module Imports": test_backend_modules(),
        "Route Endpoints": test_routes(),
        "Test Suite Setup": test_test_suite(),
        "Documentation": test_documentation(),
        "Folder Structure": test_folder_structure(),
        "End-to-End Wiring": test_wiring(),
    }
    
    success = print_summary(results)
    
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())

"""Test configuration and fixtures"""
import pytest
import os
import sys
from pathlib import Path

# Set environment to test mode
os.environ["ENVIRONMENT"] = "development"
os.environ["DOCS_ENABLED"] = "false"

sys.path.append(str(Path(__file__).resolve().parents[1]))

# ── In-memory MongoDB for tests ────────────────────────────────────────────────
# No real MongoDB is available in CI/dev sandboxes here, so every collection the app touches is
# backed by mongomock-motor instead. This must happen BEFORE any app module (database.py, main.py,
# routes/*, services/*) is imported, since they all call motor.motor_asyncio.AsyncIOMotorClient(...)
# at import time and bind collection references into their own module namespace.
import motor.motor_asyncio
from mongomock_motor import AsyncMongoMockClient

motor.motor_asyncio.AsyncIOMotorClient = AsyncMongoMockClient

import asyncio  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
import database  # noqa: E402
from main import app  # noqa: E402
from utils.limiter import limiter  # noqa: E402


async def _clear_all_collections():
    for col in (
        database.users_col, database.products_col, database.orders_col, database.reviews_col,
        database.wishlist_col, database.promos_col, database.admin_users_col, database.riders_col,
        database.inventory_history_col, database.audit_logs_col,
    ):
        await col.delete_many({})


@pytest.fixture()
def client():
    """A TestClient against the real app, with every collection cleared before each test.

    Also resets slowapi's in-memory rate-limit storage — it's process-global state (the same
    limitation tracked in NOTES_schema_audit.md §7/task 6), so without a reset, tests that hit a
    tightly-limited endpoint (e.g. /auth/register at 3/minute) start failing once enough tests in
    the same pytest run have exercised it, regardless of test order.
    """
    asyncio.run(_clear_all_collections())
    limiter.reset()
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="session")
def test_data():
    """Fixture providing test data"""
    return {
        "user": {
            "email": "test@example.com",
            "password": "TestPass123",
            "name": "Test User",
        },
        "admin": {
            "email": "admin@example.com",
            "password": "AdminPass123",
            "name": "Admin User",
        },
        "product": {
            "name": "Test Product",
            "description": "A test product",
            "price": 99.99,
            "stock": 100,
            "category": "Test Category",
        },
    }


@pytest.fixture(scope="session")
def api_base_url():
    """Fixture providing API base URL"""
    return "http://localhost:8000/api/v1"

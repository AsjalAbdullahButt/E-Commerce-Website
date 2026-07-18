"""Test configuration and fixtures"""
import pytest
import os
import sys
from pathlib import Path

# Set environment to test mode, and point the app at the dedicated test database — both must be
# set BEFORE any app module (config.py, database.py, main.py, routes/*, services/*) is imported,
# since Settings() is instantiated once at import time and database.py builds its engine from it.
os.environ["ENVIRONMENT"] = "development"
os.environ["DOCS_ENABLED"] = "false"
os.environ["MYSQL_DATABASE"] = os.environ.get("MYSQL_TEST_DATABASE", "ecommerce_test")
os.environ["TESTING"] = "1"  # selects NullPool in database.py — see its comment for why

sys.path.append(str(Path(__file__).resolve().parents[1]))

import asyncio  # noqa: E402
from sqlalchemy import text  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
import database  # noqa: E402
from db.base import Base  # noqa: E402
from db import address, admin, order, payment, product, promo, return_request, review, rider, user, wishlist  # noqa: E402,F401
from main import app  # noqa: E402
from utils.limiter import limiter  # noqa: E402


async def _create_schema():
    async with database.engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)


async def _truncate_all_tables():
    async with database.AsyncSessionLocal() as session:
        await session.execute(text("SET FOREIGN_KEY_CHECKS=0"))
        for table in Base.metadata.sorted_tables:
            await session.execute(text(f"TRUNCATE TABLE `{table.name}`"))
        await session.execute(text("SET FOREIGN_KEY_CHECKS=1"))
        await session.commit()


@pytest.fixture(scope="session", autouse=True)
def _test_schema():
    """Creates a fresh schema in the test database once per test session (drop+create, not
    Alembic — mirrors Base.metadata exactly, no migration history needed for a throwaway test
    DB)."""
    asyncio.run(_create_schema())
    yield


@pytest.fixture()
def client():
    """A TestClient against the real app, with every table truncated before each test.

    Each request still opens its own session the normal way via database.py::get_db() — no
    savepoint/transaction-sharing across TestClient's internal event loop, which async
    SQLAlchemy sessions can't safely cross. Isolation instead comes from truncating every table
    before each test starts (FK checks disabled during the truncate pass so table order doesn't
    matter), mirroring the previous mongomock-based conftest's per-test delete_many() pattern.

    Also resets slowapi's in-memory rate-limit storage — it's process-global state (the same
    limitation tracked in NOTES_schema_audit.md §7/task 6), so without a reset, tests that hit a
    tightly-limited endpoint (e.g. /auth/register at 3/minute) start failing once enough tests in
    the same pytest run have exercised it, regardless of test order.
    """
    asyncio.run(_truncate_all_tables())
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

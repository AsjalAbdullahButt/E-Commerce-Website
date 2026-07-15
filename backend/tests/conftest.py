"""Test configuration and fixtures"""
import pytest
import os
from pathlib import Path

# Set environment to test mode
os.environ["ENVIRONMENT"] = "development"
os.environ["DOCS_ENABLED"] = "false"


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

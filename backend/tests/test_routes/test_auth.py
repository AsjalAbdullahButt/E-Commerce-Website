"""Test authentication route"""
import pytest
from config import settings


class TestAuthRoute:
    """Tests for authentication endpoints"""
    
    def test_settings_loaded(self):
        """Verify settings are loaded correctly"""
        assert settings.jwt_secret is not None
        assert settings.mysql_host is not None
        assert settings.mysql_database is not None
    
    def test_environment_configuration(self):
        """Verify environment configuration"""
        assert hasattr(settings, 'is_development')
        assert hasattr(settings, 'is_production')
        assert hasattr(settings, 'is_staging')
    
    def test_cors_origins(self):
        """Verify CORS origins are configured"""
        origins = settings.allowed_origins.split(",")
        assert len(origins) > 0
        assert all(isinstance(o, str) for o in origins)

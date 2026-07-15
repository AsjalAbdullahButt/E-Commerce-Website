"""Centralized settings management with environment-based configuration"""
from pydantic_settings import BaseSettings
from pathlib import Path
from typing import Optional
from .environments import Environment

class Settings(BaseSettings):
    """Application settings loaded from .env file"""
    
    # ── Environment ────────────────────────────────────────────────────────
    environment: str = "development"
    api_version: str = "v1"
    
    # ── Database ───────────────────────────────────────────────────────────
    mongodb_uri: str
    database_name: str = "E_Commerce"
    
    # ── JWT Authentication ─────────────────────────────────────────────────
    jwt_secret: str
    jwt_algorithm: str = "HS256"
    jwt_access_expire_minutes: int = 15            # 15 minutes for access token
    jwt_refresh_expire_minutes: int = 10080        # 7 days for refresh token
    
    # ── Frontend & CORS ────────────────────────────────────────────────────
    frontend_url: str = "http://localhost:3000"
    allowed_origins: str = "http://localhost:3000,http://127.0.0.1:3000,http://localhost:8080,http://127.0.0.1:8080,http://localhost:5500,http://127.0.0.1:5500"
    
    # ── Security ───────────────────────────────────────────────────────────
    cookie_secure: bool = False                    # Set True in production (HTTPS)
    docs_enabled: bool = False                     # Enable explicitly in development
    
    # ── Rate Limiting (requests/minute) ────────────────────────────────────
    rate_login: str = "5/minute"
    rate_register: str = "3/minute"
    rate_order: str = "10/minute"
    rate_general: str = "60/minute"
    
    # ── Logging ────────────────────────────────────────────────────────────
    log_level: str = "INFO"
    log_file: str = "logs/app.log"
    
    class Config:
        """Pydantic config"""
        env_file = str(Path(__file__).parent.parent.parent / ".env")
        case_sensitive = False
    
    @property
    def is_production(self) -> bool:
        """Check if running in production"""
        return self.environment.lower() == "production"
    
    @property
    def is_development(self) -> bool:
        """Check if running in development"""
        return self.environment.lower() == "development"
    
    @property
    def is_staging(self) -> bool:
        """Check if running in staging"""
        return self.environment.lower() == "staging"


# Global settings instance
settings = Settings()

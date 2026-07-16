"""Centralized settings management with environment-based configuration"""
from pydantic_settings import BaseSettings
from pydantic import field_validator
from pathlib import Path
from typing import Optional
from .environments import Environment

# Placeholder values that must never reach production — lifted straight from .env.example and
# other common defaults people forget to change.
_PLACEHOLDER_JWT_SECRETS = {
    "replace_with_a_long_random_string_min_32_chars",
    "secret", "changeme", "change_me", "your-secret-key", "supersecret",
}

class Settings(BaseSettings):
    """Application settings loaded from .env file"""

    # ── Environment ────────────────────────────────────────────────────────
    environment: str = "development"
    api_version: str = "v1"

    # ── Database ───────────────────────────────────────────────────────────
    mysql_host: str = "localhost"
    mysql_port: int = 3306
    mysql_user: str = "root"
    mysql_password: str
    mysql_database: str = "ecommerce"
    mysql_test_database: str = "ecommerce_test"
    sql_echo: bool = False

    # ── JWT Authentication ─────────────────────────────────────────────────
    jwt_secret: str
    jwt_algorithm: str = "HS256"
    jwt_access_expire_minutes: int = 15            # 15 minutes for access token
    jwt_refresh_expire_minutes: int = 10080        # 7 days for refresh token

    @field_validator('jwt_secret')
    @classmethod
    def jwt_secret_must_be_strong(cls, v: str) -> str:
        if len(v) < 32:
            raise ValueError('JWT_SECRET must be at least 32 characters — generate one with e.g. `openssl rand -hex 32`')
        if v.strip().lower() in _PLACEHOLDER_JWT_SECRETS:
            raise ValueError('JWT_SECRET is still set to a placeholder value from .env.example — replace it with a real secret')
        return v

    # ── Frontend & CORS ────────────────────────────────────────────────────
    frontend_url: str = "http://localhost:3000"
    allowed_origins: str = "http://localhost:3000,http://127.0.0.1:3000,http://localhost:8080,http://127.0.0.1:8080,http://localhost:5500,http://127.0.0.1:5500"

    # ── Trusted Hosts ──────────────────────────────────────────────────────
    # Used by TrustedHostMiddleware (main.py), enabled only when is_production — prevents
    # Host-header injection. Must be overridden via env var in production; the default is only
    # sensible for local development.
    trusted_hosts: str = "localhost,127.0.0.1"

    # ── Security ───────────────────────────────────────────────────────────
    cookie_secure: bool = False                    # Set True in production (HTTPS)
    docs_enabled: bool = False                     # Enable explicitly in development

    # ── Deployment ─────────────────────────────────────────────────────────
    # utils/cache.py and utils/limiter.py are process-local (in-memory dict / slowapi default
    # storage) — there is no Redis or other shared backend. Running more than one worker process
    # means each worker has its own independent cache and rate-limit counters, so cache
    # invalidation and rate limits silently stop being consistent across requests. Set this to
    # match whatever --workers/-w value actually launches the app so main.py can fail fast
    # instead of degrading silently. See NOTES_schema_audit.md §7 / README "Deployment".
    web_concurrency: int = 1
    
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

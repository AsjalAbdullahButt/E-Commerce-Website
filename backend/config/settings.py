"""Centralized settings management with environment-based configuration"""
from pydantic_settings import BaseSettings
from pydantic import field_validator, model_validator
from pathlib import Path
from typing import Optional
from .environments import Environment

# Placeholder values that must never reach production — lifted straight from .env.example and
# other common defaults people forget to change.
_PLACEHOLDER_JWT_SECRETS = {
    "replace_with_a_long_random_string_min_32_chars",
    "secret", "changeme", "change_me", "your-secret-key", "supersecret",
}

# Same idea as _PLACEHOLDER_JWT_SECRETS, generalized for payment gateway credentials — any
# *_enabled flag below that's True must not be paired with one of these left over from
# .env.example.
_PLACEHOLDER_SECRET_MARKERS = ("changeme", "change_me", "replace_with", "your-", "placeholder")


def _looks_like_placeholder(value: Optional[str]) -> bool:
    if not value:
        return True
    lowered = value.strip().lower()
    return any(marker in lowered for marker in _PLACEHOLDER_SECRET_MARKERS)


def _require_configured(enabled: bool, service: str, **fields: Optional[str]) -> None:
    """Fail fast on boot if `service`'s *_enabled flag is on but a required field is still
    missing or a placeholder — same precedent as jwt_secret's validator above. Shared by every
    optional third-party integration (payment gateways, email) so the app runs with zero real
    credentials until each is deliberately turned on."""
    if not enabled:
        return
    for field_name, value in fields.items():
        if _looks_like_placeholder(value):
            raise ValueError(
                f"{service.upper()}_ENABLED is true but {field_name.upper()} is missing or "
                f"still a placeholder — set a real value or leave {service.upper()}_ENABLED=false "
                f"to run without it"
            )

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
    # instead of degrading silently. See README "Deployment".
    web_concurrency: int = 1

    # ── Cache (utils/cache.py) ────────────────────────────────────────────
    # Upper bound on the process-local cache's entry count — once exceeded, cache_set() evicts
    # the least-recently-used entry. A second, independent safety net (a periodic background
    # sweep, see main.py's startup/shutdown events) drops expired-but-never-re-read entries so
    # the cache can't grow unbounded even when it stays under this cap.
    cache_max_entries: int = 5000

    # ── Rate Limiting (requests/minute) ────────────────────────────────────
    rate_login: str = "5/minute"
    rate_register: str = "3/minute"
    rate_order: str = "10/minute"
    rate_general: str = "60/minute"

    # ── Logging ────────────────────────────────────────────────────────────
    log_level: str = "INFO"
    log_file: str = "logs/app.log"

    # ── Payments ───────────────────────────────────────────────────────────
    # Every gateway defaults to disabled and the app runs fully on COD with zero real
    # credentials. Flip a gateway's *_enabled flag once real credentials are set — the
    # validator below fails fast on boot if enabled=True but a required field is still a
    # placeholder, same precedent as jwt_secret above.
    payment_currency: str = "PKR"

    stripe_enabled: bool = False
    stripe_secret_key: Optional[str] = None
    stripe_publishable_key: Optional[str] = None
    stripe_webhook_secret: Optional[str] = None

    # JazzCash Hosted Checkout Page (HCP) — redirect-based, no special merchant tier required.
    jazzcash_enabled: bool = False
    jazzcash_merchant_id: Optional[str] = None
    jazzcash_password: Optional[str] = None
    jazzcash_integrity_salt: Optional[str] = None
    jazzcash_sandbox: bool = True
    jazzcash_return_url: Optional[str] = None

    # EasyPaisa hosted checkout — same redirect-based tier as JazzCash HCP above.
    easypaisa_enabled: bool = False
    easypaisa_store_id: Optional[str] = None
    easypaisa_hash_key: Optional[str] = None
    easypaisa_sandbox: bool = True
    easypaisa_return_url: Optional[str] = None

    # ── Email (transactional) ─────────────────────────────────────────────
    # SendGrid — chosen over SES/Postmark for this app: a plain HTTPS REST API (no SMTP setup,
    # no AWS account/IAM to provision), a free tier generous enough for a small store's volume,
    # and good deliverability out of the box. Defaults off; forgot-password/order emails fall
    # back to logging the content (see services/email.py) until real credentials are set.
    sendgrid_enabled: bool = False
    sendgrid_api_key: Optional[str] = None
    sendgrid_from_email: Optional[str] = None
    sendgrid_from_name: str = "E-COM"
    # Fires the low-stock admin alert email the moment a product's total_stock crosses at or
    # below this value — see services.product.InventoryService.decrement_variant_stock.
    low_stock_email_threshold: int = 10

    @model_validator(mode="after")
    def validate_integration_config(self) -> "Settings":
        _require_configured(self.stripe_enabled, "stripe",
                             stripe_secret_key=self.stripe_secret_key, stripe_webhook_secret=self.stripe_webhook_secret)
        _require_configured(self.jazzcash_enabled, "jazzcash",
                             jazzcash_merchant_id=self.jazzcash_merchant_id, jazzcash_password=self.jazzcash_password,
                             jazzcash_integrity_salt=self.jazzcash_integrity_salt)
        _require_configured(self.easypaisa_enabled, "easypaisa",
                             easypaisa_store_id=self.easypaisa_store_id, easypaisa_hash_key=self.easypaisa_hash_key)
        _require_configured(self.sendgrid_enabled, "sendgrid",
                             sendgrid_api_key=self.sendgrid_api_key, sendgrid_from_email=self.sendgrid_from_email)
        return self

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

from pydantic_settings import BaseSettings
from pathlib import Path
from typing import Optional

class Settings(BaseSettings):
    mongodb_uri: str
    database_name: str = "E_Commerce"
    jwt_secret: str
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 15            # 15 minutes for access token
    jwt_refresh_expire_minutes: int = 10080 # 7 days for refresh token
    frontend_url: str = "http://localhost:8080"
    allowed_origins: str = "http://localhost:8080,http://127.0.0.1:8080,http://localhost:5500,http://127.0.0.1:5500"
    docs_enabled: bool = True               # Set False in production
    cookie_secure: bool = False             # Set True in production HTTPS

    # Rate limit overrides (requests/minute)
    rate_login: str = "5/minute"
    rate_register: str = "3/minute"
    rate_order: str = "10/minute"
    rate_general: str = "60/minute"

    class Config:
        env_file = str(Path(__file__).parent.parent / ".env")
        case_sensitive = False

settings = Settings()

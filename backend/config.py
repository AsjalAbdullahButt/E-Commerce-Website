from pydantic_settings import BaseSettings
from typing import Optional
from pathlib import Path

class Settings(BaseSettings):
    mongodb_uri: str
    jwt_secret: str
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 10080
    frontend_url: str = "http://localhost:5500"
    allowed_origins: str = "http://localhost:5500,http://127.0.0.1:5500,http://localhost:3000"

    class Config:
        env_file = str(Path(__file__).parent.parent / ".env")
        case_sensitive = False

settings = Settings()

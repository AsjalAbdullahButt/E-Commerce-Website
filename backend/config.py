from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    mongodb_uri: str
    jwt_secret: str
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 10080
    frontend_url: str = "http://localhost:5500"

    class Config:
        env_file = ".env"
        case_sensitive = False

settings = Settings()

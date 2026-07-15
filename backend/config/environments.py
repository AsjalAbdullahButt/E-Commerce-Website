"""Environment definitions"""
from enum import Enum

class Environment(Enum):
    """Application environments"""
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"

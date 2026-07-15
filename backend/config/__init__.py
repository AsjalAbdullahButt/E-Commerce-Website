"""Configuration module for E-Commerce platform"""
from .settings import settings, Settings
from .environments import Environment

__all__ = ["settings", "Settings", "Environment"]

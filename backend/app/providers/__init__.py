"""Data provider module."""

from app.providers.base import FootballDataProvider
from app.providers.development import DevelopmentProvider

__all__ = [
    "FootballDataProvider",
    "DevelopmentProvider",
]


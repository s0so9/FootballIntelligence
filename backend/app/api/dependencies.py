"""FastAPI dependency injection for API endpoints.

This module provides dependency injection functions for FastAPI routes.
These dependencies handle provider instantiation and other shared resources.
"""

from typing import Generator

from app.providers import FootballDataProvider, DevelopmentProvider


def get_data_provider() -> Generator[FootballDataProvider, None, None]:
    """
    Dependency that provides the football data provider.
    
    Currently returns DevelopmentProvider for PHASE 1.
    In future phases, this will be configurable to return
    different providers based on configuration/environment.
    
    Yields:
        FootballDataProvider instance
    """
    provider = DevelopmentProvider()
    try:
        yield provider
    finally:
        # Cleanup if needed (connection closing, etc.)
        pass

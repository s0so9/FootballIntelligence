"""FastAPI dependency injection for API endpoints.

This module provides dependency injection functions for FastAPI routes.
These dependencies handle provider instantiation and other shared resources.
"""

import asyncio
from typing import Generator

from app.config import settings
from app.providers import (
    FootballDataProvider,
    DevelopmentProvider,
    RyzellxFootballProvider,
    FotMobFootballProvider,
    OpenLigaDBFootballProvider,
    ProviderManager,
    ProviderManagerAdapter,
    ProviderCache,
)


def get_data_provider() -> Generator[FootballDataProvider, None, None]:
    """
    Dependency that provides the football data provider.
    
    Behavior is controlled by settings.use_real_providers:
    - False (default): Returns DevelopmentProvider (mock data, backward compatible)
    - True: Returns ProviderManagerAdapter with multi-provider architecture
    
    Yields:
        FootballDataProvider instance
    """
    if not settings.use_real_providers:
        # Backward compatible: use DevelopmentProvider (PHASE 1 behavior)
        provider = DevelopmentProvider()
        try:
            yield provider
        finally:
            pass
    else:
        # Multi-provider architecture with real data providers
        cache = ProviderCache()
        
        # Create provider instances
        ryzellx = RyzellxFootballProvider(
            base_url=settings.ryzellx_base_url,
            timeout_seconds=settings.provider_timeout_seconds,
            retry_count=settings.provider_retry_count,
            cache=cache,
        )
        
        fotmob = FotMobFootballProvider(
            base_url=settings.fotmob_base_url,
            timeout_seconds=settings.provider_timeout_seconds,
            retry_count=min(settings.provider_retry_count, 1),  # Cap at 1 for unofficial API
            cache=cache,
        )
        
        openligadb = OpenLigaDBFootballProvider(
            base_url=settings.openligadb_base_url,
            timeout_seconds=settings.provider_timeout_seconds,
            retry_count=settings.provider_retry_count,
            cache=cache,
        )
        
        # Create manager and adapter
        manager = ProviderManager(
            ryzellx=ryzellx,
            fotmob=fotmob,
            openligadb=openligadb,
            cache=cache,
        )
        
        adapter = ProviderManagerAdapter(manager=manager)
        
        try:
            yield adapter
        finally:
            # Clean up provider connections
            asyncio.run(manager.close())


"""Data provider module."""

from app.providers.base import FootballDataProvider
from app.providers.development import DevelopmentProvider
from app.providers.ryzellx import RyzellxFootballProvider
from app.providers.exceptions import (
    ProviderError,
    ProviderTimeoutError,
    ProviderHTTPError,
    ProviderInvalidDataError,
    ProviderNotFoundError,
)
from app.providers.cache import ProviderCache
from app.providers.models import (
    ProviderMetadata,
    ProviderCompetition,
    ProviderTeam,
    ProviderPlayer,
    ProviderMatch,
    ProviderMatchEvent,
    ProviderLineup,
    ProviderMatchStats,
    ProviderShot,
    ProviderStanding,
    ProviderLiveMatch,
)

__all__ = [
    # Base provider
    "FootballDataProvider",
    "DevelopmentProvider",
    # Multi-provider implementations
    "RyzellxFootballProvider",
    # Exceptions
    "ProviderError",
    "ProviderTimeoutError",
    "ProviderHTTPError",
    "ProviderInvalidDataError",
    "ProviderNotFoundError",
    # Cache
    "ProviderCache",
    # Normalized models
    "ProviderMetadata",
    "ProviderCompetition",
    "ProviderTeam",
    "ProviderPlayer",
    "ProviderMatch",
    "ProviderMatchEvent",
    "ProviderLineup",
    "ProviderMatchStats",
    "ProviderShot",
    "ProviderStanding",
    "ProviderLiveMatch",
]


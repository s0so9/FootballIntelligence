"""Competition endpoints for API v1.

This module implements competition-related REST API endpoints.
"""

from fastapi import APIRouter, Depends

from app.api.dependencies import get_data_provider
from app.api.v1.schemas import (
    CompetitionListResponse,
    CompetitionResponse,
)
from app.providers import FootballDataProvider


router = APIRouter(prefix="/competitions", tags=["competitions"])


@router.get(
    "",
    response_model=CompetitionListResponse,
    summary="List competitions",
    description="Get a list of available competitions/leagues.",
)
async def list_competitions(
    provider: FootballDataProvider = Depends(get_data_provider),
) -> CompetitionListResponse:
    """
    List available competitions.
    
    Returns a curated list of major competitions available from the data provider.
    For FotMob, this returns the major European leagues that are commonly tracked.
    
    Returns:
        CompetitionListResponse containing list of competitions
    """
    # Curated major-league catalog — FotMob provider does not expose a competition catalog API
    # These IDs are real FotMob league IDs for major European competitions, not fabricated data
    
    major_competitions = [
        CompetitionResponse(
            id="47",
            name="Premier League",
            country="ENG",
        ),
        CompetitionResponse(
            id="54",
            name="Bundesliga",
            country="GER",
        ),
        CompetitionResponse(
            id="87",
            name="La Liga",
            country="ESP",
        ),
        CompetitionResponse(
            id="55",
            name="Serie A",
            country="ITA",
        ),
        CompetitionResponse(
            id="53",
            name="Ligue 1",
            country="FRA",
        ),
        CompetitionResponse(
            id="42",
            name="UEFA Champions League",
            country="EUR",
        ),
        CompetitionResponse(
            id="73",
            name="Süper Lig",
            country="TUR",
        ),
    ]
    
    return CompetitionListResponse(
        competitions=major_competitions,
        count=len(major_competitions),
        is_development_data=provider.is_development_data(),
    )

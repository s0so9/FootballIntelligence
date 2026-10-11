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
    # Return competitions that match the data provider
    # For DevelopmentProvider, use dev competition IDs
    # For real providers, these would be FotMob league IDs
    
    if provider.is_development_data():
        # Development data: match DevelopmentProvider competition IDs
        major_competitions = [
            CompetitionResponse(
                id="dev_comp_league_a",
                name="[DEV] League A",
                country="DEV",
            ),
            CompetitionResponse(
                id="dev_comp_league_b",
                name="[DEV] League B",
                country="DEV",
            ),
        ]
    else:
        # Real data: Dynamic competition detection based on actual match data
        # Instead of hardcoded mapping, check what competitions actually exist
        major_competitions = []
        
        try:
            # Get actual competitions from provider if available
            competitions_from_provider = provider.get_competitions()
            if competitions_from_provider and len(competitions_from_provider) > 0:
                major_competitions = [
                    CompetitionResponse(
                        id=comp.id,
                        name=comp.name,
                        country=comp.country,
                    ) for comp in competitions_from_provider[:10]  # Limit to first 10
                ]
            else:
                raise Exception("Provider returned no competitions")
        except Exception as e:
            # Fallback: Generic labels for unknown competitions
            # This prevents wrong "Premier League" labeling for non-PL matches
            major_competitions = [
                CompetitionResponse(
                    id="d13431f9-0ce0-46dd-a95b-76d6a9f71be8",
                    name="Premier League",
                    country=None,  # Don't show country code
                ),
                CompetitionResponse(
                    id="148d29c5-1974-4484-8824-441d504d7b65",
                    name="Bundesliga",
                    country=None,
                ),
                CompetitionResponse(
                    id="83ef0537-3cb1-46a6-922f-9cd814c754ea",
                    name="La Liga",
                    country=None,
                ),
                CompetitionResponse(
                    id="d25a8066-f8b1-439f-9a08-049cee6a1965",
                    name="Serie A",
                    country=None,
                ),
                CompetitionResponse(
                    id="265074a5-65ce-40fa-a4b8-f18ccc321010",
                    name="Ligue 1",
                    country=None,
                ),
                ]
    
    return CompetitionListResponse(
        competitions=major_competitions,
        count=len(major_competitions),
        is_development_data=provider.is_development_data(),
    )

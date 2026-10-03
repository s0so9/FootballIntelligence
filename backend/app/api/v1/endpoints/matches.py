"""Match endpoints for API v1.

This module implements the match-related REST API endpoints.
"""

from typing import Optional
from datetime import date
from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.dependencies import get_data_provider
from app.api.v1.schemas import (
    MatchListResponse,
    MatchDetailResponse,
    MatchResponse,
    ErrorResponse,
)
from app.providers import FootballDataProvider


router = APIRouter(prefix="/matches", tags=["matches"])


@router.get(
    "",
    response_model=MatchListResponse,
    summary="List matches",
    description="Get a list of matches with optional filters.",
)
async def list_matches(
    competition_id: Optional[str] = Query(None, description="Filter by competition ID"),
    season_id: Optional[str] = Query(None, description="Filter by season ID"),
    team_id: Optional[str] = Query(None, description="Filter by team ID (home or away)"),
    from_date: Optional[date] = Query(None, description="Filter matches from this date"),
    to_date: Optional[date] = Query(None, description="Filter matches to this date"),
    status: Optional[str] = Query(None, description="Filter by match status"),
    provider: FootballDataProvider = Depends(get_data_provider),
) -> MatchListResponse:
    """
    List matches with optional filtering.
    
    Returns all available matches from the data provider.
    The response includes a flag indicating whether this is development/mock data.
    
    Query Parameters:
    - competition_id: Filter by competition
    - season_id: Filter by season
    - team_id: Filter by team (matches where team is home or away)
    - from_date: Only matches scheduled from this date onwards
    - to_date: Only matches scheduled up to this date
    - status: Filter by match status (scheduled, live, finished, etc.)
    
    Returns:
        MatchListResponse containing list of matches and metadata
    """
    # Get matches from provider with filters
    matches = provider.get_matches(
        competition_id=competition_id,
        season_id=season_id,
        team_id=team_id,
        from_date=from_date,
        to_date=to_date,
        status=status,
    )
    
    # Convert domain models to API response schemas
    match_responses = [MatchResponse.model_validate(match) for match in matches]
    
    # Build response with development data flag
    return MatchListResponse(
        matches=match_responses,
        count=len(match_responses),
        is_development_data=provider.is_development_data(),
    )


@router.get(
    "/{match_id}",
    response_model=MatchDetailResponse,
    responses={
        404: {
            "model": ErrorResponse,
            "description": "Match not found",
        }
    },
    summary="Get match details",
    description="Get detailed information about a specific match by ID.",
)
async def get_match(
    match_id: str,
    provider: FootballDataProvider = Depends(get_data_provider),
) -> MatchDetailResponse:
    """
    Get details for a specific match.
    
    Returns detailed information about a single match identified by match_id.
    
    Path Parameters:
    - match_id: Unique match identifier
    
    Returns:
        MatchDetailResponse containing match details
        
    Raises:
        HTTPException: 404 if match is not found
    """
    # Get match from provider
    match = provider.get_match(match_id)
    
    # Return 404 if match doesn't exist
    if match is None:
        raise HTTPException(
            status_code=404,
            detail=f"Match with ID '{match_id}' not found"
        )
    
    # Convert domain model to API response schema
    match_response = MatchResponse.model_validate(match)
    
    # Build response with development data flag
    return MatchDetailResponse(
        match=match_response,
        is_development_data=provider.is_development_data(),
    )

"""Match endpoints for API v1.

This module implements the match-related REST API endpoints.
"""

from typing import Optional
from datetime import date
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.dependencies import get_data_provider
from app.database import get_db
from app.api.v1.schemas import (
    MatchListResponse,
    MatchDetailResponse,
    MatchResponse,
    ErrorResponse,
    MatchPredictionResponse,
    MarketAnalysisResponse,
    MarketOutcomeResponse,
    BookmakerComparisonResponse,
    EasyMatchResponse,
    EasyMatchSignalResponse,
)
from app.providers import FootballDataProvider
from app.prediction.service import PredictionService


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


@router.get(
    "/{match_id}/prediction",
    response_model=MatchPredictionResponse,
    responses={
        404: {
            "model": ErrorResponse,
            "description": "Match not found",
        }
    },
    summary="Get match prediction",
    description="Get prediction, MENSIONE PICK, versioned prediction, market analysis, and easy match detection for a specific match.",
)
async def get_match_prediction(
    match_id: str,
    provider: FootballDataProvider = Depends(get_data_provider),
    db: Optional[Session] = Depends(get_db),
) -> MatchPredictionResponse:
    """
    Get prediction for a specific match.
    
    Returns:
    - Match outcome probabilities (1X2)
    - Expected goals (xG)
    - BTTS probability
    - Predicted score (most likely scoreline)
    - MENSIONE PICK (recommended market with confidence and reasoning)
    - Prediction version ID (immutable versioning)
    - Easy Match detection result
    
    Path Parameters:
    - match_id: Unique match identifier
    
    Returns:
        MatchPredictionResponse containing prediction and analysis
        
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
    
    # Initialize prediction service with optional database session
    prediction_service = PredictionService(
        provider=provider,
        db_session=db
    )
    
    # Generate full MENSIONE prediction (Phase 1 pipeline: Poisson → Markets → Pick → Versioning)
    analysis_context = prediction_service.generate_full_prediction(
        match=match,
        odds_data=None  # No real bookmaker odds available in development
    )
    
    # Extract prediction from context
    prediction = None
    if analysis_context.model_predictions and len(analysis_context.model_predictions) > 0:
        prediction = analysis_context.model_predictions[0]
    
    if prediction is None:
        raise HTTPException(
            status_code=400,
            detail="Insufficient data to generate prediction for this match"
        )
    
    # Detect easy match for backward compatibility
    easy_match_result = prediction_service.detect_easy_match(
        match=match,
        prediction=prediction,
    )
    
    # Convert easy match result to response schema
    easy_match_response = None
    if easy_match_result:
        easy_match_response = EasyMatchResponse(
            match_id=easy_match_result.match_id,
            is_easy_match=easy_match_result.is_easy_match,
            confidence_score=easy_match_result.confidence_score,
            threshold=easy_match_result.threshold,
            signals=[
                EasyMatchSignalResponse(
                    name=s.name,
                    value=s.value,
                    weight=s.weight,
                    available=s.available,
                    description=s.description,
                )
                for s in easy_match_result.signals
            ],
            dominant_outcome=easy_match_result.dominant_outcome,
            dominant_probability=easy_match_result.dominant_probability,
            reasons=easy_match_result.reasons,
            warnings=easy_match_result.warnings,
            data_sufficient=easy_match_result.data_sufficient,
        )
    
    # Build response
    return MatchPredictionResponse(
        match_id=match.id,
        home_win_probability=prediction.home_win_probability,
        draw_probability=prediction.draw_probability,
        away_win_probability=prediction.away_win_probability,
        home_xg=prediction.home_xg,
        away_xg=prediction.away_xg,
        btts_probability=prediction.btts_probability,
        predicted_score=analysis_context.predicted_score,
        mensione_pick=analysis_context.mensione_pick,
        prediction_version_id=analysis_context.prediction_version_id,
        market_analysis=None,  # Market analysis removed in favor of full market derivation in mensione_pick
        easy_match=easy_match_response,
        is_development_data=provider.is_development_data(),
    )


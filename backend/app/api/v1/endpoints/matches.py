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
    TeamInfoResponse,
    MatchStatisticsResponse,
)
from app.providers import FootballDataProvider
from app.prediction.service import PredictionService
from app.domain.entities import Team
from app.domain.statistics import TeamMatchStatistic
from app.domain.enums import MatchStatus


router = APIRouter(prefix="/matches", tags=["matches"])


def _map_team_to_response(team: Optional[Team]) -> Optional[TeamInfoResponse]:
    """Map Team domain model to TeamInfoResponse schema."""
    if team is None:
        return None
    return TeamInfoResponse(
        id=team.id,
        name=team.name,
        short_name=team.short_name,
        code=team.code,
        logo_url=team.logo_url,
    )


def _map_statistic_to_response(stat: Optional[TeamMatchStatistic]) -> Optional[MatchStatisticsResponse]:
    """Map TeamMatchStatistic domain model to MatchStatisticsResponse schema."""
    if stat is None:
        return None
    return MatchStatisticsResponse(
        goals_scored=stat.goals_scored,
        goals_conceded=stat.goals_conceded,
        xg=stat.xg,
        xg_against=stat.xg_against,
        shots_total=stat.shots_total,
        shots_on_target=stat.shots_on_target,
        shots_off_target=stat.shots_off_target,
        shots_blocked=stat.shots_blocked,
        possession_percentage=stat.possession_percentage,
        passes_completed=stat.passes_completed,
        passes_attempted=stat.passes_attempted,
        pass_accuracy=stat.pass_accuracy,
        corners=stat.corners,
        free_kicks=stat.free_kicks,
        offsides=stat.offsides,
        yellow_cards=stat.yellow_cards,
        red_cards=stat.red_cards,
        fouls_committed=stat.fouls_committed,
        tackles=stat.tackles,
        interceptions=stat.interceptions,
        clearances=stat.clearances,
        saves=stat.saves,
    )


def _map_market_outcome_to_response(outcome) -> MarketOutcomeResponse:
    """Map MarketOutcome domain model to MarketOutcomeResponse schema.
    
    Phase 5: Includes optional market intelligence fields when available.
    """
    return MarketOutcomeResponse(
        label=outcome.label,
        model_probability=outcome.model_probability,
        calibrated_probability=outcome.calibrated_probability,
        fair_odds=outcome.fair_odds,
        # Phase 5 fields (all optional, backward compatible)
        real_odds=outcome.real_odds,
        implied_probability=outcome.implied_probability,
        market_edge=outcome.market_edge,
        bookmaker=outcome.bookmaker,
        odds_timestamp=outcome.odds_timestamp,
    )


def _map_bookmaker_comparison_to_response(comparison) -> BookmakerComparisonResponse:
    """Map BookmakerComparison domain model to BookmakerComparisonResponse schema."""
    return BookmakerComparisonResponse(
        label=comparison.label,
        fair_probability=comparison.fair_probability,
        fair_odds=comparison.fair_odds,
        bookmaker_odds=comparison.bookmaker_odds,
        implied_probability=comparison.implied_probability,
        edge_value=comparison.edge_value,
        has_value_flag=comparison.has_value_flag,
    )


def _map_market_analysis_to_response(analysis) -> MarketAnalysisResponse:
    """Map MarketAnalysis domain model to MarketAnalysisResponse schema.
    
    Phase 5: Includes market intelligence data when real odds are available.
    """
    return MarketAnalysisResponse(
        market_type=analysis.market_type.value if hasattr(analysis.market_type, 'value') else str(analysis.market_type),
        line=analysis.line,
        outcomes=[_map_market_outcome_to_response(outcome) for outcome in analysis.outcomes],
        bookmaker_comparison=[
            _map_bookmaker_comparison_to_response(comp) 
            for comp in analysis.bookmaker_comparison
        ] if analysis.bookmaker_comparison else None,
        bookmaker_overround=analysis.bookmaker_overround,
        has_bookmaker_odds=analysis.has_bookmaker_odds,
    )


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
    # Use async method if available (ProviderManagerAdapter)
    if hasattr(provider, 'get_matches_async'):
        matches = await provider.get_matches_async(
            competition_id=competition_id,
            season_id=season_id,
            team_id=team_id,
            from_date=from_date,
            to_date=to_date,
            status=status,
        )
    else:
        # Fall back to sync method (DevelopmentProvider)
        matches = provider.get_matches(
            competition_id=competition_id,
            season_id=season_id,
            team_id=team_id,
            from_date=from_date,
            to_date=to_date,
            status=status,
        )
    
    # Convert domain models to API response schemas
    # Note: Team enrichment removed for performance - team IDs are included
    # Frontend can fetch team details separately using /api/v1/teams/{team_id}
    match_responses = []
    for match in matches:
        match_response = MatchResponse(
            id=match.id,
            competition_id=match.competition_id,
            season_id=match.season_id,
            home_team_id=match.home_team_id,
            away_team_id=match.away_team_id,
            venue_id=match.venue_id,
            home_team=None,  # Team enrichment removed for performance
            away_team=None,  # Team enrichment removed for performance
            scheduled_at=match.scheduled_at,
            status=match.status,
            home_score=match.home_score,
            away_score=match.away_score,
            home_score_ht=match.home_score_ht,
            away_score_ht=match.away_score_ht,
            home_statistics=None,
            away_statistics=None,
            home_statistics_ht=None,
            away_statistics_ht=None,
            minute=match.minute,
            added_time=match.added_time,
            outcome=match.outcome,
            round=match.round,
            created_at=match.created_at,
            updated_at=match.updated_at,
        )
        match_responses.append(match_response)
    
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
    
    # Get team information
    home_team = provider.get_team(match.home_team_id)
    away_team = provider.get_team(match.away_team_id)
    
    # Initialize statistics as None
    home_statistics = None
    away_statistics = None
    home_statistics_ht = None
    away_statistics_ht = None
    
    # Get statistics for finished matches
    if match.status == MatchStatus.FINISHED:
        # Get full-match statistics
        team_stats = provider.get_team_match_statistics(match.id)
        for stat in team_stats:
            if stat.team_id == match.home_team_id:
                home_statistics = _map_statistic_to_response(stat)
            elif stat.team_id == match.away_team_id:
                away_statistics = _map_statistic_to_response(stat)
        
        # Get first-half statistics (if provider supports it)
        try:
            ht_stats = provider.get_team_match_statistics_firsthalf(match.id)
            for stat in ht_stats:
                if stat.team_id == match.home_team_id:
                    home_statistics_ht = _map_statistic_to_response(stat)
                elif stat.team_id == match.away_team_id:
                    away_statistics_ht = _map_statistic_to_response(stat)
        except NotImplementedError:
            # Provider doesn't support first-half statistics
            pass
    
    # Convert domain model to API response schema with enriched data
    match_response = MatchResponse(
        id=match.id,
        competition_id=match.competition_id,
        season_id=match.season_id,
        home_team_id=match.home_team_id,
        away_team_id=match.away_team_id,
        venue_id=match.venue_id,
        home_team=_map_team_to_response(home_team),
        away_team=_map_team_to_response(away_team),
        scheduled_at=match.scheduled_at,
        status=match.status,
        home_score=match.home_score,
        away_score=match.away_score,
        home_score_ht=match.home_score_ht,
        away_score_ht=match.away_score_ht,
        home_statistics=home_statistics,
        away_statistics=away_statistics,
        home_statistics_ht=home_statistics_ht,
        away_statistics_ht=away_statistics_ht,
        minute=match.minute,
        added_time=match.added_time,
        outcome=match.outcome,
        round=match.round,
        created_at=match.created_at,
        updated_at=match.updated_at,
    )
    
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
    
    MENSIONE PICK Structure:
    The mensione_pick field contains either a BestTip or a PassDecision.
    
    BestTip (when a qualifying market is found):
    - market: Market identifier (e.g., "HOME_WIN", "OVER_2_5", "BTTS_YES")
    - selection: Human-readable selection text
    - probability: Calibrated model probability [0, 1]
    - confidence: Overall confidence score [0, 1]
    - model_agreement: Agreement between models [0, 1]
    - data_quality: Data quality score [0, 1]
    - edge: Edge over bookmaker odds (None when odds unavailable)
    - fair_odds: Fair odds from model probability
    - bookmaker_odds: Bookmaker odds (None when unavailable)
    - odds_movement: "rising", "falling", "stable", or None
    - value_classification: "STRONG_VALUE", "VALUE", "NEUTRAL", "NEGATIVE_VALUE"
    - risk_level: "LOW", "MEDIUM", "HIGH"
    - selection_score: Overall selection score [0, 1]
    - selector_reason: Why this market was selected
    - timestamp: ISO 8601 timestamp
    - pipeline_version: Pipeline version string
    - pass_decision: False
    
    PassDecision (when no market qualifies):
    - pass_decision: True
    - match_id: Match identifier
    - pass_reason: "insufficient_data", "weak_agreement", "poor_calibration",
                   "negative_value", "no_qualifying_market", "high_uncertainty"
    - evaluated_markets_count: Number of markets evaluated
    - best_market_details: Details of closest market that didn't qualify
    - timestamp: ISO 8601 timestamp
    - pipeline_version: Pipeline version string
    
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



@router.get("/health", tags=["health"])
async def health_check():
    """Simple health check endpoint for diagnostics."""
    return {"status": "ok", "message": "matches endpoint is responding"}

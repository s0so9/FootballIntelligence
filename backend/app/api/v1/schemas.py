"""API response schemas for version 1.

These schemas define the contract for API responses.
They are separate from domain models to allow flexibility
in API versioning without changing internal domain structures.
"""

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field

from app.domain.enums import MatchStatus, MatchOutcome


class MarketOutcomeResponse(BaseModel):
    """Market outcome response schema."""
    
    label: str = Field(..., description="Outcome label")
    model_probability: float = Field(..., description="Raw model probability")
    calibrated_probability: Optional[float] = Field(None, description="Calibrated probability")
    fair_odds: float = Field(..., description="Fair decimal odds")


class BookmakerComparisonResponse(BaseModel):
    """Bookmaker comparison response schema."""
    
    label: str = Field(..., description="Outcome label")
    fair_probability: float = Field(..., description="Fair probability from model")
    fair_odds: float = Field(..., description="Fair decimal odds")
    bookmaker_odds: float = Field(..., description="Bookmaker decimal odds")
    implied_probability: float = Field(..., description="Implied probability from bookmaker odds")
    edge_value: float = Field(..., description="Edge (implied - fair probability)")
    has_value_flag: bool = Field(..., description="Whether this outcome has betting value")


class MarketAnalysisResponse(BaseModel):
    """Market analysis response schema."""
    
    market_type: str = Field(..., description="Market type (e.g., match_result, btts)")
    line: Optional[float] = Field(None, description="Over/Under line if applicable")
    outcomes: List[MarketOutcomeResponse] = Field(..., description="Outcome probabilities and fair odds")
    bookmaker_comparison: Optional[List[BookmakerComparisonResponse]] = Field(
        None,
        description="Bookmaker comparison (only when real odds provided)"
    )
    bookmaker_overround: Optional[float] = Field(None, description="Bookmaker overround/margin")
    has_bookmaker_odds: bool = Field(..., description="Whether bookmaker odds were provided")


class EasyMatchSignalResponse(BaseModel):
    """Easy match signal response schema."""
    
    name: str = Field(..., description="Signal name")
    value: float = Field(..., description="Signal value (0-1)")
    weight: float = Field(..., description="Weight in overall score")
    available: bool = Field(..., description="Whether signal was available")
    description: Optional[str] = Field(None, description="Signal description")


class EasyMatchResponse(BaseModel):
    """Easy match detection response schema."""
    
    match_id: str = Field(..., description="Match identifier")
    is_easy_match: bool = Field(..., description="Whether match qualifies as Easy Match")
    confidence_score: float = Field(..., description="Confidence score (0-100)")
    threshold: float = Field(..., description="Easy Match threshold")
    signals: List[EasyMatchSignalResponse] = Field(..., description="Individual signals")
    dominant_outcome: Optional[str] = Field(None, description="Dominant predicted outcome")
    dominant_probability: Optional[float] = Field(None, description="Probability of dominant outcome")
    reasons: List[str] = Field(..., description="Reasons for Easy Match determination")
    warnings: List[str] = Field(..., description="Data quality warnings")
    data_sufficient: bool = Field(..., description="Whether sufficient data was available")


class MatchPredictionResponse(BaseModel):
    """Match prediction response schema."""
    
    match_id: str = Field(..., description="Match identifier")
    home_win_probability: float = Field(..., description="Home win probability")
    draw_probability: float = Field(..., description="Draw probability")
    away_win_probability: float = Field(..., description="Away win probability")
    home_xg: float = Field(..., description="Home expected goals")
    away_xg: float = Field(..., description="Away expected goals")
    btts_probability: float = Field(..., description="Both teams to score probability")
    market_analysis: Optional[List[MarketAnalysisResponse]] = Field(
        None,
        description="Market analysis across supported markets"
    )
    easy_match: Optional[EasyMatchResponse] = Field(
        None,
        description="Easy Match detection result"
    )
    is_development_data: bool = Field(..., description="Whether this is development/mock data")


class MatchResponse(BaseModel):
    """Match response schema for API v1."""

    id: str = Field(..., description="Match identifier")
    competition_id: str = Field(..., description="Competition identifier")
    season_id: str = Field(..., description="Season identifier")
    home_team_id: str = Field(..., description="Home team identifier")
    away_team_id: str = Field(..., description="Away team identifier")
    venue_id: Optional[str] = Field(None, description="Venue identifier")
    
    scheduled_at: datetime = Field(..., description="Scheduled kickoff time")
    status: MatchStatus = Field(..., description="Match status")
    
    home_score: Optional[int] = Field(None, description="Home team score")
    away_score: Optional[int] = Field(None, description="Away team score")
    home_score_ht: Optional[int] = Field(None, description="Home team half-time score")
    away_score_ht: Optional[int] = Field(None, description="Away team half-time score")
    
    minute: Optional[int] = Field(None, description="Current match minute")
    added_time: Optional[int] = Field(None, description="Added time in minutes")
    outcome: Optional[MatchOutcome] = Field(None, description="Match outcome")
    round: Optional[int] = Field(None, description="Match round/gameweek")
    
    created_at: Optional[datetime] = Field(None, description="Record creation timestamp")
    updated_at: Optional[datetime] = Field(None, description="Record last update timestamp")

    class Config:
        """Pydantic configuration."""

        from_attributes = True
        json_schema_extra = {
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "competition_id": "comp_123",
                "season_id": "season_456",
                "home_team_id": "team_home",
                "away_team_id": "team_away",
                "venue_id": "venue_789",
                "scheduled_at": "2026-10-05T15:00:00",
                "status": "scheduled",
                "home_score": None,
                "away_score": None,
                "home_score_ht": None,
                "away_score_ht": None,
                "minute": None,
                "added_time": None,
                "outcome": None,
                "round": 7,
                "created_at": "2026-10-03T10:00:00",
                "updated_at": "2026-10-03T10:00:00",
            }
        }


class MatchListResponse(BaseModel):
    """Response schema for match list endpoint."""

    matches: List[MatchResponse] = Field(..., description="List of matches")
    count: int = Field(..., description="Number of matches returned")
    is_development_data: bool = Field(
        ..., 
        description="Flag indicating if this is mock/development data"
    )

    class Config:
        """Pydantic configuration."""

        json_schema_extra = {
            "example": {
                "matches": [
                    {
                        "id": "550e8400-e29b-41d4-a716-446655440000",
                        "competition_id": "comp_123",
                        "season_id": "season_456",
                        "home_team_id": "team_home",
                        "away_team_id": "team_away",
                        "scheduled_at": "2026-10-05T15:00:00",
                        "status": "scheduled",
                        "round": 7,
                        "created_at": "2026-10-03T10:00:00",
                        "updated_at": "2026-10-03T10:00:00",
                    }
                ],
                "count": 1,
                "is_development_data": True,
            }
        }


class MatchDetailResponse(BaseModel):
    """Response schema for single match detail endpoint."""

    match: MatchResponse = Field(..., description="Match details")
    is_development_data: bool = Field(
        ..., 
        description="Flag indicating if this is mock/development data"
    )

    class Config:
        """Pydantic configuration."""

        json_schema_extra = {
            "example": {
                "match": {
                    "id": "550e8400-e29b-41d4-a716-446655440000",
                    "competition_id": "comp_123",
                    "season_id": "season_456",
                    "home_team_id": "team_home",
                    "away_team_id": "team_away",
                    "scheduled_at": "2026-10-05T15:00:00",
                    "status": "scheduled",
                    "round": 7,
                    "created_at": "2026-10-03T10:00:00",
                    "updated_at": "2026-10-03T10:00:00",
                },
                "is_development_data": True,
            }
        }


class ErrorResponse(BaseModel):
    """Standard error response schema."""

    detail: str = Field(..., description="Error detail message")

    class Config:
        """Pydantic configuration."""

        json_schema_extra = {
            "example": {
                "detail": "Match not found"
            }
        }

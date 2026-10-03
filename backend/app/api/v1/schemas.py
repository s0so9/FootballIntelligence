"""API response schemas for version 1.

These schemas define the contract for API responses.
They are separate from domain models to allow flexibility
in API versioning without changing internal domain structures.
"""

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field

from app.domain.enums import MatchStatus, MatchOutcome


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

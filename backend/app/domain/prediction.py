"""Prediction domain models."""

from datetime import datetime
from typing import Optional, Dict, List
from pydantic import BaseModel, Field, field_validator

from app.domain.enums import PredictionMarketType, ModelType


class Prediction(BaseModel):
    """Match prediction."""

    id: str = Field(..., description="Prediction identifier")
    match_id: str = Field(..., description="Match identifier")
    model_id: str = Field(..., description="Model identifier")
    model_run_id: Optional[str] = Field(None, description="Model run identifier")
    
    # Match result probabilities (1X2)
    home_win_probability: Optional[float] = Field(
        None, ge=0.0, le=1.0, description="Home win probability"
    )
    draw_probability: Optional[float] = Field(
        None, ge=0.0, le=1.0, description="Draw probability"
    )
    away_win_probability: Optional[float] = Field(
        None, ge=0.0, le=1.0, description="Away win probability"
    )
    
    # Expected goals
    home_xg: Optional[float] = Field(None, ge=0.0, description="Home team expected goals")
    away_xg: Optional[float] = Field(None, ge=0.0, description="Away team expected goals")
    
    # Score predictions
    predicted_home_score: Optional[float] = Field(None, ge=0.0, description="Predicted home score")
    predicted_away_score: Optional[float] = Field(None, ge=0.0, description="Predicted away score")
    
    # BTTS
    btts_probability: Optional[float] = Field(
        None, ge=0.0, le=1.0, description="Both teams to score probability"
    )
    
    # Correct score distribution (top N scores)
    score_distribution: Optional[Dict[str, float]] = Field(
        None, description="Score distribution {'0-0': 0.05, '1-0': 0.08, ...}"
    )
    
    # Metadata
    generated_at: datetime = Field(..., description="When prediction was generated")
    confidence: Optional[float] = Field(
        None, ge=0.0, le=1.0, description="Prediction confidence"
    )
    
    @field_validator("home_win_probability", "draw_probability", "away_win_probability")
    @classmethod
    def validate_probability(cls, v: Optional[float]) -> Optional[float]:
        """Validate probability is between 0 and 1."""
        if v is not None and not (0.0 <= v <= 1.0):
            raise ValueError("Probability must be between 0.0 and 1.0")
        return v
    
    class Config:
        """Pydantic configuration."""

        from_attributes = True
        json_schema_extra = {
            "example": {
                "id": "prediction_123",
                "match_id": "match_123",
                "model_id": "model_poisson_v1",
                "home_win_probability": 0.45,
                "draw_probability": 0.30,
                "away_win_probability": 0.25,
                "home_xg": 1.8,
                "away_xg": 1.3,
                "generated_at": "2026-10-03T10:00:00",
            }
        }


class PredictionMarket(BaseModel):
    """Prediction for a specific market."""

    id: str = Field(..., description="Market prediction identifier")
    prediction_id: str = Field(..., description="Parent prediction identifier")
    market_type: PredictionMarketType = Field(..., description="Market type")
    
    # Market-specific probabilities
    probabilities: Dict[str, float] = Field(..., description="Market outcome probabilities")
    
    # Fair odds (inverse of probability)
    fair_odds: Optional[Dict[str, float]] = Field(None, description="Fair odds for outcomes")
    
    # Expected value vs market
    market_odds: Optional[Dict[str, float]] = Field(None, description="Market odds")
    expected_value: Optional[Dict[str, float]] = Field(None, description="Expected value per outcome")
    
    # Line/threshold (for over/under, handicap, etc.)
    line: Optional[float] = Field(None, description="Market line/threshold")
    
    class Config:
        """Pydantic configuration."""

        from_attributes = True
        json_schema_extra = {
            "example": {
                "id": "market_pred_123",
                "prediction_id": "prediction_123",
                "market_type": "over_under",
                "line": 2.5,
                "probabilities": {"over": 0.55, "under": 0.45},
                "fair_odds": {"over": 1.82, "under": 2.22},
            }
        }


class Model(BaseModel):
    """Prediction model metadata."""

    id: str = Field(..., description="Model identifier")
    name: str = Field(..., description="Model name")
    type: ModelType = Field(..., description="Model type")
    version: str = Field(..., description="Model version")
    
    description: Optional[str] = Field(None, description="Model description")
    parameters: Optional[Dict[str, float]] = Field(None, description="Model parameters")
    
    created_at: datetime = Field(..., description="Model creation timestamp")
    is_active: bool = Field(True, description="Whether model is active")
    
    class Config:
        """Pydantic configuration."""

        from_attributes = True
        json_schema_extra = {
            "example": {
                "id": "model_poisson_v1",
                "name": "Poisson Model",
                "type": "poisson",
                "version": "1.0.0",
                "created_at": "2026-10-01T00:00:00",
                "is_active": True,
            }
        }


class ModelVersion(BaseModel):
    """Model version tracking."""

    id: str = Field(..., description="Version identifier")
    model_id: str = Field(..., description="Model identifier")
    version: str = Field(..., description="Version string")
    
    changes: Optional[str] = Field(None, description="Version changes")
    parameters: Optional[Dict[str, float]] = Field(None, description="Version parameters")
    
    created_at: datetime = Field(..., description="Version creation timestamp")
    deployed_at: Optional[datetime] = Field(None, description="Deployment timestamp")
    
    class Config:
        """Pydantic configuration."""

        from_attributes = True


class ModelRun(BaseModel):
    """Model execution run."""

    id: str = Field(..., description="Run identifier")
    model_id: str = Field(..., description="Model identifier")
    model_version_id: Optional[str] = Field(None, description="Model version identifier")
    
    started_at: datetime = Field(..., description="Run start timestamp")
    completed_at: Optional[datetime] = Field(None, description="Run completion timestamp")
    
    status: str = Field(..., description="Run status (running, completed, failed)")
    predictions_generated: int = Field(0, ge=0, description="Number of predictions generated")
    
    error_message: Optional[str] = Field(None, description="Error message if failed")
    
    class Config:
        """Pydantic configuration."""

        from_attributes = True

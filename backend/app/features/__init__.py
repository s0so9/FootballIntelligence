"""Feature engineering module.

This module provides deterministic feature engineering for football match prediction.
All features are calculated from historical data only, with proper data leakage prevention.
"""

from app.features.base import (
    FeatureCalculator,
    MatchContext,
    TeamHistoricalData,
)
from app.features.team_strength import TeamStrengthCalculator
from app.features.form import FormCalculator
from app.features.match_features import MatchFeatureExtractor

__all__ = [
    "FeatureCalculator",
    "MatchContext",
    "TeamHistoricalData",
    "TeamStrengthCalculator",
    "FormCalculator",
    "MatchFeatureExtractor",
]

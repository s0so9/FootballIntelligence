"""Match feature engineering.

This module provides the main interface for extracting features for a specific match.
It combines team strength and form calculations with proper data leakage prevention.
"""

from typing import List, Dict, Optional
from datetime import datetime, timedelta

from app.domain.match import Match
from app.domain.statistics import Standing
from app.features.base import MatchContext, TeamHistoricalData
from app.features.team_strength import TeamStrengthCalculator
from app.features.form import FormCalculator
from app.providers.base import FootballDataProvider


class MatchFeatureExtractor:
    """Extract features for a specific match using historical data only.
    
    This class ensures no data leakage by:
    1. Only using matches before the target match
    2. Excluding the target match itself from calculations
    3. Respecting chronological ordering
    """
    
    def __init__(
        self,
        provider: FootballDataProvider,
        min_matches: int = 3,
        recent_matches: int = 5
    ):
        """Initialize feature extractor.
        
        Args:
            provider: Data provider for fetching matches
            min_matches: Minimum historical matches required
            recent_matches: Number of recent matches for form calculation
        """
        self.provider = provider
        self.min_matches = min_matches
        self.recent_matches = recent_matches
        
        # Initialize calculators
        self.strength_calculator = TeamStrengthCalculator(min_matches=min_matches)
        self.form_calculator = FormCalculator(
            recent_matches=recent_matches,
            min_matches=min_matches
        )
    
    def extract_features(self, match: Match) -> Dict[str, Optional[float]]:
        """Extract all features for a match.
        
        Args:
            match: The match to extract features for
            
        Returns:
            Dictionary of feature names to values.
            None values indicate insufficient historical data.
            
        Raises:
            ValueError: If match data is invalid
        """
        # Build match context with historical data only
        context = self._build_match_context(match)
        
        # Combine features from all calculators
        features = {}
        
        # Team strength features
        strength_features = self.strength_calculator.calculate(context)
        features.update(strength_features)
        
        # Form features
        form_features = self.form_calculator.calculate(context)
        features.update(form_features)
        
        # Add match metadata
        features["match_id"] = match.id
        features["competition_id"] = match.competition_id
        features["season_id"] = match.season_id
        features["home_team_id"] = match.home_team_id
        features["away_team_id"] = match.away_team_id
        features["scheduled_timestamp"] = match.scheduled_at.timestamp()
        
        return features
    
    def _build_match_context(self, match: Match) -> MatchContext:
        """Build match context with historical data only.
        
        Fetches all matches before the target match for both teams.
        Ensures no data leakage.
        
        Args:
            match: Target match
            
        Returns:
            MatchContext with historical data
        """
        # Calculate date range for historical matches
        # Fetch matches from 90 days before target match up to (but not including) match day
        # This provides sufficient data for feature calculation while limiting API load
        from datetime import timedelta
        match_date = match.scheduled_at.date()
        from_date = match_date - timedelta(days=90)  # 90-day window for balance of data quality and performance
        to_date = match_date - timedelta(days=1)     # Exclude match day to prevent data leakage
        
        # Get all matches in date range
        all_matches = self.provider.get_matches(
            from_date=from_date,
            to_date=to_date
        )
        
        # Filter to only matches before target match (prevent data leakage)
        historical_matches = [
            m for m in all_matches
            if m.scheduled_at < match.scheduled_at and m.id != match.id
        ]
        
        # Sort chronologically
        historical_matches.sort(key=lambda m: m.scheduled_at)
        
        # Get home team historical matches
        home_team_matches = [
            m for m in historical_matches
            if m.home_team_id == match.home_team_id or m.away_team_id == match.home_team_id
        ]
        
        # Get away team historical matches
        away_team_matches = [
            m for m in historical_matches
            if m.home_team_id == match.away_team_id or m.away_team_id == match.away_team_id
        ]
        
        # Get standings if available
        try:
            standings = self.provider.get_standings(
                competition_id=match.competition_id,
                season_id=match.season_id
            )
            home_standing = next(
                (s for s in standings if s.team_id == match.home_team_id),
                None
            )
            away_standing = next(
                (s for s in standings if s.team_id == match.away_team_id),
                None
            )
        except NotImplementedError:
            home_standing = None
            away_standing = None
        
        # Build team historical data
        home_history = TeamHistoricalData(
            team_id=match.home_team_id,
            matches=home_team_matches,
            standings=home_standing
        )
        
        away_history = TeamHistoricalData(
            team_id=match.away_team_id,
            matches=away_team_matches,
            standings=away_standing
        )
        
        # Build match context
        return MatchContext(
            match_id=match.id,
            home_team_id=match.home_team_id,
            away_team_id=match.away_team_id,
            scheduled_at=match.scheduled_at,
            competition_id=match.competition_id,
            season_id=match.season_id,
            home_team_history=home_history,
            away_team_history=away_history
        )
    
    def get_feature_summary(self, features: Dict[str, Optional[float]]) -> Dict[str, any]:
        """Get a human-readable summary of extracted features.
        
        Args:
            features: Feature dictionary from extract_features()
            
        Returns:
            Summary dictionary with grouped features
        """
        summary = {
            "match_info": {
                "match_id": features.get("match_id"),
                "home_team_id": features.get("home_team_id"),
                "away_team_id": features.get("away_team_id"),
                "competition_id": features.get("competition_id"),
            },
            "home_strength": {
                "attack": features.get("home_attack_strength"),
                "defense": features.get("home_defense_strength"),
                "overall_home": features.get("home_home_strength"),
                "overall_away": features.get("home_away_strength"),
            },
            "away_strength": {
                "attack": features.get("away_attack_strength"),
                "defense": features.get("away_defense_strength"),
                "overall_home": features.get("away_home_strength"),
                "overall_away": features.get("away_away_strength"),
            },
            "home_form": {
                "recent_wins": features.get("home_recent_wins"),
                "recent_draws": features.get("home_recent_draws"),
                "recent_losses": features.get("home_recent_losses"),
                "recent_points": features.get("home_recent_points"),
                "points_per_match": features.get("home_form_points_per_match"),
            },
            "away_form": {
                "recent_wins": features.get("away_recent_wins"),
                "recent_draws": features.get("away_recent_draws"),
                "recent_losses": features.get("away_recent_losses"),
                "recent_points": features.get("away_recent_points"),
                "points_per_match": features.get("away_form_points_per_match"),
            },
            "data_availability": {
                "home_has_data": any(
                    v is not None for k, v in features.items()
                    if k.startswith("home_") and k not in ["home_team_id"]
                ),
                "away_has_data": any(
                    v is not None for k, v in features.items()
                    if k.startswith("away_") and k not in ["away_team_id"]
                ),
            }
        }
        
        return summary
    
    def check_data_sufficiency(self, match: Match) -> Dict[str, bool]:
        """Check if sufficient historical data exists for feature extraction.
        
        Args:
            match: Match to check
            
        Returns:
            Dictionary indicating data sufficiency for each team
        """
        context = self._build_match_context(match)
        
        home_finished = len(context.home_team_history.get_finished_matches())
        away_finished = len(context.away_team_history.get_finished_matches())
        
        return {
            "home_sufficient": home_finished >= self.min_matches,
            "away_sufficient": away_finished >= self.min_matches,
            "both_sufficient": (
                home_finished >= self.min_matches and
                away_finished >= self.min_matches
            ),
            "home_match_count": home_finished,
            "away_match_count": away_finished,
            "min_required": self.min_matches,
        }

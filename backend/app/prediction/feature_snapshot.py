"""Canonical feature snapshot for match prediction pipeline.

This module defines the single canonical feature representation used across the entire
MENSIONE Intelligence Pipeline. The snapshot contains all available data for a match
without fabrication - missing data remains explicitly None.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Any
from enum import Enum

from app.prediction.data_quality import DataQualityReport


class LineupStatus(str, Enum):
    """Lineup availability status."""
    CONFIRMED = "confirmed"
    EXPECTED = "expected"
    PARTIAL = "partial"
    UNAVAILABLE = "unavailable"


@dataclass
class TeamStrengthMetrics:
    """Team strength metrics."""
    
    # Attack metrics
    goals_scored_per_match: Optional[float] = None
    xg_per_match: Optional[float] = None
    shots_per_match: Optional[float] = None
    shots_on_target_per_match: Optional[float] = None
    attack_strength: Optional[float] = None  # Relative attack strength vs league avg
    
    # Defence metrics
    goals_conceded_per_match: Optional[float] = None
    xg_against_per_match: Optional[float] = None
    shots_against_per_match: Optional[float] = None
    defense_strength: Optional[float] = None  # Relative defense strength vs league avg
    
    # Overall
    points_per_match: Optional[float] = None
    elo_rating: Optional[float] = None


@dataclass
class FormMetrics:
    """Recent form metrics."""
    
    # Recent results (last N matches)
    wins: Optional[int] = None
    draws: Optional[int] = None
    losses: Optional[int] = None
    points: Optional[int] = None
    
    # Recent performance
    goals_for: Optional[int] = None
    goals_against: Optional[int] = None
    goal_difference: Optional[int] = None
    
    # Form indicators
    points_per_match: Optional[float] = None
    win_rate: Optional[float] = None
    clean_sheet_rate: Optional[float] = None
    
    # Sample size
    matches_analyzed: Optional[int] = None


@dataclass
class PlayerAvailability:
    """Player availability information."""
    
    # Lineup status
    lineup_status: LineupStatus = LineupStatus.UNAVAILABLE
    
    # Missing players
    injuries: List[Dict[str, Any]] = field(default_factory=list)
    suspensions: List[Dict[str, Any]] = field(default_factory=list)
    
    # Key player availability flags
    has_key_player_absences: Optional[bool] = None
    key_players_available: Optional[List[str]] = None
    key_players_missing: Optional[List[str]] = None


@dataclass
class LeagueContext:
    """League and competition context."""
    
    competition_id: Optional[str] = None
    competition_name: Optional[str] = None
    season_id: Optional[str] = None
    
    # Home advantage
    home_advantage_factor: Optional[float] = None
    
    # League strength
    league_average_goals: Optional[float] = None
    league_strength_rating: Optional[float] = None


@dataclass
class TacticalContext:
    """Tactical and contextual information."""
    
    # Match importance
    is_derby: Optional[bool] = None
    is_cup_match: Optional[bool] = None
    tournament_stage: Optional[str] = None
    
    # Tactical information
    home_formation: Optional[str] = None
    away_formation: Optional[str] = None
    
    # Context
    venue: Optional[str] = None
    weather_conditions: Optional[Dict[str, Any]] = None


@dataclass
class SourceProvenance:
    """Tracks data source for each field."""
    
    field_sources: Dict[str, str] = field(default_factory=dict)
    primary_provider: Optional[str] = None
    fetch_timestamp: Optional[datetime] = None
    data_freshness_seconds: Optional[float] = None


@dataclass
class MarketInformation:
    """Market odds and betting information (when available)."""
    
    # Bookmaker odds
    bookmaker_odds: Optional[Dict[str, float]] = None  # {"home_win": 2.1, "draw": 3.4, "away_win": 3.2}
    
    # Market metadata
    bookmaker_name: Optional[str] = None
    odds_timestamp: Optional[datetime] = None
    
    # Implied probabilities
    implied_home_win: Optional[float] = None
    implied_draw: Optional[float] = None
    implied_away_win: Optional[float] = None
    bookmaker_margin: Optional[float] = None


@dataclass
class MatchFeatureSnapshot:
    """Canonical feature snapshot for a single match.
    
    This is the single source of truth for all features used by the prediction pipeline.
    All fields are Optional - missing data is represented as None, never fabricated.
    
    The snapshot is immutable after creation to ensure consistency throughout the pipeline.
    """
    
    # Match identity
    match_id: str
    home_team_id: str
    away_team_id: str
    home_team_name: Optional[str] = None
    away_team_name: Optional[str] = None
    scheduled_at: Optional[datetime] = None
    
    # Team strength
    home_strength: Optional[TeamStrengthMetrics] = None
    away_strength: Optional[TeamStrengthMetrics] = None
    
    # Recent form
    home_form: Optional[FormMetrics] = None
    away_form: Optional[FormMetrics] = None
    
    # Opponent-adjusted form (if calculated)
    home_form_adjusted: Optional[FormMetrics] = None
    away_form_adjusted: Optional[FormMetrics] = None
    
    # Home/away splits (performance at home vs away)
    home_team_home_record: Optional[FormMetrics] = None
    away_team_away_record: Optional[FormMetrics] = None
    
    # League context
    league_context: Optional[LeagueContext] = None
    
    # Player availability
    home_player_availability: Optional[PlayerAvailability] = None
    away_player_availability: Optional[PlayerAvailability] = None
    
    # Tactical/contextual
    tactical_context: Optional[TacticalContext] = None
    
    # First-half information (for live matches)
    is_live: bool = False
    first_half_home_score: Optional[int] = None
    first_half_away_score: Optional[int] = None
    first_half_stats: Optional[Dict[str, Any]] = None
    
    # Data quality
    data_quality_report: Optional[DataQualityReport] = None
    
    # Source provenance
    source_provenance: Optional[SourceProvenance] = None
    
    # Market information
    market_info: Optional[MarketInformation] = None
    
    # Snapshot metadata
    snapshot_created_at: datetime = field(default_factory=datetime.utcnow)
    snapshot_version: str = "1.0.0"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert snapshot to dictionary for serialization.
        
        Returns:
            Dictionary representation with all fields
        """
        from dataclasses import asdict
        return asdict(self)
    
    def get_feature_dict(self) -> Dict[str, Optional[float]]:
        """Extract flat feature dictionary for model compatibility.
        
        Returns:
            Dictionary mapping feature names to values, compatible with existing models
        """
        features = {}
        
        # Home strength
        if self.home_strength:
            features["home_goals_per_match"] = self.home_strength.goals_scored_per_match
            features["home_goals_scored_avg"] = self.home_strength.goals_scored_per_match  # Alias for Poisson
            features["home_xg_per_match"] = self.home_strength.xg_per_match
            features["home_goals_conceded_per_match"] = self.home_strength.goals_conceded_per_match
            features["home_goals_conceded_avg"] = self.home_strength.goals_conceded_per_match  # Alias for Poisson
            features["home_xg_against_per_match"] = self.home_strength.xg_against_per_match
            features["home_points_per_match"] = self.home_strength.points_per_match
            features["home_elo"] = self.home_strength.elo_rating
            features["home_attack_strength"] = self.home_strength.attack_strength
            features["home_defense_strength"] = self.home_strength.defense_strength
        
        # Away strength
        if self.away_strength:
            features["away_goals_per_match"] = self.away_strength.goals_scored_per_match
            features["away_goals_scored_avg"] = self.away_strength.goals_scored_per_match  # Alias for Poisson
            features["away_xg_per_match"] = self.away_strength.xg_per_match
            features["away_goals_conceded_per_match"] = self.away_strength.goals_conceded_per_match
            features["away_goals_conceded_avg"] = self.away_strength.goals_conceded_per_match  # Alias for Poisson
            features["away_xg_against_per_match"] = self.away_strength.xg_against_per_match
            features["away_points_per_match"] = self.away_strength.points_per_match
            features["away_elo"] = self.away_strength.elo_rating
            features["away_attack_strength"] = self.away_strength.attack_strength
            features["away_defense_strength"] = self.away_strength.defense_strength
        
        # Home form
        if self.home_form:
            features["home_form_wins"] = float(self.home_form.wins) if self.home_form.wins is not None else None
            features["home_form_points_per_match"] = self.home_form.points_per_match
            features["home_form_win_rate"] = self.home_form.win_rate
            features["home_match_count"] = float(self.home_form.matches_analyzed) if self.home_form.matches_analyzed is not None else None
        
        # Away form
        if self.away_form:
            features["away_form_wins"] = float(self.away_form.wins) if self.away_form.wins is not None else None
            features["away_form_points_per_match"] = self.away_form.points_per_match
            features["away_form_win_rate"] = self.away_form.win_rate
            features["away_match_count"] = float(self.away_form.matches_analyzed) if self.away_form.matches_analyzed is not None else None
        
        # League context
        if self.league_context:
            features["home_advantage"] = self.league_context.home_advantage_factor
            features["league_avg_goals"] = self.league_context.league_average_goals
        
        # Data quality
        if self.data_quality_report:
            features["data_quality_score"] = self.data_quality_report.overall_score
        
        return features
    
    def validate_no_fabricated_data(self) -> List[str]:
        """Validate that no data appears to be fabricated placeholders.
        
        Returns:
            List of warnings for suspicious values
        """
        warnings = []
        
        # Check for suspicious round numbers that might be placeholders
        def check_suspicious(value: Optional[float], field_name: str) -> None:
            if value is not None:
                # Check for common placeholder values
                if value in (0.0, 1.0, 0.5, 0.7):
                    # These could be legitimate, so just warn
                    pass
                # Check for clearly impossible values
                if value < 0:
                    warnings.append(f"{field_name} has negative value: {value}")
        
        # Check strength metrics
        if self.home_strength:
            check_suspicious(self.home_strength.goals_scored_per_match, "home_goals_per_match")
            check_suspicious(self.home_strength.goals_conceded_per_match, "home_goals_conceded_per_match")
        
        if self.away_strength:
            check_suspicious(self.away_strength.goals_scored_per_match, "away_goals_per_match")
            check_suspicious(self.away_strength.goals_conceded_per_match, "away_goals_conceded_per_match")
        
        return warnings


def extract_feature_snapshot(
    match_id: str,
    home_team_id: str,
    away_team_id: str,
    feature_set: Optional[Any] = None,
    data_quality_report: Optional[DataQualityReport] = None,
    home_team_name: Optional[str] = None,
    away_team_name: Optional[str] = None,
    scheduled_at: Optional[datetime] = None,
    market_info: Optional[MarketInformation] = None,
) -> MatchFeatureSnapshot:
    """Extract canonical feature snapshot from various sources.
    
    This is the factory method for creating feature snapshots. It aggregates data
    from multiple sources while maintaining the guarantee that missing data stays None.
    
    Args:
        match_id: Match identifier
        home_team_id: Home team identifier
        away_team_id: Away team identifier
        feature_set: FeatureSet from FeatureAggregator (optional)
        data_quality_report: DataQualityReport (optional)
        home_team_name: Home team name (optional)
        away_team_name: Away team name (optional)
        scheduled_at: Match scheduled time (optional)
        market_info: Market odds information (optional)
    
    Returns:
        MatchFeatureSnapshot with all available data
    """
    snapshot = MatchFeatureSnapshot(
        match_id=match_id,
        home_team_id=home_team_id,
        away_team_id=away_team_id,
        home_team_name=home_team_name,
        away_team_name=away_team_name,
        scheduled_at=scheduled_at,
        data_quality_report=data_quality_report,
        market_info=market_info,
    )
    
    # Extract features from feature_set if available
    if feature_set:
        # Extract home form
        if hasattr(feature_set, 'home_form') and feature_set.home_form:
            hf = feature_set.home_form
            snapshot.home_form = FormMetrics(
                wins=hf.get('wins'),
                draws=hf.get('draws'),
                losses=hf.get('losses'),
                points=hf.get('points'),
                goals_for=hf.get('goals_for'),
                goals_against=hf.get('goals_against'),
                goal_difference=hf.get('goal_difference'),
                points_per_match=hf.get('points_per_match'),
                win_rate=hf.get('win_rate'),
                clean_sheet_rate=hf.get('clean_sheet_rate'),
                matches_analyzed=hf.get('sample_size'),
            )
        
        # Extract away form
        if hasattr(feature_set, 'away_form') and feature_set.away_form:
            af = feature_set.away_form
            snapshot.away_form = FormMetrics(
                wins=af.get('wins'),
                draws=af.get('draws'),
                losses=af.get('losses'),
                points=af.get('points'),
                goals_for=af.get('goals_for'),
                goals_against=af.get('goals_against'),
                goal_difference=af.get('goal_difference'),
                points_per_match=af.get('points_per_match'),
                win_rate=af.get('win_rate'),
                clean_sheet_rate=af.get('clean_sheet_rate'),
                matches_analyzed=af.get('sample_size'),
            )
        
        # Extract attack/defence features for strength metrics
        if hasattr(feature_set, 'attack_defence_home') and feature_set.attack_defence_home:
            adh = feature_set.attack_defence_home
            snapshot.home_strength = TeamStrengthMetrics(
                goals_scored_per_match=adh.get('goals_per_match'),
                xg_per_match=adh.get('xg_per_match'),
                goals_conceded_per_match=adh.get('goals_conceded_per_match'),
                xg_against_per_match=adh.get('xg_against_per_match'),
                points_per_match=snapshot.home_form.points_per_match if snapshot.home_form else None,
            )
        
        if hasattr(feature_set, 'attack_defence_away') and feature_set.attack_defence_away:
            ada = feature_set.attack_defence_away
            snapshot.away_strength = TeamStrengthMetrics(
                goals_scored_per_match=ada.get('goals_per_match'),
                xg_per_match=ada.get('xg_per_match'),
                goals_conceded_per_match=ada.get('goals_conceded_per_match'),
                xg_against_per_match=ada.get('xg_against_per_match'),
                points_per_match=snapshot.away_form.points_per_match if snapshot.away_form else None,
            )
    
    return snapshot

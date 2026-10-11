"""ELO rating features calculator.

Calculates ELO ratings for teams based on historical match results.
Ensures temporal validity - only uses matches before the prediction date.
"""

from datetime import datetime, timezone
from typing import Dict, List, Optional
from dataclasses import dataclass
import logging

from sqlalchemy.orm import Session
from app.database.models import Match, MatchStatus, MatchOutcome

logger = logging.getLogger(__name__)


@dataclass
class EloFeatures:
    """ELO rating features for both teams."""
    
    home_elo: Optional[float] = None
    away_elo: Optional[float] = None
    elo_difference: Optional[float] = None
    home_elo_form: Optional[float] = None  # ELO change in last 5 matches
    away_elo_form: Optional[float] = None


class EloFeatureCalculator:
    """Calculator for ELO rating features."""
    
    def __init__(
        self, 
        session: Session,
        k_factor: float = 32.0,
        initial_rating: float = 1500.0,
        home_advantage: float = 100.0,
        min_matches: int = 3
    ):
        """Initialize ELO feature calculator.
        
        Args:
            session: Database session
            k_factor: ELO rating sensitivity
            initial_rating: Starting rating for new teams
            home_advantage: Home advantage in ELO points
            min_matches: Minimum matches required for reliable ratings
        """
        self.session = session
        self.k_factor = k_factor
        self.initial_rating = initial_rating
        self.home_advantage = home_advantage
        self.min_matches = min_matches
        self._elo_system = None
        self._cached_until = None
    
    def calculate_for_match(
        self,
        home_team_id: str,
        away_team_id: str,
        match_date: datetime
    ) -> EloFeatures:
        """Calculate ELO features for a specific match.
        
        Args:
            home_team_id: Home team ID
            away_team_id: Away team ID  
            match_date: Match date (only uses data before this date)
            
        Returns:
            EloFeatures with calculated ratings
        """
        try:
            # Ensure match_date is timezone-aware (use UTC if naive)
            if match_date.tzinfo is None:
                match_date = match_date.replace(tzinfo=timezone.utc)
            
            # Ensure ELO system is up to date
            self._ensure_elo_system_current(match_date)
            
            if self._elo_system is None:
                logger.warning("[ELO] No ELO system available - insufficient historical data")
                return EloFeatures()
            
            # Get ratings at the match date (temporal safety)
            home_elo = self._elo_system.get_rating_at_time(home_team_id, match_date)
            away_elo = self._elo_system.get_rating_at_time(away_team_id, match_date)
            
            # Skip if either team has too few matches
            home_matches = self._count_team_matches_before(home_team_id, match_date)
            away_matches = self._count_team_matches_before(away_team_id, match_date)
            
            logger.info(
                f"[ELO] Match history: home_team={home_team_id[:8]}... ({home_matches} matches), "
                f"away_team={away_team_id[:8]}... ({away_matches} matches)"
            )
            
            if home_matches < self.min_matches or away_matches < self.min_matches:
                logger.info(
                    f"[ELO] Insufficient match history: home={home_matches}, "
                    f"away={away_matches}, min={self.min_matches} - ELO unavailable"
                )
                return EloFeatures()
            
            # Calculate additional features
            elo_difference = home_elo - away_elo
            home_elo_form = self._calculate_elo_form(home_team_id, match_date)
            away_elo_form = self._calculate_elo_form(away_team_id, match_date)
            
            logger.info(f"[ELO] Ratings calculated: home={home_elo:.1f}, away={away_elo:.1f}")
            
            return EloFeatures(
                home_elo=home_elo,
                away_elo=away_elo,
                elo_difference=elo_difference,
                home_elo_form=home_elo_form,
                away_elo_form=away_elo_form
            )
            
        except Exception as e:
            logger.error(f"[ELO] Error calculating features: {e}", exc_info=True)
            return EloFeatures()
    
    def _ensure_elo_system_current(self, until_date: datetime) -> None:
        """Ensure ELO system is processed up to the given date."""
        # Ensure until_date is timezone-aware
        if until_date.tzinfo is None:
            until_date = until_date.replace(tzinfo=timezone.utc)
        
        if self._elo_system is not None and self._cached_until and self._cached_until >= until_date:
            return
        
        logger.info(f"[ELO] Building ELO rating system from historical matches until {until_date}")
        
        # Create new ELO system
        # Import here to avoid circular imports
        from app.prediction.elo import EloRatingSystem
        
        # Create new ELO system
        self._elo_system = EloRatingSystem(
            k_factor=self.k_factor,
            initial_rating=self.initial_rating,
            home_advantage=self.home_advantage
        )
        
        # Get all finished matches before the date
        matches = self.session.query(Match).filter(
            Match.status == MatchStatus.FINISHED,
            Match.scheduled_at < until_date,
            Match.home_score.isnot(None),
            Match.away_score.isnot(None)
        ).order_by(Match.scheduled_at).all()
        
        logger.info(f"[ELO] Found {len(matches)} finished matches in database")
        
        if len(matches) < 10:
            logger.warning(f"[ELO] Very few historical matches found: {len(matches)} - ELO unavailable")
            self._elo_system = None
            return
        
        logger.info(f"[ELO] Processing {len(matches)} historical matches for ELO ratings")
        
        # Process matches chronologically
        match_data = []
        for match in matches:
            match_data.append({
                "match_id": match.id,
                "home_team_id": match.home_team_id,
                "away_team_id": match.away_team_id,
                "home_goals": match.home_score,
                "away_goals": match.away_score,
                "played_at": match.scheduled_at
            })
        
        try:
            self._elo_system.process_matches_chronologically(match_data)
            self._cached_until = until_date
            
            logger.info(
                f"[ELO] System built successfully: {len(match_data)} matches processed, "
                f"{len(self._elo_system._ratings)} teams rated"
            )
            
        except Exception as e:
            logger.error(f"[ELO] Failed to build system: {e}", exc_info=True)
            self._elo_system = None
    
    def _count_team_matches_before(self, team_id: str, before_date: datetime) -> int:
        """Count finished matches for a team before the given date."""
        # Ensure before_date is timezone-aware
        if before_date.tzinfo is None:
            before_date = before_date.replace(tzinfo=timezone.utc)
        
        return self.session.query(Match).filter(
            Match.status == MatchStatus.FINISHED,
            Match.scheduled_at < before_date,
            (Match.home_team_id == team_id) | (Match.away_team_id == team_id),
            Match.home_score.isnot(None),
            Match.away_score.isnot(None)
        ).count()
    
    def _calculate_elo_form(self, team_id: str, match_date: datetime, n_matches: int = 5) -> Optional[float]:
        """Calculate ELO form (rating change over last N matches)."""
        if self._elo_system is None:
            return None
        
        # Ensure match_date is timezone-aware
        if match_date.tzinfo is None:
            match_date = match_date.replace(tzinfo=timezone.utc)
        
        # Get last N matches for this team before the match date
        matches = self.session.query(Match).filter(
            Match.status == MatchStatus.FINISHED,
            Match.scheduled_at < match_date,
            (Match.home_team_id == team_id) | (Match.away_team_id == team_id),
            Match.home_score.isnot(None),
            Match.away_score.isnot(None)
        ).order_by(Match.scheduled_at.desc()).limit(n_matches).all()
        
        if len(matches) < 2:
            return None
        
        # Get rating after first and last match in the period
        first_match = matches[-1]  # Oldest match (last in desc order)
        last_match = matches[0]    # Most recent match
        
        try:
            # Rating before first match (approximate)
            rating_start = self._elo_system.get_rating_at_time(team_id, first_match.scheduled_at)
            # Rating after last match
            rating_end = self._elo_system.get_rating_at_time(team_id, last_match.scheduled_at)
            
            return rating_end - rating_start
            
        except Exception:
            return None
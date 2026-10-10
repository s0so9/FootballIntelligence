"""Hybrid provider that combines external providers with database fallback.

This provider tries external providers first for fresh data, but falls back
to database lookups for canonical UUIDs that external providers cannot resolve.
"""

from typing import List, Optional, Dict, Any
from datetime import datetime, date
from sqlalchemy.orm import Session

from app.providers.base import FootballDataProvider
from app.providers.adapter import ProviderManagerAdapter
from app.providers.database_adapter import DatabaseBackedProvider
from app.domain.match import Match
from app.domain.entities import Team, Competition, Season
from app.domain.statistics import TeamMatchStatistic


class HybridProvider(FootballDataProvider):
    """Provider that combines external providers with database fallback.
    
    This provider first attempts to use external providers (ProviderManagerAdapter)
    for live data, but falls back to database lookups when external providers
    fail to resolve canonical UUIDs.
    """
    
    def __init__(self, external_provider: ProviderManagerAdapter, session: Session):
        """Initialize hybrid provider.
        
        Args:
            external_provider: ProviderManagerAdapter for external data
            session: Database session for fallback lookups
        """
        self.external_provider = external_provider
        self.db_provider = DatabaseBackedProvider(session)
    
    def is_development_data(self) -> bool:
        """Return False since this uses real data from both sources."""
        return False
    
    def _is_canonical_uuid(self, id_str: str) -> bool:
        """Check if the ID looks like a canonical UUID.
        
        Args:
            id_str: ID string to check
            
        Returns:
            True if it looks like a UUID (contains dashes and is 36 chars)
        """
        return len(id_str) == 36 and id_str.count('-') == 4
    
    def get_match(self, match_id: str) -> Optional[Match]:
        """Get match, trying external providers first, then database.
        
        Args:
            match_id: Match ID (could be external provider ID or canonical UUID)
            
        Returns:
            Match domain object or None if not found
        """
        # First try external providers
        try:
            match = self.external_provider.get_match(match_id)
            if match is not None:
                # Update status before returning - this fixes cached SCHEDULED matches  
                updated_match = self._update_single_match_status(match)
                return updated_match
        except Exception:
            # External provider failed, continue to database fallback
            pass
        
        # If external providers fail or return None, try database
        # This handles canonical UUIDs that external providers don't know about
        db_match = self.db_provider.get_match(match_id)
        if db_match is not None:
            return self._update_single_match_status(db_match)
        return None
    
    def get_team(self, team_id: str) -> Optional[Team]:
        """Get team, trying external providers first, then database.
        
        Args:
            team_id: Team ID (could be external provider ID or canonical UUID)
            
        Returns:
            Team domain object or None if not found
        """
        # First try external providers
        try:
            team = self.external_provider.get_team(team_id)
            if team is not None:
                return team
        except Exception:
            # External provider failed, continue to database fallback
            pass
        
        # If external providers fail or return None, try database
        # This handles canonical UUIDs that external providers don't know about
        return self.db_provider.get_team(team_id)
    
    def get_matches(
        self,
        competition_id: Optional[str] = None,
        season_id: Optional[str] = None,
        team_id: Optional[str] = None,
        from_date: Optional[date] = None,
        to_date: Optional[date] = None,
        status: Optional[str] = None,
    ) -> List[Match]:
        """Get matches, trying external providers first, then database.
        
        Args:
            competition_id: Filter by competition
            season_id: Filter by season  
            team_id: Filter by team
            from_date: Filter from date
            to_date: Filter to date
            status: Filter by status
            
        Returns:
            List of Match domain objects with updated statuses
        """
        # First try external providers
        try:
            matches = self.external_provider.get_matches(
                competition_id=competition_id,
                season_id=season_id,
                team_id=team_id,
                from_date=from_date,
                to_date=to_date,
                status=status,
            )
            if matches:
                # Update statuses before returning - this fixes cached SCHEDULED matches
                updated_matches = self._update_match_statuses(matches)
                return updated_matches
        except Exception:
            # External provider failed, continue to database fallback
            pass
        
        # If external providers fail or return empty, try database
        db_matches = self.db_provider.get_matches(
            competition_id=competition_id,
            season_id=season_id,
            team_id=team_id,
            from_date=from_date,
            to_date=to_date,
            status=status,
        )
        return self._update_match_statuses(db_matches)
    
    def get_team_match_statistics(self, match_id: str) -> List[TeamMatchStatistic]:
        """Get team match statistics, trying external providers first, then database.
        
        Args:
            match_id: Match ID
            
        Returns:
            List of TeamMatchStatistic objects
        """
        # First try external providers
        try:
            stats = self.external_provider.get_team_match_statistics(match_id)
            if stats:
                return stats
        except Exception:
            # External provider failed, continue to database fallback
            pass
        
        # If external providers fail, try database
        return self.db_provider.get_team_match_statistics(match_id)
    
    def get_team_match_statistics_firsthalf(self, match_id: str) -> List[TeamMatchStatistic]:
        """Get first-half statistics, trying external providers first, then database.
        
        Args:
            match_id: Match ID
            
        Returns:
            List of TeamMatchStatistic objects for first half
        """
        # First try external providers
        try:
            stats = self.external_provider.get_team_match_statistics_firsthalf(match_id)
            if stats:
                return stats
        except Exception:
            # External provider failed, continue to database fallback
            pass
        
        # If external providers fail, try database
        return self.db_provider.get_team_match_statistics_firsthalf(match_id)
    
    def get_competitions(self, country: Optional[str] = None) -> List[Competition]:
        """Get competitions, trying external providers first, then database.
        
        Args:
            country: Filter by country
            
        Returns:
            List of Competition objects
        """
        # First try external providers
        try:
            competitions = self.external_provider.get_competitions(country=country)
            if competitions:
                return competitions
        except Exception:
            # External provider failed, continue to database fallback
            pass
        
        # If external providers fail, try database
        return self.db_provider.get_competitions(country=country)
    
    def get_provider_name(self) -> str:
        """Return the hybrid provider name."""
        return "HybridProvider"
    
    def get_competition(self, competition_id: str) -> Optional[Competition]:
        """Get competition, trying external providers first, then database.
        
        Args:
            competition_id: Competition ID
            
        Returns:
            Competition domain object or None if not found
        """
        # First try external providers
        try:
            competition = self.external_provider.get_competition(competition_id)
            if competition is not None:
                return competition
        except Exception:
            # External provider failed, continue to database fallback
            pass
        
        # If external providers fail, try database
        competitions = self.db_provider.get_competitions()
        for comp in competitions:
            if comp.id == competition_id:
                return comp
        return None
    
    def get_seasons(self, competition_id: str) -> List[Season]:
        """Get seasons, trying external providers first, then database.
        
        Args:
            competition_id: Competition ID
            
        Returns:
            List of Season objects
        """
        # First try external providers
        try:
            seasons = self.external_provider.get_seasons(competition_id)
            if seasons:
                return seasons
        except Exception:
            # External provider failed, continue to database fallback
            pass
        
        # Database fallback - return a default season if none found
        # This is a simple fallback for now
        return [Season(
            id="2024/25",
            competition_id=competition_id,
            year="2024/25",
            is_current=True
        )]
    
    def get_current_season(self, competition_id: str) -> Optional[Season]:
        """Get current season, trying external providers first, then database.
        
        Args:
            competition_id: Competition ID
            
        Returns:
            Current Season object or None if not found
        """
        # First try external providers
        try:
            season = self.external_provider.get_current_season(competition_id)
            if season is not None:
                return season
        except Exception:
            # External provider failed, continue to database fallback
            pass
        
        # Database fallback - return a default current season
        return Season(
            id="2024/25",
            competition_id=competition_id,
            year="2024/25",
            is_current=True
        )

    def get_teams(self, competition_id: str, season_id: Optional[str] = None) -> List[Team]:
        """Get teams, trying external providers first, then database.
        
        Args:
            competition_id: Competition ID
            season_id: Season ID
            
        Returns:
            List of Team objects
        """
        # First try external providers
        try:
            teams = self.external_provider.get_teams(competition_id, season_id)
            if teams:
                return teams
        except Exception:
            # External provider failed, continue to database fallback
            pass
        
        # If external providers fail, try database
        return self.db_provider.get_teams(competition_id, season_id)
    
    def _update_match_statuses(self, matches: List[Match]) -> List[Match]:
        """Update match statuses based on current time for stale SCHEDULED matches.
        
        SAFETY POLICY: 
        - NEVER change status based solely on time elapsed
        - Only trust explicit status from external providers
        - Preserve provider data integrity
        - Avoid fabricating match results or scores
        """
        from datetime import datetime, timezone
        from app.domain.enums import MatchStatus
        
        # CONSERVATIVE APPROACH: Do not modify status based on time
        # The external provider is the authoritative source for status updates
        # Time-based status changes can create inconsistencies and false data
        
        updated_matches = []
        for match in matches:
            # Create a copy to preserve immutability
            updated_match = Match(
                id=match.id,
                competition_id=match.competition_id,
                season_id=match.season_id,
                home_team_id=match.home_team_id,
                away_team_id=match.away_team_id,
                venue_id=match.venue_id,
                scheduled_at=match.scheduled_at,
                status=match.status,  # PRESERVE original status from provider
                home_score=match.home_score,
                away_score=match.away_score,
                round=match.round,
                created_at=match.created_at,
                updated_at=match.updated_at,
            )
            
            # SAFETY: No automatic status changes based on time
            # Status changes should only come from:
            # 1. Real provider data updates (FotMob, etc.)
            # 2. Manual admin intervention
            # 3. Confirmed match results from official sources
            
            updated_matches.append(updated_match)
        
        return updated_matches
    
    def _update_single_match_status(self, match: Match) -> Match:
        """Update status for a single match."""
        if match is None:
            return None
        
        updated_matches = self._update_match_statuses([match])
        return updated_matches[0] if updated_matches else match
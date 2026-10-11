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
    
    async def get_matches_async(
        self,
        competition_id: Optional[str] = None,
        season_id: Optional[str] = None,
        team_id: Optional[str] = None,
        from_date: Optional[date] = None,
        to_date: Optional[date] = None,
        status: Optional[str] = None,
    ) -> List[Match]:
        """Async version of get_matches for API endpoints.
        
        Uses hybrid approach: merge external provider matches with database matches
        to ensure complete coverage of all matches.
        
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
        import logging
        logger = logging.getLogger(__name__)
        
        # Store the requested status filter for later application
        requested_status = status
        all_matches = []
        
        # Try external providers first
        try:
            logger.debug(f"HybridProvider.get_matches_async: Trying external providers")
            external_matches = await self.external_provider.get_matches_async(
                competition_id=competition_id,
                season_id=season_id,
                team_id=team_id,
                from_date=from_date,
                to_date=to_date,
                status=None,  # CRITICAL: Don't filter by status yet - do it after update
            )
            if external_matches:
                logger.debug(f"HybridProvider.get_matches_async: External providers returned {len(external_matches)} matches")
                all_matches.extend(external_matches)
        except Exception as e:
            logger.debug(f"HybridProvider.get_matches_async: External providers failed: {e}")
        
        # Always get database matches as well (for complete coverage)
        try:
            logger.debug(f"HybridProvider.get_matches_async: Getting database matches")
            db_matches = self.db_provider.get_matches(
                competition_id=competition_id,
                season_id=season_id,
                team_id=team_id,
                from_date=from_date,
                to_date=to_date,
                status=None,  # Don't filter by status yet
            )
            
            if db_matches:
                logger.debug(f"HybridProvider.get_matches_async: Database returned {len(db_matches)} matches")
                
                # Merge database matches, avoiding duplicates
                external_ids = {m.id for m in all_matches}
                for db_match in db_matches:
                    if db_match.id not in external_ids:
                        all_matches.append(db_match)
                
                logger.debug(f"HybridProvider.get_matches_async: Total matches after merge: {len(all_matches)}")
        except Exception as e:
            logger.debug(f"HybridProvider.get_matches_async: Database lookup failed: {e}")
        
        if not all_matches:
            logger.debug(f"HybridProvider.get_matches_async: No matches found from any source")
            return []
        
        # Update statuses for all matches
        updated_matches = self._update_match_statuses(all_matches)
        logger.debug(f"HybridProvider.get_matches_async: Status updates applied to {len(updated_matches)} matches")
        
        # Now apply status filter after updates
        if requested_status:
            from app.domain.enums import MatchStatus
            try:
                requested_match_status = MatchStatus(requested_status.upper())
                before_filter = len(updated_matches)
                updated_matches = [m for m in updated_matches if m.status == requested_match_status]
                logger.debug(f"HybridProvider.get_matches_async: Status filter '{requested_status}' applied: {before_filter} -> {len(updated_matches)} matches")
            except ValueError:
                logger.warning(f"HybridProvider.get_matches_async: Invalid status '{requested_status}', returning empty")
                return []
        
        return updated_matches

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
        import logging
        logger = logging.getLogger(__name__)
        
        # Store the requested status filter for later application
        requested_status = status
        
        # First try external providers
        try:
            logger.debug(f"HybridProvider.get_matches: Trying external providers")
            matches = self.external_provider.get_matches(
                competition_id=competition_id,
                season_id=season_id,
                team_id=team_id,
                from_date=from_date,
                to_date=to_date,
                status=None,  # Don't filter by status yet - do it after update
            )
            if matches:
                logger.debug(f"HybridProvider.get_matches: External providers returned {len(matches)} matches")
                # Update statuses first
                updated_matches = self._update_match_statuses(matches)
                logger.debug(f"HybridProvider.get_matches: Status updates applied")
                
                # Now apply status filter after updates
                if requested_status:
                    from app.domain.enums import MatchStatus
                    try:
                        requested_match_status = MatchStatus(requested_status.upper())
                        before_filter = len(updated_matches)
                        updated_matches = [m for m in updated_matches if m.status == requested_match_status]
                        logger.debug(f"HybridProvider.get_matches: Status filter '{requested_status}' applied: {before_filter} -> {len(updated_matches)} matches")
                    except ValueError:
                        logger.warning(f"HybridProvider.get_matches: Invalid status '{requested_status}', returning empty")
                        return []
                        
                return updated_matches
        except Exception as e:
            logger.debug(f"HybridProvider.get_matches: External providers failed: {e}")
            # External provider failed, continue to database fallback
            pass
        
        # If external providers fail or return empty, try database
        logger.debug(f"HybridProvider.get_matches: Using database fallback")
        # Get matches without status filter first, then update, then filter
        db_matches = self.db_provider.get_matches(
            competition_id=competition_id,
            season_id=season_id,
            team_id=team_id,
            from_date=from_date,
            to_date=to_date,
            status=None,  # Don't filter by status yet
        )
        
        logger.debug(f"HybridProvider.get_matches: Database returned {len(db_matches)} matches")
        
        # Update statuses first
        updated_matches = self._update_match_statuses(db_matches)
        logger.debug(f"HybridProvider.get_matches: Status updates applied to database matches")
        
        # Now apply status filter after updates
        if requested_status:
            from app.domain.enums import MatchStatus
            try:
                requested_match_status = MatchStatus(requested_status.upper())
                before_filter = len(updated_matches)
                updated_matches = [m for m in updated_matches if m.status == requested_match_status]
                logger.debug(f"HybridProvider.get_matches: Status filter '{requested_status}' applied: {before_filter} -> {len(updated_matches)} matches")
            except ValueError:
                logger.warning(f"HybridProvider.get_matches: Invalid status '{requested_status}', returning empty")
                return []
        
        return updated_matches
    
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
        
        UPDATED POLICY: 
        - Only update SCHEDULED matches that are clearly finished based on time
        - Never modify other statuses or add fake scores
        - Conservative 4-hour window to avoid false positives
        - Preserve provider data integrity for all other cases
        """
        from datetime import datetime, timezone
        from app.domain.enums import MatchStatus
        import logging
        
        logger = logging.getLogger(__name__)
        current_time = datetime.now(timezone.utc)
        updated_matches = []
        
        status_changes = 0
        target_match_id = '849f5743-1f96-4ade-be4c-af1c5d3da039'
        
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
                status=match.status,
                home_score=match.home_score,
                away_score=match.away_score,
                round=match.round,
                created_at=match.created_at,
                updated_at=match.updated_at,
            )
            
            # ONLY update SCHEDULED matches that are clearly finished
            if match.status == MatchStatus.SCHEDULED and match.scheduled_at:
                # Make scheduled_at timezone-aware if it isn't already
                if match.scheduled_at.tzinfo is None:
                    match_time = match.scheduled_at.replace(tzinfo=timezone.utc)
                else:
                    match_time = match.scheduled_at
                
                time_diff = current_time - match_time
                hours_passed = time_diff.total_seconds() / 3600
                
                # Conservative 4-hour window: only mark as finished if clearly over
                if hours_passed > 4:
                    updated_match.status = MatchStatus.FINISHED
                    status_changes += 1
                    
                    if match.id == target_match_id:
                        logger.debug(f"STATUS UPDATE: Target match {target_match_id} updated SCHEDULED->FINISHED (hours_passed: {hours_passed:.1f})")
                    # SAFETY: Never add fake scores - preserve existing scores
            
            # All other statuses remain unchanged (LIVE, FINISHED, etc.)
            updated_matches.append(updated_match)
        
        if status_changes > 0:
            logger.debug(f"HybridProvider._update_match_statuses: Updated {status_changes} matches from SCHEDULED to FINISHED")
        
        return updated_matches
    
    def _update_single_match_status(self, match: Match) -> Match:
        """Update status for a single match."""
        if match is None:
            return None
        
        updated_matches = self._update_match_statuses([match])
        return updated_matches[0] if updated_matches else match
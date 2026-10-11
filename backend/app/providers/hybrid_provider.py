"""Hybrid provider that combines external providers with database fallback.

This provider tries external providers first for fresh data, but falls back
to database lookups for canonical UUIDs that external providers cannot resolve.

Implements smart data freshness policy based on match status and timestamps.
"""

from typing import List, Optional, Dict, Any
from datetime import datetime, date, timedelta
from sqlalchemy.orm import Session

from app.providers.base import FootballDataProvider
from app.providers.adapter import ProviderManagerAdapter
from app.providers.database_adapter import DatabaseBackedProvider
from app.domain.match import Match
from app.domain.entities import Team, Competition, Season
from app.domain.statistics import TeamMatchStatistic
from app.domain.enums import MatchStatus
from app.config import settings


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
    
    def _should_refresh_from_external(self, db_matches: List[Match], status_filter: Optional[str] = None) -> bool:
        """Determine if database matches need refreshing from external providers.
        
        Implements timestamp-based freshness policy:
        - LIVE: Always refresh (handled by status-aware policy, not called here)
        - SCHEDULED: Refresh if stale OR approaching kickoff
        - FINISHED: Refresh if recently finished and stale OR very old
        - No filter: Always refresh (handled by status-aware policy, not called here)
        
        Args:
            db_matches: List of matches from database
            status_filter: Status filter applied to query
            
        Returns:
            True if external provider should be called for fresh data
        """
        if not db_matches:
            # No data in database, need external refresh
            return True
        
        now = datetime.now(tz=db_matches[0].scheduled_at.tzinfo if db_matches[0].scheduled_at.tzinfo else None)
        
        for match in db_matches:
            # If any match lacks provider_fetched_at timestamp, refresh all
            if match.provider_fetched_at is None:
                return True
            
            # Calculate data age
            data_age = now - match.provider_fetched_at
            
            if status_filter and status_filter.upper() == "SCHEDULED":
                # SCHEDULED matches: Check for stale data or approaching kickoff
                scheduled_minutes = settings.data_freshness_scheduled_minutes
                approaching_minutes = settings.data_freshness_approaching_kickoff_minutes
                
                # Refresh if data is too old
                if data_age > timedelta(minutes=scheduled_minutes):
                    return True
                
                # Refresh if kickoff is approaching and data isn't very fresh
                time_until_kickoff = match.scheduled_at - now
                if time_until_kickoff < timedelta(minutes=approaching_minutes):
                    # For approaching matches, require fresher data (15 minutes)
                    if data_age > timedelta(minutes=15):
                        return True
            
            elif status_filter and status_filter.upper() == "FINISHED":
                # FINISHED matches: Check if recently finished or very old
                finished_recent_minutes = settings.data_freshness_finished_recent_minutes
                finished_minutes = settings.data_freshness_finished_minutes
                
                # Check if match finished recently (within last 3 hours)
                time_since_match = now - match.scheduled_at
                if time_since_match < timedelta(minutes=finished_recent_minutes):
                    # Recently finished: need fresh data for score confirmation (30 minutes freshness)
                    if data_age > timedelta(minutes=30):
                        return True
                
                # For older finished matches, allow longer staleness
                if data_age > timedelta(minutes=finished_minutes):
                    return True
        
        # All matches are fresh enough
        return False
    
    def get_match(self, match_id: str) -> Optional[Match]:
        """Get match, trying external providers first, then database.

        Returns None (never raises) if no source can resolve the match ID.

        Args:
            match_id: Match ID (could be external provider ID or canonical UUID)

        Returns:
            Match domain object or None if not found
        """
        import logging
        logger = logging.getLogger(__name__)

        # First try external providers
        try:
            match = self.external_provider.get_match(match_id)
            if match is not None:
                # Update status before returning - this fixes cached SCHEDULED matches
                updated_match = self._update_single_match_status(match)
                return updated_match
        except Exception as exc:
            logger.debug(f"HybridProvider.get_match: external provider failed for {match_id}: {exc}")

        # If external providers fail or return None, try database.
        # This handles canonical UUIDs that external providers don't know about.
        try:
            db_match = self.db_provider.get_match(match_id)
            if db_match is not None:
                return self._update_single_match_status(db_match)
            return None
        except Exception as exc:
            logger.warning(f"HybridProvider.get_match: DB fallback failed for {match_id}: {exc} – returning None")
            return None
    
    def get_team(self, team_id: str) -> Optional[Team]:
        """Get team, trying external providers first, then database.

        Returns None (never raises) if no source can resolve the team ID.
        On Vercel's ephemeral SQLite environment the 'teams' table may not
        exist; that OperationalError is caught here so callers receive None
        instead of an unhandled 500.

        Args:
            team_id: Team ID (could be external provider ID or canonical UUID)

        Returns:
            Team domain object or None if not found
        """
        import logging
        logger = logging.getLogger(__name__)

        # 1. Try external providers
        try:
            team = self.external_provider.get_team(team_id)
            if team is not None:
                return team
        except Exception as exc:
            logger.debug(
                f"HybridProvider.get_team: external provider failed for "
                f"team_id={team_id}: {exc}"
            )

        # 2. Try database (may fail if teams table does not exist)
        try:
            return self.db_provider.get_team(team_id)
        except Exception as exc:
            logger.warning(
                f"HybridProvider.get_team: database fallback failed for "
                f"team_id={team_id}: {exc} – returning None"
            )
            return None
    
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
        
        PERFORMANCE OPTIMIZATION: Passes status filter to providers when safe to do so,
        reducing data transfer and processing overhead.
        
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
        
        # PERFORMANCE: Determine if we can safely pass status filter to providers
        # We can pass status filter directly when:
        # 1. Status is provided
        # 2. We don't need status updates (statuses are trusted from provider/DB)
        # OR we're only querying database (which has canonical statuses)
        
        # For now, we need to update statuses after fetch, so we DON'T pass status
        # to external providers (they may have stale data). But we CAN pass it to database.
        
        requested_status = status
        provider_status_filter = None  # Don't filter at provider level yet
        db_status_filter = status  # Database has canonical statuses, filter there
        
        all_matches = []
        
        # DATA FRESHNESS POLICY:
        # - Database-first for all status queries (canonical data is authoritative)
        # - External only for no-status queries (fresh data across all statuses)
        # - Trust database status filtering over external provider status
        
        should_check_external_first = (
            not status  # No status filter = user expects fresh data across all statuses
        )
        
        if should_check_external_first:
            # No status filter: Check external providers first for freshness
            try:
                logger.debug(f"HybridProvider.get_matches_async: Checking external providers first (no status filter)")
                external_matches = await self.external_provider.get_matches_async(
                    competition_id=competition_id,
                    season_id=season_id,
                    team_id=team_id,
                    from_date=from_date,
                    to_date=to_date,
                    status=provider_status_filter,
                )
                if external_matches:
                    logger.debug(f"HybridProvider.get_matches_async: External providers returned {len(external_matches)} matches")
                    all_matches.extend(external_matches)
            except Exception as e:
                logger.debug(f"HybridProvider.get_matches_async: External providers failed: {e}")
            
            # Also get database matches for merge
            try:
                logger.debug(f"HybridProvider.get_matches_async: Getting database matches (status={db_status_filter})")
                db_matches = self.db_provider.get_matches(
                    competition_id=competition_id,
                    season_id=season_id,
                    team_id=team_id,
                    from_date=from_date,
                    to_date=to_date,
                    status=db_status_filter,
                )
                
                if db_matches:
                    logger.debug(f"HybridProvider.get_matches_async: Database returned {len(db_matches)} matches")
                    # Merge database matches, avoiding duplicates (external data takes precedence)
                    external_ids = {m.id for m in all_matches}
                    for db_match in db_matches:
                        if db_match.id not in external_ids:
                            all_matches.append(db_match)
                    logger.debug(f"HybridProvider.get_matches_async: Total matches after merge: {len(all_matches)}")
            except Exception as e:
                logger.debug(f"HybridProvider.get_matches_async: Database lookup failed: {e}")
        
        else:
            # ALL STATUS queries: Database-first with controlled fallback
            # Database is authoritative for status filtering (SCHEDULED, LIVE, FINISHED, CANCELLED)
            db_matches = []
            try:
                logger.debug(f"HybridProvider.get_matches_async: Checking database first (status={db_status_filter})")
                db_matches = self.db_provider.get_matches(
                    competition_id=competition_id,
                    season_id=season_id,
                    team_id=team_id,
                    from_date=from_date,
                    to_date=to_date,
                    status=db_status_filter,
                )
                
                if db_matches:
                    logger.debug(f"HybridProvider.get_matches_async: Database returned {len(db_matches)} matches")
                    
                    # DATABASE-FIRST OPTIMIZATION:
                    # For status queries (SCHEDULED/LIVE/FINISHED/CANCELLED), database is authoritative.
                    # Database has canonical UUIDs and team relationships.
                    logger.debug(f"HybridProvider.get_matches_async: Using database matches (canonical data)")
                    all_matches.extend(db_matches)
            except Exception as e:
                logger.debug(f"HybridProvider.get_matches_async: Database lookup failed: {e}")
            
            # CONTROLLED FALLBACK: Only try external providers if database returned nothing
            # This handles cases where database is not yet populated (e.g., fresh deployment)
            if not all_matches:
                try:
                    logger.debug(f"HybridProvider.get_matches_async: Database empty for status={status}, trying external providers as fallback")
                    external_matches = await self.external_provider.get_matches_async(
                        competition_id=competition_id,
                        season_id=season_id,
                        team_id=team_id,
                        from_date=from_date,
                        to_date=to_date,
                        status=provider_status_filter,
                    )
                    if external_matches:
                        logger.debug(f"HybridProvider.get_matches_async: External providers returned {len(external_matches)} matches")
                        
                        # Apply status filter to external matches since provider_status_filter is None
                        if status:
                            from app.domain.enums import MatchStatus
                            try:
                                filter_status = MatchStatus(status.upper())
                                external_matches = [m for m in external_matches if m.status == filter_status]
                                logger.debug(f"HybridProvider.get_matches_async: After status filter: {len(external_matches)} matches")
                            except ValueError:
                                logger.warning(f"HybridProvider.get_matches_async: Invalid status value: {status}")
                                external_matches = []
                        
                        all_matches.extend(external_matches)
                except Exception as e:
                    logger.debug(f"HybridProvider.get_matches_async: External providers fallback failed: {e}")
            
            if not all_matches:
                logger.debug(f"HybridProvider.get_matches_async: No matches found from any source for status={status}")
        
        if not all_matches:
            logger.debug(f"HybridProvider.get_matches_async: No matches found from any source")
            return []
        
        # DATABASE-FIRST: No status updates needed (database is canonical)
        # Database query already filtered by correct status, results are authoritative
        logger.debug(f"HybridProvider.get_matches_async: Returning {len(all_matches)} matches (database-first)")
        
        # No post-update status filtering - database already filtered by status before update
        # This preserves matches that were corrected from SCHEDULED to FINISHED
        
        return all_matches

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
        
        PERFORMANCE OPTIMIZATION: Passes status filter to database queries when possible,
        reducing data transfer and processing overhead.
        
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
        
        requested_status = status
        provider_status_filter = None  # External providers may have stale statuses
        db_status_filter = status  # Database has canonical statuses
        
        all_matches = []
        
        # DATA FRESHNESS POLICY:
        # - For LIVE matches: Always check external providers (real-time data critical)
        # - For SCHEDULED/FINISHED: Database-first is safe (stale data acceptable)
        # - For no status filter: Check external providers (user expects fresh data)
        
        should_check_external_first = (
            not status or  # No status filter = user expects fresh data
            status.upper() == "LIVE"  # Live matches need real-time updates
        )
        
        if should_check_external_first:
            # LIVE or unfiltered queries: Check external providers first for freshness
            try:
                logger.debug(f"HybridProvider.get_matches: Checking external providers first (status={status})")
                external_matches = self.external_provider.get_matches(
                    competition_id=competition_id,
                    season_id=season_id,
                    team_id=team_id,
                    from_date=from_date,
                    to_date=to_date,
                    status=provider_status_filter,
                )
                if external_matches:
                    logger.debug(f"HybridProvider.get_matches: External providers returned {len(external_matches)} matches")
                    all_matches.extend(external_matches)
            except Exception as e:
                logger.debug(f"HybridProvider.get_matches: External providers failed: {e}")
            
            # Also get database matches for merge
            try:
                logger.debug(f"HybridProvider.get_matches: Getting database matches (status={db_status_filter})")
                db_matches = self.db_provider.get_matches(
                    competition_id=competition_id,
                    season_id=season_id,
                    team_id=team_id,
                    from_date=from_date,
                    to_date=to_date,
                    status=db_status_filter,
                )
                
                if db_matches:
                    logger.debug(f"HybridProvider.get_matches: Database returned {len(db_matches)} matches")
                    # Merge database matches, avoiding duplicates (external data takes precedence)
                    external_ids = {m.id for m in all_matches}
                    for db_match in db_matches:
                        if db_match.id not in external_ids:
                            all_matches.append(db_match)
                    logger.debug(f"HybridProvider.get_matches: Total matches after merge: {len(all_matches)}")
            except Exception as e:
                logger.debug(f"HybridProvider.get_matches: Database lookup failed: {e}")
        
        else:
            # SCHEDULED/FINISHED queries: Database-first optimization is safe
            db_matches = []
            try:
                logger.debug(f"HybridProvider.get_matches: Checking database first (status={db_status_filter})")
                db_matches = self.db_provider.get_matches(
                    competition_id=competition_id,
                    season_id=season_id,
                    team_id=team_id,
                    from_date=from_date,
                    to_date=to_date,
                    status=db_status_filter,
                )
                
                if db_matches:
                    logger.debug(f"HybridProvider.get_matches: Database returned {len(db_matches)} matches")
                    
                    # TIMESTAMP-BASED FRESHNESS CHECK
                    should_refresh = self._should_refresh_from_external(db_matches, status)
                    
                    if should_refresh:
                        logger.debug(f"HybridProvider.get_matches: Database data is stale, refreshing from external providers")
                        # Fetch fresh data from external providers
                        try:
                            external_matches = self.external_provider.get_matches(
                                competition_id=competition_id,
                                season_id=season_id,
                                team_id=team_id,
                                from_date=from_date,
                                to_date=to_date,
                                status=provider_status_filter,
                            )
                            if external_matches:
                                logger.debug(f"HybridProvider.get_matches: External providers returned {len(external_matches)} matches (refreshed)")
                                # Merge: external data takes precedence
                                external_ids = {m.id for m in external_matches}
                                for db_match in db_matches:
                                    if db_match.id not in external_ids:
                                        external_matches.append(db_match)
                                all_matches.extend(external_matches)
                            else:
                                # External failed, use stale DB data as fallback
                                logger.debug(f"HybridProvider.get_matches: External refresh failed, using stale database data")
                                all_matches.extend(db_matches)
                        except Exception as e:
                            # External failed, use stale DB data as fallback
                            logger.debug(f"HybridProvider.get_matches: External refresh failed ({e}), using stale database data")
                            all_matches.extend(db_matches)
                    else:
                        # Data is fresh enough, use database
                        logger.debug(f"HybridProvider.get_matches: Database data is fresh, using cached data")
                        all_matches.extend(db_matches)
            except Exception as e:
                logger.debug(f"HybridProvider.get_matches: Database lookup failed: {e}")
            
            # Only try external providers if database returned nothing
            if not all_matches:
                try:
                    logger.debug(f"HybridProvider.get_matches: Database empty, trying external providers")
                    matches = self.external_provider.get_matches(
                        competition_id=competition_id,
                        season_id=season_id,
                        team_id=team_id,
                        from_date=from_date,
                        to_date=to_date,
                        status=provider_status_filter,
                    )
                    if matches:
                        logger.debug(f"HybridProvider.get_matches: External providers returned {len(matches)} matches")
                        all_matches.extend(matches)
                except Exception as e:
                    logger.debug(f"HybridProvider.get_matches: External providers failed: {e}")
        
        if not all_matches:
            return []
        
        # DATABASE-FIRST: No status updates needed (database is canonical)
        # Database query already filtered by correct status, results are authoritative
        logger.debug(f"HybridProvider.get_matches: Returning {len(all_matches)} matches (database-first)")
        
        # No post-update status filtering - database already filtered by status before update
        # This preserves matches that were corrected from SCHEDULED to FINISHED
        
        return all_matches
    
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

        If both external providers and the database return nothing (e.g. the DB
        competitions table does not exist in the Vercel SQLite ephemeral
        environment), returns an empty list and logs the root cause so that
        callers can use ``get_competitions_from_matches_async`` instead.

        Args:
            country: Filter by country

        Returns:
            List of Competition objects (may be empty if no source has data)
        """
        import logging
        logger = logging.getLogger(__name__)

        # 1. Try external providers (ProviderManagerAdapter raises NotImplementedError)
        try:
            competitions = self.external_provider.get_competitions()
            if competitions:
                logger.debug(
                    f"HybridProvider.get_competitions: external provider returned "
                    f"{len(competitions)} competitions"
                )
                return competitions
        except NotImplementedError:
            logger.info(
                "HybridProvider.get_competitions: external provider not implemented "
                "(ProviderManagerAdapter.get_competitions raises NotImplementedError) "
                "- falling back to database"
            )
        except Exception as exc:
            logger.warning(
                f"HybridProvider.get_competitions: external provider failed: {exc} "
                "- falling back to database"
            )

        # 2. Try database (may fail if competitions table does not exist)
        try:
            db_competitions = self.db_provider.get_competitions(country=country)
            if db_competitions:
                logger.debug(
                    f"HybridProvider.get_competitions: database returned "
                    f"{len(db_competitions)} competitions"
                )
                return db_competitions
            logger.info(
                "HybridProvider.get_competitions: database returned 0 competitions "
                "(table exists but is empty) - caller should use "
                "get_competitions_from_matches_async"
            )
        except Exception as exc:
            logger.warning(
                f"HybridProvider.get_competitions: database fallback failed: {exc} "
                "(competitions table likely missing) - caller should use "
                "get_competitions_from_matches_async"
            )

        return []

    async def get_competitions_from_matches_async(
        self,
        country: Optional[str] = None,
    ) -> List[Competition]:
        """Derive available competitions from the current match schedule.

        This is the primary source of competition data when neither the external
        provider nor the database can supply a competition list.  It fetches
        upcoming matches for a 30-day window from today via the external provider
        (FotMob) and extracts the unique (competition_id, competition_name) pairs
        that are already present in the live match feed.

        The IDs returned here are the same provider-numeric IDs that appear in
        ``/api/v1/matches``, so the frontend can use them to filter matches by
        competition without any UUID translation.

        Args:
            country: Unused – retained for signature compatibility.

        Returns:
            Deduplicated list of Competition objects derived from live matches.
            Returns an empty list (never raises) if the external provider fails.
        """
        import logging
        from datetime import date, timedelta
        logger = logging.getLogger(__name__)

        today = date.today()
        to_date = today + timedelta(days=30)

        provider_matches = []
        try:
            provider_matches = await self.external_provider.get_matches_async(
                from_date=today,
                to_date=to_date,
            )
            logger.debug(
                f"HybridProvider.get_competitions_from_matches_async: "
                f"fetched {len(provider_matches)} matches from external provider"
            )
        except Exception as exc:
            logger.warning(
                f"HybridProvider.get_competitions_from_matches_async: "
                f"external provider failed: {exc}"
            )

        # Extract unique competitions from match objects.
        # Matches produced by ProviderManagerAdapter carry competition_id
        # (fotmob numeric string) and _provider_competition_name (display name).
        seen: set = set()
        competitions: List[Competition] = []
        for match in provider_matches:
            comp_id = getattr(match, "competition_id", None)
            comp_name = getattr(match, "_provider_competition_name", None)
            if not comp_id or not comp_name:
                continue
            if comp_id in seen:
                continue
            seen.add(comp_id)
            competitions.append(
                Competition(
                    id=comp_id,
                    name=comp_name,
                    country=None,
                )
            )

        logger.info(
            f"HybridProvider.get_competitions_from_matches_async: "
            f"derived {len(competitions)} unique competitions from match schedule"
        )
        return competitions
    
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
        
        CONSERVATIVE POLICY: 
        - Only update SCHEDULED matches that are clearly finished (>= 3 hours past kickoff)
        - Never modify LIVE, FINISHED, CANCELLED statuses from providers
        - Never add fake scores
        - Preserve provider data integrity
        
        This handles edge case where database has old SCHEDULED status but match has finished.
        External providers should provide authoritative real-time status.
        """
        from datetime import datetime, timezone
        from app.domain.enums import MatchStatus
        import logging
        
        logger = logging.getLogger(__name__)
        current_time = datetime.now(timezone.utc)
        updated_matches = []
        
        status_changes = 0
        
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
                provider_fetched_at=match.provider_fetched_at,
            )
            
            # ONLY update SCHEDULED matches that are clearly finished
            # Use 3-hour threshold: typical match is 90 min + 15 min HT + buffer
            if match.status == MatchStatus.SCHEDULED and match.scheduled_at:
                # Make scheduled_at timezone-aware if it isn't already
                if match.scheduled_at.tzinfo is None:
                    match_time = match.scheduled_at.replace(tzinfo=timezone.utc)
                else:
                    match_time = match.scheduled_at
                
                time_diff = current_time - match_time
                hours_passed = time_diff.total_seconds() / 3600
                
                # Conservative 3-hour window: only mark as finished if clearly over
                # This prevents false positives for delayed kickoffs
                if hours_passed >= 3:
                    updated_match.status = MatchStatus.FINISHED
                    status_changes += 1
                    logger.debug(f"Auto-updated match {match.id[:8]} SCHEDULED->FINISHED (hours_passed: {hours_passed:.1f})")
            
            # All other statuses remain unchanged (LIVE, FINISHED, CANCELLED, etc.)
            updated_matches.append(updated_match)
        
        if status_changes > 0:
            logger.info(f"HybridProvider._update_match_statuses: Updated {status_changes} matches from SCHEDULED to FINISHED")
        
        return updated_matches
    
    def _update_single_match_status(self, match: Match) -> Match:
        """Update status for a single match."""
        if match is None:
            return None
        
        updated_matches = self._update_match_statuses([match])
        return updated_matches[0] if updated_matches else match
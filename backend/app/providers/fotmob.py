"""# Unofficial FotMob Integration

⚠️ This is NOT an official FotMob API integration.

This provider uses publicly accessible FotMob JSON endpoints for live/fast data.
Request volume must be conservative. No bypasses, no anti-bot evasion, no scraping tricks.
If a request fails, return structured provider failure — never invent data.

FotMob is the LIVE/FAST provider for real-time match data where it provides fresher
information than Ryzellx. This is an unofficial integration using conservative request
patterns only.

Conservative request patterns:
- retry_count=1 max (no aggressive retry loops)
- No CAPTCHA bypasses
- No authentication bypasses
- No anti-bot evasion
- No scraping tricks
- If request fails, raise ProviderError (never invent data)
"""

import logging
from datetime import datetime, date, timezone
from typing import List, Optional, Dict, Any, Tuple
import httpx

from app.providers.exceptions import (
    ProviderError,
    ProviderTimeoutError,
    ProviderHTTPError,
    ProviderInvalidDataError,
    ProviderNotFoundError,
)
from app.providers.cache import (
    ProviderCache,
    LIVE_DATA_TTL,
    UPCOMING_FIXTURES_TTL,
    HISTORICAL_MATCH_TTL,
)
from app.providers.models import (
    ProviderMatch,
    ProviderCompetition,
    ProviderTeam,
    ProviderPlayer,
    ProviderStanding,
    ProviderLiveMatch,
    ProviderMatchStats,
)
from app.domain.enums import MatchStatus, MatchOutcome


logger = logging.getLogger(__name__)


class FotMobFootballProvider:
    """FotMob Football Provider (LIVE/FAST provider, unofficial).
    
    This provider is designed for LIVE/FAST data where FotMob provides fresher
    information than other providers. It is NOT an official FotMob API integration.
    
    PRIMARY USE CASES:
    - Live match data (scores, minute, events)
    - Daily match schedules with fresh data
    - Match details with real-time updates
    
    STUB/NOT IMPLEMENTED:
    - League metadata (use Ryzellx instead)
    - Team details (use Ryzellx instead)
    - Player details (use Ryzellx instead)
    - Standings (use Ryzellx or OpenLigaDB instead)
    
    Conservative request patterns only:
    - retry_count=1 max (no aggressive retry loops)
    - No bypasses, no anti-bot evasion, no scraping tricks
    - If request fails, raise ProviderError (never invent data)
    
    Args:
        base_url: Base URL for FotMob endpoints (configurable)
        timeout_seconds: HTTP request timeout in seconds
        retry_count: Max retries for transient failures (default: 1, conservative)
        cache: Optional ProviderCache for caching responses
    """
    
    PROVIDER_NAME = "fotmob"
    
    def __init__(
        self,
        base_url: str,
        timeout_seconds: float = 10.0,
        retry_count: int = 1,  # Conservative: only 1 retry
        cache: Optional[ProviderCache] = None
    ):
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.retry_count = retry_count
        self.cache = cache
        
        # Create async HTTP client with timeout
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=httpx.Timeout(timeout_seconds),
            follow_redirects=True,
        )
        
        logger.info(
            f"Initialized {self.PROVIDER_NAME} provider (UNOFFICIAL): "
            f"base_url={self.base_url}, timeout={timeout_seconds}s, "
            f"retry_count={retry_count}, cache={'enabled' if cache else 'disabled'}"
        )
    
    async def close(self):
        """Close the HTTP client."""
        await self._client.aclose()
    
    async def _request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Make HTTP request with error handling and conservative retry logic.
        
        Conservative retry policy:
        - retry_count=1 max (no aggressive retry loops)
        - Only retry on connection errors and 5xx server errors
        - No bypasses, no anti-bot evasion
        
        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint path (e.g., '/api/matches')
            params: Optional query parameters
            
        Returns:
            Parsed JSON response as dict
            
        Raises:
            ProviderTimeoutError: Request timed out
            ProviderHTTPError: HTTP error response (4xx, 5xx after retries)
            ProviderNotFoundError: Resource not found (404)
            ProviderInvalidDataError: Invalid JSON response
            ProviderError: Connection or other request errors
        """
        operation = f"{method} {endpoint}"
        attempt = 0
        last_error = None
        
        while attempt <= self.retry_count:
            try:
                if attempt > 0:
                    logger.debug(
                        f"[{self.PROVIDER_NAME}] Retry {attempt}/{self.retry_count} "
                        f"for {operation}"
                    )
                
                logger.debug(
                    f"[{self.PROVIDER_NAME}] {operation} "
                    f"params={params if params else 'none'}"
                )
                
                response = await self._client.request(
                    method=method,
                    url=endpoint,
                    params=params
                )
                
                # Check HTTP status
                if response.status_code == 404:
                    raise ProviderNotFoundError(
                        provider_name=self.PROVIDER_NAME,
                        operation=operation,
                        message=f"Resource not found: {endpoint}"
                    )
                
                if 400 <= response.status_code < 500:
                    raise ProviderHTTPError(
                        provider_name=self.PROVIDER_NAME,
                        operation=operation,
                        message=f"Client error: {response.status_code} {response.reason_phrase}",
                        status_code=response.status_code
                    )
                
                if 500 <= response.status_code < 600:
                    # Server error - retry once (conservative)
                    last_error = ProviderHTTPError(
                        provider_name=self.PROVIDER_NAME,
                        operation=operation,
                        message=f"Server error: {response.status_code} {response.reason_phrase}",
                        status_code=response.status_code
                    )
                    attempt += 1
                    if attempt <= self.retry_count:
                        await self._wait_before_retry(attempt)
                        continue
                    raise last_error
                
                # Success - parse JSON
                try:
                    data = response.json()
                    logger.debug(
                        f"[{self.PROVIDER_NAME}] {operation} succeeded: "
                        f"{response.status_code}"
                    )
                    return data
                    
                except Exception as e:
                    raise ProviderInvalidDataError(
                        provider_name=self.PROVIDER_NAME,
                        operation=operation,
                        message=f"Failed to parse JSON response: {str(e)}",
                        original_error=e
                    )
            
            except httpx.TimeoutException as e:
                raise ProviderTimeoutError(
                    provider_name=self.PROVIDER_NAME,
                    operation=operation,
                    message=f"Request timed out after {self.timeout_seconds}s",
                    original_error=e
                )
            
            except httpx.RequestError as e:
                # Connection error - retry once (conservative)
                last_error = ProviderError(
                    provider_name=self.PROVIDER_NAME,
                    operation=operation,
                    message=f"Connection error: {type(e).__name__}",
                    original_error=e
                )
                attempt += 1
                if attempt <= self.retry_count:
                    logger.warning(
                        f"[{self.PROVIDER_NAME}] {operation} connection error, "
                        f"retrying ({attempt}/{self.retry_count})"
                    )
                    await self._wait_before_retry(attempt)
                    continue
                raise last_error
            
            except (ProviderTimeoutError, ProviderHTTPError, ProviderNotFoundError, 
                    ProviderInvalidDataError, ProviderError):
                # Re-raise provider exceptions as-is
                raise
            
            except Exception as e:
                # Unexpected error
                raise ProviderError(
                    provider_name=self.PROVIDER_NAME,
                    operation=operation,
                    message=f"Unexpected error: {type(e).__name__}",
                    original_error=e
                )
        
        # Should not reach here, but raise last error if we do
        if last_error:
            raise last_error
        raise ProviderError(
            provider_name=self.PROVIDER_NAME,
            operation=operation,
            message="Max retries exceeded"
        )
    
    async def _wait_before_retry(self, attempt: int):
        """Wait before retry with exponential backoff."""
        import asyncio
        wait_seconds = min(2 ** attempt, 10)  # Max 10 seconds
        await asyncio.sleep(wait_seconds)
    
    def _parse_match_status(self, status_str: Optional[str]) -> MatchStatus:
        """Parse FotMob match status to domain MatchStatus.
        
        Args:
            status_str: Status string from FotMob API
            
        Returns:
            Normalized MatchStatus
        """
        if not status_str:
            return MatchStatus.SCHEDULED
        
        status_lower = status_str.lower()
        
        # FotMob typically uses status strings like:
        # "live", "finished", "not_started", "halftime", "postponed", "fulltime_short", etc.
        if status_lower in ["live", "in_play", "playing"]:
            return MatchStatus.LIVE
        elif status_lower in ["ht", "half_time", "halftime", "halftime_short"]:
            return MatchStatus.HALF_TIME
        elif status_lower in ["ft", "finished", "full_time", "fulltime", "fulltime_short"]:
            return MatchStatus.FINISHED
        elif status_lower in ["postponed", "pst", "postponed_short"]:
            return MatchStatus.POSTPONED
        elif status_lower in ["cancelled", "canceled", "cnc", "cancelled_short"]:
            return MatchStatus.CANCELLED
        elif status_lower in ["suspended", "susp", "suspended_short"]:
            return MatchStatus.SUSPENDED
        elif status_lower in ["scheduled", "not_started", "ns", "not started", "notstarted_short"]:
            return MatchStatus.SCHEDULED
        else:
            logger.warning(
                f"[{self.PROVIDER_NAME}] Unknown status '{status_str}', "
                f"defaulting to SCHEDULED"
            )
            return MatchStatus.SCHEDULED
    
    def _parse_match_outcome(
        self,
        home_score: Optional[int],
        away_score: Optional[int]
    ) -> Optional[MatchOutcome]:
        """Parse match outcome from scores.
        
        Args:
            home_score: Home team score
            away_score: Away team score
            
        Returns:
            MatchOutcome if match is finished, None otherwise
        """
        if home_score is None or away_score is None:
            return None
        
        if home_score > away_score:
            return MatchOutcome.HOME_WIN
        elif away_score > home_score:
            return MatchOutcome.AWAY_WIN
        else:
            return MatchOutcome.DRAW
    
    def _normalize_match(self, data: Dict[str, Any], is_live: bool = False, league_context: Optional[Dict[str, Any]] = None) -> ProviderMatch:
        """Normalize FotMob match data to ProviderMatch.
        
        Args:
            data: Raw match data from FotMob API
            is_live: Whether this is live match data
            league_context: Optional league data when parsing from leagues list
            
        Returns:
            Normalized ProviderMatch
        """
        now = datetime.now(timezone.utc)
        
        # Parse scheduled time
        # Priority 1: general.matchTimeUTCDate (matchDetails primary field)
        # Priority 2-N: existing fallbacks preserved
        scheduled_at = now
        general_data = data.get("general") or {}

        # Try general.matchTimeUTCDate first
        if isinstance(general_data, dict) and "matchTimeUTCDate" in general_data:
            try:
                scheduled_at = datetime.fromisoformat(general_data["matchTimeUTCDate"].replace("Z", "+00:00"))
            except:
                pass

        # Existing fallback logic preserved
        if scheduled_at == now:
            status_data = data.get("status") or {}
            # Try status.utcTime first (existing logic)
            if isinstance(status_data, dict) and "utcTime" in status_data:
                try:
                    scheduled_at = datetime.fromisoformat(status_data["utcTime"].replace("Z", "+00:00"))
                except:
                    pass

            # Fallback to other time fields (existing logic preserved)
            if scheduled_at == now:
                scheduled_str = (
                    data.get("startTime") or
                    data.get("time") or
                    data.get("kickoff") or
                    data.get("date")
                )
                if scheduled_str:
                    try:
                        # Try parsing as ISO format
                        scheduled_at = datetime.fromisoformat(scheduled_str.replace("Z", "+00:00"))
                    except:
                        try:
                            # Try parsing as timestamp (milliseconds)
                            timestamp_ms = int(scheduled_str) if isinstance(scheduled_str, (int, str)) else scheduled_str
                            scheduled_at = datetime.fromtimestamp(timestamp_ms / 1000, tz=timezone.utc)
                        except:
                            pass
        
        status_data = data.get("status") or {}

        # Parse status from status.reason or status object
        if isinstance(status_data, dict):
            # Check for nested reason
            if "reason" in status_data and isinstance(status_data["reason"], dict):
                status_str = status_data["reason"].get("shortKey") or status_data["reason"].get("short")
            else:
                status_str = status_data.get("type") or status_data.get("reason")

            # Map FotMob status flags to status string
            if not status_str:
                if status_data.get("finished"):
                    status_str = "finished"
                elif status_data.get("started"):
                    status_str = "live"
                elif status_data.get("cancelled"):
                    status_str = "cancelled"
                else:
                    status_str = "not_started"
        else:
            status_str = str(status_data)

        status = self._parse_match_status(status_str)

        # Parse teams - FotMob matchDetails structure
        # Priority 1: general.homeTeam / general.awayTeam
        # Priority 2: header.teams[0] / header.teams[1]
        home_team = None
        away_team = None
        home_team_id = None
        away_team_id = None
        home_team_name = ""
        away_team_name = ""

        # Try general.homeTeam / awayTeam first (matchDetails primary structure)
        general_data = data.get("general") or {}
        if isinstance(general_data, dict):
            home_team = general_data.get("homeTeam")
            away_team = general_data.get("awayTeam")

        # Fallback to header.teams if general not available (match list structure)
        if not home_team or not away_team:
            header_data = data.get("header") or {}
            if isinstance(header_data, dict):
                teams = header_data.get("teams", [])
                if isinstance(teams, list) and len(teams) >= 2:
                    home_team = teams[0]
                    away_team = teams[1]

        # Fallback to old structure for backward compatibility with other endpoints
        if not home_team:
            home_team = data.get("home") or data.get("homeTeam") or {}
        if not away_team:
            away_team = data.get("away") or data.get("awayTeam") or {}

        # Extract team IDs and names
        if isinstance(home_team, dict):
            home_team_id = home_team.get("id")
            if home_team_id is not None:
                home_team_id = str(home_team_id)
            home_team_name = home_team.get("longName") or home_team.get("name", "")
        else:
            home_team_name = str(home_team) if home_team else ""

        if isinstance(away_team, dict):
            away_team_id = away_team.get("id")
            if away_team_id is not None:
                away_team_id = str(away_team_id)
            away_team_name = away_team.get("longName") or away_team.get("name", "")
        else:
            away_team_name = str(away_team) if away_team else ""

        # DATA INTEGRITY CHECK: If no valid team IDs, raise ProviderInvalidDataError
        # Do NOT fabricate team IDs - fail safely
        if not home_team_id or not away_team_id:
            match_id_for_error = (
                data.get("id") or 
                data.get("matchId") or 
                (general_data.get("matchId") if isinstance(general_data, dict) else None) or 
                "unknown"
            )
            raise ProviderInvalidDataError(
                provider_name=self.PROVIDER_NAME,
                operation="normalize_match",
                message=f"Missing required team IDs in match data (match_id: {match_id_for_error})"
            )

        # Parse scores
        # Priority 1: header.teams[0].score / header.teams[1].score
        # Priority 2: team object scores (for backward compatibility)
        # Priority 3: existing fallbacks
        home_score = None
        away_score = None

        # Try header.teams scores first (most reliable for matchDetails)
        header_data = data.get("header") or {}
        if isinstance(header_data, dict):
            teams = header_data.get("teams", [])
            if isinstance(teams, list) and len(teams) >= 2:
                home_score = teams[0].get("score")
                away_score = teams[1].get("score")

        # Fallback: check team objects (for backward compatibility)
        if home_score is None and isinstance(home_team, dict):
            home_score = home_team.get("score")
        if away_score is None and isinstance(away_team, dict):
            away_score = away_team.get("score")

        # Fallback: check for separate score object (existing logic preserved)
        if home_score is None and "score" in data:
            home_score = data["score"].get("home")
            away_score = data["score"].get("away")
        elif home_score is None:
            home_score = data.get("homeScore") or data.get("home_score")
            away_score = data.get("awayScore") or data.get("away_score")

        # Parse competition - use league context if provided, otherwise from match data
        if league_context:
            competition_id = str(league_context.get("primaryId")) if league_context.get("primaryId") else str(league_context.get("id")) if league_context.get("id") else None
            competition_name = league_context.get("name")
        else:
            # Try general.leagueId / leagueName first (matchDetails structure)
            general_data = data.get("general") or {}
            if isinstance(general_data, dict) and general_data.get("leagueId"):
                competition_id = str(general_data["leagueId"])
                competition_name = general_data.get("leagueName")
            else:
                # Fallback to existing logic
                league_data = data.get("league") or data.get("competition") or {}
                if isinstance(league_data, dict):
                    competition_id = str(league_data.get("id")) if league_data.get("id") else None
                    competition_name = league_data.get("name")
                else:
                    # Final fallback: top-level leagueId
                    league_id = data.get("leagueId")
                    competition_id = str(league_id) if league_id else None
                    competition_name = str(league_data) if league_data else None
        
        # Parse minute
        minute = None
        if "minute" in data:
            minute = data.get("minute")
        elif isinstance(status_data, dict) and "minute" in status_data:
            minute = status_data.get("minute")
        
        # Parse outcome
        outcome = None
        if status == MatchStatus.FINISHED:
            outcome = self._parse_match_outcome(home_score, away_score)
        
        return ProviderMatch(
            # Source metadata
            provider=self.PROVIDER_NAME,
            source_id=str(
                data.get("id") or 
                data.get("matchId") or 
                (general_data.get("matchId") if isinstance(general_data, dict) else None) or 
                ""
            ),
            fetched_at=now,
            source_updated_at=None,  # FotMob doesn't typically provide this
            is_live=is_live or status == MatchStatus.LIVE,
            data_freshness_seconds=None,
            
            # Match identifiers
            competition_id=competition_id,
            competition_name=competition_name,
            season=None,  # FotMob doesn't always provide season in match data
            
            # Teams
            home_team_id=home_team_id,
            home_team_name=home_team_name,
            away_team_id=away_team_id,
            away_team_name=away_team_name,
            
            # Venue
            venue_name=data.get("venue") or data.get("stadium"),
            
            # Timing
            scheduled_at=scheduled_at,
            status=status,
            minute=minute,
            added_time=data.get("addedTime") or data.get("added_time"),
            
            # Scores
            home_score=home_score,
            away_score=away_score,
            home_score_ht=None,  # Would need to parse from detailed match data
            away_score_ht=None,
            
            # Outcome
            outcome=outcome,
            
            # Match round
            # Priority 1: general.matchRound
            # Priority 2: existing fallbacks
            round=(
                (lambda: (
                    int(general_data.get("matchRound"))
                    if isinstance(general_data, dict) and "matchRound" in general_data and general_data.get("matchRound") is not None
                    else None
                ))() or data.get("round") or data.get("matchday")
            ),
        )
    
    def _extract_match_statistics(
        self,
        data: Dict[str, Any],
        match_id: str,
        home_team_id: str,
        away_team_id: str
    ) -> Tuple[Optional[ProviderMatchStats], Optional[ProviderMatchStats]]:
        """Extract match statistics from FotMob matchDetails response.
        
        Args:
            data: Raw matchDetails data from FotMob
            match_id: Match ID
            home_team_id: Home team ID
            away_team_id: Away team ID
            
        Returns:
            Tuple of (home_stats, away_stats), either may be None if unavailable
        """
        from app.providers.models import ProviderMatchStats
        
        now = datetime.now(timezone.utc)
        
        # Extract stats from content.stats.Periods.All
        content = data.get("content", {})
        if not content:
            return (None, None)
        
        stats_data = content.get("stats", {})
        if not stats_data:
            return (None, None)
        
        periods = stats_data.get("Periods", {})
        all_period = periods.get("All", {})
        stat_groups = all_period.get("stats", [])
        
        if not stat_groups:
            return (None, None)
        
        # Extract home/away values from nested structure
        home_values = {}
        away_values = {}
        
        for group in stat_groups:
            group_stats = group.get("stats", [])
            
            for stat in group_stats:
                key = stat.get("key")
                if not key:
                    continue
                
                raw_stats = stat.get("rawStats", [])
                if len(raw_stats) >= 2 and raw_stats[0] and raw_stats[1]:
                    home_value = raw_stats[0].get("value")
                    away_value = raw_stats[1].get("value")
                    
                    home_values[key] = home_value
                    away_values[key] = away_value
        
        if not home_values and not away_values:
            return (None, None)
        
        # Map FotMob keys to our ProviderMatchStats fields
        def create_stats(values: Dict, team_id: str) -> ProviderMatchStats:
            return ProviderMatchStats(
                provider=self.PROVIDER_NAME,
                source_id=f"{match_id}_{team_id}",
                fetched_at=now,
                match_id=match_id,
                team_id=team_id,
                period="full",
                # Goals - not in stats, need from match data
                goals_scored=None,
                goals_conceded=None,
                # Expected goals
                xg=float(values.get("expected_goals")) if values.get("expected_goals") is not None else None,
                xg_against=None,  # Would need opponent's xg
                # Shots
                shots_total=int(values.get("total_shots")) if values.get("total_shots") is not None else None,
                shots_on_target=int(values.get("ShotsOnTarget")) if values.get("ShotsOnTarget") is not None else None,
                shots_off_target=int(values.get("ShotsOffTarget")) if values.get("ShotsOffTarget") is not None else None,
                shots_blocked=int(values.get("blocked_shots")) if values.get("blocked_shots") is not None else None,
                # Possession
                possession_percentage=float(values.get("BallPossesion")) if values.get("BallPossesion") is not None else None,
                # Passing
                passes_completed=int(values.get("accurate_passes")) if values.get("accurate_passes") is not None else None,
                passes_attempted=int(values.get("passes")) if values.get("passes") is not None else None,
                pass_accuracy=None,  # Could calculate from above
                # Set pieces
                corners=int(values.get("corners")) if values.get("corners") is not None else None,
                free_kicks=None,  # Not directly available
                offsides=int(values.get("Offsides")) if values.get("Offsides") is not None else None,
                # Discipline
                yellow_cards=int(values.get("yellow_cards")) if values.get("yellow_cards") is not None else None,
                red_cards=int(values.get("red_cards")) if values.get("red_cards") is not None else None,
                fouls_committed=int(values.get("fouls")) if values.get("fouls") is not None else None,
                # Defensive
                tackles=int(values.get("matchstats.headers.tackles")) if values.get("matchstats.headers.tackles") is not None else None,
                interceptions=int(values.get("interceptions")) if values.get("interceptions") is not None else None,
                clearances=int(values.get("clearances")) if values.get("clearances") is not None else None,
                saves=int(values.get("keeper_saves")) if values.get("keeper_saves") is not None else None,
            )
        
        home_stats = create_stats(home_values, home_team_id) if home_values else None
        away_stats = create_stats(away_values, away_team_id) if away_values else None
        
        return (home_stats, away_stats)
    
    async def get_match_statistics(
        self,
        match_id: str,
        period: str = 'full'
    ) -> Tuple[Optional[ProviderMatchStats], Optional[ProviderMatchStats]]:
        """Get match statistics from FotMob matchDetails.
        
        Args:
            match_id: FotMob match ID
            period: Period to fetch ('full' only supported by FotMob)
            
        Returns:
            Tuple of (home_stats, away_stats), both None if not found
            
        Raises:
            ProviderError: On request failure (except 404)
        """
        from app.providers.models import ProviderMatchStats
        
        # Check cache
        cache_key = f"{self.PROVIDER_NAME}:stats:{match_id}:{period}"
        if self.cache:
            cached = self.cache.get(cache_key)
            if cached is not None:
                logger.debug(f"[{self.PROVIDER_NAME}] Cache hit: {cache_key}")
                return cached
        
        # Fetch match details (includes statistics)
        try:
            endpoint = "/api/data/matchDetails"
            params = {"matchId": match_id}
            data = await self._request("GET", endpoint, params=params)
            
            # Extract team IDs from match data first
            general_data = data.get("general", {})
            home_team_data = general_data.get("homeTeam", {})
            away_team_data = general_data.get("awayTeam", {})
            
            home_team_id = str(home_team_data.get("id", ""))
            away_team_id = str(away_team_data.get("id", ""))
            
            if not home_team_id or not away_team_id:
                # Fallback to header.teams
                header_data = data.get("header", {})
                teams = header_data.get("teams", [])
                if len(teams) >= 2:
                    home_team_id = str(teams[0].get("id", ""))
                    away_team_id = str(teams[1].get("id", ""))
            
            if not home_team_id or not away_team_id:
                logger.warning(f"[{self.PROVIDER_NAME}] Could not extract team IDs for match {match_id}")
                return (None, None)
            
            # Extract statistics
            home_stats, away_stats = self._extract_match_statistics(
                data, match_id, home_team_id, away_team_id
            )
            
            # Cache result
            if self.cache:
                ttl = HISTORICAL_MATCH_TTL  # Statistics are static after match
                self.cache.set(cache_key, (home_stats, away_stats), ttl_seconds=ttl)
            
            logger.info(f"[{self.PROVIDER_NAME}] Fetched statistics for match {match_id}")
            return (home_stats, away_stats)
            
        except ProviderNotFoundError:
            logger.info(f"[{self.PROVIDER_NAME}] Statistics for match {match_id} not found")
            return (None, None)
        except ProviderError:
            raise
    
    async def get_matches_by_date(self, date_obj: date) -> List[ProviderMatch]:
        """Get matches for a specific date.
        
        FotMob typically provides daily matches through endpoints like:
        /api/matches?date=YYYYMMDD
        
        Args:
            date_obj: Date to fetch matches for
            
        Returns:
            List of ProviderMatch for the date
            
        Raises:
            ProviderError: On request failure
        """
        # Check cache
        cache_key = f"{self.PROVIDER_NAME}:matches:date:{date_obj.isoformat()}"
        if self.cache:
            cached = self.cache.get(cache_key)
            if cached is not None:
                logger.debug(f"[{self.PROVIDER_NAME}] Cache hit: {cache_key}")
                return cached
        
        # Fetch from API - FotMob uses YYYYMMDD format
        date_str = date_obj.strftime("%Y%m%d")
        endpoint = "/api/data/matches"
        params = {"date": date_str}
        
        try:
            data = await self._request("GET", endpoint, params=params)
        except ProviderError:
            # If request fails, raise error (never invent data)
            raise
        
        # Parse response - FotMob structure may vary
        matches = []
        
        # FotMob typically nests matches in leagues
        if isinstance(data, dict):
            # Check for matches in various possible structures
            if "leagues" in data:
                for league in data["leagues"]:
                    league_matches = league.get("matches", [])
                    for match_data in league_matches:
                        try:
                            # Pass league context for better normalization
                            match = self._normalize_match(match_data, is_live=False, league_context=league)
                            matches.append(match)
                        except Exception as e:
                            logger.warning(
                                f"[{self.PROVIDER_NAME}] Failed to normalize match: {e}"
                            )
            elif "matches" in data:
                for match_data in data["matches"]:
                    try:
                        match = self._normalize_match(match_data, is_live=False)
                        matches.append(match)
                    except Exception as e:
                        logger.warning(
                            f"[{self.PROVIDER_NAME}] Failed to normalize match: {e}"
                        )
        elif isinstance(data, list):
            for match_data in data:
                try:
                    match = self._normalize_match(match_data, is_live=False)
                    matches.append(match)
                except Exception as e:
                    logger.warning(
                        f"[{self.PROVIDER_NAME}] Failed to normalize match: {e}"
                    )
        
        # Cache result with appropriate TTL
        if self.cache:
            today = date.today()
            if date_obj == today:
                ttl = LIVE_DATA_TTL
            else:
                ttl = UPCOMING_FIXTURES_TTL
            self.cache.set(cache_key, matches, ttl_seconds=ttl)
        
        logger.info(
            f"[{self.PROVIDER_NAME}] Fetched {len(matches)} matches for {date_obj}"
        )
        return matches
    
    async def get_matches_by_range(
        self,
        start_date: date,
        end_date: date
    ) -> List[ProviderMatch]:
        """Get matches in date range.

        FotMob doesn't have a native range endpoint, so we iterate through dates.

        Args:
            start_date: Start date (inclusive)
            end_date: End date (inclusive)

        Returns:
            List of ProviderMatch in the range

        Raises:
            ProviderError: On request failure
        """
        from datetime import timedelta

        # Check cache
        cache_key = (
            f"{self.PROVIDER_NAME}:matches:range:"
            f"{start_date.isoformat()}:{end_date.isoformat()}"
        )
        if self.cache:
            cached = self.cache.get(cache_key)
            if cached is not None:
                logger.debug(f"[{self.PROVIDER_NAME}] Cache hit: {cache_key}")
                return cached

        # Iterate through dates and collect matches
        all_matches = []
        current_date = start_date

        while current_date <= end_date:
            try:
                daily_matches = await self.get_matches_by_date(current_date)
                all_matches.extend(daily_matches)
            except ProviderError as e:
                logger.warning(
                    f"[{self.PROVIDER_NAME}] Failed to fetch matches for {current_date}: {e}"
                )
                # Continue with other dates even if one fails

            current_date += timedelta(days=1)

        # Cache result with TTL based on date range
        if self.cache:
            today = date.today()
            if end_date < today:
                # Historical data - longer TTL
                ttl = HISTORICAL_MATCH_TTL
            elif start_date > today:
                # Future data - medium TTL
                ttl = UPCOMING_FIXTURES_TTL
            else:
                # Range includes today - short TTL
                ttl = LIVE_DATA_TTL
            self.cache.set(cache_key, all_matches, ttl_seconds=ttl)

        logger.info(
            f"[{self.PROVIDER_NAME}] Fetched {len(all_matches)} matches for range {start_date} to {end_date}"
        )
        return all_matches

    async def get_match(self, match_id: str) -> Optional[ProviderMatch]:
        """Get detailed match information.

        FotMob typically provides match details through:
        /api/matchDetails?matchId={match_id}
        
        Args:
            match_id: Match ID
            
        Returns:
            ProviderMatch if found, None if not found
            
        Raises:
            ProviderError: On request failure (except 404)
        """
        # Check cache
        cache_key = f"{self.PROVIDER_NAME}:match:{match_id}"
        if self.cache:
            cached = self.cache.get(cache_key)
            if cached is not None:
                logger.debug(f"[{self.PROVIDER_NAME}] Cache hit: {cache_key}")
                return cached
        
        # Fetch from API
        try:
            endpoint = "/api/data/matchDetails"
            params = {"matchId": match_id}
            data = await self._request("GET", endpoint, params=params)
            
            # Normalize match
            is_live = False
            if "status" in data:
                status_data = data["status"]
                if isinstance(status_data, dict):
                    status_str = status_data.get("type", "")
                else:
                    status_str = str(status_data)
                is_live = "live" in status_str.lower()
            
            match = self._normalize_match(data, is_live=is_live)
            
            # Cache result
            if self.cache:
                ttl = LIVE_DATA_TTL if is_live else UPCOMING_FIXTURES_TTL
                self.cache.set(cache_key, match, ttl_seconds=ttl)
            
            logger.info(f"[{self.PROVIDER_NAME}] Fetched match {match_id}")
            return match
            
        except ProviderNotFoundError:
            logger.info(f"[{self.PROVIDER_NAME}] Match {match_id} not found")
            return None
        except ProviderError:
            # If request fails, raise error (never invent data)
            raise
    
    async def get_live_matches(self) -> List[ProviderLiveMatch]:
        """Get currently live matches.
        
        FotMob provides live matches through endpoints like:
        /api/matches/live or similar
        
        Returns:
            List of ProviderLiveMatch
            
        Raises:
            ProviderError: On request failure
        """
        # Check cache
        cache_key = f"{self.PROVIDER_NAME}:matches:live"
        if self.cache:
            cached = self.cache.get(cache_key)
            if cached is not None:
                logger.debug(f"[{self.PROVIDER_NAME}] Cache hit: {cache_key}")
                return cached
        
        # Fetch from API - FotMob doesn't have a dedicated live endpoint
        # Get today's matches and filter for live ones
        try:
            today = date.today()
            date_str = today.strftime("%Y%m%d")
            endpoint = "/api/data/matches"
            params = {"date": date_str}
            data = await self._request("GET", endpoint, params=params)
        except ProviderError:
            # If request fails, raise error (never invent data)
            raise
        
        # Parse response
        now = datetime.now(timezone.utc)
        live_matches = []
        
        # Extract matches from various possible structures
        match_list = []
        if isinstance(data, dict):
            if "leagues" in data:
                for league in data["leagues"]:
                    match_list.extend(league.get("matches", []))
            elif "matches" in data:
                match_list = data["matches"]
        elif isinstance(data, list):
            match_list = data
        
        # Filter and normalize live matches only
        for match_data in match_list:
            try:
                # Check if match is live
                status_data = match_data.get("status", {})
                if isinstance(status_data, dict):
                    status_str = status_data.get("type", "")
                else:
                    status_str = str(status_data)
                
                status = self._parse_match_status(status_str)
                
                # Only include live matches
                if status not in [MatchStatus.LIVE, MatchStatus.HALF_TIME]:
                    continue
                
                # Parse scores
                home_score = 0
                away_score = 0
                if "score" in match_data:
                    home_score = match_data["score"].get("home", 0)
                    away_score = match_data["score"].get("away", 0)
                else:
                    home_score = match_data.get("homeScore", 0) or match_data.get("home_score", 0)
                    away_score = match_data.get("awayScore", 0) or match_data.get("away_score", 0)
                
                # Parse minute
                minute = None
                if "minute" in match_data:
                    minute = match_data.get("minute")
                elif isinstance(status_data, dict) and "minute" in status_data:
                    minute = status_data.get("minute")
                
                live_match = ProviderLiveMatch(
                    # Source metadata
                    provider=self.PROVIDER_NAME,
                    source_id=str(match_data.get("id") or match_data.get("matchId", "")),
                    fetched_at=now,
                    source_updated_at=None,
                    is_live=True,
                    data_freshness_seconds=None,
                    
                    # Live state
                    match_id=str(match_data.get("id") or match_data.get("matchId", "")),
                    status=status,
                    minute=minute,
                    added_time=match_data.get("addedTime") or match_data.get("added_time"),
                    
                    # Scores
                    home_score=home_score,
                    away_score=away_score,
                    
                    # Events (simplified)
                    live_events=match_data.get("events") if match_data.get("events") else None,
                    
                    # Last updated
                    last_updated=now,
                )
                live_matches.append(live_match)
                
            except Exception as e:
                logger.warning(
                    f"[{self.PROVIDER_NAME}] Failed to normalize live match: {e}"
                )
        
        # Cache result
        if self.cache:
            self.cache.set(cache_key, live_matches, ttl_seconds=LIVE_DATA_TTL)
        
        logger.info(
            f"[{self.PROVIDER_NAME}] Fetched {len(live_matches)} live matches"
        )
        return live_matches
    
    async def get_league(self, league_id: str) -> Optional[ProviderCompetition]:
        """Get league/competition information.
        
        STUB: FotMob league lookup not implemented — use Ryzellx or OpenLigaDB for metadata.
        
        Args:
            league_id: League ID
            
        Returns:
            None (not implemented)
        """
        logger.debug(
            f"[{self.PROVIDER_NAME}] get_league not implemented — "
            f"use Ryzellx or OpenLigaDB for league metadata"
        )
        return None
    
    async def get_team(self, team_id: str) -> Optional[ProviderTeam]:
        """Get team information.
        
        STUB: FotMob team lookup not a priority — use Ryzellx instead.
        
        Args:
            team_id: Team ID
            
        Returns:
            None (not implemented)
        """
        logger.debug(
            f"[{self.PROVIDER_NAME}] get_team not implemented — "
            f"use Ryzellx for team metadata"
        )
        return None
    
    async def get_player(self, player_id: str) -> Optional[ProviderPlayer]:
        """Get player information.
        
        STUB: FotMob player lookup not a priority — use Ryzellx instead.
        
        Args:
            player_id: Player ID
            
        Returns:
            None (not implemented)
        """
        logger.debug(
            f"[{self.PROVIDER_NAME}] get_player not implemented — "
            f"use Ryzellx for player metadata"
        )
        return None
    
    async def get_standings(self, league_id: str) -> List[ProviderStanding]:
        """Get league standings/table.
        
        STUB: FotMob standings not a priority — use Ryzellx or OpenLigaDB instead.
        
        Args:
            league_id: League ID
            
        Returns:
            Empty list (not implemented)
        """
        logger.debug(
            f"[{self.PROVIDER_NAME}] get_standings not implemented — "
            f"use Ryzellx or OpenLigaDB for standings"
        )
        return []

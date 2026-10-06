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
from typing import List, Optional, Dict, Any
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
)
from app.providers.models import (
    ProviderMatch,
    ProviderCompetition,
    ProviderTeam,
    ProviderPlayer,
    ProviderStanding,
    ProviderLiveMatch,
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
        # "live", "finished", "not_started", "halftime", "postponed", etc.
        if status_lower in ["live", "in_play", "playing"]:
            return MatchStatus.LIVE
        elif status_lower in ["ht", "half_time", "halftime"]:
            return MatchStatus.HALF_TIME
        elif status_lower in ["ft", "finished", "full_time", "fulltime"]:
            return MatchStatus.FINISHED
        elif status_lower in ["postponed", "pst"]:
            return MatchStatus.POSTPONED
        elif status_lower in ["cancelled", "canceled", "cnc"]:
            return MatchStatus.CANCELLED
        elif status_lower in ["suspended", "susp"]:
            return MatchStatus.SUSPENDED
        elif status_lower in ["scheduled", "not_started", "ns", "not started"]:
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
    
    def _normalize_match(self, data: Dict[str, Any], is_live: bool = False) -> ProviderMatch:
        """Normalize FotMob match data to ProviderMatch.
        
        Args:
            data: Raw match data from FotMob API
            is_live: Whether this is live match data
            
        Returns:
            Normalized ProviderMatch
        """
        now = datetime.now(timezone.utc)
        
        # Parse scheduled time - FotMob may use different field names
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
                    timestamp_ms = int(scheduled_str)
                    scheduled_at = datetime.fromtimestamp(timestamp_ms / 1000, tz=timezone.utc)
                except:
                    scheduled_at = now
        else:
            scheduled_at = now
        
        # Parse status
        status_data = data.get("status") or {}
        if isinstance(status_data, dict):
            status_str = status_data.get("type") or status_data.get("reason")
        else:
            status_str = str(status_data)
        status = self._parse_match_status(status_str)
        
        # Parse scores - FotMob may nest scores differently
        home_score = None
        away_score = None
        if "score" in data:
            home_score = data["score"].get("home")
            away_score = data["score"].get("away")
        else:
            home_score = data.get("homeScore") or data.get("home_score")
            away_score = data.get("awayScore") or data.get("away_score")
        
        # Parse teams
        home_team = data.get("home") or data.get("homeTeam") or {}
        away_team = data.get("away") or data.get("awayTeam") or {}
        
        if isinstance(home_team, dict):
            home_team_id = str(home_team.get("id", ""))
            home_team_name = home_team.get("name", "")
        else:
            home_team_id = ""
            home_team_name = str(home_team)
        
        if isinstance(away_team, dict):
            away_team_id = str(away_team.get("id", ""))
            away_team_name = away_team.get("name", "")
        else:
            away_team_id = ""
            away_team_name = str(away_team)
        
        # Parse competition
        league_data = data.get("league") or data.get("competition") or {}
        if isinstance(league_data, dict):
            competition_id = str(league_data.get("id")) if league_data.get("id") else None
            competition_name = league_data.get("name")
        else:
            competition_id = None
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
            source_id=str(data.get("id") or data.get("matchId", "")),
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
            round=data.get("round") or data.get("matchday"),
        )
    
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
                            match = self._normalize_match(match_data, is_live=False)
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

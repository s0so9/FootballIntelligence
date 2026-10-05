"""Live matches endpoint for API v1.

This module implements the live matches REST API endpoint with
provider health and data quality reporting.

CRITICAL: NEVER returns fabricated match data. Returns empty list
with provider health status on failure.
"""

from typing import Optional, Dict, Any, List
from datetime import datetime
from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from app.config import settings
from app.providers.models import ProviderLiveMatch
from app.providers.manager import ProviderManager
from app.providers.cache import ProviderCache
from app.providers.ryzellx import RyzellxFootballProvider
from app.providers.fotmob import FotMobFootballProvider
from app.providers.openligadb import OpenLigaDBFootballProvider
from app.providers.health import ProviderHealthService


router = APIRouter(prefix="/matches", tags=["live-matches"])


class LiveMatchResponse(BaseModel):
    """Live match response schema."""
    
    match_id: str
    status: str
    minute: Optional[int] = None
    home_score: int
    away_score: int
    home_team_id: Optional[str] = None
    away_team_id: Optional[str] = None
    data_quality_flags: Dict[str, bool] = Field(default_factory=dict)


class LiveMatchesResponse(BaseModel):
    """Live matches API response."""
    
    matches: List[LiveMatchResponse] = Field(
        default_factory=list,
        description="List of live matches"
    )
    
    provider_health: Dict[str, Any] = Field(
        default_factory=dict,
        description="Provider health status"
    )
    
    data_quality: Dict[str, Any] = Field(
        default_factory=dict,
        description="Aggregated data quality indicators"
    )
    
    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="Response timestamp"
    )
    
    provider_used: Optional[str] = Field(
        None,
        description="Provider that supplied the data"
    )
    
    total_count: int = Field(
        0,
        description="Total number of live matches"
    )


def _build_data_quality_flags(match: ProviderLiveMatch) -> Dict[str, bool]:
    """Build data quality flags from ProviderLiveMatch.
    
    Args:
        match: Provider live match data
        
    Returns:
        Dict of data quality flags
    """
    flags = {}
    
    if match.data_quality:
        flags = {
            "has_xg": match.data_quality.has_xg,
            "has_events": match.data_quality.has_events,
            "has_shots": match.data_quality.has_shots,
            "has_player_positions": match.data_quality.has_player_positions,
            "has_ball_tracking": match.data_quality.has_ball_tracking,
            "has_shot_coordinates": match.data_quality.has_shot_coordinates,
            "has_live_statistics": match.data_quality.has_live_statistics,
        }
    else:
        # Infer from available data
        flags = {
            "has_xg": False,
            "has_events": match.live_events is not None and len(match.live_events) > 0,
            "has_shots": False,
            "has_player_positions": match.player_positions is not None,
            "has_ball_tracking": match.ball_position is not None,
            "has_shot_coordinates": False,
            "has_live_statistics": False,
        }
    
    return flags


def _aggregate_data_quality(matches: List[ProviderLiveMatch]) -> Dict[str, Any]:
    """Aggregate data quality across all matches.
    
    Args:
        matches: List of provider live matches
        
    Returns:
        Dict with aggregated quality statistics
    """
    if not matches:
        return {
            "total_matches": 0,
            "matches_with_xg": 0,
            "matches_with_events": 0,
            "matches_with_shots": 0,
            "matches_with_player_positions": 0,
            "matches_with_ball_tracking": 0,
        }
    
    total = len(matches)
    with_xg = 0
    with_events = 0
    with_shots = 0
    with_positions = 0
    with_ball = 0
    
    for match in matches:
        flags = _build_data_quality_flags(match)
        if flags.get("has_xg"):
            with_xg += 1
        if flags.get("has_events"):
            with_events += 1
        if flags.get("has_shots"):
            with_shots += 1
        if flags.get("has_player_positions"):
            with_positions += 1
        if flags.get("has_ball_tracking"):
            with_ball += 1
    
    return {
        "total_matches": total,
        "matches_with_xg": with_xg,
        "matches_with_events": with_events,
        "matches_with_shots": with_shots,
        "matches_with_player_positions": with_positions,
        "matches_with_ball_tracking": with_ball,
    }


@router.get(
    "/live",
    response_model=LiveMatchesResponse,
    summary="Get live matches",
    description="Get currently live matches with provider health and data quality reporting.",
)
async def get_live_matches(
    league_id: Optional[str] = Query(None, description="Filter by league ID"),
    include_stats: bool = Query(False, description="Include live statistics"),
) -> LiveMatchesResponse:
    """
    Get currently live matches.
    
    Returns live matches from the provider with health and quality information.
    On provider failure, returns empty matches list with provider health status.
    NEVER fabricates match data.
    
    Query Parameters:
    - league_id: Optional filter by league/competition ID
    - include_stats: Whether to include live statistics (not yet implemented)
    
    Returns:
        LiveMatchesResponse with matches, provider health, and data quality
    """
    # Initialize provider infrastructure
    cache = ProviderCache()
    
    # Create provider instances
    ryzellx = RyzellxFootballProvider(
        base_url=settings.ryzellx_base_url,
        timeout_seconds=settings.provider_timeout_seconds,
        retry_count=settings.provider_retry_count,
        cache=cache,
    )
    
    fotmob = FotMobFootballProvider(
        base_url=settings.fotmob_base_url,
        timeout_seconds=settings.provider_timeout_seconds,
        retry_count=min(settings.provider_retry_count, 1),
        cache=cache,
    )
    
    openligadb = OpenLigaDBFootballProvider(
        base_url=settings.openligadb_base_url,
        timeout_seconds=settings.provider_timeout_seconds,
        retry_count=settings.provider_retry_count,
        cache=cache,
    )
    
    # Create provider manager
    manager = ProviderManager(
        ryzellx=ryzellx,
        fotmob=fotmob,
        openligadb=openligadb,
        cache=cache,
    )
    
    # Create health service
    health_service = ProviderHealthService(
        provider_configs={
            "ryzellx": {
                "base_url": settings.ryzellx_base_url,
                "test_endpoints": ["/api/matches/live"],
            },
            "fotmob": {
                "base_url": settings.fotmob_base_url,
                "test_endpoints": ["/matches"],
            },
            "openligadb": {
                "base_url": settings.openligadb_base_url,
                "test_endpoints": ["/getavailableleagues"],
            },
        },
        timeout_seconds=settings.provider_timeout_seconds,
    )
    
    try:
        # Get live matches from manager
        matches_raw, metadata = await manager.get_live_matches()
        
        # Extract provider used
        provider_used = metadata.get("selected_provider")
        
        # Convert to response schema
        matches_response = []
        for match in matches_raw:
            # Extract team IDs if available (not in ProviderLiveMatch by default)
            home_team_id = None
            away_team_id = None
            
            match_response = LiveMatchResponse(
                match_id=match.match_id,
                status=match.status.value if hasattr(match.status, 'value') else str(match.status),
                minute=match.minute,
                home_score=match.home_score,
                away_score=match.away_score,
                home_team_id=home_team_id,
                away_team_id=away_team_id,
                data_quality_flags=_build_data_quality_flags(match),
            )
            matches_response.append(match_response)
        
        # Get provider health status
        health_statuses = await health_service.check_all()
        provider_health = {
            name: {
                "is_available": status.is_available,
                "availability_code": status.availability_code.value,
                "last_check_utc": status.last_check_utc.isoformat(),
                "consecutive_failures": status.consecutive_failures,
                "error_detail": status.error_detail,
            }
            for name, status in health_statuses.items()
        }
        
        # Aggregate data quality
        data_quality = _aggregate_data_quality(matches_raw)
        
        # Build response
        return LiveMatchesResponse(
            matches=matches_response,
            provider_health=provider_health,
            data_quality=data_quality,
            timestamp=datetime.utcnow(),
            provider_used=provider_used,
            total_count=len(matches_response),
        )
        
    except Exception as e:
        # On any error, return empty list with health status
        # NEVER fabricate match data
        health_statuses = await health_service.check_all()
        provider_health = {
            name: {
                "is_available": status.is_available,
                "availability_code": status.availability_code.value,
                "last_check_utc": status.last_check_utc.isoformat(),
                "consecutive_failures": status.consecutive_failures,
                "error_detail": status.error_detail,
            }
            for name, status in health_statuses.items()
        }
        
        return LiveMatchesResponse(
            matches=[],
            provider_health=provider_health,
            data_quality={"total_matches": 0, "error": str(type(e).__name__)},
            timestamp=datetime.utcnow(),
            provider_used=None,
            total_count=0,
        )
    
    finally:
        # Clean up
        await manager.close()

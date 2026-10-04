"""Tests for multi-provider football data abstraction foundation layer.

Tests for FEAT-001: normalized models, exceptions, and cache.
"""

import pytest
from datetime import datetime, timedelta
import threading
import time

from app.providers.exceptions import (
    ProviderError,
    ProviderTimeoutError,
    ProviderHTTPError,
    ProviderInvalidDataError,
    ProviderNotFoundError,
)
from app.providers.cache import ProviderCache, LIVE_DATA_TTL, METADATA_TTL
from app.providers.models import (
    ProviderCompetition,
    ProviderTeam,
    ProviderPlayer,
    ProviderMatch,
    ProviderMatchEvent,
    ProviderLineup,
    ProviderMatchStats,
    ProviderShot,
    ProviderStanding,
    ProviderLiveMatch,
)
from app.domain.enums import MatchStatus, MatchEventType


class TestProviderExceptions:
    """Tests for provider exception classes."""
    
    def test_provider_error_basic(self):
        """Test basic ProviderError creation and attributes."""
        error = ProviderError(
            provider_name="test_provider",
            operation="get_match",
            message="Something went wrong"
        )
        
        assert error.provider_name == "test_provider"
        assert error.operation == "get_match"
        assert error.message == "Something went wrong"
        assert error.original_error is None
        assert "[test_provider] get_match: Something went wrong" in str(error)
    
    def test_provider_error_with_original(self):
        """Test ProviderError wrapping an original exception."""
        original = ValueError("Invalid value")
        error = ProviderError(
            provider_name="test_provider",
            operation="parse_response",
            message="Failed to parse",
            original_error=original
        )
        
        assert error.original_error is original
        assert error.message == "Failed to parse"
    
    def test_provider_timeout_error(self):
        """Test ProviderTimeoutError."""
        error = ProviderTimeoutError(
            provider_name="slow_provider",
            operation="get_standings",
            message="Request timed out after 30s"
        )
        
        assert isinstance(error, ProviderError)
        assert error.provider_name == "slow_provider"
        assert "timed out" in error.message
    
    def test_provider_http_error(self):
        """Test ProviderHTTPError with status code."""
        error = ProviderHTTPError(
            provider_name="api_provider",
            operation="get_team",
            message="Not found",
            status_code=404
        )
        
        assert isinstance(error, ProviderError)
        assert error.status_code == 404
        assert error.message == "Not found"
        assert "status_code=404" in repr(error)
    
    def test_provider_invalid_data_error(self):
        """Test ProviderInvalidDataError."""
        error = ProviderInvalidDataError(
            provider_name="data_provider",
            operation="parse_match",
            message="Missing required field: home_team_id"
        )
        
        assert isinstance(error, ProviderError)
        assert "Missing required field" in error.message
    
    def test_provider_not_found_error(self):
        """Test ProviderNotFoundError."""
        error = ProviderNotFoundError(
            provider_name="api_provider",
            operation="get_player",
            message="Player with ID 'player_999' not found"
        )
        
        assert isinstance(error, ProviderError)
        assert "not found" in error.message
    
    def test_exception_repr(self):
        """Test exception repr() format."""
        error = ProviderError(
            provider_name="test",
            operation="test_op",
            message="test message"
        )
        
        repr_str = repr(error)
        assert "ProviderError" in repr_str
        assert "provider_name='test'" in repr_str
        assert "operation='test_op'" in repr_str
        assert "message='test message'" in repr_str


class TestProviderModels:
    """Tests for normalized provider models."""
    
    def test_provider_competition_minimal(self):
        """Test ProviderCompetition with minimal required fields."""
        comp = ProviderCompetition(
            provider="test_provider",
            source_id="comp_123",
            fetched_at=datetime.utcnow(),
            name="Test League"
        )
        
        assert comp.provider == "test_provider"
        assert comp.source_id == "comp_123"
        assert comp.name == "Test League"
        assert comp.is_live is False
        assert comp.country is None
        assert comp.level is None
    
    def test_provider_competition_full(self):
        """Test ProviderCompetition with all fields."""
        now = datetime.utcnow()
        comp = ProviderCompetition(
            provider="ryzellx",
            source_id="39",
            fetched_at=now,
            source_updated_at=now - timedelta(hours=1),
            is_live=False,
            data_freshness_seconds=3600,
            name="Premier League",
            country="ENG",
            level=1,
            type="league",
            season="2023/2024",
            logo_url="https://example.com/logo.png"
        )
        
        assert comp.provider == "ryzellx"
        assert comp.name == "Premier League"
        assert comp.country == "ENG"
        assert comp.level == 1
        assert comp.data_freshness_seconds == 3600
    
    def test_provider_team_minimal(self):
        """Test ProviderTeam with minimal required fields."""
        team = ProviderTeam(
            provider="test_provider",
            source_id="team_123",
            fetched_at=datetime.utcnow(),
            name="Test FC"
        )
        
        assert team.name == "Test FC"
        assert team.short_name is None
        assert team.code is None
    
    def test_provider_player_optional_fields(self):
        """Test ProviderPlayer uses Optional for unavailable data."""
        player = ProviderPlayer(
            provider="test_provider",
            source_id="player_123",
            fetched_at=datetime.utcnow(),
            name="John Doe"
        )
        
        # All these should be None (not invented values)
        assert player.date_of_birth is None
        assert player.nationality is None
        assert player.position is None
        assert player.shirt_number is None
        assert player.height_cm is None
        assert player.weight_kg is None
    
    def test_provider_match_required_fields(self):
        """Test ProviderMatch with required fields."""
        match = ProviderMatch(
            provider="test_provider",
            source_id="match_123",
            fetched_at=datetime.utcnow(),
            home_team_id="team_1",
            home_team_name="Home FC",
            away_team_id="team_2",
            away_team_name="Away FC",
            scheduled_at=datetime.utcnow() + timedelta(days=1),
            status=MatchStatus.SCHEDULED
        )
        
        assert match.home_team_name == "Home FC"
        assert match.away_team_name == "Away FC"
        assert match.status == MatchStatus.SCHEDULED
        assert match.home_score is None  # Not yet played
        assert match.minute is None
    
    def test_provider_match_live(self):
        """Test ProviderMatch for live match."""
        now = datetime.utcnow()
        match = ProviderMatch(
            provider="fotmob",
            source_id="match_live",
            fetched_at=now,
            is_live=True,
            data_freshness_seconds=5,
            home_team_id="team_1",
            home_team_name="Home FC",
            away_team_id="team_2",
            away_team_name="Away FC",
            scheduled_at=now - timedelta(minutes=45),
            status=MatchStatus.LIVE,
            minute=45,
            home_score=2,
            away_score=1
        )
        
        assert match.is_live is True
        assert match.status == MatchStatus.LIVE
        assert match.minute == 45
        assert match.home_score == 2
        assert match.away_score == 1
    
    def test_provider_match_event(self):
        """Test ProviderMatchEvent."""
        event = ProviderMatchEvent(
            provider="test_provider",
            source_id="event_123",
            fetched_at=datetime.utcnow(),
            match_id="match_123",
            type=MatchEventType.GOAL,
            minute=23,
            team_id="team_1",
            player_id="player_1",
            player_name="John Doe"
        )
        
        assert event.type == MatchEventType.GOAL
        assert event.minute == 23
        assert event.added_time is None
    
    def test_provider_lineup(self):
        """Test ProviderLineup."""
        lineup = ProviderLineup(
            provider="test_provider",
            source_id="lineup_123",
            fetched_at=datetime.utcnow(),
            match_id="match_123",
            team_id="team_1",
            formation="4-3-3",
            starting_xi=["p1", "p2", "p3", "p4", "p5", "p6", "p7", "p8", "p9", "p10", "p11"],
            substitutes=["p12", "p13", "p14"]
        )
        
        assert lineup.formation == "4-3-3"
        assert len(lineup.starting_xi) == 11
        assert len(lineup.substitutes) == 3
    
    def test_provider_match_stats_all_optional(self):
        """Test ProviderMatchStats with all fields optional except identifiers."""
        stats = ProviderMatchStats(
            provider="test_provider",
            source_id="stats_123",
            fetched_at=datetime.utcnow(),
            match_id="match_123",
            team_id="team_1"
        )
        
        # All stats should be None if not provided
        assert stats.xg is None
        assert stats.shots_total is None
        assert stats.possession_percentage is None
        assert stats.corners is None
    
    def test_provider_match_stats_with_xg(self):
        """Test ProviderMatchStats with xG values."""
        stats = ProviderMatchStats(
            provider="ryzellx",
            source_id="stats_123",
            fetched_at=datetime.utcnow(),
            match_id="match_123",
            team_id="team_1",
            xg=2.35,
            xg_against=1.12,
            shots_total=15,
            shots_on_target=7
        )
        
        assert stats.xg == 2.35
        assert stats.xg_against == 1.12
        assert stats.shots_total == 15
    
    def test_provider_shot(self):
        """Test ProviderShot."""
        shot = ProviderShot(
            provider="test_provider",
            source_id="shot_123",
            fetched_at=datetime.utcnow(),
            match_id="match_123",
            team_id="team_1",
            player_id="player_1",
            minute=34,
            xg=0.45,
            result="goal",
            coordinates={"x": 88.5, "y": 52.3}
        )
        
        assert shot.xg == 0.45
        assert shot.result == "goal"
        assert shot.coordinates["x"] == 88.5
    
    def test_provider_standing(self):
        """Test ProviderStanding."""
        standing = ProviderStanding(
            provider="test_provider",
            source_id="standing_123",
            fetched_at=datetime.utcnow(),
            team_id="team_1",
            team_name="Test FC",
            position=3,
            played=10,
            won=6,
            drawn=2,
            lost=2,
            goals_for=18,
            goals_against=12,
            goal_difference=6,
            points=20
        )
        
        assert standing.position == 3
        assert standing.points == 20
        assert standing.goal_difference == 6
    
    def test_provider_live_match(self):
        """Test ProviderLiveMatch."""
        now = datetime.utcnow()
        live_match = ProviderLiveMatch(
            provider="fotmob",
            source_id="live_123",
            fetched_at=now,
            is_live=True,
            data_freshness_seconds=3,
            match_id="match_123",
            status=MatchStatus.LIVE,
            minute=67,
            added_time=None,
            home_score=2,
            away_score=1,
            last_updated=now
        )
        
        assert live_match.is_live is True
        assert live_match.status == MatchStatus.LIVE
        assert live_match.minute == 67
        assert live_match.home_score == 2


class TestProviderCache:
    """Tests for ProviderCache."""
    
    def test_cache_get_set(self):
        """Test basic cache get/set operations."""
        cache = ProviderCache()
        
        cache.set("key1", "value1", ttl_seconds=60)
        
        assert cache.get("key1") == "value1"
        assert cache.get("nonexistent") is None
    
    def test_cache_ttl_expiry(self):
        """Test that cache entries expire after TTL."""
        cache = ProviderCache()
        
        # Set with very short TTL
        cache.set("short_lived", "data", ttl_seconds=1)
        
        # Should be available immediately
        assert cache.get("short_lived") == "data"
        
        # Wait for expiry
        time.sleep(1.1)
        
        # Should be expired
        assert cache.get("short_lived") is None
    
    def test_cache_delete(self):
        """Test cache delete operation."""
        cache = ProviderCache()
        
        cache.set("key1", "value1", ttl_seconds=60)
        assert cache.get("key1") == "value1"
        
        cache.delete("key1")
        assert cache.get("key1") is None
    
    def test_cache_clear(self):
        """Test cache clear operation."""
        cache = ProviderCache()
        
        cache.set("key1", "value1", ttl_seconds=60)
        cache.set("key2", "value2", ttl_seconds=60)
        
        assert cache.size() == 2
        
        cache.clear()
        
        assert cache.size() == 0
        assert cache.get("key1") is None
        assert cache.get("key2") is None
    
    def test_cache_cleanup_expired(self):
        """Test cleanup of expired entries."""
        cache = ProviderCache()
        
        # Add some entries
        cache.set("active", "data", ttl_seconds=60)
        cache.set("expired", "old_data", ttl_seconds=1)
        
        # Wait for one to expire
        time.sleep(1.1)
        
        # Cleanup should remove expired entry
        removed = cache.cleanup_expired()
        assert removed == 1
        assert cache.size() == 1
        assert cache.get("active") == "data"
    
    def test_cache_thread_safety(self):
        """Test that cache is thread-safe."""
        cache = ProviderCache()
        results = []
        
        def writer(key_prefix, count):
            for i in range(count):
                cache.set(f"{key_prefix}_{i}", f"value_{i}", ttl_seconds=60)
        
        def reader(key_prefix, count):
            found = 0
            for i in range(count):
                if cache.get(f"{key_prefix}_{i}") is not None:
                    found += 1
            results.append(found)
        
        # Create multiple threads
        threads = [
            threading.Thread(target=writer, args=("thread1", 50)),
            threading.Thread(target=writer, args=("thread2", 50)),
            threading.Thread(target=reader, args=("thread1", 50)),
            threading.Thread(target=reader, args=("thread2", 50)),
        ]
        
        # Start all threads
        for t in threads:
            t.start()
        
        # Wait for completion
        for t in threads:
            t.join()
        
        # No assertions about specific counts due to race conditions,
        # but the test should complete without errors
        assert len(results) == 2
    
    def test_cache_ttl_constants(self):
        """Test that TTL constants are defined."""
        assert LIVE_DATA_TTL == 30
        assert METADATA_TTL == 3600
    
    def test_cache_complex_objects(self):
        """Test caching complex objects like Pydantic models."""
        cache = ProviderCache()
        
        match = ProviderMatch(
            provider="test",
            source_id="match_123",
            fetched_at=datetime.utcnow(),
            home_team_id="team_1",
            home_team_name="Home FC",
            away_team_id="team_2",
            away_team_name="Away FC",
            scheduled_at=datetime.utcnow(),
            status=MatchStatus.SCHEDULED
        )
        
        cache.set("match:123", match, ttl_seconds=60)
        
        cached_match = cache.get("match:123")
        assert cached_match is not None
        assert cached_match.source_id == "match_123"
        assert cached_match.home_team_name == "Home FC"

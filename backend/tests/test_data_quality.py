"""Tests for DataQualityEngine (Phase 4 FEAT-002).

Tests completeness, consistency, freshness, source conflict detection, and quality scoring.
"""

import pytest
from datetime import datetime, timezone, timedelta
from app.providers import DataQualityEngine, ProviderMatchStats, ProviderMetadata


@pytest.fixture
def engine():
    """Create DataQualityEngine instance."""
    return DataQualityEngine()


@pytest.fixture
def complete_stats():
    """Create complete match statistics for testing."""
    return ProviderMatchStats(
        provider='test_provider',
        source_id='match_123',
        fetched_at=datetime.now(timezone.utc),
        match_id='match_123',
        team_id='team_456',
        goals_scored=2,
        goals_conceded=1,
        xg=1.8,
        xg_against=0.9,
        shots_total=15,
        shots_on_target=8,
        shots_off_target=5,
        shots_blocked=2,
        possession_percentage=55.0,
        passes_completed=450,
        passes_attempted=500,
        pass_accuracy=90.0,
        corners=6,
        free_kicks=12,
        offsides=2,
        yellow_cards=3,
        red_cards=0,
        fouls_committed=10,
        tackles=18,
        interceptions=12,
        clearances=15,
        saves=3,
    )


@pytest.fixture
def partial_stats():
    """Create partial match statistics (only some fields present)."""
    return ProviderMatchStats(
        provider='test_provider',
        source_id='match_123',
        fetched_at=datetime.now(timezone.utc),
        match_id='match_123',
        team_id='team_456',
        goals_scored=2,
        shots_total=15,
        shots_on_target=8,
        possession_percentage=55.0,
        yellow_cards=2,
    )


@pytest.fixture
def inconsistent_stats():
    """Create inconsistent statistics (violates logical rules)."""
    return ProviderMatchStats(
        provider='test_provider',
        source_id='match_123',
        fetched_at=datetime.now(timezone.utc),
        match_id='match_123',
        team_id='team_456',
        goals_scored=-1,  # Invalid: negative
        shots_total=10,
        shots_on_target=15,  # Invalid: more than total
        shots_off_target=12,  # Invalid: more than total
        possession_percentage=150.0,  # Invalid: > 100
        xg=-0.5,  # Invalid: negative
    )


@pytest.fixture
def fresh_metadata():
    """Create fresh metadata (fetched recently)."""
    return ProviderMetadata(
        provider='test_provider',
        source_id='match_123',
        fetched_at=datetime.now(timezone.utc) - timedelta(seconds=60),
        is_live=True,
    )


@pytest.fixture
def stale_metadata():
    """Create stale metadata (fetched long ago)."""
    return ProviderMetadata(
        provider='test_provider',
        source_id='match_123',
        fetched_at=datetime.now(timezone.utc) - timedelta(seconds=600),
        is_live=False,
    )


class TestCheckCompleteness:
    """Test completeness calculation."""
    
    def test_complete_stats(self, engine, complete_stats):
        """Verify complete stats have ratio of 1.0."""
        result = engine.check_completeness(complete_stats)
        
        assert result['available'] == 22
        assert result['expected'] == 22
        assert result['ratio'] == 1.0
        assert result['missing_fields'] == []
    
    def test_partial_stats(self, engine, partial_stats):
        """Verify partial stats have correct ratio."""
        result = engine.check_completeness(partial_stats)
        
        assert result['available'] == 5
        assert result['expected'] == 22
        assert result['ratio'] == pytest.approx(5 / 22)
        assert len(result['missing_fields']) == 17
        assert 'xg' in result['missing_fields']
        assert 'corners' in result['missing_fields']
    
    def test_empty_stats(self, engine):
        """Verify empty stats have ratio of 0.0."""
        empty_stats = ProviderMatchStats(
            provider='test_provider',
            source_id='match_123',
            fetched_at=datetime.now(timezone.utc),
            match_id='match_123',
            team_id='team_456',
        )
        
        result = engine.check_completeness(empty_stats)
        
        assert result['available'] == 0
        assert result['expected'] == 22
        assert result['ratio'] == 0.0
        assert len(result['missing_fields']) == 22


class TestCheckConsistency:
    """Test consistency validation."""
    
    def test_consistent_stats(self, engine, complete_stats):
        """Verify logically consistent stats have no violations."""
        result = engine.check_consistency(complete_stats)
        
        assert result['is_consistent'] is True
        assert result['violations'] == []
    
    def test_shots_on_target_exceeds_total(self, engine):
        """Verify detection of shots_on_target > shots_total."""
        stats = ProviderMatchStats(
            provider='test_provider',
            source_id='match_123',
            fetched_at=datetime.now(timezone.utc),
            match_id='match_123',
            team_id='team_456',
            shots_total=10,
            shots_on_target=15,
        )
        
        result = engine.check_consistency(stats)
        
        assert result['is_consistent'] is False
        assert len(result['violations']) == 1
        assert 'shots_on_target (15) > shots_total (10)' in result['violations']
    
    def test_shots_off_target_exceeds_total(self, engine):
        """Verify detection of shots_off_target > shots_total."""
        stats = ProviderMatchStats(
            provider='test_provider',
            source_id='match_123',
            fetched_at=datetime.now(timezone.utc),
            match_id='match_123',
            team_id='team_456',
            shots_total=10,
            shots_off_target=12,
        )
        
        result = engine.check_consistency(stats)
        
        assert result['is_consistent'] is False
        assert 'shots_off_target (12) > shots_total (10)' in result['violations']
    
    def test_shots_blocked_exceeds_total(self, engine):
        """Verify detection of shots_blocked > shots_total."""
        stats = ProviderMatchStats(
            provider='test_provider',
            source_id='match_123',
            fetched_at=datetime.now(timezone.utc),
            match_id='match_123',
            team_id='team_456',
            shots_total=10,
            shots_blocked=11,
        )
        
        result = engine.check_consistency(stats)
        
        assert result['is_consistent'] is False
        assert 'shots_blocked (11) > shots_total (10)' in result['violations']
    
    def test_possession_out_of_range(self, engine):
        """Verify detection of possession_percentage outside [0, 100]."""
        stats = ProviderMatchStats(
            provider='test_provider',
            source_id='match_123',
            fetched_at=datetime.now(timezone.utc),
            match_id='match_123',
            team_id='team_456',
            possession_percentage=150.0,
        )
        
        result = engine.check_consistency(stats)
        
        assert result['is_consistent'] is False
        assert 'possession_percentage (150.0) not in range [0, 100]' in result['violations']
    
    def test_negative_xg(self, engine):
        """Verify detection of negative xG."""
        stats = ProviderMatchStats(
            provider='test_provider',
            source_id='match_123',
            fetched_at=datetime.now(timezone.utc),
            match_id='match_123',
            team_id='team_456',
            xg=-0.5,
        )
        
        result = engine.check_consistency(stats)
        
        assert result['is_consistent'] is False
        assert 'xg (-0.5) < 0' in result['violations']
    
    def test_negative_goals(self, engine):
        """Verify detection of negative goals."""
        stats = ProviderMatchStats(
            provider='test_provider',
            source_id='match_123',
            fetched_at=datetime.now(timezone.utc),
            match_id='match_123',
            team_id='team_456',
            goals_scored=-1,
        )
        
        result = engine.check_consistency(stats)
        
        assert result['is_consistent'] is False
        assert 'goals_scored (-1) < 0' in result['violations']
    
    def test_multiple_violations(self, engine, inconsistent_stats):
        """Verify detection of multiple violations."""
        result = engine.check_consistency(inconsistent_stats)
        
        assert result['is_consistent'] is False
        assert len(result['violations']) >= 5
    
    def test_missing_fields_not_violations(self, engine, partial_stats):
        """Verify None/missing fields don't trigger violations."""
        result = engine.check_consistency(partial_stats)
        
        # partial_stats has consistent values for fields present
        assert result['is_consistent'] is True
        assert result['violations'] == []


class TestCheckFreshness:
    """Test freshness validation."""
    
    def test_fresh_data(self, engine, fresh_metadata):
        """Verify recently fetched data is considered fresh."""
        result = engine.check_freshness(fresh_metadata, max_age_seconds=300)
        
        assert result is True
    
    def test_stale_data(self, engine, stale_metadata):
        """Verify old data is considered stale."""
        result = engine.check_freshness(stale_metadata, max_age_seconds=300)
        
        assert result is False
    
    def test_custom_threshold(self, engine):
        """Verify custom max_age_seconds threshold works."""
        metadata = ProviderMetadata(
            provider='test_provider',
            source_id='match_123',
            fetched_at=datetime.now(timezone.utc) - timedelta(seconds=150),
        )
        
        # Should be stale with 60s threshold
        assert engine.check_freshness(metadata, max_age_seconds=60) is False
        
        # Should be fresh with 300s threshold
        assert engine.check_freshness(metadata, max_age_seconds=300) is True
    
    def test_timezone_aware_timestamps(self, engine):
        """Verify timezone-aware timestamps are handled correctly."""
        metadata = ProviderMetadata(
            provider='test_provider',
            source_id='match_123',
            fetched_at=datetime.now(timezone.utc),
        )
        
        result = engine.check_freshness(metadata, max_age_seconds=300)
        assert result is True


class TestDetectSourceConflicts:
    """Test source conflict detection."""
    
    def test_no_conflicts_same_values(self, engine):
        """Verify no conflicts when providers agree."""
        stats1 = ProviderMatchStats(
            provider='provider_a',
            source_id='match_123',
            fetched_at=datetime.now(timezone.utc),
            match_id='match_123',
            team_id='team_456',
            shots_total=15,
            goals_scored=2,
        )
        
        stats2 = ProviderMatchStats(
            provider='provider_b',
            source_id='match_123',
            fetched_at=datetime.now(timezone.utc),
            match_id='match_123',
            team_id='team_456',
            shots_total=15,
            goals_scored=2,
        )
        
        result = engine.detect_source_conflicts([stats1, stats2])
        
        assert result['has_conflicts'] is False
        assert result['conflicts'] == []
    
    def test_conflicts_different_values(self, engine):
        """Verify conflicts detected when providers disagree."""
        stats1 = ProviderMatchStats(
            provider='provider_a',
            source_id='match_123',
            fetched_at=datetime.now(timezone.utc),
            match_id='match_123',
            team_id='team_456',
            shots_total=15,
            goals_scored=2,
        )
        
        stats2 = ProviderMatchStats(
            provider='provider_b',
            source_id='match_123',
            fetched_at=datetime.now(timezone.utc),
            match_id='match_123',
            team_id='team_456',
            shots_total=14,  # Different
            goals_scored=2,
        )
        
        result = engine.detect_source_conflicts([stats1, stats2])
        
        assert result['has_conflicts'] is True
        assert len(result['conflicts']) == 1
        
        conflict = result['conflicts'][0]
        assert conflict['field'] == 'shots_total'
        assert len(conflict['values']) == 2
        
        # Check both provider values are present
        providers = [v['provider'] for v in conflict['values']]
        values = [v['value'] for v in conflict['values']]
        assert 'provider_a' in providers
        assert 'provider_b' in providers
        assert 15 in values
        assert 14 in values
    
    def test_multiple_conflicts(self, engine):
        """Verify multiple field conflicts are detected."""
        stats1 = ProviderMatchStats(
            provider='provider_a',
            source_id='match_123',
            fetched_at=datetime.now(timezone.utc),
            match_id='match_123',
            team_id='team_456',
            shots_total=15,
            goals_scored=2,
            corners=6,
        )
        
        stats2 = ProviderMatchStats(
            provider='provider_b',
            source_id='match_123',
            fetched_at=datetime.now(timezone.utc),
            match_id='match_123',
            team_id='team_456',
            shots_total=14,  # Different
            goals_scored=3,  # Different
            corners=6,
        )
        
        result = engine.detect_source_conflicts([stats1, stats2])
        
        assert result['has_conflicts'] is True
        assert len(result['conflicts']) == 2
        
        conflict_fields = [c['field'] for c in result['conflicts']]
        assert 'shots_total' in conflict_fields
        assert 'goals_scored' in conflict_fields
        assert 'corners' not in conflict_fields  # Same value
    
    def test_partial_provider_coverage(self, engine):
        """Verify conflicts only for fields where both providers have values."""
        stats1 = ProviderMatchStats(
            provider='provider_a',
            source_id='match_123',
            fetched_at=datetime.now(timezone.utc),
            match_id='match_123',
            team_id='team_456',
            shots_total=15,
            goals_scored=2,
            xg=1.8,  # Only in provider_a
        )
        
        stats2 = ProviderMatchStats(
            provider='provider_b',
            source_id='match_123',
            fetched_at=datetime.now(timezone.utc),
            match_id='match_123',
            team_id='team_456',
            shots_total=15,
            goals_scored=2,
            # xg is None in provider_b
        )
        
        result = engine.detect_source_conflicts([stats1, stats2])
        
        # No conflicts because xg is only present in one provider
        assert result['has_conflicts'] is False


class TestCalculateQualityScore:
    """Test quality score calculation."""
    
    def test_perfect_quality(self, engine):
        """Verify perfect quality score for complete, consistent, fresh data."""
        completeness = {
            'ratio': 1.0,
            'available': 22,
            'expected': 22,
            'missing_fields': []
        }
        consistency = {
            'is_consistent': True,
            'violations': []
        }
        freshness = True
        
        result = engine.calculate_quality_score(completeness, consistency, freshness)
        
        assert result['overall'] == 100.0
        assert result['completeness'] == 100.0
        assert result['consistency'] == 100.0
        assert result['freshness'] == 100.0
    
    def test_partial_completeness(self, engine):
        """Verify score reflects partial completeness."""
        completeness = {
            'ratio': 0.5,
            'available': 11,
            'expected': 22,
            'missing_fields': []
        }
        consistency = {
            'is_consistent': True,
            'violations': []
        }
        freshness = True
        
        result = engine.calculate_quality_score(completeness, consistency, freshness)
        
        assert result['completeness'] == 50.0
        assert result['consistency'] == 100.0
        assert result['freshness'] == 100.0
        # overall = 50*0.4 + 100*0.4 + 100*0.2 = 20 + 40 + 20 = 80
        assert result['overall'] == 80.0
    
    def test_consistency_violations(self, engine):
        """Verify consistency violations reduce score."""
        completeness = {
            'ratio': 1.0,
            'available': 22,
            'expected': 22,
            'missing_fields': []
        }
        consistency = {
            'is_consistent': False,
            'violations': ['violation_1', 'violation_2']
        }
        freshness = True
        
        result = engine.calculate_quality_score(completeness, consistency, freshness)
        
        assert result['completeness'] == 100.0
        # consistency = 100 - (2 * 20) = 60
        assert result['consistency'] == 60.0
        assert result['freshness'] == 100.0
        # overall = 100*0.4 + 60*0.4 + 100*0.2 = 40 + 24 + 20 = 84
        assert result['overall'] == 84.0
    
    def test_stale_data(self, engine):
        """Verify stale data reduces score."""
        completeness = {
            'ratio': 1.0,
            'available': 22,
            'expected': 22,
            'missing_fields': []
        }
        consistency = {
            'is_consistent': True,
            'violations': []
        }
        freshness = False
        
        result = engine.calculate_quality_score(completeness, consistency, freshness)
        
        assert result['completeness'] == 100.0
        assert result['consistency'] == 100.0
        assert result['freshness'] == 50.0
        # overall = 100*0.4 + 100*0.4 + 50*0.2 = 40 + 40 + 10 = 90
        assert result['overall'] == 90.0
    
    def test_poor_quality_all_factors(self, engine):
        """Verify low score when all factors are poor."""
        completeness = {
            'ratio': 0.25,
            'available': 5,
            'expected': 22,
            'missing_fields': []
        }
        consistency = {
            'is_consistent': False,
            'violations': ['v1', 'v2', 'v3']
        }
        freshness = False
        
        result = engine.calculate_quality_score(completeness, consistency, freshness)
        
        assert result['completeness'] == 25.0
        # consistency = 100 - (3 * 20) = 40
        assert result['consistency'] == 40.0
        assert result['freshness'] == 50.0
        # overall = 25*0.4 + 40*0.4 + 50*0.2 = 10 + 16 + 10 = 36
        assert result['overall'] == 36.0
    
    def test_many_violations_floor_at_zero(self, engine):
        """Verify consistency score floors at 0 for many violations."""
        completeness = {
            'ratio': 1.0,
            'available': 22,
            'expected': 22,
            'missing_fields': []
        }
        consistency = {
            'is_consistent': False,
            'violations': ['v1', 'v2', 'v3', 'v4', 'v5', 'v6']  # 6 violations
        }
        freshness = True
        
        result = engine.calculate_quality_score(completeness, consistency, freshness)
        
        # 100 - (6 * 20) = -20, but should floor at 0
        assert result['consistency'] == 0.0
        # overall = 100*0.4 + 0*0.4 + 100*0.2 = 40 + 0 + 20 = 60
        assert result['overall'] == 60.0

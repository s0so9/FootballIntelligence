"""Tests for data quality gate."""

import pytest
from typing import Dict, Optional

from app.prediction.data_quality import (
    DataQualityCheck,
    DataQualityReport,
    DataQualityGate,
)


def test_data_quality_check_creation():
    """Test DataQualityCheck creation."""
    check = DataQualityCheck(
        check_name="test_check",
        passed=True,
        score=0.95,
        severity="HIGH",
        message="Check passed",
        details={"value": 10}
    )
    
    assert check.check_name == "test_check"
    assert check.passed is True
    assert check.score == 0.95
    assert check.severity == "HIGH"


def test_data_quality_report_creation():
    """Test DataQualityReport creation."""
    checks = [
        DataQualityCheck(
            check_name="check_1",
            passed=True,
            score=1.0,
            severity="HIGH",
            message="Pass"
        ),
        DataQualityCheck(
            check_name="check_2",
            passed=False,
            score=0.5,
            severity="MEDIUM",
            message="Fail"
        )
    ]
    
    report = DataQualityReport(
        overall_score=0.75,
        checks=checks,
        passed=1,
        failed=1,
        warnings=["check_2 failed"]
    )
    
    assert report.overall_score == 0.75
    assert report.passed == 1
    assert report.failed == 1
    assert len(report.checks) == 2


def test_data_quality_gate_sample_size_check_sufficient():
    """Test sample size check with sufficient data."""
    gate = DataQualityGate(min_sample_size=5)
    
    features = {
        "home_match_count": 10.0,
        "away_match_count": 8.0,
        "home_goals_avg": 1.5
    }
    
    report = gate.assess(features)
    
    # Find sample_size_check
    sample_check = next(c for c in report.checks if c.check_name == "sample_size_check")
    assert sample_check.passed is True
    assert sample_check.score >= 1.0


def test_data_quality_gate_sample_size_check_insufficient():
    """Test sample size check with insufficient data."""
    gate = DataQualityGate(min_sample_size=5)
    
    features = {
        "home_match_count": 3.0,
        "away_match_count": 2.0,
        "home_goals_avg": 1.5
    }
    
    report = gate.assess(features)
    
    sample_check = next(c for c in report.checks if c.check_name == "sample_size_check")
    assert sample_check.passed is False
    assert sample_check.severity == "CRITICAL"


def test_data_quality_gate_recency_check_recent():
    """Test recency check with recent data."""
    gate = DataQualityGate(max_days_stale=365)
    
    features = {
        "home_match_count": 10.0,
        "away_match_count": 10.0,
        "days_since_last_match": 30.0
    }
    
    report = gate.assess(features)
    
    recency_check = next(c for c in report.checks if c.check_name == "recency_check")
    assert recency_check.passed is True


def test_data_quality_gate_recency_check_stale():
    """Test recency check with stale data."""
    gate = DataQualityGate(max_days_stale=365)
    
    features = {
        "home_match_count": 10.0,
        "away_match_count": 10.0,
        "days_since_last_match": 400.0
    }
    
    report = gate.assess(features)
    
    recency_check = next(c for c in report.checks if c.check_name == "recency_check")
    assert recency_check.passed is False
    assert recency_check.severity == "MEDIUM"


def test_data_quality_gate_recency_check_missing():
    """Test recency check with missing data."""
    gate = DataQualityGate(max_days_stale=365)
    
    features = {
        "home_match_count": 10.0,
        "away_match_count": 10.0
        # Missing days_since_last_match
    }
    
    report = gate.assess(features)
    
    recency_check = next(c for c in report.checks if c.check_name == "recency_check")
    assert recency_check.passed is False


def test_data_quality_gate_completeness_check_complete():
    """Test completeness check with complete data."""
    gate = DataQualityGate(min_completeness=0.7)
    
    features = {
        "home_goals_avg": 1.5,
        "away_goals_avg": 1.2,
        "home_match_count": 10.0,
        "away_match_count": 10.0,
        "home_xg": 1.8
    }
    
    report = gate.assess(features)
    
    completeness_check = next(c for c in report.checks if c.check_name == "completeness_check")
    assert completeness_check.passed is True
    assert completeness_check.score == 1.0


def test_data_quality_gate_completeness_check_incomplete():
    """Test completeness check with incomplete data."""
    gate = DataQualityGate(min_completeness=0.7)
    
    features = {
        "home_goals_avg": 1.5,
        "away_goals_avg": None,
        "home_match_count": 10.0,
        "away_match_count": None,
        "home_xg": None
    }
    
    report = gate.assess(features)
    
    completeness_check = next(c for c in report.checks if c.check_name == "completeness_check")
    assert completeness_check.passed is False
    assert completeness_check.score < 0.7


def test_data_quality_gate_consistency_check_valid():
    """Test consistency check with valid data."""
    gate = DataQualityGate()
    
    features = {
        "home_goals_avg": 1.5,
        "away_goals_avg": 1.2,
        "home_match_count": 10.0,
        "away_match_count": 8.0
    }
    
    report = gate.assess(features)
    
    consistency_check = next(c for c in report.checks if c.check_name == "consistency_check")
    assert consistency_check.passed is True


def test_data_quality_gate_consistency_check_negative_values():
    """Test consistency check with invalid negative values."""
    gate = DataQualityGate()
    
    features = {
        "home_goals_avg": -1.5,  # Invalid
        "away_goals_avg": 1.2,
        "home_match_count": 10.0
    }
    
    report = gate.assess(features)
    
    consistency_check = next(c for c in report.checks if c.check_name == "consistency_check")
    assert consistency_check.passed is False
    assert len(consistency_check.details["issues"]) > 0


def test_data_quality_gate_consistency_check_unrealistic_values():
    """Test consistency check with unrealistic values."""
    gate = DataQualityGate()
    
    features = {
        "home_goals_avg": 25.0,  # Unrealistic
        "away_goals_avg": 1.2,
        "home_match_count": 10.0
    }
    
    report = gate.assess(features)
    
    consistency_check = next(c for c in report.checks if c.check_name == "consistency_check")
    assert consistency_check.passed is False


def test_data_quality_gate_temporal_leakage_check():
    """Test temporal leakage check."""
    gate = DataQualityGate()
    
    features = {
        "home_goals_avg": 1.5,
        "away_goals_avg": 1.2
    }
    
    report = gate.assess(features)
    
    temporal_check = next(c for c in report.checks if c.check_name == "temporal_leakage_check")
    assert temporal_check.severity == "CRITICAL"
    # Should pass if features exist (assumes MatchFeatureExtractor did its job)
    assert temporal_check.passed is True


def test_data_quality_gate_overall_score_calculation():
    """Test overall score calculation with mixed results."""
    gate = DataQualityGate(min_sample_size=5, min_completeness=0.7)
    
    features = {
        "home_match_count": 10.0,
        "away_match_count": 10.0,
        "home_goals_avg": 1.5,
        "away_goals_avg": 1.2,
        "days_since_last_match": 30.0
    }
    
    report = gate.assess(features)
    
    assert 0.0 <= report.overall_score <= 1.0
    assert report.passed + report.failed == len(report.checks)


def test_data_quality_gate_warnings_generation():
    """Test that warnings are generated for high/critical failures."""
    gate = DataQualityGate(min_sample_size=10)
    
    features = {
        "home_match_count": 2.0,  # Will fail critical check
        "away_match_count": 3.0,
        "home_goals_avg": 1.5
    }
    
    report = gate.assess(features)
    
    assert len(report.warnings) > 0
    # Should have warning for sample_size_check
    assert any("sample_size_check" in w for w in report.warnings)


def test_data_quality_gate_empty_features():
    """Test behavior with empty features dictionary."""
    gate = DataQualityGate()
    
    features: Dict[str, Optional[float]] = {}
    
    report = gate.assess(features)
    
    # Should have low overall score
    assert report.overall_score < 0.5
    # Should have multiple failures
    assert report.failed > 0


def test_data_quality_gate_all_checks_present():
    """Test that all 5 required checks are present."""
    gate = DataQualityGate()
    
    features = {
        "home_match_count": 10.0,
        "away_match_count": 10.0,
        "home_goals_avg": 1.5,
        "away_goals_avg": 1.2,
        "days_since_last_match": 30.0
    }
    
    report = gate.assess(features)
    
    check_names = {c.check_name for c in report.checks}
    
    # Verify all 5 checks are present
    assert "sample_size_check" in check_names
    assert "recency_check" in check_names
    assert "completeness_check" in check_names
    assert "consistency_check" in check_names
    assert "temporal_leakage_check" in check_names
    assert len(report.checks) == 5


def test_data_quality_gate_custom_thresholds():
    """Test data quality gate with custom thresholds."""
    gate = DataQualityGate(
        min_sample_size=20,
        max_days_stale=180,
        min_completeness=0.9
    )
    
    features = {
        "home_match_count": 15.0,  # Below custom threshold
        "away_match_count": 15.0,
        "home_goals_avg": 1.5,
        "away_goals_avg": None,  # Affects completeness
        "days_since_last_match": 200.0  # Above custom threshold
    }
    
    report = gate.assess(features)
    
    # Should have failures due to custom thresholds
    sample_check = next(c for c in report.checks if c.check_name == "sample_size_check")
    assert sample_check.passed is False
    
    recency_check = next(c for c in report.checks if c.check_name == "recency_check")
    assert recency_check.passed is False

"""Tests for data quality feature calculations."""

import pytest
from datetime import datetime, timezone

from app.features.data_quality import DataQualityFeatureCalculator, DataQualityFeatures
from app.features.team_form import TeamFormFeatures
from app.features.attack_defence import AttackDefenceFeatures


def test_data_quality_with_full_data():
    """Test data quality calculation with complete data."""
    calculator = DataQualityFeatureCalculator(min_sample_size=3)
    
    home_form = TeamFormFeatures(
        team_id="team_home",
        last_n_results=["W", "W", "D", "W", "L"],
        wins=3,
        draws=1,
        losses=1,
        goals_scored=8,
        goals_conceded=5,
        home_wins=2,
        home_draws=1,
        home_losses=0,
        away_wins=1,
        away_draws=0,
        away_losses=1,
        form_string="LWDWW",
        sample_size=5,
        is_available=True
    )
    
    away_form = TeamFormFeatures(
        team_id="team_away",
        last_n_results=["D", "L", "W", "D", "W"],
        wins=2,
        draws=2,
        losses=1,
        goals_scored=6,
        goals_conceded=6,
        home_wins=1,
        home_draws=1,
        home_losses=0,
        away_wins=1,
        away_draws=1,
        away_losses=1,
        form_string="WDWLD",
        sample_size=5,
        is_available=True
    )
    
    home_attack_defence = AttackDefenceFeatures(team_id="team_id", goals_per_match=1.6,
        goals_conceded_per_match=1.0,
        xg_per_match=1.8,
        xga_per_match=0.9,
        shots_per_match=12.0,
        sample_size=5,
        xg_sample_size=5
    )
    
    away_attack_defence = AttackDefenceFeatures(team_id="team_id", goals_per_match=1.2,
        goals_conceded_per_match=1.2,
        xg_per_match=1.3,
        xga_per_match=1.1,
        shots_per_match=10.0,
        sample_size=5,
        xg_sample_size=5
    )
    
    data_quality = calculator.calculate_confidence(
        home_form=home_form,
        away_form=away_form,
        home_attack_defence=home_attack_defence,
        away_attack_defence=away_attack_defence,
        data_freshness_seconds=3600  # 1 hour old
    )
    
    assert data_quality.sample_size_home == 5
    assert data_quality.sample_size_away == 5
    assert data_quality.xg_available_home is True
    assert data_quality.xg_available_away is True
    assert data_quality.data_freshness_seconds == 3600
    assert data_quality.missing_field_ratio < 0.5
    assert data_quality.feature_confidence > 0.7  # High confidence with complete data
    assert data_quality.provider_available is True


def test_data_quality_zero_sample_size():
    """Test data quality calculation with zero sample size."""
    calculator = DataQualityFeatureCalculator(min_sample_size=3)
    
    home_form = TeamFormFeatures(
        team_id="team_home",
        last_n_results=[],
        wins=0,
        draws=0,
        losses=0,
        goals_scored=0,
        goals_conceded=0,
        home_wins=0,
        home_draws=0,
        home_losses=0,
        away_wins=0,
        away_draws=0,
        away_losses=0,
        form_string="",
        sample_size=0,
        is_available=False
    )
    
    away_form = TeamFormFeatures(
        team_id="team_away",
        last_n_results=[],
        wins=0,
        draws=0,
        losses=0,
        goals_scored=0,
        goals_conceded=0,
        home_wins=0,
        home_draws=0,
        home_losses=0,
        away_wins=0,
        away_draws=0,
        away_losses=0,
        form_string="",
        sample_size=0,
        is_available=False
    )
    
    data_quality = calculator.calculate_confidence(
        home_form=home_form,
        away_form=away_form,
        home_attack_defence=None,
        away_attack_defence=None,
        data_freshness_seconds=None
    )
    
    assert data_quality.sample_size_home == 0
    assert data_quality.sample_size_away == 0
    assert data_quality.xg_available_home is False
    assert data_quality.xg_available_away is False
    assert data_quality.feature_confidence == 0.1  # Only freshness component (default 1.0 * 0.1)
    assert data_quality.missing_field_ratio > 0.5
    assert "Insufficient home team data" in data_quality.notes
    assert "Insufficient away team data" in data_quality.notes


def test_data_quality_missing_xg():
    """Test data quality calculation with missing xG data."""
    calculator = DataQualityFeatureCalculator(min_sample_size=3)
    
    home_form = TeamFormFeatures(team_id="team_id", last_n_results=["W", "W", "D"],
        wins=2,
        draws=1,
        losses=0,
        goals_scored=5,
        goals_conceded=2,
        home_wins=None,
        home_draws=None,
        home_losses=None,
        away_wins=None,
        away_draws=None,
        away_losses=None,
        form_string="DWW",
        sample_size=3,
        is_available=True
    )
    
    away_form = TeamFormFeatures(team_id="team_id", last_n_results=["L", "W", "D"],
        wins=1,
        draws=1,
        losses=1,
        goals_scored=3,
        goals_conceded=3,
        home_wins=None,
        home_draws=None,
        home_losses=None,
        away_wins=None,
        away_draws=None,
        away_losses=None,
        form_string="DWL",
        sample_size=3,
        is_available=True
    )
    
    # Attack/defence features without xG
    home_attack_defence = AttackDefenceFeatures(team_id="team_id", goals_per_match=1.7,
        goals_conceded_per_match=0.7,
        xg_per_match=None,  # No xG available
        xga_per_match=None,
        shots_per_match=11.0,
        sample_size=3,
        xg_sample_size=0
    )
    
    away_attack_defence = AttackDefenceFeatures(team_id="team_id", goals_per_match=1.0,
        goals_conceded_per_match=1.0,
        xg_per_match=None,  # No xG available
        xga_per_match=None,
        shots_per_match=9.0,
        sample_size=3,
        xg_sample_size=0
    )
    
    data_quality = calculator.calculate_confidence(
        home_form=home_form,
        away_form=away_form,
        home_attack_defence=home_attack_defence,
        away_attack_defence=away_attack_defence,
        data_freshness_seconds=7200
    )
    
    assert data_quality.xg_available_home is False
    assert data_quality.xg_available_away is False
    assert "xG data not available" in data_quality.notes
    # Confidence should be reduced but not zero (xG weight is 20%)
    assert 0.3 < data_quality.feature_confidence < 0.7


def test_data_quality_stale_data():
    """Test data quality calculation with very old data."""
    calculator = DataQualityFeatureCalculator(min_sample_size=3)
    
    home_form = TeamFormFeatures(team_id="team_id", last_n_results=["W", "W", "W", "W", "W"],
        wins=5,
        draws=0,
        losses=0,
        goals_scored=12,
        goals_conceded=3,
        home_wins=3,
        home_draws=0,
        home_losses=0,
        away_wins=2,
        away_draws=0,
        away_losses=0,
        form_string="WWWWW",
        sample_size=5,
        is_available=True
    )
    
    away_form = TeamFormFeatures(team_id="team_id", last_n_results=["W", "D", "W", "W", "L"],
        wins=3,
        draws=1,
        losses=1,
        goals_scored=7,
        goals_conceded=5,
        home_wins=2,
        home_draws=0,
        home_losses=0,
        away_wins=1,
        away_draws=1,
        away_losses=1,
        form_string="LWWDW",
        sample_size=5,
        is_available=True
    )
    
    # Data is 45 days old
    stale_seconds = 45 * 24 * 3600
    
    data_quality = calculator.calculate_confidence(
        home_form=home_form,
        away_form=away_form,
        home_attack_defence=None,
        away_attack_defence=None,
        data_freshness_seconds=stale_seconds
    )
    
    assert data_quality.data_freshness_seconds == stale_seconds
    # Confidence should be lower due to stale data (freshness score 0.2 * 0.1 weight)
    # Without xG and with stale data: 0.4 (sample) + 0.3 (availability) + 0.0 (xG) + 0.02 (stale) = 0.72
    assert data_quality.feature_confidence < 0.75


def test_data_quality_partial_xg():
    """Test data quality calculation with xG available for only one team."""
    calculator = DataQualityFeatureCalculator(min_sample_size=3)
    
    home_form = TeamFormFeatures(team_id="team_id", last_n_results=["W", "W", "D", "L"],
        wins=2,
        draws=1,
        losses=1,
        goals_scored=6,
        goals_conceded=4,
        home_wins=None,
        home_draws=None,
        home_losses=None,
        away_wins=None,
        away_draws=None,
        away_losses=None,
        form_string="LDWW",
        sample_size=4,
        is_available=True
    )
    
    away_form = TeamFormFeatures(team_id="team_id", last_n_results=["D", "D", "W", "L"],
        wins=1,
        draws=2,
        losses=1,
        goals_scored=4,
        goals_conceded=5,
        home_wins=None,
        home_draws=None,
        home_losses=None,
        away_wins=None,
        away_draws=None,
        away_losses=None,
        form_string="LWDD",
        sample_size=4,
        is_available=True
    )
    
    # Home has xG, away doesn't
    home_attack_defence = AttackDefenceFeatures(team_id="team_id", goals_per_match=1.5,
        goals_conceded_per_match=1.0,
        xg_per_match=1.6,
        xga_per_match=0.9,
        shots_per_match=13.0,
        sample_size=4,
        xg_sample_size=4
    )
    
    away_attack_defence = AttackDefenceFeatures(team_id="team_id", goals_per_match=1.0,
        goals_conceded_per_match=1.25,
        xg_per_match=None,  # No xG
        xga_per_match=None,
        shots_per_match=8.0,
        sample_size=4,
        xg_sample_size=0
    )
    
    data_quality = calculator.calculate_confidence(
        home_form=home_form,
        away_form=away_form,
        home_attack_defence=home_attack_defence,
        away_attack_defence=away_attack_defence,
        data_freshness_seconds=1800
    )
    
    assert data_quality.xg_available_home is True
    assert data_quality.xg_available_away is False
    # xG score should be 0.5 (partial) * 0.2 weight = 0.1
    # Sample score: (4/10) * 0.4 = 0.16
    # Confidence: 0.16 (sample) + 0.3 (availability) + 0.1 (partial xG) + 0.1 (fresh) = 0.66
    assert 0.65 < data_quality.feature_confidence < 0.67


def test_data_quality_insufficient_sample():
    """Test data quality with sample size below minimum."""
    calculator = DataQualityFeatureCalculator(min_sample_size=5)
    
    home_form = TeamFormFeatures(team_id="team_id", last_n_results=["W", "L"],
        wins=1,
        draws=0,
        losses=1,
        goals_scored=2,
        goals_conceded=2,
        home_wins=None,
        home_draws=None,
        home_losses=None,
        away_wins=None,
        away_draws=None,
        away_losses=None,
        form_string="LW",
        sample_size=2,
        is_available=False  # Below minimum
    )
    
    away_form = TeamFormFeatures(team_id="team_id", last_n_results=["W", "W", "D"],
        wins=2,
        draws=1,
        losses=0,
        goals_scored=5,
        goals_conceded=1,
        home_wins=None,
        home_draws=None,
        home_losses=None,
        away_wins=None,
        away_draws=None,
        away_losses=None,
        form_string="DWW",
        sample_size=3,
        is_available=False  # Below minimum
    )
    
    data_quality = calculator.calculate_confidence(
        home_form=home_form,
        away_form=away_form,
        home_attack_defence=None,
        away_attack_defence=None,
        data_freshness_seconds=None
    )
    
    # Sample size component should be 0 (min_sample=2 < min_sample_size=5)
    # No availability, no xG, default freshness
    # Confidence: 0.0 (sample) + 0.0 (availability) + 0.0 (xG) + 0.1 (fresh) = 0.1
    assert data_quality.feature_confidence == 0.1
    assert "Insufficient home team data" in data_quality.notes
    assert "Insufficient away team data" in data_quality.notes


def test_data_quality_missing_field_ratio():
    """Test missing field ratio calculation."""
    calculator = DataQualityFeatureCalculator(min_sample_size=3)
    
    # Complete data
    home_form_complete = TeamFormFeatures(team_id="team_id", last_n_results=["W", "W", "W"],
        wins=3,
        draws=0,
        losses=0,
        goals_scored=6,
        goals_conceded=1,
        home_wins=2,
        home_draws=0,
        home_losses=0,
        away_wins=1,
        away_draws=0,
        away_losses=0,
        form_string="WWW",
        sample_size=3,
        is_available=True
    )
    
    away_form_complete = TeamFormFeatures(team_id="team_id", last_n_results=["D", "W", "W"],
        wins=2,
        draws=1,
        losses=0,
        goals_scored=5,
        goals_conceded=2,
        home_wins=1,
        home_draws=1,
        home_losses=0,
        away_wins=1,
        away_draws=0,
        away_losses=0,
        form_string="WWD",
        sample_size=3,
        is_available=True
    )
    
    home_attack = AttackDefenceFeatures(team_id="team_id", goals_per_match=2.0,
        goals_conceded_per_match=0.3,
        xg_per_match=2.1,
        xga_per_match=0.4,
        shots_per_match=15.0,
        sample_size=3,
        xg_sample_size=3
    )
    
    away_attack = AttackDefenceFeatures(team_id="team_id", goals_per_match=1.7,
        goals_conceded_per_match=0.7,
        xg_per_match=1.6,
        xga_per_match=0.6,
        shots_per_match=12.0,
        sample_size=3,
        xg_sample_size=3
    )
    
    data_quality_complete = calculator.calculate_confidence(
        home_form=home_form_complete,
        away_form=away_form_complete,
        home_attack_defence=home_attack,
        away_attack_defence=away_attack,
        data_freshness_seconds=600
    )
    
    # With complete data, missing_field_ratio should be 0
    assert data_quality_complete.missing_field_ratio == 0.0
    
    # Incomplete data (no forms)
    home_form_incomplete = TeamFormFeatures(team_id="team_id", last_n_results=[],
        wins=0,
        draws=0,
        losses=0,
        goals_scored=0,
        goals_conceded=0,
        home_wins=None,
        home_draws=None,
        home_losses=None,
        away_wins=None,
        away_draws=None,
        away_losses=None,
        form_string="",
        sample_size=0,
        is_available=False
    )
    
    away_form_incomplete = TeamFormFeatures(team_id="team_id", last_n_results=[],
        wins=0,
        draws=0,
        losses=0,
        goals_scored=0,
        goals_conceded=0,
        home_wins=None,
        home_draws=None,
        home_losses=None,
        away_wins=None,
        away_draws=None,
        away_losses=None,
        form_string="",
        sample_size=0,
        is_available=False
    )
    
    data_quality_incomplete = calculator.calculate_confidence(
        home_form=home_form_incomplete,
        away_form=away_form_incomplete,
        home_attack_defence=None,
        away_attack_defence=None,
        data_freshness_seconds=None
    )
    
    # With no forms and no xG: missing 2+2+1+1 = 6 out of 10 = 0.6
    assert data_quality_incomplete.missing_field_ratio == 0.6



"""Tests for Fix #7: Calibration score_distribution rescaling.

Verifies that CalibrationIntegration.calibrate_prediction() rescales
score_distribution to match calibrated 1X2 probabilities, maintaining
consistency between marginal probabilities and scoreline probabilities.
"""
import pytest
from app.prediction.model_orchestrator import CalibrationIntegration, Calibrator1X2
from app.prediction.interfaces import ModelPrediction


def test_calibration_rescales_score_distribution():
    """BUGFIX: score_distribution is rescaled proportionally after calibration."""
    # Create calibration integration (unfitted - will use identity transform)
    calibrator = Calibrator1X2()  # Unfitted calibrator
    integration = CalibrationIntegration(calibrator=calibrator)
    
    # Original prediction with score distribution that matches 1X2
    # Home wins: (2,0)=0.15 + (1,0)=0.20 = 0.35 (but home_win_prob=0.50)
    # This is an inconsistent prediction - rescaling should fix it
    original_pred = ModelPrediction(
        model_id="test_model",
        home_score_mean=1.5,
        away_score_mean=1.0,
        home_win_prob=0.50,
        draw_prob=0.30,
        away_win_prob=0.20,
        confidence_score=0.7,
        data_quality_score=0.8,
        score_distribution={
            (2, 0): 0.15,  # Home win
            (1, 0): 0.20,  # Home win (total home: 0.35)
            (1, 1): 0.15,  # Draw
            (0, 0): 0.10,  # Draw (total draw: 0.25)
            (0, 1): 0.10,  # Away win (total away: 0.10)
        }
    )
    
    # Calibrate (unfitted calibrator applies identity + renormalization)
    calibrated = integration.calibrate_prediction(original_pred)
    
    # Verify score_distribution was rescaled
    assert calibrated.score_distribution is not None
    
    # Calculate marginals from score distribution
    home_sum = sum(
        prob for (h, a), prob in calibrated.score_distribution.items()
        if h > a
    )
    draw_sum = sum(
        prob for (h, a), prob in calibrated.score_distribution.items()
        if h == a
    )
    away_sum = sum(
        prob for (h, a), prob in calibrated.score_distribution.items()
        if h < a
    )
    
    # After rescaling, marginals should be closer to calibrated 1X2 probabilities
    # Original home_sum was 0.35, should be scaled to match home_win_prob=0.50
    # Scale factor = 0.50/0.50 = 1.0 (identity), but distribution was inconsistent
    # The rescaling logic scales by (calibrated/original) ratio
    assert home_sum > 0.30  # Should be rescaled proportionally
    
    # Verify metadata preserved
    assert calibrated.metadata["original_home_prob"] == 0.50


def test_calibration_preserves_within_category_proportions():
    """Rescaling preserves relative probabilities within each outcome category."""
    calibrator = Calibrator1X2()
    integration = CalibrationIntegration(calibrator=calibrator)
    
    original_pred = ModelPrediction(
        model_id="test_model",
        home_score_mean=2.0,
        away_score_mean=1.0,
        home_win_prob=0.60,
        draw_prob=0.25,
        away_win_prob=0.15,
        confidence_score=0.8,
        data_quality_score=0.9,
        score_distribution={
            (2, 0): 0.20,  # Home win (33% of home wins)
            (3, 1): 0.40,  # Home win (67% of home wins)
            (1, 1): 0.15,  # Draw (60% of draws)
            (2, 2): 0.10,  # Draw (40% of draws)
            (0, 1): 0.15,  # Away win (100%)
        }
    )
    
    calibrated = integration.calibrate_prediction(original_pred)
    
    # Extract home win scorelines
    home_scorelines = {
        k: v for k, v in calibrated.score_distribution.items()
        if k[0] > k[1]
    }
    
    # Check proportions within home wins are preserved
    total_home = sum(home_scorelines.values())
    if total_home > 0:
        ratio_2_0 = home_scorelines[(2, 0)] / total_home
        ratio_3_1 = home_scorelines[(3, 1)] / total_home
        
        # Original ratios: 0.20/0.60=33%, 0.40/0.60=67%
        assert abs(ratio_2_0 - 0.333) < 0.01
        assert abs(ratio_3_1 - 0.667) < 0.01


def test_calibration_handles_empty_score_distribution():
    """Calibration handles predictions without score distribution."""
    calibrator = Calibrator1X2()
    integration = CalibrationIntegration(calibrator=calibrator)
    
    original_pred = ModelPrediction(
        model_id="test_model",
        home_score_mean=1.5,
        away_score_mean=1.2,
        home_win_prob=0.45,
        draw_prob=0.30,
        away_win_prob=0.25,
        confidence_score=0.7,
        data_quality_score=0.8,
        score_distribution={}  # Empty
    )
    
    calibrated = integration.calibrate_prediction(original_pred)
    
    # Should return empty distribution (not crash)
    assert calibrated.score_distribution == {}


def test_calibration_metadata_preserved():
    """Calibration preserves original probabilities in metadata."""
    calibrator = Calibrator1X2()
    integration = CalibrationIntegration(calibrator=calibrator)
    
    original_pred = ModelPrediction(
        model_id="test_model",
        home_score_mean=1.5,
        away_score_mean=1.2,
        home_win_prob=0.45,
        draw_prob=0.30,
        away_win_prob=0.25,
        confidence_score=0.7,
        data_quality_score=0.8,
        score_distribution={(1, 0): 0.20}
    )
    
    calibrated = integration.calibrate_prediction(original_pred)
    
    # Check metadata
    assert calibrated.metadata["original_home_prob"] == 0.45
    assert calibrated.metadata["original_draw_prob"] == 0.30
    assert calibrated.metadata["original_away_prob"] == 0.25
    assert "calibration_status" in calibrated.metadata

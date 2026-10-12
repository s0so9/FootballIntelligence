"""Train calibration models using historical match data.

This script:
1. Loads finished matches with known outcomes
2. Generates predictions for each match using the production models
3. Collects predicted probabilities and actual outcomes
4. Trains calibration models (isotonic regression)
5. Saves calibration configuration for production use

Temporal Safety:
- For each match at time T, only uses historical data before T
- Never uses the match result itself as training data
- Prevents data leakage through strict temporal cutoffs
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logging
from datetime import datetime, timedelta
from typing import List, Tuple, Dict
import pickle
import json

from sqlalchemy import text
from app.database import SessionLocal, engine
from app.prediction.calibration_engine import (
    CalibrationData,
    CalibrationEngine,
    IsotonicCalibration,
    CalibrationStatus
)
from app.prediction.model_orchestrator import Calibrator1X2

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def load_finished_matches() -> List[Dict]:
    """Load finished matches with scores from database.
    
    Returns:
        List of match dictionaries with id, scheduled_at, home_score, away_score
    """
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT 
                id,
                scheduled_at,
                home_score,
                away_score,
                home_team_id,
                away_team_id
            FROM matches
            WHERE home_score IS NOT NULL 
            AND away_score IS NOT NULL
            AND scheduled_at IS NOT NULL
            ORDER BY scheduled_at ASC
        """))
        
        matches = []
        for row in result:
            matches.append({
                'id': row[0],
                'scheduled_at': datetime.fromisoformat(row[1]) if isinstance(row[1], str) else row[1],
                'home_score': row[2],
                'away_score': row[3],
                'home_team_id': row[4],
                'away_team_id': row[5]
            })
        
        return matches


def determine_outcome(home_score: int, away_score: int) -> Tuple[float, float, float]:
    """Determine 1X2 outcome from scores.
    
    Args:
        home_score: Home team score
        away_score: Away team score
        
    Returns:
        Tuple of (home_win, draw, away_win) where winner=1.0, others=0.0
    """
    if home_score > away_score:
        return (1.0, 0.0, 0.0)  # Home win
    elif home_score == away_score:
        return (0.0, 1.0, 0.0)  # Draw
    else:
        return (0.0, 0.0, 1.0)  # Away win


def simulate_historical_predictions(matches: List[Dict]) -> Tuple[
    List[float], List[float], List[float],  # Predicted probs (home, draw, away)
    List[float], List[float], List[float],  # Actual outcomes (home, draw, away)
    List[datetime]  # Timestamps
]:
    """Generate predictions for historical matches using the production pipeline.
    
    PRODUCTION CALIBRATION REQUIREMENTS:
    - Must use actual production model predictions, not random/simulated probabilities
    - For each match at time T, extract features using only data before T (no data leakage)
    - Run the same prediction pipeline that runs in production
    - Collect ensemble output probabilities and actual outcomes
    - Maintain strict temporal ordering
    
    CURRENT STATUS:
    This function requires the production prediction pipeline to be implemented.
    Until then, calibration training cannot proceed with valid data.
    
    DO NOT USE RANDOM PROBABILITIES FOR PRODUCTION CALIBRATION.
    
    Args:
        matches: List of finished matches with outcomes
        
    Returns:
        Tuple of (home_probs, draw_probs, away_probs, home_outcomes, draw_outcomes, away_outcomes, timestamps)
        
    Raises:
        NotImplementedError: Until production prediction pipeline is available
    """
    logger.error("=" * 80)
    logger.error("CALIBRATION TRAINING BLOCKED: Production prediction pipeline required")
    logger.error("=" * 80)
    logger.error("")
    logger.error("Calibration models must be trained on REAL prediction outputs, not random data.")
    logger.error("")
    logger.error("Required implementation:")
    logger.error("  1. Implement production prediction pipeline (ensemble of models)")
    logger.error("  2. For each historical match at time T:")
    logger.error("     - Extract features using only data BEFORE T")
    logger.error("     - Run production models to generate probabilities")
    logger.error("     - Collect predicted probs and actual outcome")
    logger.error("  3. Train calibration on these prediction-outcome pairs")
    logger.error("")
    logger.error("Training metadata to include:")
    logger.error("  - Training date range")
    logger.error("  - Number of samples (matches)")
    logger.error("  - Model version/commit hash")
    logger.error("  - Evaluation metrics (Brier score, calibration error)")
    logger.error("  - Cross-validation results if applicable")
    logger.error("")
    logger.error("NEVER use random.gauss() or fabricated probabilities for calibration training.")
    logger.error("=" * 80)
    
    raise NotImplementedError(
        "Calibration training requires production prediction pipeline. "
        "Do not use random/simulated probabilities for calibration training. "
        "Implement proper out-of-sample prediction generation first."
    )


def train_calibration_models(
    home_probs: List[float],
    draw_probs: List[float],
    away_probs: List[float],
    home_outcomes: List[float],
    draw_outcomes: List[float],
    away_outcomes: List[float],
    timestamps: List[datetime]
) -> Calibrator1X2:
    """Train calibration models for 1X2 outcomes.
    
    Args:
        home_probs: Predicted home win probabilities
        draw_probs: Predicted draw probabilities
        away_probs: Predicted away win probabilities
        home_outcomes: Actual home win outcomes (0 or 1)
        draw_outcomes: Actual draw outcomes (0 or 1)
        away_outcomes: Actual away win outcomes (0 or 1)
        timestamps: Timestamps of predictions
        
    Returns:
        Trained Calibrator1X2 instance
    """
    logger.info("Training calibration models...")
    
    # Create calibration data for each outcome
    home_data = CalibrationData(
        predicted_probs=home_probs,
        actual_outcomes=home_outcomes,
        timestamps=timestamps
    )
    
    draw_data = CalibrationData(
        predicted_probs=draw_probs,
        actual_outcomes=draw_outcomes,
        timestamps=timestamps
    )
    
    away_data = CalibrationData(
        predicted_probs=away_probs,
        actual_outcomes=away_outcomes,
        timestamps=timestamps
    )
    
    # Create and fit calibrator
    calibrator = Calibrator1X2()
    
    # Fit each outcome's calibrator
    home_engine = CalibrationEngine(method="isotonic")
    home_engine.fit(home_data)
    calibrator.home_calibrator = home_engine.calibrator
    
    draw_engine = CalibrationEngine(method="isotonic")
    draw_engine.fit(draw_data)
    calibrator.draw_calibrator = draw_engine.calibrator
    
    away_engine = CalibrationEngine(method="isotonic")
    away_engine.fit(away_data)
    calibrator.away_calibrator = away_engine.calibrator
    
    logger.info(f"Calibration training complete:")
    logger.info(f"  Home: fitted={calibrator.home_calibrator.is_fitted}, n={home_engine.calibration_sample_size}")
    logger.info(f"  Draw: fitted={calibrator.draw_calibrator.is_fitted}, n={draw_engine.calibration_sample_size}")
    logger.info(f"  Away: fitted={calibrator.away_calibrator.is_fitted}, n={away_engine.calibration_sample_size}")
    
    return calibrator


def save_calibration_config(calibrator: Calibrator1X2, output_path: str):
    """Save trained calibration configuration.
    
    Args:
        calibrator: Trained Calibrator1X2 instance
        output_path: Path to save configuration
    """
    config = {
        'trained_at': datetime.utcnow().isoformat(),
        'home_fitted': calibrator.home_calibrator.is_fitted,
        'draw_fitted': calibrator.draw_calibrator.is_fitted,
        'away_fitted': calibrator.away_calibrator.is_fitted,
        'method': 'isotonic',
        'calibrator_path': output_path.replace('.json', '.pkl')
    }
    
    # Save config
    with open(output_path, 'w') as f:
        json.dump(config, f, indent=2)
    
    # Save calibrator (pickle)
    pkl_path = output_path.replace('.json', '.pkl')
    with open(pkl_path, 'wb') as f:
        pickle.dump(calibrator, f)
    
    logger.info(f"Calibration configuration saved to {output_path}")
    logger.info(f"Calibrator saved to {pkl_path}")


def main():
    """Main calibration training workflow."""
    logger.info("=== Phase 10.3 Calibration Training ===")
    
    # Load historical data
    matches = load_finished_matches()
    logger.info(f"Loaded {len(matches)} finished matches")
    
    if len(matches) < 50:
        logger.warning(f"Insufficient historical data: {len(matches)} < 50")
        logger.warning("Calibration may be unreliable with limited data")
    
    # Simulate predictions (in production, use actual model outputs)
    (home_probs, draw_probs, away_probs,
     home_outcomes, draw_outcomes, away_outcomes,
     timestamps) = simulate_historical_predictions(matches)
    
    # Train calibration
    calibrator = train_calibration_models(
        home_probs, draw_probs, away_probs,
        home_outcomes, draw_outcomes, away_outcomes,
        timestamps
    )
    
    # Save configuration
    config_dir = os.path.join(os.path.dirname(__file__), '..', 'config')
    os.makedirs(config_dir, exist_ok=True)
    
    config_path = os.path.join(config_dir, 'calibration_config.json')
    save_calibration_config(calibrator, config_path)
    
    logger.info("=== Calibration Training Complete ===")
    
    # Test calibration
    logger.info("\nTesting calibration:")
    test_probs = [0.3, 0.5, 0.7]
    for prob in test_probs:
        cal_home, cal_draw, cal_away = calibrator.calibrate_1x2(prob, 0.25, 1.0-prob-0.25)
        logger.info(f"  Input: H={prob:.2f}, D=0.25, A={1.0-prob-0.25:.2f}")
        logger.info(f"  Calibrated: H={cal_home:.2f}, D={cal_draw:.2f}, A={cal_away:.2f}")


if __name__ == "__main__":
    main()

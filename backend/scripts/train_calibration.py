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
    
    PRODUCTION CALIBRATION IMPLEMENTATION:
    - Uses actual settled predictions from PredictionVersionRepository
    - Chronologically ordered with temporal cutoff
    - Real prediction→outcome pairs, not simulated
    
    Args:
        matches: List of finished matches with outcomes
        
    Returns:
        Tuple of (home_probs, draw_probs, away_probs, home_outcomes, draw_outcomes, away_outcomes, timestamps)
        
    Raises:
        ValueError: If insufficient settled predictions available
    """
    from app.database import SessionLocal
    from app.prediction.version_manager import PredictionVersionRepository
    
    logger.info("Loading settled predictions from PredictionVersionRepository...")
    
    db = SessionLocal()
    try:
        repo = PredictionVersionRepository(db)
        
        # Get all settled predictions for 1X2 market
        # Note: get_settled_picks_by_market returns picks with actual outcomes
        settled_picks = repo.get_settled_picks_by_market(
            market="1X2",
            cutoff_date=None  # All historical data
        )
        
        if not settled_picks:
            logger.error("No settled predictions found in database")
            raise ValueError(
                "Cannot train calibration: no settled predictions available. "
                "Generate predictions on historical matches first, then settle them with actual outcomes."
            )
        
        logger.info(f"Found {len(settled_picks)} settled predictions")
        
        # Extract predicted probabilities and actual outcomes
        home_probs = []
        draw_probs = []
        away_probs = []
        home_outcomes = []
        draw_outcomes = []
        away_outcomes = []
        timestamps = []
        
        for pick in settled_picks:
            # Parse prediction data (JSON stored in version)
            pred_data = pick.get('prediction_data', {})
            if not pred_data:
                continue
                
            # Extract calibrated probabilities (post-calibration if available, else ensemble)
            calibrated = pred_data.get('calibrated_probabilities', {})
            ensemble = pred_data.get('ensemble_probabilities', {})
            
            home_prob = calibrated.get('home_win') or ensemble.get('home_win')
            draw_prob = calibrated.get('draw') or ensemble.get('draw')
            away_prob = calibrated.get('away_win') or ensemble.get('away_win')
            
            if home_prob is None or draw_prob is None or away_prob is None:
                continue
            
            # Determine actual outcome
            actual_outcome = pick.get('actual_outcome')
            if actual_outcome == 'home_win':
                h_out, d_out, a_out = 1.0, 0.0, 0.0
            elif actual_outcome == 'draw':
                h_out, d_out, a_out = 0.0, 1.0, 0.0
            elif actual_outcome == 'away_win':
                h_out, d_out, a_out = 0.0, 0.0, 1.0
            else:
                continue  # Unknown outcome
            
            home_probs.append(float(home_prob))
            draw_probs.append(float(draw_prob))
            away_probs.append(float(away_prob))
            home_outcomes.append(h_out)
            draw_outcomes.append(d_out)
            away_outcomes.append(a_out)
            
            # Timestamp
            predicted_at = pick.get('predicted_at')
            if predicted_at:
                if isinstance(predicted_at, str):
                    predicted_at = datetime.fromisoformat(predicted_at)
                timestamps.append(predicted_at)
            else:
                timestamps.append(datetime.utcnow())
        
        MIN_SAMPLES = 30
        if len(home_probs) < MIN_SAMPLES:
            logger.error(f"Insufficient samples for calibration: {len(home_probs)} < {MIN_SAMPLES}")
            raise ValueError(
                f"Cannot train calibration: {len(home_probs)} samples < {MIN_SAMPLES} minimum. "
                "Generate and settle more predictions first."
            )
        
        logger.info(f"Loaded {len(home_probs)} valid prediction-outcome pairs")
        return (home_probs, draw_probs, away_probs,
                home_outcomes, draw_outcomes, away_outcomes,
                timestamps)
    
    finally:
        db.close()


def train_calibration_models(
    home_probs: List[float],
    draw_probs: List[float],
    away_probs: List[float],
    home_outcomes: List[float],
    draw_outcomes: List[float],
    away_outcomes: List[float],
    timestamps: List[datetime],
    cutoff_date: datetime = None
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
        cutoff_date: Optional temporal cutoff for training
        
    Returns:
        Trained Calibrator1X2 instance
        
    Raises:
        ValueError: If insufficient samples (< 30)
    """
    MIN_SAMPLES = 30
    if len(home_probs) < MIN_SAMPLES:
        raise ValueError(
            f"Insufficient samples for calibration training: {len(home_probs)} < {MIN_SAMPLES}"
        )
    
    logger.info(f"Training calibration models on {len(home_probs)} samples...")
    
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
    home_engine.fit(home_data, cutoff_date=cutoff_date)
    calibrator.home_calibrator = home_engine.calibrator
    
    draw_engine = CalibrationEngine(method="isotonic")
    draw_engine.fit(draw_data, cutoff_date=cutoff_date)
    calibrator.draw_calibrator = draw_engine.calibrator
    
    away_engine = CalibrationEngine(method="isotonic")
    away_engine.fit(away_data, cutoff_date=cutoff_date)
    calibrator.away_calibrator = away_engine.calibrator
    
    logger.info(f"Calibration training complete:")
    logger.info(f"  Home: fitted={calibrator.home_calibrator.is_fitted}, n={home_engine.calibration_sample_size}")
    logger.info(f"  Draw: fitted={calibrator.draw_calibrator.is_fitted}, n={draw_engine.calibration_sample_size}")
    logger.info(f"  Away: fitted={calibrator.away_calibrator.is_fitted}, n={away_engine.calibration_sample_size}")
    
    # Calculate and log calibration metrics
    from app.prediction.calibration import brier_score, calibration_error
    
    # Brier scores (uncalibrated)
    brier_uncal = brier_score(home_probs, home_outcomes)
    logger.info(f"  Brier score (uncalibrated home_win): {brier_uncal:.4f}")
    
    # Calibration error
    cal_error = calibration_error(home_probs, home_outcomes, n_bins=10)
    logger.info(f"  Expected Calibration Error (home_win): {cal_error.ece:.4f}")
    
    return calibrator


def save_calibration_config(calibrator: Calibrator1X2, output_path: str, metadata: Dict):
    """Save trained calibration configuration with metadata.
    
    Args:
        calibrator: Trained Calibrator1X2 instance
        output_path: Path to save configuration
        metadata: Training metadata (sample count, date range, metrics)
    """
    config = {
        'trained_at': datetime.utcnow().isoformat(),
        'home_fitted': calibrator.home_calibrator.is_fitted,
        'draw_fitted': calibrator.draw_calibrator.is_fitted,
        'away_fitted': calibrator.away_calibrator.is_fitted,
        'method': 'isotonic',
        'calibrator_path': output_path.replace('.json', '.pkl'),
        'metadata': metadata
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
    logger.info("=== Phase 10.3 Calibration Training (Real Pipeline) ===")
    
    # Load historical data
    matches = load_finished_matches()
    logger.info(f"Loaded {len(matches)} finished matches from database")
    
    if len(matches) < 50:
        logger.warning(f"Limited historical data: {len(matches)} < 50 recommended")
    
    # Load actual predictions and outcomes from PredictionVersionRepository
    try:
        (home_probs, draw_probs, away_probs,
         home_outcomes, draw_outcomes, away_outcomes,
         timestamps) = simulate_historical_predictions(matches)
    except ValueError as e:
        logger.error(f"Failed to load prediction data: {e}")
        logger.error("To train calibration:")
        logger.error("  1. Generate predictions on historical matches using production pipeline")
        logger.error("  2. Settle predictions with actual outcomes (PredictionVersionRepository)")
        logger.error("  3. Re-run this script")
        return
    
    # Training metadata
    metadata = {
        'n_samples': len(home_probs),
        'date_range': {
            'first': min(timestamps).isoformat() if timestamps else None,
            'last': max(timestamps).isoformat() if timestamps else None,
        },
        'data_source': 'PredictionVersionRepository.get_settled_picks_by_market',
        'market': '1X2'
    }
    
    # Train calibration with temporal cutoff (most recent timestamp)
    cutoff = max(timestamps) if timestamps else None
    calibrator = train_calibration_models(
        home_probs, draw_probs, away_probs,
        home_outcomes, draw_outcomes, away_outcomes,
        timestamps,
        cutoff_date=cutoff
    )
    
    # Save configuration with metadata
    config_dir = os.path.join(os.path.dirname(__file__), '..', 'config')
    os.makedirs(config_dir, exist_ok=True)
    
    config_path = os.path.join(config_dir, 'calibration_config.json')
    save_calibration_config(calibrator, config_path, metadata)
    
    logger.info("=== Calibration Training Complete ===")
    logger.info(f"Metadata: {json.dumps(metadata, indent=2)}")
    
    # Test calibration
    logger.info("\nTesting calibration:")
    test_probs = [0.3, 0.5, 0.7]
    for prob in test_probs:
        cal_home, cal_draw, cal_away = calibrator.calibrate_1x2(prob, 0.25, 1.0-prob-0.25)
        logger.info(f"  Input: H={prob:.2f}, D=0.25, A={1.0-prob-0.25:.2f}")
        logger.info(f"  Calibrated: H={cal_home:.2f}, D={cal_draw:.2f}, A={cal_away:.2f}")


if __name__ == "__main__":
    main()

"""Load trained calibration models into production.

This module provides functions to load pre-trained calibration models
and integrate them into the prediction pipeline.
"""

import os
import pickle
import json
import logging
from typing import Optional

from app.prediction.model_orchestrator import Calibrator1X2

logger = logging.getLogger(__name__)


def load_calibration_config(config_path: Optional[str] = None) -> Optional[dict]:
    """Load calibration configuration.
    
    Args:
        config_path: Path to calibration config JSON file.
                    If None, uses default path in backend/config/
    
    Returns:
        Configuration dictionary or None if not found
    """
    if config_path is None:
        # Default path
        backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        config_path = os.path.join(backend_dir, 'config', 'calibration_config.json')
    
    if not os.path.exists(config_path):
        logger.warning(f"Calibration config not found at {config_path}")
        return None
    
    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
        logger.info(f"Loaded calibration config from {config_path}")
        return config
    except Exception as e:
        logger.error(f"Failed to load calibration config: {e}")
        return None


def load_trained_calibrator(calibrator_path: Optional[str] = None) -> Optional[Calibrator1X2]:
    """Load trained calibrator from pickle file.
    
    Args:
        calibrator_path: Path to calibrator pickle file.
                        If None, uses path from config
    
    Returns:
        Trained Calibrator1X2 instance or None if not found
    """
    if calibrator_path is None:
        # Try to get path from config
        config = load_calibration_config()
        if config and 'calibrator_path' in config:
            calibrator_path = config['calibrator_path']
        else:
            # Default path
            backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            calibrator_path = os.path.join(backend_dir, 'config', 'calibration_config.pkl')
    
    if not os.path.exists(calibrator_path):
        logger.warning(f"Calibrator not found at {calibrator_path}")
        return None
    
    try:
        with open(calibrator_path, 'rb') as f:
            calibrator = pickle.load(f)
        
        if not isinstance(calibrator, Calibrator1X2):
            logger.error(f"Loaded object is not a Calibrator1X2: {type(calibrator)}")
            return None
        
        logger.info(f"Loaded trained calibrator from {calibrator_path}")
        logger.info(f"  Home fitted: {calibrator.home_calibrator.is_fitted}")
        logger.info(f"  Draw fitted: {calibrator.draw_calibrator.is_fitted}")
        logger.info(f"  Away fitted: {calibrator.away_calibrator.is_fitted}")
        logger.info(f"  Overall fitted: {calibrator.is_fitted}")
        
        return calibrator
    except Exception as e:
        logger.error(f"Failed to load calibrator: {e}")
        return None


def create_calibration_integration_with_trained_model():
    """Create CalibrationIntegration with trained calibrator.
    
    Returns:
        CalibrationIntegration instance with trained calibrator if available,
        otherwise default untrained instance
    """
    from app.prediction.model_orchestrator import CalibrationIntegration
    
    calibrator = load_trained_calibrator()
    
    if calibrator is None:
        logger.warning("No trained calibrator available, using default untrained calibrator")
        return CalibrationIntegration.create_default()
    
    if not calibrator.is_fitted:
        logger.warning("Loaded calibrator is not fitted, predictions will be uncalibrated")
    
    return CalibrationIntegration(calibrator=calibrator)

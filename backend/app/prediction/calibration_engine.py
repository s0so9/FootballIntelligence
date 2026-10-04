"""Calibration engine using isotonic regression.

This module implements probability calibration using isotonic regression
to adjust raw model probabilities based on historical performance.

Features:
- Isotonic regression calibration (sklearn)
- Platt calibration (logistic regression)
- Strict temporal cutoff enforcement (NO DATA LEAKAGE)
- Brier score and log loss tracking
- Minimum sample size requirements
- Returns uncalibrated probability with warning when not fitted
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional, Tuple
import warnings

# Optional sklearn import (graceful degradation if not available)
try:
    from sklearn.isotonic import IsotonicRegression
    from sklearn.linear_model import LogisticRegression
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False
    warnings.warn(
        "sklearn not available. CalibrationEngine will return uncalibrated probabilities."
    )


@dataclass
class CalibrationData:
    """Historical prediction data for calibration."""
    
    predicted_probs: List[float]
    """Predicted probabilities [0, 1]"""
    
    actual_outcomes: List[float]
    """Actual outcomes (0.0 or 1.0)"""
    
    timestamps: List[datetime]
    """Timestamps of predictions"""
    
    def __len__(self) -> int:
        return len(self.predicted_probs)
    
    def validate(self) -> None:
        """Validate data consistency."""
        if not (len(self.predicted_probs) == len(self.actual_outcomes) == len(self.timestamps)):
            raise ValueError(
                f"Length mismatch: probs={len(self.predicted_probs)}, "
                f"outcomes={len(self.actual_outcomes)}, times={len(self.timestamps)}"
            )
        
        for prob in self.predicted_probs:
            if not (0.0 <= prob <= 1.0):
                raise ValueError(f"Probability must be in [0, 1], got {prob}")
        
        for outcome in self.actual_outcomes:
            if outcome not in (0.0, 1.0):
                raise ValueError(f"Outcome must be 0.0 or 1.0, got {outcome}")


@dataclass
class CalibrationMetrics:
    """Calibration performance metrics."""
    
    brier_score: float
    """Brier score (lower is better)"""
    
    log_loss: float
    """Log loss (lower is better)"""
    
    n_samples: int
    """Number of samples used"""
    
    is_reliable: bool
    """Whether sample size is sufficient"""


class IsotonicCalibration:
    """Isotonic regression calibration.
    
    Uses sklearn's IsotonicRegression to fit a monotonic mapping
    from predicted probabilities to calibrated probabilities.
    """
    
    MIN_SAMPLES = 50
    
    def __init__(self):
        self.calibrator: Optional[IsotonicRegression] = None
        self.is_fitted_: bool = False
        self.n_training_samples: int = 0
    
    @property
    def is_fitted(self) -> bool:
        """Whether calibrator has been fitted."""
        return self.is_fitted_
    
    def fit(self, data: CalibrationData) -> None:
        """Fit isotonic regression calibrator.
        
        Args:
            data: Historical calibration data
            
        Raises:
            ValueError: If insufficient data or sklearn not available
        """
        if not SKLEARN_AVAILABLE:
            warnings.warn("sklearn not available, calibration disabled")
            return
        
        data.validate()
        
        if len(data) < self.MIN_SAMPLES:
            warnings.warn(
                f"Insufficient data for calibration: {len(data)} < {self.MIN_SAMPLES}. "
                "Calibrator will not be fitted."
            )
            return
        
        # Fit isotonic regression
        self.calibrator = IsotonicRegression(out_of_bounds="clip")
        self.calibrator.fit(data.predicted_probs, data.actual_outcomes)
        self.is_fitted_ = True
        self.n_training_samples = len(data)
    
    def calibrate(self, prob: float) -> float:
        """Calibrate a single probability.
        
        Args:
            prob: Raw probability [0, 1]
            
        Returns:
            Calibrated probability [0, 1]
        """
        if not self.is_fitted_:
            warnings.warn("Calibrator not fitted, returning uncalibrated probability")
            return prob
        
        if not (0.0 <= prob <= 1.0):
            warnings.warn(f"Probability {prob} outside [0,1], clipping")
            prob = max(0.0, min(1.0, prob))
        
        # sklearn calibrator expects array-like
        calibrated = self.calibrator.predict([prob])[0]
        return float(calibrated)


class PlattCalibration:
    """Platt calibration using logistic regression.
    
    Fits a logistic regression model to map predicted probabilities
    to calibrated probabilities.
    """
    
    MIN_SAMPLES = 50
    
    def __init__(self):
        self.calibrator: Optional[LogisticRegression] = None
        self.is_fitted_: bool = False
        self.n_training_samples: int = 0
    
    @property
    def is_fitted(self) -> bool:
        """Whether calibrator has been fitted."""
        return self.is_fitted_
    
    def fit(self, data: CalibrationData) -> None:
        """Fit Platt calibrator.
        
        Args:
            data: Historical calibration data
            
        Raises:
            ValueError: If insufficient data or sklearn not available
        """
        if not SKLEARN_AVAILABLE:
            warnings.warn("sklearn not available, calibration disabled")
            return
        
        data.validate()
        
        if len(data) < self.MIN_SAMPLES:
            warnings.warn(
                f"Insufficient data for calibration: {len(data)} < {self.MIN_SAMPLES}. "
                "Calibrator will not be fitted."
            )
            return
        
        # Fit logistic regression
        import numpy as np
        X = np.array(data.predicted_probs).reshape(-1, 1)
        y = np.array(data.actual_outcomes)
        
        self.calibrator = LogisticRegression()
        self.calibrator.fit(X, y)
        self.is_fitted_ = True
        self.n_training_samples = len(data)
    
    def calibrate(self, prob: float) -> float:
        """Calibrate a single probability.
        
        Args:
            prob: Raw probability [0, 1]
            
        Returns:
            Calibrated probability [0, 1]
        """
        if not self.is_fitted_:
            warnings.warn("Calibrator not fitted, returning uncalibrated probability")
            return prob
        
        if not (0.0 <= prob <= 1.0):
            warnings.warn(f"Probability {prob} outside [0,1], clipping")
            prob = max(0.0, min(1.0, prob))
        
        # sklearn calibrator expects array-like
        import numpy as np
        X = np.array([[prob]])
        calibrated = self.calibrator.predict_proba(X)[0][1]
        return float(calibrated)


class CalibrationEngine:
    """Main calibration engine.
    
    Manages calibration fitting, application, and metrics tracking.
    Enforces strict temporal cutoff to prevent data leakage.
    """
    
    def __init__(self, method: str = "isotonic"):
        """Initialize calibration engine.
        
        Args:
            method: Calibration method ("isotonic" or "platt")
        """
        if method not in ("isotonic", "platt"):
            raise ValueError(f"Unknown calibration method: {method}")
        
        self.method = method
        if method == "isotonic":
            self.calibrator = IsotonicCalibration()
        else:
            self.calibrator = PlattCalibration()
        
        self.metrics: Optional[CalibrationMetrics] = None
    
    @property
    def is_fitted(self) -> bool:
        """Whether engine has been fitted."""
        return self.calibrator.is_fitted
    
    def fit(
        self,
        data: CalibrationData,
        cutoff_date: Optional[datetime] = None
    ) -> None:
        """Fit calibration model with strict temporal cutoff.
        
        Args:
            data: Historical prediction data
            cutoff_date: Only use data BEFORE this date (prevents leakage)
        """
        data.validate()
        
        # Apply temporal cutoff if specified
        if cutoff_date is not None:
            filtered_probs = []
            filtered_outcomes = []
            filtered_times = []
            
            for prob, outcome, ts in zip(
                data.predicted_probs, data.actual_outcomes, data.timestamps
            ):
                if ts < cutoff_date:
                    filtered_probs.append(prob)
                    filtered_outcomes.append(outcome)
                    filtered_times.append(ts)
            
            data = CalibrationData(
                predicted_probs=filtered_probs,
                actual_outcomes=filtered_outcomes,
                timestamps=filtered_times
            )
        
        # Fit calibrator
        self.calibrator.fit(data)
        
        # Calculate metrics if fitted
        if self.calibrator.is_fitted:
            self.metrics = self._calculate_metrics(data)
    
    def calibrate(self, prob: float) -> float:
        """Calibrate a probability.
        
        Args:
            prob: Raw probability [0, 1]
            
        Returns:
            Calibrated probability [0, 1]
        """
        if not self.is_fitted:
            warnings.warn("CalibrationEngine not fitted, returning uncalibrated probability")
            return prob
        
        return self.calibrator.calibrate(prob)
    
    def _calculate_metrics(self, data: CalibrationData) -> CalibrationMetrics:
        """Calculate calibration metrics.
        
        Args:
            data: Calibration data
            
        Returns:
            CalibrationMetrics
        """
        # Calculate Brier score
        brier_sum = 0.0
        log_loss_sum = 0.0
        eps = 1e-15  # Epsilon to avoid log(0)
        
        for prob, outcome in zip(data.predicted_probs, data.actual_outcomes):
            # Brier score component
            brier_sum += (prob - outcome) ** 2
            
            # Log loss component
            prob_clipped = max(eps, min(1.0 - eps, prob))
            if outcome == 1.0:
                log_loss_sum -= math.log(prob_clipped)
            else:
                log_loss_sum -= math.log(1.0 - prob_clipped)
        
        n = len(data)
        brier_score = brier_sum / n if n > 0 else 0.0
        log_loss = log_loss_sum / n if n > 0 else 0.0
        
        return CalibrationMetrics(
            brier_score=brier_score,
            log_loss=log_loss,
            n_samples=n,
            is_reliable=(n >= self.calibrator.MIN_SAMPLES)
        )

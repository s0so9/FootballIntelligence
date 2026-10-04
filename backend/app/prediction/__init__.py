"""Prediction module.

This module provides prediction models and services for football match prediction.
"""

from app.prediction.poisson import PoissonModel, PoissonPrediction
from app.prediction.elo import (
    EloCalculator,
    EloMatchResult,
    EloPrediction,
    EloRatingState,
    EloRatingSystem,
)
from app.prediction.dixon_coles import (
    DixonColesAdjustment,
    DixonColesPrediction,
    DixonColesModel,
)
from app.prediction.calibration import (
    BinaryCalibrationResult,
    BrierScoreResult,
    CalibrationErrorResult,
    IsotonicScaler,
    LogLossResult,
    Multiclass1X2CalibrationResult,
    PlattScaler,
    ReliabilityBin,
    ReliabilityData,
    brier_score,
    calibration_error,
    evaluate_1x2,
    evaluate_binary,
    log_loss_binary,
    log_loss_multiclass,
    reliability_data,
)
from app.prediction.ensemble import (
    EnsembleModel,
    EnsemblePrediction,
    ModelContribution,
    ModelPredictionInput,
)
from app.prediction.service import PredictionService

__all__ = [
    # Poisson
    "PoissonModel",
    "PoissonPrediction",
    # Elo
    "EloCalculator",
    "EloMatchResult",
    "EloPrediction",
    "EloRatingState",
    "EloRatingSystem",
    # Dixon-Coles
    "DixonColesAdjustment",
    "DixonColesPrediction",
    "DixonColesModel",
    # Ensemble
    "EnsembleModel",
    "EnsemblePrediction",
    "ModelContribution",
    "ModelPredictionInput",
    # Calibration
    "BinaryCalibrationResult",
    "BrierScoreResult",
    "CalibrationErrorResult",
    "IsotonicScaler",
    "LogLossResult",
    "Multiclass1X2CalibrationResult",
    "PlattScaler",
    "ReliabilityBin",
    "ReliabilityData",
    "brier_score",
    "calibration_error",
    "evaluate_1x2",
    "evaluate_binary",
    "log_loss_binary",
    "log_loss_multiclass",
    "reliability_data",
    # Service
    "PredictionService",
]

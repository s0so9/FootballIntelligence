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
from app.prediction.negative_binomial import (
    NegativeBinomialModel,
    NegativeBinomialPrediction,
)
from app.prediction.logistic_regression import (
    LogisticRegressionModel,
    LogisticRegressionPrediction,
    TrainingStats,
)
from app.prediction.ensemble import (
    EnsembleModel,
    EnsemblePrediction,
    ModelContribution,
    ModelPredictionInput,
)
from app.prediction.backtest import (
    BacktestAggregator,
    BacktestMetrics,
    BacktestResult,
    BacktestRunner,
    ChronologicalSplitter,
    PredictionRecord,
    WindowSplit,
    run_backtest,
    poisson_predict_fn,
    negative_binomial_predict_fn,
    elo_predict_fn,
    logistic_regression_predict_fn,
)
from app.prediction.comparison import (
    ComparisonResult,
    MetricComparison,
    ModelComparator,
    ModelMetricSnapshot,
    ModelRanking,
    RankingMetric,
    snapshot_from_backtest_metrics,
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
    # Negative Binomial
    "NegativeBinomialModel",
    "NegativeBinomialPrediction",
    # Logistic Regression
    "LogisticRegressionModel",
    "LogisticRegressionPrediction",
    "TrainingStats",
    # Backtest
    "BacktestAggregator",
    "BacktestMetrics",
    "BacktestResult",
    "BacktestRunner",
    "ChronologicalSplitter",
    "PredictionRecord",
    "WindowSplit",
    "run_backtest",
    "poisson_predict_fn",
    "negative_binomial_predict_fn",
    "elo_predict_fn",
    "logistic_regression_predict_fn",
    # Comparison
    "ComparisonResult",
    "MetricComparison",
    "ModelComparator",
    "ModelMetricSnapshot",
    "ModelRanking",
    "RankingMetric",
    "snapshot_from_backtest_metrics",
]

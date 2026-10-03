"""Prediction module.

This module provides prediction models and services for football match prediction.
"""

from app.prediction.poisson import PoissonModel, PoissonPrediction
from app.prediction.service import PredictionService

__all__ = [
    "PoissonModel",
    "PoissonPrediction",
    "PredictionService",
]

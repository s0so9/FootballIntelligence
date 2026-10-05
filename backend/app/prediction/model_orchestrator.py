"""Model orchestration layer for running multiple prediction models.

This module coordinates execution of all available prediction models from a
MatchFeatureSnapshot, handles partial failures gracefully, and aggregates results.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Any
import logging

from app.prediction.interfaces import (
    PredictionModel,
    ModelPrediction,
    ModelAvailability,
)
from app.prediction.feature_snapshot import MatchFeatureSnapshot
from app.prediction.poisson import PoissonModel
from app.prediction.dixon_coles import DixonColesModel
from app.prediction.elo import EloModel
from app.prediction.monte_carlo import MonteCarloSimulation
from app.prediction.negative_binomial import NegativeBinomialModel
from app.prediction.form_adjusted import FormAdjustedModel
from app.prediction.logistic_regression import LogisticRegressionModel
from app.prediction.ensemble_engine import EnsembleEngine, ReliabilityWeights


logger = logging.getLogger(__name__)


class ModelStatus(str, Enum):
    """Status of model execution."""
    SUPPORTED_RUN = "supported_run"  # Model ran successfully
    UNAVAILABLE_MISSING_INPUTS = "unavailable_missing_inputs"  # Required data missing
    FAILED = "failed"  # Model execution failed with error


@dataclass
class ModelOutput:
    """Output from a single model execution.
    
    Wraps either successful prediction or failure/unavailability information.
    """
    
    # Model identification
    model_id: str
    model_version: str
    
    # Execution status
    status: ModelStatus
    
    # Prediction result (only if status == SUPPORTED_RUN)
    prediction: Optional[ModelPrediction] = None
    
    # Availability info (only if status == UNAVAILABLE_MISSING_INPUTS)
    availability: Optional[ModelAvailability] = None
    
    # Error info (only if status == FAILED)
    error_message: Optional[str] = None
    error_traceback: Optional[str] = None
    
    # Execution metadata
    execution_time_ms: Optional[float] = None
    warnings: List[str] = field(default_factory=list)
    diagnostics: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def is_successful(self) -> bool:
        """Check if model ran successfully."""
        return self.status == ModelStatus.SUPPORTED_RUN
    
    @property
    def is_unavailable(self) -> bool:
        """Check if model was unavailable due to missing inputs."""
        return self.status == ModelStatus.UNAVAILABLE_MISSING_INPUTS
    
    @property
    def is_failed(self) -> bool:
        """Check if model execution failed."""
        return self.status == ModelStatus.FAILED


@dataclass
class ModelOrchestrationResult:
    """Result of orchestrating multiple models."""
    
    # Model outputs
    successful_predictions: List[ModelOutput] = field(default_factory=list)
    unavailable_models: List[ModelOutput] = field(default_factory=list)
    failed_models: List[ModelOutput] = field(default_factory=list)
    
    # Metadata
    total_models: int = 0
    participating_model_ids: List[str] = field(default_factory=list)
    execution_metadata: Dict[str, Any] = field(default_factory=dict)
    orchestration_timestamp: datetime = field(default_factory=datetime.utcnow)
    
    @property
    def has_predictions(self) -> bool:
        """Check if at least one model produced a prediction."""
        return len(self.successful_predictions) > 0
    
    @property
    def success_rate(self) -> float:
        """Calculate proportion of successful models."""
        if self.total_models == 0:
            return 0.0
        return len(self.successful_predictions) / self.total_models
    
    def get_all_outputs(self) -> List[ModelOutput]:
        """Get all model outputs regardless of status."""
        return (
            self.successful_predictions +
            self.unavailable_models +
            self.failed_models
        )


class ModelOrchestrator:
    """Orchestrates execution of multiple prediction models.
    
    Responsibilities:
    1. Register and manage prediction models
    2. Execute all compatible models from a MatchFeatureSnapshot
    3. Handle partial failures gracefully (one model failure doesn't kill pipeline)
    4. Distinguish between unavailable inputs vs execution failures
    5. Collect diagnostics and warnings
    """
    
    def __init__(self):
        """Initialize model orchestrator."""
        self._models: Dict[str, PredictionModel] = {}
    
    def register_model(self, model: PredictionModel) -> None:
        """Register a prediction model.
        
        Args:
            model: PredictionModel instance to register
        """
        metadata = model.get_metadata()
        model_id = metadata.model_id
        
        if model_id in self._models:
            logger.warning(f"Overwriting existing model: {model_id}")
        
        self._models[model_id] = model
        logger.info(f"Registered model: {model_id} (version {metadata.version})")
    
    def run_all(
        self,
        snapshot: MatchFeatureSnapshot,
        match_context: Optional[Dict[str, Any]] = None,
    ) -> ModelOrchestrationResult:
        """Run all registered models on the feature snapshot.
        
        Models are executed independently. A failure in one model does not
        prevent execution of other models.
        
        Args:
            snapshot: MatchFeatureSnapshot with match features
            match_context: Additional context (lineups, injuries, etc.)
        
        Returns:
            ModelOrchestrationResult with all model outputs
        """
        result = ModelOrchestrationResult(
            total_models=len(self._models),
            execution_metadata={
                "snapshot_version": snapshot.snapshot_version,
                "match_id": snapshot.match_id,
            }
        )
        
        # Convert snapshot to feature dict for models
        features = snapshot.get_feature_dict()
        
        # Execute each model
        for model_id, model in self._models.items():
            output = self._run_single_model(
                model=model,
                features=features,
                match_context=match_context,
            )
            
            # Categorize output by status
            if output.is_successful:
                result.successful_predictions.append(output)
                result.participating_model_ids.append(model_id)
            elif output.is_unavailable:
                result.unavailable_models.append(output)
            elif output.is_failed:
                result.failed_models.append(output)
        
        logger.info(
            f"Orchestration complete: {len(result.successful_predictions)} successful, "
            f"{len(result.unavailable_models)} unavailable, "
            f"{len(result.failed_models)} failed"
        )
        
        return result
    
    def _run_single_model(
        self,
        model: PredictionModel,
        features: Dict[str, Optional[float]],
        match_context: Optional[Dict[str, Any]],
    ) -> ModelOutput:
        """Run a single model and wrap the result.
        
        Args:
            model: PredictionModel to execute
            features: Feature dictionary
            match_context: Additional context
        
        Returns:
            ModelOutput with execution result
        """
        metadata = model.get_metadata()
        start_time = datetime.now()
        
        try:
            # Check if model can run with available features
            requirements_met, missing = model.check_requirements(features)
            
            if not requirements_met:
                # Model cannot run due to missing inputs
                return ModelOutput(
                    model_id=metadata.model_id,
                    model_version=metadata.version,
                    status=ModelStatus.UNAVAILABLE_MISSING_INPUTS,
                    availability=ModelAvailability(
                        model_id=metadata.model_id,
                        available=False,
                        reason=f"Missing required features: {', '.join(missing)}",
                        missing_features=missing,
                    ),
                    diagnostics={
                        "required_features": metadata.required_features,
                        "missing_features": missing,
                    }
                )
            
            # Run model prediction
            result = model.predict(features=features, match_context=match_context)
            
            # Check result type
            if isinstance(result, ModelPrediction):
                # Successful prediction
                execution_time = (datetime.now() - start_time).total_seconds() * 1000
                
                return ModelOutput(
                    model_id=metadata.model_id,
                    model_version=metadata.version,
                    status=ModelStatus.SUPPORTED_RUN,
                    prediction=result,
                    execution_time_ms=execution_time,
                    diagnostics={
                        "confidence_score": result.confidence_score,
                        "data_quality_score": result.data_quality_score,
                    }
                )
            
            elif isinstance(result, ModelAvailability):
                # Model returned unavailability
                return ModelOutput(
                    model_id=metadata.model_id,
                    model_version=metadata.version,
                    status=ModelStatus.UNAVAILABLE_MISSING_INPUTS,
                    availability=result,
                    diagnostics={"reason": result.reason}
                )
            
            else:
                # Unexpected return type
                return ModelOutput(
                    model_id=metadata.model_id,
                    model_version=metadata.version,
                    status=ModelStatus.FAILED,
                    error_message=f"Unexpected return type: {type(result)}",
                )
        
        except Exception as e:
            # Model execution failed
            import traceback
            logger.error(f"Model {metadata.model_id} failed: {e}", exc_info=True)
            
            return ModelOutput(
                model_id=metadata.model_id,
                model_version=metadata.version,
                status=ModelStatus.FAILED,
                error_message=str(e),
                error_traceback=traceback.format_exc(),
            )
    
    def get_registered_models(self) -> List[str]:
        """Get list of registered model IDs.
        
        Returns:
            List of model IDs
        """
        return list(self._models.keys())
    
    @staticmethod
    def create_default_registry() -> "ModelOrchestrator":
        """Create orchestrator with all standard models registered.
        
        Returns:
            ModelOrchestrator with 7 models registered:
            - Poisson
            - Dixon-Coles
            - Elo
            - Monte Carlo
            - Negative Binomial
            - Form-Adjusted Poisson
            - Logistic Regression
        """
        orchestrator = ModelOrchestrator()
        
        # Register core statistical models
        poisson_model = PoissonModel()
        orchestrator.register_model(poisson_model)
        
        orchestrator.register_model(DixonColesModel(poisson_model=poisson_model))
        orchestrator.register_model(EloModel())
        orchestrator.register_model(MonteCarloSimulation())
        orchestrator.register_model(NegativeBinomialModel())
        
        # Register adjusted models
        orchestrator.register_model(FormAdjustedModel(base_model=poisson_model))
        
        # Register ML models
        orchestrator.register_model(LogisticRegressionModel())
        
        logger.info(f"Created default orchestrator with {len(orchestrator._models)} models")
        
        return orchestrator


class EnsembleIntegration:
    """Integration layer for ensemble prediction.
    
    Wires the canonical ensemble_engine.py into the model orchestration pipeline.
    """
    
    def __init__(self, engine: Optional[EnsembleEngine] = None):
        """Initialize ensemble integration.
        
        Args:
            engine: EnsembleEngine instance (defaults to ReliabilityWeights)
        """
        if engine is None:
            # Default to reliability-based weighting
            engine = EnsembleEngine(strategy=ReliabilityWeights())
        self.engine = engine
    
    def combine_predictions(
        self,
        orchestration_result: ModelOrchestrationResult,
        context: Optional[Dict[str, Any]] = None
    ) -> ModelPrediction | ModelAvailability:
        """Combine predictions from orchestration result.
        
        Args:
            orchestration_result: Result from ModelOrchestrator.run_all()
            context: Optional context (league_id, etc.)
            
        Returns:
            Combined ensemble prediction or ModelAvailability
        """
        # Extract successful predictions
        predictions = [
            output.prediction
            for output in orchestration_result.successful_predictions
            if output.prediction is not None
        ]
        
        if len(predictions) == 0:
            return ModelAvailability(
                model_id="ensemble_v1",
                available=False,
                reason="No successful model predictions available",
                missing_features=[]
            )
        
        # Use ensemble engine to combine
        result = self.engine.combine(predictions, context)
        
        # Log ensemble result
        if isinstance(result, ModelPrediction):
            agreement = result.metadata.get("model_agreement", 0.0)
            n_models = result.metadata.get("n_models", 0)
            logger.info(
                f"Ensemble combined {n_models} models with agreement={agreement:.3f}"
            )
        
        return result
    
    @staticmethod
    def create_default() -> "EnsembleIntegration":
        """Create ensemble integration with default reliability-based weighting.
        
        Returns:
            EnsembleIntegration with ReliabilityWeights strategy
        """
        return EnsembleIntegration()

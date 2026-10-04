"""Form-Adjusted Prediction Model.

Wraps any base PredictionModel and adjusts its predictions based on
opponent-adjusted recent form with time decay.

The adjustment modifies the base model's lambda parameters (expected goals)
according to team form scores.
"""

from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple

from app.prediction.interfaces import (
    PredictionModel,
    ModelPrediction,
    ModelAvailability,
    PredictionModelMetadata,
)
from app.domain.enums import ModelType


class FormAdjustedModel(PredictionModel):
    """Form-adjusted wrapper for any base prediction model.
    
    Applies opponent-adjusted form scores to modify base predictions.
    
    Algorithm:
    1. Base model generates prediction (lambda_home, lambda_away)
    2. Extract form scores from features (home_form_score, away_form_score in [-1, 1])
    3. Adjust lambdas: lambda_adjusted = lambda_base * (1 + form_weight * form_score)
    4. Regenerate prediction with adjusted lambdas
    
    Form score interpretation:
    - form_score = -1: very poor form (all losses) → reduce lambda by form_weight
    - form_score = 0: average form → no adjustment
    - form_score = +1: excellent form (all wins) → increase lambda by form_weight
    """
    
    MODEL_ID = "form_adjusted_v1"
    MODEL_VERSION = "1.0.0"
    
    def __init__(
        self,
        base_model: PredictionModel,
        form_weight: float = 0.15,
        min_matches_for_form: int = 5
    ):
        """Initialize form-adjusted model.
        
        Args:
            base_model: Base prediction model to wrap
            form_weight: Weight factor for form adjustment (default: 0.15)
                        Higher values = more form influence
                        Typical range: 0.1 to 0.3
            min_matches_for_form: Minimum matches required for form calculation
        """
        self.base_model = base_model
        self.form_weight = form_weight
        self.min_matches_for_form = min_matches_for_form
    
    def predict(
        self,
        features: Dict[str, Optional[float]],
        match_context: Optional[Dict[str, Any]] = None
    ) -> ModelPrediction | ModelAvailability:
        """Generate form-adjusted prediction.
        
        Args:
            features: Feature dictionary (must include form scores)
            match_context: Additional context
        
        Returns:
            ModelPrediction with form-adjusted probabilities or ModelAvailability
        """
        # Check requirements
        requirements_met, missing = self.check_requirements(features)
        if not requirements_met:
            return ModelAvailability(
                model_id=self.MODEL_ID,
                available=False,
                reason="insufficient_data",
                missing_features=missing
            )
        
        # Get base prediction
        base_prediction = self.base_model.predict(features, match_context)
        
        # If base model unavailable, propagate unavailability
        if isinstance(base_prediction, ModelAvailability):
            return ModelAvailability(
                model_id=self.MODEL_ID,
                available=False,
                reason=f"base_model_unavailable: {base_prediction.reason}",
                missing_features=base_prediction.missing_features
            )
        
        # Extract form scores
        home_form = features.get("home_form_score", 0.0)
        away_form = features.get("away_form_score", 0.0)
        
        # If form scores not available, return base prediction unchanged
        if home_form is None or away_form is None:
            return ModelPrediction(
                model_id=self.MODEL_ID,
                home_score_mean=base_prediction.home_score_mean,
                away_score_mean=base_prediction.away_score_mean,
                score_distribution=base_prediction.score_distribution,
                home_win_prob=base_prediction.home_win_prob,
                draw_prob=base_prediction.draw_prob,
                away_win_prob=base_prediction.away_win_prob,
                confidence_score=base_prediction.confidence_score * 0.9,  # Slightly lower confidence
                data_quality_score=base_prediction.data_quality_score,
                metadata={
                    "base_model_id": base_prediction.model_id,
                    "form_adjustment_applied": False,
                    "reason": "form_scores_unavailable"
                }
            )
        
        # Apply form adjustments to expected goals
        home_multiplier = 1.0 + (self.form_weight * home_form)
        away_multiplier = 1.0 + (self.form_weight * away_form)
        
        adjusted_home_lambda = base_prediction.home_score_mean * home_multiplier
        adjusted_away_lambda = base_prediction.away_score_mean * away_multiplier
        
        # Ensure non-negative lambdas
        adjusted_home_lambda = max(0.1, adjusted_home_lambda)
        adjusted_away_lambda = max(0.1, adjusted_away_lambda)
        
        # Recalculate score distribution with adjusted lambdas
        # Use Poisson distribution for simplicity
        adjusted_distribution = self._calculate_poisson_distribution(
            adjusted_home_lambda,
            adjusted_away_lambda,
            max_goals=10
        )
        
        # Calculate 1X2 probabilities from distribution
        home_win_prob = sum(
            prob for (h, a), prob in adjusted_distribution.items()
            if h > a
        )
        draw_prob = sum(
            prob for (h, a), prob in adjusted_distribution.items()
            if h == a
        )
        away_win_prob = sum(
            prob for (h, a), prob in adjusted_distribution.items()
            if h < a
        )
        
        # Normalize probabilities
        total = home_win_prob + draw_prob + away_win_prob
        if total > 0:
            home_win_prob /= total
            draw_prob /= total
            away_win_prob /= total
        
        # Calculate confidence: base confidence adjusted by form score reliability
        form_confidence = 1.0 - (abs(home_form - away_form) * 0.1)  # Less confident with extreme form differences
        adjusted_confidence = base_prediction.confidence_score * form_confidence
        
        return ModelPrediction(
            model_id=self.MODEL_ID,
            home_score_mean=adjusted_home_lambda,
            away_score_mean=adjusted_away_lambda,
            score_distribution=adjusted_distribution,
            home_win_prob=home_win_prob,
            draw_prob=draw_prob,
            away_win_prob=away_win_prob,
            confidence_score=adjusted_confidence,
            data_quality_score=base_prediction.data_quality_score,
            metadata={
                "base_model_id": base_prediction.model_id,
                "base_home_lambda": base_prediction.home_score_mean,
                "base_away_lambda": base_prediction.away_score_mean,
                "home_form_score": home_form,
                "away_form_score": away_form,
                "home_multiplier": home_multiplier,
                "away_multiplier": away_multiplier,
                "form_weight": self.form_weight,
                "form_adjustment_applied": True
            }
        )
    
    def _calculate_poisson_distribution(
        self,
        lambda_home: float,
        lambda_away: float,
        max_goals: int = 10
    ) -> Dict[Tuple[int, int], float]:
        """Calculate Poisson scoreline distribution.
        
        Args:
            lambda_home: Expected home goals
            lambda_away: Expected away goals
            max_goals: Maximum goals to consider
        
        Returns:
            Dict mapping (home_goals, away_goals) to probability
        """
        import math
        
        def poisson_pmf(k: int, lam: float) -> float:
            """Poisson probability mass function."""
            if lam <= 0:
                return 1.0 if k == 0 else 0.0
            return (lam ** k) * math.exp(-lam) / math.factorial(k)
        
        distribution = {}
        total_prob = 0.0
        
        for h in range(max_goals + 1):
            for a in range(max_goals + 1):
                prob = poisson_pmf(h, lambda_home) * poisson_pmf(a, lambda_away)
                distribution[(h, a)] = prob
                total_prob += prob
        
        # Normalize
        if total_prob > 0:
            distribution = {k: v / total_prob for k, v in distribution.items()}
        
        return distribution
    
    def get_metadata(self) -> PredictionModelMetadata:
        """Return model metadata.
        
        Returns:
            PredictionModelMetadata
        """
        base_metadata = self.base_model.get_metadata()
        
        return PredictionModelMetadata(
            model_id=self.MODEL_ID,
            model_type=ModelType.FORM_ADJUSTED,
            version=self.MODEL_VERSION,
            description=f"Form-adjusted wrapper for {base_metadata.model_id} with opponent-adjusted time-decayed form",
            required_features=base_metadata.required_features + [
                "home_form_score",
                "away_form_score"
            ],
            optional_features=base_metadata.optional_features + [
                "home_form_matches_used",
                "away_form_matches_used"
            ],
            min_samples_required=max(
                self.min_matches_for_form,
                base_metadata.min_samples_required
            )
        )
    
    def check_requirements(
        self,
        features: Dict[str, Optional[float]]
    ) -> Tuple[bool, List[str]]:
        """Check if required data is available.
        
        Args:
            features: Feature dictionary
        
        Returns:
            (requirements_met, missing_requirements)
        """
        missing = []
        
        # Check base model requirements
        base_met, base_missing = self.base_model.check_requirements(features)
        if not base_met:
            missing.extend(base_missing)
        
        # Check form score availability
        if features.get("home_form_score") is None:
            missing.append("home_form_score")
        if features.get("away_form_score") is None:
            missing.append("away_form_score")
        
        # Check sufficient matches for form calculation
        home_form_matches = features.get("home_form_matches_used", 0)
        away_form_matches = features.get("away_form_matches_used", 0)
        
        if home_form_matches < self.min_matches_for_form:
            missing.append(f"home_form_matches < {self.min_matches_for_form}")
        if away_form_matches < self.min_matches_for_form:
            missing.append(f"away_form_matches < {self.min_matches_for_form}")
        
        return len(missing) == 0, missing

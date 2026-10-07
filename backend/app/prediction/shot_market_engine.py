"""Shot market prediction engine.

This module calculates shot market probabilities using the existing ShotProductionCalculator
from the shot production feature engineering module.

Shot Markets Supported:
- Team shots (home/away separately)
- Team shots on target (home/away separately)
- Total shots (home + away combined)
- Total shots on target (home + away combined)

Thresholds:
- Team shots: 10+, 12+, 15+, 18+, 20+
- Team SOT: 3+, 4+, 5+, 6+
- Total shots: 20+, 22+, 25+, 30+
- Total SOT: 8+, 10+, 12+ (combined thresholds)

Distribution Selection:
- Poisson: When variance ≈ mean (equidispersed)
- Negative Binomial: When variance > mean (overdispersed)
- UNAVAILABLE: When insufficient data

Data Flow:
1. Extract shot data from MatchFeatureSnapshot
2. Use ShotProductionCalculator to fit distributions
3. Calculate P(X >= T) for each threshold
4. Return ShotMarketPrediction with probabilities and provenance
"""

from __future__ import annotations

from typing import Optional, Dict, List
from datetime import datetime

from app.prediction.interfaces import (
    ShotMarketType,
    ShotMarketPrediction,
    ShotMarketThreshold,
    DistributionType
)
from app.prediction.feature_snapshot import MatchFeatureSnapshot
from app.features.shot_production import ShotProductionCalculator, ShotProduction
from app.features.shot_intelligence import ShotIntelligenceCalculator


class ShotMarketEngine:
    """Calculate shot market probabilities using statistical distributions.
    
    Reuses ShotProductionCalculator from feature engineering infrastructure.
    """
    
    # Threshold definitions
    TEAM_SHOTS_THRESHOLDS = [10, 12, 15, 18, 20]
    SOT_THRESHOLDS = [3, 4, 5, 6]
    TOTAL_SHOTS_THRESHOLDS = [20, 22, 25, 30]
    TOTAL_SOT_THRESHOLDS = [8, 10, 12]
    
    def __init__(self, session, shot_production_calc: Optional[ShotProductionCalculator] = None):
        """Initialize shot market engine.
        
        Args:
            session: Database session
            shot_production_calc: Optional ShotProductionCalculator instance
        """
        self.session = session
        self.shot_calc = shot_production_calc or ShotProductionCalculator(session=session)
    
    def predict_all_shot_markets(
        self,
        snapshot: MatchFeatureSnapshot
    ) -> Dict[ShotMarketType, List[ShotMarketPrediction]]:
        """Predict all available shot markets for a match.
        
        Args:
            snapshot: Match feature snapshot
            
        Returns:
            Dictionary mapping market type to list of predictions (home, away, total)
        """
        results: Dict[ShotMarketType, List[ShotMarketPrediction]] = {}
        
        # Check if shot intelligence data is available in snapshot
        if not hasattr(snapshot, 'shot_intelligence') or snapshot.shot_intelligence is None:
            # Shot intelligence not available in this snapshot
            # Return empty dict - shot markets unavailable
            # This is expected behavior until MatchFeatureSnapshot includes shot intelligence
            return results
        
        # Placeholder: In full implementation, this would:
        # 1. Extract shot intelligence from snapshot
        # 2. Call ShotProductionCalculator for each team
        # 3. Build ShotMarketPrediction objects using _build_team_shots_prediction
        # 4. Return predictions
        
        # For now, return empty dict as shot intelligence integration is pending
        return results
    
    def _build_team_shots_prediction(
        self,
        team_id: str,
        shot_production: ShotProduction,
        market_type: ShotMarketType
    ) -> ShotMarketPrediction:
        """Build shot market prediction from ShotProduction result.
        
        Args:
            team_id: Team identifier
            shot_production: ShotProduction from calculator
            market_type: Market type
            
        Returns:
            ShotMarketPrediction
        """
        # Determine distribution type
        # Validate that ShotProductionCalculator actually populated the distribution model
        if shot_production.shots_distribution_model is None:
            # Distribution fitting was not performed or failed
            dist_type = DistributionType.UNAVAILABLE
            unavailability_reason = "distribution_not_fit"
        elif shot_production.shots_distribution_model == "poisson":
            dist_type = DistributionType.POISSON
            unavailability_reason = None
        elif shot_production.shots_distribution_model == "negative_binomial":
            dist_type = DistributionType.NEGATIVE_BINOMIAL
            unavailability_reason = None
        else:
            # Unknown distribution type
            dist_type = DistributionType.UNAVAILABLE
            unavailability_reason = "unknown_distribution_type"
        
        # Build thresholds
        thresholds: List[ShotMarketThreshold] = []
        
        if market_type == ShotMarketType.TEAM_SHOTS:
            threshold_probs = [
                (10, shot_production.over_10_shots_prob),
                (12, shot_production.over_12_shots_prob),
                (15, shot_production.over_15_shots_prob),
                (18, shot_production.over_18_shots_prob),
                (20, shot_production.over_20_shots_prob),
            ]
        elif market_type == ShotMarketType.TEAM_SHOTS_ON_TARGET:
            threshold_probs = [
                (3, shot_production.over_3_sot_prob),
                (4, shot_production.over_4_sot_prob),
                (5, shot_production.over_5_sot_prob),
                (6, shot_production.over_6_sot_prob),
            ]
        else:
            threshold_probs = []
        
        for threshold_val, prob in threshold_probs:
            if prob is not None:
                thresholds.append(ShotMarketThreshold(
                    threshold=threshold_val,
                    over_probability=prob,
                    distribution_model=dist_type,
                    expected_value=shot_production.expected_shots_mean,
                    variance=shot_production.expected_shots_variance,
                    data_quality=shot_production.data_quality_score
                ))
        
        # Check availability
        available = (dist_type != DistributionType.UNAVAILABLE and len(thresholds) > 0)
        # unavailability_reason already set above during distribution type determination
        if not available and unavailability_reason is None:
            unavailability_reason = "insufficient_shot_data"
        
        return ShotMarketPrediction(
            team_id=team_id,
            market_type=market_type,
            thresholds=thresholds,
            distribution_model=dist_type,
            expected_value=shot_production.expected_shots_mean,
            variance=shot_production.expected_shots_variance,
            available=available,
            unavailability_reason=unavailability_reason,
            sample_size=shot_production.sample_size,
            data_quality_score=shot_production.data_quality_score,
            model_id="shot_market_v1"
        )

"""Odds service for İddaa integration and value calculations.

Provides utilities for:
- Implied probability calculation
- Edge calculation (model prob - implied prob)
- Expected value calculation
- Temporal validation
- Odds normalization

Critical: Never fabricates odds. Returns None when unavailable.
"""

from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from enum import Enum


class OddsAvailability(str, Enum):
    """Odds availability status."""
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    STALE = "stale"
    FUTURE = "future"  # Odds timestamp is after prediction timestamp (leakage)


@dataclass
class MarketOdds:
    """Odds for a specific market selection."""
    
    market: str          # "OVER_0_5", "BTTS_YES", "HOME_WIN", etc.
    selection: str       # Human-readable selection
    odds: Optional[float]           # Decimal odds (None if unavailable)
    odds_timestamp: Optional[datetime]  # When odds were published
    provider: Optional[str]         # "iddaa", "development", etc.
    availability: OddsAvailability
    
    @property
    def implied_probability(self) -> Optional[float]:
        """Calculate implied probability from odds.
        
        Returns:
            Implied probability [0, 1] or None if odds unavailable
        """
        if self.odds is None or self.odds <= 0:
            return None
        return 1.0 / self.odds
    
    def calculate_edge(self, model_probability: float) -> Optional[float]:
        """Calculate probability edge.
        
        Edge = Model Probability - Implied Probability
        
        Positive edge suggests model sees value.
        Negative edge suggests overpriced market.
        
        Args:
            model_probability: Calibrated model probability [0, 1]
            
        Returns:
            Edge in probability points or None if odds unavailable
        """
        implied = self.implied_probability
        if implied is None:
            return None
        return model_probability - implied
    
    def calculate_expected_value(self, model_probability: float) -> Optional[float]:
        """Calculate expected value.
        
        EV = (Model Probability × Odds) - 1
        
        Positive EV suggests profitable bet in long run.
        
        Args:
            model_probability: Calibrated model probability [0, 1]
            
        Returns:
            Expected value (e.g., 0.08 = 8% EV) or None if odds unavailable
        """
        if self.odds is None or self.odds <= 0:
            return None
        return (model_probability * self.odds) - 1.0
    
    def is_valid_for_timestamp(self, prediction_timestamp: datetime) -> bool:
        """Validate odds are not from the future (temporal leakage check).
        
        Args:
            prediction_timestamp: When prediction is being made
            
        Returns:
            True if odds_timestamp <= prediction_timestamp
        """
        if self.odds_timestamp is None:
            # No timestamp = assume valid (conservative)
            return True
        
        return self.odds_timestamp <= prediction_timestamp


@dataclass
class ValueAssessment:
    """Value assessment for a market candidate."""
    
    market: str
    model_probability: float
    fair_odds: float
    
    # Bookmaker data
    bookmaker_odds: Optional[float]
    implied_probability: Optional[float]
    
    # Value metrics
    edge: Optional[float]              # Probability edge
    expected_value: Optional[float]    # EV percentage
    
    # Classification
    value_classification: str  # "STRONG_VALUE", "VALUE", "NEUTRAL", "NEGATIVE_VALUE", "NO_ODDS"
    value_score: float         # 0.0-1.0 score for use in selection
    
    @staticmethod
    def from_market_odds(
        market: str,
        model_probability: float,
        market_odds: Optional[MarketOdds]
    ) -> "ValueAssessment":
        """Create value assessment from market odds.
        
        Args:
            market: Market identifier
            model_probability: Calibrated model probability
            market_odds: MarketOdds or None
            
        Returns:
            ValueAssessment with calculated metrics
        """
        # Calculate fair odds
        fair_odds = 1.0 / model_probability if model_probability > 0 else 0.0
        
        # If no odds available
        if market_odds is None or market_odds.odds is None:
            return ValueAssessment(
                market=market,
                model_probability=model_probability,
                fair_odds=fair_odds,
                bookmaker_odds=None,
                implied_probability=None,
                edge=None,
                expected_value=None,
                value_classification="NO_ODDS",
                value_score=0.0  # No value contribution without odds
            )
        
        # Calculate value metrics
        implied_prob = market_odds.implied_probability
        edge = market_odds.calculate_edge(model_probability)
        expected_value = market_odds.calculate_expected_value(model_probability)
        
        # Classify value
        if expected_value >= 0.15:  # EV >= 15%
            value_classification = "STRONG_VALUE"
            value_score = 1.0
        elif expected_value >= 0.08:  # EV >= 8%
            value_classification = "VALUE"
            value_score = 0.7
        elif expected_value >= 0.03:  # EV >= 3%
            value_classification = "VALUE"
            value_score = 0.4
        elif expected_value >= 0.0:  # EV >= 0%
            value_classification = "NEUTRAL"
            value_score = 0.1
        else:  # Negative EV
            value_classification = "NEGATIVE_VALUE"
            value_score = 0.0
        
        return ValueAssessment(
            market=market,
            model_probability=model_probability,
            fair_odds=fair_odds,
            bookmaker_odds=market_odds.odds,
            implied_probability=implied_prob,
            edge=edge,
            expected_value=expected_value,
            value_classification=value_classification,
            value_score=value_score
        )


class OddsService:
    """Service for odds retrieval and value calculations."""
    
    @staticmethod
    def get_market_odds(
        odds_data: Optional[Dict[str, float]],
        market: str,
        provider: str = "unknown",
        odds_timestamp: Optional[datetime] = None
    ) -> Optional[MarketOdds]:
        """Get odds for a specific market.
        
        Args:
            odds_data: Dict mapping market -> odds (e.g., {"OVER_0_5": 1.05})
            market: Market identifier
            provider: Odds provider name
            odds_timestamp: When odds were published
            
        Returns:
            MarketOdds or None if unavailable
        """
        if odds_data is None or market not in odds_data:
            return MarketOdds(
                market=market,
                selection=market,
                odds=None,
                odds_timestamp=None,
                provider=None,
                availability=OddsAvailability.UNAVAILABLE
            )
        
        odds_value = odds_data[market]
        
        if odds_value is None or odds_value <= 0:
            return MarketOdds(
                market=market,
                selection=market,
                odds=None,
                odds_timestamp=odds_timestamp,
                provider=provider,
                availability=OddsAvailability.UNAVAILABLE
            )
        
        return MarketOdds(
            market=market,
            selection=market,
            odds=odds_value,
            odds_timestamp=odds_timestamp,
            provider=provider,
            availability=OddsAvailability.AVAILABLE
        )
    
    @staticmethod
    def calculate_value_contribution(
        value_assessment: ValueAssessment,
        use_conservative_thresholds: bool = True
    ) -> float:
        """Calculate value contribution to selection score.
        
        This replaces the old tiny edge bonus with meaningful value scoring.
        
        Args:
            value_assessment: ValueAssessment for the market
            use_conservative_thresholds: If True, requires higher EV for contribution
            
        Returns:
            Value contribution [0.0, 0.30] for selection score
        """
        if value_assessment.expected_value is None:
            # No odds = no value contribution
            return 0.0
        
        ev = value_assessment.expected_value
        
        if use_conservative_thresholds:
            # Conservative: require meaningful EV
            if ev >= 0.15:  # EV >= 15%
                return 0.30  # Maximum value contribution
            elif ev >= 0.08:  # EV >= 8%
                return 0.20
            elif ev >= 0.05:  # EV >= 5%
                return 0.12
            elif ev >= 0.03:  # EV >= 3%
                return 0.06
            else:
                return 0.0  # Insufficient value
        else:
            # Aggressive: accept lower EV
            if ev >= 0.08:
                return 0.30
            elif ev >= 0.05:
                return 0.20
            elif ev >= 0.03:
                return 0.12
            elif ev >= 0.01:
                return 0.06
            else:
                return 0.0
    
    @staticmethod
    def apply_high_base_rate_protection(
        market: str,
        probability: float,
        value_assessment: ValueAssessment,
        base_selection_score: float
    ) -> float:
        """Apply protection against trivial high base-rate markets.
        
        High base-rate markets (OVER_0.5, HOME_OR_AWAY) should not win by default.
        They need to show actual value to be selected.
        
        Args:
            market: Market identifier
            probability: Model probability
            value_assessment: Value assessment for this market
            base_selection_score: Selection score before protection
            
        Returns:
            Adjusted selection score (may be penalized)
        """
        # Define high base-rate markets
        HIGH_BASE_RATE_MARKETS = {
            'OVER_0_5',
            'HOME_OR_AWAY',
            'UNDER_6_5',  # Trivially likely
        }
        
        if market not in HIGH_BASE_RATE_MARKETS:
            # Not a high base-rate market
            return base_selection_score
        
        # High base-rate market: check if it has genuine value
        if value_assessment.expected_value is not None:
            ev = value_assessment.expected_value
            
            if ev >= 0.05:  # EV >= 5%
                # Good value, no penalty
                return base_selection_score
            elif ev >= 0.0:  # Positive but low EV
                # Moderate penalty
                return base_selection_score * 0.85
            else:  # Negative EV
                # Strong penalty
                return base_selection_score * 0.60
        else:
            # No odds available, moderate penalty for high base-rate
            # (We don't know if it has value, so penalize conservatively)
            return base_selection_score * 0.80
    
    @staticmethod
    def validate_temporal_boundary(
        odds_timestamp: Optional[datetime],
        prediction_timestamp: datetime
    ) -> bool:
        """Validate odds are not from the future (leakage check).
        
        Args:
            odds_timestamp: When odds were published
            prediction_timestamp: When prediction is being made
            
        Returns:
            True if valid (odds_timestamp <= prediction_timestamp)
        """
        if odds_timestamp is None:
            # No timestamp = cannot validate, assume valid (conservative)
            return True
        
        return odds_timestamp <= prediction_timestamp

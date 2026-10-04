"""Easy Match Detection System.

This module identifies matches where predictions have high confidence
based on multiple validated signals from the prediction system.

An "Easy Match" is defined by:
- Strong model consensus across multiple signals
- Sufficient data quality
- Statistical confidence thresholds
- Model agreement on outcome

This is NOT a subjective assessment. All scores are derived from
numerical calculations based on available statistical signals.

The Easy Match score ranges from 0-100 and is computed from:
- 1X2 probability confidence (dominant outcome probability)
- Over/Under confidence signals
- BTTS confidence
- Expected goals differential
- Data sufficiency indicators
- Model calibration quality (when available)

Missing or insufficient data results in explicit "unavailable" state.
The system never fabricates an Easy Match score.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional
import math


@dataclass
class EasyMatchSignal:
    """Individual signal contributing to Easy Match detection."""
    
    name: str
    """Signal name (e.g., '1x2_confidence', 'ou_confidence')."""
    
    value: float
    """Signal value (0-1 range typically)."""
    
    weight: float
    """Weight of this signal in overall score (0-1)."""
    
    available: bool = True
    """Whether this signal was available from data."""
    
    description: Optional[str] = None
    """Human-readable description of what this signal represents."""


@dataclass
class EasyMatchResult:
    """Result of Easy Match detection analysis.
    
    Combines multiple statistical signals to produce a confidence score
    indicating how "easy" a match is to predict based on available data.
    """
    
    match_id: str
    """Match identifier."""
    
    is_easy_match: bool
    """True if match exceeds Easy Match threshold."""
    
    confidence_score: float
    """Overall confidence score (0-100). 0 means insufficient data."""
    
    threshold: float
    """Threshold used for Easy Match determination."""
    
    signals: List[EasyMatchSignal]
    """Individual signals that contributed to the score."""
    
    dominant_outcome: Optional[str] = None
    """Predicted dominant outcome (e.g., 'home', 'draw', 'away', 'over_2.5')."""
    
    dominant_probability: Optional[float] = None
    """Probability of the dominant outcome."""
    
    reasons: List[str] = field(default_factory=list)
    """Structured reasons why this is/isn't an Easy Match."""
    
    warnings: List[str] = field(default_factory=list)
    """Warnings about data quality or missing signals."""
    
    data_sufficient: bool = True
    """Whether sufficient data was available for analysis."""
    
    @property
    def weighted_score(self) -> float:
        """Compute weighted score from available signals."""
        if not self.signals:
            return 0.0
        
        available_signals = [s for s in self.signals if s.available]
        if not available_signals:
            return 0.0
        
        total_weight = sum(s.weight for s in available_signals)
        if total_weight == 0:
            return 0.0
        
        weighted_sum = sum(s.value * s.weight for s in available_signals)
        return (weighted_sum / total_weight) * 100.0


@dataclass
class EasyMatchConfig:
    """Configuration for Easy Match detection."""
    
    easy_match_threshold: float = 65.0
    """Minimum confidence score to qualify as Easy Match (0-100)."""
    
    min_dominant_probability: float = 0.60
    """Minimum probability for dominant 1X2 outcome."""
    
    min_data_signals: int = 3
    """Minimum number of available signals required."""
    
    # Signal weights (must sum to reasonable total)
    weight_1x2_confidence: float = 0.35
    """Weight for 1X2 outcome confidence."""
    
    weight_goals_confidence: float = 0.25
    """Weight for goals market confidence (O/U)."""
    
    weight_btts_confidence: float = 0.15
    """Weight for BTTS confidence."""
    
    weight_xg_differential: float = 0.15
    """Weight for expected goals differential."""
    
    weight_data_quality: float = 0.10
    """Weight for data sufficiency/quality."""


class EasyMatchDetector:
    """Detects matches with high prediction confidence.
    
    Uses multiple statistical signals from the prediction system to
    compute a confidence score. All calculations are deterministic
    and based on available data.
    
    Usage:
        detector = EasyMatchDetector()
        result = detector.detect(
            match_id="m1",
            home_win_prob=0.75,
            draw_prob=0.15,
            away_win_prob=0.10,
            btts_prob=0.35,
            over_2_5_prob=0.68,
            home_xg=2.3,
            away_xg=0.9,
        )
        
        if result.is_easy_match:
            print(f"Easy Match! Score: {result.confidence_score:.1f}")
    """
    
    def __init__(self, config: Optional[EasyMatchConfig] = None):
        """Initialize Easy Match detector.
        
        Args:
            config: Configuration for detection thresholds and weights.
        """
        self.config = config or EasyMatchConfig()
    
    def detect(
        self,
        match_id: str,
        *,
        # 1X2 probabilities
        home_win_prob: Optional[float] = None,
        draw_prob: Optional[float] = None,
        away_win_prob: Optional[float] = None,
        # Calibrated 1X2 (if available)
        home_win_calibrated: Optional[float] = None,
        draw_calibrated: Optional[float] = None,
        away_win_calibrated: Optional[float] = None,
        # Goals markets
        btts_prob: Optional[float] = None,
        over_2_5_prob: Optional[float] = None,
        over_3_5_prob: Optional[float] = None,
        # Expected goals
        home_xg: Optional[float] = None,
        away_xg: Optional[float] = None,
        # Data quality indicators
        has_sufficient_historical_data: bool = True,
        model_agreement_score: Optional[float] = None,
    ) -> EasyMatchResult:
        """Detect if a match qualifies as an Easy Match.
        
        All probability arguments are optional. Signals are only computed
        when the relevant data is available.
        
        Args:
            match_id: Match identifier.
            home_win_prob: Home win probability (model or calibrated).
            draw_prob: Draw probability.
            away_win_prob: Away win probability.
            home_win_calibrated: Calibrated home win probability.
            draw_calibrated: Calibrated draw probability.
            away_win_calibrated: Calibrated away win probability.
            btts_prob: Both teams to score probability.
            over_2_5_prob: Over 2.5 goals probability.
            over_3_5_prob: Over 3.5 goals probability.
            home_xg: Home expected goals.
            away_xg: Away expected goals.
            has_sufficient_historical_data: Data quality flag.
            model_agreement_score: Agreement across models (0-1).
        
        Returns:
            EasyMatchResult with confidence score and analysis.
        """
        signals = []
        reasons = []
        warnings = []
        
        # Use calibrated probabilities if available, else model probabilities
        h_prob = home_win_calibrated if home_win_calibrated is not None else home_win_prob
        d_prob = draw_calibrated if draw_calibrated is not None else draw_prob
        a_prob = away_win_calibrated if away_win_calibrated is not None else away_win_prob
        
        # Signal 1: 1X2 Confidence
        dominant_outcome = None
        dominant_probability = None
        
        if all(p is not None for p in [h_prob, d_prob, a_prob]):
            max_prob = max(h_prob, d_prob, a_prob)
            
            if h_prob == max_prob:
                dominant_outcome = "home"
                dominant_probability = h_prob
            elif a_prob == max_prob:
                dominant_outcome = "away"
                dominant_probability = a_prob
            else:
                dominant_outcome = "draw"
                dominant_probability = d_prob
            
            # Confidence is based on how much the dominant outcome exceeds others
            # Use entropy-like measure: higher dominance = higher confidence
            confidence_1x2 = self._compute_outcome_confidence(h_prob, d_prob, a_prob)
            
            signals.append(EasyMatchSignal(
                name="1x2_confidence",
                value=confidence_1x2,
                weight=self.config.weight_1x2_confidence,
                available=True,
                description=f"{dominant_outcome.capitalize()} win dominance",
            ))
            
            if dominant_probability >= self.config.min_dominant_probability:
                reasons.append(
                    f"Strong {dominant_outcome} prediction ({dominant_probability:.1%})"
                )
            else:
                reasons.append(
                    f"Moderate {dominant_outcome} prediction ({dominant_probability:.1%})"
                )
        else:
            signals.append(EasyMatchSignal(
                name="1x2_confidence",
                value=0.0,
                weight=self.config.weight_1x2_confidence,
                available=False,
                description="1X2 probabilities not available",
            ))
            warnings.append("1X2 probabilities not available")
        
        # Signal 2: Goals Market Confidence
        if over_2_5_prob is not None:
            # Clear signal if probability is strongly above or below 0.5
            goals_confidence = abs(over_2_5_prob - 0.5) * 2  # 0-1 scale
            
            signals.append(EasyMatchSignal(
                name="goals_confidence",
                value=goals_confidence,
                weight=self.config.weight_goals_confidence,
                available=True,
                description=f"Over 2.5 goals: {over_2_5_prob:.1%}",
            ))
            
            if over_2_5_prob >= 0.65:
                reasons.append(f"High-scoring match expected (O2.5: {over_2_5_prob:.1%})")
            elif over_2_5_prob <= 0.35:
                reasons.append(f"Low-scoring match expected (O2.5: {over_2_5_prob:.1%})")
        else:
            signals.append(EasyMatchSignal(
                name="goals_confidence",
                value=0.0,
                weight=self.config.weight_goals_confidence,
                available=False,
                description="Goals market not available",
            ))
            warnings.append("Goals market (O/U 2.5) not available")
        
        # Signal 3: BTTS Confidence
        if btts_prob is not None:
            btts_confidence = abs(btts_prob - 0.5) * 2  # 0-1 scale
            
            signals.append(EasyMatchSignal(
                name="btts_confidence",
                value=btts_confidence,
                weight=self.config.weight_btts_confidence,
                available=True,
                description=f"BTTS: {btts_prob:.1%}",
            ))
            
            if btts_prob >= 0.65:
                reasons.append(f"Both teams likely to score ({btts_prob:.1%})")
            elif btts_prob <= 0.35:
                reasons.append(f"Clean sheet likely ({(1-btts_prob):.1%})")
        else:
            signals.append(EasyMatchSignal(
                name="btts_confidence",
                value=0.0,
                weight=self.config.weight_btts_confidence,
                available=False,
                description="BTTS not available",
            ))
        
        # Signal 4: xG Differential
        if home_xg is not None and away_xg is not None:
            xg_diff = abs(home_xg - away_xg)
            # Normalize: 0 diff = 0 confidence, 2+ diff = 1.0 confidence
            xg_confidence = min(xg_diff / 2.0, 1.0)
            
            signals.append(EasyMatchSignal(
                name="xg_differential",
                value=xg_confidence,
                weight=self.config.weight_xg_differential,
                available=True,
                description=f"xG differential: {xg_diff:.2f}",
            ))
            
            if xg_diff >= 1.0:
                reasons.append(f"Clear quality gap (xG diff: {xg_diff:.2f})")
        else:
            signals.append(EasyMatchSignal(
                name="xg_differential",
                value=0.0,
                weight=self.config.weight_xg_differential,
                available=False,
                description="Expected goals not available",
            ))
        
        # Signal 5: Data Quality
        data_quality_score = 1.0 if has_sufficient_historical_data else 0.3
        
        if model_agreement_score is not None:
            # Blend data sufficiency with model agreement
            data_quality_score = (data_quality_score + model_agreement_score) / 2.0
        
        signals.append(EasyMatchSignal(
            name="data_quality",
            value=data_quality_score,
            weight=self.config.weight_data_quality,
            available=True,
            description="Data sufficiency and model agreement",
        ))
        
        if not has_sufficient_historical_data:
            warnings.append("Limited historical data available")
        
        # Compute overall confidence score
        available_count = sum(1 for s in signals if s.available)
        data_sufficient = available_count >= self.config.min_data_signals
        
        if not data_sufficient:
            warnings.append(
                f"Insufficient signals ({available_count}/{self.config.min_data_signals} minimum)"
            )
            confidence_score = 0.0
        else:
            confidence_score = self._compute_weighted_score(signals)
        
        # Determine if this is an Easy Match
        is_easy_match = (
            data_sufficient and
            confidence_score >= self.config.easy_match_threshold
        )
        
        if is_easy_match:
            reasons.append(
                f"Confidence score {confidence_score:.1f} exceeds threshold {self.config.easy_match_threshold:.1f}"
            )
        elif data_sufficient:
            reasons.append(
                f"Confidence score {confidence_score:.1f} below threshold {self.config.easy_match_threshold:.1f}"
            )
        else:
            reasons.append("Insufficient data for Easy Match determination")
        
        return EasyMatchResult(
            match_id=match_id,
            is_easy_match=is_easy_match,
            confidence_score=confidence_score,
            threshold=self.config.easy_match_threshold,
            signals=signals,
            dominant_outcome=dominant_outcome,
            dominant_probability=dominant_probability,
            reasons=reasons,
            warnings=warnings,
            data_sufficient=data_sufficient,
        )
    
    def _compute_outcome_confidence(
        self,
        home_prob: float,
        draw_prob: float,
        away_prob: float,
    ) -> float:
        """Compute confidence based on outcome probability distribution.
        
        Uses a normalized entropy-like measure where higher dominance
        of one outcome produces higher confidence.
        
        Args:
            home_prob: Home win probability.
            draw_prob: Draw probability.
            away_prob: Away win probability.
        
        Returns:
            Confidence score (0-1).
        """
        max_prob = max(home_prob, draw_prob, away_prob)
        
        # Confidence increases with dominance of max probability
        # Simple linear scaling: 0.33 (equal) -> 0, 1.0 (certain) -> 1
        baseline = 1.0 / 3.0  # Equal probabilities
        confidence = (max_prob - baseline) / (1.0 - baseline)
        
        return max(0.0, min(1.0, confidence))
    
    def _compute_weighted_score(self, signals: List[EasyMatchSignal]) -> float:
        """Compute weighted confidence score from signals.
        
        Args:
            signals: List of signals with values and weights.
        
        Returns:
            Weighted score (0-100).
        """
        available_signals = [s for s in signals if s.available]
        if not available_signals:
            return 0.0
        
        total_weight = sum(s.weight for s in available_signals)
        if total_weight == 0:
            return 0.0
        
        weighted_sum = sum(s.value * s.weight for s in available_signals)
        normalized_score = (weighted_sum / total_weight) * 100.0
        
        return max(0.0, min(100.0, normalized_score))

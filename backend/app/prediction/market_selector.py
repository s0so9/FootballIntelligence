"""Smart Market Selector for MENSIONE canonical pipeline.

Evaluates all available betting markets and selects the best tip or issues a PASS decision.

This module is the authoritative market selection component in the canonical flow:
Match → Feature Snapshot → ModelOrchestrator → Ensemble → Calibration → Confidence
→ Market Intelligence → **Smart Market Selector** → Best Tip / PASS → Prediction → AnalysisContext → API

Selection criteria:
- Probability threshold (model conviction)
- Confidence threshold (overall confidence)
- Edge threshold (value over bookmaker odds, when available)
- Risk level (LOW/MEDIUM/HIGH based on confidence + agreement + data quality)
- Selection score (weighted combination of probability, confidence, agreement, quality, edge)

When no market qualifies, issues a PASS with explicit reasoning.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Optional, Any

from app.prediction.market_derivation import MarketProbabilities
from app.prediction.confidence_engine import ConfidenceAssessment


@dataclass
class BestTip:
    """Best market selection with full analysis."""
    
    match_id: str
    market: str          # e.g. "HOME_WIN", "OVER_2_5", "BTTS_YES"
    selection: str       # Human-readable selection text
    probability: float   # Calibrated model probability
    confidence: float    # Overall confidence score 0.0-1.0
    model_agreement: float  # Agreement between models 0.0-1.0
    data_quality: float  # Data quality score 0.0-1.0
    edge: Optional[float]          # Edge over bookmaker odds (None when no odds)
    fair_odds: float               # Fair odds from model probability
    bookmaker_odds: Optional[float]  # Bookmaker odds (None when unavailable)
    odds_movement: Optional[str]   # "rising", "falling", "stable" or None
    value_classification: str      # "STRONG_VALUE", "VALUE", "NEUTRAL", "NEGATIVE_VALUE"
    risk_level: str                # "LOW", "MEDIUM", "HIGH"
    selection_score: float         # Overall selection score 0.0-1.0
    selector_reason: str           # Why this market was selected
    timestamp: datetime
    pipeline_version: str


@dataclass
class PassDecision:
    """Decision to pass on a match (no qualifying market)."""
    
    match_id: str
    pass_reason: str   # "insufficient_data", "weak_agreement", "poor_calibration",
                       # "negative_value", "no_qualifying_market", "high_uncertainty"
    evaluated_markets_count: int
    best_market_details: Optional[Dict[str, Any]]  # Details of closest market that didn't qualify
    timestamp: datetime
    pipeline_version: str


class SmartMarketSelector:
    """Smart market selector for the MENSIONE canonical pipeline.
    
    Evaluates all available markets from MarketProbabilities and selects the best tip
    based on probability, confidence, edge, and risk assessment.
    
    Issues a PASS decision when no market meets the qualification criteria.
    """
    
    def __init__(
        self,
        min_confidence: float = 0.4,
        min_probability: float = 0.5,
        min_edge: float = 0.0,
        max_risk_level: str = "HIGH"
    ):
        """Initialize smart market selector.
        
        Args:
            min_confidence: Minimum confidence threshold [0, 1]
            min_probability: Minimum probability threshold [0, 1]
            min_edge: Minimum edge threshold (when odds available)
            max_risk_level: Maximum acceptable risk level ("LOW", "MEDIUM", "HIGH")
        """
        self.min_confidence = min_confidence
        self.min_probability = min_probability
        self.min_edge = min_edge
        self.max_risk_level = max_risk_level
    
    def evaluate_and_select(
        self,
        market_probs: MarketProbabilities,
        confidence_assessment: ConfidenceAssessment,
        odds_data: Optional[Dict[str, float]] = None,
        pipeline_version: str = "1.0.0"
    ):
        """Evaluate all available markets and select the best tip or issue a PASS.
        
        Args:
            market_probs: MarketProbabilities from market_derivation
            confidence_assessment: ConfidenceAssessment from confidence_engine
            odds_data: Optional dict mapping market_key -> bookmaker_odds
            pipeline_version: Pipeline version for tracking
            
        Returns:
            BestTip if a qualifying market is found, PassDecision otherwise
        """
        # Extract match_id
        match_id = getattr(market_probs, 'match_id', 'unknown')
        
        # Extract confidence components
        overall_confidence = confidence_assessment.overall_confidence
        model_agreement = confidence_assessment.components.model_agreement
        data_quality = confidence_assessment.components.data_quality
        
        # Build candidate markets
        candidates = self._build_candidates(
            market_probs=market_probs,
            overall_confidence=overall_confidence,
            model_agreement=model_agreement,
            data_quality=data_quality,
            odds_data=odds_data
        )
        
        if not candidates:
            return PassDecision(
                match_id=match_id,
                pass_reason="insufficient_data",
                evaluated_markets_count=0,
                best_market_details=None,
                timestamp=datetime.utcnow(),
                pipeline_version=pipeline_version
            )
        
        # Apply filters
        qualifying = self._filter_candidates(
            candidates=candidates,
            min_confidence=self.min_confidence,
            min_probability=self.min_probability,
            min_edge=self.min_edge,
            max_risk_level=self.max_risk_level
        )
        
        if not qualifying:
            # Determine pass reason
            pass_reason = self._determine_pass_reason(
                candidates=candidates,
                min_confidence=self.min_confidence,
                min_probability=self.min_probability,
                min_edge=self.min_edge
            )
            
            # Find best candidate (highest selection_score before filtering)
            best_candidate = max(candidates, key=lambda c: c['selection_score'])
            best_market_details = {
                'market': best_candidate['market'],
                'selection': best_candidate['selection'],
                'probability': best_candidate['probability'],
                'confidence': best_candidate['confidence'],
                'selection_score': best_candidate['selection_score'],
                'risk_level': best_candidate['risk_level'],
                'value_classification': best_candidate['value_classification']
            }
            
            return PassDecision(
                match_id=match_id,
                pass_reason=pass_reason,
                evaluated_markets_count=len(candidates),
                best_market_details=best_market_details,
                timestamp=datetime.utcnow(),
                pipeline_version=pipeline_version
            )
        
        # Sort by selection_score (descending), then confidence, then probability
        qualifying.sort(
            key=lambda c: (c['selection_score'], c['confidence'], c['probability']),
            reverse=True
        )
        
        # Select best
        best = qualifying[0]
        
        # Build selector reason
        selector_reason = (
            f"Selected {best['market']}: "
            f"probability={best['probability']:.2f}, "
            f"confidence={best['confidence']:.2f}, "
            f"model_agreement={best['model_agreement']:.2f}, "
            f"risk={best['risk_level']}, "
            f"value={best['value_classification']}"
        )
        
        return BestTip(
            match_id=match_id,
            market=best['market'],
            selection=best['selection'],
            probability=best['probability'],
            confidence=best['confidence'],
            model_agreement=best['model_agreement'],
            data_quality=best['data_quality'],
            edge=best['edge'],
            fair_odds=best['fair_odds'],
            bookmaker_odds=best['bookmaker_odds'],
            odds_movement=best['odds_movement'],
            value_classification=best['value_classification'],
            risk_level=best['risk_level'],
            selection_score=best['selection_score'],
            selector_reason=selector_reason,
            timestamp=datetime.utcnow(),
            pipeline_version=pipeline_version
        )
    
    def _build_candidates(
        self,
        market_probs: MarketProbabilities,
        overall_confidence: float,
        model_agreement: float,
        data_quality: float,
        odds_data: Optional[Dict[str, float]]
    ):
        """Build list of candidate markets with all analysis fields.
        
        Returns:
            List of candidate dicts with all fields computed
        """
        candidates = []
        
        # 1X2 markets
        for market_key, prob, selection in [
            ('HOME_WIN', market_probs.home_win, 'Home Win'),
            ('DRAW', market_probs.draw, 'Draw'),
            ('AWAY_WIN', market_probs.away_win, 'Away Win')
        ]:
            if prob and prob > 0:
                candidate = self._build_candidate(
                    market=market_key,
                    selection=selection,
                    probability=prob,
                    confidence=overall_confidence,
                    model_agreement=model_agreement,
                    data_quality=data_quality,
                    odds_data=odds_data
                )
                candidates.append(candidate)
        
        # Double chance markets
        for market_key, prob, selection in [
            ('HOME_OR_DRAW', market_probs.home_or_draw, 'Home or Draw'),
            ('DRAW_OR_AWAY', market_probs.draw_or_away, 'Draw or Away'),
            ('HOME_OR_AWAY', market_probs.home_or_away, 'Home or Away')
        ]:
            if prob and prob > 0:
                candidate = self._build_candidate(
                    market=market_key,
                    selection=selection,
                    probability=prob,
                    confidence=overall_confidence,
                    model_agreement=model_agreement,
                    data_quality=data_quality,
                    odds_data=odds_data
                )
                candidates.append(candidate)
        
        # Over/Under markets
        for line, (over_prob, under_prob) in market_probs.over_under.items():
            if over_prob and over_prob > 0:
                candidate = self._build_candidate(
                    market=f'OVER_{line}'.replace('.', '_'),
                    selection=f'Over {line} Goals',
                    probability=over_prob,
                    confidence=overall_confidence,
                    model_agreement=model_agreement,
                    data_quality=data_quality,
                    odds_data=odds_data
                )
                candidates.append(candidate)
            
            if under_prob and under_prob > 0:
                candidate = self._build_candidate(
                    market=f'UNDER_{line}'.replace('.', '_'),
                    selection=f'Under {line} Goals',
                    probability=under_prob,
                    confidence=overall_confidence,
                    model_agreement=model_agreement,
                    data_quality=data_quality,
                    odds_data=odds_data
                )
                candidates.append(candidate)
        
        # BTTS markets
        if market_probs.btts_yes and market_probs.btts_yes > 0:
            candidate = self._build_candidate(
                market='BTTS_YES',
                selection='Both Teams to Score',
                probability=market_probs.btts_yes,
                confidence=overall_confidence,
                model_agreement=model_agreement,
                data_quality=data_quality,
                odds_data=odds_data
            )
            candidates.append(candidate)
        
        if market_probs.btts_no and market_probs.btts_no > 0:
            candidate = self._build_candidate(
                market='BTTS_NO',
                selection='Both Teams NOT to Score',
                probability=market_probs.btts_no,
                confidence=overall_confidence,
                model_agreement=model_agreement,
                data_quality=data_quality,
                odds_data=odds_data
            )
            candidates.append(candidate)
        
        # Team totals
        for line, prob in market_probs.home_team_over.items():
            if prob and prob > 0:
                candidate = self._build_candidate(
                    market=f'HOME_OVER_{line}'.replace('.', '_'),
                    selection=f'Home Over {line} Goals',
                    probability=prob,
                    confidence=overall_confidence,
                    model_agreement=model_agreement,
                    data_quality=data_quality,
                    odds_data=odds_data
                )
                candidates.append(candidate)
        
        for line, prob in market_probs.away_team_over.items():
            if prob and prob > 0:
                candidate = self._build_candidate(
                    market=f'AWAY_OVER_{line}'.replace('.', '_'),
                    selection=f'Away Over {line} Goals',
                    probability=prob,
                    confidence=overall_confidence,
                    model_agreement=model_agreement,
                    data_quality=data_quality,
                    odds_data=odds_data
                )
                candidates.append(candidate)
        
        return candidates
    
    def _build_candidate(
        self,
        market: str,
        selection: str,
        probability: float,
        confidence: float,
        model_agreement: float,
        data_quality: float,
        odds_data: Optional[Dict[str, float]]
    ) -> Dict[str, Any]:
        """Build a single candidate market with all analysis fields.
        
        Returns:
            Dict containing all candidate fields
        """
        # Calculate fair odds
        fair_odds = 1.0 / probability if probability > 0 else 0.0
        
        # Get bookmaker odds
        bookmaker_odds = odds_data.get(market) if odds_data else None
        
        # Calculate edge
        edge = None
        if bookmaker_odds and bookmaker_odds > 0:
            implied_prob = 1.0 / bookmaker_odds
            edge = probability - implied_prob
        
        # Value classification
        if edge is None:
            value_classification = "NEUTRAL"
        elif edge >= 0.10:
            value_classification = "STRONG_VALUE"
        elif edge >= 0.05:
            value_classification = "VALUE"
        elif edge >= 0.0:
            value_classification = "NEUTRAL"
        else:
            value_classification = "NEGATIVE_VALUE"
        
        # Risk level
        if confidence >= 0.7 and model_agreement >= 0.8 and data_quality >= 0.7:
            risk_level = "LOW"
        elif confidence >= 0.5 and model_agreement >= 0.6 and data_quality >= 0.5:
            risk_level = "MEDIUM"
        else:
            risk_level = "HIGH"
        
        # Selection score
        selection_score = (
            0.35 * probability +
            0.30 * confidence +
            0.20 * model_agreement +
            0.15 * data_quality
        )
        
        # Add edge bonus (capped)
        if edge is not None and edge > 0:
            edge_bonus = 0.10 * min(edge, 0.2)
            selection_score = min(1.0, selection_score + edge_bonus)
        
        return {
            'market': market,
            'selection': selection,
            'probability': probability,
            'confidence': confidence,
            'model_agreement': model_agreement,
            'data_quality': data_quality,
            'fair_odds': fair_odds,
            'bookmaker_odds': bookmaker_odds,
            'edge': edge,
            'value_classification': value_classification,
            'risk_level': risk_level,
            'selection_score': selection_score,
            'odds_movement': None  # Not implemented yet
        }
    
    def _filter_candidates(
        self,
        candidates,
        min_confidence: float,
        min_probability: float,
        min_edge: float,
        max_risk_level: str
    ):
        """Filter candidates by thresholds.
        
        Returns:
            List of qualifying candidates
        """
        risk_order = {'LOW': 0, 'MEDIUM': 1, 'HIGH': 2}
        max_risk_value = risk_order.get(max_risk_level, 2)
        
        qualifying = []
        for c in candidates:
            # Check confidence
            if c['confidence'] < min_confidence:
                continue
            
            # Check probability
            if c['probability'] < min_probability:
                continue
            
            # Check edge (only if edge is available)
            if c['edge'] is not None and c['edge'] < min_edge:
                continue
            
            # Check risk level
            candidate_risk_value = risk_order.get(c['risk_level'], 2)
            if candidate_risk_value > max_risk_value:
                continue
            
            qualifying.append(c)
        
        return qualifying
    
    def _determine_pass_reason(
        self,
        candidates,
        min_confidence: float,
        min_probability: float,
        min_edge: float
    ) -> str:
        """Determine the reason for passing on this match.
        
        Returns:
            Pass reason string
        """
        if not candidates:
            return "insufficient_data"
        
        # Check if all below confidence
        all_below_confidence = all(c['confidence'] < min_confidence for c in candidates)
        if all_below_confidence:
            return "poor_calibration"
        
        # Check if all below probability
        all_below_probability = all(c['probability'] < min_probability for c in candidates)
        if all_below_probability:
            return "weak_agreement"
        
        # Check if all have negative edge
        candidates_with_edge = [c for c in candidates if c['edge'] is not None]
        if candidates_with_edge and all(c['edge'] < min_edge for c in candidates_with_edge):
            return "negative_value"
        
        return "no_qualifying_market"

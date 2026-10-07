# Phase 10 Group 5 Implementation Plan
## Market-Specific Modeling + Model Disagreement + Uncertainty + Calibration Integration

---

## ARCHITECTURE AUDIT FINDINGS

### Current Pipeline Architecture

```
MatchFeatureSnapshot
↓
ModelOrchestrator.run_all() → ModelOrchestrationResult
↓
EnsembleIntegration.combine() → ModelPrediction (ensemble)
↓
CalibrationIntegration.calibrate_prediction() → ModelPrediction (calibrated)
↓
ConfidenceIntegration.assess_confidence() → ConfidenceAssessment
↓
MarketDerivationEngine.derive() → MarketProbabilities
↓
SmartMarketSelector.evaluate_and_select() → BestTip / PassDecision
```

### Key Existing Components

**ModelOrchestrationResult** contains:
- `successful_predictions: List[ModelOutput]` where each ModelOutput has `prediction: ModelPrediction`
- `unavailable_models: List[ModelOutput]`
- `failed_models: List[ModelOutput]`

**ModelPrediction** contains:
- `home_win_prob`, `draw_prob`, `away_win_prob` (1X2 probabilities)
- `score_distribution: Dict[Tuple[int, int], float]` (scoreline probabilities)
- `home_score_mean`, `away_score_mean` (expected goals)
- `confidence_score`, `data_quality_score`
- `metadata: Dict[str, Any]` (extensible)

**EnsembleEngine** already calculates:
- `model_agreement` via `_calculate_agreement()` (std dev of home_win_prob across models)
- Stores in `metadata["model_agreement"]`

**ConfidenceEngine** already consumes:
- `model_agreement` from ensemble metadata
- `data_quality_score` from snapshot
- `n_matches` from snapshot form data
- `brier_score` from calibration metadata (optional)
- Returns `ConfidenceAssessment` with `overall_confidence` and `ConfidenceComponents`

**CalibrationEngine** (calibration_engine.py):
- `IsotonicCalibration` class already exists
- Has `is_fitted` property and `calibrate(prob)` method
- Returns uncalibrated probability when not fitted

**Calibrator1X2** (model_orchestrator.py):
- Wraps three `IsotonicCalibration` instances
- Has `calibrate_1x2()` method
- Has `is_fitted` property
- Currently lacks temporal leakage protection and status tracking

**MarketDerivationEngine**:
- Derives all markets from `score_distribution`
- Returns `MarketProbabilities` with 1X2, O/U, BTTS, double chance, team totals, exact score, Asian handicap

**SmartMarketSelector**:
- Evaluates markets from `MarketProbabilities`
- Takes `ConfidenceAssessment` as input
- Returns `BestTip` or `PassDecision`
- Already calculates risk level and selection score

**ShotProductionCalculator** (shot_production.py):
- Fits Poisson or Negative Binomial distributions to shot counts
- Calculates `P(X > T)` for thresholds: 10, 12, 15, 18, 20 (shots) and 3, 4, 5, 6 (SOT)
- Returns `ShotProduction` dataclass

**ShotIntelligenceCalculator** (shot_intelligence.py):
- Extracts raw shot counts from `MatchWithStatistics`
- Returns `ShotIntelligenceMetrics`

### Feature Engineering State

From audit: **172 tests passing** in feature engineering.

Existing feature engineering includes:
- Team intelligence (Group 1)
- Opponent adjustment (Group 2)
- Temporal intelligence (Group 3)
- Lineup intelligence (Group 4)
- Tactical intelligence (Group 5)
- Shot intelligence (Group 6)
- Common opponent intelligence (Group 7)
- **Advanced feature engineering** (Group 8) with `AdvancedFeatureSet`

`MatchFeatureSnapshot` has:
- `advanced_feature_set: Optional[AdvancedFeatureSet]` field
- Standard features: team strength, form, league context, player availability, tactical context
- Shot data available via ShotIntelligenceCalculator

---

## IMPLEMENTATION STRATEGY

### Core Principle
**DO NOT create new prediction engines or duplicate existing infrastructure.**

Extend existing components:
1. Market-specific feature eligibility (not weighting) in feature snapshot
2. Shot market structures as new dataclasses in `interfaces.py`
3. Shot market engine reuses `ShotProductionCalculator`
4. Model disagreement extracted from existing ensemble metadata
5. Uncertainty engine combines existing confidence components
6. Calibration extensions add temporal protection
7. Market reliability combines existing metrics
8. Smart Market Selector extended with uncertainty filtering

---

## DETAILED IMPLEMENTATION PLAN

### 10I — MARKET-SPECIFIC MODELING

---

- [ ] **1. Create `backend/app/prediction/market_features.py`**
  
  **What:** Define market types, feature-to-market eligibility mapping, and market feature selector.
  
  **Content:**
  ```python
  class MarketType(str, Enum):
      MATCH_RESULT_1X2 = "1x2"
      OVER_UNDER = "over_under"
      BTTS = "btts"
      DOUBLE_CHANCE = "double_chance"
      HANDICAP = "handicap"
      TEAM_SHOTS = "team_shots"
      TEAM_SHOTS_ON_TARGET = "team_shots_on_target"
      TOTAL_SHOTS = "total_shots"
      TOTAL_SHOTS_ON_TARGET = "total_shots_on_target"
  
  MARKET_FEATURE_ELIGIBILITY = {
      MarketType.MATCH_RESULT_1X2: [
          "home_goals_per_match", "away_goals_per_match",
          "home_xg_per_match", "away_xg_per_match",
          "home_elo", "away_elo",
          "home_form_points_per_match", "away_form_points_per_match",
          "home_attack_strength", "away_attack_strength",
          "home_defense_strength", "away_defense_strength",
          "home_advantage", "league_avg_goals",
          # Advanced features (if available)
          "team_intelligence_score", "opponent_adjustment_factor",
          "temporal_form_trend", "lineup_impact_score",
          "tactical_matchup_score", "common_opponent_strength_delta"
      ],
      MarketType.OVER_UNDER: [
          "home_goals_per_match", "away_goals_per_match",
          "home_xg_per_match", "away_xg_per_match",
          "home_goals_conceded_per_match", "away_goals_conceded_per_match",
          "league_avg_goals",
          "team_intelligence_score", "opponent_adjustment_factor",
          "shot_volume_home", "shot_volume_away"
      ],
      MarketType.BTTS: [
          "home_goals_per_match", "away_goals_per_match",
          "home_goals_conceded_per_match", "away_goals_conceded_per_match",
          "home_attack_strength", "away_attack_strength",
          "home_defense_strength", "away_defense_strength"
      ],
      MarketType.DOUBLE_CHANCE: [
          # Same as 1X2 (derived from 1X2)
          "home_goals_per_match", "away_goals_per_match",
          "home_xg_per_match", "away_xg_per_match",
          "home_elo", "away_elo",
          "home_form_points_per_match", "away_form_points_per_match"
      ],
      MarketType.HANDICAP: [
          "home_goals_per_match", "away_goals_per_match",
          "home_xg_per_match", "away_xg_per_match",
          "home_elo", "away_elo",
          "team_strength_delta", "common_opponent_strength_delta"
      ],
      MarketType.TEAM_SHOTS: [
          "shot_volume_home", "shot_volume_away",
          "shots_per_match_home", "shots_per_match_away",
          "opponent_shots_suppression",
          "team_intelligence_score", "tactical_matchup_score"
      ],
      MarketType.TEAM_SHOTS_ON_TARGET: [
          "sot_per_match_home", "sot_per_match_away",
          "shot_quality_home", "shot_quality_away",
          "opponent_sot_suppression"
      ],
      MarketType.TOTAL_SHOTS: [
          "shot_volume_home", "shot_volume_away",
          "shots_per_match_home", "shots_per_match_away",
          "league_avg_shots"
      ],
      MarketType.TOTAL_SHOTS_ON_TARGET: [
          "sot_per_match_home", "sot_per_match_away",
          "shot_quality_home", "shot_quality_away"
      ]
  }
  
  class MarketFeatureSelector:
      def get_eligible_features(self, market: MarketType, snapshot: MatchFeatureSnapshot) -> Dict[str, Optional[float]]:
          """Extract eligible features for a market from snapshot."""
      
      def get_feature_availability(self, market: MarketType, snapshot: MatchFeatureSnapshot) -> Dict[str, Any]:
          """Return feature availability report for market."""
  ```
  
  **Files:** `backend/app/prediction/market_features.py` (new)
  
  **Verify:** Run `pytest backend/tests/prediction/test_market_features.py -v` (create test alongside implementation)

---

- [ ] **2. Extend `backend/app/prediction/interfaces.py` with shot market structures**
  
  **What:** Add shot market prediction dataclasses to interfaces.py.
  
  **Add to interfaces.py:**
  ```python
  @dataclass
  class ShotMarketThreshold:
      """Shot market threshold definition."""
      threshold: int  # e.g., 10, 12, 15, 18, 20
      over_probability: float  # P(X > threshold)
      distribution_model: str  # "poisson", "negative_binomial", "none"
      expected_value: Optional[float] = None
      variance: Optional[float] = None
      data_quality: float = 0.0
  
  class ShotMarketType(str, Enum):
      """Shot market types."""
      TEAM_SHOTS = "team_shots"
      TEAM_SHOTS_ON_TARGET = "team_shots_on_target"
      TOTAL_SHOTS = "total_shots"
      TOTAL_SHOTS_ON_TARGET = "total_shots_on_target"
  
  @dataclass
  class ShotMarketPrediction:
      """Shot market prediction with threshold probabilities."""
      team_id: str
      market_type: ShotMarketType
      thresholds: List[ShotMarketThreshold]
      
      # Distribution parameters
      distribution_model: str  # "poisson", "negative_binomial", "none"
      expected_value: Optional[float] = None
      variance: Optional[float] = None
      
      # Availability
      available: bool = True
      unavailability_reason: Optional[str] = None
      
      # Provenance
      sample_size: int = 0
      data_quality_score: float = 0.0
      model_id: str = "shot_market_v1"
  ```
  
  **Files:** `backend/app/prediction/interfaces.py`
  
  **Verify:** Run `pytest backend/tests/prediction/test_interfaces.py -v` (extend existing test)

---

- [ ] **3. Create `backend/app/prediction/shot_market_engine.py`**
  
  **What:** Shot market probability calculator using existing `ShotProductionCalculator`.
  
  **Content:**
  ```python
  class ShotMarketEngine:
      """Calculate shot market probabilities using ShotProductionCalculator."""
      
      TEAM_SHOTS_THRESHOLDS = [10, 12, 15, 18, 20]
      SOT_THRESHOLDS = [3, 4, 5, 6]
      TOTAL_SHOTS_THRESHOLDS = [20, 22, 25, 30]
      
      def __init__(self, session, shot_production_calc: Optional[ShotProductionCalculator] = None):
          self.session = session
          self.shot_calc = shot_production_calc or ShotProductionCalculator(session=session)
      
      def predict_team_shots(
          self,
          team_id: str,
          shot_intelligence: ShotIntelligenceMetrics,
          match_context: Optional[Dict[str, Any]] = None
      ) -> ShotMarketPrediction:
          """Predict team shots market probabilities."""
          # Use shot_intelligence.get_raw_shot_counts() to get historical data
          # Pass to shot_production_calc.calculate()
          # Map ShotProduction thresholds to ShotMarketThreshold objects
          # Return ShotMarketPrediction with TEAM_SHOTS market type
      
      def predict_team_sot(
          self,
          team_id: str,
          shot_intelligence: ShotIntelligenceMetrics,
          match_context: Optional[Dict[str, Any]] = None
      ) -> ShotMarketPrediction:
          """Predict team SOT market probabilities."""
          # Similar to team shots but for SOT thresholds
      
      def predict_total_shots(
          self,
          home_shot_intelligence: ShotIntelligenceMetrics,
          away_shot_intelligence: ShotIntelligenceMetrics,
          match_context: Optional[Dict[str, Any]] = None
      ) -> ShotMarketPrediction:
          """Predict total shots (home + away) market probabilities."""
          # Use shot_production_calc.calculate_total()
          # Map to TOTAL_SHOTS market type
      
      def predict_all_shot_markets(
          self,
          snapshot: MatchFeatureSnapshot
      ) -> Dict[ShotMarketType, ShotMarketPrediction]:
          """Predict all available shot markets for a match."""
          # Orchestrate all shot market predictions
          # Return dict mapping market type to prediction
          # Return empty dict if insufficient shot data
  ```
  
  **Files:** `backend/app/prediction/shot_market_engine.py` (new)
  
  **Verify:** Run `pytest backend/tests/prediction/test_shot_market_engine.py -v`

---

### 10J — MODEL DISAGREEMENT + UNCERTAINTY

---

- [ ] **4. Create `backend/app/prediction/model_disagreement.py`**
  
  **What:** Extract and formalize model disagreement calculation from ensemble.
  
  **Content:**
  ```python
  @dataclass
  class ModelDisagreementResult:
      """Model disagreement metrics."""
      model_count: int
      available_model_count: int
      mean_probability: float
      probability_std: float  # Standard deviation
      probability_range: float  # max - min
      agreement_score: float  # 1 - (std * 3), from EnsembleEngine formula
      disagreement_score: float  # 1 - agreement_score
      
      # Individual model probabilities for transparency
      model_probabilities: Dict[str, float] = field(default_factory=dict)
      
      # Interpretation
      agreement_label: str = ""  # "HIGH", "MEDIUM", "LOW"
  
  class ModelDisagreementAnalyzer:
      """Analyze model disagreement from orchestration results."""
      
      def analyze(
          self,
          orchestration_result: ModelOrchestrationResult,
          outcome: str = "home_win"  # "home_win", "draw", "away_win"
      ) -> ModelDisagreementResult:
          """Calculate disagreement metrics for a specific outcome."""
          # Extract probabilities for the outcome from all successful predictions
          # Calculate mean, std, range
          # Calculate agreement score using ensemble formula: 1 - (std * 3)
          # Determine label: HIGH (agreement > 0.8), MEDIUM (0.5-0.8), LOW (< 0.5)
      
      def analyze_all_outcomes(
          self,
          orchestration_result: ModelOrchestrationResult
      ) -> Dict[str, ModelDisagreementResult]:
          """Analyze disagreement for home_win, draw, away_win."""
          return {
              "home_win": self.analyze(orchestration_result, "home_win"),
              "draw": self.analyze(orchestration_result, "draw"),
              "away_win": self.analyze(orchestration_result, "away_win")
          }
  ```
  
  **Files:** `backend/app/prediction/model_disagreement.py` (new)
  
  **Verify:** Run `pytest backend/tests/prediction/test_model_disagreement.py -v`

---

- [ ] **5. Create `backend/app/prediction/uncertainty_engine.py`**
  
  **What:** Combine model disagreement + data quality + feature availability + calibration into uncertainty assessment.
  
  **Content:**
  ```python
  @dataclass
  class UncertaintyComponents:
      """Individual uncertainty contributors."""
      model_disagreement: float  # 0 = high agreement, 1 = high disagreement
      data_quality_deficit: float  # 1 - data_quality_score
      feature_availability_deficit: float  # Proportion of missing features
      probability_dispersion: float  # How spread out probabilities are
      sample_size_inadequacy: float  # Inverse of sample size score
      calibration_uncertainty: float  # Uncertainty from calibration status
  
  @dataclass
  class UncertaintyAssessment:
      """Overall uncertainty assessment."""
      overall_uncertainty: float  # 0 = low uncertainty, 1 = high uncertainty
      uncertainty_label: str  # "LOW", "MEDIUM", "HIGH"
      components: UncertaintyComponents
      interpretation: str  # Human-readable explanation
      
      # Inverse: confidence from uncertainty
      implied_confidence: float  # 1 - overall_uncertainty
  
  class UncertaintyEngine:
      """Assess prediction uncertainty from multiple sources."""
      
      def assess(
          self,
          model_disagreement: ModelDisagreementResult,
          data_quality_score: float,
          feature_availability: Dict[str, bool],
          sample_size: int,
          calibration_status: str,  # "FITTED", "INSUFFICIENT_DATA", "NOT_FITTED"
          probability_dispersion: Optional[float] = None
      ) -> UncertaintyAssessment:
          """Assess overall uncertainty."""
          # Component calculations:
          # - model_disagreement: use disagreement_score from result
          # - data_quality_deficit: 1 - data_quality_score
          # - feature_availability_deficit: count(missing) / count(eligible)
          # - sample_size_inadequacy: 1 / (1 + exp(0.1 * (n - 30)))
          # - calibration_uncertainty: 0.0 if FITTED, 0.3 if INSUFFICIENT, 0.5 if NOT_FITTED
          # - probability_dispersion: optional, from score distribution entropy
          
          # Weighted average:
          # overall = (0.30 * disagreement + 0.25 * data_deficit + 
          #            0.20 * feature_deficit + 0.15 * sample_inadequacy + 
          #            0.10 * calibration)
          
          # Label: LOW (< 0.3), MEDIUM (0.3-0.6), HIGH (> 0.6)
  ```
  
  **Files:** `backend/app/prediction/uncertainty_engine.py` (new)
  
  **Verify:** Run `pytest backend/tests/prediction/test_uncertainty_engine.py -v`

---

- [ ] **6. Extend `backend/app/prediction/calibration_engine.py` with temporal protection**
  
  **What:** Add calibration status enum and temporal leakage protection to existing `CalibrationEngine`.
  
  **Add to calibration_engine.py:**
  ```python
  class CalibrationStatus(str, Enum):
      """Calibration status."""
      FITTED = "fitted"  # Calibrator fitted with sufficient data
      INSUFFICIENT_DATA = "insufficient_data"  # Not enough samples
      NOT_FITTED = "not_fitted"  # Never fitted
  
  # Extend CalibrationEngine:
  class CalibrationEngine:
      def __init__(self, method: str = "isotonic"):
          # ... existing __init__ ...
          self._status = CalibrationStatus.NOT_FITTED
          self._calibration_sample_size = 0
          self._fitted_at: Optional[datetime] = None
      
      @property
      def status(self) -> CalibrationStatus:
          """Get calibration status."""
          if not self.calibrator.is_fitted:
              return CalibrationStatus.NOT_FITTED
          if self._calibration_sample_size < IsotonicCalibration.MIN_SAMPLES:
              return CalibrationStatus.INSUFFICIENT_DATA
          return CalibrationStatus.FITTED
      
      @property
      def calibration_sample_size(self) -> int:
          return self._calibration_sample_size
      
      def fit(self, data: CalibrationData, cutoff_date: Optional[datetime] = None) -> None:
          # Existing fit method already has cutoff_date parameter
          # Update to set _status and _calibration_sample_size
          # ... existing code ...
          self._calibration_sample_size = len(data)
          self._fitted_at = datetime.utcnow()
      
      def get_status_metadata(self) -> Dict[str, Any]:
          """Return calibration status metadata."""
          return {
              "status": self.status.value,
              "sample_size": self._calibration_sample_size,
              "fitted_at": self._fitted_at.isoformat() if self._fitted_at else None,
              "is_fitted": self.is_fitted,
              "method": self.method
          }
  ```
  
  **Add market-specific calibration stubs (for future):**
  ```python
  class MarketSpecificCalibration:
      """Market-specific calibration manager (stub for Group 6)."""
      
      def __init__(self):
          self.calibrators: Dict[str, CalibrationEngine] = {}
      
      def register_market(self, market_type: str, engine: CalibrationEngine) -> None:
          """Register calibrator for a market type."""
          self.calibrators[market_type] = engine
      
      def get_calibrator(self, market_type: str) -> Optional[CalibrationEngine]:
          """Get calibrator for market type (returns None if not registered)."""
          return self.calibrators.get(market_type)
      
      def calibrate_for_market(self, market_type: str, prob: float) -> float:
          """Calibrate probability for specific market."""
          calibrator = self.get_calibrator(market_type)
          if calibrator is None or not calibrator.is_fitted:
              return prob  # Return uncalibrated
          return calibrator.calibrate(prob)
  ```
  
  **Files:** `backend/app/prediction/calibration_engine.py`
  
  **Verify:** Run `pytest backend/tests/prediction/test_calibration_engine.py -v` (extend existing tests)

---

- [ ] **7. Create `backend/app/prediction/market_reliability.py`**
  
  **What:** Combine probability + calibration + uncertainty + data quality into market reliability score.
  
  **Content:**
  ```python
  @dataclass
  class MarketReliability:
      """Reliability assessment for a market prediction."""
      market_key: str  # e.g., "HOME_WIN", "OVER_2_5"
      probability: float  # Calibrated probability
      calibration_status: CalibrationStatus
      uncertainty: float  # From UncertaintyAssessment
      data_quality: float  # From snapshot
      
      # Composite reliability score
      reliability_score: float  # 0.0 = unreliable, 1.0 = highly reliable
      reliability_label: str  # "HIGH", "MEDIUM", "LOW"
      
      # Components breakdown
      probability_factor: float  # How conviction affects reliability
      calibration_factor: float  # Penalty for uncalibrated
      uncertainty_factor: float  # 1 - uncertainty
      data_quality_factor: float  # Direct data quality
      
      # Interpretation
      recommendation: str  # "STRONG_BET", "CONSIDER", "PASS", "AVOID"
  
  class MarketReliabilityCalculator:
      """Calculate market reliability from measurable components."""
      
      def calculate(
          self,
          market_key: str,
          probability: float,
          calibration_status: CalibrationStatus,
          uncertainty_assessment: UncertaintyAssessment,
          data_quality_score: float
      ) -> MarketReliability:
          """Calculate market reliability."""
          # Component factors:
          # - probability_factor: penalize low conviction (< 0.6)
          #   factor = (prob - 0.5) / 0.5 if prob > 0.5 else 0.0
          # - calibration_factor: FITTED = 1.0, INSUFFICIENT = 0.7, NOT_FITTED = 0.5
          # - uncertainty_factor: 1 - uncertainty.overall_uncertainty
          # - data_quality_factor: data_quality_score
          
          # Reliability score (weighted average):
          # reliability = (0.25 * prob_factor + 0.25 * calib_factor + 
          #                0.30 * uncertainty_factor + 0.20 * data_quality_factor)
          
          # Label: HIGH (> 0.7), MEDIUM (0.4-0.7), LOW (< 0.4)
          
          # Recommendation:
          # STRONG_BET: reliability > 0.7 and probability > 0.65
          # CONSIDER: reliability > 0.5 and probability > 0.55
          # PASS: reliability 0.3-0.5
          # AVOID: reliability < 0.3
  ```
  
  **Files:** `backend/app/prediction/market_reliability.py` (new)
  
  **Verify:** Run `pytest backend/tests/prediction/test_market_reliability.py -v`

---

- [ ] **8. Extend `backend/app/prediction/market_selector.py` with uncertainty filtering**
  
  **What:** Update SmartMarketSelector to accept and use UncertaintyAssessment and ModelDisagreementResult.
  
  **Modifications to market_selector.py:**
  ```python
  # Extend SmartMarketSelector.__init__:
  def __init__(
      self,
      min_confidence: float = 0.4,
      min_probability: float = 0.5,
      min_edge: float = 0.0,
      max_risk_level: str = "HIGH",
      max_uncertainty: float = 0.7  # NEW: reject if uncertainty > threshold
  ):
      # ... existing fields ...
      self.max_uncertainty = max_uncertainty
  
  # Extend evaluate_and_select signature:
  def evaluate_and_select(
      self,
      market_probs: MarketProbabilities,
      confidence_assessment: ConfidenceAssessment,
      odds_data: Optional[Dict[str, float]] = None,
      pipeline_version: str = "1.0.0",
      uncertainty_assessment: Optional[UncertaintyAssessment] = None,  # NEW
      model_disagreement: Optional[ModelDisagreementResult] = None,  # NEW
      shot_market_predictions: Optional[Dict[ShotMarketType, ShotMarketPrediction]] = None  # NEW
  ):
      # In _build_candidates, add shot market candidates if available
      # In _filter_candidates, add uncertainty filter:
      #   if uncertainty_assessment and c['uncertainty'] > self.max_uncertainty:
      #       continue
      # In _determine_pass_reason, add uncertainty check:
      #   if all candidates have high uncertainty: return "high_uncertainty"
  
  # Add shot market candidate building:
  def _build_shot_market_candidates(...):
      """Build candidates from shot market predictions."""
      # For each ShotMarketPrediction and each threshold:
      # Create candidate with market = "TEAM_SHOTS_OVER_12", probability = threshold.over_probability
  ```
  
  **Files:** `backend/app/prediction/market_selector.py`
  
  **Verify:** Run `pytest backend/tests/prediction/test_market_selector.py -v` (extend existing tests)

---

- [ ] **9. Extend `backend/app/prediction/model_orchestrator.py` to wire Group 5 components**
  
  **What:** Add optional uncertainty and disagreement to ModelOrchestrationResult and integration classes.
  
  **Modifications to model_orchestrator.py:**
  ```python
  # Extend ModelOrchestrationResult dataclass:
  @dataclass
  class ModelOrchestrationResult:
      # ... existing fields ...
      
      # NEW Group 5 fields (optional, backward compatible)
      model_disagreement: Optional[ModelDisagreementResult] = None
      uncertainty_assessment: Optional[UncertaintyAssessment] = None
      shot_market_predictions: Optional[Dict[ShotMarketType, ShotMarketPrediction]] = None
  
  # Create new integration class:
  class UncertaintyIntegration:
      """Integration layer for uncertainty assessment."""
      
      def __init__(
          self,
          disagreement_analyzer: Optional[ModelDisagreementAnalyzer] = None,
          uncertainty_engine: Optional[UncertaintyEngine] = None
      ):
          self.disagreement_analyzer = disagreement_analyzer or ModelDisagreementAnalyzer()
          self.uncertainty_engine = uncertainty_engine or UncertaintyEngine()
      
      def assess_uncertainty(
          self,
          orchestration_result: ModelOrchestrationResult,
          snapshot: MatchFeatureSnapshot,
          calibration_status: CalibrationStatus,
          market_type: MarketType = MarketType.MATCH_RESULT_1X2
      ) -> Tuple[ModelDisagreementResult, UncertaintyAssessment]:
          """Assess model disagreement and uncertainty."""
          # Analyze disagreement
          disagreement = self.disagreement_analyzer.analyze(orchestration_result, "home_win")
          
          # Get feature availability
          feature_selector = MarketFeatureSelector()
          feature_avail = feature_selector.get_feature_availability(market_type, snapshot)
          
          # Get data quality
          data_quality = snapshot.data_quality_report.overall_score if snapshot.data_quality_report else 0.5
          
          # Get sample size
          n_matches = self._extract_n_matches(snapshot)
          
          # Assess uncertainty
          uncertainty = self.uncertainty_engine.assess(
              model_disagreement=disagreement,
              data_quality_score=data_quality,
              feature_availability=feature_avail,
              sample_size=n_matches,
              calibration_status=calibration_status.value
          )
          
          return (disagreement, uncertainty)
  
  # Create shot market integration:
  class ShotMarketIntegration:
      """Integration layer for shot market predictions."""
      
      def __init__(self, engine: Optional[ShotMarketEngine] = None):
          self.engine = engine or ShotMarketEngine(session=None)
      
      def predict_shot_markets(
          self,
          snapshot: MatchFeatureSnapshot
      ) -> Dict[ShotMarketType, ShotMarketPrediction]:
          """Predict all shot markets from snapshot."""
          return self.engine.predict_all_shot_markets(snapshot)
  ```
  
  **Files:** `backend/app/prediction/model_orchestrator.py`
  
  **Verify:** Run `pytest backend/tests/prediction/test_model_orchestrator.py -v` (extend existing tests)

---

### TESTING

---

- [ ] **10. Create comprehensive test suite**
  
  **Test files to create:**
  
  1. `backend/tests/prediction/test_market_features.py`
     - `TestMarketType`: Test enum values
     - `TestMarketFeatureEligibility`: Test feature mappings for each market
     - `TestMarketFeatureSelector`:
       - `test_get_eligible_features_1x2`: Verify 1X2 features extracted
       - `test_get_eligible_features_shots`: Verify shot features extracted
       - `test_feature_availability_full`: All features available
       - `test_feature_availability_partial`: Some features missing
       - `test_feature_availability_empty`: No features available
  
  2. `backend/tests/prediction/test_shot_market_engine.py`
     - `TestShotMarketEngine`:
       - `test_predict_team_shots_sufficient_data`: Valid shot prediction with Poisson
       - `test_predict_team_shots_overdispersed`: Negative Binomial selected
       - `test_predict_team_shots_insufficient_data`: Returns unavailable
       - `test_predict_team_sot`: SOT threshold predictions
       - `test_predict_total_shots`: Combined home+away shots
       - `test_predict_all_shot_markets`: Full shot market suite
  
  3. `backend/tests/prediction/test_model_disagreement.py`
     - `TestModelDisagreementAnalyzer`:
       - `test_analyze_high_agreement`: All models agree (std ~0)
       - `test_analyze_low_agreement`: Models disagree (std high)
       - `test_analyze_all_outcomes`: Home/draw/away disagreement
       - `test_disagreement_label`: HIGH/MEDIUM/LOW labeling
  
  4. `backend/tests/prediction/test_uncertainty_engine.py`
     - `TestUncertaintyEngine`:
       - `test_assess_low_uncertainty`: Good data, fitted calibration, high agreement
       - `test_assess_high_uncertainty`: Poor data, no calibration, low agreement
       - `test_uncertainty_components`: Individual component calculations
       - `test_uncertainty_label`: LOW/MEDIUM/HIGH labeling
  
  5. `backend/tests/prediction/test_market_reliability.py`
     - `TestMarketReliabilityCalculator`:
       - `test_calculate_high_reliability`: Strong conditions
       - `test_calculate_low_reliability`: Weak conditions
       - `test_recommendation_strong_bet`: High reliability + high probability
       - `test_recommendation_pass`: Medium reliability
       - `test_recommendation_avoid`: Low reliability
  
  6. Extend `backend/tests/prediction/test_calibration_engine.py`
     - `TestCalibrationStatus`: Test status enum transitions
     - `TestTemporalProtection`: Verify cutoff_date filtering
     - `TestMarketSpecificCalibration`: Test market-specific stub
  
  7. Extend `backend/tests/prediction/test_market_selector.py`
     - `TestUncertaintyFiltering`: Verify high uncertainty → PASS
     - `TestShotMarketSelection`: Shot market candidates evaluated
     - `TestPassReasonUncertainty`: "high_uncertainty" pass reason
  
  8. Extend `backend/tests/prediction/test_model_orchestrator.py`
     - `TestUncertaintyIntegration`: Wiring uncertainty assessment
     - `TestShotMarketIntegration`: Wiring shot markets
     - `TestBackwardCompatibility`: Old code still works with new optional fields
  
  **Verification command:** `pytest backend/tests/prediction/ -v --tb=short`
  
  **Expected:** All new tests pass + existing tests remain passing (no regressions)
  
  **Files:** All test files listed above (8 new/extended test files)

---

### INTEGRATION & WIRING

---

- [ ] **11. Integration wiring in model_orchestrator.py**
  
  **What:** Wire all Group 5 components into the existing prediction pipeline flow.
  
  **Specific changes in ModelOrchestrator or new orchestration helper:**
  
  ```python
  # Add to ModelOrchestrator or create new PredictionPipeline class:
  
  class PredictionPipeline:
      """Full prediction pipeline with Group 5 integration."""
      
      def __init__(self, session):
          self.session = session
          self.orchestrator = ModelOrchestrator.create_default_registry()
          self.ensemble_integration = EnsembleIntegration.create_default()
          self.calibration_integration = CalibrationIntegration.create_default()
          self.confidence_integration = ConfidenceIntegration.create_default()
          self.uncertainty_integration = UncertaintyIntegration()  # NEW
          self.shot_market_integration = ShotMarketIntegration()  # NEW
      
      def predict(self, snapshot: MatchFeatureSnapshot) -> Dict[str, Any]:
          """Run full prediction pipeline with Group 5 components."""
          
          # 1. Run models
          orch_result = self.orchestrator.run_all(snapshot)
          
          # 2. Ensemble
          ensemble_pred = self.ensemble_integration.combine_predictions(orch_result)
          if isinstance(ensemble_pred, ModelAvailability):
              return {"available": False, "reason": ensemble_pred.reason}
          
          # 3. Calibration
          calibrated_pred = self.calibration_integration.calibrate_prediction(ensemble_pred)
          calib_status = self.calibration_integration.calibrator.is_fitted
          calib_status_enum = CalibrationStatus.FITTED if calib_status else CalibrationStatus.NOT_FITTED
          
          # 4. Confidence
          confidence = self.confidence_integration.assess_confidence(
              snapshot=snapshot,
              orchestration_result=orch_result,
              ensemble_prediction=calibrated_pred,
              calibration_metadata={"brier_score": None}
          )
          
          # 5. NEW: Model disagreement + uncertainty
          disagreement, uncertainty = self.uncertainty_integration.assess_uncertainty(
              orchestration_result=orch_result,
              snapshot=snapshot,
              calibration_status=calib_status_enum,
              market_type=MarketType.MATCH_RESULT_1X2
          )
          
          # 6. NEW: Shot markets
          shot_markets = self.shot_market_integration.predict_shot_markets(snapshot)
          
          # 7. Market derivation
          market_engine = MarketDerivationEngine()
          market_probs = market_engine.derive(calibrated_pred.score_distribution)
          
          # 8. Smart market selector
          selector = SmartMarketSelector(
              min_confidence=0.4,
              min_probability=0.5,
              max_uncertainty=0.7  # NEW threshold
          )
          best_tip = selector.evaluate_and_select(
              market_probs=market_probs,
              confidence_assessment=confidence,
              odds_data=None,
              uncertainty_assessment=uncertainty,  # NEW
              model_disagreement=disagreement,  # NEW
              shot_market_predictions=shot_markets  # NEW
          )
          
          return {
              "available": True,
              "ensemble_prediction": calibrated_pred,
              "confidence": confidence,
              "disagreement": disagreement,  # NEW
              "uncertainty": uncertainty,  # NEW
              "shot_markets": shot_markets,  # NEW
              "market_probabilities": market_probs,
              "best_tip": best_tip
          }
  ```
  
  **Files:** `backend/app/prediction/model_orchestrator.py` or new `backend/app/prediction/prediction_pipeline.py`
  
  **Verify:** 
  - Run integration test: `pytest backend/tests/prediction/test_prediction_pipeline_integration.py -v`
  - Verify backward compatibility: existing code without Group 5 still works

---

- [ ] **12. Backward compatibility verification**
  
  **What:** Ensure existing code continues to work without Group 5 components.
  
  **Strategy:**
  - All new fields in dataclasses are `Optional` with `None` defaults
  - ModelOrchestrationResult.model_disagreement is Optional
  - SmartMarketSelector.evaluate_and_select has uncertainty/disagreement as Optional params
  - Old calling code continues to work:
    ```python
    # OLD CODE (still works):
    selector.evaluate_and_select(market_probs, confidence_assessment)
    
    # NEW CODE (with Group 5):
    selector.evaluate_and_select(
        market_probs, confidence_assessment,
        uncertainty_assessment=uncertainty,
        model_disagreement=disagreement
    )
    ```
  
  **Test approach:**
  - Create `test_backward_compatibility.py`
  - Call pipeline with OLD signatures
  - Verify no errors
  - Verify output structure unchanged (new fields absent or None)
  
  **Files:** `backend/tests/prediction/test_backward_compatibility.py` (new)
  
  **Verify:** Run `pytest backend/tests/prediction/test_backward_compatibility.py -v`

---

## VERIFICATION PLAN

### Unit Test Verification
```bash
# Run all new prediction tests
pytest backend/tests/prediction/ -v --tb=short

# Expected: All tests pass
# Target: 172 existing feature tests + ~30-40 new Group 5 tests = ~210 total
```

### Integration Test Verification
```bash
# Run full integration test
pytest backend/tests/prediction/test_prediction_pipeline_integration.py -v

# Expected: Full pipeline runs with Group 5 components
```

### Regression Test Verification
```bash
# Run existing tests to ensure no breakage
pytest backend/tests/features/ -v --tb=short

# Expected: 172 tests still passing (no regressions)
```

### Type Checking (if mypy configured)
```bash
mypy backend/app/prediction/
```

---

## DEPENDENCIES & IMPORTS

All new modules depend on:
- **Existing modules:** `interfaces.py`, `ensemble_engine.py`, `confidence_engine.py`, `calibration_engine.py`, `market_derivation.py`, `market_selector.py`, `feature_snapshot.py`
- **Feature modules:** `shot_intelligence.py`, `shot_production.py`
- **Standard library:** `dataclasses`, `typing`, `datetime`, `enum`
- **Third-party:** `scipy.stats` (already used in shot_production.py)

No new external dependencies required.

---

## CRITICAL CONSTRAINTS

1. **DO NOT create a second prediction engine** — reuse existing 7 models
2. **DO NOT create a second feature snapshot** — extend existing MatchFeatureSnapshot
3. **DO NOT assume feature weights** — only declare eligibility
4. **DO NOT fabricate data** — None when unavailable
5. **DO NOT conflate uncertainty with probability** — separate concepts
6. **Preserve backward compatibility** — all new fields Optional
7. **Follow existing patterns** — reuse MatchWithStatistics, DataQualityReport patterns
8. **Temporal validity** — strict < comparison with before_datetime
9. **Test coverage** — every new component has tests

---

## SUCCESS CRITERIA

Group 5 is complete when:

1. ✅ Market-specific feature eligibility defined for 9 markets
2. ✅ Shot market predictions working for 4 shot market types
3. ✅ Model disagreement properly extracted and formalized
4. ✅ Uncertainty assessment combines 6 measurable components
5. ✅ Calibration status tracking with temporal protection
6. ✅ Market reliability calculator combining all factors
7. ✅ Smart Market Selector filters by uncertainty
8. ✅ All components integrated into model orchestration
9. ✅ Full test suite passing (~210 tests)
10. ✅ Backward compatibility verified
11. ✅ No regressions in existing 172 feature tests

---

## WHAT GROUP 5 DOES NOT IMPLEMENT

**OUT OF SCOPE FOR GROUP 5:**

- Walk-forward backtesting (Group 6)
- Optimal feature weights per market (Group 6)
- Calibration training on historical data (Group 6)
- Market-specific calibration training (Group 6)
- Performance validation (Group 6)
- Self-evaluation (Group 7)
- ROI tracking (Group 7)
- Calibration drift detection (Group 7)

Group 5 provides the **infrastructure and measurement** for these capabilities.

Group 6 will **validate and optimize** using this infrastructure.

---

## IMPLEMENTATION ORDER

Follow this sequence:

1. **Market features** (step 1) — foundation
2. **Shot market structures** (step 2) — interfaces
3. **Shot market engine** (step 3) — shot predictions
4. **Model disagreement** (step 4) — extract from ensemble
5. **Uncertainty engine** (step 5) — combine components
6. **Calibration extensions** (step 6) — add status tracking
7. **Market reliability** (step 7) — combine metrics
8. **Market selector extensions** (step 8) — add filtering
9. **Orchestrator wiring** (step 9) — integrate
10. **Testing** (step 10) — verify all components
11. **Integration** (step 11) — full pipeline
12. **Backward compatibility** (step 12) — verify no breakage

Each step leaves the codebase in a buildable, testable state.

---

## END OF PLAN

This plan extends the existing architecture without replacing any working components.

All 7 models remain.
Ensemble engine remains.
Calibration engine extended.
Confidence engine reused.
Smart Market Selector extended.

Group 5 adds measurement infrastructure for model disagreement, uncertainty, and market-specific modeling.

Group 6 will use this infrastructure for validation and optimization.

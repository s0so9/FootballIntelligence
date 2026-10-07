# Implementation Plan: Shot Market Engine + Walk-Forward Validation

This plan implements the Shot Market Engine completion and real historical walk-forward validation for the TUTAR X Football Intelligence platform.

**Critical Constraints:**
- NEVER fabricate probabilities, statistics, or results
- TEMPORAL LEAKAGE: prediction timestamp T only uses data where event_timestamp < T (STRICT <, not <=)
- DO NOT rebuild existing architecture
- DO NOT create mock historical results presented as real
- IF insufficient data: return PASS / INSUFFICIENT_HISTORICAL_SAMPLE
- PRESERVE all existing prediction engine functionality

---

## FEAT-001: Historical Coverage + Shot Intelligence in Snapshot

**What:** Inspect real database for shot coverage and extend MatchFeatureSnapshot to include shot intelligence fields.

**Files:**
- Create: `backend/scripts/inspect_historical_coverage.py`
- Modify: `backend/app/prediction/feature_snapshot.py`
- Modify: `backend/app/features/feature_engineering.py` (or `advanced_feature_engineering.py` where `build_snapshot` lives)

**Steps:**

1. **Create inspection script** following pattern in `validate_data_coverage.py`:
   - Query finished matches: `Match.status == 'FINISHED'`
   - Count shot coverage: `shots_total IS NOT NULL`
   - Count SOT coverage: `shots_on_target IS NOT NULL`
   - Count xG coverage: `xg IS NOT NULL`
   - Get date range: `MIN(scheduled_at)`, `MAX(scheduled_at)`
   - Get competition distribution: `GROUP BY competition_id`
   - Print structured report
   - Handle empty DB: print `INSUFFICIENT_HISTORICAL_SAMPLE`

2. **Extend MatchFeatureSnapshot** in `feature_snapshot.py`:
   - Add fields after `common_opponent_intel`:
     ```python
     home_shot_intelligence: Optional[ShotIntelligenceMetrics] = None
     away_shot_intelligence: Optional[ShotIntelligenceMetrics] = None
     ```
   - Import `ShotIntelligenceMetrics` from `app.features.shot_intelligence`
   - Update `get_feature_dict()` to extract shot features when available:
     - `home_shots_per_match`
     - `away_shots_per_match`
     - `home_sot_per_match`
     - `away_sot_per_match`
     - `home_xg_per_match`
     - `away_xg_per_match`

3. **Extend AdvancedFeatureEngineer.build_snapshot()**:
   - After building snapshot, call `ShotIntelligenceCalculator.calculate_shot_metrics()` for home and away teams
   - Pass `before_datetime=match.scheduled_at` for temporal validity
   - Populate `snapshot.home_shot_intelligence` and `snapshot.away_shot_intelligence`
   - Handle insufficient data gracefully (low `data_quality_score`)

**Verification:**
```powershell
cd backend
.venv\Scripts\python.exe scripts\inspect_historical_coverage.py
# Should print coverage report without errors

.venv\Scripts\python.exe -m pytest tests\features\test_feature_engineering.py -v
# All existing tests must pass (no regression)
```

---

## FEAT-002: Complete Shot Market Engine

**What:** Transform `predict_all_shot_markets()` stub into full production implementation.

**Files:**
- Modify: `backend/app/prediction/shot_market_engine.py`
- Create: `backend/tests/prediction/test_shot_market_engine.py`

**Steps:**

1. **Read existing code**:
   - `shot_market_engine.py` (understand stub)
   - `shot_intelligence.py` (calculator interface)
   - `shot_production.py` (distribution fitting)
   - `interfaces.py` (ShotMarketPrediction structures)

2. **Implement predict_all_shot_markets()**:
   - Check if `snapshot.home_shot_intelligence` and `snapshot.away_shot_intelligence` available
   - If either is `None`, return empty dict `{}`
   - Extract raw shot counts using `ShotIntelligenceCalculator.get_raw_shot_counts()` for home/away
   - Call `self.shot_calc.calculate()` for home team (shots + SOT)
   - Call `self.shot_calc.calculate()` for away team (shots + SOT)
   - Call `self.shot_calc.calculate_total()` for total shots
   - Build predictions using helper methods
   - Return `Dict[ShotMarketType, List[ShotMarketPrediction]]`:
     - `TEAM_SHOTS` → `[home_pred, away_pred]`
     - `TEAM_SHOTS_ON_TARGET` → `[home_sot, away_sot]`
     - `TOTAL_SHOTS` → `[total_pred]`

3. **Create _build_team_sot_prediction() helper**:
   - Accept `team_id`, `shot_production`, `market_type`
   - Extract SOT thresholds: `over_3_sot_prob`, `over_4_sot_prob`, `over_5_sot_prob`, `over_6_sot_prob`
   - Build `ShotMarketThreshold` objects for each
   - Determine `DistributionType` from `shot_production.sot_distribution_model`
   - Return `ShotMarketPrediction` with thresholds and parameters

4. **Create _build_total_shots_prediction() helper**:
   - Accept `shot_production` from `calculate_total()`
   - Extract total thresholds: `total_over_20_prob`, `total_over_22_prob`, `total_over_25_prob`, `total_over_30_prob`
   - Build `ShotMarketThreshold` objects
   - Return `ShotMarketPrediction` with `team_id='total'`, `market_type=TOTAL_SHOTS`

5. **Handle insufficient data**:
   - When `shots_distribution_model == 'none'` → set `distribution_model=UNAVAILABLE`, `available=False`, `unavailability_reason='insufficient_shot_data'`
   - When `sample_size < 5` → `unavailability_reason='insufficient_historical_sample'`
   - When distribution fitting fails → `unavailability_reason='distribution_fitting_failed'`

6. **Write comprehensive tests** in `test_shot_market_engine.py`:
   - Test: complete shot intelligence → all market types returned
   - Test: team shots thresholds 10+/12+/15+/18+/20+ present
   - Test: SOT thresholds 3+/4+/5+/6+ present
   - Test: total shots thresholds 20+/22+/25+/30+ present
   - Test: Poisson selected when variance ≈ mean
   - Test: Negative Binomial selected when variance > mean
   - Test: insufficient data → `available=False` with `unavailability_reason`
   - Test: shot intelligence absent → empty dict (not crash)
   - Test: distribution parameters populated correctly

**Verification:**
```powershell
cd backend
.venv\Scripts\python.exe -m pytest tests\prediction\test_shot_market_engine.py -v
# All tests must pass
```

---

## FEAT-003: Shot Markets in Market Selector + Prediction Service

**What:** Integrate shot markets into Smart Market Selector and PredictionService.

**Files:**
- Modify: `backend/app/prediction/market_selector.py`
- Modify: `backend/app/prediction/service.py`
- Create: `backend/tests/prediction/test_market_selector_shot_integration.py`

**Steps:**

1. **Read existing code**:
   - `market_selector.py` (understand `evaluate_and_select()`, `CandidateEvaluation`)
   - `service.py` (understand `generate_full_prediction()` flow)

2. **Extend SmartMarketSelector.evaluate_and_select()**:
   - Add parameter: `shot_market_predictions: Optional[Dict[ShotMarketType, List[ShotMarketPrediction]]] = None`
   - When provided, iterate through shot markets
   - Evaluate each threshold as a candidate using same logic as existing markets
   - Check probability, confidence, data quality, uncertainty

3. **Create _evaluate_shot_market_candidate() helper**:
   - Accept `shot_market_prediction`, `threshold`
   - Build `CandidateEvaluation` with:
     - `market='{team_name} {threshold}+ Shots'`
     - `selection=format_selection_string`
     - `model_probability=threshold.over_probability`
     - `confidence=derived from data_quality and uncertainty`
     - `data_quality=threshold.data_quality`
   - Calculate `selection_score` using existing scoring logic
   - Check qualification: `min_probability`, `min_confidence` thresholds

4. **Extend _select_best_qualified_candidate()**:
   - Include shot market candidates in comparison
   - Shot markets compete on `selection_score` (NOT just probability)
   - Evaluate: calibrated probability, uncertainty, data quality, threshold stability, sample size
   - Do NOT simply select highest probability

5. **Extend PredictionService.generate_full_prediction()**:
   - After calling `model_orchestrator`, before market selection:
   - Call `shot_market_engine.predict_all_shot_markets(snapshot)`
   - Pass shot market predictions to `market_selector.evaluate_and_select()`
   - Store shot market predictions in `AnalysisContext` for AI Analyst

6. **Handle PASS for weak shot markets**:
   - If best shot market has:
     - Low confidence (< `min_confidence`)
     - High uncertainty (> `max_uncertainty`)
     - Insufficient data (`data_quality < threshold`)
   - Include in `PassDecision.best_market_details` with rejection reason:
     - `'insufficient_shot_data'`
     - `'weak_shot_conviction'`
     - `'high_shot_uncertainty'`

7. **Write integration tests** in `test_market_selector_shot_integration.py`:
   - Test: shot markets evaluated alongside 1X2 markets
   - Test: best shot market selected when highest `selection_score`
   - Test: weak shot markets trigger PASS
   - Test: shot market with insufficient data excluded
   - Test: candidate structure matches `CandidateEvaluation`

**Verification:**
```powershell
cd backend
.venv\Scripts\python.exe -m pytest tests\prediction\test_market_selector_shot_integration.py -v
# All tests must pass

.venv\Scripts\python.exe -m pytest tests\prediction\test_service.py -v
# Existing service tests must still pass (no regression)
```

---

## FEAT-004: Temporal Leakage Protection Tests

**What:** Comprehensive tests ensuring shot market predictions never use post-match data.

**Files:**
- Create: `backend/tests/backtesting/test_temporal_leakage.py`

**Steps:**

1. **Read existing temporal leakage tests**:
   - `tests/features/test_group2_temporal_leakage.py` (understand pattern)

2. **Create test file** `tests/backtesting/test_temporal_leakage.py`:
   - Import: `pytest`, `datetime`, `ShotMarketEngine`, `ShotIntelligenceCalculator`, `MatchWithStatistics`, `Match`, `TeamMatchStatistic`
   - Create fixtures for mock session, calculator instances

3. **Write test_shot_market_excludes_target_match()**:
   - Create target match at time T
   - Create 5 historical matches before T with shot data
   - Call `predict_all_shot_markets()` with snapshot at T
   - Assert target match statistics (shots_total, shots_on_target) NOT used
   - Verify `sample_size` matches historical count (excludes target)

4. **Write test_shot_market_excludes_future_matches()**:
   - Create target match at T
   - Create 3 matches before T, 2 matches after T
   - Call `predict_all_shot_markets()` with `before_datetime=T`
   - Assert `sample_size=3` (only pre-T matches)

5. **Write test_shot_market_strict_less_than_boundary()**:
   - Create target match at exactly T=2024-01-15 12:00:00
   - Create match at T-1 day (included), T exactly (EXCLUDED), T+1 day (excluded)
   - Verify prediction uses only T-1 day match
   - Tests strict `<` comparison (not `<=`)

6. **Write test_shot_intelligence_snapshot_isolation()**:
   - Build `MatchFeatureSnapshot` for target match
   - Verify `snapshot.home_shot_intelligence` and `snapshot.away_shot_intelligence` computed using only historical data
   - Check `sample_size`, `data_quality_score`
   - Verify target match's final `shots_total` NOT included

7. **Write test_post_match_stats_never_in_pre_match_features()**:
   - Create finished match with final statistics (shots_total=15, shots_on_target=7, xg=2.1)
   - Build snapshot at `scheduled_at` timestamp
   - Call shot market prediction
   - Verify prediction uses only previous matches, NOT target match final stats
   - Assert `sample_size` excludes target

8. **Write test_all_shot_calculators_respect_temporal_cutoff()**:
   - Integration test: verify `ShotIntelligenceCalculator`, `ShotProductionCalculator`, `ShotMarketEngine` all use strict `<` consistently
   - Create timeline: T-5, T-3, T-1, T (target), T+2
   - Build prediction with `before_datetime=T`
   - Assert `sample_size=3` across all calculators

**Verification:**
```powershell
cd backend
.venv\Scripts\python.exe -m pytest tests\backtesting\test_temporal_leakage.py -v
# All tests must pass (no leakage detected)
```

---

## FEAT-005: Walk-Forward Validation Infrastructure + Execution

**What:** Implement WalkForwardValidator and execution script for real historical validation.

**Files:**
- Create: `backend/app/backtesting/__init__.py`
- Create: `backend/app/backtesting/walk_forward.py`
- Create: `backend/scripts/run_walk_forward.py`
- Create: `backend/tests/backtesting/test_walk_forward.py`

**Steps:**

1. **Create backtesting module**:
   - `backend/app/backtesting/__init__.py` (empty or with imports)
   - `backend/app/backtesting/walk_forward.py` (main implementation)

2. **Define data structures** in `walk_forward.py`:
   ```python
   @dataclass
   class EvaluationMetrics:
       sample_size: int
       brier_score: Optional[float]
       log_loss: Optional[float]
       hit_rate: Optional[float]
       calibration_error: Optional[float]
       mean_probability: Optional[float]
       mean_actual: Optional[float]
   
   @dataclass
   class VariantResults:
       variant_name: str
       thresholds: Dict[int, EvaluationMetrics]  # 10+, 12+, 15+, 18+, 20+
   
   class ShotMarketVariant(Enum):
       BASELINE = "baseline"  # Simple historical average only
       PLUS_OPPONENT = "plus_opponent"  # + opponent suppression
       PLUS_RECENCY = "plus_recency"  # + recency weighting
       PLUS_SHOT_QUALITY = "plus_shot_quality"  # + xG/shot quality
       PLUS_HOME_AWAY = "plus_home_away"  # + venue split
       FULL = "full"  # All shot intelligence features
   ```

3. **Implement WalkForwardValidator class**:
   ```python
   class WalkForwardValidator:
       def __init__(self, session, shot_market_engine, feature_engineer, min_matches=10):
           self.session = session
           self.shot_market_engine = shot_market_engine
           self.feature_engineer = feature_engineer
           self.min_matches = min_matches
       
       def validate(self, variant: ShotMarketVariant) -> VariantResults:
           # Query finished matches with shot data, ordered chronologically
           # For each match (skip first min_matches as warmup):
           #   1. Freeze prediction_timestamp = match.scheduled_at
           #   2. Build MatchFeatureSnapshot using only data < prediction_timestamp
           #   3. Call shot_market_engine.predict_all_shot_markets()
           #   4. Store prediction
           #   5. Load actual match statistics AFTER prediction
           #   6. Evaluate prediction vs actual for each threshold
           #   7. Calculate Brier score, log loss, hit rate
           # Return VariantResults with metrics per threshold
   ```

4. **Implement baseline comparison**:
   - For each variant (BASELINE, PLUS_OPPONENT, PLUS_RECENCY, PLUS_SHOT_QUALITY, PLUS_HOME_AWAY, FULL):
     - Configure `ShotIntelligenceCalculator` with appropriate feature flags
     - BASELINE: use only `shots_total_per_match` (simple average)
     - PLUS_OPPONENT: add `shots_against_per_match`
     - PLUS_RECENCY: add `shots_per_match_weighted`
     - PLUS_SHOT_QUALITY: add `xg_per_shot`
     - PLUS_HOME_AWAY: add venue split (`shots_home_per_match` / `shots_away_per_match`)
     - FULL: all shot intelligence features
   - Run walk-forward for each variant, store results

5. **Implement calculate_evaluation_metrics() helper**:
   - Accept list of `(probability, actual_binary)` tuples
   - Calculate Brier score: `mean((p - a)^2)`
   - Calculate log loss: `-mean(a*log(p) + (1-a)*log(1-p))` with epsilon
   - Calculate hit rate: proportion where `(p >= 0.5 and a == 1) or (p < 0.5 and a == 0)`
   - Calculate calibration error using binning approach from `calibration.py`
   - Return `EvaluationMetrics`

6. **Create execution script** `run_walk_forward.py`:
   - Initialize `SessionLocal`, `ShotMarketEngine`, `AdvancedFeatureEngineer`
   - Create `WalkForwardValidator`
   - Call `validate()` for all variants
   - Collect `VariantResults` for each
   - Write results to `c:\FootballIntelligence\.agents\tasks\shot-market-validation\results.json`:
     ```json
     {
       "variants": [
         {
           "variant_name": "baseline",
           "thresholds": {
             "10": {"brier_score": 0.23, "log_loss": 0.65, "hit_rate": 0.67, "sample_size": 150},
             "12": {...},
             ...
           }
         },
         ...
       ],
       "summary": {
         "best_variant": "full",
         "improvement_over_baseline": 0.08,
         "total_matches_evaluated": 150
       }
     }
     ```
   - Print summary to console

7. **Handle insufficient data**:
   - If query returns < `min_matches` finished matches with shot data:
   - Print: `INSUFFICIENT_HISTORICAL_SAMPLE: Found X finished matches with shot data, need at least Y. Shot market walk-forward validation cannot proceed.`
   - Write to `results.json`:
     ```json
     {
       "status": "insufficient_data",
       "message": "...",
       "matches_found": X,
       "matches_required": Y
     }
     ```
   - Exit with code 0 (not an error, expected condition)

8. **Add temporal leakage detection**:
   - In `WalkForwardValidator.validate()`, before loading actual stats:
   - Assert `snapshot.home_shot_intelligence.sample_size < total_historical_matches`
   - Target match must be excluded
   - If assertion fails, raise `TemporalLeakageError` with details
   - This is a validation safety check

9. **Write walk-forward tests** in `test_walk_forward.py`:
   - Test: `validate()` processes matches chronologically
   - Test: each prediction uses only historical data
   - Test: baseline variant uses only simple features
   - Test: FULL variant uses all shot intelligence features
   - Test: evaluation metrics calculated correctly (Brier, log loss, hit rate)
   - Test: insufficient data handled gracefully
   - Test: temporal leakage detection triggers when violated

**Verification:**
```powershell
cd backend
.venv\Scripts\python.exe -m pytest tests\backtesting\test_walk_forward.py -v
# All tests must pass

.venv\Scripts\python.exe scripts\run_walk_forward.py
# Should run successfully and write results.json
# If insufficient data, should print graceful message
# If sufficient data, should print summary with Brier scores

# Verify results file
Test-Path c:\FootballIntelligence\.agents\tasks\shot-market-validation\results.json
# Should be True (or message about insufficient data)
```

---

## Summary

This plan implements:

1. **Historical coverage inspection** — verify real database state
2. **Shot intelligence in snapshot** — extend feature snapshot for shot markets
3. **Complete shot market engine** — full implementation with threshold probabilities
4. **Market selector integration** — shot markets compete with 1X2/BTTS/goals
5. **Temporal leakage tests** — ensure no post-match data leakage
6. **Walk-forward validation** — real historical evaluation with baseline comparison

All work follows existing patterns, preserves existing functionality, and includes comprehensive tests and verification steps.

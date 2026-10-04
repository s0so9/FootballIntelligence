# MENSIONE Prediction Engine Core — Implementation Plan

**Status:** Ready for Implementation  
**Approved Design:** c:\FootballIntelligence\.agents\tasks\prediction-engine\design.md  
**Original Requirements:** User request to implement production-grade prediction engine core  
**Architecture:** Multi-model ensemble with calibration, confidence assessment, and market derivation

---

## IMPLEMENTATION STRATEGY

This plan implements the MENSIONE Prediction Engine Core in 5 sequential features (FEATs), each building on the previous. The work is decomposed to enable:

1. Independent verification at each stage
2. Incremental build-up of complexity
3. Preservation of existing 651 passing tests
4. Backward compatibility with existing AnalysisContext

**Dependencies:** Each FEAT must be completed before the next begins.

**Verification:** After each FEAT, run the full test suite to ensure no regressions.

---

## FEAT-001: Core Infrastructure & Interfaces

**Purpose:** Foundation that all models will use

### Files to Create

1. **c:\FootballIntelligence\backend\app\prediction\interfaces.py**
   - `PredictionModel` abstract base class with `predict()`, `get_metadata()`, `check_requirements()`
   - `ModelPrediction` dataclass with all probability fields, validation, normalization
   - `ModelAvailability` dataclass for unavailable models
   - `ModelMetadata` dataclass with model information
   
2. **c:\FootballIntelligence\backend\app\prediction\data_quality.py**
   - `DataQualityCheck` dataclass
   - `DataQualityReport` dataclass
   - `DataQualityGate` class with 5 checks:
     - `_check_match_count()` - sufficient historical matches
     - `_check_feature_completeness()` - % features available
     - `_check_data_freshness()` - data recency
     - `_check_critical_features()` - required features present
     - `_check_data_consistency()` - validate values
   
3. **c:\FootballIntelligence\backend\app\prediction\model_registry.py**
   - `ModelRegistry` class
   - `register_model()` - register model instance
   - `get_model(model_id)` - retrieve by ID
   - `get_models_by_type(model_type)` - retrieve by type
   - `list_models()` - all registered models

### Files to Modify

4. **c:\FootballIntelligence\backend\app\domain\prediction.py**
   - Add `PlayerImpactResult` dataclass
   - Add `TacticalEffect` dataclass
   - Add `TacticalAdvantage` dataclass
   - Add `ConfidenceAssessment` dataclass
   - Add `PredictionWithOutcome` dataclass
   - Keep existing Model, ModelMetadata, Prediction unchanged

### Test Files to Create

5. **c:\FootballIntelligence\backend\tests\test_prediction_interfaces.py**
   - Test ModelPrediction probability validation (range, sum)
   - Test ModelPrediction.validate_probabilities()
   - Test ModelPrediction.normalize_probabilities()
   - Test ModelAvailability construction
   
6. **c:\FootballIntelligence\backend\tests\test_data_quality.py**
   - Test DataQualityGate with sufficient data → pass
   - Test with insufficient match count → critical failure
   - Test with missing features → high failure
   - Test with stale data → medium failure
   - Test overall score calculation
   - Test blocked model identification

### Dependencies
- None (foundational)

### Verification
```powershell
cd c:\FootballIntelligence\backend
python -m pytest tests/test_prediction_interfaces.py -v
python -m pytest tests/test_data_quality.py -v
python -m pytest tests/ -v --tb=short
```

**Expected:** All new tests pass, all 651 existing tests pass.

---

## FEAT-002: Refactor Existing Models to New Interface

**Purpose:** Adapt existing working models (Poisson, Dixon-Coles, Elo, Negative Binomial) to implement PredictionModel interface while preserving functionality

### Files to Modify

1. **c:\FootballIntelligence\backend\app\prediction\poisson.py**
   - Make `PoissonModel` inherit from `PredictionModel`
   - Implement `predict(match_id, features, match_context) -> ModelPrediction | ModelAvailability`
   - Implement `get_metadata() -> ModelMetadata`
   - Implement `check_requirements() -> (bool, List[str])`
   - Keep existing `PoissonPrediction` dataclass for internal calculations
   - Map internal PoissonPrediction to ModelPrediction for return
   - Add `_calculate_confidence()` based on sample size
   - Add `_calculate_data_quality()` based on feature availability
   
2. **c:\FootballIntelligence\backend\app\prediction\dixon_coles.py**
   - Same refactoring as Poisson
   - Implement all 3 PredictionModel methods
   - Preserve existing Dixon-Coles tau correction logic
   
3. **c:\FootballIntelligence\backend\app\prediction\elo.py**
   - Same refactoring
   - Implement interface methods
   - Preserve existing Elo rating update logic
   
4. **c:\FootballIntelligence\backend\app\prediction\negative_binomial.py**
   - Same refactoring
   - Handle r parameter calculation
   - Return ModelAvailability if r ≤ 0

### Test Files to Modify

5. **c:\FootballIntelligence\backend\tests\test_poisson.py**
   - Add tests for new `predict(match_id, features, match_context)` interface
   - Test ModelAvailability returned when features missing
   - Test get_metadata() returns correct ModelMetadata
   - Test check_requirements() identifies missing data
   - Keep existing legacy tests for backward compatibility
   
6. **c:\FootballIntelligence\backend\tests\test_elo.py**
   - Same interface tests as Poisson
   
7. **c:\FootballIntelligence\backend\tests\test_negative_binomial.py**
   - Same interface tests

### Test Files to Create

8. **c:\FootballIntelligence\backend\tests\test_dixon_coles_interface.py**
   - Test Dixon-Coles implementation of PredictionModel interface
   - Test rho correction still applied correctly
   - Test unavailability handling

### Dependencies
- FEAT-001 complete (interfaces must exist)

### Verification
```powershell
cd c:\FootballIntelligence\backend
python -m pytest tests/test_poisson.py -v
python -m pytest tests/test_elo.py -v
python -m pytest tests/test_negative_binomial.py -v
python -m pytest tests/test_dixon_coles_interface.py -v
python -m pytest tests/ -k "not slow" --tb=short
```

**Expected:** All model tests pass, models correctly implement interface, 651+ tests pass.

---

## FEAT-003: New Specialized Models

**Purpose:** Add Form-Adjusted, Logistic Regression (refactor), and Monte Carlo models

### Files to Create

1. **c:\FootballIntelligence\backend\app\prediction\form_adjusted.py**
   - `FormAdjustedModel` class implementing PredictionModel
   - Constructor: `__init__(base_model, form_weight, time_decay)`
   - `predict()` - gets base prediction, adjusts lambdas by form features
   - Form adjustment formula: `lambda_adjusted = lambda_base * (1 + form_weight * form_score)`
   - Time decay: recent matches weighted higher
   - Required features: `home_form_points_per_match`, `away_form_points_per_match`
   - `get_metadata()` - describes form adjustment approach
   - `check_requirements()` - needs base model + form features
   
2. **c:\FootballIntelligence\backend\app\prediction\monte_carlo.py**
   - `MonteCarloSimulation` class implementing PredictionModel
   - Constructor: `__init__(base_models, n_simulations=10000, seed=None)`
   - `predict()` - runs n simulations, each samples from ensemble distribution
   - Generates scoreline distribution from simulation results
   - Deterministic when seed provided
   - Convergence check: standard error of probabilities
   - Required: at least 1 base model available
   
### Files to Modify

3. **c:\FootballIntelligence\backend\app\prediction\logistic_regression.py**
   - Refactor existing `LogisticRegressionModel` to implement PredictionModel interface
   - Implement `predict()`, `get_metadata()`, `check_requirements()`
   - Handle missing features gracefully
   - Return ModelAvailability if insufficient features

4. **c:\FootballIntelligence\backend\app\prediction\model_registry.py**
   - Register form_adjusted_v1, monte_carlo_v1, logistic_regression_v1 in module init

### Test Files to Create

5. **c:\FootballIntelligence\backend\tests\test_form_adjusted.py**
   - Test form weight application to lambdas
   - Test time decay calculation
   - Test unavailability when form features missing
   - Test with various base models
   
6. **c:\FootballIntelligence\backend\tests\test_monte_carlo.py**
   - Test simulation convergence (probabilities stable)
   - Test deterministic reproduction with seed
   - Test distribution matches ensemble
   - Test performance with different n_simulations

### Test Files to Modify

7. **c:\FootballIntelligence\backend\tests\test_logistic_regression.py**
   - Add interface compliance tests
   - Test missing feature handling

### Dependencies
- FEAT-001 complete (interfaces)
- FEAT-002 complete (base models to wrap/use)

### Verification
```powershell
cd c:\FootballIntelligence\backend
python -m pytest tests/test_form_adjusted.py -v
python -m pytest tests/test_monte_carlo.py -v
python -m pytest tests/test_logistic_regression.py -v
python -m pytest tests/ --tb=short
```

**Expected:** All new model tests pass, 651+ tests pass.

---

## FEAT-004: Ensemble, Calibration, Confidence, Contextual Engines

**Purpose:** Combine models, calibrate probabilities, assess confidence, apply contextual adjustments

### Files to Create

1. **c:\FootballIntelligence\backend\app\prediction\ensemble_engine.py**
   - `EnsembleEngine` class
   - `combine_predictions(predictions: List[ModelPrediction]) -> EnsemblePrediction`
   - Weighting strategies: static, reliability_based, performance_based
   - Calculate model agreement score (std dev of probabilities)
   - Weighted averaging of probabilities
   - Merge scoreline distributions
   - Output: EnsemblePrediction with consensus metrics
   
2. **c:\FootballIntelligence\backend\app\prediction\calibration_engine.py**
   - `CalibrationEngine` class
   - `fit(historical_predictions: List[PredictionWithOutcome])`
   - Isotonic regression calibration per model
   - `calibrate(prediction: ModelPrediction) -> ModelPrediction`
   - Handle unseen probabilities via interpolation
   - Separate calibration per model_id and market_type
   
3. **c:\FootballIntelligence\backend\app\prediction\confidence_engine.py**
   - `ConfidenceEngine` class
   - `assess_confidence(prediction, data_quality_report, model_agreement) -> ConfidenceAssessment`
   - Factors: data quality score, model agreement, historical accuracy, feature completeness
   - Weighted combination into overall confidence [0-1]
   - Confidence tiers: HIGH (>0.75), MEDIUM (0.5-0.75), LOW (<0.5)
   
4. **c:\FootballIntelligence\backend\app\prediction\player_impact.py**
   - `PlayerImpactEngine` class
   - `calculate_impact(lineup_changes, player_stats, team_stats) -> PlayerImpactResult`
   - Adjusts xG based on confirmed lineup changes
   - Requires player statistics (xG, xA, minutes)
   - Never fabricates player data
   - Returns None impact if player data unavailable
   - Output: adjusted xG home/away, strength multipliers, player contributions
   
5. **c:\FootballIntelligence\backend\app\prediction\tactical_matchup.py**
   - `TacticalMatchupEngine` class
   - `analyze_matchup(home_tactical_features, away_tactical_features) -> TacticalAdvantage`
   - Rule-based matchup detection from structured features
   - Examples: "High press vs weak build-up", "Cross-heavy vs aerial weakness"
   - Output: xG adjustments, detected matchups, confidence
   - All conclusions derived from data (never invented)
   
6. **c:\FootballIntelligence\backend\app\prediction\contextual_adjuster.py**
   - `ContextualAdjuster` class
   - `apply_adjustments(ensemble_prediction, player_impact, tactical_advantage) -> ModelPrediction`
   - Combines player and tactical adjustments
   - Recalculates scoreline distribution with adjusted xG
   - Preserves probability consistency

### Test Files to Create

7. **c:\FootballIntelligence\backend\tests\test_ensemble_engine.py**
   - Test static weighting
   - Test reliability-based weighting
   - Test model agreement calculation
   - Test probability normalization
   - Test scoreline distribution merging
   
8. **c:\FootballIntelligence\backend\tests\test_calibration_engine.py**
   - Test isotonic regression fitting
   - Test calibration adjustment
   - Test interpolation for unseen probabilities
   - Test per-model calibration
   
9. **c:\FootballIntelligence\backend\tests\test_confidence_engine.py**
   - Test confidence calculation from multiple factors
   - Test tier assignment
   - Test factor weighting
   
10. **c:\FootballIntelligence\backend\tests\test_player_impact.py**
    - Test xG adjustment for lineup changes
    - Test handling missing player data (returns None impact)
    - Test replacement player effects
    
11. **c:\FootballIntelligence\backend\tests\test_tactical_matchup.py**
    - Test matchup rule detection
    - Test xG adjustment calculation
    - Test missing feature handling

### Dependencies
- FEAT-001 complete (interfaces, supporting structures)
- FEAT-002 complete (models to ensemble)
- FEAT-003 complete (more models for ensemble diversity)

### Verification
```powershell
cd c:\FootballIntelligence\backend
python -m pytest tests/test_ensemble_engine.py -v
python -m pytest tests/test_calibration_engine.py -v
python -m pytest tests/test_confidence_engine.py -v
python -m pytest tests/test_player_impact.py -v
python -m pytest tests/test_tactical_matchup.py -v
python -m pytest tests/ --tb=short
```

**Expected:** All engine tests pass, 651+ tests pass.

---

## FEAT-005: Orchestration, Markets, Pick, Persistence, Integration

**Purpose:** Complete end-to-end pipeline with orchestrator, market derivation, MENSIONE pick, database persistence, AnalysisContext enrichment

### Files to Create

1. **c:\FootballIntelligence\backend\app\prediction\market_derivation.py**
   - `MarketDerivationEngine` class
   - `derive_markets(scoreline_distribution) -> Dict[PredictionMarketType, MarketProbabilities]`
   - Derive from scoreline:
     - 1X2: sum scorelines by outcome
     - Over/Under: sum scorelines above/below line
     - BTTS: sum scorelines where both > 0 / either = 0
     - Correct Score: top N scorelines
   - Calculate fair odds: `1 / probability`
   - Validate probabilities sum to ~1.0
   
2. **c:\FootballIntelligence\backend\app\prediction\mensione_pick.py**
   - `MensionePickGenerator` class
   - `generate_pick(market_probabilities, confidence, market_odds) -> MensionePick`
   - Rank markets by expected value: `EV = (prob * market_odds) - 1`
   - Apply confidence threshold: only recommend if confidence >= threshold
   - Select highest EV market above threshold
   - Output: recommended outcome, probability, confidence, reasoning
   
3. **c:\FootballIntelligence\backend\app\prediction\engine.py**
   - `PredictionEngine` class - main orchestrator
   - Constructor: inject all engines (data quality, models, ensemble, calibration, confidence, contextual, market, pick)
   - `generate_prediction(match_id, as_of_date=None) -> EnrichedPrediction | PredictionUnavailable`
   - Pipeline:
     1. Load match from database
     2. Extract features (MatchFeatureExtractor)
     3. Data quality gate
     4. Invoke all registered models
     5. Ensemble predictions
     6. Calibrate ensemble
     7. Apply contextual adjustments
     8. Assess confidence
     9. Derive markets
     10. Generate MENSIONE pick
     11. Version and timestamp
   - Handle partial model availability
   - Return PredictionUnavailable if critical failure
   
4. **c:\FootballIntelligence\backend\app\prediction\persistence.py**
   - `PredictionPersistenceService` class
   - `save_prediction(prediction, match_id) -> str (prediction_id)`
   - `save_prediction_version(prediction_id, version_metadata)`
   - `get_prediction(prediction_id) -> Prediction`
   - `get_predictions_for_match(match_id) -> List[Prediction]`
   - Uses SQLAlchemy session

### Files to Modify

5. **c:\FootballIntelligence\backend\app\database\models.py**
   - Add `PredictionVersion` table:
     - id, prediction_id FK, version_number, generated_at, model_weights, ensemble_metadata
   - Add `PredictionRun` table:
     - id, run_timestamp, matches_predicted, models_used, average_confidence
   
6. **c:\FootballIntelligence\backend\app\analysis\context.py**
   - Read existing AnalysisContextBuilder
   - Add `enrich_with_predictions(context, prediction_engine_output) -> AnalysisContext`
   - Populate:
     - `model_predictions`
     - `models_used`
     - `ensemble_prediction`
     - `prediction_markets`
     - `model_calibration_info`
     - `historical_accuracy`
   - Maintain all existing fields (backward compatible)

### Database Migration

7. **Create Alembic migration**
   ```powershell
   cd c:\FootballIntelligence\backend
   alembic revision -m "add_prediction_versioning_tables"
   ```
   - Add prediction_versions table
   - Add prediction_runs table
   - Add indexes: (prediction_id), (run_timestamp)

### Test Files to Create

8. **c:\FootballIntelligence\backend\tests\test_market_derivation.py**
   - Test 1X2 derivation from scoreline
   - Test Over/Under for multiple lines
   - Test BTTS derivation
   - Test correct score top N
   - Test probability validation
   
9. **c:\FootballIntelligence\backend\tests\test_mensione_pick.py**
   - Test EV calculation
   - Test confidence threshold application
   - Test market ranking
   - Test pick selection logic
   
10. **c:\FootballIntelligence\backend\tests\test_prediction_engine.py**
    - Test full pipeline: match → prediction → markets → pick
    - Test with all models available
    - Test with partial model availability
    - Test with insufficient data (returns PredictionUnavailable)
    - Test feature extraction integration
    - Test contextual adjustment application
    
11. **c:\FootballIntelligence\backend\tests\test_prediction_persistence.py**
    - Test save prediction to database
    - Test retrieve prediction by ID
    - Test prediction versioning
    - Test prediction run tracking

### Dependencies
- FEAT-001 through FEAT-004 complete
- All engines implemented
- All models refactored

### Verification
```powershell
cd c:\FootballIntelligence\backend
alembic upgrade head
python -m pytest tests/test_market_derivation.py -v
python -m pytest tests/test_mensione_pick.py -v
python -m pytest tests/test_prediction_engine.py -v
python -m pytest tests/test_prediction_persistence.py -v
python -m pytest tests/ -v --tb=line
python -c "from app.prediction.engine import PredictionEngine; print('Import successful')"
```

**Expected:** All integration tests pass, full test suite passes (651+ tests), imports work, database migration applies cleanly.

---

## POST-IMPLEMENTATION VERIFICATION

After all 5 FEATs complete:

1. **Full Test Suite**
   ```powershell
   cd c:\FootballIntelligence\backend
   python -m pytest tests/ -v --tb=short --durations=10
   ```
   Expected: All tests pass, no regressions

2. **Import Verification**
   ```powershell
   python -c "from app.prediction.engine import PredictionEngine; from app.prediction.interfaces import PredictionModel; print('All imports OK')"
   ```

3. **Integration Smoke Test**
   ```python
   # Run in Python REPL from backend directory
   from app.prediction.engine import PredictionEngine
   from app.database.session import SessionLocal
   from app.providers.development import DevelopmentProvider
   
   # Initialize engine
   provider = DevelopmentProvider()
   engine = PredictionEngine(provider=provider, db_session=SessionLocal())
   
   # Generate prediction for a match
   match_id = "test_match_123"
   result = engine.generate_prediction(match_id)
   print(f"Prediction generated: {result}")
   ```

4. **Update Documentation**
   - Append to `c:\FootballIntelligence\docs\PROGRESS.md`:
     ```markdown
     ## 2025-01-27 - MENSIONE Prediction Engine Core Implementation Complete
     
     Implemented production-grade prediction engine with:
     - 7 specialized models implementing unified interface
     - Multi-model ensemble with weighted combination
     - Probability calibration using isotonic regression
     - Confidence assessment from data quality + model agreement
     - Player impact and tactical matchup adjustments
     - Market derivation and MENSIONE pick generation
     - Database persistence with versioning
     - AnalysisContext enrichment
     
     Verified:
     - All 651+ tests passing
     - Full integration pipeline tested
     - Backward compatibility maintained
     - No data fabrication (explicit unavailability)
     
     Next: API endpoints for prediction engine
     ```

---

## FILE SUMMARY

### New Files (35 total)

**Interfaces & Infrastructure (6)**
- app/prediction/interfaces.py
- app/prediction/data_quality.py
- app/prediction/model_registry.py
- app/prediction/form_adjusted.py
- app/prediction/monte_carlo.py
- app/prediction/contextual_adjuster.py

**Engines (6)**
- app/prediction/ensemble_engine.py
- app/prediction/calibration_engine.py
- app/prediction/confidence_engine.py
- app/prediction/player_impact.py
- app/prediction/tactical_matchup.py
- app/prediction/market_derivation.py

**Orchestration & Persistence (3)**
- app/prediction/mensione_pick.py
- app/prediction/engine.py
- app/prediction/persistence.py

**Tests (20)**
- tests/test_prediction_interfaces.py
- tests/test_data_quality.py
- tests/test_dixon_coles_interface.py
- tests/test_form_adjusted.py
- tests/test_monte_carlo.py
- tests/test_ensemble_engine.py
- tests/test_calibration_engine.py
- tests/test_confidence_engine.py
- tests/test_player_impact.py
- tests/test_tactical_matchup.py
- tests/test_market_derivation.py
- tests/test_mensione_pick.py
- tests/test_prediction_engine.py
- tests/test_prediction_persistence.py

### Modified Files (11)

**Domain & Models**
- app/domain/prediction.py (add supporting structures)
- app/database/models.py (add PredictionVersion, PredictionRun)

**Existing Models (4)**
- app/prediction/poisson.py
- app/prediction/dixon_coles.py
- app/prediction/elo.py
- app/prediction/negative_binomial.py
- app/prediction/logistic_regression.py

**Analysis Integration**
- app/analysis/context.py

**Tests (3)**
- tests/test_poisson.py
- tests/test_elo.py
- tests/test_negative_binomial.py
- tests/test_logistic_regression.py

**Database Migration**
- alembic/versions/YYYYMMDD_add_prediction_versioning_tables.py (generated)

---

## IMPLEMENTATION ORDER SUMMARY

1. **FEAT-001** → Core interfaces, data quality gate, model registry
2. **FEAT-002** → Refactor 4 existing models to new interface
3. **FEAT-003** → Add 3 new specialized models
4. **FEAT-004** → Implement 6 engines (ensemble, calibration, confidence, contextual)
5. **FEAT-005** → Orchestrator, markets, pick, persistence, integration

Each FEAT is independently verifiable and builds on previous work.

**Total estimated complexity:** Large (5 major features, 35+ new files, 11 modified files, full integration testing)

---

## CRITICAL SUCCESS CRITERIA

✅ All 651+ existing tests pass (no regressions)  
✅ New models implement PredictionModel interface correctly  
✅ Models return ModelAvailability when data insufficient (never fabricate)  
✅ Ensemble combines predictions with proper weighting  
✅ Calibration improves probability accuracy  
✅ Confidence engine assesses prediction reliability  
✅ Market derivation maintains probability consistency  
✅ MENSIONE pick generation applies confidence thresholds  
✅ Database persistence with versioning works  
✅ AnalysisContext enrichment maintains backward compatibility  
✅ Full pipeline tested end-to-end  
✅ No data leakage in feature extraction  
✅ Imports work without errors  

---

**Plan Status:** Complete and ready for implementation by coding agent.

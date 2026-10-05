# MENSIONE Canonical Pipeline Integration Plan

**Task:** Wire existing implementations into one coherent runtime pipeline without rewriting or duplicating anything.

**Critical Constraints:**
- DO NOT rewrite existing models (poisson.py, dixon_coles.py, elo.py, monte_carlo.py, negative_binomial.py, form_adjusted.py, contextual_adjuster.py, logistic_regression.py)
- DO NOT create duplicate ensemble, calibration, or confidence systems
- DO NOT break the 931-test baseline
- Wire together existing implementations, don't replace them
- Preserve DevelopmentProvider determinism
- Maintain backward compatibility with existing API contracts

---

## Repository Audit Findings

### Models (app/prediction/)
**All exist and are working - DO NOT MODIFY:**
- ✅ poisson.py - PoissonModel (functional)
- ✅ dixon_coles.py - DixonColesModel (layers over Poisson)
- ✅ elo.py - EloRatingSystem (Elo ratings)
- ✅ monte_carlo.py - Monte Carlo simulation
- ✅ negative_binomial.py - Negative Binomial model
- ✅ form_adjusted.py - Form-based adjustments
- ✅ contextual_adjuster.py - Contextual adjustments
- ✅ logistic_regression.py - Logistic regression model

### Ensemble (app/prediction/)
**Canonical Decision: ensemble_engine.py**

- ✅ **ensemble_engine.py** - CANONICAL
  - Has WeightingStrategy abstraction (StaticWeights, ReliabilityWeights, DynamicWeights)
  - Calculates model_agreement from prediction variance
  - Handles ModelPrediction and ModelAvailability from interfaces.py
  - Returns ensemble with full metadata (weights, strategy, agreement, contributing models)
  
- ✅ **ensemble.py** - COMPATIBILITY WRAPPER
  - Simpler weighted averaging implementation
  - Lacks strategy abstraction and agreement calculation
  - Will become thin wrapper calling ensemble_engine.py
  - Preserves backward compatibility for existing code using EnsembleModel

**Action:** Refactor ensemble.py to wrap ensemble_engine.py, preserving API

### Calibration (app/prediction/)
**Canonical Decision: calibration_engine.py for application, calibration.py for evaluation**

- ✅ **calibration_engine.py** - CANONICAL ENGINE
  - Implements IsotonicCalibration and PlattCalibration with sklearn
  - Enforces temporal cutoff (fit(data, cutoff_date) prevents leakage)
  - Tracks CalibrationMetrics (brier_score, log_loss, n_samples, is_reliable)
  - Gracefully degrades when sklearn unavailable or insufficient samples
  
- ✅ **calibration.py** - EVALUATION LIBRARY (KEEP AS-IS)
  - Foundational metrics: brier_score(), log_loss_binary(), calibration_error(), evaluate_1x2()
  - Used by calibration_engine.py internally for metrics calculation
  - Used for backtest evaluation and reliability diagrams
  - NO MODIFICATION NEEDED

**Action:** Keep both files, use calibration_engine.py for pipeline calibration application

### Supporting Components (all exist and functional)
- ✅ confidence_engine.py - ConfidenceEngine (multi-component confidence assessment)
- ✅ data_quality.py - DataQualityGate (validates data sufficiency)
- ✅ market_derivation.py - MarketDerivationEngine (derives markets from score distributions)
- ✅ market_analysis.py - MarketAnalyser (compares model vs market odds)
- ✅ mensione_pick.py - MensionePickGenerator (generates recommended picks)
- ✅ easy_matches.py - EasyMatchDetector (identifies easy matches)
- ✅ prediction_version.py - PredictionVersionManager (immutable prediction versioning)

### Feature Engineering (app/features/)
- ✅ base.py - FeatureCalculator, MatchContext (feature extraction foundation)
- ✅ aggregator.py - FeatureAggregator (database-backed feature aggregation)

### Service Layer (app/prediction/)
- ⚠️ service.py - PredictionService (NEEDS REFACTORING)
  - Currently repeats feature extraction and model execution
  - No unified pipeline - each component called separately
  - Confidence hardcoded to None
  - Limited integration between components

### Domain Models (app/domain/)
- ✅ analysis.py - AnalysisContext (structured context for AI Analyst)
- ✅ prediction.py - Prediction, PredictionMarket, Model, ModelRun
- ✅ match.py - Match, Lineup
- ✅ entities.py - Team, Competition

### API (app/api/v1/endpoints/)
- ✅ matches.py - GET /matches, GET /matches/{id}, GET /matches/{id}/prediction
  - Currently returns basic prediction only
  - Needs extension to include confidence, markets, mensione_pick

---

## Canonical Pipeline Architecture

```
REAL DATA (ProviderManager)
    ↓
Normalization
    ↓
┌─────────────────────────────────────────────────────┐
│ MatchFeatureSnapshot (NEW)                          │
│ - match_identity, team_ids, competition             │
│ - strength_metrics, form_metrics, home_advantage    │
│ - player_availability (injuries/suspensions/lineup) │
│ - DataQualityReport (from DataQualityGate)          │
│ - source_provenance (per-field)                     │
│ - All fields Optional (None = unavailable)          │
└─────────────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────────────┐
│ ModelOrchestrator (NEW)                              │
│ - Runs all compatible models from snapshot          │
│ - Collects ModelPrediction | ModelAvailability      │
│ - Distinguishes: successful/unavailable/failed      │
│ - Partial failure does NOT kill pipeline            │
└─────────────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────────────┐
│ Individual Models (EXISTING - NO CHANGES)            │
│ - Poisson, Dixon-Coles, Elo, Monte Carlo            │
│ - Negative Binomial, Form-Adjusted, Contextual      │
│ - Each returns ModelPrediction or ModelAvailability │
└─────────────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────────────┐
│ Canonical Ensemble (ensemble_engine.py)              │
│ - EnsembleEngine with WeightingStrategy             │
│ - Calculates model_agreement from variance          │
│ - Returns ModelPrediction with metadata             │
│ - ensemble.py becomes compatibility wrapper         │
└─────────────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────────────┐
│ Calibration (calibration_engine.py)                  │
│ - Calibrator1X2 wraps 3 CalibrationEngines          │
│ - Applies isotonic/platt calibration per outcome    │
│ - Renormalizes to sum=1.0                           │
│ - Gracefully degrades if not fitted                 │
└─────────────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────────────┐
│ Confidence Engine (confidence_engine.py)             │
│ - REAL inputs from pipeline:                        │
│   - model_agreement (from ensemble)                 │
│   - data_quality_score (from DataQualityGate)       │
│   - calibration_reliability (from brier_score)      │
│   - sample_size, lineup_certainty, feature_stability│
│ - NO MORE HARDCODED VALUES                          │
└─────────────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────────────┐
│ Market Derivation (EXISTING)                         │
│ - MarketDerivationEngine                            │
│ - Derives all markets from score distribution       │
│ - MarketAnalyser compares vs bookmaker odds         │
└─────────────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────────────┐
│ MENSIONE Pick (EXISTING)                             │
│ - MensionePickGenerator                             │
│ - Ranks markets by EV/conviction                    │
│ - Filters by confidence threshold                   │
│ - DISTINCT from predicted score                     │
└─────────────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────────────┐
│ MensionePipeline Result (NEW)                        │
│ - Single execution produces:                        │
│   - Calibrated prediction                           │
│   - Confidence assessment                           │
│   - Market probabilities                            │
│   - MENSIONE Pick                                   │
│   - AnalysisContext (for AI Analyst)                │
│   - Prediction version metadata                     │
└─────────────────────────────────────────────────────┘
    ↓
API Response / AnalysisContext
```

---

## Implementation Plan: 6 FEATs

### FEAT-001: MatchFeatureSnapshot
**Type:** feat  
**Description:** Create canonical feature representation containing all available data without fabrication.

**Files to Create:**
- `backend/app/prediction/feature_snapshot.py` - MatchFeatureSnapshot dataclass
- `backend/tests/test_feature_snapshot.py` - Unit tests

**Files to Modify:**
- `backend/app/features/base.py` - Add extract_snapshot() method to MatchFeatureExtractor

**Key Components:**
- MatchFeatureSnapshot dataclass with Optional fields for: match_identity, strength_metrics, form_metrics, player_availability, data_quality_metadata (DataQualityReport), source_provenance
- Factory method: from_features(features: Dict, match: Match, data_quality_report: DataQualityReport)
- Validation: ensure no fabricated placeholder values (warn, don't fail)
- Serialization: to_dict() for AnalysisContext population

**Acceptance Criteria:**
- Snapshot preserves None for unavailable data (no conversion to 0 or 1.0)
- DataQualityReport attached to snapshot.data_quality_metadata
- 5+ unit tests pass
- 931 existing tests still pass

**Verification:**
```bash
cd backend && python -m pytest tests/test_feature_snapshot.py -v
cd backend && python -m pytest tests/ -k 'not test_feature_snapshot' --tb=short
```

---

### FEAT-002: ModelOrchestrator
**Type:** feat  
**Description:** Run all compatible models from MatchFeatureSnapshot, collect outputs, track success/failure/unavailability.

**Files to Create:**
- `backend/app/prediction/model_orchestrator.py` - ModelOrchestrator class
- `backend/tests/test_model_orchestrator.py` - Unit tests

**Files to Modify:**
- Adapt existing models if needed to fully implement PredictionModel interface (predict, get_metadata, check_requirements)

**Key Components:**
- ModelOrchestrator.register_model(model: PredictionModel)
- ModelOrchestrator.run_all(snapshot: MatchFeatureSnapshot) -> ModelOrchestrationResult
- ModelOrchestrationResult dataclass: successful_predictions, unavailable_models, failed_models, participating_model_ids, execution_metadata
- ModelOrchestrator.create_default_registry() -> instantiates all 8 models (Poisson, Dixon-Coles, Elo, MonteCarlo, NegativeBinomial, FormAdjusted, ContextualAdjuster, LogisticRegression)

**Acceptance Criteria:**
- Partial model failure does NOT kill orchestration
- ModelOrchestrationResult clearly distinguishes successful/unavailable/failed
- Default registry instantiates 8 models
- 5+ unit tests pass
- Existing model tests still pass

**Verification:**
```bash
cd backend && python -m pytest tests/test_model_orchestrator.py -v
cd backend && python -m pytest tests/test_poisson.py tests/test_dixon_coles.py tests/test_elo.py -v
```

---

### FEAT-003: Canonical Ensemble Integration
**Type:** feat  
**Description:** Select ensemble_engine.py as canonical, refactor ensemble.py as compatibility wrapper, wire into pipeline.

**Canonical Decision:** ensemble_engine.py  
**Rationale:** Has WeightingStrategy abstraction, model_agreement calculation, better extensibility.

**Files to Modify:**
- `backend/app/prediction/ensemble.py` - Refactor EnsembleModel to wrap EnsembleEngine
- `backend/app/prediction/model_orchestrator.py` - Add EnsembleIntegration class

**Files to Create:**
- `backend/tests/test_ensemble_integration.py` - Integration tests

**Files to Preserve:**
- `backend/app/prediction/ensemble_engine.py` - NO CHANGES (canonical)

**Key Components:**
- Refactor EnsembleModel.predict() to convert inputs, call EnsembleEngine, convert outputs (backward compatibility)
- Add EnsembleIntegration.combine_predictions(orchestration_result, strategy) -> ModelPrediction
- Preserve model_agreement calculation from ensemble_engine.py (std dev of predictions)

**Acceptance Criteria:**
- ensemble_engine.py unchanged (canonical)
- ensemble.py becomes wrapper (backward compatibility preserved)
- Model agreement calculated from prediction variance
- All existing ensemble tests pass
- 5+ integration tests pass

**Verification:**
```bash
cd backend && python -m pytest tests/test_ensemble.py tests/test_ensemble_engine.py -v
cd backend && python -m pytest tests/test_ensemble_integration.py -v
```

---

### FEAT-004: Canonical Calibration Integration
**Type:** feat  
**Description:** Select calibration_engine.py as canonical engine, keep calibration.py as evaluation library, wire into pipeline.

**Canonical Decision:** calibration_engine.py (engine), calibration.py (metrics library)  
**Rationale:** calibration_engine.py has sklearn integration, temporal cutoff enforcement. calibration.py provides metrics foundation.

**Files to Modify:**
- `backend/app/prediction/calibration_engine.py` - Add Calibrator1X2 class
- `backend/app/prediction/model_orchestrator.py` - Add CalibrationIntegration class

**Files to Create:**
- `backend/tests/test_calibration_integration.py` - Integration tests

**Files to Preserve:**
- `backend/app/prediction/calibration.py` - NO CHANGES (metrics library)

**Key Components:**
- Calibrator1X2 class wrapping 3 CalibrationEngines (home_win, draw, away_win)
- Calibrator1X2.calibrate_1x2(home_prob, draw_prob, away_prob) -> renormalized tuple
- CalibrationIntegration.calibrate_prediction(ensemble_prediction, calibrator) -> ModelPrediction with metadata
- Graceful degradation: return uncalibrated with metadata when calibrator not fitted

**Acceptance Criteria:**
- calibration_engine.py remains canonical engine
- calibration.py unchanged (evaluation library)
- Calibrator1X2 renormalizes to sum=1.0
- Graceful degradation when not fitted or insufficient data
- All existing calibration tests pass
- 5+ integration tests pass

**Verification:**
```bash
cd backend && python -m pytest tests/test_calibration.py tests/test_calibration_engine.py -v
cd backend && python -m pytest tests/test_calibration_integration.py -v
```

---

### FEAT-005: Real Confidence Integration
**Type:** feat  
**Description:** Wire ConfidenceEngine to actual pipeline outputs, eliminate all hardcoded assumptions.

**Files to Modify:**
- `backend/app/prediction/model_orchestrator.py` - Add ConfidenceIntegration class
- `backend/app/prediction/service.py` - Remove hardcoded confidence values

**Files to Create:**
- `backend/tests/test_confidence_integration.py` - Integration tests

**Files to Preserve:**
- `backend/app/prediction/confidence_engine.py` - NO CHANGES (functional)

**Key Components:**
- ConfidenceIntegration.assess_confidence(snapshot, orchestration_result, ensemble_prediction, calibration_metrics) -> ConfidenceAssessment
- Extract real values:
  - model_agreement from ensemble_prediction.metadata['model_agreement']
  - data_quality_score from snapshot.data_quality_metadata.overall_score
  - n_matches from snapshot metadata
  - brier_score from calibration_metrics if available
  - lineup_status from snapshot.player_availability
- Remove hardcoded values: search for 'confidence = 0.7', 'model_agreement = 1.0', 'data_quality_score = 0.7', etc.

**Acceptance Criteria:**
- ConfidenceEngine receives real values from pipeline components
- NO hardcoded confidence values remain (confidence=0.7, model_agreement=1.0, etc.)
- Confidence degrades with low data quality, low model agreement, missing calibration
- ConfidenceAssessment.component_breakdown provides transparency
- All existing ConfidenceEngine tests pass
- 5+ integration tests pass

**Verification:**
```bash
cd backend && python -m pytest tests/test_confidence_engine.py -v
cd backend && python -m pytest tests/test_confidence_integration.py -v
```

---

### FEAT-006: Unified MensionePipeline + API Extension
**Type:** feat  
**Description:** Create single pipeline execution wiring all components, refactor PredictionService to eliminate redundant execution, extend API with confidence/markets/pick while preserving backward compatibility.

**Files to Create:**
- `backend/app/prediction/pipeline.py` - MensionePipeline class
- `backend/tests/test_pipeline_integration.py` - Integration tests

**Files to Modify:**
- `backend/app/prediction/service.py` - Refactor to use MensionePipeline
- `backend/app/prediction/prediction_version.py` - Extend PredictionVersionMetadata
- `backend/app/api/v1/endpoints/matches.py` - Extend GET /matches/{id}/prediction response

**Key Components:**
- MensionePipeline.execute(snapshot, match, bookmaker_odds) -> PipelineResult
  - Pipeline stages in order:
    1. orchestrator.run_all(snapshot)
    2. EnsembleIntegration.combine()
    3. CalibrationIntegration.calibrate()
    4. ConfidenceIntegration.assess()
    5. market_derivation.derive()
    6. market_analyser.analyze() if odds available
    7. easy_match_detector.detect()
    8. mensione_pick_generator.generate()
    9. version_manager.create_version()
    10. build_analysis_context()
- PipelineResult dataclass: snapshot, orchestration_result, ensemble_prediction, calibrated_prediction, confidence_assessment, market_probabilities, market_analysis, easy_match, mensione_pick, prediction_version, analysis_context, execution_time, pipeline_metadata
- PredictionService.generate_prediction() refactored to call pipeline.execute() internally
- PredictionService.generate_prediction_with_context() -> (Prediction, AnalysisContext)
- Extend PredictionVersionMetadata: models_used, ensemble_strategy, calibration_status, confidence_score, data_quality_score, feature_snapshot_version, pipeline_version
- API extension: GET /matches/{id}/prediction returns prediction + confidence_assessment + mensione_pick + markets (backward compatible - add fields, don't remove)

**Acceptance Criteria:**
- MensionePipeline.execute() runs full pipeline in correct order
- PipelineResult contains all intermediate and final outputs
- PredictionService eliminates redundant feature extraction and model execution
- API response extended with confidence, mensione_pick, markets while preserving backward compatibility
- AnalysisContext populated from single pipeline execution
- PredictionVersionManager tracks models_used, ensemble, calibration, confidence, data_quality
- All existing service and API tests pass
- 8+ pipeline integration tests pass
- 931+ baseline maintained or increased

**Verification:**
```bash
cd backend && python -m pytest tests/test_pipeline_integration.py -v
cd backend && python -m pytest tests/test_prediction_service.py tests/test_api_matches.py -v
cd backend && python -m pytest tests/ --tb=short
# Manual: uvicorn app.main:app --reload
# Call: GET /api/v1/matches/{dev_match_id}/prediction
# Confirm response has: prediction, confidence_assessment, mensione_pick, markets
```

---

## Summary

**6 FEATs in dependency order:**

1. **FEAT-001:** MatchFeatureSnapshot (canonical feature representation)
2. **FEAT-002:** ModelOrchestrator (run all models, collect outputs)
3. **FEAT-003:** Ensemble Integration (ensemble_engine.py canonical, ensemble.py wrapper)
4. **FEAT-004:** Calibration Integration (calibration_engine.py canonical engine, calibration.py metrics library)
5. **FEAT-005:** Confidence Integration (wire real values, eliminate hardcoded assumptions)
6. **FEAT-006:** MensionePipeline (unified execution, service refactor, API extension)

**What is NOT being changed:**
- Individual model implementations (poisson.py, dixon_coles.py, elo.py, monte_carlo.py, negative_binomial.py, form_adjusted.py, contextual_adjuster.py, logistic_regression.py)
- calibration.py (evaluation library)
- ensemble_engine.py (canonical ensemble)
- confidence_engine.py (core confidence logic)
- market_derivation.py, market_analysis.py, mensione_pick.py, easy_matches.py (all functional)
- prediction_version.py (only extending metadata, not changing versioning logic)

**Interfaces that must remain backward compatible:**
- PredictionService.generate_prediction(match) -> Prediction
- EnsembleModel.predict() API from ensemble.py
- GET /api/v1/matches/{id}/prediction response structure (add fields, don't remove)

**Genuine blockers identified:**
- None - all required interfaces exist and are functional. Integration is straightforward wiring.

**Test baseline:** 931 tests must pass after each FEAT. May increase with new integration tests, but must not decrease.

**DevelopmentProvider determinism:** Preserved throughout - no changes to mock data generation.

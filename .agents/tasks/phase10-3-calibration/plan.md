# PHASE 10.3 — CALIBRATION + MODEL OPTIMIZATION + WALK-FORWARD VALIDATION
## Implementation Plan

**Current Production State (DO NOT MODIFY):**
- 4 operational models: Poisson, Dixon-Coles, Negative Binomial, Form Adjusted  
- ~4,543 total matches, ~2,673 finished matches in database
- GET /api/v1/matches/fotmob_5071211/prediction → HTTP 200, ~1.03s, is_development_data=false
- Phase 10.1 and 10.2 COMPLETE — no changes to completed work

**Repository Inspection Results:**

### Current Infrastructure Assessment
- **WalkForwardEvaluator**: Full implementation exists with temporal safety, 12 configurations, pipeline integration
- **CalibrationEngine**: Complete with isotonic/Platt methods, sklearn graceful degradation, temporal cutoff enforcement
- **EnsembleEngine**: 3 weighting strategies (Static, Reliability, Dynamic), model agreement calculation
- **ConfidenceEngine**: 6-component confidence assessment (agreement, data quality, sample size, calibration, lineup, stability)
- **ModelOrchestrator**: 7-model registry with graceful failure handling
- **Database Models**: Match/MatchEvent/Team with xG fields, provider infrastructure ready
- **Current Git State**: 25 files modified, active development visible

### Existing Test Coverage
- Walk-forward: 10/10 tests PASS ✅
- Model tests: 95/95 tests PASS (from PROGRESS.md)  
- Prediction tests: 80/82 tests PASS (2 skipped - sklearn dependency)
- sklearn unavailable (expected): CalibrationEngine returns uncalibrated with warnings

---

## IMPLEMENTATION PLAN

### GROUP 0 — CURRENT STATE INSPECTION ✅ 
**STATUS: COMPLETE** - Infrastructure assessment complete, no changes needed to Phase 10.1/10.2 work.

### GROUP 1 — ESTABLISH REAL HISTORICAL DATASET

- [ ] 1. Create database census script to document exact historical dataset usability
      - Query total finished matches, teams with valid scores, temporal coverage
      - Calculate exclusion reasons (missing teams, null scores, invalid timestamps)
      - Document sample sizes per team, per competition, per time period
      Files: `backend/scripts/historical_dataset_census.py`
      Verify: Script outputs detailed census report with exclusion counts

- [ ] 2. Add dataset validation utilities to prediction service
      - Extend PredictionService with dataset quality checks
      - Implement match eligibility filtering for walk-forward evaluation
      - Add sample size validation per team/competition combination
      Files: `backend/app/prediction/dataset_validator.py`
      Verify: Validation utilities correctly identify usable historical matches

### GROUP 2 — BASELINE PRODUCTION EVALUATION

- [ ] 3. Implement baseline model evaluation without optimization
      - Create production pipeline evaluator using current 4-model ensemble
      - Calculate individual model metrics (accuracy, Brier, log loss, calibration) 
      - Ensure 1X2 probability normalization validation (sum = 1.0 ± tolerance)
      - Handle insufficient sample cases with explicit INSUFFICIENT_HISTORICAL_SAMPLE
      Files: `backend/app/prediction/baseline_evaluator.py`
      Verify: `python backend/scripts/evaluate_baseline_models.py` produces metric report

- [ ] 4. Add baseline evaluation script with current production weights
      - Use existing EnsembleEngine with current ReliabilityWeights strategy
      - Evaluate on real database matches (no advanced optimization)
      - Output per-model and ensemble metrics in structured format
      Files: `backend/scripts/evaluate_baseline_models.py`
      Verify: Script completes and generates baseline metrics JSON

### GROUP 3 — WALK-FORWARD TEMPORAL VALIDATION

- [ ] 5. Enhance WalkForwardEvaluator integration with existing prediction pipeline
      - Connect WalkForwardEvaluator._build_snapshot to PredictionService feature extraction
      - Implement proper temporal cutoff queries (database queries with WHERE match_date < T)
      - Add leakage detection tests for model training/calibration
      Files: `backend/app/prediction/walk_forward.py` (enhance existing implementation)
      Verify: Walk-forward evaluation runs with temporal safety validation

- [ ] 6. Create comprehensive walk-forward evaluation script
      - Use mandatory WalkForwardEvaluator with database-backed feature extraction
      - Implement training window expansion and temporal boundary enforcement
      - Generate chronological prediction accuracy tracking
      Files: `backend/scripts/run_walk_forward_evaluation.py`
      Verify: Script produces walk-forward results with no temporal leakage warnings

### GROUP 4 — CALIBRATION

- [ ] 7. Enhance CalibrationEngine with historical data integration
      - Connect CalibrationEngine to database historical predictions
      - Implement walk-forward-safe calibration fitting (training data before T only)
      - Add calibration performance comparison (baseline vs calibrated OOS metrics)
      Files: `backend/app/prediction/calibration_engine.py` (enhance existing implementation)
      Verify: Calibration evaluation shows OOS improvement metrics or INSUFFICIENT_HISTORICAL_SAMPLE

- [ ] 8. Create calibration evaluation and comparison script
      - Compare uncalibrated vs calibrated prediction performance  
      - Use isotonic regression with sklearn graceful degradation
      - Measure Brier, log loss, calibration error improvements on genuinely unseen data
      Files: `backend/scripts/evaluate_calibration.py`
      Verify: Script produces calibration comparison report with OOS validation

### GROUP 5 — MODEL AGREEMENT / DISAGREEMENT

- [ ] 9. Implement model agreement analysis using existing 4 operational models
      - Use EnsembleEngine model_agreement calculation on historical predictions
      - Create agreement buckets (high/medium/high-disagreement) with historical performance
      - Validate correlation between agreement scores and actual prediction reliability
      Files: `backend/app/prediction/agreement_analyzer.py`
      Verify: Agreement analysis produces historically-validated reliability buckets

- [ ] 10. Create model agreement evaluation script
       - Analyze agreement vs reliability correlation on historical data
       - Generate agreement bucket performance statistics
       - Do NOT convert agreement to arbitrary confidence percentages without validation
       Files: `backend/scripts/analyze_model_agreement.py`
       Verify: Script outputs agreement-reliability correlation analysis

### GROUP 6 — ENSEMBLE WEIGHT OPTIMIZATION

- [ ] 11. Implement walk-forward-safe weight optimization
       - Extend EnsembleEngine with optimized weight strategy using historical performance
       - Ensure training data = observations before T, validation = observations after T
       - Compare equal weights vs performance-based weights vs optimized weights
       Files: `backend/app/prediction/ensemble_engine.py` (add OptimizedWeights strategy)
       Verify: Weight optimization shows OOS improvement or recommends keeping existing ensemble

- [ ] 12. Create ensemble optimization evaluation script  
       - Compare current ReliabilityWeights vs optimized weights on OOS data
       - Use walk-forward validation for weight parameter optimization
       - Only promote optimized weights if genuine OOS improvement demonstrated
       Files: `backend/scripts/optimize_ensemble_weights.py`
       Verify: Script either promotes optimized weights or recommends keeping current ensemble

### GROUP 7 — MODEL CONTRIBUTION

- [ ] 13. Implement individual model contribution analysis
       - Test single-model performance vs ensemble using OOS evaluation
       - Measure each model's contribution to ensemble performance
       - Use multiple metrics (not just one) for model evaluation decisions
       Files: `backend/app/prediction/model_contribution.py`
       Verify: Contribution analysis runs on adequate sample sizes

- [ ] 14. Create model contribution evaluation script
       - Compare Poisson-only, Dixon-Coles-only, Negative-Binomial-only, Form-Adjusted-only vs 4-model ensemble
       - Calculate performance deltas and statistical significance where sample permits
       - Provide recommendations based on multiple evaluation metrics
       Files: `backend/scripts/evaluate_model_contributions.py`  
       Verify: Script completes contribution analysis with adequate samples

### GROUP 8 — CALIBRATION / RELIABILITY BUCKETS

- [ ] 15. Implement reliability bucket analysis with sufficient observation requirements
       - Create probability buckets: 50-55%, 55-60%, 60-65%, 65-70%, 70-75%, 75-80%, 80%+
       - Calculate empirical success rates vs predicted probabilities
       - Only create buckets with adequate historical observations
       Files: `backend/app/prediction/reliability_buckets.py`
       Verify: Bucket analysis shows whether predicted X% events happen ~X% of the time

- [ ] 16. Create reliability bucket evaluation script
       - Generate calibration analysis: "Does predicted 70% actually happen 70% of time?"
       - Report bucket statistics with confidence intervals where sample size supports
       - Do NOT force calibration results - report actual empirical findings  
       Files: `backend/scripts/evaluate_reliability_buckets.py`
       Verify: Script produces bucket analysis with actual vs predicted probability comparison

### GROUP 9 — DATA QUALITY / AGREEMENT INTERACTION

- [ ] 17. Implement data quality-agreement interaction analysis (if data available)
       - Analyze correlation between data quality scores and model agreement
       - Check if high data quality corresponds to higher model agreement
       - Report INSUFFICIENT_HISTORICAL_SAMPLE if data quality fields mostly null
       Files: `backend/app/prediction/data_quality_agreement.py`
       Verify: Analysis completes or reports insufficient data quality coverage

- [ ] 18. Create data quality interaction evaluation script
       - Evaluate relationship between DataQualityGate outputs and model performance
       - Do NOT manufacture data quality values - use only available database fields
       - Report findings or explicitly state insufficient data for this analysis
       Files: `backend/scripts/evaluate_data_quality_interaction.py`
       Verify: Script produces interaction analysis or insufficient data report

### GROUP 10 — PRODUCTION INTEGRATION

- [ ] 19. Integrate validated improvements into production prediction service
       - Only promote changes with demonstrated OOS improvement
       - Test production endpoint after any calibration/weight changes
       - Ensure Phase 10.1/10.2 functionality remains intact
       Files: `backend/app/prediction/service.py` (minimal validated changes only)
       Verify: GET /api/v1/matches/fotmob_5071211/prediction still returns HTTP 200

- [ ] 20. Create production validation script
       - Test production endpoint with new calibration/weight configurations
       - Validate prediction quality metrics before/after changes
       - Rollback capability if production performance degrades
       Files: `backend/scripts/validate_production_integration.py`
       Verify: Production endpoint maintains performance with any integrated changes

### GROUP 11 — REGRESSION TESTING

- [ ] 21. Run comprehensive test suite to ensure no Phase 10.3 regressions
       - Execute all existing prediction tests, model tests, feature tests
       - Run walk-forward tests, calibration tests, ensemble tests
       - Verify exact test counts: 80+ prediction tests, 95+ model tests
       Files: N/A (existing test suite)
       Verify: All existing tests pass with no new failures introduced by Phase 10.3

- [ ] 22. Add Phase 10.3 specific tests for new evaluation components  
       - Test dataset census, baseline evaluation, agreement analysis
       - Test walk-forward integration, calibration evaluation, weight optimization
       - Ensure new code has adequate test coverage
       Files: `backend/tests/prediction/test_phase10_3_*.py`
       Verify: New tests pass and provide coverage for Phase 10.3 functionality

### GROUP 12 — REAL API VALIDATION

- [ ] 23. Validate health and prediction endpoints with Phase 10.3 changes
       - Test GET /health for system health status
       - Test GET /api/v1/matches/fotmob_5071211/prediction for production prediction
       - Confirm HTTP 200, is_development_data=false, probability sum=1.0, PICK/PASS functions
       Files: N/A (endpoint testing)
       Verify: Both endpoints return expected responses with correct prediction structure

- [ ] 24. Update PROGRESS.md with Phase 10.3 completion documentation
       - Document calibration/optimization results, walk-forward validation findings
       - Record which improvements were validated and integrated vs which were not suitable
       - Provide clear status for each GROUP with actual results achieved
       Files: `docs/PROGRESS.md`
       Verify: PROGRESS.md contains complete Phase 10.3 documentation

---

## SEQUENCING CONSTRAINTS

**Dependencies:**
- GROUP 2 (baseline) depends on GROUP 1 (dataset establishment)
- GROUP 3 (walk-forward) depends on GROUP 1 (dataset establishment)  
- GROUP 4 (calibration) depends on GROUP 3 (walk-forward temporal validation)
- GROUP 6 (weight optimization) depends on GROUP 2-5 (baseline evaluation complete)
- GROUP 10 (production integration) depends on GROUP 4-8 (evaluation complete)
- GROUP 11 (regression testing) depends on GROUP 10 (integration complete)
- GROUP 12 (API validation) depends on GROUP 11 (testing complete)

**Risk Notes:**
- INSUFFICIENT_HISTORICAL_SAMPLE likely for some advanced metrics (expected behavior)
- sklearn availability matters for isotonic calibration (graceful degradation implemented)
- Walk-forward evaluation requires adequate historical data per team/competition
- Optimization may not show improvement (valid outcome - keep existing system)
- Data quality analysis may be impossible if fields mostly null (report truthfully)

**Expected Output:** Complete Phase 10.3 with validated calibration/optimization improvements integrated into production pipeline, or documented findings showing current system performance is optimal. All changes maintain Phase 10.1/10.2 integrity.
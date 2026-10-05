# MENSIONE Canonical Pipeline - Updated Implementation Plan

## Current State Summary

### What's Already Done ✅

1. **ModelOrchestrator Architecture**: Complete with all 7 models registered (Poisson, Dixon-Coles, Elo, Monte Carlo, Negative Binomial, Form-Adjusted, Logistic Regression)
2. **EnsembleIntegration**: Implemented with reliability weighting and model agreement calculation
3. **CalibrationIntegration**: Implemented with Isotonic Calibration wrappers (unfitted - expected for Phase 1)
4. **ConfidenceIntegration**: Implemented with 6-component confidence assessment
5. **DevelopmentProvider**: Extended from 4 to 20 matches (19 completed, 1 scheduled) with varied scorelines
6. **FeatureSnapshot**: Dataclass structure exists in `app/prediction/feature_snapshot.py`
7. **MarketDerivationEngine**: Implemented in `app/prediction/market_derivation.py`
8. **PredictionService**: Partially wired with canonical components instantiated in `__init__()` (lines 90-153)
9. **generate_full_prediction()**: Skeleton implementation exists (lines 740-1020) with STEP 1-12 structure

### What's Broken/Missing ❌

**Current Failure**: 1 test failing
- `test_full_prediction_pipeline_with_development_fallback` fails with `predicted_score = None`
- Root cause: Test uses teams `team_pipeline_1/team_pipeline_2` which don't exist in DevelopmentProvider
- DevelopmentProvider has `dev_team_alpha/beta/gamma/delta` with 19 completed historical matches

**Review Findings (8 Critical Issues)**:
1. ✅ Canonical pipeline IS wired in generate_full_prediction() but may have bugs
2. ⚠️ FeatureSnapshot extraction not fully implemented - `_extract_canonical_snapshot()` may not use `extract_feature_snapshot()`
3. ⚠️ Hardcoded confidence inputs may still exist in fallback paths
4. ❌ No PipelineResult dataclass reuse - each method does separate extraction
5. ⚠️ Ensemble agreement calculation exists but may not be wired to confidence
6. ⚠️ DataQualityEngine may not be instantiated or called
7. ✅ Calibration unfitted status acknowledged (Phase 1 acceptable)
8. ❌ API backward compatibility untested

---

## Architectural Decisions

### Decision 1: Fix Test vs Fix Provider
**Decision**: Fix the test to use existing DevelopmentProvider teams (`dev_team_alpha`, `dev_team_beta`).
**Rationale**: DevelopmentProvider already has 20 matches with 4 teams and varied historical data. Creating new teams for non-existent test IDs adds unnecessary data. The test should use the canonical dev data.

### Decision 2: PipelineResult Pattern
**Decision**: Create `PipelineResult` dataclass as central execution artifact, refactor all methods to derive outputs from single pipeline run.
**Rationale**: Review finding #4 is critical - duplicate feature extraction/model runs violate the "single execution" principle. `PipelineResult` becomes the source of truth, preventing redundant computation.

### Decision 3: DataQualityEngine Integration
**Decision**: Instantiate `DataQualityEngine` in `PredictionService.__init__()` and call it in `_extract_canonical_snapshot()` to populate `snapshot.data_quality_report`.
**Rationale**: Review finding #6 - without data quality assessment, confidence defaults to 0.5, making confidence scores meaningless.

### Decision 4: API Backward Compatibility
**Decision**: Keep existing API response schema unchanged, add new fields as optional. Add regression test comparing response schemas.
**Rationale**: Frontend already consumes the API. Breaking changes require coordinated frontend updates. Additive changes are safe.

### Decision 5: SmartMarketSelector Integration Timing
**Decision**: Implement SmartMarketSelector after fixing canonical pipeline, not before.
**Rationale**: The failing test doesn't even reach market selection - it fails during prediction generation. Fix the foundation first.

---

## Remaining Work - Priority Order

### PRIORITY 1: Fix Failing Test (FEAT-001 Revised)

**Issue**: Test uses non-existent teams
**Fix**: Update test to use DevelopmentProvider's actual teams

**Files to modify**:
- `backend/tests/test_prediction_service.py` (line ~556-605)

**Changes**:
1. Replace `team_pipeline_1` → `dev_team_alpha`
2. Replace `team_pipeline_2` → `dev_team_beta`
3. Replace `comp_pipeline` → `dev_comp_league_a`
4. Replace `season_pipeline` → `dev_season_2023_2024`

**Verification**:
```powershell
cd backend
.venv\Scripts\python.exe -m pytest tests/test_prediction_service.py::TestDevelopmentDataFallback::test_full_prediction_pipeline_with_development_fallback -v
# Expected: PASS with predicted_score not None
```

### PRIORITY 2: Verify/Fix Canonical Pipeline Wiring (FEAT-001b)

**Issue**: Pipeline exists but may have bugs preventing predicted_score

**Inspection checklist**:
1. Read `_extract_canonical_snapshot()` - verify it calls `extract_feature_snapshot()` from `feature_snapshot.py`
2. Verify `extract_feature_snapshot()` instantiates `DataQualityEngine` and populates `snapshot.data_quality_report`
3. Trace execution path from `ModelOrchestrator.run_all()` through ensemble/calibration/confidence
4. Verify `market_probs.exact_score_top` is populated correctly
5. Check error handling - are exceptions swallowing the pipeline?

**Files to inspect/modify**:
- `backend/app/prediction/service.py` (lines 740-1020)
- `backend/app/prediction/feature_snapshot.py`
- `backend/app/prediction/model_orchestrator.py`

**Potential fixes**:
- If `_extract_canonical_snapshot()` doesn't exist, implement it to call `extract_feature_snapshot()`
- If `DataQualityEngine` not instantiated, add to `__init__()`
- If exceptions are caught and return empty context, fix error handling to propagate useful errors

**Verification**:
```powershell
cd backend
.venv\Scripts\python.exe -m pytest tests/test_prediction_service.py::TestDevelopmentDataFallback -v
# Expected: Both tests pass
```

### PRIORITY 3: Eliminate Hardcoded Confidence Inputs (Review Finding #3)

**Issue**: May have `model_agreement=1.0` or `data_quality_score=0.7` in fallback paths

**Search and destroy**:
```powershell
cd backend
Select-String -Path 'app\prediction\*.py' -Pattern 'model_agreement\s*=\s*(0\.\d+|1\.0)' | Where-Object { $_.Line -notmatch '^(\s*#|.*def.*model_agreement)' }
Select-String -Path 'app\prediction\*.py' -Pattern 'data_quality.*=\s*0\.\d+' | Where-Object { $_.Line -notmatch '^(\s*#|.*def.*data_quality)' }
```

**Fix approach**:
- Replace with `orchestration_result.model_agreement` or `ensemble_result.metadata.get('model_agreement', 0.0)`
- Replace with `snapshot.data_quality_report.overall_score` or default to `0.5` with clear comment

**Files to modify**:
- `backend/app/prediction/service.py`
- Potentially `backend/app/prediction/confidence_engine.py`

**Verification**:
```powershell
# Rerun search commands - should return no matches in production code
# Run tests to ensure confidence values are realistic (not all 1.0 or 0.7)
cd backend
.venv\Scripts\python.exe -m pytest tests/test_confidence_engine.py -v
```

### PRIORITY 4: Create PipelineResult Dataclass (Review Finding #4)

**Issue**: Multiple methods do redundant feature extraction

**Implementation**:
1. Define `PipelineResult` dataclass in `service.py` (already exists in current code - lines 60-88)
2. Refactor `generate_full_prediction()` to return `PipelineResult` internally
3. Create `_execute_pipeline()` private method that returns `PipelineResult`
4. Refactor public methods to call `_execute_pipeline()` once and derive outputs:
   - `generate_prediction()` → derives `Prediction` from `PipelineResult`
   - `generate_prediction_markets()` → derives markets from `PipelineResult.market_probabilities`
   - `detect_easy_match()` → derives from `PipelineResult.confidence_assessment`
   - `build_analysis_context()` → derives from `PipelineResult.analysis_context`

**Files to modify**:
- `backend/app/prediction/service.py`

**Verification**:
```powershell
cd backend
.venv\Scripts\python.exe -m pytest tests/test_prediction_service.py -v
# Expected: All tests pass, execution faster (no duplicate runs)
```

### PRIORITY 5: Implement SmartMarketSelector (FEAT-002)

**Follow FEAT-002.json specification exactly**:
- Create `backend/app/prediction/market_selector.py`
- Define `BestTip` dataclass with 16 fields
- Define `PassDecision` dataclass with 5 fields
- Implement `SmartMarketSelector` class with `evaluate_and_select()` method
- Value classification: STRONG_VALUE (≥10%), VALUE (≥5%), NEUTRAL (≥0%), NEGATIVE_VALUE (<0%)
- Risk levels: LOW/MEDIUM/HIGH based on confidence/agreement/quality thresholds
- Create comprehensive test suite with 15+ tests

**Files to create**:
- `backend/app/prediction/market_selector.py`
- `backend/tests/test_market_selector.py`

**Verification**:
```powershell
cd backend
.venv\Scripts\python.exe -m pytest tests/test_market_selector.py -v
# Expected: 15+ tests pass
```

### PRIORITY 6: Integrate SmartMarketSelector (FEAT-003)

**Follow FEAT-003.json specification**:
- Replace `MensionePickGenerator` with `SmartMarketSelector` in `PredictionService.__init__()`
- Update `generate_full_prediction()` STEP 8 to call `evaluate_and_select()`
- Convert `BestTip`/`PassDecision` to dict for `AnalysisContext.mensione_pick`
- Update API documentation in `backend/app/api/v1/endpoints/matches.py`

**Files to modify**:
- `backend/app/prediction/service.py` (lines ~138, 870-905)
- `backend/app/api/v1/endpoints/matches.py` (docstring update)

**Verification**:
```powershell
cd backend
.venv\Scripts\python.exe -m pytest tests/test_prediction_service.py tests/test_match_intelligence.py -v
# Expected: All tests pass with enhanced mensione_pick structure
```

### PRIORITY 7: Extend PredictionVersionManager (FEAT-004)

**Follow FEAT-004.json specification**:
- Add frozen pick fields to `PredictionVersion` dataclass (9 fields from BestTip)
- Add result tracking foundation fields (3 fields: actual_result, profit_loss, settled_at)
- Update `create_version()` to accept `mensione_pick` parameter
- Implement population logic: if BestTip, populate frozen fields; if PassDecision, leave None
- Add foundation methods: `settle_prediction()`, `get_settled_picks_by_market()` (stubs with TODO)

**Files to modify**:
- `backend/app/prediction/prediction_version.py`
- `backend/app/prediction/service.py` (pass mensione_pick to create_version)
- `backend/tests/test_prediction_version.py`

**Verification**:
```powershell
cd backend
.venv\Scripts\python.exe -m pytest tests/test_prediction_version.py -v
# Expected: All frozen pick tests pass
```

### PRIORITY 8: API Backward Compatibility Test (Review Finding #8)

**Implementation**:
- Create test comparing old vs new response schemas
- Test in `backend/tests/test_api_matches.py` or `test_match_intelligence.py`
- Verify all existing fields still present
- Verify new fields are optional (not breaking)

**Files to modify**:
- `backend/tests/test_match_intelligence.py` (add test)

**Verification**:
```powershell
cd backend
.venv\Scripts\python.exe -m pytest tests/test_match_intelligence.py::test_api_backward_compatibility -v
# Expected: PASS confirming schema compatibility
```

### PRIORITY 9: Final Audit (FEAT-005)

**Audit checklist**:
1. ModelOrchestrator registers exactly 7 models
2. EnsembleEngine used (no duplicate ensemble)
3. CalibrationEngine used (no duplicate calibration)
4. Confidence computed from real values (no hardcoded model_agreement=1.0 or data_quality_score=0.7)
5. Single pipeline execution (no redundant feature extraction)
6. Market intelligence connected via MarketDerivationEngine
7. Full test suite passes: 974+ tests

**Verification commands**:
```powershell
cd backend
# Full test suite
.venv\Scripts\python.exe -m pytest tests/ -v --tb=short
# Expected: 974+ passed, 0 failed

# Hardcoded value search
Select-String -Path 'app\prediction\*.py' -Pattern '(model_agreement|data_quality_score)\s*=\s*[0-9]' | Where-Object { $_.Line -notmatch '^(\s*#|.*def)' }
# Expected: No suspicious hardcoded values in production code

# Component tests
.venv\Scripts\python.exe -m pytest tests/test_model_orchestrator.py tests/test_ensemble_engine.py tests/test_calibration_engine.py tests/test_confidence_engine.py -v
# Expected: All component tests pass
```

---

## Conflict Resolution

### Conflict 1: FEAT-001 vs Review Finding #1
**FEAT-001**: Says add 16 historical matches to DevelopmentProvider
**Review #1**: Says canonical pipeline never wired

**Resolution**: DevelopmentProvider already has 20 matches (done in previous workflow). Review #1 is outdated - pipeline IS wired in service.py but may have bugs. Focus on fixing bugs, not adding more data.

### Conflict 2: FEAT-002 Timing vs Test Failure
**FEAT-002**: Says implement SmartMarketSelector next
**Test failure**: Pipeline doesn't even reach market selection stage

**Resolution**: Fix pipeline execution first (PRIORITY 1-4), then implement SmartMarketSelector (PRIORITY 5-7). Tests must pass at each stage.

### Conflict 3: Review Finding #2 vs Current Code
**Review #2**: Says FeatureSnapshot extraction not implemented
**Current code**: `_extract_canonical_snapshot()` exists in service.py

**Resolution**: Verify whether `_extract_canonical_snapshot()` actually calls `extract_feature_snapshot()` or just uses legacy `extract_features()`. If legacy, refactor to use canonical function.

---

## Review Findings - Concrete Fixes

### Finding 1: Canonical pipeline never wired
**Status**: PARTIALLY FIXED - pipeline exists but has bugs
**Fix**: Debug generate_full_prediction() to find why predicted_score is None
**Location**: backend/app/prediction/service.py lines 740-1020

### Finding 2: FeatureSnapshot extraction not implemented
**Status**: NEEDS VERIFICATION
**Fix**: Ensure `_extract_canonical_snapshot()` calls `extract_feature_snapshot()` from feature_snapshot.py
**Location**: backend/app/prediction/service.py

### Finding 3: Hardcoded confidence inputs
**Status**: NEEDS SEARCH & DESTROY
**Fix**: Search for `model_agreement=1.0` and `data_quality_score=0.7`, replace with pipeline values
**Location**: backend/app/prediction/service.py, possibly confidence_engine.py

### Finding 4: No PipelineResult reuse
**Status**: NEEDS REFACTORING
**Fix**: Create `_execute_pipeline()` returning PipelineResult, refactor all methods to reuse it
**Location**: backend/app/prediction/service.py

### Finding 5: Ensemble agreement not from models
**Status**: NEEDS VERIFICATION
**Fix**: Verify ensemble_result.metadata['model_agreement'] flows to confidence assessment
**Location**: backend/app/prediction/service.py lines 836+

### Finding 6: DataQualityEngine unused
**Status**: NEEDS INSTANTIATION
**Fix**: Add `self.data_quality_engine = DataQualityEngine()` to __init__, call in _extract_canonical_snapshot
**Location**: backend/app/prediction/service.py lines 90-153

### Finding 7: Calibration never fitted
**Status**: ACCEPTABLE FOR PHASE 1
**Fix**: Document in metadata that calibration is unfitted, expose is_fitted status
**Location**: backend/app/prediction/calibration_engine.py

### Finding 8: API backward compatibility untested
**Status**: NEEDS NEW TEST
**Fix**: Add test comparing response schemas before/after pipeline changes
**Location**: backend/tests/test_match_intelligence.py

---

## Success Criteria

### Must Have (Blocking Completion)
- ✅ All 974+ tests passing, 0 failing
- ✅ No hardcoded model_agreement=1.0 or data_quality_score=0.7 in production code
- ✅ Single pipeline execution (no duplicate feature extraction)
- ✅ DataQualityEngine instantiated and used
- ✅ Canonical pipeline: Match → FeatureSnapshot → ModelOrchestrator → Ensemble → Calibration → Confidence → Markets → Selector → Versioning
- ✅ SmartMarketSelector implemented and integrated
- ✅ PredictionVersionManager stores frozen picks
- ✅ API backward compatibility verified

### Should Have (Strongly Recommended)
- ✅ PipelineResult dataclass reused across all methods
- ✅ Full test coverage for SmartMarketSelector (15+ tests)
- ✅ API documentation updated for new mensione_pick structure
- ✅ Calibration unfitted status documented

### Nice to Have (Optional)
- Frontend typecheck/lint/build verification
- API smoke test with curl/httpie
- Performance benchmarks comparing old vs new pipeline

---

## Execution Strategy

1. **Fast Fixes First**: Fix the test team IDs (5 minutes) to get to green
2. **Verify Then Fix**: Inspect pipeline code before making changes
3. **Incremental Testing**: Run tests after each priority item
4. **No Speculation**: Read code before claiming what it does
5. **Preserve Working Code**: Don't refactor what already works
6. **Clear Error Messages**: If pipeline fails, log useful diagnostics

---

## Notes for Implementer

- DevelopmentProvider is COMPLETE with 20 matches - don't add more data
- Test failure is test bug (wrong team IDs), not provider bug
- Pipeline structure exists but may have bugs - debug, don't rebuild
- Review.json findings are from BEFORE current code state - verify each one
- SmartMarketSelector is NEW functionality - implement after pipeline works
- PredictionVersionManager extension is additive - safe to implement last
- Backward compatibility is critical - don't break existing API contracts
- Use `.venv\Scripts\python.exe` on Windows (not `python` or `python3`)

---

## Timeline Estimate

- PRIORITY 1 (Fix test): 10 minutes
- PRIORITY 2 (Verify/fix pipeline): 30-60 minutes
- PRIORITY 3 (Hardcoded values): 20 minutes
- PRIORITY 4 (PipelineResult): 45 minutes
- PRIORITY 5 (SmartMarketSelector): 60 minutes
- PRIORITY 6 (Integration): 30 minutes
- PRIORITY 7 (Versioning): 30 minutes
- PRIORITY 8 (API test): 15 minutes
- PRIORITY 9 (Audit): 20 minutes

**Total: 4-5 hours** for complete implementation and verification

---

**Last Updated**: 2026-10-05 (generated from workflow wf_0b6ce076ee27092a)

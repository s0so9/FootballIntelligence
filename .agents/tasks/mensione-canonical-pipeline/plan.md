# Implementation Plan: MENSIONE Canonical Pipeline + Smart Market Selection

## Overview

This plan implements the complete MENSIONE canonical prediction pipeline with Smart Market Selection architecture. The work is organized into features that build progressively on each other, starting with fixing the 2 failing tests.

## Current State Analysis

**Test Status:** 972 passing, 2 failing
- `test_match_intelligence.py::TestBackwardCompatibility::test_prediction_endpoint_still_works` → Returns 400 "Insufficient data"
- `test_prediction_service.py::TestDevelopmentDataFallback::test_full_prediction_pipeline_with_development_fallback` → AnalysisContext.predicted_score is None

**Root Cause:** DevelopmentProvider has only 4 mock matches. When `generate_full_prediction()` runs, ModelOrchestrator executes all 7 models (Poisson, Dixon-Coles, Elo, Monte Carlo, Negative Binomial, Form-Adjusted, Logistic Regression). Models requiring extensive historical data fail gracefully, but when ALL models fail due to insufficient data, the pipeline returns an empty AnalysisContext with no prediction.

**Canonical Pipeline Verified:**
- ✓ ModelOrchestrator registers all 7 models (verified in `model_orchestrator.py:create_default_registry()`)
- ✓ EnsembleEngine used via EnsembleIntegration (verified in `service.py:144`)
- ✓ CalibrationEngine used via CalibrationIntegration (verified in `service.py:820`)
- ✓ Confidence computed from real pipeline values via ConfidenceIntegration (verified in `service.py:836`)
- ✓ Single pipeline execution in `generate_full_prediction()` (verified - no duplicate model runs)
- ✓ MarketDerivationEngine derives markets from score distribution (verified in `service.py:868`)

**Key Files:**
- Pipeline: `backend/app/prediction/service.py` (PredictionService.generate_full_prediction)
- Orchestration: `backend/app/prediction/model_orchestrator.py` (ModelOrchestrator)
- Models: `backend/app/prediction/{poisson,dixon_coles,elo,monte_carlo,negative_binomial,form_adjusted,logistic_regression}.py`
- Market Derivation: `backend/app/prediction/market_derivation.py` (MarketDerivationEngine)
- Ensemble: `backend/app/prediction/ensemble_engine.py` (EnsembleEngine)
- Calibration: `backend/app/prediction/calibration_engine.py` (CalibrationEngine)
- Confidence: `backend/app/prediction/confidence_engine.py` (ConfidenceEngine)
- Versioning: `backend/app/prediction/prediction_version.py` (PredictionVersionManager)
- Provider: `backend/app/providers/development.py` (DevelopmentProvider)
- Tests: `backend/tests/{test_match_intelligence.py,test_prediction_service.py}`

---

## Implementation Plan

### ✓ FEAT-001: Fix 2 Failing Tests (Enhance DevelopmentProvider Historical Data)

**Type:** fix  
**Priority:** CRITICAL - Must complete first

**Description:**
Fix the 2 failing tests by ensuring DevelopmentProvider provides sufficient historical match data for at least the Poisson model to execute successfully. The canonical pipeline gracefully handles partial model failures, but needs at least ONE model to succeed. Enhance DevelopmentProvider fixtures without fabricating real football data.

**Steps:**

1. Read `backend/app/providers/development.py` and count existing matches (currently 4)
   - Verify existing teams: dev_team_alpha, dev_team_beta, dev_team_gamma, dev_team_delta

2. Extend DevelopmentProvider._init_mock_data() to add 16 more historical matches (total: 20 matches)
   - Matches should be clearly labeled with `[DEV]` prefix or DEVELOPMENT indicators
   - Create matches spanning 3-4 months in the past for all 4 teams
   - Include varied scorelines: home wins, away wins, draws
   - Include varied scores: 0-0, 1-0, 2-1, 3-0, 1-1, 2-2, etc. (not all 1-1)
   - Set status=MatchStatus.FINISHED, outcome appropriately, home_score/away_score
   - Set scheduled_at to dates in the past (today - 15 days, today - 22 days, etc.)
   - Ensure each team has at least 5-6 completed matches for historical analysis

3. Ensure mock team statistics exist for the new matches
   - Add entries to `_team_statistics` list
   - Include possession (40-60%), shots (8-18), shots_on_target (3-8), corners (4-10), fouls (10-16)
   - Keep xG and xG_against as None (don't fabricate xG data unless necessary)

4. Run failing test 1 to verify fix:
   ```powershell
   cd backend
   .\.venv\Scripts\python.exe -m pytest tests/test_match_intelligence.py::TestBackwardCompatibility::test_prediction_endpoint_still_works -v
   ```
   - Expected: 200 OK response with prediction probabilities
   - Verify response contains: home_win_probability, draw_probability, away_win_probability

5. Run failing test 2 to verify fix:
   ```powershell
   cd backend
   .\.venv\Scripts\python.exe -m pytest tests/test_prediction_service.py::TestDevelopmentDataFallback::test_full_prediction_pipeline_with_development_fallback -v
   ```
   - Expected: AnalysisContext.predicted_score is not None
   - Verify context contains: predicted_score, mensione_pick, prediction_version_id

6. Run full backend test suite to ensure no regressions:
   ```powershell
   cd backend
   .\.venv\Scripts\python.exe -m pytest tests/ -v --tb=short
   ```
   - Expected: 974 passed, 0 failed (all tests passing)

**Acceptance Criteria:**
- [x] DevelopmentProvider has 20+ historical matches with varied outcomes
- [x] At least Poisson model can execute successfully with DevelopmentProvider data
- [x] Test `test_prediction_endpoint_still_works` passes (returns 200 with probabilities)
- [x] Test `test_full_prediction_pipeline_with_development_fallback` passes (predicted_score not None)
- [x] Full test suite passes with 0 failures
- [x] No fabricated real football data (all data clearly marked as DEVELOPMENT)

**Verification:**
```powershell
cd C:\FootballIntelligence\backend
.\.venv\Scripts\python.exe -m pytest tests/ -v --tb=short
# Expected: 974 passed, 0 failed
```

**Files:**
- Modify: `backend/app/providers/development.py`

---

### ✓ FEAT-002: Implement SmartMarketSelector Architecture

**Type:** feat  
**Priority:** HIGH - Core new feature

**Description:**
Implement the SmartMarketSelector that evaluates all available markets from MarketProbabilities, ranks them by quality, applies filters, and selects the single best tip or issues a PASS decision. This replaces the current MensionePickGenerator approach with a more sophisticated market evaluation system.

**Steps:**

1. Create `backend/app/prediction/market_selector.py` with SmartMarketSelector class
   - Read existing `backend/app/prediction/mensione_pick.py` to understand current MensionePickGenerator
   - Read `backend/app/prediction/market_derivation.py` to understand MarketProbabilities structure

2. Define BestTip dataclass in market_selector.py:
   ```python
   @dataclass
   class BestTip:
       match_id: str
       market: str  # e.g. "HOME_WIN", "OVER_2_5", "BTTS_YES"
       selection: str  # Human-readable selection
       probability: float  # Calibrated model probability
       confidence: float  # Overall confidence score (0.0-1.0)
       model_agreement: float  # Agreement between models (0.0-1.0)
       data_quality: float  # Data quality score (0.0-1.0)
       edge: Optional[float]  # Edge over bookmaker odds (when available)
       fair_odds: float  # Fair odds from model probability
       bookmaker_odds: Optional[float]  # Bookmaker odds (when available)
       odds_movement: Optional[str]  # "rising", "falling", "stable" (when available)
       value_classification: str  # "STRONG_VALUE", "VALUE", "NEUTRAL", "NEGATIVE_VALUE"
       risk_level: str  # "LOW", "MEDIUM", "HIGH"
       selection_score: float  # Overall selection score (0.0-1.0)
       selector_reason: str  # Why this market was selected
       timestamp: datetime
       pipeline_version: str
   ```

3. Define PassDecision dataclass:
   ```python
   @dataclass
   class PassDecision:
       match_id: str
       pass_reason: str  # "insufficient_data", "weak_agreement", "poor_calibration", "negative_value", "no_qualifying_market", "high_uncertainty"
       evaluated_markets_count: int
       best_market_details: Optional[Dict[str, Any]]  # Details of closest market that didn't qualify
       timestamp: datetime
       pipeline_version: str
   ```

4. Implement SmartMarketSelector.__init__():
   - Parameters: min_confidence (0.4), min_probability (0.5), min_edge (0.0), max_risk_level ("HIGH")
   - Store thresholds for filtering

5. Implement SmartMarketSelector.evaluate_and_select():
   - Input: MarketProbabilities, ConfidenceAssessment, Optional[Dict[str, float]] odds_data
   - Step 1: Extract all available markets from MarketProbabilities
   - Step 2: For each market, calculate selection_score combining:
     * Market probability (higher is better for selections >50%)
     * Confidence score
     * Model agreement
     * Data quality
     * Edge (when bookmaker odds available)
     * Historical reliability (when available - start with None)
   - Step 3: Apply filters:
     * confidence >= min_confidence
     * probability >= min_probability (for positive selections)
     * edge >= min_edge (when odds available)
     * risk_level <= max_risk_level
   - Step 4: Rank qualifying markets by selection_score (descending)
   - Step 5: Return BestTip for highest-ranked market OR PassDecision if none qualify

6. Implement value_classification logic:
   - STRONG_VALUE: edge >= 0.10 (10%+)
   - VALUE: edge >= 0.05 (5-10%)
   - NEUTRAL: edge >= 0.0 (0-5%)
   - NEGATIVE_VALUE: edge < 0.0

7. Implement risk_level logic:
   - LOW: confidence >= 0.7, model_agreement >= 0.8, data_quality >= 0.7
   - MEDIUM: confidence >= 0.5, model_agreement >= 0.6, data_quality >= 0.5
   - HIGH: below MEDIUM thresholds

8. Create comprehensive unit tests in `backend/tests/test_market_selector.py`:
   - Test 1: Select best market when multiple qualify (verify highest selection_score wins)
   - Test 2: PASS when all markets below confidence threshold
   - Test 3: PASS when all markets below probability threshold
   - Test 4: PASS when all markets have negative edge
   - Test 5: PASS when insufficient data (pass_reason="insufficient_data")
   - Test 6: Value classification: STRONG_VALUE for 12% edge
   - Test 7: Value classification: VALUE for 6% edge
   - Test 8: Value classification: NEUTRAL for 2% edge
   - Test 9: Value classification: NEGATIVE_VALUE for -3% edge
   - Test 10: Risk level: LOW for high confidence/agreement/quality
   - Test 11: Risk level: MEDIUM for moderate scores
   - Test 12: Risk level: HIGH for low scores
   - Test 13: Selection with no bookmaker odds (edge=None, classify as NEUTRAL)
   - Test 14: Multiple markets with same probability (verify tie-breaking by confidence)
   - Test 15: PassDecision includes best_market_details showing why closest market didn't qualify

9. Run SmartMarketSelector tests:
   ```powershell
   cd backend
   .\.venv\Scripts\python.exe -m pytest tests/test_market_selector.py -v
   ```
   - Expected: All 15+ tests pass

**Acceptance Criteria:**
- [x] SmartMarketSelector class exists in `backend/app/prediction/market_selector.py`
- [x] BestTip and PassDecision dataclasses defined with all required fields
- [x] evaluate_and_select() method ranks markets by selection_score
- [x] Filters apply: min_confidence, min_probability, min_edge, max_risk_level
- [x] Value classification logic: STRONG_VALUE, VALUE, NEUTRAL, NEGATIVE_VALUE
- [x] Risk level logic: LOW, MEDIUM, HIGH
- [x] PassDecision issued when no markets qualify with appropriate pass_reason
- [x] 15+ unit tests covering all scenarios
- [x] All tests pass

**Verification:**
```powershell
cd C:\FootballIntelligence\backend
.\.venv\Scripts\python.exe -m pytest tests/test_market_selector.py -v
# Expected: 15+ passed
```

**Files:**
- Create: `backend/app/prediction/market_selector.py`
- Create: `backend/tests/test_market_selector.py`

---

### ✓ FEAT-003: Integrate SmartMarketSelector into Canonical Pipeline

**Type:** feat  
**Priority:** HIGH - Integration

**Description:**
Replace MensionePickGenerator with SmartMarketSelector in PredictionService.generate_full_prediction(). Update AnalysisContext schema to support BestTip/PassDecision structure. Update API response schemas to expose new fields.

**Steps:**

1. Read `backend/app/prediction/service.py` (PredictionService.generate_full_prediction)
   - Locate where MensionePickGenerator is called (around line 880)
   - Understand mensione_pick dict structure currently used

2. Modify PredictionService.__init__():
   - Replace `self.mensione_pick_generator = MensionePickGenerator(...)` with:
   ```python
   from app.prediction.market_selector import SmartMarketSelector
   self.market_selector = SmartMarketSelector(
       min_confidence=0.4,
       min_probability=0.5,
       min_edge=0.0,
       max_risk_level="HIGH"
   )
   ```

3. Modify PredictionService.generate_full_prediction() STEP 8 (around line 870-905):
   - Replace MensionePickGenerator.generate() call with SmartMarketSelector.evaluate_and_select()
   - Input: market_probs, confidence_assessment, odds_data
   - Output: Union[BestTip, PassDecision]
   - Convert BestTip/PassDecision to dict for AnalysisContext.mensione_pick

4. Update mensione_pick dict structure:
   - If BestTip: include all BestTip fields (market, selection, probability, confidence, model_agreement, data_quality, edge, fair_odds, bookmaker_odds, value_classification, risk_level, selection_score, selector_reason, predicted_score)
   - If PassDecision: include pass_decision=True, pass_reason, evaluated_markets_count, best_market_details

5. Read `backend/app/domain/analysis.py` (AnalysisContext dataclass)
   - Verify mensione_pick field type (Optional[Dict[str, Any]])
   - Field already supports dict structure, no schema change needed

6. Read `backend/app/api/v1/endpoints/matches.py` (prediction endpoint)
   - Locate get_match_prediction endpoint
   - Verify response schema includes mensione_pick

7. Update API response documentation in matches.py:
   - Add docstring describing new mensione_pick structure
   - Document BestTip fields vs PassDecision fields
   - Add example responses for both BestTip and PASS cases

8. Run integration test:
   ```powershell
   cd backend
   .\.venv\Scripts\python.exe -m pytest tests/test_prediction_service.py::TestDevelopmentDataFallback::test_full_prediction_pipeline_with_development_fallback -v
   ```
   - Expected: Test passes, mensione_pick contains SmartMarketSelector output

9. Run API endpoint test:
   ```powershell
   cd backend
   .\.venv\Scripts\python.exe -m pytest tests/test_match_intelligence.py -v
   ```
   - Expected: All tests pass

10. Test actual API response:
    ```powershell
    cd backend
    .\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
    # In another terminal:
    Invoke-WebRequest -Uri "http://127.0.0.1:8000/api/v1/matches/dev_match_002/prediction" -Method GET -UseBasicParsing | Select-Object StatusCode, Content
    ```
    - Expected: 200 OK, JSON contains mensione_pick with BestTip or PassDecision structure

**Acceptance Criteria:**
- [x] PredictionService uses SmartMarketSelector instead of MensionePickGenerator
- [x] generate_full_prediction() produces mensione_pick with BestTip or PassDecision structure
- [x] AnalysisContext.mensione_pick contains all SmartMarketSelector output fields
- [x] API response includes enhanced mensione_pick structure
- [x] API documentation describes new fields
- [x] Integration tests pass
- [x] API endpoint returns 200 with enhanced mensione_pick

**Verification:**
```powershell
cd C:\FootballIntelligence\backend
.\.venv\Scripts\python.exe -m pytest tests/test_prediction_service.py tests/test_match_intelligence.py -v
# Expected: All tests pass

# Also verify API manually:
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
# Test endpoint: GET /api/v1/matches/dev_match_002/prediction
```

**Files:**
- Modify: `backend/app/prediction/service.py`
- Modify: `backend/app/api/v1/endpoints/matches.py` (documentation)
- Potentially modify: `backend/app/domain/analysis.py` (if schema adjustment needed)

---

### ✓ FEAT-004: Extend PredictionVersionManager for Frozen Picks with Result Tracking Foundation

**Type:** feat  
**Priority:** MEDIUM - Track record infrastructure

**Description:**
Extend PredictionVersionManager to store SmartMarketSelector's BestTip as a frozen pick at prediction time. Add result tracking foundation fields (actual_result, profit_loss) that remain None until manually settled. This enables future historical accuracy calculation per market type.

**Steps:**

1. Read `backend/app/prediction/prediction_version.py` (PredictionVersionManager, PredictionVersion dataclass)
   - Understand current versioning structure
   - Verify fields: version_id, match_id, stage, prediction_data, model_versions, data_quality_score, confidence_score, created_at, notes

2. Extend PredictionVersion dataclass with frozen pick fields:
   ```python
   # Frozen MENSIONE Pick (for track record)
   selected_market: Optional[str] = None  # "HOME_WIN", "OVER_2_5", etc.
   selection_text: Optional[str] = None  # Human-readable selection
   selection_probability: Optional[float] = None  # Model probability at prediction time
   selection_confidence: Optional[float] = None  # Confidence score at prediction time
   selection_odds: Optional[float] = None  # Bookmaker odds (if available)
   selection_fair_odds: Optional[float] = None  # Fair odds from model
   selection_edge: Optional[float] = None  # Edge at prediction time
   value_classification: Optional[str] = None  # "STRONG_VALUE", "VALUE", "NEUTRAL", "NEGATIVE_VALUE"
   risk_level: Optional[str] = None  # "LOW", "MEDIUM", "HIGH"
   
   # Result Tracking (populated after match settlement)
   actual_result: Optional[str] = None  # "WON", "LOST", "PUSH", "VOID"
   profit_loss: Optional[float] = None  # P/L in units (e.g., +0.85, -1.00)
   settled_at: Optional[datetime] = None  # When result was recorded
   ```

3. Modify PredictionVersionManager.create_version():
   - Add optional parameter: `mensione_pick: Optional[Union[BestTip, Dict[str, Any]]] = None`
   - If mensione_pick is BestTip or dict with BestTip structure, populate frozen pick fields
   - If mensione_pick is PassDecision or None, leave frozen pick fields as None
   - Example:
   ```python
   if mensione_pick:
       if isinstance(mensione_pick, dict) and "market" in mensione_pick:
           version.selected_market = mensione_pick.get("market")
           version.selection_text = mensione_pick.get("selection")
           version.selection_probability = mensione_pick.get("probability")
           version.selection_confidence = mensione_pick.get("confidence")
           version.selection_odds = mensione_pick.get("bookmaker_odds")
           version.selection_fair_odds = mensione_pick.get("fair_odds")
           version.selection_edge = mensione_pick.get("edge")
           version.value_classification = mensione_pick.get("value_classification")
           version.risk_level = mensione_pick.get("risk_level")
   ```

4. Update PredictionService.generate_full_prediction() to pass mensione_pick to create_version():
   - Modify call to `self.version_manager.create_version()` (around line 955)
   - Add parameter: `mensione_pick=mensione_pick` (pass the dict or BestTip)

5. Add method to PredictionVersionManager for result settlement (future use):
   ```python
   def settle_prediction(
       self,
       version_id: str,
       actual_result: str,  # "WON", "LOST", "PUSH", "VOID"
       profit_loss: Optional[float] = None
   ) -> Optional[PredictionVersion]:
       """Settle a prediction with actual match result.
       
       This method will be called manually after matches finish.
       For now, it's a foundation for future track record calculation.
       """
       # Implementation: find version, update actual_result, profit_loss, settled_at
       # Return updated version
       pass  # TODO: implement when result ingestion is ready
   ```

6. Add query methods for future accuracy calculation:
   ```python
   def get_settled_picks_by_market(
       self,
       market_type: str,
       start_date: Optional[datetime] = None,
       end_date: Optional[datetime] = None
   ) -> List[PredictionVersion]:
       """Get all settled picks for a specific market type.
       
       Future use: calculate historical accuracy per market.
       Example: get_settled_picks_by_market("HOME_WIN") for home win accuracy.
       """
       # Implementation: filter by selected_market, actual_result is not None
       pass  # TODO: implement when track record analysis is built
   ```

7. Create unit tests in `backend/tests/test_prediction_version.py`:
   - Test 1: create_version with BestTip populates frozen pick fields
   - Test 2: create_version with PassDecision leaves frozen pick fields as None
   - Test 3: create_version without mensione_pick leaves frozen pick fields as None
   - Test 4: Frozen pick fields preserve market, probability, confidence, odds, edge
   - Test 5: actual_result and profit_loss remain None until settlement
   - Test 6: settle_prediction() method exists (even if not implemented)

8. Run PredictionVersionManager tests:
   ```powershell
   cd backend
   .\.venv\Scripts\python.exe -m pytest tests/test_prediction_version.py -v
   ```
   - Expected: All tests pass

9. Run integration test to verify frozen picks stored:
   ```powershell
   cd backend
   .\.venv\Scripts\python.exe -m pytest tests/test_prediction_service.py::TestDevelopmentDataFallback::test_full_prediction_pipeline_with_development_fallback -v
   ```
   - Expected: Test passes, PredictionVersion has frozen pick fields populated

**Acceptance Criteria:**
- [x] PredictionVersion dataclass extended with frozen pick fields (selected_market, selection_probability, selection_confidence, selection_odds, selection_edge, value_classification, risk_level)
- [x] PredictionVersion has result tracking fields (actual_result, profit_loss, settled_at) initialized to None
- [x] create_version() accepts mensione_pick parameter and populates frozen pick fields for BestTip
- [x] create_version() leaves frozen pick fields None for PassDecision or when mensione_pick=None
- [x] settle_prediction() method exists as foundation (implementation optional)
- [x] get_settled_picks_by_market() method exists as foundation (implementation optional)
- [x] Unit tests verify frozen pick storage
- [x] Integration test verifies frozen picks stored in pipeline
- [x] No fabricated historical accuracy (actual_result/profit_loss remain None)

**Verification:**
```powershell
cd C:\FootballIntelligence\backend
.\.venv\Scripts\python.exe -m pytest tests/test_prediction_version.py -v
# Expected: All new tests pass

.\.venv\Scripts\python.exe -m pytest tests/test_prediction_service.py::TestDevelopmentDataFallback -v
# Expected: Integration test passes with frozen pick stored
```

**Files:**
- Modify: `backend/app/prediction/prediction_version.py`
- Modify: `backend/app/prediction/service.py` (pass mensione_pick to create_version)
- Modify or Create: `backend/tests/test_prediction_version.py`

---

### ✓ FEAT-005: Final Verification - Canonical Pipeline Audit

**Type:** test  
**Priority:** MEDIUM - Quality assurance

**Description:**
Comprehensive audit to verify the canonical pipeline is working correctly with no duplicate execution, no hardcoded values, and proper integration of all components. This is a verification-only feature with no code changes unless issues are found.

**Steps:**

1. Verify ModelOrchestrator registration:
   - Read `backend/app/prediction/model_orchestrator.py:create_default_registry()`
   - Count registered models: should be exactly 7
   - List: Poisson, Dixon-Coles, Elo, Monte Carlo, Negative Binomial, Form-Adjusted, Logistic Regression
   - ✓ VERIFIED in exploration: all 7 models registered

2. Verify EnsembleEngine usage:
   - Read `backend/app/prediction/service.py:generate_full_prediction()`
   - Confirm EnsembleIntegration.combine_predictions() is called
   - Verify no duplicate ensemble calculation
   - ✓ VERIFIED in exploration: EnsembleIntegration used at line 809

3. Verify CalibrationEngine usage:
   - Read `backend/app/prediction/service.py:generate_full_prediction()`
   - Confirm CalibrationIntegration.calibrate_prediction() is called
   - Verify no duplicate calibration
   - ✓ VERIFIED in exploration: CalibrationIntegration used at line 820

4. Verify Confidence calculation:
   - Read `backend/app/prediction/confidence_engine.py`
   - Search for hardcoded values: `grep -n "model_agreement\s*=\s*1\.0" backend/app/prediction/*.py`
   - Search for hardcoded values: `grep -n "data_quality_score\s*=\s*0\.7" backend/app/prediction/*.py`
   - Verify ConfidenceIntegration.assess_confidence() uses real pipeline values
   - ✓ VERIFIED in exploration: ConfidenceIntegration computes from pipeline values at line 836

5. Verify single pipeline execution:
   - Read PredictionService.generate_full_prediction() completely
   - Verify no repeated calls to:
     * extract_feature_snapshot
     * ModelOrchestrator.run_all
     * EnsembleIntegration.combine_predictions
     * CalibrationIntegration.calibrate_prediction
     * MarketDerivationEngine.derive
   - ✓ VERIFIED in exploration: single execution flow, no duplicates

6. Verify market intelligence connection:
   - Read `backend/app/prediction/market_derivation.py` (MarketDerivationEngine)
   - Verify derive() method converts score distribution to market probabilities
   - Verify markets include: 1X2, Over/Under 0.5/1.5/2.5/3.5, BTTS, Double Chance, Team Totals
   - ✓ VERIFIED in exploration: MarketDerivationEngine derives all markets at line 868

7. Run full backend test suite:
   ```powershell
   cd backend
   .\.venv\Scripts\python.exe -m pytest tests/ -v --tb=short -k "not slow"
   ```
   - Expected: All tests pass (974+)
   - If any test fails due to findings in audit, fix and rerun

8. Run specific pipeline integration tests:
   ```powershell
   cd backend
   .\.venv\Scripts\python.exe -m pytest tests/test_model_orchestrator.py -v
   .\.venv\Scripts\python.exe -m pytest tests/test_prediction_service.py -v
   .\.venv\Scripts\python.exe -m pytest tests/test_confidence_engine.py -v
   .\.venv\Scripts\python.exe -m pytest tests/test_ensemble_engine.py -v
   .\.venv\Scripts\python.exe -m pytest tests/test_calibration_engine.py -v
   ```
   - Expected: All component tests pass

9. Check for hardcoded confidence values:
   ```powershell
   cd backend
   Select-String -Path "app\prediction\*.py" -Pattern "model_agreement\s*=\s*(0\.\d+|1\.0)" | Where-Object { $_.Line -notmatch "^(\s*#|.*def.*model_agreement)" }
   ```
   - Expected: Only legitimate assignments (parameters, method returns), no hardcoded production values

10. Check for hardcoded data quality:
    ```powershell
    cd backend
    Select-String -Path "app\prediction\*.py" -Pattern "data_quality.*=\s*0\.\d+" | Where-Object { $_.Line -notmatch "^(\s*#|.*def.*data_quality)" }
    ```
    - Expected: Only legitimate assignments, no hardcoded production values

11. Document findings:
    - If issues found: create list of findings, fix them, rerun tests
    - If no issues: confirm canonical pipeline verified

**Acceptance Criteria:**
- [x] All 7 models registered in ModelOrchestrator
- [x] EnsembleEngine used (no duplicate ensemble systems)
- [x] CalibrationEngine used (no duplicate calibration systems)
- [x] Confidence computed from real pipeline values (no hardcoded model_agreement=1.0 or data_quality=0.7)
- [x] Single pipeline execution (no duplicate model runs)
- [x] Market intelligence connected to canonical pipeline
- [x] Full test suite passes (974+ tests)
- [x] No hardcoded confidence or data quality values in production code
- [x] Audit report confirms canonical pipeline integrity

**Verification:**
```powershell
cd C:\FootballIntelligence\backend
.\.venv\Scripts\python.exe -m pytest tests/ -v --tb=short
# Expected: 974+ passed, 0 failed

# Verify no hardcoded values:
Select-String -Path "app\prediction\*.py" -Pattern "(model_agreement|data_quality_score)\s*=\s*[0-9]" | Where-Object { $_.Line -notmatch "^(\s*#|.*def)" }
# Expected: No suspicious hardcoded values in production code
```

**Files:**
- Read only (audit): All files in `backend/app/prediction/`
- Fix if needed: Any files where issues are found
- Document: Create audit report in PROGRESS.md

---

## Summary

**Total Features:** 5 (1 fix + 4 features)

**Estimated Completion Order:**
1. FEAT-001: Fix tests (1-2 hours) - CRITICAL
2. FEAT-002: SmartMarketSelector (2-3 hours) - Core feature
3. FEAT-003: Pipeline integration (1-2 hours) - Integration
4. FEAT-004: Frozen picks tracking (1-2 hours) - Track record
5. FEAT-005: Final audit (1 hour) - Verification

**Key Constraints:**
- NO rewriting of existing models (poisson.py, dixon_coles.py, elo.py, etc.)
- NO duplicate ensemble/calibration systems
- NO fabricated bookmaker odds, xG, injuries, or historical accuracy
- NO breaking Phase 1-5 functionality
- Preserve DevelopmentProvider determinism
- Maintain backward API compatibility

**Success Metrics:**
- ✓ 974+ tests passing, 0 failing
- ✓ SmartMarketSelector selects best market or issues PASS
- ✓ Frozen picks stored with market type for future accuracy tracking
- ✓ API returns enhanced MENSIONE pick structure
- ✓ Canonical pipeline verified (no duplicates, no hardcoded values)

**Next Steps After This Plan:**
- Phase 6: Implement result ingestion to populate actual_result/profit_loss
- Phase 7: Build historical accuracy dashboard per market type
- Phase 8: Implement odds scraping for real bookmaker edge calculation
- Phase 9: Add market-specific reliability scoring based on historical performance

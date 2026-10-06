# Implementation Plan: Fix Prediction API Integration (fotmob_5181855 → 404)

## Problem Analysis

The frontend requests `GET /api/v1/matches/fotmob_5181855/prediction` but receives 404 because:

1. **Adapter creates domain IDs with provider prefix**: `adapter.py` line ~219: `match_id = f"{pm.provider}_{pm.source_id}"` (e.g., "fotmob_5181855")
2. **Prediction endpoint passes prefixed ID unchanged**: `matches.py` line ~347: `match = provider.get_match(match_id)` passes "fotmob_5181855" directly to adapter
3. **Adapter passes prefixed ID to ProviderManager unchanged**: `adapter.py` line ~216: `self._exec(self._manager.get_match(match_id))` passes "fotmob_5181855"
4. **ProviderManager routes to all providers with prefixed ID**: `manager.py` line ~182: tries sofascore, ryzellx, fotmob, openligadb with "fotmob_5181855"
5. **Individual providers expect ONLY numeric ID**: 
   - fotmob: `endpoint = "/api/data/matchDetails"`, `params = {"matchId": match_id}` expects "5181855"
   - ryzellx: `endpoint = f"/api/match/{match_id}"` expects "5181855"
   - openligadb: `endpoint = f"/getmatchdata/{match_id}"` expects numeric ID
6. **All providers fail, return None → 404**

## Root Cause

The adapter creates prefixed domain IDs (`"{provider}_{source_id}"`) for consistency, but `get_match()` cannot resolve them back to the source provider + numeric ID.

## Solution Architecture

Add ID parsing logic to `adapter.get_match()` to:
1. Detect prefixed IDs (pattern: `{provider}_{numeric_id}`)
2. Extract provider name and numeric source_id
3. Route directly to the specific provider's `get_match()`
4. Fall back to ProviderManager routing for non-prefixed IDs (backward compatibility)

This preserves the existing ProviderManager routing for unprefixed IDs while supporting the prefixed IDs that the adapter itself generates.

---

## Implementation Steps

- [ ] **1. Add ID parsing logic to ProviderManagerAdapter.get_match()**
  
  **What:** Modify `backend/app/providers/adapter.py` `get_match()` method to parse prefixed match IDs and route to specific providers.
  
  **Details:**
  - Parse `match_id` for pattern `{provider}_{source_id}` using regex or split
  - Known providers: fotmob, ryzellx, openligadb, sofascore
  - If match: extract provider name and numeric source_id
  - Call specific provider: `self._manager._providers[provider_name].get_match(source_id)`
  - If no match or provider not available: fall back to existing `self._exec(self._manager.get_match(match_id))`
  - Handle ProviderNotFoundError and return None (existing behavior)
  
  **Files:** 
  - `backend/app/providers/adapter.py` (modify `get_match()` at line ~215)
  
  **Verify:** 
  ```powershell
  # Run provider adapter tests
  pytest backend/tests/test_providers_adapter.py -v
  
  # Run prediction endpoint tests
  pytest backend/tests/test_api_matches.py::TestMatchPredictionEndpoint -v
  ```

- [ ] **2. Add test cases for prefixed match ID resolution**
  
  **What:** Add tests to verify adapter correctly parses and routes prefixed match IDs.
  
  **Details:**
  - Test: `fotmob_12345` → routes to fotmob provider with ID "12345"
  - Test: `ryzellx_67890` → routes to ryzellx provider with ID "67890"
  - Test: `openligadb_54321` → routes to openligadb provider with ID "54321"
  - Test: unprefixed `12345` → falls back to ProviderManager routing (backward compatibility)
  - Test: invalid provider `invalid_12345` → falls back to ProviderManager routing
  - Test: malformed `fotmob_` → falls back to ProviderManager routing
  
  **Files:**
  - `backend/tests/test_providers_adapter.py` (add test class `TestPrefixedMatchIDResolution`)
  
  **Verify:**
  ```powershell
  pytest backend/tests/test_providers_adapter.py::TestPrefixedMatchIDResolution -v
  ```

- [ ] **3. Test prediction endpoint with real fotmob match ID**
  
  **What:** Manually test the failing match ID `fotmob_5181855` through the prediction endpoint.
  
  **Details:**
  - Start backend: `cd backend && python -m uvicorn app.main:app --host 0.0.0.0 --port 8002 --reload`
  - Test GET `/api/v1/matches/fotmob_5181855` (should return 200 with match data)
  - Test GET `/api/v1/matches/fotmob_5181855/prediction` (should return 200 or prediction unavailable, NOT 404)
  - Document response: actual prediction, PASS, or unavailable data (all valid)
  
  **Files:** None (manual verification)
  
  **Verify:**
  ```powershell
  # Test match lookup
  curl http://127.0.0.1:8002/api/v1/matches/fotmob_5181855
  
  # Test prediction endpoint
  curl http://127.0.0.1:8002/api/v1/matches/fotmob_5181855/prediction
  ```

- [ ] **4. Add frontend error handling for prediction states**
  
  **What:** Ensure frontend distinguishes between loading, unavailable, and error states for predictions.
  
  **Details:**
  - Check `Dashboard.tsx` line ~89: already has try-catch for `getMatchPrediction()`
  - Check `MatchDetail.tsx` line ~57: already has try-catch
  - Check `Predictions.tsx` line ~41: already has try-catch
  - Verify: frontend shows appropriate Turkish messages:
    - Loading: "Veriler yükleniyor..."
    - Unavailable: "Bu maç için yeterli tahmin verisi henüz mevcut değil."
    - Error: "Tahmin servisine ulaşılamadı."
  - Add logging for 404 errors vs prediction unavailable (mensione_pick.pass_decision === true)
  
  **Files:**
  - `frontend/src/pages/Dashboard.tsx` (verify error handling at line ~89-95)
  - `frontend/src/pages/MatchDetail.tsx` (verify error handling at line ~57-63)
  - `frontend/src/pages/Predictions.tsx` (verify error handling at line ~41-49)
  
  **Verify:**
  ```powershell
  # Type-check frontend
  cd frontend && npm run type-check
  
  # Build frontend
  npm run build
  ```

- [ ] **5. Test MENSIONE Picks page end-to-end**
  
  **What:** Verify the frontend Picks page loads and handles the previously failing match.
  
  **Details:**
  - Start backend: `cd backend && python -m uvicorn app.main:app --host 0.0.0.0 --port 8002 --reload`
  - Start frontend: `cd frontend && npm run dev`
  - Navigate to `http://localhost:5173/`
  - Verify MENSIONE PICKS section:
    - Does NOT remain stuck on "Veriler yükleniyor..."
    - Shows actual predictions OR "Bu maç için yeterli tahmin verisi henüz mevcut değil." OR clear error message
    - No console errors related to 404
  - Test match detail page for fotmob_5181855 if visible in list
  
  **Files:** None (manual verification)
  
  **Verify:** Manual browser testing

- [ ] **6. Run regression tests**
  
  **What:** Ensure existing prediction and provider functionality still works.
  
  **Details:**
  - Run all provider tests: `pytest backend/tests/test_providers*.py -v`
  - Run all prediction tests: `pytest backend/tests/test_prediction*.py -v`
  - Run matches endpoint tests: `pytest backend/tests/test_api_matches.py -v`
  - Verify `/matches?from_date=2026-10-06` still returns 111 matches with `is_development_data = false`
  
  **Files:** None (test execution)
  
  **Verify:**
  ```powershell
  # Provider tests
  pytest backend/tests/ -k "provider" -v
  
  # Prediction tests
  pytest backend/tests/ -k "prediction" -v
  
  # API tests
  pytest backend/tests/test_api_matches.py -v
  
  # Verify matches endpoint still works
  curl "http://127.0.0.1:8002/api/v1/matches?from_date=2026-10-06"
  ```

- [ ] **7. Update PROGRESS.md**
  
  **What:** Document the fix, verification results, and any remaining limitations.
  
  **Details:**
  - Add entry for "Fixed prediction API integration for prefixed match IDs"
  - Document: what was broken, root cause, solution approach
  - Document: verification results (tests passed, manual testing results)
  - Document: whether fotmob_5181855 returned a prediction, PASS, or unavailable
  - Note any remaining work (e.g., if data is genuinely unavailable for that match)
  
  **Files:**
  - `docs/PROGRESS.md` (append new entry)
  
  **Verify:** File updated and committed

---

## Key Design Decisions

1. **Adapter-level routing instead of ProviderManager change:** The adapter is responsible for domain model mapping, so it's the correct place to handle domain ID → provider routing. ProviderManager remains unchanged and continues to work with unprefixed IDs.

2. **Backward compatibility:** Unprefixed IDs fall back to ProviderManager's multi-provider routing (MATCH_DETAIL_ORDER). This preserves existing behavior for any code paths still using unprefixed IDs.

3. **No special-casing fotmob_5181855:** The solution works generically for all `{provider}_{id}` patterns.

4. **Frontend already handles errors correctly:** The frontend has try-catch blocks and shows appropriate messages. No frontend changes needed beyond verification.

5. **404 vs unavailable distinction:** 
   - 404 = match doesn't exist (backend cannot find the match entity)
   - 200 with `mensione_pick.pass_decision = true` = match exists but prediction unavailable (insufficient data)
   - The fix ensures we don't return 404 for matches that exist but have prefixed IDs

---

## Expected Outcomes

After implementation:
- ✅ `GET /api/v1/matches/fotmob_5181855` returns 200 (match found)
- ✅ `GET /api/v1/matches/fotmob_5181855/prediction` returns 200 (prediction or PASS, not 404)
- ✅ MENSIONE Picks page no longer stuck on "Veriler yükleniyor..."
- ✅ All existing tests pass
- ✅ `/matches?from_date=2026-10-06` still returns 111 real matches

## Risk Assessment

**Low risk:** 
- Single method change in adapter
- Backward compatible (fallback to existing behavior)
- No changes to ProviderManager, prediction service, or frontend logic
- Comprehensive test coverage ensures no regression

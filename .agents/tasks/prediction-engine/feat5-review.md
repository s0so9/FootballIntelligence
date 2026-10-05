# FEAT-005 Implementation Review

**Orchestration, Markets, MENSIONE PICK, API**

**Verdict**: NEEDS_CHANGES

Watch for: **confirmed** The predicted_score vs MENSIONE PICK separation exists in data structures but service.py doesn't populate both fields in the API response path (no predicted_score field added to AnalysisContext or Prediction). **confirmed** PredictionService is a legacy foundation-model-only service that doesn't execute the designed 13-stage pipeline (ensemble → calibration → confidence → markets → pick). **confirmed** API endpoint missing entirely — verification report acknowledges this was deferred. **likely** Immutability claim unverified: PredictionVersionManager has delete_version() method; no enforcement tests confirming overwrites rejected in the presence of real database writes.

---

## High-level view

MarketDerivationEngine derives all markets from score distributions with strict mathematical consistency checks. MensionePickGenerator maintains the design's separation between predicted_score (in the pick struct for context) and pick_market (the actual recommendation). PredictionVersionManager provides immutable versioning with stage-based organization, though the delete_version escape hatch exists and immutability enforcement depends on correct use of allow_stage_overwrite flags.

The integration gap is in service.py: it implements only the foundation Poisson model workflow (extract features → run Poisson → build markets), not the full MENSIONE engine pipeline (ensemble → calibration → confidence → Monte Carlo → market derivation → pick generation → versioning). The enriched AnalysisContext path doesn't populate a predicted_score field alongside MENSIONE pick because the service doesn't invoke MensionePickGenerator or create versioned predictions.

API endpoint is entirely missing. Without the endpoint, there's no response schema to verify the predicted_score vs mensione_pick separation in the wire format.

---

<details>
<summary>Issues (5)</summary>

1. **Predicted score field missing from API response path** — PredictionService doesn't add a `predicted_score` field to AnalysisContext or Prediction when building context. The separation exists in MensionePick struct but isn't propagated through the service layer. Add `predicted_score` field to AnalysisContext and populate it from the most likely scoreline.

2. **Full orchestration pipeline not implemented** — service.py runs only Poisson → markets path, not the designed 13-stage pipeline (ensemble → calibration → confidence → Monte Carlo → markets → pick). The verified components exist but aren't wired together. Implement the full pipeline or document the phased rollout plan.

3. **API endpoint missing** — No endpoint at `/api/v1/matches/{match_id}/prediction` to expose predictions. Cannot verify wire-format separation of predicted_score vs mensione_pick fields. Create the endpoint with response schema containing both fields.

4. **Immutability enforcement untested under database writes** — PredictionVersionManager has delete_version() and allows stage overwrites via flag. No test verifies that duplicate stage writes are rejected when persistence_service is configured. Add integration test with database persistence that confirms immutability violations raise ValueError.

5. **Service doesn't invoke versioning or pick generation** — PredictionService.predict_match() returns AnalysisContext, not PredictionVersion. Doesn't call PredictionVersionManager.create_version() or MensionePickGenerator.generate(). The core engine artifacts (versioned predictions, MENSIONE picks) aren't produced by the service. Wire versioning and pick generation into the service method.

</details>

---

<details>
<summary>Details</summary>

## Service layer doesn't populate predicted_score field

PredictionService.build_analysis_context() creates an AnalysisContext with prediction and prediction_markets, but doesn't extract the most likely scoreline from the score distribution and add it as a top-level field. The Prediction domain object has predicted_home_score and predicted_away_score fields, which service.py populates with home_lambda and away_lambda (expected goals), not the mode of the distribution.

When service.py calls market_analyser.analyse_match(), it passes correct_score_probs (the top scorelines), but this lives in the MatchMarketAnalysis struct, not in the AnalysisContext that the AI Analyst receives. The AI Analyst sees prediction.predicted_home_score (an xG value like 1.73) and prediction_markets, but there's no single `predicted_score: "2-1"` field at the top level.

The separation only exists in MensionePick struct, not in the API response schema or AnalysisContext that downstream consumers see.

## Full orchestration pipeline not implemented

The design (section 1.2) specifies a 13-stage pipeline:

1. Load match metadata → 2. Data Quality Gate → 3. Extract features → 4. Invoke models → 5. Collect predictions → 6. Weight models by reliability → 7. Combine into ensemble → 8. Apply contextual adjustments → 9. Calibrate probabilities → 10. Calculate confidence → 11. Derive markets → 12. Generate MENSIONE PICK → 13. Version and persist

PredictionService.predict_match() implements stages 1, 3, 4 (Poisson only), and 11 (markets via market_analyser for 1X2/BTTS/OU only, not full MarketDerivationEngine coverage). It doesn't invoke EnsembleEngine, CalibrationEngine, ConfidenceEngine, MensionePickGenerator, or PredictionVersionManager.

The ensemble_engine.py, calibration_engine.py, confidence_engine.py files exist, but service.py doesn't call them. This means the 811 passing tests validate isolated components, but the end-to-end pipeline that wires them together isn't executable. A match prediction request would run Poisson, derive 1X2/BTTS/OU markets, and return an AnalysisContext, but wouldn't produce a versioned prediction with calibrated probabilities, confidence scores, and a MENSIONE pick.

## Immutability enforcement untested under database writes

create_version() checks for existing versions at the same stage if allow_stage_overwrite=False (default), and raises ValueError if found. The check calls get_version_by_stage(), which delegates to persistence_service.get_versions() if persistence is configured, else reads from _memory_store.

No test verifies that this gate works when persistence_service is a real database-backed service. The tests in test_prediction_version.py likely use the in-memory fallback. If persistence_service.save_version() and get_versions() have bugs (e.g., get_versions filters by match_id but not stage, returning all versions and making the duplicate check always pass), the immutability claim fails.

Also, delete_version() exists with a warning comment ("This violates immutability principle..."). If this method is accessible in production code paths, someone can delete a version and rewrite it. The comment is a policy statement, not an enforcement mechanism.

## TrackRecordManager sample selection effect

record_outcome() creates a PredictionResult and persists it via persistence_service.save_track_record(). There's no filtering logic that skips failed predictions or low-confidence predictions.

One caveat: the system only records outcomes for predictions that were generated. If the DataQualityGate rejects a match entirely, no prediction is created, so there's no outcome to record. This is not cherry-picking; it's a sample selection effect. The track record reflects "all predictions the engine chose to make," not "all matches that occurred." If the engine only generates predictions when confidence > threshold, the track record will overstate performance relative to a policy of "predict everything."

## PredictionService doesn't invoke versioning or pick generation

predict_match() calls generate_prediction() → generate_prediction_markets() → build_analysis_context() and returns context. It doesn't call PredictionVersionManager.create_version() or MensionePickGenerator.generate(). The versioned prediction with mensione_pick lives in a parallel path that isn't connected.

The components are validated in isolation but not connected into a pipeline. The 811 tests prove each component works; they don't prove the system works end-to-end.

## Database migration not run

The verification report says the migration file was created (b1a2c3d4e5f6_prediction_engine_tables.py) but not run ("⚠️ NOT YET RUN"). Without running the migration, persistence_service will fail at runtime with "table does not exist" errors.

## API endpoint missing

No file at backend/app/api/v1/endpoints/predictions.py exists. Cannot verify: response schema has both predicted_score and mensione_pick fields at top level; predicted score is a scoreline string ("3-1"), not xG floats; mensione pick is a separate field with market, outcome, confidence, reasoning; backward compatibility with existing AnalysisContext consumers; the full pipeline (versioning, calibration, confidence, pick generation) is invoked by the endpoint.

The design specifies the endpoint should be at `/api/v1/matches/{match_id}/prediction`.

## Test coverage gap

The verification report claims 811 tests passing (up from 676 baseline), a net increase of 135 tests. Critical gap: no integration test that runs the full pipeline (service → versioning → persistence → API response). The tests validate isolated components. The system isn't tested end-to-end.

</details>

---

<details>
<summary>File Map</summary>

Full diff not provided; review based on file reads. Changed files (inferred from verification report and task description):

- **market_derivation.py** — MarketDerivationEngine derives all markets from score distributions with mathematical consistency checks
- **mensione_pick.py** — MensionePickGenerator ranks markets by EV/conviction, generates MENSIONE PICK separate from predicted score
- **prediction_version.py** — PredictionVersionManager provides immutable versioning with stage-based organization
- **change_attribution.py** — ChangeAttributionEngine explains prediction changes with proportional factor attribution
- **track_record.py** — TrackRecordManager stores all predictions and outcomes, calculates Brier/log loss/accuracy/ROI
- **service.py** — PredictionService (existing) used for reference; full orchestration pipeline not yet integrated
- **persistence.py** — PredictionPersistenceService wraps database writes for versions and track record
- **feat5-verification.md** — Verification report documenting test results and implementation status

API endpoint file (backend/app/api/v1/endpoints/predictions.py) does not exist.

</details>

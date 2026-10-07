# Brand Rebrand Review: MENSIONE → TUTAR X

Replace all user-facing MENSIONE branding with TUTAR X while preserving prediction logic, data integrity, and internal architecture.

**Verdict**: CHANGES_REQUESTED

Watch for: incomplete branding in LivePickCard component (4 user-facing MENSIONE references), incomplete branding in ComponentsTest page, several comment-only MENSIONE references that are lower priority. No prediction logic was modified (confirmed). Frontend build passed. Backend tests passed.

## High-level view

The core Dashboard, MensionePickCard, Sidebar, and API branding have been successfully updated to TUTAR X. Browser metadata, README, and backend API documentation now reflect TUTAR X branding. The LivePickCard component contains 4 user-facing MENSIONE badge labels that were overlooked and must be changed to TUTAR X. The ComponentsTest page (a test utility page) retains MENSIONE branding in its title, which should be updated for consistency. Several comment-only MENSIONE references remain in frontend source files (types, utilities, component documentation), but these are internal developer notes and lower priority. The prediction engine, feature engineering, database schemas, API contracts, and provider logic remain completely untouched, as required.

<details>
<summary>Issues (5)</summary>

1. **LivePickCard badges show MENSIONE branding** — Lines 43, 58, 91, and 131 in `frontend/src/components/live/LivePickCard.tsx` display "MENSIONE LIVE", "MENSIONE LIVE PASS", "MENSIONE LIVE - GEÇERSİZ", and "MENSIONE LIVE PICK" to users. Change all four to TUTAR X equivalents ("TUTAR X LIVE", "TUTAR X LIVE PASS", "TUTAR X LIVE - GEÇERSİZ", "TUTAR X LIVE PICK").

2. **ComponentsTest page title shows MENSIONE** — Line 25 in `frontend/src/pages/ComponentsTest.tsx` displays `<h1>MENSIONE Component Test</h1>` to users. Change to "TUTAR X Component Test".

3. **LivePickCard test assertions expect MENSIONE text** — Lines 58, 99, and 113 in `frontend/src/components/live/__tests__/LivePickCard.test.tsx` assert for "MENSIONE LIVE PICK", "MENSIONE LIVE PASS", and "MENSIONE LIVE - GEÇERSİZ". Update these to match the corrected TUTAR X badge text after fixing issue #1.

4. **Comment-only MENSIONE references in frontend** — Several files contain MENSIONE in comments/docstrings but not user-facing text: `frontend/src/api/types.ts` line 142, `frontend/src/types/live.ts` line 222, `frontend/src/utils/visualization.ts` line 2, `frontend/src/utils/visualization.test.ts` line 2, and `frontend/src/components/predictions/AIConfidence.tsx` lines 4-5. Update these for consistency but they're lower priority since they're not user-visible.

5. **ComponentsTest comment references MENSIONE** — Line 4 in `frontend/src/pages/ComponentsTest.tsx` says "Temporary page for testing MENSIONE components." Update to TUTAR X for consistency.

</details>

<details>
<summary>Details</summary>

## Dashboard and primary prediction card branding

The Dashboard component was updated across two commits. The MensionePickCard component's badge changed from "MENSIONE PICK" to "TUTAR X PICK" (line 336 in `MensionePickCard.tsx`). The Dashboard title (line 207) changed from "MENSIONE PICKS" to "TUTAR X PICKS" and the empty state message (line 223) from "Şu anda MENSIONE seçimi yok" to "Şu anda TUTAR X seçimi yok". The PerformanceOverview component (lines 27 and 83) changed from "MENSIONE Performans Takibi" to "TUTAR X Performans Takibi".

Component file names (`MensionePickCard.tsx`, `MensionePickCard.css`), CSS class names (`.mensione-pick-card`, `.mensione-pick-hero`, `.mensione-picks-grid`), and internal field names (`mensione_pick` in API responses) were preserved as internal technical identifiers.

## Live match card branding gap

The LivePickCard component (`frontend/src/components/live/LivePickCard.tsx`) displays four badge states all showing MENSIONE branding: unavailable (line 43: "MENSIONE LIVE"), pass decision (line 58: "MENSIONE LIVE PASS"), invalidated (line 91: "MENSIONE LIVE - GEÇERSİZ"), and active pick (line 131: "MENSIONE LIVE PICK"). None were changed to TUTAR X. This is the most significant branding gap in the review.

The corresponding test file (`frontend/src/components/live/__tests__/LivePickCard.test.tsx`) contains three assertions (lines 58, 99, 113) that check for the MENSIONE badge text. These will fail after the badge text is corrected.

## Header, sidebar, and browser metadata

The Sidebar component (lines 96-102 in `Sidebar.tsx`) was updated to reference `/tutar-x-logo.png` for the logo placeholder and display the tagline "Maçın geleceğini veriden oku." The browser title in `frontend/index.html` (line 8) was changed to "TUTAR X — Maçın geleceğini veriden oku." and the meta description (line 7) includes the full brand statement. The favicon reference (line 5) now points to `/tutar-x-favicon.svg`.

A placeholder note file (`LOGO_PLACEHOLDER_NOTES.md`) documents the logo integration strategy and required file paths for when the user provides the actual logo assets.

## API and backend branding

The backend `main.py` (lines 34-35, 60, 68) was updated to reflect TUTAR X branding in the FastAPI title ("TUTAR X API"), description, health check response, and root endpoint message. The matches endpoint documentation in `backend/app/api/v1/endpoints/matches.py` (lines 342, 357, 361) was updated to replace "MENSIONE PICK" with "TUTAR X PICK" in OpenAPI descriptions. The schemas file (`backend/app/api/v1/schemas.py` lines 99, 103) was updated to reference "TUTAR X PICK" in field descriptions.

The `mensione_pick` field name in JSON responses remains unchanged (documented in line 362 of matches.py and line 103 of schemas.py).

## Python module docstrings and comments

Docstrings and comments in Python prediction modules were updated to replace user-facing "MENSIONE" references with "TUTAR X" while preserving all internal identifiers. The `mensione_pick.py` module (line 1) now documents itself as "TUTAR X Pick generator (internal module name: mensione_pick for backward compatibility)". The market_selector.py docstrings (lines 1, 66) reference "TUTAR X canonical pipeline". The analysis.py and prediction.py modules (lines 123, 134, 317) were updated to reference "TUTAR X PICK" and "TUTAR X Prediction Engine Core".

Parameter names (`mensione_id`, `provider_to_mensione_ms`) and variable names (`MENSIONE_TO_SOFASCORE_IDS`) were preserved. Docstrings that explain these parameters were updated to clarify they're kept for backward compatibility.

## README and documentation

The root README.md (line 1) was updated to "# TUTAR X - Football Intelligence Platform" with the tagline "TUTAR X — Maçın geleceğini veriden oku." on line 3. Line 8 was changed to "TUTAR X is a comprehensive football analytics system...".

The generate_design.py script (lines 1, 24) was updated to reference "TUTAR X Prediction Engine" instead of "MENSIONE Prediction Engine".

## ComponentsTest page branding gap

The ComponentsTest page (`frontend/src/pages/ComponentsTest.tsx`) is a test utility page. Line 25 displays `<h1>MENSIONE Component Test</h1>` and line 4 contains a comment "Temporary page for testing MENSIONE components." Both should be updated to TUTAR X.

## Comment-only MENSIONE references

Several frontend files contain MENSIONE references in comments or docstrings but not in user-facing text:
- `frontend/src/api/types.ts` line 142: "MENSIONE Pick Response - SmartMarketSelector format"
- `frontend/src/types/live.ts` line 222: "MENSIONE LIVE PICK or PASS decision"
- `frontend/src/utils/visualization.ts` line 2: "MENSIONE Data Visualization Utilities"
- `frontend/src/utils/visualization.test.ts` line 2: "MENSIONE Data Visualization Rules - Test Suite"
- `frontend/src/components/predictions/AIConfidence.tsx` lines 4-5: "MENSIONE AI Confidence indicator" and "Uses custom CSS icons with MENSIONE green glow"

These are internal developer documentation and lower priority than user-visible gaps.

## Prediction logic preservation

No prediction logic, formulas, model weights, thresholds, feature engineering, or statistical calculations were modified. The diff shows no changes to core prediction files: `monte_carlo.py`, `calibration_engine.py`, `calibration.py`, `change_attribution.py`, feature engineering modules, model ensemble logic, confidence calculations, or provider integration.

The only prediction-related files modified were documentation strings in `mensione_pick.py`, `market_selector.py`, `service.py`, `prediction.py`, and `analysis.py`.

## Database and API contract preservation

Database models (`backend/app/database/models.py` line 428) were updated only in comments. No table names, column names, or field types were changed.

API endpoint paths remain unchanged. The `mensione_pick` field name in JSON responses was preserved throughout `schemas.py`, `analysis.py`, and `prediction_version.py`.

## CSS and internal identifiers preservation

CSS class names (`.mensione-pick-card`, `.mensione-pick-hero`, `.mensione-picks-grid`) and CSS variable names (`--glow-green-mensione`, `--color-accent-green`) were left unchanged. Only CSS comments (lines 54-56, 193-194 in `tokens.css` and line 449 in `MensionePickCard.css`) were updated from "MENSIONE PICK" to "TUTAR X PICK".

Component file names (`MensionePickCard.tsx`, `MensionePickCard.css`) were preserved.

## Test coverage

The plan document reports that `npm run build` succeeded (5.81s, no errors) after the final changes. Backend tests (`python -m pytest tests/test_mensione_pick.py -v`) passed with 7 tests. The health endpoint test (`python -m pytest tests/test_api_matches.py::TestHealthEndpoint -v`) passed with 2 tests.

The LivePickCard tests will fail once the badge text is corrected (issue #1) and will need updating.

</details>

## File map

<details>
<summary>36 files changed (full diff: `.agents/tasks/tutar-x-rebrand/full-diff.txt`)</summary>

**Frontend (user-facing branding):**
- `frontend/index.html` — browser title, favicon, meta description
- `frontend/src/components/layout/Sidebar.tsx` — logo placeholder, tagline
- `frontend/src/components/predictions/MensionePickCard.tsx` — "TUTAR X PICK" badge, comments
- `frontend/src/pages/Dashboard.tsx` — "TUTAR X PICKS" title, empty state message
- `frontend/src/components/track-record/PerformanceOverview.tsx` — performance tracking title
- `frontend/src/components/match/GeneralAnalysis.tsx` — component documentation (comment)

**Frontend (assets):**
- `frontend/public/tutar-x-favicon.svg` — new favicon placeholder

**Backend (API documentation and comments):**
- `backend/app/main.py` — FastAPI title, description, health check, root endpoint
- `backend/app/api/v1/endpoints/matches.py` — OpenAPI descriptions
- `backend/app/api/v1/schemas.py` — field descriptions
- `backend/app/domain/analysis.py` — docstrings, comments
- `backend/app/domain/prediction.py` — comments
- `backend/app/prediction/mensione_pick.py` — module docstring
- `backend/app/prediction/market_selector.py` — docstrings
- `backend/app/prediction/service.py` — comments
- `backend/app/prediction/feature_snapshot.py` — module comment
- `backend/app/database/models.py` — field comment
- `backend/app/prediction/prediction_version.py` — comments
- `backend/app/providers/sofascore.py` — docstring
- `backend/app/latency/models.py` — field description

**Backend (new scripts and utilities, not part of rebrand scope):**
- `backend/scripts/import_historical_data.py` — modified (not reviewed, out of scope)
- `backend/scripts/import_upcoming_matches.py` — new file (not reviewed, out of scope)
- `backend/scripts/inspect_fotmob_response.py` — new file (not reviewed, out of scope)
- `backend/scripts/quick_prediction_validation.py` — new file (not reviewed, out of scope)
- `backend/scripts/test_predictions_sample.py` — new file (not reviewed, out of scope)
- `backend/scripts/validate_data_coverage.py` — new file (not reviewed, out of scope)
- `backend/scripts/verify_historical_data.py` — new file (not reviewed, out of scope)
- `backend/app/providers/fotmob.py` — modified (not reviewed, out of scope)
- `backend/app/providers/openligadb.py` — modified (not reviewed, out of scope)

**Documentation:**
- `README.md` — title, tagline, product name
- `LOGO_PLACEHOLDER_NOTES.md` — new file documenting logo integration
- `scripts/generate_design.py` — documentation generator docstring
- `docs/PHASE10-GROUP1-2-REPORT.md` — new file (not reviewed, out of scope)
- `docs/PROGRESS.md` — updated (not reviewed, out of scope)

**Task management:**
- `.agents/tasks/tutar-x-rebrand/plan.md` — task execution plan and verification log

</details>

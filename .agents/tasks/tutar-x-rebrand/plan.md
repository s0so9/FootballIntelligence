# TUTAR X Brand Rebrand Implementation Plan

## Overview

This is a **BRAND REPLACEMENT / BRAND INJECTION task only**. Replace all user-facing MENSIONE branding with TUTAR X while preserving 100% of existing functionality, data, predictions, and internal architecture.

## Key Constraints

**DO NOT MODIFY:**
- Prediction logic, formulas, model weights, thresholds
- Feature engineering calculations
- Poisson calculations, ensemble logic, calibration
- Confidence calculations, pick generation
- Database schemas (table names, column names, field names)
- API endpoint paths or internal field names (e.g., `mensione_pick` stays as field name)
- Provider logic (FotMob, Ryzellx, OpenLigaDB, SofaScore, Easy Match)
- FastAPI routes and their internal behavior
- Any numerical/statistical outputs
- Internal technical identifiers that would break the application

**ONLY MODIFY:**
- User-facing text strings in UI components
- Page titles, meta tags, browser metadata
- Documentation and user-facing comments
- Component display text (not component names in code)
- Header/footer branding
- Logo placeholder references (waiting for actual logo file from user)

## Brand Replacements

### Primary Brand
- **MENSIONE** → **TUTAR X**

### Taglines and Slogans
- Main slogan: **"Maçın geleceğini veriden oku."**
- Brand statement: **"Geçmiş tekrar eder. Mesele onu görebilmektir."**

### Feature Branding
- **MENSIONE PREDICTION ENGINE** → **TUTAR X PREDICTION ENGINE**
- **MENSIONE AI ANALYST** → **TUTAR X AI ANALYST**
- **MENSIONE PICK** (UI display) → **TUTAR X PICK** (but keep field name `mensione_pick` in code)
- New feature concept: **TUTAR X EXPERIENCE** (for historical/similarity intelligence)

### Supporting Messages
- "Geçmiş maçlardan öğren."
- "Benzerlikleri keşfet."
- "Veriyi oku."
- "Maçı gör."

## Logo Placeholder Strategy

The user will provide the official TUTAR X logo later. For now:
- Reference logo as `/tutar-x-logo.svg` or `/tutar-x-logo.png` in code
- Update favicon reference to point to TUTAR X favicon (user will provide)
- Replace `/torres.jpg` reference in Sidebar with TUTAR X logo placeholder
- Document in comments: "TUTAR X logo will be provided by user"

---

## Implementation Steps

### Step 1: Frontend - HTML Metadata and Title

**What:** Update browser title, favicon reference, and meta tags in `frontend/index.html`.

**Files:**
- `c:\FootballIntelligence\frontend\index.html`

**Changes:**
- Line 5: Change favicon from `/favicon.svg` to `/tutar-x-favicon.svg` (placeholder, user will provide actual file)
- Line 8: Change `<title>Football Intelligence</title>` to `<title>TUTAR X — Maçın geleceğini veriden oku.</title>`
- Add meta description if not present: `<meta name="description" content="TUTAR X - Maçın geleceğini veriden oku. Geçmiş tekrar eder. Mesele onu görebilmektir." />`

**Verify:** Run `cd c:\FootballIntelligence\frontend && npm run build` — build succeeds with no errors.

---

### Step 2: Frontend - Sidebar Brand and Tagline

**What:** Replace MENSIONE brand display in Sidebar component with TUTAR X branding. Replace torres.jpg with TUTAR X logo placeholder.

**Files:**
- `c:\FootballIntelligence\frontend\src\components\layout\Sidebar.tsx`
- `c:\FootballIntelligence\frontend\src\components\layout\Sidebar.css` (review only, may need updates if hard-coded text exists)

**Changes in Sidebar.tsx:**
- Line 91: Comment says `{/* MENSIONE Brand */}` → change to `{/* TUTAR X Brand */}`
- Line 96: `src="/torres.jpg"` → change to `src="/tutar-x-logo.png"` (placeholder for user-provided logo)
- Line 97: `alt="MENSIONE"` → change to `alt="TUTAR X"`
- Line 102: `<p className="sidebar__tagline">Football Intelligence</p>` → change to `<p className="sidebar__tagline">Maçın geleceğini veriden oku.</p>`

**Verify:** Run `cd c:\FootballIntelligence\frontend && npm run build` — build succeeds. Visually inspect sidebar shows "TUTAR X" branding and new tagline.

---

### Step 3: Frontend - MensionePickCard Component Display Text

**What:** Update user-facing display text "MENSIONE PICK" to "TUTAR X PICK" in MensionePickCard component. **Do NOT rename the component file or class names**, only update the visible badge text.

**Files:**
- `c:\FootballIntelligence\frontend\src\components\predictions\MensionePickCard.tsx`

**Changes:**
- Line 2: Comment `* MensionePickCard Component - Premium Football Intelligence Card` → change to `* TutarXPickCard Component - Premium Football Intelligence Card` (comment only, helps future readers)
- Line 5: Comment `* MENSIONE green identity` → change to `* TUTAR X green identity`
- Line 336: `<div className="mensione-pick-hero__badge">MENSIONE PICK</div>` → change to `<div className="mensione-pick-hero__badge">TUTAR X PICK</div>`

**Note:** Keep the component file name as `MensionePickCard.tsx` and CSS class names as `mensione-pick-card`, `mensione-pick-hero`, etc. These are internal technical identifiers. Only the visible text "MENSIONE PICK" changes to "TUTAR X PICK".

**Verify:** Run `cd c:\FootballIntelligence\frontend && npm run build` — build succeeds. Visually inspect prediction cards show "TUTAR X PICK" badge.

---

### Step 4: Frontend - Dashboard and Page Display Text

**What:** Review Dashboard and other pages for any remaining user-facing "MENSIONE" or "Football Intelligence" references that should be replaced with TUTAR X branding.

**Files:**
- `c:\FootballIntelligence\frontend\src\pages\Dashboard.tsx`
- `c:\FootballIntelligence\frontend\src\pages\Dashboard.css` (CSS class names stay as-is, but check for content strings)

**Changes:**
- Review `Dashboard.tsx` for any hardcoded "MENSIONE" text in user-facing strings (unlikely, but check)
- CSS class names like `.mensione-picks-grid` should remain unchanged (internal identifiers)
- No changes expected here unless hardcoded branding text is found

**Verify:** Run `cd c:\FootballIntelligence\frontend && npm run build` — build succeeds. Review output for any remaining "MENSIONE" in rendered HTML.

---

### Step 5: Frontend - CSS Comments and Design Token Documentation

**What:** Update CSS comments that reference MENSIONE brand for clarity, but leave all class names and CSS variable names unchanged (they are technical identifiers).

**Files:**
- `c:\FootballIntelligence\frontend\src\styles\tokens.css`
- `c:\FootballIntelligence\frontend\src\components\predictions\MensionePickCard.css`

**Changes in tokens.css:**
- Line 54-56: Comments about "MENSIONE PICK" glow → update to "TUTAR X PICK" (comments only)
- Line 193-194: Comments about MENSIONE color → update to "TUTAR X" (comments only)
- **Keep all CSS variable names as-is:** `--glow-green-mensione`, `--color-accent-green` etc. remain unchanged

**Changes in MensionePickCard.css:**
- Line 449: Comment `/* MENSIONE PICK Hero Section */` → change to `/* TUTAR X PICK Hero Section */`
- **Keep all CSS class names unchanged:** `.mensione-pick-card`, `.mensione-pick-hero`, `.mensione-pick-hero__badge`, etc.

**Verify:** Run `cd c:\FootballIntelligence\frontend && npm run build` — build succeeds with no CSS errors.

---

### Step 6: Backend - API Documentation and Endpoint Descriptions

**What:** Update user-facing API documentation strings (OpenAPI descriptions) to replace "MENSIONE" with "TUTAR X" where appropriate. **Do NOT change field names, endpoint paths, or internal identifiers.**

**Files:**
- `c:\FootballIntelligence\backend\app\main.py`
- `c:\FootballIntelligence\backend\app\api\v1\endpoints\matches.py`
- `c:\FootballIntelligence\backend\app\api\v1\schemas.py`

**Changes in main.py:**
- Line 34: `title="Football Intelligence API"` → change to `title="TUTAR X API"`
- Line 35: `description="Professional football analytics and prediction platform"` → change to `description="TUTAR X - Maçın geleceğini veriden oku. Professional football analytics and prediction platform."`
- Line 60: `"service": "Football Intelligence API"` → change to `"service": "TUTAR X API"`
- Line 68: `"message": "Football Intelligence API"` → change to `"message": "TUTAR X API"`

**Changes in matches.py:**
- Line 342: OpenAPI description `"Get prediction, MENSIONE PICK, versioned prediction..."` → change to `"Get prediction, TUTAR X PICK, versioned prediction..."`
- Line 357: `"- MENSIONE PICK (recommended market...)"` → change to `"- TUTAR X PICK (recommended market...)"`
- Line 361: `"MENSIONE PICK Structure:"` → change to `"TUTAR X PICK Structure:"`
- Line 362: `"The mensione_pick field contains..."` → keep as is (field name stays `mensione_pick`)
- Line 418: Comment `"# Generate full MENSIONE prediction..."` → change to `"# Generate full TUTAR X prediction..."`

**Changes in schemas.py:**
- Line 99: `description="Most likely scoreline (e.g., '3-1') - distinct from MENSIONE PICK"` → change to `description="Most likely scoreline (e.g., '3-1') - distinct from TUTAR X PICK"`
- Line 103: `description="MENSIONE recommended pick with market, confidence, and reasoning"` → change to `description="TUTAR X recommended pick with market, confidence, and reasoning"`
- **Keep field name as `mensione_pick`** — this is an internal API field name used throughout the codebase

**Verify:** Run `cd c:\FootballIntelligence\backend && python -m pytest tests/ -v` — all tests pass (field names unchanged, so tests unaffected).

---

### Step 7: Backend - Python Module Documentation Comments

**What:** Update docstrings and comments in Python modules that reference "MENSIONE" as user-facing branding. **Do NOT change module names, function names, class names, or variable names.**

**Files:**
- `c:\FootballIntelligence\backend\app\prediction\mensione_pick.py`
- `c:\FootballIntelligence\backend\app\prediction\market_selector.py`
- `c:\FootballIntelligence\backend\app\domain\prediction.py`
- `c:\FootballIntelligence\backend\app\domain\analysis.py`
- `c:\FootballIntelligence\backend\app\prediction\feature_snapshot.py`

**Changes in mensione_pick.py:**
- Line 1: `"""MENSIONE Pick generator."""` → change to `"""TUTAR X Pick generator (internal module name: mensione_pick for backward compatibility)."""`

**Changes in market_selector.py:**
- Line 1: `"""Smart Market Selector for MENSIONE canonical pipeline."""` → change to `"""Smart Market Selector for TUTAR X canonical pipeline."""`
- Line 66: `"""Smart market selector for the MENSIONE canonical pipeline."""` → change to `"""Smart market selector for the TUTAR X canonical pipeline."""`

**Changes in prediction.py:**
- Line 317: `# Supporting structures for MENSIONE Prediction Engine Core` → change to `# Supporting structures for TUTAR X Prediction Engine Core`

**Changes in analysis.py:**
- Line 123: `description="Most likely scoreline (e.g., '3-1') - distinct from MENSIONE PICK"` → change to `description="Most likely scoreline (e.g., '3-1') - distinct from TUTAR X PICK"`
- Line 134: `# === MENSIONE PICK ===` → change to `# === TUTAR X PICK ===`
- Line 135: `mensione_pick: Optional[Dict[str, Any]] = Field(None, description="MENSIONE recommended pick...")` → change description to `"TUTAR X recommended pick (field name: mensione_pick for backward compatibility)"`
- Line 215: `provider_to_mensione_ms: Optional[float]` → **keep as-is** (internal field name)
- Line 216: `description="Latency from provider event to MENSIONE receipt (milliseconds)"` → change to `description="Latency from provider event to TUTAR X receipt (milliseconds)"`

**Changes in feature_snapshot.py:**
- Line 4: `MENSIONE Intelligence Pipeline` → change to `TUTAR X Intelligence Pipeline`

**Verify:** Run `cd c:\FootballIntelligence\backend && python -m pytest tests/ -v` — all tests pass.

---

### Step 8: Backend - Database Model Comments

**What:** Update comments in database models that reference MENSIONE for user-facing context. **Do NOT change table names, column names, or field names.**

**Files:**
- `c:\FootballIntelligence\backend\app\database\models.py`
- `c:\FootballIntelligence\backend\app\prediction\prediction_version.py`

**Changes in models.py:**
- Line 428: `# Frozen MENSIONE Pick (immutable after creation)` → change to `# Frozen TUTAR X Pick (immutable after creation, field names kept for backward compatibility)`

**Changes in prediction_version.py:**
- Line 68: `"mensione_pick": {...},` → keep as-is (this is showing JSON structure with actual field name)
- Line 92: `# Frozen MENSIONE Pick (stored at prediction time for track record)` → change to `# Frozen TUTAR X Pick (stored at prediction time for track record)`
- Line 197: `mensione_pick: Optional[Any] = None` → keep parameter name as-is
- Line 197: Comment about `mensione_pick` parameter → add clarification: `mensione_pick: Optional TUTAR X pick data (parameter name kept for backward compatibility)`
- Line 229: Comment `# Populate frozen pick fields from mensione_pick if provided` → change to `# Populate frozen pick fields from tutar_x_pick (mensione_pick parameter) if provided`

**Verify:** Run `cd c:\FootballIntelligence\backend && python -m pytest tests/ -v` — all tests pass (no schema changes).

---

### Step 9: Backend - Provider and Latency Tracking Comments

**What:** Update comments in provider modules and latency tracking that reference "MENSIONE" for clarity.

**Files:**
- `c:\FootballIntelligence\backend\app\providers\sofascore.py`
- `c:\FootballIntelligence\backend\app\latency\tracker.py`
- `c:\FootballIntelligence\backend\app\latency\models.py`

**Changes in sofascore.py:**
- Line 78: `MENSIONE_TO_SOFASCORE_IDS: Dict[str, str] = {}` → **keep as-is** (internal variable name)
- Line 109: `def _resolve_sofascore_id(self, mensione_id: str)` → **keep as-is** (internal parameter name)
- Line 110: Docstring `"""Resolve MENSIONE internal ID to SofaScore ID."""` → change to `"""Resolve TUTAR X internal ID to SofaScore ID."""`
- Line 113: `mensione_id: MENSIONE internal match/team ID` → change to `mensione_id: TUTAR X internal match/team ID (parameter name kept for compatibility)`
- Line 118: `return self.MENSIONE_TO_SOFASCORE_IDS.get(mensione_id)` → keep as-is (variable name)

**Changes in tracker.py:**
- Line 92: `provider_to_mensione_ms = None` → keep variable name as-is
- Line 94: Comment about `provider_to_mensione_ms` → change to `# Calculate provider_to_tutar_x latency (variable name kept as provider_to_mensione_ms for compatibility)`
- Line 130: Comment `# If future timestamp detected, set provider_to_mensione_ms to None` → keep as-is (variable name)
- Line 139: `provider_to_mensione_ms=provider_to_mensione_ms,` → keep as-is

**Changes in latency/models.py:**
- Line 42: `provider_to_mensione_ms: Optional[float]` → keep field name as-is
- Line 44: `description="Milliseconds from provider event to MENSIONE receipt"` → change to `description="Milliseconds from provider event to TUTAR X receipt"`
- Line 100: JSON example showing `"provider_to_mensione_ms": 1333.0` → keep as-is (shows actual field name)

**Verify:** Run `cd c:\FootballIntelligence\backend && python -m pytest tests/ -v` — all tests pass.

---

### Step 10: Documentation - README and User-Facing Docs

**What:** Update user-facing documentation (README files, user guides) to replace "MENSIONE" and "Football Intelligence" with TUTAR X branding. **Do NOT change PROJECT_SPEC.md or AGENTS.md** (these are internal development docs).

**Files:**
- `c:\FootballIntelligence\README.md`
- `c:\FootballIntelligence\backend\README.md` (if exists)
- `c:\FootballIntelligence\frontend\README.md` (if exists)

**Changes in root README.md:**
- Line 1: `# Football Intelligence Platform` → change to `# TUTAR X - Football Intelligence Platform`
- Line 3: `Professional football analytics...` → prepend with `TUTAR X — `
- Throughout: Replace instances of "Football Intelligence" when referring to the product name with "TUTAR X"
- Preserve "Football Intelligence" when it describes the general concept (e.g., "football intelligence system")
- Line 6: `Football Intelligence is a comprehensive...` → change to `TUTAR X is a comprehensive...`

**Changes in backend/README.md (if exists):**
- Update title and references to replace product name with TUTAR X

**Changes in frontend/README.md (if exists):**
- Update title and references to replace product name with TUTAR X

**Verify:** Read updated files and confirm branding is consistent. No build verification needed for markdown files.

---

### Step 11: Logo and Favicon Placeholders

**What:** Document the logo placeholder strategy and prepare comments for when user provides actual logo files.

**Action:** Create a placeholder note file for the user.

**Files:**
- `c:\FootballIntelligence\LOGO_PLACEHOLDER_NOTES.md` (new file)

**Content:**
```markdown
# TUTAR X Logo Integration Notes

## Status
Awaiting official TUTAR X logo files from user.

## Required Files
- `/public/tutar-x-logo.png` or `/public/tutar-x-logo.svg` - Main logo for sidebar/header
- `/public/tutar-x-favicon.svg` or `/public/tutar-x-favicon.png` - Favicon for browser tab
- Optional: `/public/tutar-x-icon-192.png`, `/public/tutar-x-icon-512.png` for PWA (if implementing PWA later)

## Current Placeholder References
- **Frontend HTML:** `frontend/index.html` line 5 references `/tutar-x-favicon.svg`
- **Sidebar Component:** `frontend/src/components/layout/Sidebar.tsx` line 96 references `/tutar-x-logo.png`

## Integration Steps (when logo provided)
1. User provides logo files
2. Place files in `frontend/public/` directory with names:
   - `tutar-x-logo.png` (or `.svg`)
   - `tutar-x-favicon.svg` (or `.png`)
3. No code changes needed - references already point to these filenames
4. Rebuild frontend: `cd frontend && npm run build`
5. Verify logo displays correctly in sidebar and favicon appears in browser tab

## Logo Guidelines
- Logo should work on dark backgrounds (sidebar is dark navy/black)
- Favicon should be recognizable at 16x16px and 32x32px
- Recommended formats: SVG for logo (scalable), PNG for favicon
- Logo colors: white/gold/neon-green elements will stand out on dark background
```

**Verify:** File created successfully. User will see clear instructions when providing logo.

---

### Step 12: Scripts and Utility Files

**What:** Update user-facing text in scripts that reference MENSIONE.

**Files:**
- `c:\FootballIntelligence\scripts\generate_design.py`

**Changes:**
- Line 1: `"""Generate the complete MENSIONE Prediction Engine design document."""` → change to `"""Generate the complete TUTAR X Prediction Engine design document."""`
- Line 24: `## 11. MENSIONE PICK GENERATION` → change to `## 11. TUTAR X PICK GENERATION`

**Verify:** Run `cd c:\FootballIntelligence\backend && python -m pytest tests/ -v` — all tests pass (script is documentation generator, not critical path).

---

### Step 13: Final Verification - Full Build and Test

**What:** Run complete build and test suite to ensure no regressions from branding changes.

**Commands:**
```powershell
# Backend tests
cd c:\FootballIntelligence\backend
python -m pytest tests/ -v

# Frontend build
cd c:\FootballIntelligence\frontend
npm run build

# Frontend type check
npm run type-check

# Frontend lint
npm run lint
```

**Expected Results:**
- All backend tests pass
- Frontend builds successfully with no errors
- TypeScript type checking passes
- ESLint passes with no new warnings

**Verify:** All commands succeed. Review build output for any remaining "MENSIONE" references in compiled output (should only be in internal field names/class names, not user-facing strings).

---

### Step 14: Visual Inspection Checklist

**What:** Manual visual inspection of the running application to confirm all user-facing branding has been updated.

**Checklist:**
- [ ] Browser tab shows "TUTAR X — Maçın geleceğini veriden oku." title
- [ ] Browser tab shows TUTAR X favicon (placeholder, will show user-provided favicon when available)
- [ ] Sidebar shows TUTAR X logo placeholder (will show actual logo when user provides file)
- [ ] Sidebar tagline shows "Maçın geleceğini veriden oku."
- [ ] Prediction cards show "TUTAR X PICK" badge (not "MENSIONE PICK")
- [ ] API documentation at `/docs` shows "TUTAR X API" title
- [ ] Health check endpoint returns `"service": "TUTAR X API"`
- [ ] No user-visible "MENSIONE" or "Football Intelligence" text remains (except in appropriate historical/general contexts)

**Verify:** Start dev servers and manually inspect each item. Take screenshots if helpful.

---

## What MUST NOT Change

### Internal Technical Identifiers (DO NOT CHANGE)
These are internal code identifiers that would break the application if renamed:

**Backend:**
- Database table names: `prediction_versions`, `matches`, etc. (no MENSIONE names exist here)
- Database column names: `selected_market`, `selection_text`, etc.
- API field names: `mensione_pick` (field name in JSON responses)
- API endpoint paths: `/api/v1/matches`, `/health`, etc.
- Python module names: `mensione_pick.py` (changing would break imports)
- Python function/class names: No need to rename unless they are user-facing strings
- Python variable names: `mensione_id`, `provider_to_mensione_ms`, `MENSIONE_TO_SOFASCORE_IDS`

**Frontend:**
- Component file names: `MensionePickCard.tsx`, `MensionePickCard.css` (internal identifiers)
- CSS class names: `.mensione-pick-card`, `.mensione-pick-hero`, `.mensione-picks-grid` (internal)
- CSS variable names: `--glow-green-mensione`, `--color-mensione-green` (internal)
- TypeScript interface names: `MensionePickCardProps` (internal)
- Hook names: No MENSIONE hook names exist currently

### Prediction and Data Logic (DO NOT TOUCH)
- All prediction formulas, calculations, model weights
- All feature engineering logic
- All statistical calculations
- All confidence/probability calculations
- All market derivation logic
- All provider integration logic
- All database query logic

### API Contracts (PRESERVE)
- Field names in API responses (e.g., `mensione_pick` stays as field name)
- Endpoint paths (e.g., `/api/v1/matches/{match_id}/prediction`)
- Request/response schemas (Pydantic models keep existing field names)

---

## Summary

**Changes Made:**
1. Browser title and metadata → TUTAR X branding
2. Sidebar logo and tagline → TUTAR X branding
3. Prediction card display text → "TUTAR X PICK"
4. API documentation descriptions → TUTAR X references
5. Python docstrings and comments → TUTAR X references (where user-facing)
6. CSS comments → TUTAR X references
7. README documentation → TUTAR X branding
8. Logo placeholders prepared for user-provided files

**Preserved:**
- All internal technical identifiers (field names, variable names, class names, file names)
- All prediction logic, calculations, and data processing
- All database schemas and API contracts
- All existing functionality and behavior

**Logo Integration:**
- Awaiting user-provided logo files
- Placeholders in place: `/tutar-x-logo.png` and `/tutar-x-favicon.svg`
- Instructions documented in `LOGO_PLACEHOLDER_NOTES.md`

**Result:**
User-facing brand is now TUTAR X throughout the application, while internal architecture and all prediction logic remain completely unchanged and functional.

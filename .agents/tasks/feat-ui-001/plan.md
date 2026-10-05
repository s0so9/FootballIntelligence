# Implementation Plan: FEAT-UI-001 — MENSIONE Green Glow Dashboard & Match Intelligence UI

## Overview

Transform the Football Intelligence frontend from purple/galaxy aesthetic to MENSIONE green glow identity. Build production-quality dashboard with live matches panel, AI confidence indicators with green glow, MENSIONE pick cards, match intelligence page with 3-tab analysis, and combine drawer.

**Task decomposition:** This work naturally decomposes into 4 independent feature groups based on dependency structure and functional separation.

## Context Summary

**Existing architecture (DO NOT break):**
- React 18 + TypeScript + Vite frontend at `c:\FootballIntelligence\frontend`
- Routes: `/`, `/matches`, `/matches/:id`, `/predictions`, `/easy-matches`, `/analytics`, `/settings`
- AppLayout wrapper with Sidebar + Header
- API client in `src/api/` with types matching backend schemas
- Backend runs on localhost:8000, proxied via Vite at `/api`
- All UI text in Turkish (tr-TR locale)
- Backend provides `mensione_pick`, `prediction_version_id`, `predicted_score` fields in `MatchPredictionResponse`

**Backend contract (from schemas.py):**
```typescript
interface MatchPredictionResponse {
  match_id: string;
  home_win_probability: number;
  draw_probability: number;
  away_win_probability: number;
  home_xg: number;
  away_xg: number;
  btts_probability: number;
  predicted_score?: string;  // Most likely scoreline (distinct from MENSIONE PICK)
  mensione_pick?: {          // Recommended market with confidence and reasoning
    market_type: string;
    outcome_label: string;
    confidence: number;
    fair_odds: number;
    reasoning: string[];
  };
  prediction_version_id?: string;
  market_analysis?: [...];   // Deprecated in favor of mensione_pick
  easy_match?: {...};
  is_development_data: boolean;
}
```

**Current state:**
- `src/styles/global.css` has purple theme (`--color-accent-purple: #8b5cf6`, galaxy aesthetic)
- Components exist: `ProbabilityDisplay`, `ConfidenceIndicator`, `ValueIndicator` (need green theme update)
- Pages exist: `Dashboard`, `Matches`, `MatchDetail`, `Predictions` (need transformation)
- No live matches panel, no AI confidence green glow component, no combine drawer yet

**Design requirements:**
- MENSIONE green primary: ~#00ff88
- Very dark background: #0a0a0f
- Dark elevated surfaces: #13131a
- 4-level green glow hierarchy: MENSIONE PICK (strongest) → live → hover → minimal
- Inter font from Google Fonts (or closest available)
- NO purple, NO galaxy, NO casino aesthetics, NO excessive neon
- Premium football intelligence feeling
- Restrained, controlled glow effects

**Key architectural constraints:**
- DO NOT modify backend (Python+FastAPI) under any circumstances
- Work in small verifiable steps (AGENTS.md rule #4)
- Never invent statistics or fake data (rule #10)
- AI confidence ≠ odds, NEVER combine them mathematically (rule #13)
- Missing data → explicit unavailable state, not zeros or fake values (rule #14)
- Backend API is source of truth for all numerical values (rule #11)

---

## Feature Breakdown

This plan decomposes into **4 FEAT artifacts** executed sequentially by dedicated coder steps:

### FEAT-001: MENSIONE Design System & Visual Identity
**Type:** Foundation  
**Dependencies:** None (executes first)  
**What:** Replace purple/galaxy with MENSIONE green glow. Create design tokens (colors, typography, spacing, glow levels). Update global.css, create tokens.css, load Inter font, establish green glow hierarchy.  
**Why first:** All subsequent features depend on new design tokens and visual identity.

### FEAT-002: Core MENSIONE Components
**Type:** Component library  
**Dependencies:** FEAT-001 (needs design tokens)  
**What:** Build AIConfidence (green glow money-bags 1-6 scale), MensionePickCard, LiveMatchCard, MarketRow. Update existing ProbabilityDisplay/ConfidenceIndicator for green theme.  
**Why second:** Dashboard and Match Intelligence pages require these components.

### FEAT-003: MENSIONE Dashboard Page
**Type:** Page/feature  
**Dependencies:** FEAT-002 (needs components)  
**What:** Transform Dashboard.tsx to MENSIONE dashboard with left LiveMatchesPanel (desktop), main MENSIONE picks grid, responsive mobile layout. Create useFavorites and useCombine hooks with localStorage persistence. Update Header (🔔/👤 icons) and Sidebar (MENSIONE branding).  
**Why third:** Uses components from FEAT-002, establishes state hooks for FEAT-004.

### FEAT-004: Match Intelligence Page & Supporting Components
**Type:** Page/feature complex  
**Dependencies:** FEAT-002 (components), FEAT-003 (hooks/state)  
**What:** Transform MatchDetail to Match Intelligence with 3 tabs (Genel/İlk Yarı/Maç). Create GeneralAnalysis, FirstHalfAnalysis, FullMatchAnalysis, StatisticsComparison, FormDisplay, HeadToHead, CombineDrawer, PerformanceOverview foundation. Wire mensione_pick data throughout.  
**Why last:** Most complex, requires all prior work.

---

## Detailed Steps (Fallback if FEAT restructuring unavailable)

If the workflow does not support FEAT decomposition, execute these steps sequentially:

### Phase 1: Design System Foundation

- [ ] **1. Create MENSIONE design tokens**
      Read `frontend/src/styles/global.css` completely. Replace all purple color variables with MENSIONE green (~#00ff88). Change background to very dark (#0a0a0f), surfaces to dark elevated (#13131a). Add 4-level green glow hierarchy variables: `--glow-green-mensione` (strongest), `--glow-green-live`, `--glow-green-hover`, `--glow-green-minimal`. Remove galaxy/purple references.
      Files: `frontend/src/styles/global.css`
      Verify: Search global.css for "purple" or "#8b5cf6" — zero matches. Start dev server, inspect page background in DevTools — should be #0a0a0f.

- [ ] **2. Update typography system**
      Add Google Fonts import for Inter at top of global.css: `@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');`. Update `--font-family` to `'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif`. Strengthen title sizes: `--text-4xl: 2.5rem`, `--text-3xl: 2rem`.
      Files: `frontend/src/styles/global.css`
      Verify: Inspect computed font-family in DevTools — should include Inter. Check h1 element — font should be Inter, size larger.

- [ ] **3. Create tokens documentation file**
      Create `frontend/src/styles/tokens.css` with documented token structure: color palette (MENSIONE green levels, dark surfaces, status colors), typography scale, spacing scale (4/8/12/16/24/32/48/64px), glow hierarchy documentation. Import tokens.css from global.css.
      Files: `frontend/src/styles/tokens.css` (new), `frontend/src/styles/global.css` (import)
      Verify: tokens.css file exists, imported in global.css, documents all design tokens with comments.

- [ ] **4. Update focus and scrollbar styles**
      Change focus outline from purple to MENSIONE green. Update scrollbar thumb/track to match dark theme.
      Files: `frontend/src/styles/global.css`
      Verify: Tab to any button, outline should be green not purple.

- [ ] **5. Update layout component styles**
      Update `AppLayout.css`, `Sidebar.css`, `Header.css` to reference new green tokens instead of purple variables.
      Files: `frontend/src/components/layout/AppLayout.css`, `frontend/src/components/layout/Sidebar.css`, `frontend/src/components/layout/Header.css`
      Verify: `npm run type-check && npm run lint` pass. Start dev server, navigate to /, sidebar and header render with no purple, dark surfaces visible.

### Phase 2: Core Components

- [ ] **6. Create AIConfidence component**
      Create `frontend/src/components/predictions/AIConfidence.tsx`. Accept `confidence` prop (0-1 or 0-100). Map to 1-6 scale: <=0.16=1, <=0.33=2, <=0.5=3, <=0.67=4, <=0.83=5, >0.83=6. Turkish labels array. Render custom CSS/SVG money-bag icons (NOT emoji) with MENSIONE green fill and glow scaling by level (1/6 minimal, 6/6 strongest). Show level/6, label, percentage. Create matching `.css` file with glow styles using token variables.
      Files: `frontend/src/components/predictions/AIConfidence.tsx` (new), `frontend/src/components/predictions/AIConfidence.css` (new)
      Verify: Create test page importing AIConfidence with confidence=0.82. Should show 5 green glowing + 1 gray inactive money-bags, "5/6 · Yüksek", percentage. Glow visible but controlled.

- [ ] **7. Create AIConfidence tests**
      Create `frontend/src/components/predictions/AIConfidence.test.tsx`. Test confidence=0.82 → 5/6 'Yüksek', confidence=0.15 → 1/6 'Çok düşük', confidence=1.0 → 6/6 'Çok yüksek'. Test NO hardcoded values.
      Files: `frontend/src/components/predictions/AIConfidence.test.tsx` (new)
      Verify: `npm run test` — AIConfidence tests pass.

- [ ] **8. Create MensionePickCard component**
      Create `frontend/src/components/predictions/MensionePickCard.tsx`. Props: homeTeam, awayTeam, marketName, outcome, confidence (pass to AIConfidence), realOdds, isFavorite, onToggleFavorite, onToggleCombine, inCombine. Display MENSIONE PICK badge with strongest green glow. Show star ⭐/☆ for favorite (NOT green bag). Show combine checkbox. AI confidence and odds separate, never combined. Create matching `.css` with `.mensione-pick-badge` having strong glow.
      Files: `frontend/src/components/predictions/MensionePickCard.tsx` (new), `frontend/src/components/predictions/MensionePickCard.css` (new)
      Verify: Import in test page, render with sample props. MENSIONE PICK badge has strong green glow. Star toggles. Checkbox toggles. Responsive layout.

- [ ] **9. Create LiveMatchCard component**
      Create `frontend/src/components/dashboard/LiveMatchCard.tsx`. Props: homeTeam, awayTeam, score {home, away}, minute, status, liveStats?. Show 🔴 LIVE indicator with subtle red pulse (@keyframes, respects prefers-reduced-motion). Show score, minute, stats if available. Empty state: 'Şu anda canlı maç yok'. Loading state: skeleton. Unavailable stats: 'Canlı istatistikler mevcut değil'.
      Files: `frontend/src/components/dashboard/LiveMatchCard.tsx` (new), `frontend/src/components/dashboard/LiveMatchCard.css` (new)
      Verify: Render empty state — shows empty message. Render with live data — pulse visible (if motion not reduced). Set prefers-reduced-motion in DevTools — pulse stops.

- [ ] **10. Create MarketRow component**
      Create `frontend/src/components/predictions/MarketRow.tsx`. Props: marketName, confidence, realOdds, onToggleCombine, inCombine. Compact single-line row layout. Hover state, focus-within for accessibility.
      Files: `frontend/src/components/predictions/MarketRow.tsx` (new), `frontend/src/components/predictions/MarketRow.css` (new)
      Verify: Render in test page, verify compact layout, hover changes background, keyboard focus visible.

- [ ] **11. Update existing common components for green theme**
      Update `frontend/src/components/common/ConfidenceIndicator.tsx` and `ProbabilityDisplay.tsx`: replace purple references with MENSIONE green, use new CSS variables from tokens.css. Keep existing behavior, change only visual treatment.
      Files: `frontend/src/components/common/ConfidenceIndicator.tsx`, `frontend/src/components/common/ProbabilityDisplay.tsx`
      Verify: `npm run type-check && npm run lint` pass. Render in test page, no purple visible, green accents present.

### Phase 3: Dashboard Page

- [ ] **12. Create state management hooks**
      Create `frontend/src/hooks/useFavorites.ts`: manage favorite match IDs in localStorage ('mensione_favorites' key). Returns {favorites: Set<string>, toggleFavorite, isFavorite}. Create `frontend/src/hooks/useCombine.ts`: manage combine items in localStorage ('mensione_combine' key). CombineItem type: {matchId, marketName, outcome, odds, confidence}. Returns {combineItems, addToCombine, removeFromCombine, clearCombine}.
      Files: `frontend/src/hooks/useFavorites.ts` (new), `frontend/src/hooks/useCombine.ts` (new)
      Verify: Create test page using hooks. Toggle favorite, check localStorage. Add combine item, check localStorage. Refresh page, state restored.

- [ ] **13. Transform Dashboard page**
      Read current `frontend/src/pages/Dashboard.tsx`. Rewrite structure: desktop layout with left panel (250px) for LiveMatchesPanel, main area for MENSIONE picks grid. Mobile layout: picks first, live secondary (horizontal scroll or drawer). Fetch matches with `getUpcomingMatches(7)`, for each fetch prediction with `getMatchPrediction(matchId)`. Filter where `prediction.mensione_pick` exists. Map mensione_pick to MensionePickCard props. Wire useFavorites and useCombine hooks. Render loading skeletons, empty state: 'Şu anda MENSIONE seçimi yok'.
      Files: `frontend/src/pages/Dashboard.tsx`, `frontend/src/pages/Dashboard.css`
      Verify: Start dev server, navigate to /. Desktop shows left live panel + picks grid. Mobile shows picks first. Loading shows skeleton. If no picks, empty state visible. API calls in Network tab. No console errors.

- [ ] **14. Create LiveMatchesPanel component**
      Create `frontend/src/components/dashboard/LiveMatchesPanel.tsx`. Wrapper component rendering multiple LiveMatchCard components. Accept array of live match data. Handle empty (no live matches) and loading states.
      Files: `frontend/src/components/dashboard/LiveMatchesPanel.tsx` (new), `frontend/src/components/dashboard/LiveMatchesPanel.css` (new)
      Verify: Import in Dashboard, render with mock data or empty. Empty state shows 'Şu anda canlı maç yok'. Compact layout fits left panel.

- [ ] **15. Update Header component**
      Update `frontend/src/components/layout/Header.tsx`. Add 🔔 notification icon button (placeholder, non-functional) and 👤 profile icon button (placeholder, non-functional) to right side. Update brand to MENSIONE.
      Files: `frontend/src/components/layout/Header.tsx`, `frontend/src/components/layout/Header.css`
      Verify: Header shows MENSIONE brand, 🔔 and 👤 icons visible on right side. Icons clickable (no action yet). Mobile menu button still on left.

- [ ] **16. Update Sidebar component**
      Update `frontend/src/components/layout/Sidebar.tsx`. Change logo text to MENSIONE, tagline to 'Football Intelligence'. Update Dashboard nav icon if needed.
      Files: `frontend/src/components/layout/Sidebar.tsx`, `frontend/src/components/layout/Sidebar.css`
      Verify: Sidebar logo shows MENSIONE, tagline shows Football Intelligence. Navigation works.

- [ ] **17. Test Dashboard responsive behavior**
      Manually test dashboard at desktop (>1024px), tablet (768-1024px), mobile (<768px) widths. Verify layout adapts correctly, live panel behavior, picks grid columns.
      Verify: Desktop has left panel + grid. Tablet compact/toggle panel. Mobile picks first. Tab through with keyboard, all interactive elements accessible.

### Phase 4: Match Intelligence Page

- [ ] **18. Create match analysis components**
      Create `frontend/src/components/match/GeneralAnalysis.tsx`: display primary MENSIONE PICK (MensionePickCard if mensione_pick exists), predicted_score if available, 1X2 probabilities, xG, BTTS, key indicators from reasoning. Data from prediction, never fabricate. Create matching `.css`.
      Files: `frontend/src/components/match/GeneralAnalysis.tsx` (new), `frontend/src/components/match/GeneralAnalysis.css` (new)
      Verify: Render in test page with mock prediction data. MENSIONE pick shown prominently if exists, probabilities and xG visible.

- [ ] **19. Create FirstHalfAnalysis component**
      Create `frontend/src/components/match/FirstHalfAnalysis.tsx`: display first-half markets if available (İlk Yarı 0.5+ Gol, 1.5+ Gol, Toplam Şut, İsabetli Şut, Korner). Use MarketRow. Lines come from data, never hardcoded. Empty state: 'İlk yarı analizi mevcut değil'.
      Files: `frontend/src/components/match/FirstHalfAnalysis.tsx` (new), `frontend/src/components/match/FirstHalfAnalysis.css` (new)
      Verify: Render with mock data containing first-half markets — markets display. Render with no data — empty state shows.

- [ ] **20. Create FullMatchAnalysis component**
      Create `frontend/src/components/match/FullMatchAnalysis.tsx`: display full match markets (Toplam Şut, İsabetli Şut, Korner, Kartlar, Goller, BTTS). Only render markets present in data. Use MarketRow. Empty state if no markets.
      Files: `frontend/src/components/match/FullMatchAnalysis.tsx` (new), `frontend/src/components/match/FullMatchAnalysis.css` (new)
      Verify: Render with mock markets — displays. Empty data — empty state.

- [ ] **21. Create StatisticsComparison component**
      Create `frontend/src/components/match/StatisticsComparison.tsx`: compact table for Şut, İsabetli Şut, Korner, Topa Sahip %, xG. Show real values from prediction (home_xg, away_xg), '--' when unavailable. NEVER fake stats.
      Files: `frontend/src/components/match/StatisticsComparison.tsx` (new), `frontend/src/components/match/StatisticsComparison.css` (new)
      Verify: Render with xG values — table shows xG. Render without stats — shows '--'.

- [ ] **22. Create FormDisplay component**
      Create `frontend/src/components/match/FormDisplay.tsx`: show recent form as W/D/L indicators (last 5). Optional goals/shots/corners if data available. Empty state if no form data.
      Files: `frontend/src/components/match/FormDisplay.tsx` (new), `frontend/src/components/match/FormDisplay.css` (new)
      Verify: Render with form data — W/D/L indicators show (green/gray/red). Empty data — empty state.

- [ ] **23. Create HeadToHead component**
      Create `frontend/src/components/match/HeadToHead.tsx`: show recent h2h meetings, results, compact. Secondary info. Empty state if no h2h.
      Files: `frontend/src/components/match/HeadToHead.tsx` (new), `frontend/src/components/match/HeadToHead.css` (new)
      Verify: Render with h2h data — meetings display. Empty — empty state.

- [ ] **24. Create CombineDrawer component**
      Create `frontend/src/components/combine/CombineDrawer.tsx`: display combine items from useCombine hook. Calculate totalOdds = product of all realOdds. Calculate potentialReturn = totalOdds × stake (stake input, default 10). AI confidence NEVER in calculation. If no odds, show 'Oran Yok', never fabricate. Bottom drawer mobile (<768px), right panel desktop (>768px). Toggle button to open/close.
      Files: `frontend/src/components/combine/CombineDrawer.tsx` (new), `frontend/src/components/combine/CombineDrawer.css` (new)
      Verify: Add items to combine, drawer shows. Total odds = product. Change stake, potential return updates. Clear button works. Mobile bottom, desktop right side.

- [ ] **25. Create PerformanceOverview foundation**
      Create `frontend/src/components/track-record/PerformanceOverview.tsx`: foundation for track record. Structure: Başarılı/Başarısız/Bekleyen/Toplam counters. Filters: Bugün/7 Gün/30 Gün/Sezon/Tümü. Show ONLY empty/loading states, NO fake data. Future FEAT-006 integration.
      Files: `frontend/src/components/track-record/PerformanceOverview.tsx` (new), `frontend/src/components/track-record/PerformanceOverview.css` (new)
      Verify: Render — shows structure with empty states. No numbers displayed.

- [ ] **26. Transform MatchDetail to Match Intelligence page**
      Read current `frontend/src/pages/MatchDetail.tsx`. Rewrite: add 3-tab navigation (Genel/İlk Yarı/Maç). Genel tab: GeneralAnalysis + StatisticsComparison + FormDisplay + HeadToHead. İlk Yarı tab: FirstHalfAnalysis. Maç tab: FullMatchAnalysis. Keep match header (teams, competition, date, status) above tabs. Wire favorites and combine hooks. Fetch with getMatch and getMatchPrediction.
      Files: `frontend/src/pages/MatchDetail.tsx`, `frontend/src/pages/MatchDetail.css`
      Verify: Navigate to /matches/:id. 3 tabs visible. Click tabs — content switches. Genel shows MENSIONE pick. İlk Yarı and Maç show markets or empty states. Tabs keyboard accessible. No console errors.

- [ ] **27. Test combine drawer integration**
      From Match Intelligence page, add markets to combine. Verify drawer opens, items appear, total odds calculated correctly. Change stake, verify potential return. Remove items, verify recalculation. Clear combine.
      Verify: Combine math correct (product of odds). AI confidence not in calculation. If item has no odds, 'Oran Yok' displayed.

- [ ] **28. Final cross-feature verification**
      Run full test suite: `npm run type-check`, `npm run lint`, `npm run test`, `npm run build`. Start dev server, navigate through: Dashboard → Matches → Match detail. Toggle favorites (persist across refresh). Add to combine (persist). Test responsive (desktop/tablet/mobile). Test accessibility (keyboard nav through all features). Check Network tab (API calls correct). Check console (no errors).
      Verify: All TypeScript, ESLint, tests pass. Build succeeds. All features work. Favorites and combine persist. Responsive works. Keyboard accessible. No console errors.

---

## Verification Commands

After each step:
- **Type check:** `npm run type-check` (must pass, no TypeScript errors)
- **Lint:** `npm run lint` (must pass, no ESLint errors)
- **Tests:** `npm run test` (must pass, new tests included)
- **Dev server:** `npm run dev` → http://localhost:5173 (manual verification)
- **Build:** `npm run build` (production build must succeed before completion)

---

## Critical Reminders

1. **DO NOT modify backend** (c:\FootballIntelligence\backend\) under any circumstances
2. **Never fabricate data**: If backend doesn't provide a field, show unavailable state
3. **AI confidence ≠ odds**: Never combine confidence with odds mathematically
4. **Green glow hierarchy**: MENSIONE PICK strongest, live medium, hover subtle, cards minimal
5. **Accessibility**: All interactive elements keyboard accessible, focus visible, reduced-motion support
6. **Turkish UI**: All user-facing text in Turkish
7. **Real data only**: Use backend mensione_pick, predicted_score, xG, probabilities — no fake values
8. **Verify immediately**: After each step, run checks before moving to next step

---

## Success Criteria

- [ ] No purple visible anywhere in UI
- [ ] MENSIONE green glow identity established throughout
- [ ] Inter font loaded and active
- [ ] Dashboard shows left live panel (desktop) and MENSIONE picks grid
- [ ] AIConfidence shows 1-6 green glowing money-bags
- [ ] MensionePickCard displays pick with strongest green glow
- [ ] Match Intelligence page has 3-tab structure (Genel/İlk Yarı/Maç)
- [ ] Combine drawer calculates odds correctly (product, never includes confidence)
- [ ] Favorites and combine persist across page refresh (localStorage)
- [ ] All loading/empty/unavailable states implemented (no fake data)
- [ ] Responsive layout works (desktop/tablet/mobile)
- [ ] All features keyboard accessible
- [ ] TypeScript, ESLint, tests, build all pass
- [ ] No console errors in browser
- [ ] Backend API integration works correctly
- [ ] docs/PROGRESS.md updated with completion summary

---

## Next Steps After Completion

Update docs/PROGRESS.md with:
- FEAT-UI-001 completed
- MENSIONE green glow dashboard operational
- Components: AIConfidence, MensionePickCard, LiveMatchCard, MarketRow, CombineDrawer, match analysis components
- Pages: Dashboard (transformed), Match Intelligence (transformed)
- State: useFavorites, useCombine hooks with localStorage persistence
- Verification: all tests passing, build successful, UI verified
- Next: FEAT-006 (track record integration) or live intelligence enhancement

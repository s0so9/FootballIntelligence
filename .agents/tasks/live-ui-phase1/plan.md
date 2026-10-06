# MENSIONE LIVE UI PHASE 1 — Implementation Plan

**Task**: Build the first complete MENSIONE Live Football Intelligence Experience
**Workspace**: c:\FootballIntelligence  
**Frontend**: c:\FootballIntelligence\frontend (React + TypeScript + Vite)  
**Backend**: c:\FootballIntelligence\backend (Python + FastAPI)

---

## EXPLORATION FINDINGS

### Frontend Architecture (REUSE STRATEGY)
The existing MENSIONE frontend is well-structured with:
- **Pages**: Dashboard, Matches, MatchDetail, Predictions, EasyMatches, Analytics, Settings
- **Components**: match/, predictions/, dashboard/, common/, layout/, track-record/, combine/
- **API Client**: `src/api/client.ts` with request abstraction, `src/api/types.ts` with backend contracts
- **Design System**: Dark navy/black foundation (#050711, #0B1020, #0D1424, #10182B), electric blue/cyan accents (#0ea5e9, #3b82f6, #06b6d4, #22d3ee), purple AI accents (#8b5cf6, #a78bfa, #7c3aed), MENSIONE green identity (#00ff88 — brand only), restrained red for LIVE (#ef4444), Inter typography, subtle blue glow, compact spacing (16-24px)
- **Existing Components to REUSE**: MensionePickCard (premium card with tabs), StatisticsComparison (team stat table), ProbabilityDisplay, ConfidenceIndicator, StatusBadge, AIConfidence, MarketRow, GeneralAnalysis/FirstHalfAnalysis/FullMatchAnalysis (tab panels), FormDisplay, HeadToHead
- **Existing Pages to EXTEND**: MatchDetail.tsx (currently shows pre-match prediction; needs live view detection and live components)
- **User-Facing Language**: Turkish (Canlı, Maçlar, İstatistik Karşılaştırması, etc.)

### Backend Live Data Availability (VERIFIED)
- **GET /api/v1/matches/live EXISTS**: `app/api/v1/endpoints/live_matches.py`
  - Returns `LiveMatchesResponse` with `matches: List[LiveMatchResponse]`, `provider_health`, `data_quality`, `timestamp`, `provider_used`, `total_count`
  - `LiveMatchResponse` schema: `match_id`, `status`, `minute`, `home_score`, `away_score`, `home_team_id`, `away_team_id`, `data_quality_flags: Dict[str, bool]` (has_xg, has_events, has_shots, has_player_positions, has_ball_tracking, has_shot_coordinates, has_live_statistics)
  - Provider infrastructure: RyzellxFootballProvider, FotMobFootballProvider, OpenLigaDBFootballProvider
  - **CRITICAL**: Backend returns empty matches list + provider health on failure; NEVER fabricates data
- **Live Match Ingestion**: `app/ingestion/live_ingestion.py` (LiveIngester with out-of-order event handling)
- **Database Schema**: `MatchStatus` enum includes `LIVE`, `HALF_TIME`, `FINISHED`, `POSTPONED`, `CANCELLED`, `SUSPENDED`
- **Match Model**: `Match` has `status`, `minute`, `added_time`, `home_score`, `away_score`, `home_statistics`, `away_statistics`, `home_statistics_ht`, `away_statistics_ht` (xG, shots, shots_on_target, possession, corners, yellow_cards, red_cards, etc.)

### Backend Live Data GAPS (NOT AVAILABLE)
- **No dedicated live match detail endpoint**: `/api/v1/matches/{matchId}` returns `MatchResponse` (includes live scores if status='live'), but no separate `/api/v1/matches/{matchId}/live` endpoint for rich live intelligence
- **No live prediction endpoint**: No `/api/v1/matches/{matchId}/prediction/live` — prediction endpoint only returns pre-match
- **No live events endpoint**: No `/api/v1/matches/{matchId}/events` for goal/card/sub timeline
- **No shot map endpoint**: No shot coordinates endpoint
- **No momentum endpoint**: No validated momentum model
- **No live market odds**: Market data appears pre-match only

### Design Decisions (APPROVED)
1. **REUSE MatchDetail.tsx as host page**: Detect `match.status === 'live'` and conditionally render LiveMatchView instead of pre-match tabs; preserve ALL existing pre-match functionality
2. **EXTEND existing components where possible**: StatisticsComparison can handle live stats; ProbabilityDisplay/ConfidenceIndicator reusable; MensionePickCard tabs can inspire LiveIntelligenceTabs
3. **CREATE new live-specific components** in `src/components/live/`: LiveMatchHeader, LiveScoreboard, LiveConnectionStatus, LiveStatGrid, LiveShotIntelligence, LiveMomentum, LiveTimeline, LivePickCard, LiveDataQuality
4. **API strategy**: Use existing `getMatch(matchId)` for live match state (score, minute, status); create `useLiveMatch(matchId)` hook with polling (5s interval) ONLY if match.status is live; gracefully handle stale/unavailable data
5. **Live prediction strategy**: Reuse existing prediction architecture; show pre-match prediction + live comparison when both available; show "LIVE MODEL Not available" when unavailable; NEVER invent live model outputs
6. **TypeScript contracts**: Define `LiveMatchState`, `LiveStats`, `LiveEvent`, `LiveShot`, `LivePrediction`, `LivePick` interfaces in `src/types/live.ts` with ALL fields optional
7. **Visual identity**: Preserve MENSIONE exactly: dark navy/black, electric blue/cyan accents, purple for AI, MENSIONE green for brand only, restrained red (#ef4444) for LIVE indicator with subtle pulse animation, Inter typography, subtle blue glow, compact spacing
8. **Unavailable data rendering**: Show `—` or `Unavailable` or dedicated empty state; NEVER show 0 when value is unknown; NEVER fabricate numbers
9. **Mock data isolation**: NO mock data in production; IF development mock mode needed, isolate completely behind explicit flag and label clearly "DEVELOPMENT MOCK DATA"
10. **Responsive**: Desktop two-column (score/header left, intelligence panels right) + full-width timeline/markets; mobile vertical stack (Score → Intelligence → Shot Intelligence → Pick → Timeline → Markets)

---

## IMPLEMENTATION PLAN

### Phase 1: TypeScript Contracts + API Hooks (Foundation)

- [ ] **1.1**: Create `src/types/live.ts` with live data TypeScript interfaces.
  - Define `LiveMatchState` (matchId, status, minute, addedTime, homeScore, awayScore, homeTeam, awayTeam, competition, venue, period, dataQuality)
  - Define `LiveStats` (shots, shotsOnTarget, shotsInsideBox, bigChances, dangerousAttacks, possession, fieldTilt, xG, xGPerShot, bigChanceRate, ppda, highTurnovers, progressivePasses, progressiveCarries, boxEntries, corners, fouls, offsides, yellowCards, redCards) — ALL fields optional
  - Define `LiveEvent` (eventId, matchId, minute, addedTime, type, team, player, description, isImportant)
  - Define `LiveShot` (shotId, matchId, minute, team, player, x, y, outcome, xG, isGoal, isBigChance)
  - Define `LivePrediction` (matchId, timestamp, homeWinProbability, drawProbability, awayWinProbability, homeXG, awayXG, bttsProbability, markets, modelAgreement, confidence)
  - Define `LivePick` (matchId, market, selection, probability, confidence, dataQuality, signal, passDecision, passReason)
  - Define `DataQualityLevel` = 'HIGH' | 'MEDIUM' | 'LOW' | 'UNAVAILABLE'
  - ALL fields optional to handle missing data gracefully
  - Files: `src/types/live.ts`
  - Verify: `npm run type-check` — no TypeScript errors

- [ ] **1.2**: Extend `src/api/client.ts` with live match API functions.
  - Implement `getLiveMatches(): Promise<LiveMatchesResponse>` (already exists in client.ts, verify it works)
  - Implement `getLiveMatchDetail(matchId: string): Promise<LiveMatchState>` — wrapper around `getMatch(matchId)` that transforms `MatchResponse` to `LiveMatchState` when status is live; returns null if not live
  - Future placeholders (return null/empty for now): `getLiveEvents(matchId)`, `getLiveShots(matchId)`, `getLivePrediction(matchId)`, `getLiveMarkets(matchId)`
  - Files: `src/api/client.ts`, `src/types/live.ts`
  - Verify: `npm run type-check` — no TypeScript errors; manual test with backend running

- [ ] **1.3**: Create `src/hooks/useLiveMatch.ts` custom hook with polling.
  - Accept `matchId: string`, `enabled: boolean` (default true)
  - Use `useState` for `liveMatch: LiveMatchState | null`, `loading: boolean`, `error: string | null`, `lastUpdated: Date | null`, `connectionStatus: 'CONNECTED' | 'UPDATING' | 'DELAYED' | 'UNAVAILABLE'`
  - Use `useEffect` to poll `getLiveMatchDetail(matchId)` every 5 seconds ONLY when `enabled === true`
  - Update `connectionStatus` based on successful fetch ('CONNECTED'), fetching ('UPDATING'), timeout > 10s ('DELAYED'), error ('UNAVAILABLE')
  - Clean up interval on unmount
  - Return `{ liveMatch, loading, error, lastUpdated, connectionStatus, refetch }`
  - Files: `src/hooks/useLiveMatch.ts`
  - Verify: `npm run type-check` + `npm test` (if hook tests exist) — no errors

### Phase 2: Live Match Core UI Components

- [ ] **2.1**: CREATE `src/components/live/LiveMatchHeader.tsx` — premium live header.
  - Props: `liveMatch: LiveMatchState`, `compact?: boolean`
  - Render: LIVE badge (red #ef4444 with subtle pulse animation), match minute + status (e.g., "63'" or "HT" or "FT"), home team name + logo (if available), away team name + logo, current score prominent (large electric blue), competition + venue (if available), halftime/fulltime/extra-time/penalties state
  - Visual: Dark navy card (#0D1424), electric blue accents, restrained red LIVE indicator, Inter typography, subtle glow
  - Files: `src/components/live/LiveMatchHeader.tsx`, `src/components/live/LiveMatchHeader.css`
  - Verify: `npm run build` — frontend builds successfully; visual inspection in browser with mock LiveMatchState

- [ ] **2.2**: CREATE `src/components/live/LiveScoreboard.tsx` — compact scoreboard anchor.
  - Props: `liveMatch: LiveMatchState`
  - Render: score (large, prominent), minute + period, status, cards/subs indicators (⚽ [goals], 🟨 [yellow], 🔴 [red], 🔄 [subs]) ONLY when data available
  - Visual: Compact design, electric blue score, dark navy background, Inter tabular numbers
  - Files: `src/components/live/LiveScoreboard.tsx`, `src/components/live/LiveScoreboard.css`
  - Verify: `npm run build` — frontend builds; visual inspection

- [ ] **2.3**: CREATE `src/components/live/LiveConnectionStatus.tsx` — data freshness indicator.
  - Props: `connectionStatus: 'CONNECTED' | 'UPDATING' | 'DELAYED' | 'UNAVAILABLE'`, `lastUpdated: Date | null`
  - Render: `● LIVE DATA CONNECTED` (green), `● UPDATING` (blue pulse), `● DELAYED` (yellow), `● UNAVAILABLE` (red), "Updated Xs ago"
  - Visual: Small badge, top-right of live view, subtle, Inter typography
  - Files: `src/components/live/LiveConnectionStatus.tsx`, `src/components/live/LiveConnectionStatus.css`
  - Verify: `npm run build` — frontend builds; visual inspection

### Phase 3: Live Intelligence Components

- [ ] **3.1**: CREATE `src/components/live/LiveStatGrid.tsx` — live stat intelligence grid.
  - Props: `homeStats: LiveStats | null`, `awayStats: LiveStats | null`, `homeTeam: string`, `awayTeam: string`
  - Render grid sections: **ATTACK** (shots, shots on target, shots inside box, big chances, dangerous attacks if available), **POSSESSION** (possession %, field tilt if available), **CHANCE QUALITY** (xG, xG per shot, big chance rate), **PRESSING** (PPDA, high turnovers), **PROGRESSION** (progressive passes, progressive carries, box entries)
  - Display `—` or `Unavailable` for missing metrics; NEVER show fake numbers
  - Reuse existing StatisticsComparison.tsx pattern (home | stat | away table)
  - Visual: Dark navy cards, electric blue accents, compact rows, Inter typography
  - Files: `src/components/live/LiveStatGrid.tsx`, `src/components/live/LiveStatGrid.css`
  - Verify: `npm run build` — frontend builds; visual inspection with partial/missing stats

- [ ] **3.2**: CREATE `src/components/live/LiveShotIntelligence.tsx` — shot comparison table (MAJOR SIGNAL).
  - Props: `homeStats: LiveStats | null`, `awayStats: LiveStats | null`, `homeTeam: string`, `awayTeam: string`
  - Render prominent **SHOT INTELLIGENCE** section: shots, on target, inside box, xG; calculate shot share, shot differential, SOT share, SOT differential, shot quality differential (xG/shot differential)
  - Handle missing data: show `—` when unavailable; if NO shot data available, show "Shot data unavailable"
  - Visual: Prominent card with strong hierarchy, electric blue highlights, dark navy background, compact table, Inter typography
  - Files: `src/components/live/LiveShotIntelligence.tsx`, `src/components/live/LiveShotIntelligence.css`
  - Verify: `npm run build` — frontend builds; visual inspection

- [ ] **3.3**: CREATE `src/components/live/LiveDataQuality.tsx` — data quality indicator.
  - Props: `dataQuality: { live: DataQualityLevel, shot: DataQualityLevel, xG: DataQualityLevel, lineup: DataQualityLevel }`
  - Render compact badges: `LIVE: HIGH`, `SHOT: MEDIUM`, `xG: LOW`, `LINEUP: UNAVAILABLE`
  - Color-coded: HIGH (green), MEDIUM (yellow), LOW (orange), UNAVAILABLE (red)
  - Visual: Small badges grid, bottom of live view or sidebar, subtle, Inter typography
  - Files: `src/components/live/LiveDataQuality.tsx`, `src/components/live/LiveDataQuality.css`
  - Verify: `npm run build` — frontend builds; visual inspection

### Phase 4: Visual Intelligence Components

- [ ] **4.1**: CREATE `src/components/live/LiveMomentum.tsx` — visual momentum representation.
  - Props: `homeStats: LiveStats | null`, `awayStats: LiveStats | null`, `homeTeam: string`, `awayTeam: string`
  - Render visual momentum bars from raw indicators (recent shots, SOT, possession, dangerous attacks, field tilt, box entries)
  - **CRITICAL**: Do NOT invent a momentum score; show raw indicators or label "MODEL INFERENCE" if model-derived
  - If insufficient data, show "Momentum data unavailable"
  - Visual: Horizontal bars, electric blue/cyan for possession team, dark navy background, compact, Inter typography
  - Files: `src/components/live/LiveMomentum.tsx`, `src/components/live/LiveMomentum.css`
  - Verify: `npm run build` — frontend builds; visual inspection

- [ ] **4.2**: CREATE `src/components/live/LiveShotMap.tsx` — shot location map (ONLY when coordinates exist).
  - Props: `shots: LiveShot[]`, `homeTeam: string`, `awayTeam: string`
  - Render shot map ONLY when `shots.length > 0` and coordinates (x, y) available
  - Show home/away separation, goal/non-goal state, shot quality (xG-based size/color), hover/tap info (player, minute, outcome, xG)
  - If NO shot coordinates: show graceful state "Shot location data unavailable" — do NOT draw fake dots
  - Visual: Pitch background (subtle), shot markers (electric blue for home, purple for away, green for goals), hover tooltips, dark navy card, Inter typography
  - Files: `src/components/live/LiveShotMap.tsx`, `src/components/live/LiveShotMap.css`
  - Verify: `npm run build` — frontend builds; visual inspection with empty/populated states

- [ ] **4.3**: CREATE `src/components/live/LiveTimeline.tsx` — chronological match events.
  - Props: `events: LiveEvent[]`, `homeTeam: string`, `awayTeam: string`
  - Render vertical timeline: goals (⚽), assists, cards (🟨🔴), subs (🔄), VAR, penalties, important shots/SOT
  - Strong hierarchy for important events (goals, red cards); chronological order (latest first or oldest first — choose one)
  - If NO events: show "Event data unavailable"
  - Visual: Vertical timeline, event icons, minute labels, team-colored dots (electric blue home, purple away), dark navy background, Inter typography
  - Files: `src/components/live/LiveTimeline.tsx`, `src/components/live/LiveTimeline.css`
  - Verify: `npm run build` — frontend builds; visual inspection

### Phase 5: Live Prediction + Pick Components

- [ ] **5.1**: CREATE `src/components/live/PreMatchLiveComparison.tsx` — pre-match vs live comparison.
  - Props: `preMatchPrediction: MatchPredictionResponse | null`, `livePrediction: LivePrediction | null`, `homeTeam: string`, `awayTeam: string`
  - Render ONLY when BOTH pre-match AND live prediction exist
  - Show: "PRE-MATCH EXPECTATION" (home win %, expected goals) → "LIVE 63'" (current score) → "LIVE MODEL STATE" (home win % now)
  - If live model unavailable: show "LIVE MODEL Not available"
  - **NEVER invent example values**
  - Visual: Compact comparison card, electric blue accents, arrow (↓) separating states, dark navy background, Inter typography
  - Files: `src/components/live/PreMatchLiveComparison.tsx`, `src/components/live/PreMatchLiveComparison.css`
  - Verify: `npm run build` — frontend builds; visual inspection

- [ ] **5.2**: CREATE `src/components/live/LivePickCard.tsx` — MENSIONE LIVE PICK or PASS.
  - Props: `livePick: LivePick | null`, `homeTeam: string`, `awayTeam: string`
  - Render **MENSIONE LIVE PICK** when `livePick.passDecision === false` and signal strong: market + selection, probability, confidence (AIConfidence component), data quality indicator, signal strength (STRONG/MEDIUM/WEAK), timestamp
  - Render first-class **MENSIONE LIVE PASS** when `livePick.passDecision === true`: "MENSIONE LIVE PASS | No sufficiently reliable live market signal", pass reason
  - Support pick invalidation/weakening: show updated timestamp, reduced confidence if signal weakens
  - **NEVER force a pick when signal weak or data insufficient**
  - Visual: Premium card matching MensionePickCard style (MENSIONE green for PICK, dark navy for PASS), electric blue accents, compact, Inter typography, subtle glow
  - Files: `src/components/live/LivePickCard.tsx`, `src/components/live/LivePickCard.css`
  - Verify: `npm run build` — frontend builds; visual inspection with PICK/PASS states

- [ ] **5.3**: CREATE `src/components/live/LiveMarketPanel.tsx` — available live markets.
  - Props: `livePrediction: LivePrediction | null`
  - Render available live markets (1X2, Over/Under, BTTS, Double Chance, Handicap) ONLY when backend supplies them
  - Clearly distinguish **MODEL PROBABILITY** vs **MARKET ODDS** (if market odds available)
  - If NO markets available: show "Live markets unavailable"
  - Visual: Compact market rows (reuse MarketRow.tsx pattern), electric blue for probabilities, gold for odds, dark navy background, Inter typography
  - Files: `src/components/live/LiveMarketPanel.tsx`, `src/components/live/LiveMarketPanel.css`
  - Verify: `npm run build` — frontend builds; visual inspection

- [ ] **5.4**: CREATE `src/components/live/LiveShotProjection.tsx` — shot projection (ONLY when backend supports).
  - Props: `homeStats: LiveStats | null`, `awayStats: LiveStats | null`, `minute: number`, `homeTeam: string`, `awayTeam: string`
  - Render: current shots, expected final shots, projection range, tempo (shots per 10 min)
  - If NO projection model available: show "SHOT PROJECTION Not available"
  - **Do NOT fabricate projections**
  - Visual: Compact card, electric blue accents, Inter typography, dark navy background
  - Files: `src/components/live/LiveShotProjection.tsx`, `src/components/live/LiveShotProjection.css`
  - Verify: `npm run build` — frontend builds; visual inspection

### Phase 6: LiveMatchView Integration into MatchDetail.tsx

- [ ] **6.1**: CREATE `src/components/live/LiveMatchView.tsx` — orchestrator component.
  - Props: `matchId: string`, `match: MatchResponse`, `homeTeam: string`, `awayTeam: string`
  - Use `useLiveMatch(matchId, enabled: match.status === 'live')` hook
  - Render layout: LiveMatchHeader → LiveConnectionStatus → LiveScoreboard → PreMatchLiveComparison (if both available) → LiveStatGrid → LiveShotIntelligence → LiveMomentum → LiveShotMap (if coordinates available) → LiveTimeline (if events available) → LivePickCard → LiveMarketPanel → LiveShotProjection (if available) → LiveDataQuality
  - Responsive: Desktop two-column (score/header left, intelligence panels right) + full-width timeline/markets; mobile vertical stack
  - Handle loading/error/stale states gracefully
  - Files: `src/components/live/LiveMatchView.tsx`, `src/components/live/LiveMatchView.css`
  - Verify: `npm run build` — frontend builds; visual inspection with live match

- [ ] **6.2**: EXTEND `src/pages/MatchDetail.tsx` to integrate LiveMatchView.
  - Detect `match.status === 'live'` (or 'halftime' or other live-adjacent statuses)
  - Conditionally render `<LiveMatchView matchId={match.id} match={match} homeTeam={homeTeam} awayTeam={awayTeam} />` instead of pre-match tabs when live
  - Preserve ALL existing pre-match functionality: if `match.status === 'scheduled'`, render existing GeneralAnalysis/FirstHalfAnalysis/FullMatchAnalysis tabs
  - Preserve existing finished match result rendering
  - Files: `src/pages/MatchDetail.tsx`
  - Verify: `npm run build` — frontend builds; test with scheduled match (pre-match UI), live match (live UI), finished match (result UI)

### Phase 7: Responsive Layout + Polish

- [ ] **7.1**: Implement responsive layout for LiveMatchView.
  - Desktop (≥1024px): Two-column grid (score/header left 40%, intelligence panels right 60%) + full-width timeline/markets below
  - Tablet (768px-1023px): Single column, full-width cards, maintained visual hierarchy
  - Mobile (<768px): Vertical stack (Score → Intelligence → Shot Intelligence → Pick → Timeline → Markets), compact spacing, touch-friendly targets
  - Test all breakpoints
  - Files: `src/components/live/LiveMatchView.css`, individual live component CSS files
  - Verify: `npm run build` — frontend builds; visual inspection at 375px, 768px, 1024px, 1440px widths

- [ ] **7.2**: Add subtle animations for LIVE indicator, minute updates, score changes, goals.
  - LIVE badge: subtle pulse animation (CSS `@keyframes` with `opacity` 1 → 0.7 → 1, 2s infinite)
  - Score update: brief scale animation (1 → 1.05 → 1, 300ms ease-out) when score changes
  - Goal event: brief electric blue glow flash (box-shadow pulse, 500ms)
  - Minute update: smooth transition (opacity fade)
  - **Keep animations restrained** — avoid distracting flashing effects
  - Files: Individual live component CSS files
  - Verify: `npm run build` — frontend builds; visual inspection; animations smooth, not distracting

- [ ] **7.3**: Implement loading, error, empty states for all live components.
  - Loading: Skeleton loaders (dark navy cards with pulse animation) matching component shapes
  - Error: Compact error message with retry button (electric blue)
  - Empty: Dedicated empty states ("Shot data unavailable", "Event data unavailable", etc.) with icons and clear messaging
  - Stale data: Show "Last updated Xs ago" when connection delayed
  - Files: `src/components/live/LiveLoadingState.tsx`, `src/components/live/LiveErrorState.tsx`, `src/components/live/LiveEmptyState.tsx` (shared components)
  - Verify: `npm run build` — frontend builds; visual inspection with loading/error/empty scenarios

- [ ] **7.4**: Accessibility audit for live components.
  - Ensure sufficient contrast (WCAG AA: 4.5:1 for text, 3:1 for UI)
  - Add meaningful ARIA labels (`aria-label`, `aria-live="polite"` for live updates, `role="status"` for connection status)
  - Keyboard navigation: all interactive elements focusable, focus visible (electric blue outline)
  - Screen reader support: announce score changes, goal events, important state changes
  - Tooltips for data quality badges, compact indicators
  - Test with keyboard only, test with screen reader (NVDA/JAWS/VoiceOver)
  - Files: All live component TSX files
  - Verify: Manual accessibility testing; `npm run lint` (if ESLint has a11y rules)

### Phase 8: Performance + Data Fetching Optimization

- [ ] **8.1**: Optimize polling logic in useLiveMatch hook.
  - Implement exponential backoff on repeated errors (5s → 10s → 20s, max 60s)
  - Stop polling when tab/window not visible (use `document.visibilityState`)
  - Resume polling when tab becomes visible again
  - Implement request deduplication (prevent multiple simultaneous requests)
  - Add request timeout (10s)
  - Files: `src/hooks/useLiveMatch.ts`
  - Verify: `npm run build` + browser DevTools Network tab — verify polling stops when tab hidden, resumes when visible; no duplicate requests

- [ ] **8.2**: Optimize chart/animation rendering performance.
  - Use `React.memo` for expensive components (LiveShotMap, LiveTimeline, LiveStatGrid)
  - Use `useMemo` for computed values (shot differentials, shot shares, momentum calculations)
  - Debounce rapid state updates (e.g., multiple events in quick succession)
  - Ensure animations use CSS transforms (hardware-accelerated) not layout properties
  - Files: Live component TSX files
  - Verify: `npm run build` + browser DevTools Performance tab — 60fps during animations, no layout thrashing

### Phase 9: Testing

- [ ] **9.1**: Write unit tests for live components (critical logic).
  - Test LiveStatGrid: handles missing stats gracefully, never shows 0 for unknown
  - Test LiveShotIntelligence: calculates differentials/shares correctly, handles missing data
  - Test LiveMomentum: renders raw indicators, does not fabricate momentum score
  - Test LivePickCard: renders PICK vs PASS correctly, handles signal weakening
  - Test useLiveMatch hook: polling starts/stops, handles errors, updates state correctly
  - Files: `src/components/live/__tests__/*.test.tsx`, `src/hooks/__tests__/useLiveMatch.test.ts`
  - Verify: `npm test` — all new tests pass

- [ ] **9.2**: Write integration tests for LiveMatchView.
  - Test match states: scheduled (pre-match UI), live (live UI), halftime (live UI), finished (result UI), postponed (info state), cancelled (info state)
  - Test data availability scenarios: complete live data, partial (no xG), missing (no shots), stale (delayed connection), unavailable (error)
  - Test score/goal updates: score changes trigger animations, timeline updates
  - Test responsive layouts: desktop/tablet/mobile render correctly
  - Files: `src/pages/__tests__/MatchDetail.test.tsx`
  - Verify: `npm test` — all integration tests pass

- [ ] **9.3**: VERIFY existing tests still pass (no regressions).
  - Run full test suite
  - Fix any broken tests caused by MatchDetail.tsx changes
  - Ensure pre-match functionality untouched
  - Files: All existing test files
  - Verify: `npm test` — ALL tests pass (existing + new)

### Phase 10: Final Verification + Documentation

- [ ] **10.1**: End-to-end manual testing checklist.
  - [ ] Scheduled match: shows pre-match tabs (General/First Half/Full Match), prediction, stats, form, H2H
  - [ ] Live match (mock/dev): shows LiveMatchView with header, scoreboard, connection status, stat grid, shot intelligence, momentum, timeline (if events), pick/PASS, markets, data quality
  - [ ] Live match with missing data: shows "Unavailable" for missing stats, graceful empty states
  - [ ] Live match with stale connection: shows "DELAYED" status, "Last updated Xs ago"
  - [ ] Live match with provider error: shows "UNAVAILABLE" status, error message, does NOT show fake data
  - [ ] Halftime match: shows live UI with "HT" status
  - [ ] Finished match: shows result section with final score, outcome
  - [ ] Responsive: test 375px (mobile), 768px (tablet), 1024px (desktop), 1440px (large desktop)
  - [ ] Accessibility: keyboard navigation works, focus visible, screen reader announces live updates
  - [ ] Performance: polling starts/stops, animations smooth, no memory leaks
  - [ ] MENSIONE visual identity: dark navy/black, electric blue/cyan accents, purple AI, restrained red LIVE, Inter typography, subtle glow, compact spacing
  - Document: Create `docs/LIVE_UI_TESTING_CHECKLIST.md` with checklist
  - Verify: All checklist items pass

- [ ] **10.2**: Run full build and verify production bundle.
  - Run `npm run build`
  - Check bundle size (should not increase excessively)
  - Check for build warnings/errors
  - Test production build locally (`npm run preview`)
  - Files: `frontend/dist/`
  - Verify: `npm run build` succeeds, `npm run preview` serves app correctly, live UI works in production build

- [ ] **10.3**: Update documentation.
  - Update `docs/PROGRESS.md` with Live UI Phase 1 completion summary
  - Document live component API in `docs/LIVE_COMPONENTS.md` (props, usage examples)
  - Document useLiveMatch hook in `docs/LIVE_HOOKS.md`
  - Document known limitations (no live prediction endpoint, no shot coordinates, no momentum model, etc.)
  - Document future enhancements (Phase 2: live prediction engine, shot map, momentum model)
  - Files: `docs/PROGRESS.md`, `docs/LIVE_COMPONENTS.md`, `docs/LIVE_HOOKS.md`
  - Verify: Documentation is clear, accurate, complete

---

## CRITICAL CONSTRAINTS (NON-NEGOTIABLE)

1. **DO NOT rebuild the app or replace architecture** — this is an EXTENSION of existing MENSIONE frontend
2. **DO NOT create a separate frontend system** — integrate into existing MatchDetail.tsx
3. **DO NOT remove working functionality** — preserve ALL pre-match prediction, match, market, provider, routing, styling, intelligence features
4. **DO NOT fabricate live data** — only display real data or show "UNAVAILABLE"/"—"; missing info must be explicitly unavailable, never null-as-zero
5. **DO NOT create a second prediction engine** — reuse existing prediction architecture; route live model outputs through it when available
6. **REUSE/EXTEND existing components** — do not duplicate MatchCard/PredictionCard/StatCard/TeamHeader/MarketCard/Timeline/Chart/API hooks if equivalents exist
7. **Mock data ONLY behind explicit development/mock mode** — clearly isolated, never activates in production by default, clearly labeled "DEVELOPMENT MOCK DATA"
8. **Preserve MENSIONE visual identity exactly** — dark navy/black foundation, electric blue/cyan accents, purple AI accents, MENSIONE green brand only, restrained red LIVE, Inter typography, subtle glow, compact spacing
9. **User-facing language**: Follow existing MENSIONE convention (Turkish: Canlı, Maçlar, İstatistik Karşılaştırması, etc.)
10. **Accessibility compliance** — keyboard navigation, screen reader support, sufficient contrast, meaningful labels

---

## REUSE/EXTEND/CREATE SUMMARY

**REUSE** (existing components used as-is):
- `StatisticsComparison.tsx` (can handle live stats with minor extension)
- `ProbabilityDisplay.tsx` (probability rendering)
- `ConfidenceIndicator.tsx` (confidence rendering)
- `StatusBadge.tsx` (status badges)
- `AIConfidence.tsx` (AI confidence money-bag indicators)
- `MarketRow.tsx` (market row rendering)
- `src/api/client.ts` (HTTP client abstraction)
- `src/styles/global.css` + `src/styles/tokens.css` (design system)

**EXTEND** (existing components/pages modified):
- `MatchDetail.tsx` (add live view detection, conditionally render LiveMatchView)
- `src/api/client.ts` (add `getLiveMatchDetail` wrapper)
- `src/api/types.ts` (extend with live types if needed, though we create separate `src/types/live.ts`)

**CREATE** (new live-specific components):
- `src/types/live.ts` (TypeScript contracts)
- `src/hooks/useLiveMatch.ts` (polling hook)
- `src/components/live/LiveMatchHeader.tsx`
- `src/components/live/LiveScoreboard.tsx`
- `src/components/live/LiveConnectionStatus.tsx`
- `src/components/live/LiveStatGrid.tsx`
- `src/components/live/LiveShotIntelligence.tsx`
- `src/components/live/LiveDataQuality.tsx`
- `src/components/live/LiveMomentum.tsx`
- `src/components/live/LiveShotMap.tsx`
- `src/components/live/LiveTimeline.tsx`
- `src/components/live/PreMatchLiveComparison.tsx`
- `src/components/live/LivePickCard.tsx`
- `src/components/live/LiveMarketPanel.tsx`
- `src/components/live/LiveShotProjection.tsx`
- `src/components/live/LiveMatchView.tsx` (orchestrator)
- `src/components/live/LiveLoadingState.tsx`
- `src/components/live/LiveErrorState.tsx`
- `src/components/live/LiveEmptyState.tsx`

---

## BACKEND LIVE DATA AVAILABILITY FINDINGS

**AVAILABLE** (verified in code):
- ✅ `/api/v1/matches/live` — returns list of live matches with provider health, data quality flags
- ✅ `/api/v1/matches/{matchId}` — returns MatchResponse including live score/minute/status when match is live
- ✅ Match model includes `home_statistics`, `away_statistics` (xG, shots, shots_on_target, possession, corners, cards, etc.)
- ✅ Live ingestion pipeline with out-of-order event handling
- ✅ Provider infrastructure (Ryzellx, FotMob, OpenLigaDB) with health monitoring
- ✅ Data quality flags (has_xg, has_events, has_shots, has_player_positions, has_ball_tracking, has_shot_coordinates, has_live_statistics)

**NOT AVAILABLE** (gaps to handle gracefully):
- ❌ No `/api/v1/matches/{matchId}/live` endpoint for rich live intelligence
- ❌ No `/api/v1/matches/{matchId}/prediction/live` for live prediction updates
- ❌ No `/api/v1/matches/{matchId}/events` for goal/card/sub timeline
- ❌ No shot coordinates endpoint (no shot map data)
- ❌ No validated momentum model (show raw indicators, do not fabricate momentum score)
- ❌ No live market odds (market data appears pre-match only)

**STRATEGY**: Use `getMatch(matchId)` for live match state; poll every 5s when live; gracefully handle missing data with "Unavailable" states; never fabricate data; clearly label data quality; prepare architecture for future backend endpoints (events, shot coords, live prediction, momentum model).

---

## VERIFICATION COMMANDS

- **Type check**: `npm run type-check` (from `frontend/`)
- **Lint**: `npm run lint` (from `frontend/`)
- **Test**: `npm test` (from `frontend/`)
- **Build**: `npm run build` (from `frontend/`)
- **Dev server**: `npm run dev` (from `frontend/`)
- **Preview production**: `npm run preview` (from `frontend/`)
- **Backend health**: `curl http://localhost:8000/health` (backend must be running)
- **Live matches API**: `curl http://localhost:8000/api/v1/matches/live` (backend must be running)

---

## SUCCESS CRITERIA

✅ LiveMatchView renders for live matches in MatchDetail.tsx  
✅ Pre-match functionality preserved for scheduled matches  
✅ Finished match result rendering preserved  
✅ Live stat grid shows real data or "Unavailable"  
✅ Live shot intelligence calculates differentials/shares correctly  
✅ Live connection status reflects real-time data freshness  
✅ LIVE indicator has subtle pulse animation (restrained red)  
✅ MENSIONE visual identity preserved exactly  
✅ Responsive layout works on mobile/tablet/desktop  
✅ Accessibility: keyboard navigation, screen reader support, sufficient contrast  
✅ Performance: polling optimized, animations smooth, no memory leaks  
✅ No fabricated data — missing data explicitly "Unavailable"  
✅ All existing tests pass  
✅ New live component tests pass  
✅ Frontend builds successfully  
✅ Production bundle works correctly  
✅ Documentation updated

---

**END OF PLAN**

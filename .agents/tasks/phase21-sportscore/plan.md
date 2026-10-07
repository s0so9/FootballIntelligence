# PHASE 21 IMPLEMENTATION PLAN
# SportScore API Integration + Live Match Center + Bird's-Eye Pitch

**Project:** TUTAR X Football Intelligence Platform  
**Worktree:** `c:\FootballIntelligence\.worktrees\phase21-sportscore`  
**Branch:** `phase21-sportscore`  
**Base:** `main` (commit 3d83b57)

---

## OVERVIEW

This phase implements a professional **Live Match Center** using the **SportScore API** as the live data source. The center includes:
- Real-time match state (score, minute, status)
- Live events timeline (goals, cards, substitutions)
- Live statistics comparison (possession, shots, corners)
- **Formation-based bird's-eye pitch** with player positioning

**CRITICAL:** SportScore API does **NOT** provide real-time player/ball tracking. The pitch visualization uses **formation-based positioning** (NOT real-time tracking), clearly labeled as "FORMATION VIEW".

---

## FEATURE DECOMPOSITION

This implementation is decomposed into **5 independent features**:

1. **FEAT-001:** SportScore Provider (backend data integration)
2. **FEAT-002:** Live Match Center API Endpoints (backend REST API)
3. **FEAT-003:** Frontend TypeScript Types & API Client (frontend data layer)
4. **FEAT-004:** Bird's-Eye Football Pitch Component (SVG pitch visualization)
5. **FEAT-005:** Live Match Center Page Integration (complete frontend page)

**Dependency Order:** FEAT-001 → FEAT-002 → FEAT-003 → FEAT-004 → FEAT-005

---

## FEAT-001: SportScore Provider

**Goal:** Integrate SportScore API as a new football data provider following existing architecture.

**Files to Create:**
- `backend/app/providers/sportscore.py` — SportScoreFootballProvider class
- `backend/tests/providers/test_sportscore.py` — Provider tests

**Files to Modify:**
- `backend/app/config.py` — Add SportScore config (sportscore_enabled, sportscore_base_url)
- `backend/app/providers/manager.py` — Add SportScore to provider registry (if manager exists)

**Key Implementation Details:**
- Inherit from `FootballDataProvider` (backend/app/providers/base.py)
- Implement required methods: `get_provider_name()`, `is_development_data()`, `get_matches()`, `get_match()`, `get_match_events()`, `get_match_lineups()`
- NEW method: `get_live_match_state()` returning `LiveMatchState` from backend/app/domain/live.py
- Use `httpx.AsyncClient` for HTTP requests with timeout and retry logic
- Integrate with `ProviderCache` (30-second TTL for live data)
- Raise `ProviderError` on failures (never fabricate data)
- Use `None` for unavailable fields (never substitute zeros)

**API Endpoint Mapping (inferred from SportScore MCP):**
- Live matches: `GET /api/1/events?status=live`
- Match detail: `GET /api/1/events/{id}`
- Tracker (investigate): `GET /api/1/events/{id}/tracker`

**Verification:**
```bash
cd backend
.venv\Scripts\python.exe -m pytest tests/providers/test_sportscore.py -v
```
Expected: All tests pass (exit code 0).

---

## FEAT-002: Live Match Center API Endpoints

**Goal:** Create backend REST API endpoints for live match data.

**Files to Create:**
- `backend/app/api/v1/endpoints/live_detail.py` — New endpoints for live match detail

**Files to Modify:**
- `backend/app/api/v1/endpoints/live_matches.py` — Extend to include SportScore provider
- `backend/app/api/v1/__init__.py` — Register live_detail router
- `backend/tests/api/test_live_endpoints.py` — API tests

**New Endpoints:**
1. `GET /api/v1/matches/{id}/live` — LiveMatchDetailResponse
2. `GET /api/v1/matches/{id}/live/events` — LiveEventsResponse
3. `GET /api/v1/matches/{id}/live/lineups` — LiveLineupsResponse
4. `GET /api/v1/matches/{id}/live/stats` — LiveStatisticsResponse

**Existing Endpoint to Extend:**
- `GET /api/v1/matches/live` — Add SportScore to provider instantiation

**Response Schemas (Pydantic):**
- `LiveMatchDetailResponse` — match state with provider, data_quality, timestamp
- `LiveEventsResponse` — list of events (goals, cards, substitutions)
- `LiveLineupsResponse` — home/away lineups with formations
- `LiveStatisticsResponse` — live statistics comparison

**Error Handling:**
- 404 for non-existent match
- 500 with error message for provider failures
- Log errors to backend logs

**Verification:**
```bash
cd backend
.venv\Scripts\python.exe -m pytest tests/api/test_live_endpoints.py -v
.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
# Test: Invoke-WebRequest -Uri http://127.0.0.1:8000/api/v1/matches/live -UseBasicParsing
```
Expected: Tests pass, server starts, /matches/live returns 200.

---

## FEAT-003: Frontend TypeScript Types & API Client

**Goal:** Define TypeScript types and API client functions for live match center.

**Files to Create or Extend:**
- `frontend/src/types/live.ts` — LiveMatchState, LiveEvent, LiveLineups, LiveStatistics types

**Files to Modify:**
- `frontend/src/api/client.ts` — Add getLiveMatchDetail, getLiveEvents, getLiveLineups, getLiveStatistics functions

**Type Definitions:**
- `MatchStatusType` — 'LIVE' | 'SCHEDULED' | 'HALF_TIME' | 'FINISHED' | 'POSTPONED' | 'CANCELLED' | 'SUSPENDED'
- `TeamInfo` — id, name, code, logo (optional except id/name)
- `LiveStats` — shots, shotsOnTarget, xG, possession, corners, fouls, cards (all optional)
- `LiveMatchState` — complete live match state with homeTeam, awayTeam, homeStats, awayStats, dataQuality
- `LiveEvent` — event with type, minute, teamId, playerName, description
- `PlayerInfo` — id, name, jerseyNumber, position
- `LineupInfo` — teamId, teamName, formation, startingXI, substitutes
- `LiveLineups` — matchId, homeLineup, awayLineup
- `LiveStatistics` — matchId, homeStats, awayStats

**API Client Functions:**
- `getLiveMatchDetail(matchId): Promise<LiveMatchState | null>` — 404 returns null
- `getLiveEvents(matchId): Promise<LiveEvent[]>` — Empty array if none
- `getLiveLineups(matchId): Promise<LiveLineups | null>` — null if unavailable
- `getLiveStatistics(matchId): Promise<LiveStatistics | null>` — null if unavailable

**Error Handling:**
- 404 → return null (not an error)
- Timeout → throw ApiError
- Network error → throw ApiError

**Verification:**
```bash
cd frontend
npx tsc --noEmit
npm run build
```
Expected: No TypeScript errors, build succeeds.

---

## FEAT-004: Bird's-Eye Football Pitch Component

**Goal:** Build professional SVG-based football pitch with formation-based player visualization.

**Files to Create:**
- `frontend/src/components/live/LivePitch.tsx` — Main pitch component

**Component Props:**
- `homeLineup: LineupInfo | undefined`
- `awayLineup: LineupInfo | undefined`
- `homeColor: string` (default '#e74c3c')
- `awayColor: string` (default '#3498db')

**SVG Pitch Specifications:**
- **ViewBox:** `0 0 1050 680` (aspect ratio ~1.5:1)
- **Background:** Green (#2d8a2d)
- **Markings:** White lines (stroke-width 2) for touchlines, halfway line, center circle (r=91.5), penalty boxes, six-yard boxes, goal lines

**Formation Mapping:**
- **Parser:** Convert '4-3-3' → [4, 3, 3], '4-4-2' → [4, 4, 2], '3-5-2' → [3, 5, 2]
- **Zones (home team, left-to-right):**
  - Goalkeeper: x=100
  - Defenders: x=200
  - Midfielders: x=500
  - Forwards: x=800
  - Y-axis: Evenly spaced within zone (e.g., 4 defenders: y=150, 300, 450, 600)
- **Away team:** Mirrored (goalkeeper x=950, defenders x=850, midfielders x=550, forwards x=250)

**Player Markers:**
- Circle: radius 20, fill team color, stroke white (stroke-width 2)
- Text (jersey number): font-size 14, bold, centered, fill white
- Text (short name): font-size 10, below circle, fill white

**Labeling:**
- Text overlay in top-right corner: **"FORMAÇÃO"** (font-size 16, fill white, stroke black)
- This clearly indicates formation view, NOT live tracking

**Unavailable Data Handling:**
- If homeLineup or awayLineup undefined: Display centered message "Escalação indisponível"

**Verification:**
```bash
cd frontend
npx tsc --noEmit
npm run dev
# Navigate to /live/test (test page in FEAT-005)
# Visual: Verify pitch renders, players positioned correctly, "FORMAÇÃO" label visible
```
Expected: TypeScript compiles, pitch renders without errors.

---

## FEAT-005: Live Match Center Page Integration

**Goal:** Build complete Live Match Center page integrating all components.

**Files to Create:**
- `frontend/src/pages/LiveMatchCenter.tsx` — Main live match center page
- `frontend/src/pages/LiveMatchesList.tsx` — List of live matches
- `frontend/src/components/live/LiveEventTimeline.tsx` — Event timeline component
- `frontend/src/components/live/LiveStatistics.tsx` — Statistics comparison component
- `frontend/src/components/live/LiveLineups.tsx` — Lineup display component
- `frontend/src/pages/LiveMatchCenter.css` — Page styles

**Files to Modify:**
- `frontend/src/App.tsx` — Add routes: /live, /live/:matchId
- `frontend/src/components/layout/AppLayout.tsx` — Add 'CANLI' navigation link (if nav exists)
- `docs/PROGRESS.md` — Add Phase 21 completion entry

**LiveMatchCenter Page Structure:**
1. **Header:** 'CANLI MAÇ MERKEZİ' title, match info (home vs away, competition)
2. **Score Section:** Score display, minute ('DAKİKA: 34'), status badge (LIVE = red pulsing, HALF_TIME = orange, FINISHED = gray)
3. **Pitch Section:** LivePitch component (center, prominent)
4. **Events Section:** LiveEventTimeline component (left sidebar or below pitch)
5. **Statistics Section:** LiveStatistics component (right sidebar or below pitch)
6. **Lineups Section:** LiveLineups component (bottom, expandable)

**Live Update Strategy:**
- **Polling:** useEffect with setInterval(30000) — 30-second interval
- **Conditions:** Only poll when match status is 'LIVE', stop when 'FINISHED'
- **Cleanup:** clearInterval on unmount

**Turkish UI Labels:**
- Page title: 'CANLI MAÇ MERKEZİ'
- Sections: 'OLAYLAR' (Events), 'İSTATİSTİKLER' (Statistics), 'KADRO' (Lineup), 'FORMAÇÃO' (Formation)
- Minute: 'DAKİKA: {minute}'
- Unavailable: 'INDISPONÍVEL' or '—'

**LiveEventTimeline Component:**
- Props: `events: LiveEvent[]`
- Display: Chronological list (newest first), event icons (⚽ goal, 🟨 yellow, 🟥 red, 🔄 substitution), minute, player name, team indicator

**LiveStatistics Component:**
- Props: `homeStats: LiveStats | undefined, awayStats: LiveStats | undefined`
- Display: Horizontal bar charts for possession %, shots comparison, corners, fouls, cards
- Unavailable: Display '—' for undefined values

**LiveLineups Component:**
- Props: `lineups: LiveLineups | null`
- Display: Home/away formations side-by-side, starting XI with jersey numbers, substitutes list, substitution indicators

**Styling:**
- Dark theme: background #1a1a1a
- Card-based layout: border, padding, margin
- Responsive: 2 columns on desktop, 1 column on mobile
- LIVE badge: Red background, pulsing animation (CSS keyframes)

**Routing:**
- `/live` → LiveMatchesList (list of live matches from backend)
- `/live/:matchId` → LiveMatchCenter (full live match center)

**Verification:**
```bash
cd frontend
npx tsc --noEmit
npm run build

# Start servers
cd ../backend && .venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 &
cd ../frontend && npm run dev &

# Test
# Navigate browser to http://localhost:5173/live
# Select a live match
# Verify: Score displays, pitch renders, events show, stats display, polling updates every 30s

# Check PROGRESS.md updated
Select-String -Path ../docs/PROGRESS.md -Pattern "Phase 21" -Quiet
```
Expected: TypeScript compiles, build succeeds, page loads, all sections render, polling works, PROGRESS.md updated.

---

## VERIFICATION SUMMARY

### Backend Verification
```bash
cd c:\FootballIntelligence\.worktrees\phase21-sportscore\backend

# Test provider
.venv\Scripts\python.exe -m pytest tests/providers/test_sportscore.py -v

# Test API endpoints
.venv\Scripts\python.exe -m pytest tests/api/test_live_endpoints.py -v

# Start server
.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload

# Health check
Invoke-WebRequest -Uri http://127.0.0.1:8000/health -UseBasicParsing
```

### Frontend Verification
```bash
cd c:\FootballIntelligence\.worktrees\phase21-sportscore\frontend

# TypeScript check
npx tsc --noEmit

# Build
npm run build

# Start dev server
npm run dev

# Open browser
# http://localhost:5173/live
```

### End-to-End Verification
1. Start backend server
2. Start frontend server
3. Navigate to http://localhost:5173/live
4. Verify live matches list loads
5. Click a live match
6. Verify Live Match Center loads with:
   - Score and minute displayed
   - Pitch renders with formation view and "FORMAÇÃO" label
   - Events timeline shows match events
   - Statistics display possession, shots, corners
   - Lineups show formations and players
7. Wait 30 seconds
8. Verify live data updates (minute increments, score changes)
9. Verify docs/PROGRESS.md contains Phase 21 entry

---

## RATE LIMITING & CACHING

**SportScore Rate Limit:** ~1000 requests / 24h / IP

**Mitigation:**
- Backend cache: 30-second TTL (aligns with SportScore 60s edge cache)
- Frontend polling: 30-second interval (not aggressive)
- Cache shared across requests (ProviderCache in backend)

**Single user, single match:** 120 requests/hour = 2,880 requests/day (within limit)

**Multiple matches/users:** May approach limit. Monitor and add request queuing if needed.

---

## KNOWN LIMITATIONS

1. **No real-time player tracking** — Formation view only (data not available from SportScore)
2. **No ball position** — Marked as unavailable (data not available)
3. **Polling-based updates** — 30-second interval (WebSocket/SSE for future phase)
4. **Rate limit risk** — Multiple simultaneous users may hit SportScore limit
5. **xG without coordinates** — xG values may exist but no shot map (coordinates unavailable)

---

## FUTURE ENHANCEMENTS (Phase 22+)

- WebSocket/SSE for real-time push updates
- Premium data provider for real player tracking
- Advanced pitch features (heatmaps, passing networks)
- Historical position data replay
- Redis caching for distributed backend
- Rate limit management with request queuing

---

## CRITICAL REMINDERS (AGENTS.md Compliance)

1. **Rule 2:** Always inspect files before editing (read first)
2. **Rule 7:** Verify after implementation (run tests, start servers)
3. **Rule 10:** Never invent statistics/probabilities/data
4. **Rule 12:** AI Analyst is explanation layer only
5. **Rule 13:** Never modify numerical values
6. **Rule 14:** Missing data = unavailable/null, NOT fabricated
7. **Rule 23:** Fix errors found during verification
8. **Rule 25:** Update docs/PROGRESS.md after completion

**DATA RULE:** REAL SPORTSCORE DATA > NULL/UNAVAILABLE > FABRICATED DATA

**NEVER fabricate:**
- Player positions (use formation-based layout only)
- Ball position (mark as unavailable)
- Statistics (use None for unavailable)
- Coordinates (no provider data exists)

**ALWAYS label:**
- Formation view as "FORMAÇÃO" (NOT "live tracking")
- Unavailable data as "—" or "INDISPONÍVEL"
- Data quality indicators in API responses

---

## IMPLEMENTATION SEQUENCE

1. **FEAT-001:** SportScore Provider (backend foundation)
2. **FEAT-002:** Live Match Center API Endpoints (backend API layer)
3. **FEAT-003:** Frontend Types & API Client (frontend data layer)
4. **FEAT-004:** Bird's-Eye Pitch Component (SVG pitch visualization)
5. **FEAT-005:** Live Match Center Page (integration & UI)

**Each FEAT:** Implement → Test → Verify → Commit → Next

**Final:** Update PROGRESS.md → Verify end-to-end → Complete Phase 21

---

**Plan Completed:** 2025-01-XX  
**Planning Agent:** Autonomous Planning Agent  
**Workflow:** wf_2ee6065b1393d5f7  
**Status:** ✅ PLAN COMPLETE — READY FOR IMPLEMENTATION

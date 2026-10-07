# Implementation Plan: Matches Page — League-First Loading and Team Name Fix

**Context:** This is an existing-system correction. The Matches page currently loads all upcoming matches without league filtering, and team names can display as raw IDs instead of human-readable names. This plan fixes the loading flow to be league-first and corrects the team name normalization bug.

**Architecture preservation:** Do NOT rebuild the Matches page. Do NOT modify the prediction engine. Do NOT create mock match data. Do NOT hardcode team names. Do NOT block match rendering on prediction generation.

---

## 1. Backend: Competition Endpoint Comment and Validation

**What to do:**
The competition endpoint at `c:\FootballIntelligence\backend\app\api\v1\endpoints\competitions.py` already returns a hardcoded list of major European competitions with FotMob IDs. This is the correct curated catalog, not fabricated data. Add an inline comment clarifying that this is a curated major-league catalog from FotMob, and verify that `is_development_data` uses `provider.is_development_data()` correctly.

**Files to read first:**
- `c:\FootballIntelligence\backend\app\api\v1\endpoints\competitions.py` (lines 1-75)

**What to change:**
- Line 26-27: Add comment after docstring: `# NOTE: This is a curated catalog of major competitions available from FotMob. These IDs are real FotMob league IDs, not fabricated data.`
- Line 67: Confirm `is_development_data=provider.is_development_data()` is correct (it already is)

**Edge cases:**
- None — this is documentation only

**Verification:**
```bash
cd c:\FootballIntelligence\backend
python -m pytest tests/test_api_competitions.py -v
```

**Expected outcome:** Test passes, confirming competition endpoint returns correct structure with `is_development_data` flag.

---

## 2. Frontend Types: Add Competition Response Types

**What to do:**
Add `CompetitionResponse` and `CompetitionListResponse` types to `c:\FootballIntelligence\frontend\src\api\types.ts`. These already exist in the backend schema (lines 438-487 of `schemas.py`) — mirror them exactly. Do NOT use `any` types.

**Files to read first:**
- `c:\FootballIntelligence\backend\app\api\v1\schemas.py` (lines 438-487: `CompetitionResponse`, `CompetitionListResponse`)
- `c:\FootballIntelligence\frontend\src\api\types.ts` (check end of file for insertion point)

**What to change:**
Add to end of `c:\FootballIntelligence\frontend\src\api\types.ts`:

```typescript
export interface CompetitionResponse {
  id: string;
  name: string;
  country: string | null;
}

export interface CompetitionListResponse {
  competitions: CompetitionResponse[];
  count: number;
  is_development_data: boolean;
}
```

**Edge cases:**
- `country` is optional in backend schema (line 449: `Optional[str]`) — map to `string | null`

**Verification:**
```bash
cd c:\FootballIntelligence\frontend
npx tsc --noEmit
```

**Expected outcome:** TypeScript compilation passes with no errors.

---

## 3. Frontend API Client: Add getCompetitions()

**What to do:**
Add `getCompetitions()` function to `c:\FootballIntelligence\frontend\src\api\client.ts`. Use the existing `request<T>()` helper (lines 23-68) which already handles timeout, HTTP errors, and abort controller. Import the new types from `./types`.

**Files to read first:**
- `c:\FootballIntelligence\frontend\src\api\client.ts` (lines 23-68: `request()` function, lines 70-96: `getMatches()` for pattern)

**What to change:**
Add after `getMatches()` function (around line 97):

```typescript
/**
 * Get list of available competitions.
 */
export async function getCompetitions(): Promise<CompetitionListResponse> {
  return request<CompetitionListResponse>('/competitions');
}
```

Import at top:
```typescript
import type {
  MatchListResponse,
  MatchDetailResponse,
  MatchPredictionResponse,
  LiveMatchesResponse,
  CompetitionListResponse, // ADD THIS
} from './types';
```

**Edge cases:**
- Empty response: handled by `request()` throwing ApiError on non-200 status
- Timeout: handled by `request()` abort controller (30 second timeout)
- Network error: handled by `request()` catch block

**Verification:**
```bash
cd c:\FootballIntelligence\frontend
npx tsc --noEmit
```

**Expected outcome:** TypeScript compilation passes. Function is available for import.

---

## 4. LeagueSelector Component (New File)

**What to do:**
Create `c:\FootballIntelligence\frontend\src\components\LeagueSelector.tsx` and `c:\FootballIntelligence\frontend\src\components\LeagueSelector.css`. This is a simple controlled component for league selection. Use the TUTAR X visual language from existing components (deep space gradient backgrounds, electric blue borders, consistent spacing).

**Files to read first:**
- `c:\FootballIntelligence\frontend\src\components\predictions\MensionePickCard.css` (lines 1-80: for color palette, border styles, gradient patterns)
- `c:\FootballIntelligence\frontend\src\pages\Matches.css` (lines 1-80: for match card styling patterns)

**What to create:**

**File 1: `c:\FootballIntelligence\frontend\src\components\LeagueSelector.tsx`**
```typescript
/**
 * LeagueSelector Component
 * 
 * League/competition selector for Matches page.
 * Follows TUTAR X visual language.
 */

import type { CompetitionResponse } from '../api/types';
import './LeagueSelector.css';

interface LeagueSelectorProps {
  competitions: CompetitionResponse[];
  selectedId: string | null;
  onChange: (id: string) => void;
  loading: boolean;
}

export function LeagueSelector({ competitions, selectedId, onChange, loading }: LeagueSelectorProps) {
  if (loading) {
    return (
      <div className="league-selector">
        <div className="league-selector__loading">
          <div className="loading-spinner"></div>
          <p>Ligler yükleniyor...</p>
        </div>
      </div>
    );
  }

  if (competitions.length === 0) {
    return (
      <div className="league-selector">
        <p className="league-selector__empty">Lig bulunamadı</p>
      </div>
    );
  }

  return (
    <div className="league-selector">
      <label className="league-selector__label">Lig Seç</label>
      <div className="league-selector__grid">
        {competitions.map((comp) => (
          <button
            key={comp.id}
            onClick={() => onChange(comp.id)}
            className={`league-btn ${selectedId === comp.id ? 'league-btn--active' : ''}`}
          >
            <span className="league-btn__name">{comp.name}</span>
            {comp.country && (
              <span className="league-btn__country">{comp.country}</span>
            )}
          </button>
        ))}
      </div>
    </div>
  );
}
```

**File 2: `c:\FootballIntelligence\frontend\src\components\LeagueSelector.css`**
```css
/* LeagueSelector Component - TUTAR X Visual Language */

.league-selector {
  margin-bottom: var(--spacing-6);
}

.league-selector__label {
  display: block;
  font-size: 0.875rem;
  font-weight: 600;
  color: var(--color-text-secondary);
  margin-bottom: var(--spacing-3);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.league-selector__grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: var(--spacing-3);
}

.league-btn {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  padding: 12px 16px;
  background: linear-gradient(135deg, rgba(13, 20, 36, 0.9) 0%, rgba(16, 24, 43, 0.85) 100%);
  border: 1px solid rgba(14, 165, 233, 0.25);
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s ease;
  text-align: left;
}

.league-btn:hover {
  border-color: rgba(14, 165, 233, 0.45);
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.3);
  transform: translateY(-1px);
}

.league-btn--active {
  border-color: #0ea5e9;
  background: linear-gradient(135deg, rgba(14, 165, 233, 0.15) 0%, rgba(14, 165, 233, 0.1) 100%);
  box-shadow: 0 0 20px rgba(14, 165, 233, 0.2);
}

.league-btn__name {
  font-size: 0.9rem;
  font-weight: 600;
  color: var(--color-text-primary);
  margin-bottom: 4px;
}

.league-btn__country {
  font-size: 0.75rem;
  color: var(--color-text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.league-selector__loading,
.league-selector__empty {
  padding: var(--spacing-4);
  text-align: center;
  color: var(--color-text-secondary);
  font-size: 0.875rem;
}

.league-selector__loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--spacing-2);
}
```

**Edge cases:**
- Empty competitions array: show "Lig bulunamadı"
- Loading state: show spinner + "Ligler yükleniyor..."
- No country: omit country badge
- Long competition names: text will wrap naturally in flex column layout

**Verification:**
```bash
cd c:\FootballIntelligence\frontend
npx tsc --noEmit
```

**Expected outcome:** TypeScript compilation passes. Component exports correctly.

---

## 5. Matches.tsx: League-First Refactor

**What to do:**
Refactor `c:\FootballIntelligence\frontend\src\pages\Matches.tsx` to implement league-first loading. The current implementation (lines 11-131) calls `getUpcomingMatches(7)` once on mount and shows all results. The new flow: (1) Load competitions on mount, (2) Show LeagueSelector, (3) On league selection call `getMatches({ competition_id })`, (4) Render matches immediately, (5) Prediction loading remains non-blocking (already non-blocking — predictions are loaded on detail page, not on matches list).

**Files to read first:**
- `c:\FootballIntelligence\frontend\src\pages\Matches.tsx` (entire file, lines 1-131)
- `c:\FootballIntelligence\frontend\src\pages\Dashboard.tsx` (lines 59-100: pattern for `useEffect` with cleanup and duplicate prevention)

**What to change:**

**Step 1: Add imports**
```typescript
import { getUpcomingMatches, getMatches, getCompetitions } from '../api';
import type { CompetitionResponse } from '../api/types';
import { LeagueSelector } from '../components/LeagueSelector';
```

**Step 2: Replace state (around lines 8-11)**
```typescript
const [competitions, setCompetitions] = useState<CompetitionResponse[]>([]);
const [selectedCompetitionId, setSelectedCompetitionId] = useState<string | null>(null);
const [matches, setMatches] = useState<NormalizedMatch[]>([]);
const [competitionsLoading, setCompetitionsLoading] = useState(true);
const [matchesLoading, setMatchesLoading] = useState(false);
const [error, setError] = useState<string | null>(null);
const [isDevelopmentData, setIsDevelopmentData] = useState(false);
```

**Step 3: Replace useEffect (lines 13-36) with two effects**

Effect 1: Load competitions on mount
```typescript
useEffect(() => {
  let isMounted = true;

  async function fetchCompetitions() {
    try {
      setCompetitionsLoading(true);
      setError(null);

      console.log('[DEBUG Matches.tsx] Fetching competitions...');
      const response = await getCompetitions();
      
      if (!isMounted) return;
      
      setCompetitions(response.competitions);
      console.log('[DEBUG Matches.tsx] Loaded', response.count, 'competitions');
    } catch (err) {
      if (!isMounted) return;
      console.error('[DEBUG Matches.tsx] Error loading competitions:', err);
      setError(err instanceof Error ? err.message : 'Ligler yüklenirken bir hata oluştu');
    } finally {
      if (isMounted) {
        setCompetitionsLoading(false);
      }
    }
  }

  fetchCompetitions();

  return () => {
    isMounted = false;
  };
}, []);
```

Effect 2: Load matches when competition selected
```typescript
useEffect(() => {
  if (!selectedCompetitionId) {
    // No competition selected yet — clear matches
    setMatches([]);
    return;
  }

  let isMounted = true;
  const abortController = new AbortController();

  async function fetchMatches() {
    try {
      setMatchesLoading(true);
      setError(null);

      console.log('[DEBUG Matches.tsx] Fetching matches for competition:', selectedCompetitionId);
      
      // Use UTC date range for filtering
      const today = new Date();
      const fromDate = formatDateForAPI(today);
      const futureDate = new Date(today);
      futureDate.setDate(futureDate.getDate() + 7);
      const toDate = formatDateForAPI(futureDate);

      const response = await getMatches({
        competition_id: selectedCompetitionId,
        from_date: fromDate,
        to_date: toDate,
        status: 'scheduled',
      });
      
      if (!isMounted) return;

      const normalizedMatches = normalizeMatches(response.matches);
      setMatches(normalizedMatches);
      setIsDevelopmentData(response.is_development_data);
      
      console.log('[DEBUG Matches.tsx] Loaded', normalizedMatches.length, 'matches');
    } catch (err) {
      if (!isMounted) return;
      console.error('[DEBUG Matches.tsx] Error loading matches:', err);
      setError(err instanceof Error ? err.message : 'Maçlar yüklenirken bir hata oluştu');
    } finally {
      if (isMounted) {
        setMatchesLoading(false);
      }
    }
  }

  fetchMatches();

  return () => {
    isMounted = false;
    abortController.abort();
  };
}, [selectedCompetitionId]);

// Helper function
function formatDateForAPI(date: Date): string {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}
```

**Step 4: Update JSX render logic**

Replace loading state (lines 38-52):
```typescript
if (competitionsLoading) {
  return (
    <div className="page-container">
      <div className="page-header">
        <h1>Maçlar</h1>
        <p className="page-subtitle">Yaklaşan maçlar ve tahminler</p>
      </div>
      <div className="loading-state">
        <div className="loading-spinner"></div>
        <p>Ligler yükleniyor...</p>
      </div>
    </div>
  );
}
```

Replace error state (lines 54-68): keep as-is

Replace empty state and main render (lines 70-131):
```typescript
return (
  <div className="page-container">
    <div className="page-header">
      <h1>Maçlar</h1>
      <p className="page-subtitle">
        Yaklaşan maçlar ve tahminler
        {isDevelopmentData && (
          <span className="dev-badge">Geliştirme Verisi</span>
        )}
      </p>
    </div>

    <LeagueSelector
      competitions={competitions}
      selectedId={selectedCompetitionId}
      onChange={setSelectedCompetitionId}
      loading={false}
    />

    {!selectedCompetitionId && (
      <div className="empty-state">
        <div className="empty-icon">⚽</div>
        <p className="empty-title">Bir lig seçin</p>
        <p className="empty-description">
          Maçları görüntülemek için yukarıdan bir lig seçin.
        </p>
      </div>
    )}

    {selectedCompetitionId && matchesLoading && (
      <div className="loading-state">
        <div className="loading-spinner"></div>
        <p>Maçlar yükleniyor...</p>
      </div>
    )}

    {selectedCompetitionId && !matchesLoading && matches.length === 0 && (
      <div className="empty-state">
        <div className="empty-icon">⚽</div>
        <p className="empty-title">Bu ligde yaklaşan maç bulunamadı</p>
        <p className="empty-description">
          Seçilen ligde önümüzdeki 7 günde planlanmış maç bulunmamaktadır.
        </p>
      </div>
    )}

    {selectedCompetitionId && !matchesLoading && matches.length > 0 && (
      <div className="matches-list">
        {matches.map((match) => {
          const dateTime = formatMatchDateTime(match.scheduledAt);

          return (
            <Link
              key={match.id}
              to={`/matches/${match.id}`}
              className="match-card"
            >
              <div className="match-card__header">
                <div className="match-card__competition">
                  {formatCompetitionName(match.competitionId)}
                  {match.round && ` - ${match.round}. Hafta`}
                </div>
                <span className={`match-status match-status--${match.status}`}>
                  {formatMatchStatus(match.status as import('../api/types').MatchStatus)}
                </span>
              </div>

              <div className="match-card__body">
                <div className="match-card__datetime">
                  <div className="match-date">{dateTime.date}</div>
                  <div className="match-time">{dateTime.time}</div>
                </div>

                <div className="match-card__teams">
                  <div className="team team--home">
                    <span className="team-name">{match.homeTeam.name}</span>
                  </div>

                  <div className="match-vs">
                    {match.homeScore !== null && match.awayScore !== null ? (
                      <div className="match-score">
                        {match.homeScore} - {match.awayScore}
                      </div>
                    ) : (
                      <span className="vs-text">vs</span>
                    )}
                  </div>

                  <div className="team team--away">
                    <span className="team-name">{match.awayTeam.name}</span>
                  </div>
                </div>

                {match.status === 'scheduled' && (
                  <div className="match-card__indicator">
                    <span className="prediction-indicator">
                      📊 Tahmin Mevcut
                    </span>
                  </div>
                )}
              </div>
            </Link>
          );
        })}
      </div>
    )}
  </div>
);
```

**Edge cases:**
- No competitions returned: handled by LeagueSelector empty state
- Competition API error: shown in main error state
- No competition selected initially: show "Bir lig seçin" empty state
- Competition selected but no matches: show "Bu ligde yaklaşan maç bulunamadı"
- Competition API slow: show "Ligler yükleniyor..."
- Matches API slow: show "Maçlar yükleniyor..." (per-league loading state)
- User rapidly switches leagues: `isMounted` flag and `abortController` prevent race conditions and duplicate state updates
- Date filtering: uses UTC timestamps via `formatDateForAPI()` helper, not browser local date strings

**Duplicate request protection:**
- `useEffect` cleanup with `isMounted = false` prevents state updates after unmount
- `abortController` cancels in-flight requests when `selectedCompetitionId` changes
- No duplicate competition requests: effect runs only once on mount
- No duplicate match requests: effect depends only on `selectedCompetitionId`, not on other state

**Verification:**
```bash
cd c:\FootballIntelligence\frontend
npx tsc --noEmit
npm run build
```

**Expected outcome:** TypeScript compilation passes. Production build succeeds. No runtime errors in console.

---

## 6. Team Name Normalization Fix

**What to do:**
Fix the bug in `c:\FootballIntelligence\frontend\src\utils\matchNormalizer.ts` lines 37-73. The current `normalizeTeam()` function has a fallback branch (lines 64-68) that returns the raw `teamId` as the team name when it is not purely numeric and not a dev pattern. This is wrong — FotMob provider IDs can be alphanumeric strings like `"fotmob_123"` or opaque identifiers that are not human-readable. NEVER display a raw identifier as a team name unless it was explicitly returned as the `name` field inside a `team` object from the backend.

**Files to read first:**
- `c:\FootballIntelligence\frontend\src\utils\matchNormalizer.ts` (lines 37-73: `normalizeTeam()`)
- `c:\FootballIntelligence\backend\app\api\v1\endpoints\matches.py` (lines 96-107: backend constructs `TeamInfoResponse` from `_provider_home_team_name` / `_provider_away_team_name` private attributes)
- `c:\FootballIntelligence\backend\app\providers\adapter.py` (lines 290-300: `_map_provider_match_to_domain()` stores team names as private attributes)

**Current priority (INCORRECT):**
1. `teamInfo.name` if exists ✅ CORRECT
2. dev pattern (`dev_team_xxx`) → format ✅ CORRECT
3. purely numeric ID → 'Takım bilgisi yok' ✅ CORRECT
4. **any other ID → use ID as name ❌ BUG**

**Required priority (CORRECT):**
1. `teamInfo.name` if teamInfo exists and name is non-empty string ✅
2. dev pattern (`dev_team_xxx`) → format ✅
3. **Otherwise (any raw ID, numeric or not) → 'Takım bilgisi yok'** ✅

**What to change:**
Replace lines 64-68 in `c:\FootballIntelligence\frontend\src\utils\matchNormalizer.ts`:

**OLD (INCORRECT):**
```typescript
  // Use the ID as-is if it looks like it might be a real identifier
  return {
    id: teamId,
    name: teamId,
  };
```

**NEW (CORRECT):**
```typescript
  // If we reach here, we have an opaque provider ID with no team info
  // Never display a raw identifier as a team name
  return {
    id: teamId,
    name: 'Takım bilgisi yok',
  };
```

**Edge cases:**
- `teamInfo.name` is null or empty string: fall through to dev pattern check, then to unavailable
- `teamInfo` exists but `name` is null: fall through to dev pattern check, then to unavailable
- `teamId` is numeric string like `"12345"`: already handled correctly (line 59)
- `teamId` is alphanumeric like `"fotmob_123"`: now correctly shows 'Takım bilgisi yok'
- `teamId` is dev pattern: already handled correctly (line 50)
- Both `teamInfo` and `teamId` missing/null: already handled correctly (lines 71-74)

**Verification:**
```bash
cd c:\FootballIntelligence\frontend
npx tsc --noEmit
```

**Expected outcome:** TypeScript compilation passes. Team names are NEVER raw IDs.

---

## 7. Regression Tests: Team Normalization

**What to do:**
Create `c:\FootballIntelligence\frontend\src\utils\__tests__\matchNormalizer.test.ts` to test all relevant response shapes for `normalizeTeam()`. Use vitest (frontend uses vitest 1.0.4 per package.json line 27).

**Files to read first:**
- `c:\FootballIntelligence\frontend\package.json` (lines 11-12: test scripts, line 27: vitest dependency)
- `c:\FootballIntelligence\frontend\src\utils\matchNormalizer.ts` (lines 37-76: `normalizeTeam()` to understand parameters)

**What to create:**

**File: `c:\FootballIntelligence\frontend\src\utils\__tests__\matchNormalizer.test.ts`**
```typescript
/**
 * Tests for matchNormalizer utility
 * 
 * Regression tests for team name normalization — ensures raw IDs are never displayed as team names.
 */

import { describe, it, expect } from 'vitest';
import { normalizeMatch, type NormalizedMatch } from '../matchNormalizer';
import type { MatchResponse, TeamInfoResponse } from '../../api/types';

describe('matchNormalizer', () => {
  describe('normalizeTeam', () => {
    // Helper to create a minimal MatchResponse
    function createMatchResponse(
      homeTeamId: string,
      awayTeamId: string,
      homeTeam: TeamInfoResponse | null = null,
      awayTeam: TeamInfoResponse | null = null
    ): MatchResponse {
      return {
        id: 'match_1',
        competition_id: 'comp_1',
        season_id: 'season_1',
        home_team_id: homeTeamId,
        away_team_id: awayTeamId,
        venue_id: null,
        home_team: homeTeam,
        away_team: awayTeam,
        scheduled_at: '2026-10-10T15:00:00Z',
        status: 'scheduled',
        home_score: null,
        away_score: null,
        home_score_ht: null,
        away_score_ht: null,
        home_statistics: null,
        away_statistics: null,
        home_statistics_ht: null,
        away_statistics_ht: null,
        minute: null,
        added_time: null,
        outcome: null,
        round: null,
        created_at: null,
        updated_at: null,
      };
    }

    it('should use teamInfo.name when available', () => {
      const match = createMatchResponse(
        'team_home',
        'team_away',
        { id: 'team_home', name: 'Arsenal', short_name: 'ARS', code: 'ARS', logo_url: 'logo.png' },
        { id: 'team_away', name: 'Chelsea', short_name: 'CHE', code: 'CHE', logo_url: null }
      );
      const normalized = normalizeMatch(match);

      expect(normalized.homeTeam.name).toBe('Arsenal');
      expect(normalized.homeTeam.shortName).toBe('ARS');
      expect(normalized.awayTeam.name).toBe('Chelsea');
      expect(normalized.awayTeam.shortName).toBe('CHE');
    });

    it('should preserve all teamInfo fields when present', () => {
      const match = createMatchResponse(
        'team_home',
        'team_away',
        { id: 'team_home', name: 'Real Madrid', short_name: 'RMA', code: 'RMA', logo_url: 'logo.png' },
        null
      );
      const normalized = normalizeMatch(match);

      expect(normalized.homeTeam.id).toBe('team_home');
      expect(normalized.homeTeam.name).toBe('Real Madrid');
      expect(normalized.homeTeam.shortName).toBe('RMA');
      expect(normalized.homeTeam.code).toBe('RMA');
      expect(normalized.homeTeam.logoUrl).toBe('logo.png');
    });

    it('should show "Takım bilgisi yok" for numeric string ID when teamInfo missing', () => {
      const match = createMatchResponse('12345', '67890', null, null);
      const normalized = normalizeMatch(match);

      expect(normalized.homeTeam.name).toBe('Takım bilgisi yok');
      expect(normalized.awayTeam.name).toBe('Takım bilgisi yok');
    });

    it('should format dev_team_xxx pattern correctly', () => {
      const match = createMatchResponse('dev_team_arsenal', 'dev_team_liverpool', null, null);
      const normalized = normalizeMatch(match);

      expect(normalized.homeTeam.name).toBe('Arsenal');
      expect(normalized.awayTeam.name).toBe('Liverpool');
    });

    it('should show "Takım bilgisi yok" for alphanumeric provider ID when teamInfo missing', () => {
      const match = createMatchResponse('fotmob_123456', 'ryzellx_abc789', null, null);
      const normalized = normalizeMatch(match);

      expect(normalized.homeTeam.name).toBe('Takım bilgisi yok');
      expect(normalized.awayTeam.name).toBe('Takım bilgisi yok');
    });

    it('should show "Takım bilgisi yok" when both teamInfo and teamId are missing', () => {
      const match = createMatchResponse('', '', null, null);
      const normalized = normalizeMatch(match);

      expect(normalized.homeTeam.name).toBe('Takım bilgisi yok');
      expect(normalized.awayTeam.name).toBe('Takım bilgisi yok');
    });

    it('should show "Takım bilgisi yok" when teamInfo is present but name is null', () => {
      const match = createMatchResponse(
        'team_home',
        'team_away',
        { id: 'team_home', name: null as any, short_name: null, code: null, logo_url: null },
        { id: 'team_away', name: '', short_name: null, code: null, logo_url: null }
      );
      const normalized = normalizeMatch(match);

      expect(normalized.homeTeam.name).toBe('Takım bilgisi yok');
      expect(normalized.awayTeam.name).toBe('Takım bilgisi yok');
    });

    it('should prefer teamInfo.name over teamId when both are present', () => {
      const match = createMatchResponse(
        'team_home',
        'team_away',
        { id: 'team_home', name: 'Manchester United', short_name: 'MUN', code: 'MUN', logo_url: null },
        { id: 'different_id', name: 'Manchester City', short_name: 'MCI', code: 'MCI', logo_url: null }
      );
      const normalized = normalizeMatch(match);

      expect(normalized.homeTeam.name).toBe('Manchester United');
      expect(normalized.homeTeam.id).toBe('team_home'); // Uses teamInfo.id
      expect(normalized.awayTeam.name).toBe('Manchester City');
      expect(normalized.awayTeam.id).toBe('different_id'); // Uses teamInfo.id
    });
  });
});
```

**Edge cases covered:**
1. `teamInfo.name` present → use name ✅
2. `teamInfo` all fields present → preserve shortName, code, logoUrl ✅
3. `teamId` is numeric string, no teamInfo → 'Takım bilgisi yok' ✅
4. `teamId` is `dev_team_arsenal` → 'Arsenal' ✅
5. `teamId` is alphanumeric provider ID like `'fotmob_123'`, no teamInfo → 'Takım bilgisi yok' ✅
6. both `teamInfo` and `teamId` missing/null → 'Takım bilgisi yok' ✅
7. `teamInfo` present but `name` is null/empty → fall to ID logic → 'Takım bilgisi yok' ✅
8. `teamInfo.name` is non-empty, `teamId` different → prefer teamInfo.name ✅

**Verification:**
```bash
cd c:\FootballIntelligence\frontend
npm run test -- matchNormalizer.test.ts
```

**Expected outcome:** All 8 tests pass.

---

## 8. Regression Tests: Matches Page Component

**What to do:**
Create `c:\FootballIntelligence\frontend\src\pages\__tests__\Matches.test.tsx` to test the league-first loading flow. Mock `getCompetitions` and `getMatches` API functions. Test: competitions load, league selector renders, selecting a competition calls correct API, match cards render with team names not IDs, empty states, error states, no duplicate requests.

**Files to read first:**
- `c:\FootballIntelligence\frontend\package.json` (lines 18-21: @testing-library/react dependency)
- `c:\FootballIntelligence\frontend\src\pages\Matches.tsx` (after refactor, to understand component behavior)

**What to create:**

**File: `c:\FootballIntelligence\frontend\src\pages\__tests__\Matches.test.tsx`**
```typescript
/**
 * Tests for Matches page
 * 
 * Regression tests for league-first loading flow and duplicate request prevention.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { userEvent } from '@testing-library/user-event';
import { BrowserRouter } from 'react-router-dom';
import { Matches } from '../Matches';
import * as api from '../../api';

// Mock API module
vi.mock('../../api', () => ({
  getCompetitions: vi.fn(),
  getMatches: vi.fn(),
}));

const mockGetCompetitions = vi.mocked(api.getCompetitions);
const mockGetMatches = vi.mocked(api.getMatches);

describe('Matches page', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  function renderMatches() {
    return render(
      <BrowserRouter>
        <Matches />
      </BrowserRouter>
    );
  }

  it('should load competitions and render LeagueSelector', async () => {
    mockGetCompetitions.mockResolvedValue({
      competitions: [
        { id: '47', name: 'Premier League', country: 'ENG' },
        { id: '87', name: 'La Liga', country: 'ESP' },
      ],
      count: 2,
      is_development_data: false,
    });

    renderMatches();

    // Should show loading initially
    expect(screen.getByText(/ligler yükleniyor/i)).toBeInTheDocument();

    // Wait for competitions to load
    await waitFor(() => {
      expect(screen.getByText('Premier League')).toBeInTheDocument();
      expect(screen.getByText('La Liga')).toBeInTheDocument();
    });

    expect(mockGetCompetitions).toHaveBeenCalledTimes(1);
  });

  it('should call getMatches with competition_id when league selected', async () => {
    mockGetCompetitions.mockResolvedValue({
      competitions: [
        { id: '47', name: 'Premier League', country: 'ENG' },
      ],
      count: 1,
      is_development_data: false,
    });

    mockGetMatches.mockResolvedValue({
      matches: [
        {
          id: 'match_1',
          competition_id: '47',
          season_id: 'season_1',
          home_team_id: 'team_home',
          away_team_id: 'team_away',
          venue_id: null,
          home_team: { id: 'team_home', name: 'Arsenal', short_name: 'ARS', code: 'ARS', logo_url: null },
          away_team: { id: 'team_away', name: 'Chelsea', short_name: 'CHE', code: 'CHE', logo_url: null },
          scheduled_at: '2026-10-10T15:00:00Z',
          status: 'scheduled',
          home_score: null,
          away_score: null,
          home_score_ht: null,
          away_score_ht: null,
          home_statistics: null,
          away_statistics: null,
          home_statistics_ht: null,
          away_statistics_ht: null,
          minute: null,
          added_time: null,
          outcome: null,
          round: 5,
          created_at: null,
          updated_at: null,
        },
      ],
      count: 1,
      is_development_data: false,
    });

    renderMatches();

    // Wait for competitions
    await waitFor(() => {
      expect(screen.getByText('Premier League')).toBeInTheDocument();
    });

    // Click Premier League
    const leagueBtn = screen.getByText('Premier League');
    await userEvent.click(leagueBtn);

    // Should call getMatches with competition_id
    await waitFor(() => {
      expect(mockGetMatches).toHaveBeenCalledWith(
        expect.objectContaining({
          competition_id: '47',
          status: 'scheduled',
        })
      );
    });
  });

  it('should display match cards with team names, not IDs', async () => {
    mockGetCompetitions.mockResolvedValue({
      competitions: [{ id: '47', name: 'Premier League', country: 'ENG' }],
      count: 1,
      is_development_data: false,
    });

    mockGetMatches.mockResolvedValue({
      matches: [
        {
          id: 'match_1',
          competition_id: '47',
          season_id: 'season_1',
          home_team_id: 'team_home',
          away_team_id: 'team_away',
          venue_id: null,
          home_team: { id: 'team_home', name: 'Arsenal', short_name: 'ARS', code: 'ARS', logo_url: null },
          away_team: { id: 'team_away', name: 'Chelsea', short_name: 'CHE', code: 'CHE', logo_url: null },
          scheduled_at: '2026-10-10T15:00:00Z',
          status: 'scheduled',
          home_score: null,
          away_score: null,
          home_score_ht: null,
          away_score_ht: null,
          home_statistics: null,
          away_statistics: null,
          home_statistics_ht: null,
          away_statistics_ht: null,
          minute: null,
          added_time: null,
          outcome: null,
          round: null,
          created_at: null,
          updated_at: null,
        },
      ],
      count: 1,
      is_development_data: false,
    });

    renderMatches();

    // Wait and select league
    await waitFor(() => {
      expect(screen.getByText('Premier League')).toBeInTheDocument();
    });
    await userEvent.click(screen.getByText('Premier League'));

    // Wait for matches to load
    await waitFor(() => {
      expect(screen.getByText('Arsenal')).toBeInTheDocument();
      expect(screen.getByText('Chelsea')).toBeInTheDocument();
    });

    // Should NOT display raw IDs like 'team_home'
    expect(screen.queryByText('team_home')).not.toBeInTheDocument();
    expect(screen.queryByText('team_away')).not.toBeInTheDocument();
  });

  it('should show correct empty state when no competition selected', async () => {
    mockGetCompetitions.mockResolvedValue({
      competitions: [{ id: '47', name: 'Premier League', country: 'ENG' }],
      count: 1,
      is_development_data: false,
    });

    renderMatches();

    await waitFor(() => {
      expect(screen.getByText('Premier League')).toBeInTheDocument();
    });

    // Should show "Bir lig seçin"
    expect(screen.getByText(/bir lig seçin/i)).toBeInTheDocument();
  });

  it('should show correct empty state when competition has no matches', async () => {
    mockGetCompetitions.mockResolvedValue({
      competitions: [{ id: '47', name: 'Premier League', country: 'ENG' }],
      count: 1,
      is_development_data: false,
    });

    mockGetMatches.mockResolvedValue({
      matches: [],
      count: 0,
      is_development_data: false,
    });

    renderMatches();

    await waitFor(() => {
      expect(screen.getByText('Premier League')).toBeInTheDocument();
    });
    await userEvent.click(screen.getByText('Premier League'));

    await waitFor(() => {
      expect(screen.getByText(/bu ligde yaklaşan maç bulunamadı/i)).toBeInTheDocument();
    });
  });

  it('should handle competition API error', async () => {
    mockGetCompetitions.mockRejectedValue(new Error('Network error'));

    renderMatches();

    await waitFor(() => {
      expect(screen.getByText(/network error/i)).toBeInTheDocument();
    });
  });

  it('should handle match API error', async () => {
    mockGetCompetitions.mockResolvedValue({
      competitions: [{ id: '47', name: 'Premier League', country: 'ENG' }],
      count: 1,
      is_development_data: false,
    });

    mockGetMatches.mockRejectedValue(new Error('Match fetch failed'));

    renderMatches();

    await waitFor(() => {
      expect(screen.getByText('Premier League')).toBeInTheDocument();
    });
    await userEvent.click(screen.getByText('Premier League'));

    await waitFor(() => {
      expect(screen.getByText(/match fetch failed/i)).toBeInTheDocument();
    });
  });

  it('should call getCompetitions only once (no duplicate requests)', async () => {
    mockGetCompetitions.mockResolvedValue({
      competitions: [{ id: '47', name: 'Premier League', country: 'ENG' }],
      count: 1,
      is_development_data: false,
    });

    renderMatches();

    await waitFor(() => {
      expect(screen.getByText('Premier League')).toBeInTheDocument();
    });

    expect(mockGetCompetitions).toHaveBeenCalledTimes(1);
  });

  it('should call getMatches once per competition selection (no duplicate requests)', async () => {
    mockGetCompetitions.mockResolvedValue({
      competitions: [{ id: '47', name: 'Premier League', country: 'ENG' }],
      count: 1,
      is_development_data: false,
    });

    mockGetMatches.mockResolvedValue({
      matches: [],
      count: 0,
      is_development_data: false,
    });

    renderMatches();

    await waitFor(() => {
      expect(screen.getByText('Premier League')).toBeInTheDocument();
    });
    await userEvent.click(screen.getByText('Premier League'));

    await waitFor(() => {
      expect(mockGetMatches).toHaveBeenCalledTimes(1);
    });

    // Click again - should not trigger additional request
    await userEvent.click(screen.getByText('Premier League'));

    // Still only called once (same competition, no re-fetch)
    expect(mockGetMatches).toHaveBeenCalledTimes(1);
  });
});
```

**Edge cases covered:**
1. Competitions load and LeagueSelector renders ✅
2. Selecting a competition calls `getMatches({ competition_id })` ✅
3. Match cards show team names (not IDs) ✅
4. Empty state when no competition selected ✅
5. Empty state when competition has no matches ✅
6. Competition API error → error state without crashing ✅
7. Match API error → error state without crashing ✅
8. `getCompetitions` called only once (no duplicate requests) ✅
9. `getMatches` not duplicated on re-clicking same league ✅

**Verification:**
```bash
cd c:\FootballIntelligence\frontend
npm run test -- Matches.test.tsx
```

**Expected outcome:** All tests pass.

---

## 9. Backend Competition Endpoint Test

**What to do:**
Create `c:\FootballIntelligence\backend\tests\test_api_competitions.py` to test the `/api/v1/competitions` endpoint. Verify response structure, `is_development_data` flag, and that each competition has required fields.

**Files to read first:**
- `c:\FootballIntelligence\backend\tests\test_api_matches.py` (lines 1-50: pattern for FastAPI test client usage)
- `c:\FootballIntelligence\backend\requirements.txt` (line 22: pytest dependency)

**What to create:**

**File: `c:\FootballIntelligence\backend\tests\test_api_competitions.py`**
```python
"""
Tests for competitions API endpoints.

Regression tests for competition list endpoint structure and flags.
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_list_competitions_returns_200():
    """GET /api/v1/competitions should return 200."""
    response = client.get("/api/v1/competitions")
    assert response.status_code == 200


def test_list_competitions_response_structure():
    """Response should have competitions array, count, and is_development_data flag."""
    response = client.get("/api/v1/competitions")
    data = response.json()
    
    assert "competitions" in data
    assert "count" in data
    assert "is_development_data" in data
    
    assert isinstance(data["competitions"], list)
    assert isinstance(data["count"], int)
    assert isinstance(data["is_development_data"], bool)


def test_list_competitions_each_has_required_fields():
    """Each competition should have id, name, and country."""
    response = client.get("/api/v1/competitions")
    data = response.json()
    
    competitions = data["competitions"]
    assert len(competitions) > 0, "Should return at least one competition"
    
    for comp in competitions:
        assert "id" in comp
        assert "name" in comp
        assert "country" in comp
        
        assert isinstance(comp["id"], str)
        assert isinstance(comp["name"], str)
        # country can be null for international competitions
        assert comp["country"] is None or isinstance(comp["country"], str)


def test_list_competitions_count_matches_length():
    """count field should match length of competitions array."""
    response = client.get("/api/v1/competitions")
    data = response.json()
    
    assert data["count"] == len(data["competitions"])


def test_list_competitions_has_known_leagues():
    """Should include major European leagues in the catalog."""
    response = client.get("/api/v1/competitions")
    data = response.json()
    
    competition_names = [comp["name"] for comp in data["competitions"]]
    
    # Verify at least some major leagues are present
    assert "Premier League" in competition_names
    assert "La Liga" in competition_names or "Serie A" in competition_names
```

**Edge cases covered:**
- 200 status code ✅
- Response has `competitions`, `count`, `is_development_data` ✅
- Each competition has `id`, `name`, `country` ✅
- `country` can be null ✅
- `count` matches array length ✅
- Known leagues present (sanity check) ✅

**Verification:**
```bash
cd c:\FootballIntelligence\backend
python -m pytest tests/test_api_competitions.py -v
```

**Expected outcome:** All tests pass.

---

## 10. Final Verification

**What to do:**
Run all verification commands to ensure the entire implementation is correct and no regressions were introduced.

**Commands to run:**

**Backend tests:**
```bash
cd c:\FootballIntelligence\backend
python -m pytest tests/ -v
```

**Expected outcome:** All backend tests pass, including new `test_api_competitions.py`.

**Frontend TypeScript check:**
```bash
cd c:\FootballIntelligence\frontend
npx tsc --noEmit
```

**Expected outcome:** No TypeScript errors.

**Frontend tests:**
```bash
cd c:\FootballIntelligence\frontend
npm run test
```

**Expected outcome:** All frontend tests pass, including new `matchNormalizer.test.ts` and `Matches.test.tsx`.

**Frontend production build:**
```bash
cd c:\FootballIntelligence\frontend
npm run build
```

**Expected outcome:** Build succeeds with no errors.

---

## Summary

This plan implements the league-first loading flow and fixes the team name normalization bug:

1. **Backend:** Competition endpoint already correct — added clarifying comment
2. **Frontend types:** Added `CompetitionResponse` and `CompetitionListResponse`
3. **API client:** Added `getCompetitions()` using existing request infrastructure
4. **LeagueSelector component:** New component following TUTAR X visual language
5. **Matches.tsx refactor:** League-first loading with duplicate request protection
6. **Team normalization fix:** NEVER display raw IDs as team names
7. **Team normalization tests:** 8 regression tests covering all edge cases
8. **Matches page tests:** 9 regression tests for league-first flow and duplicate prevention
9. **Backend tests:** 6 tests for competition endpoint structure and flags
10. **Final verification:** All tests pass, TypeScript compiles, production build succeeds

**Verification commands recap:**
```bash
# Backend
cd c:\FootballIntelligence\backend
python -m pytest tests/ -v

# Frontend
cd c:\FootballIntelligence\frontend
npx tsc --noEmit
npm run test
npm run build
```

All changes preserve the existing architecture, follow AGENTS.md rules, and maintain the TUTAR X visual language.

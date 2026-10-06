# Implementation Plan: FotMob Match Detail Normalization Fix

## Problem Summary

The FotMob provider's `_normalize_match()` method in `backend/app/providers/fotmob.py` is parsing team data from incorrect response keys, causing the prediction endpoint to return 404 for prefixed IDs like `fotmob_5181855`.

**Current buggy code (lines 401-402):**
```python
home_team = data.get("home") or data.get("homeTeam") or {}
away_team = data.get("away") or data.get("awayTeam") or {}
```

**Actual FotMob matchDetails response structure:**
```json
{
  "general": {
    "matchId": "5181855",
    "leagueId": 920743,
    "leagueName": "UEFA Nations League A Grp. 3",
    "matchRound": "4",
    "homeTeam": {"name": "Croatia", "id": 10155},
    "awayTeam": {"name": "Spain", "id": 6720},
    "matchTimeUTCDate": "2026-10-06T18:45:00.000Z"
  },
  "header": {
    "teams": [
      {"name": "Croatia", "id": 10155, "score": 0},
      {"name": "Spain", "id": 6720, "score": 0}
    ],
    "status": {
      "utcTime": "2026-10-06T18:45:00.000Z",
      "started": false,
      "cancelled": false,
      "finished": false
    }
  }
}
```

## Investigation Summary

### Current Implementation Analysis

**File:** `backend/app/providers/fotmob.py`

**Current `_normalize_match()` method (lines 336-495):**
- Line 401-402: Incorrectly reads `data.get("home")` and `data.get("away")` (these keys don't exist in matchDetails)
- Line 357-379: Existing scheduled time parsing with fallbacks: `status.utcTime` → `startTime` → `time` → `kickoff` → `date`
- Line 419-423: Existing score fallbacks: team object scores → `data["score"]` → `data.get("homeScore")`
- Line 426-437: Existing competition extraction with league_context support and `data.get("leagueId")` fallback
- Line 440-444: Existing minute extraction from `data["minute"]` or `status_data["minute"]`
- Line 492: Existing round fallback: `data.get("round") or data.get("matchday")`

**Schema:** `backend/app/providers/models.py` (lines 97-141)

`ProviderMatch` has **required** fields (lines 113-116):
```python
home_team_id: str  # REQUIRED, not Optional
home_team_name: str  # REQUIRED, not Optional
away_team_id: str  # REQUIRED, not Optional
away_team_name: str  # REQUIRED, not Optional
```

**Error handling:** `backend/app/providers/exceptions.py`

Provider exceptions for signaling unavailable data:
- `ProviderInvalidDataError` - for missing required fields or unparseable data
- Provider methods can return `None` for missing resources
- Pydantic validation will raise `ValidationError` if required fields are missing

**Adapter routing:** `backend/app/providers/adapter.py` (lines 321-380)

`ProviderManagerAdapter.get_match()`:
- Lines 333-368: Handles prefixed IDs like `fotmob_5181855` by parsing the prefix and routing to specific provider
- Line 351: Calls `provider.get_match(source_id)` directly with numeric ID `"5181855"`
- Lines 370-377: Falls back to `ProviderManager` routing if direct call fails or prefix is invalid
- Line 423: Maps `ProviderMatch` to domain `Match` with ID format `{provider}_{source_id}`

**Prediction endpoint:** `backend/app/api/v1/endpoints/matches.py` (lines 333-417)

- Line 347: Calls `provider.get_match(match_id)` with full prefixed ID
- Lines 351-356: Returns 404 if `match is None`

**League-list normalization:** `backend/app/providers/fotmob.py` (lines 563-605)

`get_matches_by_date()`:
- Lines 589-596: Iterates through `data["leagues"]` and extracts `league.get("matches", [])`
- Line 594: Passes `league_context=league` to `_normalize_match()`
- Preserves existing league-list parsing - **must not break**

### Existing Test Infrastructure

**FotMob provider tests:** `backend/tests/providers/test_fotmob_live.py`
- Real API integration tests (not mocked)
- Pattern: create provider, call methods, assert structure

**Multi-provider tests:** `backend/tests/test_providers_multi.py` (lines 1050-1400+)
- Uses `respx.mock` for HTTP mocking
- Pattern: mock HTTP response, call provider method, assert normalized result
- Existing FotMob tests use old incorrect schema (will need updating)

**Adapter prefixed ID tests:** `backend/tests/test_adapter_prefixed_ids.py`
- Lines 48-75: `test_prefixed_fotmob_id_routes_to_fotmob_provider` - mocks provider and verifies routing
- Pattern: Mock provider with AsyncMock, create adapter, verify provider called with numeric ID

**Prediction API tests:** `backend/tests/test_api_matches.py` (lines 328-522)
- Lines 331-337: `test_get_prediction_returns_200` - tests prediction endpoint
- Line 493: `test_get_prediction_404_for_invalid_match` - tests 404 response

**Test commands:**
- Backend: `cd c:/FootballIntelligence/backend && python -m pytest [test_file] -v`
- Frontend type-check: `cd c:/FootballIntelligence/frontend && npm run type-check`
- Frontend build: `cd c:/FootballIntelligence/frontend && npm run build`

## Implementation Plan

### Step 1: Update `_normalize_match()` to use correct FotMob response structure

**Files to modify:** `backend/app/providers/fotmob.py`

**Changes required:**

Replace lines 401-420 (team extraction and score parsing) with:

```python
# Parse teams - FotMob matchDetails structure
# Priority 1: general.homeTeam / general.awayTeam
# Priority 2: header.teams[0] / header.teams[1]
home_team = None
away_team = None
home_team_id = None
away_team_id = None
home_team_name = ""
away_team_name = ""

# Try general.homeTeam / awayTeam first (matchDetails primary structure)
general_data = data.get("general") or {}
if isinstance(general_data, dict):
    home_team = general_data.get("homeTeam")
    away_team = general_data.get("awayTeam")

# Fallback to header.teams if general not available (match list structure)
if not home_team or not away_team:
    header_data = data.get("header") or {}
    if isinstance(header_data, dict):
        teams = header_data.get("teams", [])
        if isinstance(teams, list) and len(teams) >= 2:
            home_team = teams[0]
            away_team = teams[1]

# Fallback to old structure for backward compatibility with other endpoints
if not home_team:
    home_team = data.get("home") or data.get("homeTeam") or {}
if not away_team:
    away_team = data.get("away") or data.get("awayTeam") or {}

# Extract team IDs and names
if isinstance(home_team, dict):
    home_team_id = home_team.get("id")
    if home_team_id is not None:
        home_team_id = str(home_team_id)
    home_team_name = home_team.get("longName") or home_team.get("name", "")
else:
    home_team_name = str(home_team) if home_team else ""

if isinstance(away_team, dict):
    away_team_id = away_team.get("id")
    if away_team_id is not None:
        away_team_id = str(away_team_id)
    away_team_name = away_team.get("longName") or away_team.get("name", "")
else:
    away_team_name = str(away_team) if away_team else ""

# DATA INTEGRITY CHECK: If no valid team IDs, raise ProviderInvalidDataError
# Do NOT fabricate team IDs - fail safely
if not home_team_id or not away_team_id:
    raise ProviderInvalidDataError(
        provider_name=self.PROVIDER_NAME,
        operation="normalize_match",
        message=f"Missing required team IDs in match data (match_id: {data.get('id') or data.get('matchId', 'unknown')})"
    )

# Parse scores
# Priority 1: header.teams[0].score / header.teams[1].score
# Priority 2: team object scores (for backward compatibility)
# Priority 3: existing fallbacks
home_score = None
away_score = None

# Try header.teams scores first (most reliable for matchDetails)
header_data = data.get("header") or {}
if isinstance(header_data, dict):
    teams = header_data.get("teams", [])
    if isinstance(teams, list) and len(teams) >= 2:
        home_score = teams[0].get("score")
        away_score = teams[1].get("score")

# Fallback: check team objects (for backward compatibility)
if home_score is None and isinstance(home_team, dict):
    home_score = home_team.get("score")
if away_score is None and isinstance(away_team, dict):
    away_score = away_team.get("score")

# Fallback: check for separate score object (existing logic preserved)
if home_score is None and "score" in data:
    home_score = data["score"].get("home")
    away_score = data["score"].get("away")
elif home_score is None:
    home_score = data.get("homeScore") or data.get("home_score")
    away_score = data.get("awayScore") or data.get("away_score")
```

Update lines 426-437 (competition extraction) to support `general.leagueId`:

```python
# Parse competition - use league context if provided, otherwise from match data
if league_context:
    competition_id = str(league_context.get("primaryId")) if league_context.get("primaryId") else str(league_context.get("id")) if league_context.get("id") else None
    competition_name = league_context.get("name")
else:
    # Try general.leagueId / leagueName first (matchDetails structure)
    general_data = data.get("general") or {}
    if isinstance(general_data, dict) and general_data.get("leagueId"):
        competition_id = str(general_data["leagueId"])
        competition_name = general_data.get("leagueName")
    else:
        # Fallback to existing logic
        league_data = data.get("league") or data.get("competition") or {}
        if isinstance(league_data, dict):
            competition_id = str(league_data.get("id")) if league_data.get("id") else None
            competition_name = league_data.get("name")
        else:
            # Final fallback: top-level leagueId
            league_id = data.get("leagueId")
            competition_id = str(league_id) if league_id else None
            competition_name = str(league_data) if league_data else None
```

Update line 357 (scheduled time parsing) to prioritize `general.matchTimeUTCDate`:

```python
# Parse scheduled time
# Priority 1: general.matchTimeUTCDate (matchDetails primary field)
# Priority 2-N: existing fallbacks preserved
scheduled_at = now
general_data = data.get("general") or {}

# Try general.matchTimeUTCDate first
if isinstance(general_data, dict) and "matchTimeUTCDate" in general_data:
    try:
        scheduled_at = datetime.fromisoformat(general_data["matchTimeUTCDate"].replace("Z", "+00:00"))
    except:
        pass

# Existing fallback logic preserved
if scheduled_at == now:
    status_data = data.get("status") or {}
    # Try status.utcTime first (existing logic)
    if isinstance(status_data, dict) and "utcTime" in status_data:
        try:
            scheduled_at = datetime.fromisoformat(status_data["utcTime"].replace("Z", "+00:00"))
        except:
            pass

    # Fallback to other time fields (existing logic preserved)
    if scheduled_at == now:
        scheduled_str = (
            data.get("startTime") or
            data.get("time") or
            data.get("kickoff") or
            data.get("date")
        )
        if scheduled_str:
            try:
                # Try parsing as ISO format
                scheduled_at = datetime.fromisoformat(scheduled_str.replace("Z", "+00:00"))
            except:
                try:
                    # Try parsing as timestamp (milliseconds)
                    timestamp_ms = int(scheduled_str) if isinstance(scheduled_str, (int, str)) else scheduled_str
                    scheduled_at = datetime.fromtimestamp(timestamp_ms / 1000, tz=timezone.utc)
                except:
                    pass
```

Update line 492 (match round) to support `general.matchRound`:

```python
# Match round
# Priority 1: general.matchRound
# Priority 2: existing fallbacks
match_round = None
general_data = data.get("general") or {}
if isinstance(general_data, dict) and "matchRound" in general_data:
    try:
        match_round = int(general_data["matchRound"])
    except (ValueError, TypeError):
        match_round = None

# Fallback to existing logic
if match_round is None:
    match_round = data.get("round") or data.get("matchday")

# Use match_round in ProviderMatch instantiation (line 495)
round=match_round,
```

**Verify:** Read the complete method first, then apply changes preserving all existing fallback logic.

**Files:** `backend/app/providers/fotmob.py`

**Verification command:**
```bash
cd c:/FootballIntelligence/backend
python -m pytest tests/providers/test_fotmob_live.py -v
```

Expected: Existing tests should still pass (they use real API which may return various structures).

---

### Step 2: Add regression tests for FotMob normalization

**Files to create/modify:** `backend/tests/providers/test_fotmob_normalization.py` (new file)

**Test cases required:**

1. **Test real matchDetails structure (match 5181855):**
   - Mock FotMob API response with exact confirmed structure
   - Assert `home_team_id == "10155"`, `away_team_id == "6720"`
   - Assert `home_team_name == "Croatia"`, `away_team_name == "Spain"`
   - Assert `competition_id == "920743"`, `competition_name == "UEFA Nations League A Grp. 3"`
   - Assert `scheduled_at` parsed from `general.matchTimeUTCDate`
   - Assert `round == 4` from `general.matchRound`

2. **Test header.teams fallback:**
   - Mock response with `header.teams` but no `general.homeTeam/awayTeam`
   - Assert team IDs and names extracted from `header.teams[0]` and `header.teams[1]`

3. **Test score extraction from header.teams:**
   - Mock response with scores in `header.teams[0].score` and `header.teams[1].score`
   - Assert scores correctly extracted

4. **Test malformed data (no valid team IDs):**
   - Mock response with neither `general.homeTeam/awayTeam` nor valid `header.teams`
   - Assert `ProviderInvalidDataError` raised
   - Assert error message contains "Missing required team IDs"

5. **Test backward compatibility with old structure:**
   - Mock response with old `data.home` / `data.away` structure (for match lists)
   - Assert normalization still works

6. **Test league_context preservation:**
   - Call `_normalize_match()` with `league_context` parameter
   - Assert `competition_id` and `competition_name` come from league_context, not general data

**Pattern to follow (from test_providers_multi.py):**
```python
import pytest
import respx
import httpx
from datetime import datetime, date
from app.providers.fotmob import FotMobFootballProvider
from app.providers.models import ProviderMatch
from app.providers.exceptions import ProviderInvalidDataError
from app.domain.enums import MatchStatus

@pytest.fixture
def provider():
    return FotMobFootballProvider(
        base_url="https://www.fotmob.com",
        timeout_seconds=10.0,
        retry_count=1
    )

@pytest.mark.asyncio
@respx.mock
async def test_fotmob_matchdetails_real_structure(provider):
    """Test normalization of confirmed FotMob matchDetails structure (match 5181855)."""
    match_id = "5181855"
    
    # Confirmed real FotMob response structure
    mock_response = {
        "general": {
            "matchId": "5181855",
            "leagueId": 920743,
            "leagueName": "UEFA Nations League A Grp. 3",
            "matchRound": "4",
            "homeTeam": {"name": "Croatia", "id": 10155},
            "awayTeam": {"name": "Spain", "id": 6720},
            "matchTimeUTCDate": "2026-10-06T18:45:00.000Z"
        },
        "header": {
            "teams": [
                {"name": "Croatia", "id": 10155, "score": 0},
                {"name": "Spain", "id": 6720, "score": 0}
            ],
            "status": {
                "utcTime": "2026-10-06T18:45:00.000Z",
                "started": False,
                "cancelled": False,
                "finished": False
            }
        }
    }
    
    respx.get(f"{provider.base_url}/api/data/matchDetails").mock(
        return_value=httpx.Response(200, json=mock_response)
    )
    
    # Call provider
    match = await provider.get_match(match_id)
    
    # Assertions
    assert match is not None
    assert match.provider == "fotmob"
    assert match.source_id == "5181855"
    assert match.home_team_id == "10155"
    assert match.home_team_name == "Croatia"
    assert match.away_team_id == "6720"
    assert match.away_team_name == "Spain"
    assert match.competition_id == "920743"
    assert match.competition_name == "UEFA Nations League A Grp. 3"
    assert match.round == 4
    assert match.home_score == 0
    assert match.away_score == 0
    assert match.status == MatchStatus.SCHEDULED
    # Verify scheduled_at parsed from general.matchTimeUTCDate
    assert match.scheduled_at.year == 2026
    assert match.scheduled_at.month == 10
    assert match.scheduled_at.day == 6
```

**Files:** `backend/tests/providers/test_fotmob_normalization.py`

**Verification command:**
```bash
cd c:/FootballIntelligence/backend
python -m pytest tests/providers/test_fotmob_normalization.py -v
```

Expected: All 6 regression tests pass.

---

### Step 3: Update existing FotMob tests that expect old schema

**Files to modify:** `backend/tests/test_providers_multi.py`

**Changes required:**

Lines 1057-1109 (`test_fotmob_get_matches_by_date`):
- Update mock response structure to use `general`/`header` instead of `home`/`away`
- Change from:
  ```python
  "home": {"id": "team_1", "name": "Arsenal"},
  "away": {"id": "team_2", "name": "Liverpool"}
  ```
- To:
  ```python
  "general": {
      "homeTeam": {"id": "team_1", "name": "Arsenal"},
      "awayTeam": {"id": "team_2", "name": "Liverpool"},
      "matchTimeUTCDate": "2024-01-15T15:00:00Z"
  },
  "header": {
      "teams": [
          {"id": "team_1", "name": "Arsenal", "score": 0},
          {"id": "team_2", "name": "Liverpool", "score": 0}
      ]
  }
  ```

Lines 1113-1159 (`test_fotmob_get_match`):
- Update mock response to matchDetails structure with `general` and `header`

**Files:** `backend/tests/test_providers_multi.py`

**Verification command:**
```bash
cd c:/FootballIntelligence/backend
python -m pytest tests/test_providers_multi.py::TestFotMobProvider -v
```

Expected: All FotMob provider tests pass with updated schema.

---

### Step 4: Test real provider call with match 5181855

**Manual verification step:**

Create temporary test script `backend/test_fotmob_real_call.py`:

```python
"""Manual test: real FotMob API call for match 5181855."""
import asyncio
from app.providers.fotmob import FotMobFootballProvider

async def test_real_call():
    provider = FotMobFootballProvider(
        base_url="https://www.fotmob.com",
        timeout_seconds=10.0,
        retry_count=1
    )
    
    try:
        print("Calling FotMob API for match 5181855...")
        match = await provider.get_match("5181855")
        
        if match is None:
            print("❌ FAILED: Provider returned None")
            return False
        
        print(f"✓ Provider: {match.provider}")
        print(f"✓ Source ID: {match.source_id}")
        print(f"✓ Home Team ID: {match.home_team_id}")
        print(f"✓ Home Team Name: {match.home_team_name}")
        print(f"✓ Away Team ID: {match.away_team_id}")
        print(f"✓ Away Team Name: {match.away_team_name}")
        print(f"✓ Competition ID: {match.competition_id}")
        print(f"✓ Competition Name: {match.competition_name}")
        print(f"✓ Round: {match.round}")
        print(f"✓ Scheduled At: {match.scheduled_at}")
        
        # Verify expected values
        assert match.provider == "fotmob"
        assert match.source_id == "5181855"
        assert match.home_team_id == "10155"
        assert match.home_team_name == "Croatia"
        assert match.away_team_id == "6720"
        assert match.away_team_name == "Spain"
        assert match.competition_id == "920743"
        
        print("\n✅ SUCCESS: Real provider call returned valid ProviderMatch")
        return True
        
    except Exception as e:
        print(f"❌ FAILED: {type(e).__name__}: {e}")
        return False
    finally:
        await provider.close()

if __name__ == "__main__":
    success = asyncio.run(test_real_call())
    exit(0 if success else 1)
```

**Verification command:**
```bash
cd c:/FootballIntelligence/backend
python test_fotmob_real_call.py
```

Expected output:
```
Calling FotMob API for match 5181855...
✓ Provider: fotmob
✓ Source ID: 5181855
✓ Home Team ID: 10155
✓ Home Team Name: Croatia
✓ Away Team ID: 6720
✓ Away Team Name: Spain
✓ Competition ID: 920743
✓ Competition Name: UEFA Nations League A Grp. 3
✓ Round: 4
✓ Scheduled At: 2026-10-06 18:45:00+00:00

✅ SUCCESS: Real provider call returned valid ProviderMatch
```

Delete the temporary test script after verification.

---

### Step 5: Test API endpoints with prefixed ID

**Manual API testing:**

Start backend server:
```bash
cd c:/FootballIntelligence/backend
.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

Test match endpoint:
```bash
# In new terminal
curl http://localhost:8000/api/v1/matches/fotmob_5181855
```

Expected: HTTP 200 with valid match JSON containing Croatia vs Spain.

Test prediction endpoint:
```bash
curl http://localhost:8000/api/v1/matches/fotmob_5181855/prediction
```

Expected: HTTP 200 with prediction JSON, OR legitimate prediction response (not 404).

Test matches list endpoint (regression check):
```bash
curl "http://localhost:8000/api/v1/matches?from_date=2026-10-06"
```

Expected: HTTP 200 with matches list (existing behavior intact).

**Automated test verification:**

**Verification command:**
```bash
cd c:/FootballIntelligence/backend
python -m pytest tests/test_api_matches.py::TestMatchDetailEndpoint -v
python -m pytest tests/test_api_matches.py::TestMatchPredictionEndpoint::test_get_prediction_404_for_invalid_match -v
```

Expected: All match API tests pass, 404 test still validates invalid IDs return 404.

---

### Step 6: Run full test suite

**Backend tests:**

```bash
cd c:/FootballIntelligence/backend

# 1. New FotMob normalization regression tests
python -m pytest tests/providers/test_fotmob_normalization.py -v

# 2. Existing FotMob provider tests
python -m pytest tests/providers/test_fotmob_live.py -v

# 3. Provider manager tests (if exists)
python -m pytest tests/test_providers_manager.py -v 2>$null ; if ($?) { echo "Provider manager tests passed" } else { echo "No provider manager tests found" }

# 4. Adapter prefixed-ID tests
python -m pytest tests/test_adapter_prefixed_ids.py -v

# 5. Prediction API tests
python -m pytest tests/test_api_matches.py::TestMatchPredictionEndpoint -v

# 6. Multi-provider tests (FotMob subset)
python -m pytest tests/test_providers_multi.py::TestFotMobProvider -v

# 7. Full backend test suite (regression check)
python -m pytest tests/ -v --tb=short
```

Expected: All tests pass. No regressions in unrelated functionality.

**Backend type checking (if mypy configured):**

```bash
cd c:/FootballIntelligence/backend
python -m mypy app/providers/fotmob.py 2>$null ; if ($?) { echo "Type check passed" } else { echo "No mypy configured" }
```

Expected: No type errors (or skip if mypy not configured).

---

### Step 7: Frontend verification

**Frontend type-check:**

```bash
cd c:/FootballIntelligence/frontend
npm run type-check
```

Expected: 0 TypeScript errors (no frontend changes, but verify no regressions).

**Frontend build:**

```bash
cd c:/FootballIntelligence/frontend
npm run build
```

Expected: Build succeeds without errors.

---

## Success Criteria Checklist

- [ ] `_normalize_match()` updated to parse `general.homeTeam` / `general.awayTeam` as primary source
- [ ] `_normalize_match()` falls back to `header.teams[0]` / `header.teams[1]` when general not available
- [ ] `_normalize_match()` preserves backward compatibility with old `data.home` / `data.away` structure
- [ ] `_normalize_match()` prioritizes `general.matchTimeUTCDate` for scheduled time
- [ ] `_normalize_match()` supports `general.leagueId` and `general.leagueName` for competition
- [ ] `_normalize_match()` supports `general.matchRound` for match round
- [ ] `_normalize_match()` raises `ProviderInvalidDataError` when no valid team IDs exist (no fabrication)
- [ ] `home_team_id` and `away_team_id` remain required `str` fields (not Optional)
- [ ] Regression test added for confirmed match 5181855 structure
- [ ] Regression test added for header.teams fallback
- [ ] Regression test added for malformed data (no fabrication)
- [ ] Existing FotMob tests updated to use correct schema
- [ ] Real provider call to `get_match("5181855")` returns valid `ProviderMatch` with correct team IDs
- [ ] `GET /api/v1/matches/fotmob_5181855` returns HTTP 200
- [ ] `GET /api/v1/matches/fotmob_5181855/prediction` returns HTTP 200 or legitimate response (not 404)
- [ ] `GET /api/v1/matches?from_date=2026-10-06` still works (existing behavior intact)
- [ ] All backend tests pass
- [ ] Frontend type-check passes
- [ ] Frontend build succeeds
- [ ] No regressions in prediction models, PredictionService, ensemble, calibration, or frontend design

---

## Files Modified

1. `backend/app/providers/fotmob.py` - `_normalize_match()` method updated
2. `backend/tests/providers/test_fotmob_normalization.py` - new regression tests (6 test cases)
3. `backend/tests/test_providers_multi.py` - existing FotMob tests updated to use correct schema

## Files Created

1. `backend/tests/providers/test_fotmob_normalization.py` - dedicated regression test file

## Files NOT Modified

- Seven prediction models (Poisson, Elo, etc.)
- `backend/app/prediction/service.py` (PredictionService)
- Ensemble, calibration, Smart Market Selector logic
- MENSIONE Pick logic
- Shot intelligence, common-opponent intelligence
- Frontend design, components, or pages
- Provider architecture (ProviderMatch schema, adapter, manager)
- `backend/app/providers/models.py` (ProviderMatch schema remains unchanged)

---

## Data Integrity Rule Implementation

**Rule:** REAL DATA > NULL/UNAVAILABLE > FABRICATED DATA

**Implementation:**

In `_normalize_match()` after team extraction (Step 1):

```python
# DATA INTEGRITY CHECK: If no valid team IDs, raise ProviderInvalidDataError
# Do NOT fabricate team IDs - fail safely
if not home_team_id or not away_team_id:
    raise ProviderInvalidDataError(
        provider_name=self.PROVIDER_NAME,
        operation="normalize_match",
        message=f"Missing required team IDs in match data (match_id: {data.get('id') or data.get('matchId', 'unknown')})"
    )
```

This ensures:
1. If real team IDs exist → use them
2. If no real team IDs exist → raise error (no fabrication)
3. ProviderMatch schema keeps `home_team_id: str` and `away_team_id: str` as required
4. Calling code receives either valid data or an exception (never fake data)

---

## Notes

- This is a **targeted bug fix**, not a redesign
- All existing fallback logic is **preserved** to avoid breaking other FotMob endpoints
- The fix adds **primary** extraction paths for matchDetails while keeping **fallback** paths for match lists
- League-list normalization (`get_matches_by_date`) continues to work because it passes `league_context` parameter
- The fix follows the project's data integrity rule: fail safely rather than fabricate data

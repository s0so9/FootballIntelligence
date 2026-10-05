# CRITICAL CORRECTION: Local Ryzellx Endpoint Status

**Date**: 2026-10-05  
**Phase**: 10A Provider Validation

---

## Local Ryzellx Service (ACTIVELY RUNNING)

The plan correctly identifies that the **public Ryzellx endpoint** (https://football-live-api.vercel.app) returns **402 Payment Required**.

However, there is a **LOCAL Ryzellx service** running successfully that must be used for all Phase 10A validation:

### Base URL
```
http://localhost:3001
```

### Validated Endpoints (Independently Confirmed Working)

1. **Health Check**
   ```
   GET http://localhost:3001/api/health
   Response: {"success": true, "source": "fotmob"}
   ```

2. **Live Matches**
   ```
   GET http://localhost:3001/api/matches/live?timezone=Europe/Istanbul&ccode3=TUR
   Response: {"success": true, "source": "fotmob", "total": 0}
   Note: Empty result is REAL data (no live matches at that time), NOT fabricated
   ```

3. **Match Statistics**
   ```
   GET http://localhost:3001/api/match/5795450/statistics
   Response: {"success": true, "source": "fotmob", ...}
   ```

### Additional Endpoints to Validate in Phase 10A

These endpoints exist in RyzellxFootballProvider and must be tested against localhost:3001:

- `GET /api/matches/date/:date` → `get_matches_by_date()`
- `GET /api/matches/range?from=&to=` → `get_matches_by_range()`
- `GET /api/match/:id` → `get_match()`
- `GET /api/match/:id/events` → (if implemented)
- `GET /api/match/:id/lineups` → (if implemented)
- `GET /api/match/:id/shotmap` → (if implemented)
- `GET /api/match/:id/heatmap` → (if implemented)
- `GET /api/match/:id/odds` → (if implemented)

---

## Implementation Changes Required

### FEAT-001: Capability Detection

**DO NOT classify Ryzellx as globally PAYMENT_REQUIRED**

Instead, distinguish between:
- **Public endpoint status**: 402 Payment Required (https://football-live-api.vercel.app)
- **Local endpoint status**: AVAILABLE (http://localhost:3001)

When implementing `RyzellxFootballProvider.detect_capabilities()`:
```python
# Test against local endpoint
base_url = "http://localhost:3001"  # or from config
# Test actual endpoints and record real status codes
```

Update `ProviderCapabilityMatrix` model to include:
- `public_endpoint_status: Optional[str]` - status of public/deployed endpoint
- `local_endpoint_status: Optional[str]` - status of local development endpoint
- `recommended_base_url: Optional[str]` - which URL to use (prefer local if available)

### Configuration

Verify `backend/app/config.py` Settings class:
```python
class Settings(BaseSettings):
    # ...
    ryzellx_base_url: str = "http://localhost:3001"  # Should default to local for dev
    # ...
```

If currently set to Vercel URL, change default to localhost:3001 for development.

### FEAT-004: API Integration Verification

Phase 10A must verify the **complete integration chain**:

```
Frontend Date Range Request
  ↓
GET /api/v1/matches?from_date=2026-10-05&to_date=2026-10-12&status=scheduled
  ↓
Backend matches.py endpoint
  ↓
ProviderManagerAdapter
  ↓
ProviderManager
  ↓
RyzellxFootballProvider.get_matches_by_range()
  ↓
HTTP GET http://localhost:3001/api/matches/range?from=2026-10-05&to=2026-10-12
  ↓
Local Ryzellx Service
  ↓
Returns real match data (or empty list if no matches)
```

The infrastructure already exists in:
- `backend/app/providers/ryzellx.py` - `get_matches_by_range()` method
- `backend/app/providers/manager.py` - ProviderManager orchestration
- `backend/app/api/v1/endpoints/matches.py` - existing matches endpoint

Verify this chain works when `use_real_providers=True`.

---

## Development Mode Clarification

### Keep DevelopmentProvider

**DO NOT remove** `backend/app/providers/development.py`

DevelopmentProvider is needed for:
- Unit tests with predictable fixtures
- Demo/example data (dev_match_002, etc.)
- Frontend development without external dependencies

### use_real_providers Flag

**Current default**: `use_real_providers: bool = False`  
**Keep this default** until Phase 10A validation is complete.

**When enabled** (`use_real_providers=True`):
- Must actually reach local Ryzellx at `http://localhost:3001`
- Must use real provider cascade order: fotmob → sofascore → ryzellx → openligadb
- Must return real data (or empty results), never fabricated data

### Real Provider Mode Testing

After Phase 10A implementation, verify real provider mode:

```bash
# Start local Ryzellx service (already running)
# In another terminal:
cd backend
export USE_REAL_PROVIDERS=true
python -m uvicorn app.main:app --reload

# Test endpoint
curl "http://localhost:8000/api/v1/matches?from_date=2026-10-05&to_date=2026-10-12"
# Should return real data from http://localhost:3001
```

---

## REAL DATA > NULL > FABRICATED DATA

This is the **CRITICAL DATA RULE** for Phase 10A and all subsequent phases.

### Correct Response When No Live Matches

If local Ryzellx returns 0 live matches:

```json
{
  "matches": [],
  "provider_health": {
    "ryzellx": {
      "is_available": true,
      "last_check_utc": "2026-10-05T14:30:00Z",
      "consecutive_failures": 0
    }
  },
  "data_quality": {
    "total_matches": 0,
    "providers_checked": ["fotmob", "sofascore", "ryzellx"]
  },
  "timestamp": "2026-10-05T14:30:00Z",
  "provider_used": "ryzellx"
}
```

### INCORRECT Response (DO NOT DO THIS)

```json
{
  "matches": [
    {
      "match_id": "fake_001",
      "home_team": "Example FC",
      // ... fabricated data to "show something"
    }
  ]
}
```

**Never create fake matches just to make the UI look populated.**

Empty lists with accurate provider health status are correct responses.

---

## PROGRESS.md Documentation Requirements

After Phase 10A implementation, `docs/PROGRESS.md` must include:

### Provider Validation Results

**Ryzellx (PRIMARY)**
- Public endpoint: https://football-live-api.vercel.app → 402 Payment Required
- Local endpoint: http://localhost:3001 → AVAILABLE
- Validated endpoints:
  - `/api/health` ✓
  - `/api/matches/live` ✓
  - `/api/match/{id}/statistics` ✓
  - `/api/matches/date/:date` [test result]
  - `/api/matches/range` [test result]
- Capabilities: [list from actual tests]
- Recommendation: Use localhost:3001 for development

**FotMob (LIVE/FAST)**
- Endpoint: https://www.fotmob.com/api → [actual test result]
- Known issue: `/api/matches` returns 404 on some queries
- Capabilities: [list from actual tests]
- Status: [AVAILABLE/PARTIAL/UNAVAILABLE]

**SofaScore (MATCH STATISTICS)**
- Endpoint: https://api.sofascore.com → [actual test result]
- Capabilities: [list from actual tests]
- Status: [AVAILABLE/PARTIAL/UNAVAILABLE]

**OpenLigaDB (FALLBACK)**
- Endpoint: https://api.openligadb.de → [actual test result]
- Capabilities: match_details (NO xG - authoritative), standings
- Status: [AVAILABLE/PARTIAL/UNAVAILABLE]

### Integration Verification

- Frontend → `/api/v1/matches` → RyzellxProvider → `localhost:3001` ✓/✗
- Live matches endpoint → `/api/v1/matches/live` → Provider cascade ✓/✗
- Provider health monitoring → All providers checked ✓/✗
- Spatial data contract → Models defined, all fields null (correct) ✓/✗

### Known Limitations

- No providers currently supply spatial data (player positions, ball tracking)
- Spatial fields in ProviderLiveMatch remain null (correct - not fabricated)
- Live Radar UI not implemented (deferred to Phase 10)
- Real provider mode requires local Ryzellx service at localhost:3001

### Next Steps

- Phase 10: Advanced Football Intelligence (Live Radar UI)
- Real-time spatial data integration (when providers supply it)
- Enhanced prediction models with live context

---

## Summary for Implementation

1. **Test against localhost:3001** for all Ryzellx validation
2. **Do NOT classify Ryzellx as globally unavailable** due to public endpoint 402
3. **Verify complete integration chain** from frontend through to local Ryzellx
4. **Keep DevelopmentProvider** for tests/fixtures
5. **Default use_real_providers=False** until validation complete
6. **Document local vs public endpoint status** in PROGRESS.md
7. **REAL DATA > NULL > FABRICATED DATA** always

---

## Questions for Clarification

If any of these points are unclear during implementation:

1. Should `ryzellx_base_url` in config.py default to localhost:3001?
2. Are there environment-specific configs (dev/staging/prod) for provider URLs?
3. Should capability detection test both public and local endpoints?
4. Is there a health check endpoint we should use instead of calling get_live_matches()?

These can be addressed during implementation based on actual codebase patterns.

---

**This correction supersedes any conflicting information in plan.md regarding Ryzellx endpoint status.**


---

## FEAT-005: Date Range Integration Validation (REQUIRED FOR PHASE 10A COMPLETION)

**CRITICAL**: Phase 10A is NOT complete merely because `/api/v1/matches/live` exists.

The existing MENSIONE match-list integration must be **explicitly validated** and **regression tested**.

### Current Frontend Integration

The frontend currently requests date-range matches:

```
GET /api/v1/matches?from_date=2026-10-05&to_date=2026-10-12&status=scheduled
```

### Expected Integration Path

```
Frontend
  ↓
GET /api/v1/matches (backend/app/api/v1/endpoints/matches.py)
  ↓
ProviderManagerAdapter.get_matches()
  ↓
ProviderManager (range method or date iteration)
  ↓
RyzellxFootballProvider.get_matches_by_range()
  ↓
HTTP GET http://localhost:3001/api/matches/range?from=2026-10-05&to=2026-10-12
  ↓
Local Ryzellx Service
  ↓
Real match data (or empty list if no matches)
```

### Known Implementation

**RyzellxFootballProvider** already has:
```python
async def get_matches_by_range(
    self,
    start_date: date,
    end_date: date
) -> List[ProviderMatch]:
    """Get matches in date range."""
    # Exists at backend/app/providers/ryzellx.py
```

### Integration Issues to Investigate

1. **Does ProviderManagerAdapter handle date ranges?**
   - Or does it only call `get_matches_by_date()` for single days?
   - If it iterates day-by-day, does it properly aggregate results?

2. **Does ProviderManager have a range method?**
   - Check for `get_matches_by_range()` or similar
   - If missing, add integration to call provider's range method

3. **Is the adapter called from `/api/v1/matches` endpoint?**
   - Verify the endpoint properly passes from_date, to_date, status params
   - Check query parameter parsing and validation

4. **Status filtering implementation**
   - Does filtering happen at provider level or adapter level?
   - Is `status=scheduled` properly applied?

### Files to Inspect

1. `backend/app/api/v1/endpoints/matches.py` - existing matches endpoint
2. `backend/app/providers/manager.py` - ProviderManager implementation
3. `backend/app/services/provider_adapter.py` or similar - adapter layer (if exists)
4. Look for any middleware/service layer between API and providers

### Implementation Requirements

**If adapter/manager currently rejects or ignores multi-day ranges:**
- Fix the integration to properly call `get_matches_by_range()`
- Do NOT iterate day-by-day if a range method exists
- Preserve backward compatibility for single-day queries

**If integration is broken or missing:**
- Wire the complete path from frontend through to Ryzellx
- Add proper error handling and fallback behavior
- Document the integration in code comments

### Acceptance Criteria (Phase 10A Completion Gates)

Phase 10A is **NOT COMPLETE** until ALL of these are verified:

1. ✓ **Real-provider mode can query a date range**
   - Set `use_real_providers=True`
   - Call `GET /api/v1/matches?from_date=X&to_date=Y`
   - Verify real data returned (or empty list if none)

2. ✓ **Ryzellx local `/api/matches/range` is actually reached**
   - Add debug logging or verify in Ryzellx service logs
   - Confirm HTTP request hits `localhost:3001/api/matches/range`

3. ✓ **Scheduled matches are returned when real upstream data exists**
   - If Ryzellx returns matches, frontend receives them
   - Data structure matches expected frontend schema

4. ✓ **Status filtering works**
   - `status=scheduled` returns only scheduled matches
   - `status=live` returns only live matches (if any)
   - No status param returns all matches

5. ✓ **DevelopmentProvider remains available for tests**
   - `use_real_providers=False` still uses DevelopmentProvider
   - Existing tests still pass
   - dev_match_002 and other fixtures still work

6. ✓ **No fake matches are introduced**
   - Empty results when no real data exists
   - REAL DATA > NULL > FABRICATED DATA rule enforced

7. ✓ **Existing frontend `/api/v1/matches` flow remains backward compatible**
   - All existing query parameters still work
   - Response schema unchanged (or extended, not breaking)
   - Frontend continues to function without modifications

8. ✓ **Regression tests for single-day and multi-day queries**
   - Test single day: `from_date=2026-10-05&to_date=2026-10-05`
   - Test multi-day: `from_date=2026-10-05&to_date=2026-10-12`
   - Test with and without status filter
   - Test with `use_real_providers=True` and `False`

### Test File

Create or extend: `backend/tests/api/test_matches_integration.py`

Test scenarios:
```python
@pytest.mark.asyncio
async def test_matches_single_day_query():
    """Test single-day query with real provider."""
    # from_date = to_date

@pytest.mark.asyncio
async def test_matches_multi_day_range():
    """Test multi-day range query with real provider."""
    # from_date < to_date

@pytest.mark.asyncio
async def test_matches_status_filter_scheduled():
    """Test status=scheduled filter."""

@pytest.mark.asyncio
async def test_matches_status_filter_live():
    """Test status=live filter."""

@pytest.mark.asyncio
async def test_matches_real_provider_reaches_ryzellx():
    """Verify actual HTTP request reaches localhost:3001."""
    # Mock httpx to verify URL called

@pytest.mark.asyncio
async def test_matches_development_provider_still_works():
    """Verify use_real_providers=False uses DevelopmentProvider."""

@pytest.mark.asyncio
async def test_matches_empty_result_when_no_data():
    """Verify empty list returned when no matches exist."""
    # Mock Ryzellx returning empty list
    # Verify frontend receives empty list, not fabricated data

@pytest.mark.asyncio
async def test_matches_backward_compatibility():
    """Verify existing query patterns still work."""
    # Test all existing query parameter combinations
```

### Integration Validation Steps

1. **Inspect existing endpoint**
   ```bash
   # Read the current implementation
   cat backend/app/api/v1/endpoints/matches.py
   ```

2. **Check for adapter layer**
   ```bash
   # Find provider adapter/service files
   find backend/app -name "*adapter*" -o -name "*service*" | grep -v __pycache__
   ```

3. **Test with curl (manual verification)**
   ```bash
   # Start backend with real providers enabled
   cd backend
   export USE_REAL_PROVIDERS=true
   python -m uvicorn app.main:app --reload &
   
   # Test single day
   curl "http://localhost:8000/api/v1/matches?from_date=2026-10-05&to_date=2026-10-05"
   
   # Test multi-day range
   curl "http://localhost:8000/api/v1/matches?from_date=2026-10-05&to_date=2026-10-12"
   
   # Test with status filter
   curl "http://localhost:8000/api/v1/matches?from_date=2026-10-05&to_date=2026-10-12&status=scheduled"
   
   # Check Ryzellx was actually called (check its logs)
   ```

4. **Run regression tests**
   ```bash
   pytest backend/tests/api/test_matches_integration.py -v
   ```

### Documentation Required

After validation, document in `docs/PROGRESS.md`:

**Date Range Integration**
- Endpoint: `/api/v1/matches` ✓
- Single-day query: ✓
- Multi-day range query: ✓
- Status filtering: ✓
- Ryzellx integration: localhost:3001/api/matches/range ✓
- DevelopmentProvider fallback: ✓
- Backward compatibility: ✓
- Regression tests: [number] tests passing

### Why This Matters

The `/api/v1/matches/live` endpoint (FEAT-004) is for **live matches only**.

But the frontend **also needs scheduled matches** for the match list view.

Without validating the date-range integration:
- Frontend might continue using DevelopmentProvider only
- Real Ryzellx data never reaches the frontend
- Phase 10A validation would be incomplete
- Integration bugs remain hidden until production

This is **not a redesign** - it's verifying that existing infrastructure actually works with real providers.

### Implementation Priority

This is **FEAT-005** and must be completed **before Phase 10A is declared complete**.

Order of implementation:
1. FEAT-001: Capabilities ✓
2. FEAT-002: Health ✓
3. FEAT-003: Spatial Models ✓
4. FEAT-004: Live Matches Endpoint ✓
5. **FEAT-005: Date Range Integration Validation** ← NEW REQUIREMENT

---

**Summary**: Phase 10A completion requires validating the complete integration chain from frontend date-range queries through to local Ryzellx service, with regression tests confirming backward compatibility and real data flow.

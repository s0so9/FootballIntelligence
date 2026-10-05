# Phase 10A: Integration Specification
## Date Range Match Query Validation

**Status**: REQUIRED FOR PHASE 10A COMPLETION  
**Priority**: CRITICAL  
**Type**: Integration Validation (not redesign)

---

## Current Architecture Understanding

### 1. API Layer: `/api/v1/matches` Endpoint

**File**: `backend/app/api/v1/endpoints/matches.py`

**Current Implementation**:
```python
@router.get("", response_model=MatchListResponse)
async def list_matches(
    from_date: Optional[date] = Query(None),
    to_date: Optional[date] = Query(None),
    status: Optional[str] = Query(None),
    provider: FootballDataProvider = Depends(get_data_provider),
) -> MatchListResponse:
    # Get matches from provider with filters
    matches = provider.get_matches(
        from_date=from_date,
        to_date=to_date,
        status=status,
    )
```

**Status**: ✓ Endpoint already supports date range parameters  
**Behavior**: Delegates to `FootballDataProvider.get_matches()` abstract method

---

### 2. Provider Interface: `FootballDataProvider`

**File**: `backend/app/providers/base.py`

**Interface Definition**:
```python
@abstractmethod
def get_matches(
    self,
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
    status: Optional[str] = None,
) -> List[Match]:
    """Get matches with optional filters."""
    pass
```

**Status**: ✓ Interface already supports date range  
**Contract**: Provider implementations must handle from_date/to_date filtering

---

### 3. DevelopmentProvider Implementation

**File**: `backend/app/providers/development.py`

**Current Implementation**:
```python
def get_matches(
    self,
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
    status: Optional[str] = None,
) -> List[Match]:
    """Get mock matches with optional filters."""
    matches = self._matches.copy()
    
    if from_date:
        matches = [m for m in matches if m.scheduled_at.date() >= from_date]
    
    if to_date:
        matches = [m for m in matches if m.scheduled_at.date() <= to_date]
    
    if status:
        matches = [m for m in matches if m.status.value == status]
    
    return matches
```

**Status**: ✓ DevelopmentProvider correctly handles date ranges  
**Behavior**: In-memory filtering of mock fixtures

---

### 4. Real Provider Dependency Injection

**File**: `backend/app/api/dependencies.py`

**Expected Pattern**:
```python
def get_data_provider() -> FootballDataProvider:
    """Dependency injection for data provider."""
    if settings.use_real_providers:
        return RealProviderAdapter()  # or similar
    else:
        return DevelopmentProvider()
```

**Action Required**: VERIFY THIS FILE EXISTS AND IMPLEMENTS CORRECTLY

---

### 5. Real Provider Adapter/Manager (NEEDS INVESTIGATION)

**Expected Files** (one of these should exist):
- `backend/app/providers/adapter.py`
- `backend/app/providers/real_provider.py`
- `backend/app/services/provider_adapter.py`

**Expected Responsibilities**:
1. Implement `FootballDataProvider` abstract interface
2. Delegate to `ProviderManager` for real data fetching
3. Convert `ProviderMatch` → `Match` domain model
4. Handle date range queries by calling appropriate provider methods

**Critical Implementation**:
```python
class RealProviderAdapter(FootballDataProvider):
    def __init__(self):
        self.manager = ProviderManager(...)
    
    def get_matches(
        self,
        from_date: Optional[date] = None,
        to_date: Optional[date] = None,
        status: Optional[str] = None,
    ) -> List[Match]:
        """Get real matches from provider manager."""
        
        # CRITICAL: Must call get_matches_by_range() when both dates provided
        if from_date and to_date:
            provider_matches = self.manager.get_matches_by_range(
                start_date=from_date,
                end_date=to_date
            )
        elif from_date and not to_date:
            # Single day or iterate from from_date
            provider_matches = self.manager.get_matches_by_date(from_date)
        else:
            # No date filter
            provider_matches = []
        
        # Convert ProviderMatch → Match domain model
        domain_matches = [
            self._convert_provider_match(pm) 
            for pm in provider_matches
        ]
        
        # Apply status filter
        if status:
            domain_matches = [
                m for m in domain_matches 
                if m.status.value == status
            ]
        
        return domain_matches
```

**Action Required**: FIND AND VERIFY THIS ADAPTER EXISTS

---

### 6. ProviderManager Integration

**File**: `backend/app/providers/manager.py`

**Expected Methods**:
- `get_matches_by_date(date_obj: date) -> List[ProviderMatch]` ✓ (already exists)
- `get_matches_by_range(start_date: date, end_date: date) -> List[ProviderMatch]` ❓ (needs verification)

**If get_matches_by_range() doesn't exist**, add it:
```python
async def get_matches_by_range(
    self,
    start_date: date,
    end_date: date
) -> Tuple[List[ProviderMatch], Dict[str, Any]]:
    """Get matches in date range using provider cascade.
    
    Returns:
        Tuple of (matches, metadata)
        - matches: List of ProviderMatch
        - metadata: Dict with 'selected_provider', 'fallback_used', etc.
    """
    for provider_name in self.DATE_RANGE_ORDER:  # e.g., ['ryzellx', 'fotmob']
        provider = self._get_provider(provider_name)
        if not provider:
            continue
        
        try:
            matches = await provider.get_matches_by_range(start_date, end_date)
            return matches, {'selected_provider': provider_name}
        except ProviderError as e:
            logger.warning(f"Provider {provider_name} failed for range query: {e}")
            continue
    
    # All providers failed
    return [], {'selected_provider': None, 'all_failed': True}
```

**Action Required**: ADD THIS METHOD IF MISSING

---

### 7. RyzellxFootballProvider Integration

**File**: `backend/app/providers/ryzellx.py`

**Existing Method** (confirmed from audit):
```python
async def get_matches_by_range(
    self,
    start_date: date,
    end_date: date
) -> List[ProviderMatch]:
    """Get matches in date range."""
    endpoint = "/api/matches/range"
    params = {
        "start": start_date.isoformat(),
        "end": end_date.isoformat()
    }
    data = await self._request("GET", endpoint, params=params)
    # ... normalization ...
```

**Status**: ✓ Method exists and should work  
**Testing Required**: Verify it actually calls `http://localhost:3001/api/matches/range`

---

## Integration Gaps to Address

### Gap 1: Provider Adapter May Not Exist

**Symptom**: `get_data_provider()` might return DevelopmentProvider even when `use_real_providers=True`

**Investigation**:
1. Check if `backend/app/api/dependencies.py` exists
2. Check if real provider adapter class exists
3. Verify dependency injection wiring

**Fix**: Create `RealProviderAdapter` if missing (see template above)

---

### Gap 2: ProviderManager May Not Have get_matches_by_range()

**Symptom**: Even with real provider enabled, date range queries fail or iterate day-by-day

**Investigation**:
1. Check `backend/app/providers/manager.py` for `get_matches_by_range()` method
2. Check if it uses efficient range query or day-by-day iteration

**Fix**: Add `get_matches_by_range()` method if missing (see template above)

---

### Gap 3: Domain Model Conversion May Be Missing

**Symptom**: `ProviderMatch` can't be used directly by API (type mismatch)

**Investigation**:
1. Check if adapter converts `ProviderMatch` → `Match` (domain model from `app.domain.match`)
2. Check field mappings

**Fix**: Implement conversion utility:
```python
def _convert_provider_match(pm: ProviderMatch) -> Match:
    """Convert ProviderMatch to domain Match model."""
    return Match(
        id=pm.source_id,
        competition_id=pm.competition_id,
        season_id=pm.season,
        home_team_id=pm.home_team_id,
        away_team_id=pm.away_team_id,
        scheduled_at=pm.scheduled_at,
        status=pm.status,
        home_score=pm.home_score,
        away_score=pm.away_score,
        # ... map all required fields
    )
```

---

## Verification Steps (FEAT-005)

### Step 1: Locate Provider Adapter
```bash
cd backend
# Find adapter/dependencies files
find app -name "*adapter*" -o -name "*dependencies*" | grep -v __pycache__
```

**Expected**: Find adapter implementation  
**If missing**: Create it as part of FEAT-005

---

### Step 2: Verify ProviderManager Range Method
```bash
cd backend
grep -n "def get_matches_by_range" app/providers/manager.py
```

**Expected**: Method exists  
**If missing**: Add it as part of FEAT-005

---

### Step 3: Test Real Provider Mode Manually
```bash
cd backend
export USE_REAL_PROVIDERS=true
export RYZELLX_BASE_URL=http://localhost:3001
python -m uvicorn app.main:app --reload &

# Wait for startup, then test
curl "http://localhost:8000/api/v1/matches?from_date=2026-10-05&to_date=2026-10-12"
```

**Expected**: Real data from localhost:3001 (or empty list if no matches)  
**If returns dev_match_002**: Real provider mode not working

---

### Step 4: Check Ryzellx Logs
```bash
# In Ryzellx service terminal, look for:
# GET /api/matches/range?start=2026-10-05&end=2026-10-12
```

**Expected**: Request log appears  
**If missing**: Request not reaching Ryzellx

---

### Step 5: Run Integration Tests
```bash
cd backend
pytest tests/api/test_matches_integration.py -v
```

**Expected**: All tests pass  
**Test file**: Create as part of FEAT-005 (see test scenarios in correction doc)

---

## Implementation Checklist for FEAT-005

### Code Changes Required

- [ ] **Verify or create** `backend/app/api/dependencies.py`
  - [ ] `get_data_provider()` function with real provider support
  - [ ] Settings-based provider selection

- [ ] **Verify or create** Real Provider Adapter
  - [ ] Implements `FootballDataProvider` interface
  - [ ] Delegates to `ProviderManager`
  - [ ] Converts `ProviderMatch` → `Match`
  - [ ] Handles date range queries efficiently

- [ ] **Extend** `backend/app/providers/manager.py`
  - [ ] Add `get_matches_by_range()` if missing
  - [ ] Use provider cascade (ryzellx → fotmob → sofascore)
  - [ ] Return matches + metadata

- [ ] **Verify** `backend/app/providers/ryzellx.py`
  - [ ] `get_matches_by_range()` calls correct endpoint
  - [ ] Uses `localhost:3001` base URL
  - [ ] Normalizes response correctly

### Test Files Required

- [ ] **Create** `backend/tests/api/test_matches_integration.py`
  - [ ] Test single-day query
  - [ ] Test multi-day range query
  - [ ] Test status filtering
  - [ ] Test real provider mode
  - [ ] Test development provider mode
  - [ ] Test empty results (no fabrication)
  - [ ] Test backward compatibility

### Configuration Updates

- [ ] **Verify** `backend/app/config.py`
  - [ ] `use_real_providers: bool = False` (default)
  - [ ] `ryzellx_base_url: str = "http://localhost:3001"` (local default)

### Documentation

- [ ] **Update** `docs/PROGRESS.md`
  - [ ] Date range integration verified ✓
  - [ ] Single-day and multi-day queries working ✓
  - [ ] Status filtering working ✓
  - [ ] Real Ryzellx integration confirmed ✓
  - [ ] Integration test results

---

## Success Criteria

Phase 10A is **COMPLETE** when:

1. ✓ FEAT-001 (Capabilities) implemented and tested
2. ✓ FEAT-002 (Health) implemented and tested
3. ✓ FEAT-003 (Spatial Models) implemented and tested
4. ✓ FEAT-004 (Live Matches Endpoint) implemented and tested
5. ✓ **FEAT-005 (Date Range Integration) VERIFIED AND TESTED**
6. ✓ All acceptance criteria from correction doc satisfied
7. ✓ Integration tests passing
8. ✓ Manual curl tests successful with `use_real_providers=true`
9. ✓ Ryzellx logs confirm requests reaching localhost:3001
10. ✓ PROGRESS.md updated with complete validation results

---

## Timeline Impact

**Original Estimate**: 4 features (FEAT-001 through FEAT-004)  
**Updated Scope**: 5 features (FEAT-001 through FEAT-005)

**FEAT-005 Complexity**: MEDIUM
- If adapter exists and works: LOW (just add tests)
- If adapter missing: MEDIUM (create adapter + tests)
- If manager method missing: MEDIUM (add method + tests)

**Expected Additional Time**: 20-30% of original estimate

---

## Communication with Workflow

This specification provides the complete picture for the coder implementing Phase 10A.

**Key Message**: The date range integration is NOT a "nice to have" — it's **required for completion** because:
1. Frontend already expects it to work
2. Infrastructure already exists (mostly)
3. Real provider validation is incomplete without it
4. Users need scheduled matches, not just live matches

**Workflow Task**: Implement FEAT-005 after FEAT-004, verify complete integration chain, add comprehensive tests.

# ROOT CAUSE INVESTIGATION: "Yaklaşan Maç Bulunamadı"

**Date**: 2026-10-12  
**Commit**: 1c78b6f  
**Task**: Independent fix for empty upcoming matches UI issue

## SCOPE

Fix the "No upcoming matches found" false negative independent of:
- UI design changes
- Numerical model refactoring
- Future enhancements

## IDENTIFIED SCENARIOS (TO REPRODUCE)

### A. Provider Success Returns Empty Array
**Hypothesis**: FotMob get_matches_by_range returns [] for all 31 days due to ProviderError, but manager treats [] as success and doesn't fallback.

**Location**: `backend/app/providers/fotmob.py:1143-1172`

**Current Code Pattern**:
```python
while current_date <= end_date:
    try:
        daily_matches = await self.get_matches_by_date(current_date)
        all_matches.extend(daily_matches)
    except ProviderError as e:
        logger.warning(...)
        # Continue with other dates
    current_date += timedelta(days=1)

# Cache and return all_matches (could be [])
return all_matches
```

**Problem**: No distinction between:
- Successful query with zero legitimate matches for that date
- Failed query (exception swallowed, continues)
- No successful days at all (returns [] which manager treats as success)

### B. DB Match Lost After External Refresh
**Hypothesis**: DB has future SCHEDULED match A; external returns only unrelated FINISHED match B; status filter after merge drops A.

**Location**: `backend/app/providers/hybrid_provider.py:412-450`

**Current Code Pattern**:
```python
external_matches = await self.external_provider.get_matches_async(...)
if external_matches:
    # Apply status filter AFTER retrieval
    if status:
        external_matches = [m for m in external_matches if m.status == filter_status]
    
    all_matches.extend(external_matches)  # DB matches not preserved
else:
    all_matches.extend(db_matches)
```

**Problem**: External data replaces DB data even when:
- External doesn't include same match (different scope)
- External has fresher state (FINISHED) but was requested with status=SCHEDULED filter

### C. Pagination Hides Matches Beyond Page 1
**Hypothesis**: First 300 records are stale SCHEDULED from past hours today; record 301 is actually future; frontend filters client-side and shows nothing.

**Location**: 
- `frontend/src/pages/Upcoming.tsx:57-64` - Client-side time filter
- `backend/app/api/v1/endpoints/matches.py:211-212` - Server pagination

**Current Flow**:
1. Backend returns first 300 matches ordered by `scheduled_at`
2. Frontend filters those 300 for `matchTime > now`
3. If all 300 are past, shows empty even if match 301+ is future

### D. Timezone Naive/Aware Confusion
**Hypothesis**: DB stores timezone-naive datetime; backend/frontend treat it incorrectly causing matches to appear past when they're future or vice versa.

**Location**: Multiple - needs verification of actual timezone handling

## INVESTIGATION STEPS

### Step 1: Create Isolated Reproduction Tests
- [x] Plan documented
- [ ] Test scenario A: Provider fails all days
- [ ] Test scenario B: DB match + unrelated external
- [ ] Test scenario C: Pagination with stale records
- [ ] Test scenario D: Timezone handling

### Step 2: Trace Actual Code Flow
- [ ] Read full fotmob.py get_matches_by_range
- [ ] Read full hybrid_provider.py get_matches_async merge logic
- [ ] Read full manager.py fallback logic
- [ ] Verify DB timezone storage contract

### Step 3: Fix Each Root Cause
- [ ] Fotmob: Track success/failure per day, raise ProviderError if no successful days
- [ ] Manager: Distinguish [] legitimate empty from failure
- [ ] Hybrid: Merge DB + external properly, preserve DB matches not in external
- [ ] Pagination: Add server-side datetime filter, not just client-side
- [ ] Timezone: Ensure consistent UTC-aware handling

### Step 4: Verify Fixes
- [ ] Backend tests pass
- [ ] Frontend tests pass
- [ ] Integration test with mock scenarios
- [ ] Update PROGRESS.md with findings

## FILES TO MODIFY

**Backend**:
- `app/providers/fotmob.py` - get_matches_by_range
- `app/providers/manager.py` - _try_providers, get_matches_by_range
- `app/providers/hybrid_provider.py` - get_matches_async merge logic
- `app/api/v1/endpoints/matches.py` - Add scheduled_after filter
- `app/providers/adapter.py` - If ID mapping issues found

**Frontend**:
- `src/pages/Upcoming.tsx` - Request cleanup, proper empty states
- `src/api/client.ts` - Add abort signal support properly
- `src/api/types.ts` - Response schema if metadata added

**Tests**:
- `tests/providers/test_fotmob_failure.py` - New
- `tests/providers/test_hybrid_merge.py` - New  
- `tests/api/test_matches_pagination.py` - Enhanced
- `frontend/src/pages/__tests__/Upcoming.test.tsx` - New

## NEXT ACTION

Read full relevant code sections to understand current behavior completely before making any changes.

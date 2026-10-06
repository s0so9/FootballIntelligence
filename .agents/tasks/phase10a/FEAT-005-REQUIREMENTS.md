# FEAT-005: Date Range Integration - Detailed Requirements

**Status**: CONFIRMED ISSUE FOUND  
**Priority**: CRITICAL FOR PHASE 10A COMPLETION  
**File Location**: `backend/app/providers/adapter.py`

---

## Issue Confirmed

**File**: `backend/app/providers/adapter.py`, line ~176 in `get_matches()` method

**Current Code**:
```python
def get_matches(
    self,
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
    status: Optional[str] = None,
) -> List[Match]:
    """Get matches with optional filters."""
    
    # Only support single-date queries for now
    if from_date is not None:
        if to_date is not None and to_date != from_date:
            raise NotImplementedError(
                "Date range queries not yet implemented - "
                "only single date (from_date == to_date) supported"
            )
        
        provider_matches = self._exec(
            self._manager.get_matches_by_date(from_date)
        )
        # ... mapping code ...
```

**Problem**: Date range queries (`from_date` ≠ `to_date`) raise NotImplementedError

**Impact**: Frontend date range requests fail when `use_real_providers=True`

---

## Fix Required

### Step 1: Verify ProviderManager Has Range Method

Check if `backend/app/providers/manager.py` has:
```python
async def get_matches_by_range(
    self,
    start_date: date,
    end_date: date
) -> Tuple[List[ProviderMatch], Dict[str, Any]]:
```

**If YES**: Proceed to Step 2  
**If NO**: Implement the method first (see template below)

### Step 2: Update ProviderManagerAdapter.get_matches()

Replace the NotImplementedError logic with range query support:

```python
def get_matches(
    self,
    competition_id: Optional[str] = None,
    season_id: Optional[str] = None,
    team_id: Optional[str] = None,
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
    status: Optional[str] = None,
) -> List[Match]:
    """Get matches with optional filters.
    
    Supports:
    - Single date query: from_date provided, to_date None or equal to from_date
    - Date range query: both from_date and to_date provided, to_date > from_date
    - Status filtering: applied after fetching matches
    
    NOT YET SUPPORTED:
    - competition_id, season_id, team_id filtering
    
    Args:
        from_date: Fetch matches from this date
        to_date: Fetch matches up to this date (inclusive)
        status: Filter by match status (scheduled, live, finished, etc.)
        
    Returns:
        List of matching fixtures
    """
    if from_date is None:
        raise NotImplementedError(
            "Date filter required - provide at least from_date parameter"
        )
    
    # Determine query type
    if to_date is None or to_date == from_date:
        # Single date query
        logger.debug(f"Fetching matches for single date: {from_date}")
        provider_matches = self._exec(
            self._manager.get_matches_by_date(from_date)
        )
    else:
        # Date range query
        logger.debug(f"Fetching matches for range: {from_date} to {to_date}")
        provider_matches = self._exec(
            self._manager.get_matches_by_range(from_date, to_date)
        )
    
    # Map ProviderMatch list to domain Match list
    matches = []
    for pm in provider_matches:
        try:
            match = self._map_provider_match_to_domain(pm)
            matches.append(match)
        except Exception as e:
            logger.warning(
                f"Failed to map provider match {pm.source_id} to domain: {e}"
            )
    
    # Apply status filter if provided
    if status:
        matches = [m for m in matches if m.status.value == status]
        logger.debug(f"Filtered to {len(matches)} matches with status={status}")
    
    # Log result
    logger.info(
        f"Returning {len(matches)} matches for date range "
        f"{from_date} to {to_date or from_date}"
    )
    
    return matches
```

### Step 3: Implement ProviderManager.get_matches_by_range() If Missing

**File**: `backend/app/providers/manager.py`

**Add this method** (if it doesn't exist):

```python
async def get_matches_by_range(
    self,
    start_date: date,
    end_date: date
) -> Tuple[List[ProviderMatch], Dict[str, Any]]:
    """Get matches in date range using provider cascade.
    
    Uses DATE_RANGE_ORDER provider priority (typically same as MATCH_ORDER).
    
    Args:
        start_date: Start date (inclusive)
        end_date: End date (inclusive)
        
    Returns:
        Tuple of (matches, metadata)
        - matches: List of ProviderMatch
        - metadata: Dict with 'selected_provider', 'fallback_used', etc.
    """
    # Use same order as MATCH_ORDER for consistency
    provider_order = self.MATCH_ORDER
    
    for provider_name in provider_order:
        provider = self._get_provider(provider_name)
        if not provider:
            logger.debug(f"Provider {provider_name} not available, skipping")
            continue
        
        try:
            logger.debug(
                f"Attempting to fetch matches from {provider_name} "
                f"for range {start_date} to {end_date}"
            )
            
            # Call provider's range method
            matches = await provider.get_matches_by_range(start_date, end_date)
            
            logger.info(
                f"Successfully fetched {len(matches)} matches from {provider_name} "
                f"for range {start_date} to {end_date}"
            )
            
            return matches, {
                'selected_provider': provider_name,
                'fallback_used': False,
                'query_type': 'date_range',
            }
            
        except ProviderNotFoundError:
            logger.info(
                f"Provider {provider_name} returned not found for date range "
                f"{start_date} to {end_date}"
            )
            continue
            
        except ProviderError as e:
            logger.warning(
                f"Provider {provider_name} failed for date range query: {e}"
            )
            continue
        
        except Exception as e:
            logger.error(
                f"Unexpected error from provider {provider_name}: {e}",
                exc_info=True
            )
            continue
    
    # All providers failed
    logger.warning(
        f"All providers failed for date range {start_date} to {end_date}, "
        f"returning empty list"
    )
    
    return [], {
        'selected_provider': None,
        'fallback_used': False,
        'all_failed': True,
        'query_type': 'date_range',
    }
```

**Note**: Check if `self.MATCH_ORDER` already exists. If not, use:
```python
provider_order = ['ryzellx', 'fotmob', 'sofascore', 'openligadb']
```

---

## Test Requirements

### Unit Tests

**File**: `backend/tests/providers/test_adapter.py` (extend or create)

```python
@pytest.mark.asyncio
async def test_adapter_get_matches_single_day():
    """Test single-day query."""
    # from_date = to_date = 2026-10-05
    # Should call manager.get_matches_by_date()

@pytest.mark.asyncio
async def test_adapter_get_matches_date_range():
    """Test multi-day range query."""
    # from_date = 2026-10-05, to_date = 2026-10-12
    # Should call manager.get_matches_by_range()

@pytest.mark.asyncio
async def test_adapter_get_matches_with_status_filter():
    """Test status filtering."""
    # Fetch matches then filter by status=scheduled
    # Verify only scheduled matches returned

@pytest.mark.asyncio
async def test_adapter_maps_provider_match_to_domain():
    """Test ProviderMatch → Match conversion."""
    # Verify all fields mapped correctly
```

### Integration Tests

**File**: `backend/tests/api/test_matches_integration.py`

```python
@pytest.mark.asyncio
async def test_matches_endpoint_single_day_real_provider(test_client):
    """Test GET /api/v1/matches with single day."""
    response = test_client.get(
        "/api/v1/matches?from_date=2026-10-05&to_date=2026-10-05"
    )
    assert response.status_code == 200
    data = response.json()
    assert "matches" in data
    assert data["is_development_data"] == False

@pytest.mark.asyncio
async def test_matches_endpoint_date_range_real_provider(test_client):
    """Test GET /api/v1/matches with date range."""
    response = test_client.get(
        "/api/v1/matches?from_date=2026-10-05&to_date=2026-10-12"
    )
    assert response.status_code == 200
    data = response.json()
    assert "matches" in data
    # Should not raise NotImplementedError anymore

@pytest.mark.asyncio
async def test_matches_endpoint_status_filter(test_client):
    """Test status filtering."""
    response = test_client.get(
        "/api/v1/matches?from_date=2026-10-05&to_date=2026-10-12&status=scheduled"
    )
    assert response.status_code == 200
    data = response.json()
    # All returned matches should have status=scheduled
    for match in data["matches"]:
        assert match["status"] == "scheduled"
```

### Manual Verification Tests

```bash
# Start backend with real providers
cd backend
export USE_REAL_PROVIDERS=true
export RYZELLX_BASE_URL=http://localhost:3001
python -m uvicorn app.main:app --reload

# Test single day
curl "http://localhost:8000/api/v1/matches?from_date=2026-10-05&to_date=2026-10-05"

# Test date range (should not raise 500 error)
curl "http://localhost:8000/api/v1/matches?from_date=2026-10-05&to_date=2026-10-12"

# Test with status filter
curl "http://localhost:8000/api/v1/matches?from_date=2026-10-05&to_date=2026-10-12&status=scheduled"

# Verify in Ryzellx logs that request reached:
# GET /api/matches/range?start=2026-10-05&end=2026-10-12
```

---

## Verification Checklist

- [ ] `ProviderManager.get_matches_by_range()` exists or is implemented
- [ ] `ProviderManagerAdapter.get_matches()` handles date ranges without NotImplementedError
- [ ] Status filtering applied correctly after fetching
- [ ] Unit tests added for adapter
- [ ] Integration tests added for API endpoint
- [ ] Manual curl tests pass with `use_real_providers=true`
- [ ] Ryzellx logs show `/api/matches/range` request
- [ ] Empty results return `[]` not fabricated data
- [ ] Backward compatibility: single-day queries still work
- [ ] DevelopmentProvider still works when `use_real_providers=false`

---

## Expected Behavior After Fix

### Single-Day Query
```
GET /api/v1/matches?from_date=2026-10-05&to_date=2026-10-05
→ adapter.get_matches(from_date=2026-10-05, to_date=2026-10-05)
→ manager.get_matches_by_date(2026-10-05)
→ ryzellx.get_matches_by_date(2026-10-05)
→ GET http://localhost:3001/api/matches/date/2026-10-05
```

### Date Range Query
```
GET /api/v1/matches?from_date=2026-10-05&to_date=2026-10-12
→ adapter.get_matches(from_date=2026-10-05, to_date=2026-10-12)
→ manager.get_matches_by_range(2026-10-05, 2026-10-12)
→ ryzellx.get_matches_by_range(2026-10-05, 2026-10-12)
→ GET http://localhost:3001/api/matches/range?start=2026-10-05&end=2026-10-12
```

### Status Filtering
```
GET /api/v1/matches?from_date=2026-10-05&to_date=2026-10-12&status=scheduled
→ Fetch all matches in range
→ Filter: [m for m in matches if m.status.value == "scheduled"]
→ Return filtered list
```

---

## PROGRESS.md Documentation

After implementation, add to `docs/PROGRESS.md`:

```markdown
### Phase 10A: Real Provider Validation - FEAT-005 ✓

**Date Range Integration Validation**

Fixed: `ProviderManagerAdapter.get_matches()` now supports multi-day date ranges

- Implementation:
  - Single-day queries: Call `manager.get_matches_by_date()` ✓
  - Multi-day ranges: Call `manager.get_matches_by_range()` ✓
  - Status filtering: Applied after fetching ✓

- Provider Integration:
  - Ryzellx: `http://localhost:3001/api/matches/range` ✓
  - Provider cascade: ryzellx → fotmob → sofascore → openligadb ✓
  - Empty results: Returns `[]` not fabricated data ✓

- Testing:
  - Unit tests: adapter date range logic ✓
  - Integration tests: API endpoint with real provider ✓
  - Manual verification: curl with use_real_providers=true ✓
  - Ryzellx logs: Confirmed requests reaching localhost:3001 ✓

- Backward Compatibility:
  - Single-day queries: Still work ✓
  - DevelopmentProvider: Still works when use_real_providers=false ✓
  - Existing frontend: No changes required ✓

**Verification**: [number] tests passing, manual curl tests successful
```

---

## Implementation Priority

**Order**: Implement AFTER FEAT-001 through FEAT-004

**Why**: Other features don't depend on date range integration, but date range integration depends on provider infrastructure from FEAT-001 and FEAT-002.

**Timeline**: ~2-3 hours of implementation + testing

---

## Success Criteria

FEAT-005 is **COMPLETE** when:

1. ✓ Date range queries don't raise NotImplementedError
2. ✓ Single-day queries still work (backward compatible)
3. ✓ Status filtering works
4. ✓ Ryzellx localhost:3001 integration verified
5. ✓ Unit tests pass
6. ✓ Integration tests pass
7. ✓ Manual curl tests successful
8. ✓ Empty results return `[]` not fake data
9. ✓ DevelopmentProvider still works
10. ✓ PROGRESS.md updated

---

**This is the final piece required for Phase 10A completion.**

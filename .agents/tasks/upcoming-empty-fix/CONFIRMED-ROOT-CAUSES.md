# CONFIRMED ROOT CAUSES: Empty Upcoming Matches

**Investigation Date**: 2026-10-12  
**Commit**: 1c78b6f  

## ROOT CAUSE #1: Provider Returns [] But Manager Treats As Success

### Evidence

**File**: `backend/app/providers/fotmob.py:1107-1172`  
**Function**: `get_matches_by_range`

```python
while current_date <= end_date:
    try:
        daily_matches = await self.get_matches_by_date(current_date)
        all_matches.extend(daily_matches)
    except ProviderError as e:
        logger.warning(f"Failed to fetch matches for {current_date}: {e}")
        # Continue with other dates even if one fails
    current_date += timedelta(days=1)

# ... cache and return
return all_matches  # Could be [] if all days raised ProviderError
```

**File**: `backend/app/providers/manager.py:86-176`  
**Function**: `_try_providers`

```python
# SOURCE-OF-TRUTH CHECK: If result is not None, use it
if result is not None:
    metadata['selected_provider'] = provider_name
    metadata['fallback_used'] = (i > 0)
    logger.info(f"success from provider '{provider_name}'")
    return (result, metadata)
```

**Problem**: 
1. FotMob iterates 31 days, each day raises `ProviderError`
2. `all_matches` remains `[]`
3. FotMob returns `[]` (not `None`, not exception)
4. Manager checks `if result is not None:` → `[] is not None` → `True`
5. Manager declares success, doesn't try fallback OpenLigaDB
6. Empty array propagates to API → frontend shows "no matches"

**Actual Behavior**: All days fail silently, return `[]`, treated as "successfully found zero matches"

**Expected Behavior**: If no day succeeded, should raise `ProviderError` so manager tries next provider

---

## ROOT CAUSE #2: External Refresh Discards DB Matches

### Evidence

**File**: `backend/app/providers/hybrid_provider.py:390-440`  
**Function**: `get_matches_async` (status=SCHEDULED branch)

```python
if should_refresh:
    try:
        external_matches = await self.external_provider.get_matches_async(...)
        if external_matches:
            # Apply status filter to external matches
            if status:
                filter_status = MatchStatus(status.upper())
                external_matches = [m for m in external_matches if m.status == filter_status]
            
            # Resolve team UUIDs
            for m in external_matches:
                self._resolve_match_team_uuids(m)
            
            all_matches.extend(external_matches)  # ← BUG: db_matches LOST
        else:
            # Only use db_matches if external returned nothing
            all_matches.extend(db_matches)
```

**Scenario**: 
- DB has: `Match A (SCHEDULED, future, UEFA Champions League)`
- External FotMob returns: `Match B (FINISHED, past, Premier League)`
- Filter: `status=SCHEDULED`
- After status filter: `external_matches = []` (Match B filtered out)
- Code path: `if external_matches:` → `False` → takes `else` → uses `db_matches`
- **WAIT**: Code actually preserves db_matches in this case!

**Re-analysis**: This specific scenario is actually handled correctly. The bug is different:

**Actual Bug Scenario**:
- DB has: `Match A (SCHEDULED, future, id=uuid-A)`
- External returns: `Match C (SCHEDULED, future, id=uuid-C, different match)`
- Status filter: both pass
- Code: `all_matches.extend(external_matches)` but no merge with `db_matches`
- Match A lost because it's not in external response

**Real Problem**: When external succeeds with different matches, DB matches are silently dropped. No deduplication/merge logic in the status-filtered path.

---

## ROOT CAUSE #3: Client-Side Pagination Filter

### Evidence

**File**: `frontend/src/pages/Upcoming.tsx:43-48, 57-64`

```typescript
// Request limit=300
const matchesResponse = await getMatches({
  from_date: fromDate,
  to_date: toDate,
  status: 'SCHEDULED',
  limit: 300,
});

// ... then filter client-side
const upcomingMatches = normalizedMatches.filter(match => {
  if (match.status !== 'SCHEDULED') return false;
  const matchTime = new Date(match.scheduledAt);
  return matchTime > now;  // ← Filter AFTER receiving from server
});
```

**File**: `backend/app/api/v1/endpoints/matches.py:211-212`

```python
total_count = len(matches)
paginated_matches = matches[offset:offset + limit] if offset is not None and limit is not None else matches
```

**Problem**:
1. Backend has 1000 SCHEDULED matches
2. First 300 are today's past hours (stale, still SCHEDULED in DB)
3. Match 301-350 are actually future
4. Frontend requests limit=300
5. Backend returns first 300 (all with `scheduled_at < now` in practice)
6. Frontend filters: `matchTime > now` → 0 matches
7. UI shows empty

**Missing**: Server-side `scheduled_at >= datetime.now()` filter before pagination

---

## ROOT CAUSE #4: Timezone Handling (Not Yet Confirmed)

### Requires Verification

**Files to check**:
- Database models: Are timestamps stored as UTC-aware?
- Provider adapters: Do they parse/store timezone correctly?
- API serialization: Is timezone preserved in ISO8601?
- Frontend parsing: Does `new Date(match.scheduledAt)` respect timezone?

**Test needed**: Create match with known UTC time, verify it displays correctly in Istanbul timezone (UTC+3).

---

## ROOT CAUSE #5: Status Filter Loss in Sync Path

### Evidence

**File**: `backend/app/providers/hybrid_provider.py:578-585`

```python
# Sync path (DevelopmentProvider)
matches = provider.get_matches(
    competition_id=competition_id,
    season_id=season_id,
    team_id=team_id,
    from_date=from_date,
    to_date=to_date,
    status=status,
)

# ... then later in merge:
# External matches added WITHOUT applying status filter
```

**Problem**: Different code path for sync vs async providers may apply filters inconsistently.

---

## SUMMARY OF CONFIRMED BUGS

| # | Root Cause | Severity | File | Fix Complexity |
|---|------------|----------|------|----------------|
| 1 | Provider returns `[]`, manager doesn't fallback | **HIGH** | fotmob.py, manager.py | Medium |
| 2 | External refresh drops DB matches (merge missing) | **HIGH** | hybrid_provider.py | High |
| 3 | Client-side time filter after pagination | **MEDIUM** | matches.py, Upcoming.tsx | Low |
| 4 | Timezone naive/aware confusion | **TBD** | Multiple | TBD |
| 5 | Status filter inconsistency sync/async | **LOW** | hybrid_provider.py | Low |

## NEXT STEPS

1. Create reproduction tests for bugs #1, #2, #3
2. Implement fixes in order of severity
3. Verify with integration tests
4. Check timezone handling (bug #4)
5. Document in PROGRESS.md

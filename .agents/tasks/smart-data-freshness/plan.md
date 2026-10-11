# Smart Data Freshness & Synchronization - Implementation Plan

## Current State Analysis

### Existing Infrastructure
✅ **Database Schema**: Already has timestamp fields:
- `provider_fetched_at`: When data was last fetched from external provider
- `provider_updated_at`: When provider reported data was updated
- `last_provider_update`: Last provider synchronization timestamp
- `created_at`, `updated_at`: Standard ORM timestamps

✅ **Status-Aware Policy**: Already implemented in `hybrid_provider.py`:
- LIVE matches → External provider first (real-time critical)
- SCHEDULED/FINISHED → Database-first (stale acceptable)
- No filter → External provider (user expects fresh data)

### Gap Analysis
❌ **Domain Model Missing Timestamps**: `Match` domain model doesn't expose `provider_fetched_at`
❌ **No Freshness Logic**: No timestamp-based freshness checks
❌ **No Configuration**: Freshness thresholds are not configurable
❌ **No Concurrent Request Handling**: Multiple requests may trigger duplicate provider calls

## Implementation Strategy

### Phase 1: Domain Model Enhancement
**File**: `backend/app/domain/match.py`
- Add `provider_fetched_at: Optional[datetime]` field to Match domain model
- Preserve backward compatibility (optional field with None default)

**File**: `backend/app/providers/database_adapter.py`
- Update `get_match()` to include `provider_fetched_at`
- Update `get_matches()` to include `provider_fetched_at`

**File**: `backend/app/api/v1/schemas.py`
- Add `provider_fetched_at` to MatchResponse schema for API transparency

### Phase 2: Freshness Configuration
**File**: `backend/app/config.py`
- Add `DATA_FRESHNESS_SCHEDULED_MINUTES` (default: 120 minutes)
- Add `DATA_FRESHNESS_LIVE_SECONDS` (default: 30 seconds)
- Add `DATA_FRESHNESS_FINISHED_MINUTES` (default: 1440 minutes = 24 hours)
- Add `DATA_FRESHNESS_UNFINISHED_RECENT_MINUTES` (default: 180 minutes = 3 hours)

**Rationale**:
- SCHEDULED: 2 hours is reasonable for scheduled matches, refresh when kickoff approaches
- LIVE: 30 seconds for real-time updates (but status-aware policy already handles this)
- FINISHED: 24 hours for final score verification
- UNFINISHED_RECENT: Matches finished in last 3 hours may need score confirmation

### Phase 3: Freshness Logic Implementation
**File**: `backend/app/providers/hybrid_provider.py`

Add method: `_should_refresh_from_external(matches: List[Match], status_filter: Optional[str]) -> bool`

**Logic**:
```
1. If status_filter == "LIVE":
   → Already handled by status-aware policy, always refresh

2. If status_filter == "SCHEDULED":
   → Check if any match lacks provider_fetched_at OR
   → Check if any match kickoff is within UNFINISHED_RECENT_MINUTES and data is stale
   → Check if data is older than DATA_FRESHNESS_SCHEDULED_MINUTES
   
3. If status_filter == "FINISHED":
   → Check if any match finished recently (within UNFINISHED_RECENT_MINUTES) AND stale
   → Check if data is older than DATA_FRESHNESS_FINISHED_MINUTES
   
4. If no status_filter:
   → Already handled by status-aware policy, always refresh
```

**Integration Points**:
- Integrate into `get_matches_async()` database-first branch
- Integrate into `get_matches()` database-first branch
- Preserve existing LIVE/unfiltered behavior (no changes needed there)

### Phase 4: Duplicate Request Prevention
**Approach**: Use database query-level optimization (already exists via DB filtering)
- Database queries are already efficient with indexes
- Provider-level caching would add complexity without significant benefit
- Focus on reducing unnecessary provider calls via freshness logic

### Phase 5: Testing Strategy

**Test File**: `backend/tests/providers/test_hybrid_provider_freshness_timestamps.py`

Scenarios:
1. **Fresh scheduled data**: DB has data from 30 mins ago → No external call
2. **Stale scheduled data**: DB has data from 3 hours ago → External refresh
3. **Approaching kickoff**: Scheduled match in 15 mins with 1-hour-old data → External refresh
4. **LIVE match**: Always external (already tested)
5. **Recent FINISHED match**: Finished 1 hour ago, 2-hour-old data → External refresh
6. **Old FINISHED match**: Finished 3 days ago, 2-day-old data → No external call (verified)
7. **Missing provider_fetched_at**: DB match without timestamp → External refresh
8. **Provider timeout**: External fails → Return stale DB data with original timestamp
9. **Mixed freshness**: Some fresh, some stale → Refresh all

**Performance Benchmark**: `backend/scripts/benchmark_api.py`
- Run before/after comparisons
- Measure p50/p95 for `/matches?status=SCHEDULED`
- Measure p50/p95 for `/matches?status=FINISHED`
- Measure p50/p95 for `/matches?status=LIVE`

### Phase 6: Database Update Strategy
**No Migration Needed**: Fields already exist in database schema
**Update Strategy**: When external provider returns fresh data:
- Set `provider_fetched_at = now()` when persisting to database
- Ensure ingestion pipeline updates this field

**File**: Check ingestion pipeline to ensure `provider_fetched_at` is set

## Success Criteria

1. ✅ All existing tests pass
2. ✅ New freshness tests pass (9 scenarios)
3. ✅ Performance maintained or improved for scheduled/finished queries
4. ✅ LIVE match freshness guaranteed (no regression)
5. ✅ API response includes `provider_fetched_at` for transparency
6. ✅ Configuration allows tuning freshness thresholds
7. ✅ Fallback behavior preserves data availability

## Risk Mitigation

**Risk**: Provider unavailable, users get stale data without knowing
**Mitigation**: API response includes `provider_fetched_at` timestamp

**Risk**: Timestamp drift between servers
**Mitigation**: Use UTC everywhere, compare time deltas not absolute times

**Risk**: Database records without `provider_fetched_at`
**Mitigation**: Treat None as "unknown age" → trigger external refresh

**Risk**: Configuration changes break production
**Mitigation**: Use sensible defaults, document in config.py

## Files to Modify

1. `backend/app/domain/match.py` - Add provider_fetched_at field
2. `backend/app/providers/database_adapter.py` - Include timestamp in conversions
3. `backend/app/config.py` - Add freshness configuration
4. `backend/app/providers/hybrid_provider.py` - Implement freshness logic
5. `backend/app/api/v1/schemas.py` - Add provider_fetched_at to response
6. `backend/app/api/v1/endpoints/matches.py` - Pass provider_fetched_at to response
7. `backend/tests/providers/test_hybrid_provider_freshness_timestamps.py` - New test file

## Implementation Order

1. Domain model + database adapter (foundation)
2. Configuration (settings)
3. Freshness logic (core feature)
4. API schema updates (transparency)
5. Comprehensive tests (validation)
6. Performance benchmark (verification)
7. Final report (documentation)

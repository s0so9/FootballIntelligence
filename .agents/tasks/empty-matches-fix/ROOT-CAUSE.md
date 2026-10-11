# Root Cause Analysis: Empty Matches UI Issue

## Problem
- Upcoming Matches: Shows "No matches" despite 954 SCHEDULED matches in DB
- Completed Matches: Shows "No matches" despite 6,157 FINISHED matches in DB (last 30 days)

## Root Cause

**Critical Bug in `HybridProvider._update_match_statuses` and status filtering logic**

### Bug Flow:
1. Database has SCHEDULED matches from October 9, 2026 (now past, current date is Oct 10)
2. `HybridProvider.get_matches_async()` fetches these matches
3. `_update_match_statuses()` correctly updates SCHEDULED → FINISHED (for matches >4 hours past)
4. **BUG**: Status filter reapplies AFTER status updates (lines 353-358)
5. When user requests `status=scheduled`, the NOW-FINISHED matches get filtered out
6. Result: 0 matches returned

### Code Location:
`backend/app/providers/hybrid_provider.py`, lines 350-360:

```python
# Update statuses for matches from external providers
updated_matches = self._update_match_statuses(all_matches)

# Apply status filter after updates  ← BUG: Should be BEFORE
if requested_status:
    from app.domain.enums import MatchStatus
    try:
        requested_match_status = MatchStatus(requested_status.upper())
        before_filter = len(updated_matches)
        updated_matches = [m for m in updated_matches if m.status == requested_match_status]
        # This filters OUT the status-updated matches!
```

## Evidence

### Database State:
```
Total matches: 36,229
- FINISHED (last 30 days): 6,157 matches
- SCHEDULED (next 7 days): 954 matches
```

### API Responses:
```
GET /api/v1/matches?status=scheduled                → count: 1 (wrong!)
GET /api/v1/matches?status=finished                 → count: 0 (wrong!)
GET /api/v1/matches                                  → count: 20 (dev data fallback)
GET /api/v1/matches?from_date=2026-10-10&to_date=2026-10-17 → count: 1 (wrong!)
```

### Sample Matches from DB:
```
Recent FINISHED (already finished in DB):
  2026-10-09 19:15:00
  2026-10-09 19:00:00
  2026-10-09 19:00:00

SCHEDULED in DB (but NOW IN PAST):
  2026-10-09 02:00:00
  2026-10-09 08:45:00
  2026-10-09 17:45:00
```

These SCHEDULED matches are >24 hours past, so `_update_match_statuses` changes them to FINISHED, then status filter removes them!

## Secondary Issue: Development Data Fallback

When database-first optimization returns 0 matches, HybridProvider falls back to external provider which returns development data (`is_development_data: true`).

## Solution

**Option 1: Remove post-update status filtering** (RECOMMENDED)
- Database already has correct statuses via ingestion
- `_update_match_statuses` is for SCHEDULED-only correction
- Status filtering should happen at DB query level (already does via `db_status_filter`)
- Remove lines 353-360 post-update filtering

**Option 2: Apply status filter BEFORE status updates**
- Move status filtering before `_update_match_statuses()` call
- But this defeats the purpose of the update logic

**Option 3: Smart filtering**
- If original status was SCHEDULED and now FINISHED, check if request was for either status
- Complex and error-prone

## Fix Priority

**CRITICAL** - This completely breaks the matches UI for 99% of use cases where database has slightly stale status data.

The `_update_match_statuses` logic exists specifically to handle stale SCHEDULED matches, but the post-filter negates its entire purpose.

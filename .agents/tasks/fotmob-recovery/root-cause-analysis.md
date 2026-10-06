# FotMob Provider Recovery - Root Cause Analysis

**Date**: 2026-10-05
**Status**: ENDPOINT_INVALID (HTTP 404)

## Root Cause

The FotMob provider is configured with incorrect endpoint paths that do not match FotMob's actual API structure.

### Current Configuration (Incorrect)

```
Base URL: https://www.fotmob.com/api
Endpoints:
- Match list: /api/matches (relative) → https://www.fotmob.com/api/api/matches ❌
- Match details: /api/matchDetails → https://www.fotmob.com/api/api/matchDetails ❌
- Live matches: /api/matches/live → https://www.fotmob.com/api/api/matches/live ❌
```

### Actual FotMob API Structure (Verified)

Based on [Public-FotMob-API documentation](https://github.com/pseudo-r/Public-FotMob-API):

```
Base URL: https://www.fotmob.com
Endpoints:
- Match list: /api/data/matches?date=YYYYMMDD ✓
- Match details: /api/data/matchDetails?matchId={matchId} ✓
- Live matches: /api/data/matches?date={today} (filter for live) ✓
```

## Issues Identified

1. **Base URL duplication**: Current base URL includes `/api`, causing double `/api/api/` path
2. **Missing `/data/` segment**: Actual endpoints use `/api/data/` not `/api/`
3. **Health check endpoint**: Uses `/matches` without required `date` parameter
4. **Endpoint paths in provider code**: Hardcoded incorrect paths

## Files Requiring Changes

### 1. Configuration
- `backend/app/config.py` - Base URL correction

### 2. Provider Implementation
- `backend/app/providers/fotmob.py` - Endpoint path corrections

### 3. Health Check Configuration
- `backend/app/api/v1/endpoints/live_matches.py` - Health check endpoint correction

### 4. Tests
- `backend/tests/providers/test_health.py` - Update test expectations
- Any integration tests using FotMob

## FotMob API Characteristics (Verified)

### Available Endpoints

1. **Matches by Date** ✓
   - URL: `https://www.fotmob.com/api/data/matches?date=YYYYMMDD`
   - Returns: Grouped by leagues, matches with scores, status, teams

2. **Match Details** ✓
   - URL: `https://www.fotmob.com/api/data/matchDetails?matchId={id}`
   - Returns: Full match data, lineup, stats, events, xG, momentum

### Response Structure

Matches endpoint returns:
```json
{
  "leagues": [
    {
      "primaryId": 47,
      "name": "Premier League",
      "matches": [
        {
          "id": 4310531,
          "home": {"id": 8456, "name": "Man City", "score": 2},
          "away": {"id": 8634, "name": "Chelsea", "score": 1},
          "status": {
            "utcTime": "2024-03-26T14:00:00.000Z",
            "started": true,
            "finished": true
          }
        }
      ]
    }
  ]
}
```

## Implementation Plan

### Phase 1: Core Fixes
1. Update base URL in config.py
2. Update endpoint paths in fotmob.py
3. Update health check configuration

### Phase 2: Response Parsing
4. Verify/update response normalization logic
5. Update status parsing for FotMob's status structure

### Phase 3: Testing
6. Update tests to reflect new endpoints
7. Run provider-specific tests
8. Run integration tests
9. Validate with real FotMob calls

### Phase 4: Documentation
10. Document actual capabilities validated
11. Update PROGRESS.md

## Next Steps

Implement corrections in the order specified above, validating each step before proceeding.

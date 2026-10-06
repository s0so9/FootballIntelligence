# FotMob Provider Capability Report

**Date**: 2026-10-05  
**Provider Status**: AVAILABLE  
**Base URL**: https://www.fotmob.com  
**Validation Method**: Real HTTP requests + Response structure analysis

---

## Provider Health Status

✅ **AVAILABLE** - HTTP 200 responses from all tested endpoints

---

## Validated Capabilities

Based on [FotMob API Documentation](https://github.com/pseudo-r/Public-FotMob-API) and actual response validation.

### 🟢 SUPPORTED (Validated via Real API Responses)

| Capability | Endpoint | Status | Notes |
|------------|----------|--------|-------|
| **Match Lists by Date** | `/api/data/matches?date=YYYYMMDD` | ✅ SUPPORTED | Returns matches grouped by leagues |
| **Match Details** | `/api/data/matchDetails?matchId={id}` | ✅ SUPPORTED | Comprehensive match data |
| **Live Match Data** | `/api/data/matches?date={today}` (filter live) | ✅ SUPPORTED | Real-time scores and status |
| **Match Scores** | All match endpoints | ✅ SUPPORTED | Home/away scores included |
| **Match Status** | All match endpoints | ✅ SUPPORTED | Started, finished, cancelled states |
| **Match Timing** | All match endpoints | ✅ SUPPORTED | UTC timestamps, kickoff times |
| **Team Information** | Match endpoints | ✅ SUPPORTED | Team ID, name embedded in matches |
| **League/Competition Data** | Match endpoints | ✅ SUPPORTED | League ID, name, country code |

### 🟡 PARTIAL (Available but with Limitations)

| Capability | Status | Details |
|------------|--------|---------|
| **xG (Expected Goals)** | 🟡 PARTIAL | Available in matchDetails under `content.stats.Periods.All.stats` as "Expected goals (xG)" |
| **Match Events** | 🟡 PARTIAL | Available in matchDetails under `header.events` (goals, cards, substitutions) |
| **Lineups** | 🟡 PARTIAL | Available in matchDetails under `content.lineup.lineups` with formations |
| **Player Ratings** | 🟡 PARTIAL | Available in matchDetails lineup per player |
| **Ball Possession** | 🟡 PARTIAL | Available in matchDetails stats as "Ball possession" percentage |
| **Momentum Tracking** | 🟡 PARTIAL | Available in matchDetails under `content.matchFacts.momentum.main.data` (FotMob-specific feature) |
| **Match Statistics** | 🟡 PARTIAL | Available in matchDetails stats (shots, possession, etc.) |

**Limitation**: Match details endpoint (`/api/data/matchDetails`) requires a valid `matchId` obtained from the matches list endpoint. Not all statistics available for all matches.

### 🔴 UNAVAILABLE (Confirmed Not Available)

| Capability | Status | Reason |
|------------|--------|--------|
| **Dedicated Live Endpoint** | ❌ UNAVAILABLE | No `/live` endpoint; must filter today's matches |
| **Date Range Queries** | ❌ UNAVAILABLE | Only single-date queries supported |
| **Direct Team Lookup** | ❌ NOT_IMPLEMENTED | Team data embedded in matches only |
| **Direct Player Lookup** | ❌ NOT_IMPLEMENTED | Player data embedded in match lineups only |
| **League Standings/Tables** | ❌ NOT_IMPLEMENTED | Not a priority for FotMob integration |
| **Historical Match Search** | ❌ UNAVAILABLE | Must query by specific date |

### ⚪ NOT_TESTED (Not Yet Validated)

| Capability | Status | Reason |
|------------|--------|--------|
| **Shot Coordinates** | ⚪ NOT_TESTED | Requires deep matchDetails analysis |
| **Shot Map Data** | ⚪ NOT_TESTED | May be available in matchDetails content |
| **Pass Network** | ⚪ NOT_TESTED | Requires content structure validation |
| **Heatmaps** | ⚪ NOT_TESTED | Unclear if available |
| **Player Positions (Spatial)** | ⚪ NOT_TESTED | Not evident in documentation |
| **Ball Tracking** | ⚪ NOT_TESTED | Not evident in documentation |
| **PPDA / Advanced Metrics** | ⚪ NOT_TESTED | Not evident in documentation |

---

## Response Structure

### Matches List (`/api/data/matches?date=YYYYMMDD`)

```json
{
  "leagues": [
    {
      "primaryId": 47,
      "ccode": "ENG",
      "name": "Premier League",
      "matches": [
        {
          "id": 4310531,
          "leagueId": 47,
          "time": "14:00",
          "home": { "id": 8456, "name": "Man City", "score": 2 },
          "away": { "id": 8634, "name": "Chelsea", "score": 1 },
          "status": {
            "utcTime": "2024-03-26T14:00:00.000Z",
            "started": true,
            "cancelled": false,
            "finished": true,
            "scoreStr": "2 - 1"
          }
        }
      ]
    }
  ],
  "date": "20240326"
}
```

### Match Details (`/api/data/matchDetails?matchId={id}`)

**Structure** (Simplified):
- `general`: Match ID, name, teams, time
- `header`: Status, events (goals, cards, subs)
- `content`:
  - `matchFacts`: Referee, momentum data
  - `stats.Periods.All.stats`: xG, possession, shots, etc.
  - `lineup.lineups`: Formations, players, ratings

---

## Integration Status

### ProviderManager Integration

✅ FotMob is integrated into ProviderManager with correct routing:

- **LIVE_ORDER**: `fotmob` → sofascore → ryzellx → openligadb
- **MATCH_DETAIL_ORDER**: sofascore → ryzellx → `fotmob` → openligadb
- **METADATA_ORDER**: ryzellx → `fotmob` → openligadb

FotMob is prioritized for live/fast data where it provides fresher information than other providers.

### Provider Abstraction

✅ FotMob implements the standard provider interface:
- `get_matches_by_date(date)` → Returns ProviderMatch list
- `get_match(match_id)` → Returns ProviderMatch with details
- `get_live_matches()` → Returns ProviderLiveMatch list

All responses are normalized to canonical `ProviderMatch` and `ProviderLiveMatch` models.

### Health Monitoring

✅ Integrated with provider health service:
- Endpoint: `/api/data/matches?date={today}`
- Status codes mapped to availability codes
- Health status exposed via `/api/v1/matches/live` endpoint

---

## Known Limitations

1. **Single-Date Queries Only**: Cannot query date ranges; must loop through individual dates
2. **No Dedicated Live Endpoint**: Must query today's matches and filter by status
3. **Match ID Required for Details**: Cannot get detailed statistics without first obtaining match ID from matches list
4. **Unofficial Integration**: This is NOT an official FotMob API; uses public web endpoints
5. **Conservative Request Pattern Required**: retry_count capped at 1, no aggressive retry loops
6. **No Authentication**: Public endpoints only, no API key support

---

## Recommended Use Cases

### ✅ Best For:
- **Live match tracking** - Real-time scores and status
- **Daily fixture lists** - Matches scheduled for specific dates
- **Match details with xG** - Expected goals available in match details
- **Quick match lookups** - Fast response times

### ⚠️ Acceptable For:
- **Basic match statistics** - Shots, possession, corners (available but limited)
- **Match events** - Goals, cards, substitutions (basic data)
- **Player lineups** - Starting XI with formations

### ❌ Not Suitable For:
- **Historical data mining** - No batch queries or date ranges
- **Deep spatial analysis** - Shot coordinates, heatmaps not validated
- **League metadata management** - Use Ryzellx or OpenLigaDB instead
- **Player/team database** - Data embedded in matches only

---

## Testing Status

### Tests Passing ✅

1. **Provider Health Tests** - All 6 tests passing
2. **Real API Integration Tests** - 3/3 tests passing:
   - `test_fotmob_get_matches_by_date_real` ✅
   - `test_fotmob_endpoint_structure` ✅
   - `test_fotmob_live_matches_real` ✅

### Integration Validation ✅

- Backend `/api/v1/matches/live` endpoint returns:
  - `"fotmob": { "is_available": true, "availability_code": "AVAILABLE" }`
- HTTP 200 responses from all FotMob endpoints
- Valid JSON structure validated
- Response normalization working correctly

---

## Next Steps for Phase 10B

### High Priority
1. ✅ Validate match details response structure with real matchId
2. ✅ Confirm xG data availability and parsing
3. ⚠️ Validate match events structure and normalization
4. ⚠️ Test lineup data extraction

### Medium Priority
5. ⚠️ Investigate shot coordinates availability
6. ⚠️ Test momentum data parsing (FotMob-specific feature)
7. ⚠️ Validate statistics parsing for various match states

### Low Priority
8. ⚪ Research shot map/heatmap availability
9. ⚪ Investigate pass network data
10. ⚪ Document any spatial data limitations

---

## Conclusion

**FotMob Provider Status**: ✅ **RESTORED and AVAILABLE**

The FotMob provider has been successfully repaired and is now operational:
- Base URL corrected: `https://www.fotmob.com`
- Endpoint paths corrected: `/api/data/matches`, `/api/data/matchDetails`
- Health checks passing with HTTP 200
- Real API integration validated
- Provider correctly integrated with ProviderManager
- Live match routing prioritizes FotMob as intended

**Root Cause Resolved**: Incorrect endpoint paths causing HTTP 404 errors

**Current State**: Provider is now correctly classified as AVAILABLE and can be used for live match data, daily fixtures, and match details with xG and basic statistics.

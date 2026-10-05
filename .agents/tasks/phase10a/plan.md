# Phase 10A Implementation Plan
## Real Provider Validation & Live Intelligence Foundation

This is a **FOUNDATION/AUDIT phase** for Phase 10 Advanced Football Intelligence.

**DO NOT** build the final Live Radar UI yet.
**DO NOT** create fake player dots, fake ball movement, fake tracking coordinates, fake pass trajectories, or simulated live events.

**CRITICAL DATA RULE**: REAL DATA > NULL > FABRICATED DATA

Never fabricate live match events, player positions, ball coordinates, shots, passes, xG, possession, tracking data, or any other football intelligence signal.

---

## Implementation Features

This plan decomposes into 4 independent features that can be implemented sequentially:

### FEAT-001: Provider Capability Detection System
**File**: `backend/app/providers/capabilities.py` (NEW)

Create capability detection infrastructure that validates what each provider actually supports through real HTTP test requests.

**Components**:
- `ProviderCapabilityStatus` enum: SUPPORTED, PARTIAL, UNAVAILABLE, NOT_TESTED, NOT_CONFIGURED, AUTH_REQUIRED, PAYMENT_REQUIRED
- `ProviderCapabilityMatrix` Pydantic model: provider_name, last_checked, capabilities (dict), endpoint_tests (dict), notes
- Capability keys: live_matches, match_details, match_statistics, player_positions, ball_tracking, xg_data, lineups, events, shots, shot_xg, shot_coordinates, possession, corners, fouls, passes, saves

**Provider Extensions**:
- Add `async detect_capabilities()` method to: RyzellxFootballProvider, FotMobFootballProvider, SofaScoreFootballProvider, OpenLigaDBFootballProvider
- Each method performs real HTTP test requests to known endpoints
- Maps HTTP status codes to capability states (402→PAYMENT_REQUIRED, 404→ENDPOINT_INVALID, timeout→TIMEOUT)
- Never exposes secrets in logs
- Returns ProviderCapabilityMatrix

**Configuration**:
- Add `sofascore_base_url: str = "https://api.sofascore.com"` to `backend/app/config.py` Settings class

**Known Provider States** (from audit):
- Ryzellx: 402 Payment Required on /api/matches/live
- FotMob: 404 Not Found on /api/matches
- SofaScore: unofficial endpoints /sport/football/events/live and /event/{id}/statistics
- OpenLigaDB: xg_data UNAVAILABLE always (authoritative)

**Verification**: `pytest backend/tests/providers/test_capabilities.py -v`

---

### FEAT-002: Provider Health Monitoring System
**File**: `backend/app/providers/health.py` (NEW)

Create health monitoring service that tracks provider availability and failure modes.

**Components**:
- `ProviderHealthStatus` Pydantic model: provider_name (str), is_available (bool), last_check_utc (datetime), last_success_utc (Optional[datetime]), consecutive_failures (int), error_code (Optional[str]), error_detail (Optional[str])
- `ProviderHealthService` class with:
  - `__init__(provider_manager: ProviderManager)`
  - `_health_cache: Dict[str, ProviderHealthStatus]` (in-memory storage only)
  - `async check_provider(provider_name: str) -> ProviderHealthStatus`
  - `async check_all() -> Dict[str, ProviderHealthStatus]`
  - `get_health_status(provider_name: str) -> Optional[ProviderHealthStatus]`
  - `get_all_health_statuses() -> Dict[str, ProviderHealthStatus]`

**Health Check Logic**:
- Calls lightweight test endpoint (e.g., get_live_matches())
- Catches ProviderHTTPError and maps status codes:
  - 402 → PAYMENT_REQUIRED
  - 404 → ENDPOINT_INVALID
  - 429 → RATE_LIMITED
  - 5xx → SERVER_ERROR
- Catches ProviderTimeoutError → TIMEOUT
- Catches ProviderError → UNKNOWN_ERROR
- Updates consecutive_failures counter (increments on failure, resets on success)
- Stores result in _health_cache (in-memory only, no database)

**Verification**: `pytest backend/tests/providers/test_health.py -v`

---

### FEAT-003: Spatial Data Models & Enhanced ProviderLiveMatch
**File**: `backend/app/providers/models.py` (EXTEND existing)

Add spatial field support to existing provider models without replacing working code.

**New Models**:
- `PlayerPosition`: player_id, player_name (optional), team_id, x, y, timestamp
  - Validators: x in [0, 120], y in [0, 80] (realistic pitch meters)
- `BallPosition`: x, y, z (optional), timestamp
  - Validators: x in [0, 120], y in [0, 80], z in [0, 10] if present
- `FieldDimensions`: length_meters, width_meters, unit
  - Validators: length in [90, 120], width in [45, 90]
- `DataQualityIndicators`: has_player_positions, has_ball_tracking, has_xg, has_shots, has_events, has_shot_coordinates, has_live_statistics (all bool)

**Extend ProviderLiveMatch** (existing model around line 318):
Add optional fields:
- `player_positions: Optional[List[PlayerPosition]] = None`
- `ball_position: Optional[BallPosition] = None`
- `field_dimensions: Optional[FieldDimensions] = None`
- `data_quality: Optional[DataQualityIndicators] = None`

**Critical Requirements**:
- DO NOT replace ProviderLiveMatch, only extend it
- All spatial fields default to None
- Docstrings must state: "Optional spatial data. Defaults to None. MUST NOT FABRICATE. Only set when provider supplies real coordinates."
- Add model_validator to check coordinates within bounds when present

**Verification**: `pytest backend/tests/providers/test_normalization.py -v`

---

### FEAT-004: Live Matches API Endpoint with Health & Quality Reporting
**Files**: 
- `backend/app/api/v1/endpoints/live_matches.py` (NEW)
- `backend/app/api/v1/schemas.py` (EXTEND)
- `backend/app/api/v1/__init__.py` (EXTEND)

Create REST API endpoint for live matches with provider health and data quality reporting.

**Endpoint**:
```
GET /api/v1/matches/live
Query params:
  - league_id: Optional[str]
  - include_stats: Optional[bool] = False
```

**Response Model**: `LiveMatchesResponse`
- matches: List[LiveMatchResponse]
- provider_health: Dict[str, Any]
- data_quality: Dict[str, Any]
- timestamp: datetime
- provider_used: Optional[str]

**LiveMatchResponse Schema**:
- match_id, status, minute, home_score, away_score
- home_team, away_team (basic info)
- data_quality_flags: Dict (has_xg, has_events, has_shots, etc.)

**Implementation Logic**:
1. Get ProviderManager from dependency injection (follow pattern in existing matches.py)
2. Optionally get ProviderHealthService if available
3. Call `manager.get_live_matches()` → returns (matches, metadata)
4. Extract `provider_used` from `metadata['selected_provider']`
5. If ProviderHealthService available, call `get_all_health_statuses()` and include in response
6. Compute data_quality summary by aggregating flags across all matches
7. Handle failures gracefully: if all providers fail, return empty matches list + health status (never fabricate data)

**Route Registration**:
- In `backend/app/api/v1/__init__.py`: import and include live_matches.router

**Verification**:
- `pytest backend/tests/providers/test_live_matches.py -v`
- Manual test: `curl http://localhost:8000/api/v1/matches/live` returns JSON with empty matches + provider health

---

## Verification Strategy

Each feature has dedicated test file:
1. `backend/tests/providers/test_capabilities.py` - mocked httpx responses for 402, 404, 200 status codes
2. `backend/tests/providers/test_health.py` - mocked provider failures and health status tracking
3. `backend/tests/providers/test_normalization.py` - spatial field validation and bounds checking
4. `backend/tests/providers/test_live_matches.py` - API endpoint response structure and graceful failure

**No real network calls in tests**. All use mocked httpx.AsyncClient responses.

**Test command**: `pytest backend/tests/providers/ -v`

---

## Implementation Order

Features are **independent** but should be implemented in this order for logical dependency flow:

1. **FEAT-001** (Capabilities) - establishes what providers support
2. **FEAT-002** (Health) - depends on providers and capability concepts
3. **FEAT-003** (Spatial Models) - extends data structures independently
4. **FEAT-004** (API Endpoint) - consumes capabilities + health + models

Each feature leaves the codebase in a working state. Build/test after each feature.

---

## Documentation

After all features complete, update `docs/PROGRESS.md` with:
- What was implemented (capabilities, health, spatial models, API endpoint)
- Verification results (pytest output)
- Known provider states (Ryzellx 402, FotMob 404, OpenLigaDB no xG)
- Next steps (Phase 10 proper - Live Radar UI with real data consumption)

---

## Critical Reminders

1. **NEVER FABRICATE DATA**: Real data > null > fabricated data
2. **Keep use_real_providers=False**: Default to safe development mode
3. **Never expose secrets**: No API keys, tokens, or credentials in logs
4. **Graceful failures**: Empty list + health status, never invented data
5. **Read before editing**: Inspect all files before modifications
6. **Test after implementing**: Run pytest after each feature
7. **Update PROGRESS.md**: Document completion and verification results

---

## Files to Create (4 new files)

1. `backend/app/providers/capabilities.py`
2. `backend/app/providers/health.py`
3. `backend/app/api/v1/endpoints/live_matches.py`
4. `backend/tests/providers/test_capabilities.py`
5. `backend/tests/providers/test_health.py`
6. `backend/tests/providers/test_normalization.py`
7. `backend/tests/providers/test_live_matches.py`

## Files to Extend (6 existing files)

1. `backend/app/providers/models.py` - add spatial models, extend ProviderLiveMatch
2. `backend/app/providers/ryzellx.py` - add detect_capabilities()
3. `backend/app/providers/fotmob.py` - add detect_capabilities()
4. `backend/app/providers/sofascore.py` - add detect_capabilities()
5. `backend/app/providers/openligadb.py` - add detect_capabilities()
6. `backend/app/config.py` - add sofascore_base_url
7. `backend/app/api/v1/schemas.py` - add LiveMatchResponse, LiveMatchesResponse
8. `backend/app/api/v1/__init__.py` - register live_matches router

## Files to Update (1 documentation file)

1. `docs/PROGRESS.md` - add Phase 10A completion entry

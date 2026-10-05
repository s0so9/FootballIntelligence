# Phase 4 Implementation Plan: SofaScore Provider + Data Quality + Source Intelligence

## Overview

This plan implements Phase 4: Data Quality & Source Intelligence + SofaScore Provider Integration.

The work is decomposed into 3 sequential features (FEATs) that can be implemented, tested, and committed independently.

---

## Architecture Context (from exploration)

### Existing Provider Architecture

**Provider Pattern:**
- Async class with `__init__(base_url, timeout_seconds, retry_count, cache)`
- Async methods: `close()`, `_request()`, provider-specific data methods
- Exception handling: ProviderError, ProviderTimeoutError, ProviderHTTPError, ProviderInvalidDataError, ProviderNotFoundError
- Normalization: raw API → ProviderXxx models with source metadata
- Caching: ProviderCache with TTL constants

**Provider Models (models.py):**
- All models include source metadata: provider, source_id, fetched_at, source_updated_at, is_live, data_freshness_seconds
- All optional fields use `Optional[T]` — NEVER invent values
- ProviderMatchStats contains: goals, xG, shots (total/on/off/blocked), possession, passes, corners, cards, fouls, defensive stats

**ProviderManager (manager.py):**
- SOURCE-OF-TRUTH rule: once a provider returns non-None, that's final — no field-level failover
- Routing orders:
  - NORMAL_ORDER: ['ryzellx', 'openligadb']
  - LIVE_ORDER: ['fotmob', 'ryzellx', 'openligadb']
  - MATCH_DETAIL_ORDER: ['ryzellx', 'fotmob', 'openligadb'] → will become ['sofascore', 'ryzellx', 'fotmob', 'openligadb']
  - METADATA_ORDER: ['ryzellx', 'fotmob', 'openligadb']

**Existing Providers:**
- DevelopmentProvider: mock data for testing (DO NOT MODIFY — 38 tests depend on it)
- RyzellxFootballProvider: primary provider
- FotMobFootballProvider: live/fast provider (unofficial)
- OpenLigaDBFootballProvider: fallback provider

**Testing:**
- 38 existing tests in backend/tests/
- Pattern: pytest with fixtures
- All existing tests MUST pass after changes

---

## Feature Breakdown

This phase is implemented as 3 sequential features:

### FEAT-001: SofaScore Provider Implementation
**Files created/modified:** 
- backend/app/providers/models.py (add `period` field)
- backend/app/providers/sofascore.py (new)
- backend/app/providers/__init__.py (export SofaScoreFootballProvider)
- backend/app/providers/manager.py (routing update)

**Verification:** Import test, routing test, 38 existing tests pass

### FEAT-002: DataQualityEngine Implementation
**Files created/modified:**
- backend/app/providers/data_quality.py (new)
- backend/app/providers/__init__.py (export DataQualityEngine)

**Verification:** Import test, synchronous test, will be fully tested in FEAT-003

### FEAT-003: SourceIntelligence + Comprehensive Testing
**Files created/modified:**
- backend/app/providers/source_intelligence.py (new)
- backend/app/providers/__init__.py (export SourceIntelligence)
- backend/tests/test_sofascore_provider.py (new)
- backend/tests/test_data_quality.py (new)
- backend/tests/test_source_intelligence.py (new)

**Verification:** All new tests pass, 38 existing tests still pass

---

## Implementation Order & Dependencies

**Dependency Chain:**
FEAT-001 (SofaScore) → FEAT-002 (DataQuality) → FEAT-003 (SourceIntelligence + Tests)

FEAT-002 depends on FEAT-001 because DataQualityEngine operates on ProviderMatchStats (which gets the `period` field in FEAT-001).

FEAT-003 depends on FEAT-002 because SourceIntelligence uses DataQualityEngine in the 'highest_quality' merge strategy.

---

## Critical Implementation Details

### 1. SofaScore Provider (FEAT-001)

**SofaScore API (unofficial/reverse-engineered):**
- Base URL: https://api.sofascore.com/api/v1
- Match detail: /event/{event_id}
- Match statistics: /event/{event_id}/statistics
- Live matches: /sport/football/events/live

**Statistics Response Format:**
```json
[
  {
    "period": "ALL",
    "groups": [
      {
        "groupName": "TVData",
        "statisticsItems": [
          {
            "name": "Ball possession",
            "home": "58%",
            "away": "42%",
            "homeValue": 58,
            "awayValue": 42
          }
        ]
      }
    ]
  }
]
```

**Period Mapping:**
- 'ALL' → 'full'
- '1ST' → 'first_half'
- '2ND' → 'second_half'

**Statistics Mapping:**
SofaScore key → ProviderMatchStats field:
- 'Ball possession' → possession_percentage
- 'Total shots' or 'Shots' → shots_total
- 'Shots on target' → shots_on_target
- 'Shots off target' → shots_off_target
- 'Blocked shots' → shots_blocked
- 'Expected goals' or 'xG' → xg
- 'Corner kicks' or 'Corners' → corners
- 'Fouls' → fouls_committed
- 'Offsides' → offsides
- 'Yellow cards' → yellow_cards
- 'Red cards' → red_cards
- 'Passes' or 'Total passes' → passes_attempted
- 'Accurate passes' or 'Passes accurate' → passes_completed
- 'Tackles' → tackles
- 'Interceptions' → interceptions
- 'Clearances' → clearances
- 'Goalkeeper saves' or 'Saves' → saves

**ID Mapping:**
- MENSIONE internal IDs ↔ SofaScore IDs
- Use class attribute dict: `MENSIONE_TO_SOFASCORE_IDS = {}` (empty for now)
- Method: `_resolve_sofascore_id(mensione_id: str) -> Optional[str]`

**ProviderManager Routing Update:**
- MATCH_DETAIL_ORDER: ['sofascore', 'ryzellx', 'fotmob', 'openligadb'] (SofaScore first)
- LIVE_ORDER: ['fotmob', 'sofascore', 'ryzellx', 'openligadb'] (FotMob still fastest)

### 2. DataQualityEngine (FEAT-002)

**Class Characteristics:**
- Pure calculation class — NO async, NO HTTP calls
- Operates on ProviderMatchStats and ProviderMetadata
- All methods synchronous

**Quality Score Formula (must be documented in docstring):**
```
completeness_score = completeness['ratio'] * 100  (0-100)
consistency_score = 100 if is_consistent else max(0, 100 - violations_count * 20)
freshness_score = 100 if fresh else 50
overall = (completeness * 0.4 + consistency * 0.4 + freshness * 0.2)
```

**Consistency Rules:**
- shots_on_target <= shots_total (if both present)
- shots_off_target <= shots_total (if both present)
- shots_blocked <= shots_total (if both present)
- 0 <= possession_percentage <= 100 (if present)
- xg >= 0 (if present)
- goals_scored >= 0 (if present)
- All count fields >= 0 (if present)

### 3. SourceIntelligence (FEAT-003)

**Merge Strategies:**
- `'first'`: First non-None value per field wins (current ProviderManager behavior)
- `'most_complete'`: Provider with most non-None fields wins ENTIRELY (not field-by-field)
- `'highest_quality'`: Use DataQualityEngine to score each ProviderMatchStats, pick highest overall score

**Conflict Detection:**
- Compare same fields across providers
- Ignore None values
- Return conflicts only where values differ

**Field Source Tracking:**
- For each non-None field in merged result, track which provider supplied it

---

## Testing Strategy

### Test Files to Create (FEAT-003):

**backend/tests/test_sofascore_provider.py:**
- Mock HTTP requests (httpx-mock or unittest.mock.patch)
- Test normalization: all fields mapped correctly
- Test normalization: missing fields → None
- Test period field set correctly
- Test caching
- Test error handling
- NO real API calls

**backend/tests/test_data_quality.py:**
- Test completeness: all fields present, some missing
- Test consistency: valid stats, various violations (shots, possession, negatives)
- Test freshness: recent data, stale data
- Test conflict detection: no conflicts, disagreements
- Test quality score: perfect, incomplete, inconsistent
- Test formula determinism

**backend/tests/test_source_intelligence.py:**
- Test merge strategies: first, most_complete, highest_quality, empty list
- Test conflict detection: no conflicts, disagreements, ignores None
- Test field source tracking

### Verification Commands:

After each FEAT:
```powershell
cd backend
.venv\Scripts\python.exe -c "from app.providers import <NewClass>; print('✓ imports')"
.venv\Scripts\python.exe -m pytest tests/ -v --tb=short
```

After FEAT-003 (final):
```powershell
cd backend
.venv\Scripts\python.exe -m pytest tests/test_sofascore_provider.py -v
.venv\Scripts\python.exe -m pytest tests/test_data_quality.py -v
.venv\Scripts\python.exe -m pytest tests/test_source_intelligence.py -v
.venv\Scripts\python.exe -m pytest tests/ -v --tb=short  # All 38 + new tests
```

---

## Files Summary

### Files to Create (6):
1. backend/app/providers/sofascore.py
2. backend/app/providers/data_quality.py
3. backend/app/providers/source_intelligence.py
4. backend/tests/test_sofascore_provider.py
5. backend/tests/test_data_quality.py
6. backend/tests/test_source_intelligence.py

### Files to Modify (3):
1. backend/app/providers/models.py (add `period` field to ProviderMatchStats)
2. backend/app/providers/manager.py (update MATCH_DETAIL_ORDER, __init__, routing)
3. backend/app/providers/__init__.py (export 3 new classes)

### Files to NOT Touch:
- backend/app/providers/development.py (38 tests depend on it)
- All 38 existing test files (must still pass)

---

## Gotchas & Warnings

### 1. ProviderMatchStats `period` field
- Add ONE new field: `period: Optional[str] = Field(None, description="Match period: 'full', 'first_half', 'second_half'")`
- Do NOT modify any existing fields
- Do NOT rename any existing fields

### 2. SofaScore API is unofficial
- Unofficial/reverse-engineered endpoints
- Must handle failures gracefully (ProviderError)
- Conservative retry_count=1
- User-Agent headers recommended
- Rate limiting may apply

### 3. SOURCE-OF-TRUTH rule in ProviderManager
- Once a provider returns non-None, that's final
- No field-level failover
- Do NOT break this rule when updating routing

### 4. DevelopmentProvider is sacred
- 38 existing tests depend on it
- Do NOT modify backend/app/providers/development.py
- Do NOT modify its behavior
- All 38 existing tests must pass after changes

### 5. DataQualityEngine is synchronous
- NO async
- NO HTTP calls
- Pure calculation class

### 6. Test mocking
- Use httpx-mock or unittest.mock.patch for HTTP mocking
- NO real API calls in tests
- SofaScore tests must mock all HTTP requests

### 7. ID mapping
- MENSIONE internal IDs ≠ SofaScore IDs
- Use mapping dict (initially empty)
- Never assume provider ID is canonical

### 8. First-half statistics
- Do NOT calculate: full_match / 2
- Use SofaScore's actual period data ('1ST')
- If unavailable: None (never fabricate)

### 9. Shot data priority
- SofaScore has excellent shot data
- shots_total, shots_on_target, shots_off_target, shots_blocked, xG
- Map all shot fields where available

### 10. Never invent statistics
- Missing field → None
- Do NOT substitute with:
  - Random values
  - Averages
  - Confidence as statistics
  - Model estimates as real statistics
  - full_match / 2 as first_half

---

## Success Criteria

✓ SofaScoreFootballProvider implemented with all required methods
✓ ProviderMatchStats has `period` field
✓ SofaScore statistics normalized to ProviderMatchStats
✓ Period-specific stats supported ('full', 'first_half', 'second_half')
✓ DataQualityEngine implemented with documented formula
✓ SourceIntelligence implemented with 3 merge strategies
✓ All 3 new classes exported in __init__.py
✓ ProviderManager routing updated (SofaScore first for match detail)
✓ 3 new test files created with comprehensive coverage
✓ All new tests pass
✓ All 38 existing tests still pass
✓ No real HTTP calls in tests
✓ No data fabrication anywhere

---

## Post-Implementation: Update docs/PROGRESS.md

After all 3 FEATs complete, append entry to docs/PROGRESS.md:

```markdown
## Entry: [DATE] - Phase 4: SofaScore Provider + Data Quality + Source Intelligence

### Completed Work

**SofaScore Provider (FEAT-001):**
- Created backend/app/providers/sofascore.py with SofaScoreFootballProvider
- Added `period` field to ProviderMatchStats model
- Implemented match statistics retrieval with period-specific support
- Mapped SofaScore statistics to ProviderMatchStats (shots, xG, possession, etc.)
- Updated ProviderManager routing: SofaScore first for match detail

**DataQualityEngine (FEAT-002):**
- Created backend/app/providers/data_quality.py
- Implemented completeness checking
- Implemented consistency validation (shots, possession, negative values)
- Implemented freshness checking
- Implemented source conflict detection
- Implemented deterministic quality scoring formula

**SourceIntelligence (FEAT-003):**
- Created backend/app/providers/source_intelligence.py
- Implemented 3 merge strategies: first, most_complete, highest_quality
- Implemented conflict detection across providers
- Implemented field source tracking

**Testing:**
- Created backend/tests/test_sofascore_provider.py
- Created backend/tests/test_data_quality.py
- Created backend/tests/test_source_intelligence.py
- All new tests pass
- All 38 existing tests still pass

### Verification

```powershell
cd backend
.venv\Scripts\python.exe -m pytest tests/ -v --tb=short
# Result: X passed (38 existing + new tests)
```

### Next Steps

Phase 5: Live data integration and event-driven architecture

### Current Status

✓ Phase 4 Complete: SofaScore provider integrated, data quality engine operational, source intelligence layer ready
```

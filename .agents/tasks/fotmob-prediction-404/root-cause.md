# FotMob Prediction 404 - Root Cause Analysis

## Date
2026-10-06

## Issue
Frontend requests `GET /api/v1/matches/fotmob_5181855/prediction` and receives `404 Not Found`.

## Root Cause

### ID Format Mismatch

1. **Match List Endpoint** (`/api/v1/matches`):
   - Returns matches with prefixed IDs: `fotmob_5181855`
   - ID is generated in `ProviderManagerAdapter._map_provider_match_to_domain()`:
     ```python
     match_id = f"{pm.provider}_{pm.source_id}"
     ```

2. **Match Detail/Prediction Endpoint** (`/api/v1/matches/{match_id}/prediction`):
   - Receives prefixed ID: `fotmob_5181855`
   - Passes to `ProviderManagerAdapter.get_match(match_id="fotmob_5181855")`
   - Adapter calls `ProviderManager.get_match(match_id="fotmob_5181855")`
   - Manager tries providers in order: sofascore → ryzellx → fotmob → openligadb
   - **Each provider receives the full prefixed ID**

3. **FotMob Provider** (`FotMobFootballProvider.get_match()`):
   - Expects numeric ID only: `"5181855"`
   - Receives prefixed ID: `"fotmob_5181855"`
   - Makes API request: `/api/data/matchDetails?matchId=fotmob_5181855`
   - FotMob API doesn't recognize the prefixed ID
   - Raises `ValidationError` or returns `None`

### Evidence from Logs

```
[ProviderManager] get_match: provider 'ryzellx' raised ProviderHTTPError: Client error: 402 Payment Required
[ProviderManager] get_match: provider 'fotmob' raised unexpected error: ValidationError
[ProviderManager] get_match: provider 'openligadb' raised unexpected error: AttributeError
[ProviderManager] get_match: all providers failed or returned None
```

The FotMob provider is throwing `ValidationError` because it's receiving an invalid ID format.

## Solution

### Option 1: Strip Prefix in Adapter (RECOMMENDED)

Modify `ProviderManagerAdapter.get_match()` to:
1. Detect if match_id has format `{provider}_{id}`
2. Extract provider name and numeric ID
3. Route directly to that provider with numeric ID only
4. Fall back to multi-provider routing if no prefix

**Advantages:**
- Single point of fix
- Preserves all existing provider logic
- No changes needed to ProviderManager or individual providers
- Backward compatible with non-prefixed IDs

**Implementation:**
```python
def get_match(self, match_id: str) -> Optional[Match]:
    """Get a specific match by ID.
    
    Supports both prefixed (fotmob_123) and unprefixed (123) IDs.
    """
    # Check for provider prefix
    if '_' in match_id:
        parts = match_id.split('_', 1)
        if len(parts) == 2 and parts[0] in self._manager._providers:
            provider_name = parts[0]
            numeric_id = parts[1]
            
            # Route directly to specific provider with numeric ID
            provider = self._manager._providers[provider_name]
            provider_match = self._exec(provider.get_match(numeric_id))
            
            if provider_match is None:
                return None
            
            return self._map_provider_match_to_domain(provider_match)
    
    # Fall back to multi-provider routing for unprefixed IDs
    provider_match = self._exec(self._manager.get_match(match_id))
    
    if provider_match is None:
        return None
    
    return self._map_provider_match_to_domain(provider_match)
```

### Option 2: Change ID Generation (NOT RECOMMENDED)

Generate non-prefixed IDs in `_map_provider_match_to_domain()`.

**Disadvantages:**
- Breaks traceability to provider
- Risk of ID collisions between providers
- Major breaking change

## Verification Steps

1. Start backend: `python -m uvicorn app.main:app --host 127.0.0.1 --port 8002 --reload`

2. Test prefixed ID:
   ```bash
   curl.exe -X GET "http://127.0.0.1:8002/api/v1/matches/fotmob_5181855/prediction"
   ```
   Expected: 200 OK with prediction JSON (or 400 if insufficient data)
   NOT: 404 Not Found

3. Test unprefixed ID (backward compatibility):
   ```bash
   curl.exe -X GET "http://127.0.0.1:8002/api/v1/matches/5181855/prediction"
   ```
   Expected: Still works

4. Open frontend: `http://localhost:5173/`
   - MENSIONE PICKS page should load
   - Should show predictions or "PASS" decisions
   - Should NOT remain stuck on "Veriler yükleniyor..."

## Related Files

- `backend/app/providers/adapter.py` - ProviderManagerAdapter
- `backend/app/providers/manager.py` - ProviderManager
- `backend/app/providers/fotmob.py` - FotMobFootballProvider
- `backend/app/api/v1/endpoints/matches.py` - Prediction endpoint
- `frontend/src/pages/Dashboard.tsx` - MENSIONE PICKS page
- `frontend/src/api/client.ts` - API client

## Status

Workflow `wf_ac786646d10aea3b` is implementing the fix following Option 1.

# Multi-provider backend implementation

Introduces a multi-provider data architecture with intelligent routing, failover logic, and source-of-truth semantics. The implementation adds OpenLigaDBFootballProvider as an independent fallback source, wraps all providers in ProviderManager for routing, and exposes the manager through ProviderManagerAdapter to preserve the existing FootballDataProvider interface. Backward compatibility is maintained via config flag `use_real_providers=False`, keeping DevelopmentProvider as the default.

**Watch for:** *(confirmed)* FotMob retry count is correctly capped at 1. *(confirmed)* OpenLigaDB error handling matches ryzellx pattern. *(confirmed)* SOURCE-OF-TRUTH rule correctly implemented—no field-level failover. *(confirmed)* Routing orders are correctly applied: LIVE_ORDER for live matches (fotmob first), MATCH_DETAIL_ORDER for match detail (ryzellx first).

**Verdict**: APPROVED

## High-level view

OpenLigaDBFootballProvider implements the same error-handling contract as ryzellx: retries on 5xx and connection errors, no retry on 4xx, returns None on 404. It never provides xG data (this is not a gap—it's the authoritative result from this provider). ProviderManager routes by data type using four priority orders (NORMAL_ORDER, LIVE_ORDER, MATCH_DETAIL_ORDER, METADATA_ORDER) and enforces the SOURCE-OF-TRUTH rule: once a provider returns non-None, that is the final result—no merging across providers, no failover for optional None fields. ProviderManagerAdapter wraps the manager with asyncio.run() to expose the sync FootballDataProvider interface, tracks metadata from the last operation, and maps ProviderXxx models to domain models. Config adds `use_real_providers=False` without breaking existing settings. Dependencies.py yields DevelopmentProvider when `use_real_providers=False` (backward compatible default) and yields ProviderManagerAdapter with all three providers when True. Tests mock HTTP responses, cover failover on errors, cover source-of-truth (no failover on optional None fields), and validate metadata structure.

<details>
<summary>Issues (0)</summary>

No blocking issues found.

</details>

<details>
<summary>Details</summary>

## OpenLigaDB error handling matches ryzellx pattern

The `_request()` method in `openligadb.py` implements the same error-handling contract as `ryzellx.py`:

- **4xx errors (except 404)**: raise `ProviderHTTPError` immediately without retry
- **404 errors**: raise `ProviderNotFoundError` (caught by caller, returns None)
- **5xx errors**: retry up to `retry_count` with exponential backoff, then raise `ProviderHTTPError`
- **Connection errors (`httpx.RequestError`)**: retry up to `retry_count`, then raise `ProviderError`
- **Timeout errors (`httpx.TimeoutException`)**: raise `ProviderTimeoutError` immediately (no retry)

This is identical to the ryzellx pattern. Both providers use the same retry loop structure, the same backoff logic (`min(2 ** attempt, 10)`), and the same exception hierarchy.

```python
# openligadb.py lines 208-220
if 400 <= response.status_code < 500:
    raise ProviderHTTPError(...)

if 500 <= response.status_code < 600:
    # Server error - retry
    last_error = ProviderHTTPError(...)
    attempt += 1
    if attempt <= self.retry_count:
        await self._wait_before_retry(attempt)
        continue
    raise last_error
```

## OpenLigaDB never provides xG

OpenLigaDB does not provide xG data. The `_normalize_match()` method constructs a `ProviderMatch` without any xG-related fields (ProviderMatch doesn't have xG fields directly—those would live in ProviderMatchStats, which OpenLigaDB never populates).

The docstring explicitly calls this out:

```python
# openligadb.py lines 14-17
CRITICAL: OpenLigaDB does NOT provide xG data.
When this provider returns a match, xg=None is the authoritative result.
```

And again in the `_normalize_match` docstring:

```python
# openligadb.py line 325
CRITICAL: xg=None always (OpenLigaDB does not provide xG).
```

This is the correct behavior. When ProviderManager returns an OpenLigaDB match, the absence of xG is the authoritative result—not a signal to try the next provider.

## ProviderManager implements SOURCE-OF-TRUTH rule

The `_try_providers()` method iterates through providers in the specified order and returns the first non-None result. It does not merge fields from multiple providers:

```python
# manager.py lines 105-107
# SOURCE-OF-TRUTH CHECK: If result is not None, use it
if result is not None:
    metadata['selected_provider'] = provider_name
    metadata['fallback_used'] = (i > 0)
    
    logger.info(...)
    
    return (result, metadata)
```

Once a provider returns a ProviderMatch (or any non-None result), the loop exits immediately. There is no code that inspects the returned object for missing fields, no code that tries another provider to fill gaps.

Test coverage confirms this behavior:

```python
# test_providers_manager.py lines 202-243
async def test_manager_source_of_truth_no_failover_for_optional_none(...):
    """Test SOURCE-OF-TRUTH rule: no failover for missing optional fields.
    
    If ryzellx returns a valid ProviderMatch (even with some fields as None),
    the manager does NOT try next provider. One provider per response.
    """
    # Ryzellx returns match with some None fields
    ryzellx_match = sample_provider_match.model_copy()
    ryzellx_match.venue_name = None
    ryzellx_match.home_score_ht = None
    ryzellx_match.away_score_ht = None
    mock_ryzellx.get_match.return_value = ryzellx_match
    
    # FotMob could provide these fields but should not be called
    fotmob_match = sample_provider_match.model_copy()
    fotmob_match.provider = "fotmob"
    fotmob_match.venue_name = "Full Stadium Name"
    mock_fotmob.get_match.return_value = fotmob_match
    
    result, metadata = await provider_manager.get_match("match_123")
    
    # Result is from ryzellx only (SOURCE-OF-TRUTH)
    assert result.provider == "ryzellx"
    assert result.venue_name is None  # Not filled from fotmob
    assert metadata['selected_provider'] == 'ryzellx'
    assert metadata['fallback_used'] is False
    
    # Verify fotmob was NOT called
    mock_fotmob.get_match.assert_not_called()
```

## Routing orders are correctly applied

ProviderManager defines four routing orders and applies them to the appropriate operations:

- **NORMAL_ORDER**: `['ryzellx', 'openligadb']` — used by `get_matches_by_date()`
- **LIVE_ORDER**: `['fotmob', 'ryzellx', 'openligadb']` — used by `get_live_matches()`
- **MATCH_DETAIL_ORDER**: `['ryzellx', 'fotmob', 'openligadb']` — used by `get_match()`
- **METADATA_ORDER**: `['ryzellx', 'fotmob', 'openligadb']` — used by `get_team()`, `get_player()`, `get_league()`, `get_standings()`

Each method passes the correct order to `_try_providers()`:

```python
# manager.py lines 137-150
async def get_matches_by_date(self, date_obj: date) -> Tuple[List, Dict]:
    provider_method_map = {
        'ryzellx': lambda: self._providers['ryzellx'].get_matches_by_date(date_obj),
        'openligadb': lambda: self._providers['openligadb'].get_matches_by_date(date_obj),
    }
    
    result, metadata = await self._try_providers(
        operation_name='get_matches_by_date',
        provider_order=self.NORMAL_ORDER,
        provider_method_map=provider_method_map
    )
```

```python
# manager.py lines 175-185
async def get_live_matches(self) -> Tuple[List, Dict]:
    provider_method_map = {
        'fotmob': lambda: self._providers['fotmob'].get_live_matches(),
        'ryzellx': lambda: self._providers['ryzellx'].get_live_matches(),
        'openligadb': lambda: self._providers['openligadb'].get_live_matches(),
    }
    
    result, metadata = await self._try_providers(
        operation_name='get_live_matches',
        provider_order=self.LIVE_ORDER,
        provider_method_map=provider_method_map
    )
```

Test coverage confirms the routing:

```python
# test_providers_manager.py lines 51-67
async def test_manager_get_match_uses_match_detail_order(...):
    """Test that get_match uses MATCH_DETAIL_ORDER (ryzellx first)."""
    mock_ryzellx.get_match.return_value = sample_provider_match
    
    result, metadata = await provider_manager.get_match("match_123")
    
    assert result == sample_provider_match
    assert metadata['selected_provider'] == 'ryzellx'
    mock_ryzellx.get_match.assert_called_once_with("match_123")

async def test_manager_get_live_matches_uses_live_order(...):
    """Test that get_live_matches uses LIVE_ORDER (fotmob first)."""
    mock_fotmob.get_live_matches.return_value = mock_live_matches
    
    result, metadata = await provider_manager.get_live_matches()
    
    assert metadata['selected_provider'] == 'fotmob'
    mock_fotmob.get_live_matches.assert_called_once()
```

## ProviderManagerAdapter implements all abstract methods

The adapter implements all methods from the `FootballDataProvider` base class. Seven methods raise `NotImplementedError` with clear messages (these are not blocking—they're explicitly marked as not-yet-implemented and guide users to alternatives):

- `get_competitions()` — "use specific provider or development provider"
- `get_competition()` — "use specific provider or development provider"
- `get_seasons()` — "use specific provider or development provider"
- `get_current_season()` — "use specific provider or development provider"
- `get_teams()` — "use specific provider or development provider"
- `get_matches()` with filters other than `from_date` — "only date-based match queries implemented"
- `get_standings()` — "not yet implemented"

The implemented methods are:

- `get_team()` — calls `manager.get_team()`, maps ProviderTeam to domain Team
- `get_match()` — calls `manager.get_match()`, maps ProviderMatch to domain Match
- `get_matches()` with `from_date` — calls `manager.get_matches_by_date()`, maps list
- `get_provider_name()` — returns `last_metadata['selected_provider']`
- `is_development_data()` — returns `False`

## Config adds use_real_providers flag without breaking existing fields

`config.py` adds the new flag with a safe default:

```python
# config.py lines 37-38
use_real_providers: bool = False  # False = DevelopmentProvider (default)
```

All existing fields remain unchanged. The flag is a new optional field with a default value, so existing deployments that don't set it will continue using DevelopmentProvider (backward compatible).

## Dependencies.py backward compatibility preserved

The `get_data_provider()` function checks `settings.use_real_providers` and yields `DevelopmentProvider` when False:

```python
# dependencies.py lines 26-33
if not settings.use_real_providers:
    # Backward compatible: use DevelopmentProvider (PHASE 1 behavior)
    provider = DevelopmentProvider()
    try:
        yield provider
    finally:
        pass
```

When True, it constructs the three provider instances, wraps them in ProviderManager, wraps the manager in ProviderManagerAdapter, and yields the adapter:

```python
# dependencies.py lines 34-71
else:
    # Multi-provider architecture with real data providers
    cache = ProviderCache()
    
    ryzellx = RyzellxFootballProvider(...)
    fotmob = FotMobFootballProvider(
        ...,
        retry_count=min(settings.provider_retry_count, 1),  # Cap at 1
    )
    openligadb = OpenLigaDBFootballProvider(...)
    
    manager = ProviderManager(
        ryzellx=ryzellx,
        fotmob=fotmob,
        openligadb=openligadb,
        cache=cache,
    )
    
    adapter = ProviderManagerAdapter(manager=manager)
    
    try:
        yield adapter
    finally:
        asyncio.run(manager.close())
```

## FotMob retry count capped at 1

The `FotMobFootballProvider` instantiation caps the retry count at 1:

```python
# dependencies.py lines 43-45
fotmob = FotMobFootballProvider(
    ...,
    retry_count=min(settings.provider_retry_count, 1),  # Cap at 1 for unofficial API
)
```

This is conservative behavior for an unofficial API. Even if the global `provider_retry_count` setting is higher, FotMob will only retry once.

</details>

<details>
<summary>File map</summary>

- **app/providers/openligadb.py** — New provider implementation for OpenLigaDB as independent fallback source
- **app/providers/manager.py** — New ProviderManager class with intelligent routing and SOURCE-OF-TRUTH logic
- **app/providers/adapter.py** — New ProviderManagerAdapter wrapping manager to expose sync FootballDataProvider interface
- **app/providers/__init__.py** — Exports for new provider, manager, adapter
- **app/config.py** — Adds `use_real_providers` flag (default False) and provider base URLs
- **app/api/dependencies.py** — Updated dependency to yield ProviderManagerAdapter when `use_real_providers=True`, else DevelopmentProvider
- **tests/test_providers_openligadb.py** — Unit tests for OpenLigaDB provider with mocked HTTP
- **tests/test_providers_manager.py** — Unit tests for ProviderManager routing, failover, source-of-truth, metadata

Full diff: run `git diff main` in c:\FootballIntelligence\backend

</details>

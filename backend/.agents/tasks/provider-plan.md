# Implementation Plan: Multi-Provider Backend Architecture

## Overview
Complete the multi-provider backend implementation with OpenLigaDB provider, ProviderManager for intelligent routing, adapter layer, conditional injection, and comprehensive testing.

## Implementation Steps

- [ ] 1. Create OpenLigaDBFootballProvider in app/providers/openligadb.py
      Implement OpenLigaDB provider following the same HTTP/cache/normalization pattern as ryzellx.py and fotmob.py. Class OpenLigaDBFootballProvider with PROVIDER_NAME='openligadb', async httpx.AsyncClient, retry_count=2, base_url configurable (default: https://api.openligadb.de). Implement get_league(league_id), get_match(match_id), get_standings(league_id) using OpenLigaDB endpoints (GET /getavailableleagues, GET /getmatchdata/{matchId}, GET /getbltable/{leagueShortcut}/{leagueSeason}). Return stubs (empty lists) for get_matches_by_date(date), get_live_matches(). Return None for get_team(team_id), get_player(player_id). CRITICAL: xg=None always (OpenLigaDB does not provide xG). Use same error handling pattern as ryzellx.py (ProviderHTTPError, ProviderTimeoutError, ProviderNotFoundError, ProviderInvalidDataError). Integrate cache with same TTL patterns as ryzellx.py.
      Files: c:\FootballIntelligence\backend/app/providers/openligadb.py
      Verify: Run pytest tests/test_providers_openligadb.py -v (after step 4 creates the test)

- [ ] 2. Create ProviderManager in app/providers/manager.py
      Implement ProviderManager class that orchestrates multiple providers with intelligent routing. Constructor: __init__(self, ryzellx, fotmob, openligadb, cache=None). Define routing constants: NORMAL_ORDER = ['ryzellx', 'openligadb'], LIVE_ORDER = ['fotmob', 'ryzellx', 'openligadb'], MATCH_DETAIL_ORDER = ['ryzellx', 'fotmob', 'openligadb'], METADATA_ORDER = ['ryzellx', 'fotmob', 'openligadb']. Implement _try_providers(operation_name, provider_order, provider_method_map) that tries providers in order, returning (result, metadata_dict) where metadata_dict has keys: selected_provider, attempted_providers, fallback_used, fetched_at. On exception or None result from a provider, try next in order. Return first non-None result. If all fail, return (None, metadata_dict with all attempted). SOURCE-OF-TRUTH RULE: ONE provider per response - no failover for missing optional fields (if primary returns result with xg=None, that is the final result). Implement async methods: get_matches_by_date(date), get_match(match_id), get_live_matches(), get_team(team_id), get_player(player_id), get_league(league_id), get_standings(league_id). Each method uses appropriate routing order and calls _try_providers with provider_method_map mapping provider names to async methods.
      Files: c:\FootballIntelligence\backend/app/providers/manager.py
      Verify: Run pytest tests/test_providers_manager.py -v (after step 5 creates the test)

- [ ] 3. Create ProviderManagerAdapter in app/providers/adapter.py
      Implement ProviderManagerAdapter(FootballDataProvider) that wraps ProviderManager to expose the FootballDataProvider interface. Store last_metadata dict (updated by each method call). Implement get_provider_name() -> str: returns last_metadata.get('selected_provider', 'unknown'). Implement is_development_data() -> bool: returns False. Implement all FootballDataProvider abstract methods (get_competitions, get_competition, get_seasons, get_current_season, get_teams, get_team, get_matches, get_match, get_team_players, get_player, get_venue, get_standings). Methods that call ProviderManager use asyncio.run() to run async code (since FootballDataProvider is sync). Map ProviderMatch fields to domain Match fields using development.py as reference for field mapping (ProviderMatch.source_id -> Match.id, ProviderMatch.home_team_name -> Match.home_team_id lookup, etc.). For unimplemented methods (get_competitions, get_seasons, get_current_season, get_teams, get_team_players, get_venue, get_match_events, get_match_lineups, get_team_match_statistics, etc.), raise NotImplementedError with clear message.
      Files: c:\FootballIntelligence\backend/app/providers/adapter.py
      Verify: Run pytest tests/test_providers.py -v (existing test should still pass)

- [ ] 4. Create tests for OpenLigaDB provider in tests/test_providers_openligadb.py
      Use respx to mock httpx requests (same pattern as test_providers_multi.py). Test cases: (1) test_openligadb_get_match returns ProviderMatch with xg=None, (2) test_openligadb_get_league returns ProviderCompetition, (3) test_openligadb_get_standings returns list of ProviderStanding, (4) test_openligadb_get_matches_by_date returns empty list (stub), (5) test_openligadb_get_live_matches returns empty list (stub), (6) test_openligadb_get_team returns None (stub), (7) test_openligadb_get_player returns None (stub), (8) test_openligadb_http_error_404 returns None for get_match when 404, (9) test_openligadb_http_error_500 raises ProviderHTTPError after retries, (10) test_openligadb_timeout_error raises ProviderTimeoutError. Use pytest fixtures and pytest.mark.asyncio. NO real HTTP calls - all mocked with respx.
      Files: c:\FootballIntelligence\backend/tests/test_providers_openligadb.py
      Verify: Run pytest tests/test_providers_openligadb.py -v and confirm all tests pass

- [ ] 5. Create tests for ProviderManager in tests/test_providers_manager.py
      Use unittest.mock.AsyncMock to mock provider instances (ryzellx, fotmob, openligadb). Test cases: (1) test_manager_get_match_uses_match_detail_order (ryzellx first), (2) test_manager_get_live_matches_uses_live_order (fotmob first), (3) test_manager_get_matches_by_date_uses_normal_order (ryzellx first), (4) test_manager_failover_on_exception (primary raises ProviderError, secondary succeeds), (5) test_manager_failover_on_none (primary returns None, secondary succeeds), (6) test_manager_all_providers_fail (all return None or raise, final result is None with full attempted_providers list), (7) test_manager_metadata_contains_selected_provider, (8) test_manager_metadata_contains_fallback_used (True when not first provider), (9) test_manager_source_of_truth_rule (primary returns result with xg=None, no failover to secondary even if it has xg). Use pytest fixtures and pytest.mark.asyncio. NO real HTTP calls - all mocked.
      Files: c:\FootballIntelligence\backend/tests/test_providers_manager.py
      Verify: Run pytest tests/test_providers_manager.py -v and confirm all tests pass

- [ ] 6. Update app/providers/__init__.py to export new classes
      Add imports: from app.providers.openligadb import OpenLigaDBFootballProvider, from app.providers.manager import ProviderManager, from app.providers.adapter import ProviderManagerAdapter. Add to __all__ list: "OpenLigaDBFootballProvider", "ProviderManager", "ProviderManagerAdapter".
      Files: c:\FootballIntelligence\backend/app/providers/__init__.py
      Verify: Run python -c "from app.providers import OpenLigaDBFootballProvider, ProviderManager, ProviderManagerAdapter; print('Imports OK')" in backend directory

- [ ] 7. Update app/config.py to add use_real_providers flag
      Add to Settings class: use_real_providers: bool = False (default False for backward compatibility). DO NOT duplicate existing provider settings (ryzellx_base_url, fotmob_base_url, openligadb_base_url, provider_timeout_seconds, provider_retry_count already exist).
      Files: c:\FootballIntelligence\backend/app/config.py
      Verify: Run python -c "from app.config import settings; print(f'use_real_providers={settings.use_real_providers}')" in backend directory

- [ ] 8. Update app/api/dependencies.py for conditional provider injection
      Import: from app.config import settings, from app.providers import (DevelopmentProvider, RyzellxFootballProvider, FotMobFootballProvider, OpenLigaDBFootballProvider, ProviderManager, ProviderManagerAdapter, ProviderCache). Modify get_data_provider(): if settings.use_real_providers is False, yield DevelopmentProvider() (current behavior, backward compatible). If settings.use_real_providers is True: create cache = ProviderCache(), create ryzellx = RyzellxFootballProvider(base_url=settings.ryzellx_base_url, timeout_seconds=settings.provider_timeout_seconds, retry_count=settings.provider_retry_count, cache=cache), create fotmob = FotMobFootballProvider(...), create openligadb = OpenLigaDBFootballProvider(...), create manager = ProviderManager(ryzellx, fotmob, openligadb, cache), create adapter = ProviderManagerAdapter(manager), yield adapter. In finally block, close all providers if real providers were used (await ryzellx.close(), fotmob.close(), openligadb.close() using asyncio.run()).
      Files: c:\FootballIntelligence\backend/app/api/dependencies.py
      Verify: Run python -c "from app.api.dependencies import get_data_provider; p = next(get_data_provider()); print(f'Provider: {p.get_provider_name()}, IsDev: {p.is_development_data()}')" in backend directory (should show DevelopmentProvider)

- [ ] 9. Update docs/PROGRESS.md to document multi-provider architecture
      Create docs/PROGRESS.md if it doesn't exist (it currently doesn't). Append entry with format matching other PROGRESS.md files in the repo (date, completed work, verification, next steps). Document: Multi-provider architecture implemented with three providers: Ryzellx (primary for matches, fixtures, xG, metadata), FotMob (live/fast data), OpenLigaDB (independent fallback, no xG). ProviderManager orchestrates intelligent routing: NORMAL_ORDER (ryzellx → openligadb), LIVE_ORDER (fotmob → ryzellx → openligadb), MATCH_DETAIL_ORDER (ryzellx → fotmob → openligadb). Source-of-truth policy: ONE provider per response, no field-level failover. ProviderManagerAdapter wraps manager to expose FootballDataProvider interface. Conditional injection via use_real_providers flag (default False for backward compatibility). Tests: test_providers_openligadb.py, test_providers_manager.py. Verification: pytest tests/test_providers_openligadb.py tests/test_providers_manager.py -v, all tests pass.
      Files: c:\FootballIntelligence\backend/docs/PROGRESS.md
      Verify: Read docs/PROGRESS.md and confirm entry exists

- [ ] 10. Run full test suite and verify backward compatibility
      Run pytest tests/ -v to ensure all existing tests still pass (especially test_providers.py, test_providers_multi.py). Run pytest tests/test_providers_openligadb.py tests/test_providers_manager.py -v to verify new tests pass. Verify backward compatibility: with use_real_providers=False (default), system uses DevelopmentProvider as before. Verify conditional behavior: temporarily set use_real_providers=True in code, verify ProviderManagerAdapter is used (can check via get_provider_name() returning 'ryzellx' or similar instead of 'DevelopmentProvider (Mock Data)').
      Files: No files modified
      Verify: Run pytest tests/ -v --tb=short and confirm all tests pass with 0 failures

## Key Design Decisions

1. **OpenLigaDB xG Policy**: OpenLigaDB does not provide xG data, so xg=None always. This is not a missing field to failover on - it's the authoritative result from this provider.

2. **Provider Routing Strategy**: Different data types use different provider orders. Live matches prioritize FotMob for freshness. Normal fixtures prioritize Ryzellx for completeness. This is encoded in routing constants in ProviderManager.

3. **Source-of-Truth Rule**: Once a provider returns a result, that is the final result - no field-level failover. If ryzellx returns a match with xg=None, we do NOT try fotmob to get xG. This prevents data inconsistency where different fields come from different sources with different timestamps.

4. **Backward Compatibility**: use_real_providers defaults to False, so existing deployments continue using DevelopmentProvider. No breaking changes to API surface.

5. **Async Wrapping**: ProviderManager methods are async (for HTTP efficiency), but FootballDataProvider interface is sync (for simplicity in domain layer). ProviderManagerAdapter uses asyncio.run() to bridge this gap.

6. **Error Handling**: Provider exceptions (ProviderHTTPError, ProviderTimeoutError, etc.) are caught by ProviderManager and trigger failover to next provider. If all providers fail, return None with metadata showing all attempts.

7. **Cache Integration**: Single shared ProviderCache instance passed to all providers and ProviderManager for coordinated caching with appropriate TTLs per data type.

## Dependencies

- Steps 1-3 can be implemented in parallel (OpenLigaDB, ProviderManager, Adapter are independent)
- Step 4 depends on step 1 (test needs OpenLigaDB implementation)
- Step 5 depends on steps 1-3 (test needs all implementations)
- Step 6 depends on steps 1-3 (exports need implementations)
- Steps 7-8 depend on step 6 (need imports)
- Step 9 can be done anytime after verification
- Step 10 must be last (full integration verification)

## Verification Commands

```bash
# Test OpenLigaDB provider
pytest tests/test_providers_openligadb.py -v

# Test ProviderManager
pytest tests/test_providers_manager.py -v

# Full test suite
pytest tests/ -v

# Verify imports
python -c "from app.providers import OpenLigaDBFootballProvider, ProviderManager, ProviderManagerAdapter"

# Verify config
python -c "from app.config import settings; print(settings.use_real_providers)"

# Verify dependency injection (development mode)
python -c "from app.api.dependencies import get_data_provider; p = next(get_data_provider()); print(p.get_provider_name())"
```

## Expected Test Results

- test_providers_openligadb.py: 10 tests, all passing
- test_providers_manager.py: 9 tests, all passing
- Full suite: All existing tests + 19 new tests, 0 failures

## Reference Patterns

- HTTP/cache/normalization pattern: app/providers/ryzellx.py (complete reference implementation)
- Conservative HTTP pattern: app/providers/fotmob.py (retry_count=1, no aggressive retries)
- Test mocking pattern: tests/test_providers_multi.py (respx for HTTP, AsyncMock for providers)
- Domain mapping pattern: app/providers/development.py (ProviderMatch → Match field mapping)
- Exception handling: app/providers/exceptions.py (ProviderError hierarchy)
- Cache integration: app/providers/cache.py (TTL constants, thread-safe operations)

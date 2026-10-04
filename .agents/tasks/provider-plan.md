# Implementation Plan: Multi-Provider Football Data Abstraction

This plan implements a production-oriented multi-provider football data abstraction for the FootballIntelligence backend with:
- **Ryzellx** (PRIMARY provider)
- **FotMob** (LIVE/FAST provider, unofficial)
- **OpenLigaDB** (INDEPENDENT FALLBACK provider)
- **ProviderManager** with routing policy
- **Normalized domain models** (provider-independent)
- **SOURCE-OF-TRUTH RULE**: one provider per response, never hybrid data

## Architecture Overview

**Files to Create:**
- `backend/app/providers/models.py` — Normalized ProviderXxx models with source metadata
- `backend/app/providers/exceptions.py` — Structured provider exceptions
- `backend/app/providers/cache.py` — Simple in-memory TTL cache
- `backend/app/providers/ryzellx.py` — Ryzellx provider (PRIMARY)
- `backend/app/providers/fotmob.py` — FotMob provider (LIVE/FAST, unofficial)
- `backend/app/providers/openligadb.py` — OpenLigaDB provider (FALLBACK)
- `backend/app/providers/manager.py` — ProviderManager with routing
- `backend/app/providers/adapter.py` — ProviderManagerAdapter (sync wrapper for async ProviderManager)
- `backend/tests/test_providers_multi.py` — Comprehensive tests (mocked HTTP, no real internet)

**Files to Update:**
- `backend/app/providers/__init__.py` — Export new symbols
- `backend/app/config.py` — Add provider configuration settings
- `backend/app/api/dependencies.py` — Integrate ProviderManager (backward-compatible)
- `docs/PROGRESS.md` — Document implementation

**Files to Preserve:**
- `backend/app/providers/base.py` — Keep existing FootballDataProvider interface
- `backend/app/providers/development.py` — Keep DevelopmentProvider unchanged (still default)

---

## Implementation Steps

### FEAT-001: Foundation Layer (Exceptions, Models, Cache)

- [ ] 1. Create structured provider exceptions in `backend/app/providers/exceptions.py`.
      
      Base ProviderError(Exception) with `provider_name: str`, `operation: str`, `message: str` (sanitized, no secrets).
      
      Subclasses:
      - ProviderTimeoutError (timeout during request)
      - ProviderHTTPError (add `status_code: int` for HTTP 4xx/5xx)
      - ProviderInvalidDataError (malformed JSON, schema mismatch)
      - ProviderNotFoundError (HTTP 404 or resource not found)
      
      Files: `backend/app/providers/exceptions.py`
      
      Verify: `pytest backend/tests/test_providers_multi.py::test_provider_exceptions -v` — instantiate each exception, verify fields

- [ ] 2. Create normalized provider-independent Pydantic models in `backend/app/providers/models.py`.
      
      All models include source metadata fields:
      - `provider: str` (e.g., 'ryzellx', 'fotmob', 'openligadb')
      - `source_id: str` (upstream provider's ID)
      - `fetched_at: datetime` (UTC timestamp when fetched)
      - `source_updated_at: Optional[datetime]` (upstream last-updated if available)
      - `is_live: bool` (whether data is from live/ongoing match)
      - `data_freshness_seconds: Optional[int]` (calculated staleness if applicable)
      
      Models:
      - **ProviderMatch**: Maps to domain Match + metadata (home_team_id, away_team_id, scheduled_at, status, home_score, away_score, minute, added_time, outcome, round, xg, xg_against, shots, possession, etc.). Use `Optional[T]` for all fields providers may not supply.
      - **ProviderTeam**: Maps to domain Team + metadata (name, short_name, code, country, founded, venue_id, logo_url).
      - **ProviderPlayer**: Maps to domain Player + metadata (name, date_of_birth, nationality, position, shirt_number, team_id, height_cm, weight_kg, photo_url).
      - **ProviderCompetition**: Maps to domain Competition + metadata (name, country, level, type).
      - **ProviderStanding**: Maps to domain Standing + metadata (team_id, position, played, won, drawn, lost, goals_for, goals_against, goal_difference, points, form).
      - **ProviderMatchEvent**: Maps to domain MatchEvent + metadata (match_id, type, minute, added_time, team_id, player_id, related_player_id, description).
      - **ProviderLineup**: Maps to domain Lineup + metadata (match_id, team_id, formation, starting_xi, substitutes, coach).
      - **ProviderMatchStats**: Team-level match statistics (match_id, team_id, goals_scored, goals_conceded, xg, xg_against, shots_total, shots_on_target, possession_percentage, passes_completed, passes_attempted, corners, yellow_cards, red_cards, etc.).
      - **ProviderShot**: Individual shot data (id, match_id, team_id, player_id, minute, xg, result, coordinates).
      - **ProviderLiveMatch**: Real-time match state (match_id, status, minute, added_time, home_score, away_score, live_events, last_updated).
      
      Use `Optional[T]` for ALL fields that providers may not provide. Never invent placeholder values.
      
      Files: `backend/app/providers/models.py`
      
      Verify: `pytest backend/tests/test_providers_multi.py::test_provider_models -v` — instantiate each model with source metadata, verify Optional fields accept None

- [ ] 3. Create simple in-memory TTL cache in `backend/app/providers/cache.py`.
      
      Class: `ProviderCache`
      
      Methods:
      - `get(key: str) -> Optional[Any]`: Return cached value if exists and not expired, else None
      - `set(key: str, value: Any, ttl_seconds: int)`: Store value with TTL
      - `delete(key: str)`: Remove key
      - `clear()`: Clear all cache
      
      Implementation:
      - Use `dict` for storage: `{key: (value, expiry_timestamp)}`
      - Thread-safe using `threading.Lock`
      - TTL constants: `LIVE_DATA_TTL = 30`, `UPCOMING_FIXTURES_TTL = 300`, `HISTORICAL_MATCH_TTL = 3600`, `METADATA_TTL = 3600`
      
      Files: `backend/app/providers/cache.py`
      
      Verify: `pytest backend/tests/test_providers_multi.py::test_provider_cache -v` — test get/set with expiry, test thread safety

- [ ] 4. Update `backend/app/providers/__init__.py` to export new symbols.
      
      Add exports: `ProviderError`, `ProviderTimeoutError`, `ProviderHTTPError`, `ProviderInvalidDataError`, `ProviderNotFoundError`, `ProviderCache`, all `ProviderXxx` models.
      
      Files: `backend/app/providers/__init__.py`
      
      Verify: `python -c "from app.providers import ProviderError, ProviderMatch, ProviderCache; print('OK')"` — imports work

---

### FEAT-002: Ryzellx Provider (PRIMARY)

- [ ] 5. Create `backend/app/providers/ryzellx.py` with RyzellxFootballProvider class.
      
      Constructor: `__init__(base_url: str, timeout_seconds: float = 10.0, retry_count: int = 2, cache: Optional[ProviderCache] = None)`
      
      Create `httpx.AsyncClient` with `timeout=httpx.Timeout(timeout_seconds)` in constructor.
      
      Docstring: "Ryzellx is the PRIMARY provider for matches, fixtures, results, match detail, teams, players, leagues, standings, xG/stats when available. Base URL is configurable — no hardcoded production URLs."
      
      Files: `backend/app/providers/ryzellx.py`
      
      Verify: Instantiate RyzellxFootballProvider, verify constructor stores parameters

- [ ] 6. Implement async `_request(method: str, endpoint: str, params: Optional[dict] = None) -> dict` helper in RyzellxFootballProvider.
      
      Error handling:
      - `httpx.TimeoutException` → raise `ProviderTimeoutError(provider_name='ryzellx', operation=endpoint, message='Request timeout')`
      - `httpx.HTTPStatusError` with 4xx → raise `ProviderNotFoundError` (404) or `ProviderHTTPError` (other 4xx)
      - `httpx.HTTPStatusError` with 5xx → retry up to `retry_count`, then raise `ProviderHTTPError(provider_name='ryzellx', operation=endpoint, message='...', status_code=5xx)`
      - `httpx.RequestError` (connection error) → retry up to `retry_count`, then raise `ProviderError`
      - `json.JSONDecodeError` → raise `ProviderInvalidDataError(provider_name='ryzellx', operation=endpoint, message='Invalid JSON response')`
      
      Log all requests and errors (without exposing secrets/tokens).
      
      Files: `backend/app/providers/ryzellx.py`
      
      Verify: `pytest backend/tests/test_providers_multi.py::test_ryzellx_error_handling -v` — mock timeout, HTTP 404, HTTP 500, invalid JSON, verify correct exceptions

- [ ] 7. Implement async `get_matches_by_date(date: date) -> List[ProviderMatch]` in RyzellxFootballProvider.
      
      Call: `GET /api/matches/date/{date.isoformat()}`
      
      Parse JSON response, normalize each match to `ProviderMatch` with:
      - `provider='ryzellx'`
      - `source_id=<upstream_match_id>`
      - `fetched_at=datetime.now(timezone.utc)`
      - `is_live=False` (date-based queries are typically scheduled/finished)
      - All match fields mapped from response (use `None` for unavailable fields, especially xG, stats)
      
      Cache: Check `cache.get(f'ryzellx:matches:date:{date}')` before request. If miss, fetch and `cache.set(key, matches, ttl=UPCOMING_FIXTURES_TTL if date >= today else HISTORICAL_MATCH_TTL)`.
      
      Files: `backend/app/providers/ryzellx.py`
      
      Verify: `pytest backend/tests/test_providers_multi.py::test_ryzellx_get_matches_by_date -v` — mock httpx response, verify normalization, verify source metadata, verify cache

- [ ] 8. Implement async `get_matches_by_range(start_date: date, end_date: date) -> List[ProviderMatch]` in RyzellxFootballProvider.
      
      Call: `GET /api/matches/range?start={start_date}&end={end_date}`
      
      Normalize to `List[ProviderMatch]` with source metadata.
      
      Cache: `f'ryzellx:matches:range:{start_date}:{end_date}'`, TTL based on date range.
      
      Files: `backend/app/providers/ryzellx.py`
      
      Verify: `pytest backend/tests/test_providers_multi.py::test_ryzellx_get_matches_by_range -v`

- [ ] 9. Implement async `get_match(match_id: str) -> Optional[ProviderMatch]` in RyzellxFootballProvider.
      
      Call: `GET /api/match/{match_id}`
      
      Return `None` if 404. Normalize to `ProviderMatch` with all available fields (score, xG if present, stats if present). If xG not in response, set `xg=None`, `xg_against=None` — do NOT invent values.
      
      Cache: `f'ryzellx:match:{match_id}'`, TTL: `LIVE_DATA_TTL` if `is_live=True` else `HISTORICAL_MATCH_TTL`.
      
      Files: `backend/app/providers/ryzellx.py`
      
      Verify: `pytest backend/tests/test_providers_multi.py::test_ryzellx_get_match -v` — verify xG=None when not in response (no invented values)

- [ ] 10. Implement async `get_live_matches() -> List[ProviderLiveMatch]` in RyzellxFootballProvider.
      
      Call: `GET /api/matches/live`
      
      Normalize to `List[ProviderLiveMatch]` with source metadata, `is_live=True`.
      
      Cache: `'ryzellx:matches:live'`, TTL: `LIVE_DATA_TTL`.
      
      Files: `backend/app/providers/ryzellx.py`
      
      Verify: `pytest backend/tests/test_providers_multi.py::test_ryzellx_get_live_matches -v`

- [ ] 11. Implement async `get_team(team_id: str) -> Optional[ProviderTeam]` in RyzellxFootballProvider.
      
      Call: `GET /api/team/{team_id}`
      
      Return `None` if 404. Normalize to `ProviderTeam`.
      
      Cache: `f'ryzellx:team:{team_id}'`, TTL: `METADATA_TTL`.
      
      Files: `backend/app/providers/ryzellx.py`
      
      Verify: `pytest backend/tests/test_providers_multi.py::test_ryzellx_get_team -v`

- [ ] 12. Implement async `get_player(player_id: str) -> Optional[ProviderPlayer]`, `get_league(league_id: str) -> Optional[ProviderCompetition]`, `get_standings(league_id: str) -> List[ProviderStanding]` in RyzellxFootballProvider.
      
      Endpoints:
      - `GET /api/player/{player_id}` → `ProviderPlayer`
      - `GET /api/league/{league_id}` → `ProviderCompetition`
      - `GET /api/league/{league_id}/table` → `List[ProviderStanding]`
      
      Normalize with source metadata. Cache with appropriate TTLs.
      
      Files: `backend/app/providers/ryzellx.py`
      
      Verify: `pytest backend/tests/test_providers_multi.py::test_ryzellx_metadata -v` — test player, league, standings

---

### FEAT-003: FotMob Provider (LIVE/FAST, Unofficial)

- [ ] 13. Create `backend/app/providers/fotmob.py` with FotMobFootballProvider class.
      
      Module docstring: "# Unofficial FotMob Integration\n\n⚠️ This is NOT an official FotMob API integration.\n\nThis provider uses publicly accessible FotMob JSON endpoints for live/fast data.\nRequest volume must be conservative. No bypasses, no anti-bot evasion, no scraping tricks.\nIf a request fails, return structured provider failure — never invent data."
      
      Constructor: `__init__(base_url: str, timeout_seconds: float = 10.0, retry_count: int = 1, cache: Optional[ProviderCache] = None)` — note `retry_count=1` (conservative).
      
      Docstring: "FotMob is the LIVE/FAST provider for real-time match data where it provides fresher information than Ryzellx. Unofficial integration — conservative request patterns only."
      
      Files: `backend/app/providers/fotmob.py`
      
      Verify: Instantiate FotMobFootballProvider, verify constructor

- [ ] 14. Implement async `_request(method: str, endpoint: str, params: Optional[dict] = None) -> dict` helper in FotMobFootballProvider.
      
      Same error handling as Ryzellx, but with `retry_count=1` (conservative retry policy for unofficial integration).
      
      Files: `backend/app/providers/fotmob.py`
      
      Verify: `pytest backend/tests/test_providers_multi.py::test_fotmob_error_handling -v`

- [ ] 15. Implement async `get_matches_by_date(date: date) -> List[ProviderMatch]` in FotMobFootballProvider.
      
      Map to FotMob daily matches endpoint (typically `/api/matches?date={date}`). Adjust endpoint based on actual FotMob API structure.
      
      Normalize to `List[ProviderMatch]` with `provider='fotmob'`, `is_live` based on match status.
      
      Cache: `f'fotmob:matches:date:{date}'`, TTL: `LIVE_DATA_TTL` if `date == today` else `UPCOMING_FIXTURES_TTL`.
      
      Files: `backend/app/providers/fotmob.py`
      
      Verify: `pytest backend/tests/test_providers_multi.py::test_fotmob_get_matches_by_date -v`

- [ ] 16. Implement async `get_match(match_id: str) -> Optional[ProviderMatch]` in FotMobFootballProvider.
      
      Map to FotMob match details endpoint (typically `/api/matchDetails?matchId={match_id}`).
      
      Return `None` if 404. Normalize to `ProviderMatch` with live data (minute, score, events if present).
      
      Cache: `f'fotmob:match:{match_id}'`, TTL: `LIVE_DATA_TTL`.
      
      Files: `backend/app/providers/fotmob.py`
      
      Verify: `pytest backend/tests/test_providers_multi.py::test_fotmob_get_match -v`

- [ ] 17. Implement async `get_live_matches() -> List[ProviderLiveMatch]` in FotMobFootballProvider.
      
      Map to FotMob live matches endpoint. Normalize to `List[ProviderLiveMatch]`.
      
      Cache: `'fotmob:matches:live'`, TTL: `LIVE_DATA_TTL`.
      
      Files: `backend/app/providers/fotmob.py`
      
      Verify: `pytest backend/tests/test_providers_multi.py::test_fotmob_get_live_matches -v`

- [ ] 18. Implement stub methods in FotMobFootballProvider: `get_league`, `get_team`, `get_player`, `get_standings`.
      
      All return `None` or empty list with docstring comments: "# FotMob league/team/player/standings lookup not implemented — use Ryzellx or OpenLigaDB for metadata."
      
      Files: `backend/app/providers/fotmob.py`
      
      Verify: Call stub methods, verify they return None/empty

---

### FEAT-004: OpenLigaDB Provider (FALLBACK)

- [ ] 19. Create `backend/app/providers/openligadb.py` with OpenLigaDBFootballProvider class.
      
      Docstring: "OpenLigaDB is the INDEPENDENT FALLBACK provider. Provides leagues, matches, match details, standings where supported. Does NOT provide advanced metrics (xG, detailed stats) — these fields will be None."
      
      Constructor: `__init__(base_url: str, timeout_seconds: float = 10.0, retry_count: int = 2, cache: Optional[ProviderCache] = None)`
      
      Files: `backend/app/providers/openligadb.py`
      
      Verify: Instantiate OpenLigaDBFootballProvider, verify constructor

- [ ] 20. Implement async `_request(method: str, endpoint: str, params: Optional[dict] = None) -> Union[dict, list]` helper in OpenLigaDBFootballProvider.
      
      Same error handling as Ryzellx.
      
      Files: `backend/app/providers/openligadb.py`
      
      Verify: `pytest backend/tests/test_providers_multi.py::test_openligadb_error_handling -v`

- [ ] 21. Implement async `get_league(league_id: str) -> Optional[ProviderCompetition]` in OpenLigaDBFootballProvider.
      
      Map `league_id` to OpenLigaDB `leagueShortcut` (e.g., 'bl1' for Bundesliga). Call `GET /getavailableleagues`. Find matching league, normalize to `ProviderCompetition`. Return `None` if not found.
      
      Cache: `f'openligadb:league:{league_id}'`, TTL: `METADATA_TTL`.
      
      Files: `backend/app/providers/openligadb.py`
      
      Verify: `pytest backend/tests/test_providers_multi.py::test_openligadb_get_league -v`

- [ ] 22. Implement async `get_match(match_id: str) -> Optional[ProviderMatch]` in OpenLigaDBFootballProvider.
      
      Call `GET /getmatchdata/{match_id}`.
      
      Normalize to `ProviderMatch`. **IMPORTANT**: Explicitly set `xg=None`, `xg_against=None`, detailed stats to `None` because OpenLigaDB does not provide them. Add comment in code: "# OpenLigaDB does not provide xG or detailed stats — set to None."
      
      Cache: `f'openligadb:match:{match_id}'`, TTL: `HISTORICAL_MATCH_TTL`.
      
      Files: `backend/app/providers/openligadb.py`
      
      Verify: `pytest backend/tests/test_providers_multi.py::test_openligadb_no_xg -v` — verify xG=None, no invented values

- [ ] 23. Implement async `get_matches_by_date(date: date) -> List[ProviderMatch]` and `get_matches_by_range(start_date: date, end_date: date) -> List[ProviderMatch]` in OpenLigaDBFootballProvider.
      
      OpenLigaDB does not have direct date-based endpoints. Return empty list with docstring comment: "# OpenLigaDB does not support direct date-based queries. Use get_match or league-based queries."
      
      This is acceptable because OpenLigaDB is a fallback provider.
      
      Files: `backend/app/providers/openligadb.py`
      
      Verify: Call methods, verify they return empty list

- [ ] 24. Implement async `get_standings(league_id: str) -> List[ProviderStanding]` in OpenLigaDBFootballProvider.
      
      If OpenLigaDB exposes standings via its data model, normalize to `List[ProviderStanding]`. If not available, return empty list with comment.
      
      Files: `backend/app/providers/openligadb.py`
      
      Verify: `pytest backend/tests/test_providers_multi.py::test_openligadb_get_standings -v`

- [ ] 25. Implement stub methods in OpenLigaDBFootballProvider: `get_team`, `get_player`, `get_live_matches`.
      
      Return `None` or empty list with docstring comments explaining OpenLigaDB limitations.
      
      Files: `backend/app/providers/openligadb.py`
      
      Verify: Call stub methods, verify they return None/empty

---

### FEAT-005: ProviderManager with Routing

- [ ] 26. Create `backend/app/providers/manager.py` with ProviderManager class.
      
      Constructor: `__init__(ryzellx: RyzellxFootballProvider, fotmob: FotMobFootballProvider, openligadb: OpenLigaDBFootballProvider, cache: Optional[ProviderCache] = None)`
      
      Define routing policy as class constants:
      - `NORMAL_ORDER = ['ryzellx', 'openligadb']`
      - `LIVE_ORDER = ['fotmob', 'ryzellx', 'openligadb']`
      - `MATCH_DETAIL_ORDER = ['ryzellx', 'fotmob', 'openligadb']`
      - `METADATA_ORDER = ['ryzellx', 'fotmob', 'openligadb']`
      
      Docstring: "ProviderManager routes requests to appropriate providers based on data type. SOURCE-OF-TRUTH RULE: For every response, ONE provider is selected as the authoritative source. Never produce hybrid results mixing data from multiple providers (e.g., Ryzellx score + FotMob xG). Choose one provider response, attach source metadata, return that normalized result. Failover only on exception or None result — NOT on missing optional field (xG=None is valid, not a failover trigger)."
      
      Files: `backend/app/providers/manager.py`
      
      Verify: Instantiate ProviderManager, verify constructor stores providers

- [ ] 27. Implement async `_try_providers(operation: str, provider_order: List[str], provider_method_map: dict[str, Callable]) -> Tuple[Optional[Any], dict[str, Any]]` helper in ProviderManager.
      
      Logic:
      1. Initialize metadata: `attempted_providers = []`, `provider_error = None`
      2. For each `provider_name` in `provider_order`:
         a. Append `provider_name` to `attempted_providers`
         b. Try `result = await provider_method_map[provider_name]()`
         c. On success (result is not None, or for list results, result is not empty): return `(result, {selected_provider: provider_name, attempted_providers, fallback_used: len(attempted_providers) > 1, fetched_at: datetime.now(UTC), provider_error: None})`
         d. On `ProviderTimeoutError`, `ProviderHTTPError`, `ProviderInvalidDataError`, `ProviderError`: log error, set `provider_error` to sanitized message, continue to next provider
         e. On `None` result when data is required: continue to next provider
      3. If all providers fail: return `(None, {selected_provider: None, attempted_providers, fallback_used: True, fetched_at: datetime.now(UTC), provider_error: <last_error>})`
      
      **CRITICAL**: Do NOT failover if result is valid but has optional field = None (e.g., `ProviderMatch` with `xg=None` is VALID, keep as source).
      
      Files: `backend/app/providers/manager.py`
      
      Verify: `pytest backend/tests/test_providers_multi.py::test_provider_manager_try_providers -v`

- [ ] 28. Implement async `get_matches_by_date(date: date) -> Tuple[List[ProviderMatch], dict]` in ProviderManager.
      
      Use `NORMAL_ORDER`. Provider method map:
      ```python
      {
        'ryzellx': lambda: self.ryzellx.get_matches_by_date(date),
        'openligadb': lambda: self.openligadb.get_matches_by_date(date),
        'fotmob': lambda: self.fotmob.get_matches_by_date(date),
      }
      ```
      
      Call `_try_providers('get_matches_by_date', NORMAL_ORDER, provider_method_map)`. Return `(matches, metadata)`.
      
      Files: `backend/app/providers/manager.py`
      
      Verify: `pytest backend/tests/test_providers_multi.py::test_provider_manager_get_matches_by_date -v` — verify Ryzellx tried first, metadata correct

- [ ] 29. Implement async `get_match(match_id: str, prefer_live: bool = False) -> Tuple[Optional[ProviderMatch], dict]` in ProviderManager.
      
      If `prefer_live=True`, use `LIVE_ORDER`; else use `MATCH_DETAIL_ORDER`.
      
      Provider method map for all three providers.
      
      Call `_try_providers`. Return `(match, metadata)`.
      
      Files: `backend/app/providers/manager.py`
      
      Verify: `pytest backend/tests/test_providers_multi.py::test_provider_manager_get_match -v` — verify prefer_live changes order, metadata correct

- [ ] 30. Implement async `get_live_matches() -> Tuple[List[ProviderLiveMatch], dict]` in ProviderManager.
      
      Use `LIVE_ORDER`. Provider method map: `{'fotmob': ..., 'ryzellx': ..., 'openligadb': lambda: []}`.
      
      Return `(matches, metadata)`.
      
      Files: `backend/app/providers/manager.py`
      
      Verify: `pytest backend/tests/test_providers_multi.py::test_provider_manager_get_live_matches -v` — verify FotMob tried first

- [ ] 31. Implement async `get_team(team_id: str) -> Tuple[Optional[ProviderTeam], dict]`, `get_player(player_id: str)`, `get_league(league_id: str)`, `get_standings(league_id: str)` in ProviderManager.
      
      All use `METADATA_ORDER`. Provider method maps for Ryzellx, FotMob (where supported), OpenLigaDB (where supported).
      
      Return `(result, metadata)`.
      
      Files: `backend/app/providers/manager.py`
      
      Verify: `pytest backend/tests/test_providers_multi.py::test_provider_manager_metadata -v`

- [ ] 32. Update `backend/app/providers/__init__.py` to export ProviderManager.
      
      Files: `backend/app/providers/__init__.py`
      
      Verify: `python -c "from app.providers import ProviderManager; print('OK')"` — import works

---

### FEAT-006: Configuration, Integration, Tests, Documentation

- [ ] 33. Update `backend/app/config.py` Settings class with provider configuration.
      
      Add fields:
      ```python
      # Provider configuration
      ryzellx_base_url: str = "http://localhost:8080"  # Safe default for local development
      fotmob_base_url: str = "https://www.fotmob.com"
      openligadb_base_url: str = "https://api.openligadb.de"
      provider_timeout_seconds: float = 10.0
      provider_retry_count: int = 2
      live_provider_order: list[str] = Field(default_factory=lambda: ["fotmob", "ryzellx", "openligadb"])
      default_provider_order: list[str] = Field(default_factory=lambda: ["ryzellx", "openligadb"])
      use_real_providers: bool = False  # False = use DevelopmentProvider; True = use ProviderManager
      ```
      
      Add comments explaining safe defaults and zero-budget architecture (no API keys required).
      
      Files: `backend/app/config.py`
      
      Verify: `python -c "from app.config import settings; print(settings.ryzellx_base_url)"` — config loads

- [ ] 34. Create `backend/app/providers/adapter.py` with ProviderManagerAdapter class.
      
      Implements `FootballDataProvider` interface (sync methods) by wrapping ProviderManager async methods with `asyncio.run()`.
      
      Methods:
      - `get_provider_name() -> str`: Return `f"ProviderManager ({self._last_metadata.get('selected_provider', 'unknown')})"`
      - `is_development_data() -> bool`: Return `False`
      - `get_competitions() -> List[Competition]`: Not implemented (raise NotImplementedError with comment)
      - `get_matches(...) -> List[Match]`: Call `asyncio.run(self.manager.get_matches_by_date(from_date))`, map `ProviderMatch` → `Match` domain model, return
      - `get_match(match_id: str) -> Optional[Match]`: Call `asyncio.run(self.manager.get_match(match_id))`, map `ProviderMatch` → `Match`, return
      - Other methods: map ProviderTeam → Team, ProviderPlayer → Player, etc.
      
      Store `_last_metadata` dict for exposing selected_provider in `get_provider_name()`.
      
      Files: `backend/app/providers/adapter.py`
      
      Verify: Instantiate adapter with mock ProviderManager, call sync methods, verify they work

- [ ] 35. Update `backend/app/api/dependencies.py` get_data_provider() to integrate ProviderManager.
      
      Logic:
      ```python
      from app.config import settings
      from app.providers import DevelopmentProvider, ProviderCache, RyzellxFootballProvider, FotMobFootballProvider, OpenLigaDBFootballProvider, ProviderManager
      from app.providers.adapter import ProviderManagerAdapter
      
      def get_data_provider() -> Generator[FootballDataProvider, None, None]:
          if not settings.use_real_providers:
              # Backward-compatible default: use DevelopmentProvider
              provider = DevelopmentProvider()
              yield provider
          else:
              # Use real providers via ProviderManager
              cache = ProviderCache()
              ryzellx = RyzellxFootballProvider(
                  base_url=settings.ryzellx_base_url,
                  timeout_seconds=settings.provider_timeout_seconds,
                  retry_count=settings.provider_retry_count,
                  cache=cache,
              )
              fotmob = FotMobFootballProvider(
                  base_url=settings.fotmob_base_url,
                  timeout_seconds=settings.provider_timeout_seconds,
                  retry_count=1,  # Conservative for unofficial
                  cache=cache,
              )
              openligadb = OpenLigaDBFootballProvider(
                  base_url=settings.openligadb_base_url,
                  timeout_seconds=settings.provider_timeout_seconds,
                  retry_count=settings.provider_retry_count,
                  cache=cache,
              )
              manager = ProviderManager(ryzellx, fotmob, openligadb, cache)
              adapter = ProviderManagerAdapter(manager)
              yield adapter
      ```
      
      **IMPORTANT**: Do NOT modify `backend/app/api/v1/endpoints/matches.py` or change API response contracts. The adapter ensures existing endpoint code continues working unchanged.
      
      Files: `backend/app/api/dependencies.py`
      
      Verify: Start app with `use_real_providers=False`, call API endpoint, verify DevelopmentProvider still works

- [ ] 36. Create comprehensive test file `backend/tests/test_providers_multi.py`.
      
      Use pytest with httpx mocking (respx library if available, else httpx MockTransport). NEVER hit real internet.
      
      Test categories:
      
      **Exceptions:**
      - `test_provider_exceptions`: Instantiate each ProviderError subclass, verify `provider_name`, `operation`, `message` fields
      
      **Models:**
      - `test_provider_models`: Instantiate each ProviderXxx model with source metadata, verify all fields, verify Optional fields accept None
      
      **Cache:**
      - `test_provider_cache`: Test get/set with TTL expiry, test thread safety (use threading to test concurrent access)
      
      **Ryzellx:**
      - `test_ryzellx_get_matches_by_date`: Mock httpx response for `/api/matches/date/{date}`, verify normalization to ProviderMatch, verify source metadata (`provider='ryzellx'`, `fetched_at`, etc.)
      - `test_ryzellx_get_match`: Mock response, verify xG=None when not in response (no invented values)
      - `test_ryzellx_error_handling`: Mock timeout → ProviderTimeoutError, HTTP 404 → ProviderNotFoundError, HTTP 500 with retry → ProviderHTTPError, invalid JSON → ProviderInvalidDataError
      - `test_ryzellx_cache`: Verify cache hit/miss behavior
      
      **FotMob:**
      - `test_fotmob_get_matches_by_date`: Mock response, verify normalization
      - `test_fotmob_get_match`: Mock response, verify live data normalization
      - `test_fotmob_error_handling`: Similar to Ryzellx
      
      **OpenLigaDB:**
      - `test_openligadb_get_match`: Mock response, verify xG=None, stats=None (no invented values)
      - `test_openligadb_no_xg`: Explicitly test that OpenLigaDB never provides xG
      
      **ProviderManager:**
      - `test_provider_manager_routing`: Verify NORMAL uses Ryzellx first, LIVE uses FotMob first
      - `test_provider_manager_failover`: Mock Ryzellx timeout, verify OpenLigaDB is tried, verify metadata (`attempted_providers`, `fallback_used=True`, `provider_error`)
      - `test_provider_manager_no_failover_on_none_xg`: Mock Ryzellx returning match with xG=None, verify ProviderManager returns that match without trying fallback (xG=None is valid, not a failover trigger)
      - `test_provider_manager_source_of_truth`: Verify each response comes from ONE provider, never hybrid data
      
      Files: `backend/tests/test_providers_multi.py`
      
      Verify: `pytest backend/tests/test_providers_multi.py -v` — expect all pass

- [ ] 37. Run `pytest backend/tests/test_providers_multi.py -v` and fix all failures.
      
      Ensure tests are deterministic (same result every run, no flakiness).
      
      Files: All provider implementation files
      
      Verify: `pytest backend/tests/test_providers_multi.py -v` — all tests pass

- [ ] 38. Run `pytest backend/tests/ -v` to verify all existing tests still pass (no regressions).
      
      If any fail, diagnose and fix. Common issue: tests may need adjustments if domain models changed, but existing tests should mostly pass unchanged because DevelopmentProvider is still the default (`use_real_providers=False`).
      
      Files: Any files causing regressions
      
      Verify: `pytest backend/tests/ -v` — all tests pass

- [ ] 39. Update `docs/PROGRESS.md` with comprehensive implementation entry.
      
      Append:
      ```markdown
      ## Multi-Provider Football Data Abstraction
      
      **Date:** {current_date}
      
      **Implemented:**
      - Provider-independent normalized models (ProviderMatch, ProviderTeam, ProviderPlayer, ProviderCompetition, ProviderStanding, ProviderMatchEvent, ProviderLineup, ProviderMatchStats, ProviderShot, ProviderLiveMatch) with source metadata (provider, source_id, fetched_at, is_live, data_freshness_seconds)
      - Structured provider exceptions (ProviderError, ProviderTimeoutError, ProviderHTTPError, ProviderInvalidDataError, ProviderNotFoundError)
      - Simple in-memory TTL cache (ProviderCache) with thread safety
      - RyzellxFootballProvider (PRIMARY provider): async httpx client, all documented endpoints (/api/matches/date, /api/matches/range, /api/match, /api/matches/live, /api/team, /api/player, /api/leagues, /api/league/table), normalization, retry logic for transient failures, cache integration
      - FotMobFootballProvider (LIVE/FAST provider, unofficial): daily matches, match details, live data — conservative request patterns, no bypasses
      - OpenLigaDBFootballProvider (INDEPENDENT FALLBACK): leagues, matches, standings — explicitly does NOT provide xG/advanced stats (None for unavailable fields)
      - ProviderManager with routing policy: NORMAL [Ryzellx, OpenLigaDB]; LIVE [FotMob, Ryzellx, OpenLigaDB]; MATCH_DETAIL [Ryzellx, FotMob, OpenLigaDB]; METADATA [Ryzellx, FotMob, OpenLigaDB]
      - SOURCE-OF-TRUTH RULE enforced: each response from ONE provider, never hybrid data
      - Failover on timeout/HTTP error/invalid data, NOT on missing optional field (xG=None is valid)
      - ProviderManagerAdapter wraps async ProviderManager for sync FootballDataProvider interface — backward-compatible, no endpoint changes
      - Configuration: ryzellx_base_url, fotmob_base_url, openligadb_base_url, provider_timeout_seconds, provider_retry_count, use_real_providers (default False = DevelopmentProvider)
      - Comprehensive tests: 100% mocked HTTP (no real internet), deterministic, covers normalization, error handling, routing, failover, source-of-truth
      
      **Provider Roles:**
      - Ryzellx: PRIMARY for matches, fixtures, results, match detail, teams, players, leagues, standings, xG/stats when available
      - FotMob: LIVE/FAST for real-time match data (unofficial integration)
      - OpenLigaDB: INDEPENDENT FALLBACK for German leagues, basic match data (no xG)
      
      **Failover Behavior:**
      - Triggers: timeout, HTTP 4xx/5xx, invalid JSON, connection error
      - Does NOT trigger on missing optional field (xG=None keeps primary provider as source)
      
      **Configuration Variables:**
      - RYZELLX_BASE_URL (default: http://localhost:8080)
      - FOTMOB_BASE_URL (default: https://www.fotmob.com)
      - OPENLIGADB_BASE_URL (default: https://api.openligadb.de)
      - PROVIDER_TIMEOUT_SECONDS (default: 10.0)
      - PROVIDER_RETRY_COUNT (default: 2)
      - USE_REAL_PROVIDERS (default: False — DevelopmentProvider remains default)
      
      **Test Results:**
      - pytest backend/tests/test_providers_multi.py: {insert_result}
      - pytest backend/tests/: {insert_result}
      - All tests deterministic, no real internet requests
      
      **Next Steps:**
      - Set USE_REAL_PROVIDERS=True and configure provider base URLs when ready to use real data
      - Monitor provider performance and cache hit rates
      - Add provider metrics/observability if needed
      - Consider rate limiting for FotMob (unofficial integration)
      ```
      
      Files: `docs/PROGRESS.md`
      
      Verify: Read `docs/PROGRESS.md`, confirm entry exists with test results

---

## Summary

This plan implements a production-oriented multi-provider football data abstraction with:

✅ **Foundation**: Normalized models, structured exceptions, TTL cache
✅ **Ryzellx Provider**: PRIMARY for matches, teams, players, leagues, xG/stats
✅ **FotMob Provider**: LIVE/FAST for real-time data (unofficial, conservative)
✅ **OpenLigaDB Provider**: FALLBACK for German leagues (no xG)
✅ **ProviderManager**: Routing policy, failover, SOURCE-OF-TRUTH enforcement
✅ **Integration**: Backward-compatible (DevelopmentProvider still default)
✅ **Tests**: Comprehensive, deterministic, 100% mocked HTTP
✅ **Documentation**: Configuration, progress tracking

**Verification**: All steps include verification commands. Run tests after each step to ensure correctness.

**CRITICAL RULES**:
- Never invent values — use None for unavailable fields
- SOURCE-OF-TRUTH: one provider per response, never hybrid
- Failover only on exception, NOT on missing optional field (xG=None is valid)
- DevelopmentProvider remains default (use_real_providers=False)
- No real internet in tests — 100% mocked HTTP

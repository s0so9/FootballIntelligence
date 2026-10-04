# Implementation Plan: MENSIONE Backend Intelligence Pipeline

This plan builds a production-grade football intelligence pipeline on top of the existing multi-provider architecture.

**Architecture Flow:**
```
ProviderManager output → INGESTION → DATABASE → FEATURE ENGINEERING → PREDICTION ENGINE → API response
```

**Existing Architecture Preserved:**
- Frontend → FastAPI → ProviderManager → (Ryzellx/FotMob/OpenLigaDB) → ProviderMatch/ProviderTeam/etc
- ProviderManager implements SOURCE-OF-TRUTH rule (no field-level failover)
- ProviderModels include metadata: provider, source_id, fetched_at, source_updated_at, is_live
- Existing PredictionService, AnalysisContext, ensemble architecture

---

## FEAT-001: Database Persistence Layer

**Objective:** Implement SQLAlchemy ORM models, Alembic migrations, repositories with idempotent upserts.

### Steps

- [ ] 1. Configure Alembic: Initialize with `alembic init alembic`, configure alembic.ini and alembic/env.py to use settings.database_url.

- [ ] 2. Create database/base.py: Define Base, TimestampMixin (created_at/updated_at UTC), BaseModel with UUID ID generation.

- [ ] 3. Create database/models.py: Implement SQLAlchemy ORM models:
  - ProviderSource (id, name, base_url, is_active, last_seen_at)
  - Competition (id, provider_source_id FK, provider_id, name, country, level, type, season, logo_url, timestamps)
  - Team (id, provider_source_id FK, provider_id, name, short_name, code, country, founded, venue_name, logo_url, timestamps)
  - Player (id, provider_source_id FK, provider_id, name, date_of_birth, nationality, position, shirt_number, team_id FK, height_cm, weight_kg, photo_url, timestamps)
  - Match (id, provider_source_id FK, provider_id, competition_id FK, home_team_id FK, away_team_id FK, scheduled_at, status, scores, minute, outcome, round, venue_name, timestamps, provider_fetched_at, provider_updated_at)
  - MatchEvent (id, provider_source_id FK, provider_id, match_id FK, type, minute, team_id FK, player_id FK, related_player_id FK, description, timestamps, provider_fetched_at)
  - Standing (id, provider_source_id FK, provider_id, competition_id FK, team_id FK, season, position, played, won, drawn, lost, goals_for/against, goal_difference, points, home/away splits, form, timestamps, provider_fetched_at)
  - MatchStatistic (id, provider_source_id FK, provider_id, match_id FK, team_id FK, goals, xg, xg_against, shots, possession, passes, corners, cards, fouls, tackles, interceptions, clearances, saves, timestamps, provider_fetched_at)
  - All models have composite unique constraints on (provider_source_id, provider_id) where applicable.

- [ ] 4. Create database/session.py: Implement get_engine(), get_session_factory(), get_db() FastAPI dependency.

- [ ] 5. Create database/repository.py: Implement BaseRepository with upsert_by_provider_id (idempotent upsert based on composite key, updates updated_at on conflict), get_by_provider_id. Implement domain-specific repositories: CompetitionRepository, TeamRepository, PlayerRepository, MatchRepository, MatchEventRepository, StandingRepository, MatchStatisticRepository with query methods (e.g., get_team_matches_before_date).

- [ ] 6. Update database/__init__.py: Export Base, session factory, repositories.

- [ ] 7. Generate initial Alembic migration: `alembic revision --autogenerate -m "Initial schema"`. Review migration file. DO NOT apply yet.

- [ ] 8. Update .env.example: Add DATABASE_URL with PostgreSQL template and SQLite fallback comment. Update config.py if needed.

- [ ] 9. Create tests/test_database.py: Test Base.metadata, TimestampMixin, upsert_by_provider_id (create, update, preserves created_at, updates updated_at, handles different provider_source with same provider_id), get_by_provider_id, repository queries. Use in-memory SQLite, run migrations in setUp.

**Files:** database/base.py, database/models.py, database/session.py, database/repository.py, database/__init__.py, alembic/, tests/test_database.py

**Verify:** `cd c:\FootballIntelligence\backend && .venv\Scripts\python.exe -m pytest tests/test_database.py -v`

---

## FEAT-002: Ingestion Layer

**Objective:** Build ingestion service that consumes ProviderModels and persists to database with deduplication, metadata preservation, and no data loss.

### Steps

- [ ] 1. Create ingestion/__init__.py.

- [ ] 2. Create ingestion/deduplication.py: Implement DeduplicationChecker with is_duplicate (checks (provider_source_id, provider_id) exists), should_update (new_fetched_at > existing OR new_updated_at > existing), should_preserve_field (returns True if existing_value is not None and new_value is None—NEVER overwrite valid data with None).

- [ ] 3. Create ingestion/match_ingestion.py: Implement MatchIngester.ingest_match(session, provider_match: ProviderMatch): resolve provider_source_id, check deduplication, create/update Competition and Team if missing, upsert Match via MatchRepository, preserve all provider metadata, apply should_preserve_field for optional fields. Implement ingest_matches for batch.

- [ ] 4. Create ingestion/metadata_ingestion.py: Implement MetadataIngester with ingest_competition, ingest_team, ingest_player. Each resolves provider_source_id, upserts, preserves metadata, applies should_preserve_field.

- [ ] 5. Create ingestion/live_ingestion.py: Implement LiveIngester with ingest_live_match (updates Match with current score/minute/status), ingest_match_event (upserts MatchEvent, handles out-of-order events by checking provider_fetched_at, no duplicate events).

- [ ] 6. Create ingestion/statistics_ingestion.py: Implement StatisticsIngester with ingest_match_statistics, ingest_standing. Use should_preserve_field for xG and optional metrics.

- [ ] 7. Create ingestion/service.py: Implement IngestionService(session_factory) coordinating all ingesters. Provide methods: ingest_provider_matches, ingest_provider_competitions, ingest_provider_teams, ingest_provider_standings, ingest_provider_match_stats, ingest_provider_live_match, ingest_provider_events. Each opens session, calls ingester, commits, handles exceptions with rollback.

- [ ] 8. Update app/main.py: Add startup event to initialize IngestionService, store in app.state.ingestion_service.

- [ ] 9. Create tests/test_ingestion.py: Test MatchIngester (new match creates entities, duplicate updates preserves created_at, None doesn't overwrite valid xG, different provider creates separate record). Test LiveIngester out-of-order events. Test StatisticsIngester partial data. Test IngestionService end-to-end. Use in-memory SQLite.

**Files:** ingestion/deduplication.py, ingestion/match_ingestion.py, ingestion/metadata_ingestion.py, ingestion/live_ingestion.py, ingestion/statistics_ingestion.py, ingestion/service.py, ingestion/__init__.py, app/main.py (updated), tests/test_ingestion.py

**Verify:** `cd c:\FootballIntelligence\backend && .venv\Scripts\python.exe -m pytest tests/test_ingestion.py -v`

---

## FEAT-003: Latency Instrumentation

**Objective:** Track real-time data freshness and processing latency with nullable metrics and clock skew detection.

### Steps

- [ ] 1. Create latency/__init__.py.

- [ ] 2. Create latency/models.py: Define LatencyMetrics Pydantic model with fields: provider_event_timestamp, provider_received_timestamp, processing_timestamp, stored_timestamp, api_timestamp, provider_to_mensione_ms, processing_ms, storage_ms, backend_to_frontend_ms, total_latency_ms, has_clock_skew, has_future_timestamp, is_realtime, data_age_seconds, event_id, notes (all Optional except booleans). Include validation: detect future timestamps (> now + 5s grace), detect unreasonable skew (> 60s between adjacent stages).

- [ ] 3. Create latency/tracker.py: Implement LatencyTracker with track_provider_response (extracts provider_event_timestamp from source_updated_at if authoritative, provider_received_timestamp from fetched_at, processing_timestamp=now, calculates provider_to_mensione_ms, detects future timestamps and clock skew), track_storage (adds stored_timestamp, calculates storage_ms), track_api_response (adds api_timestamp, calculates backend_to_frontend_ms and total_latency_ms), get_data_age_seconds.

- [ ] 4. Update ingestion/service.py: Call LatencyTracker.track_provider_response for each provider model, track_storage after commit. Store LatencyMetrics in LatencyLog table (add to database/models.py: id, entity_type enum, entity_id, latency_json JSON, created_at). Use LatencyLogRepository.create_log.

- [ ] 5. Update database/models.py: Add LatencyLog model.

- [ ] 6. Update app/api/v1/endpoints/matches.py: Retrieve latest LatencyLog for match, call track_api_response, include latency_metrics in response (add to schemas.py).

- [ ] 7. Update app/api/v1/schemas.py: Add LatencyMetricsResponse schema. Add latency_metrics: Optional[LatencyMetricsResponse] to MatchDetailResponse and MatchPredictionResponse.

- [ ] 8. Create tests/test_latency.py: Test LatencyTracker with valid timestamps (calculates metrics), with missing source_updated_at (provider_event_timestamp=None), with future timestamp (has_future_timestamp=True), with clock skew. Test track_storage, track_api_response. Test LatencyLog persistence. Test API includes latency_metrics.

**Files:** latency/models.py, latency/tracker.py, latency/__init__.py, database/models.py (updated), ingestion/service.py (updated), app/api/v1/endpoints/matches.py (updated), app/api/v1/schemas.py (updated), tests/test_latency.py

**Verify:** `cd c:\FootballIntelligence\backend && .venv\Scripts\python.exe -m pytest tests/test_latency.py -v`

---

## FEAT-004: Feature Engineering with Database

**Objective:** Extend existing features/ module to use database-backed data with no future leakage, xG preservation (None if unavailable), and comprehensive data quality metrics.

### Steps

- [ ] 1. Inspect existing features/base.py, features/form.py, features/team_strength.py, features/match_features.py. Preserve all working code.

- [ ] 2. Create features/database_extractor.py: Implement DatabaseFeatureExtractor(session_factory) wrapping existing MatchFeatureExtractor but using database queries via repositories. Provide get_team_historical_matches(team_id, before_datetime, limit) using MatchRepository, get_team_standing using StandingRepository. Convert database models to domain models for compatibility.

- [ ] 3. Update features/team_strength.py: Modify TeamStrengthFeatureCalculator to accept DatabaseFeatureExtractor. Calculate attack_strength (goals per match), defense_strength (goals conceded per match), home/away venue_strength. Return None if < min_matches.

- [ ] 4. Update features/form.py: Modify TeamFormFeatureCalculator to accept DatabaseFeatureExtractor. Calculate last_n_results (W/D/L), last_n_points, win_rate, recent_goals, home/away_form, form_string. Return None if insufficient data.

- [ ] 5. Create features/attack_defence.py: Implement AttackDefenceFeatureCalculator(min_matches=5) calculating: goals_per_match (all/home/away), goals_conceded_per_match, xg_per_match (if MatchStatistic.xg available, else None—NEVER invent xG), xga_per_match, shot_metrics if available. Include sample_size.

- [ ] 6. Create features/match_context.py: Implement MatchContextFeatureCalculator calculating: home_advantage (historical home win rate vs overall), rest_days (days since last match for both teams), form_difference, strength_difference, competition_level, is_derby (heuristic).

- [ ] 7. Create features/data_quality.py: Implement DataQualityFeatureCalculator calculating: sample_size (matches used), data_freshness_seconds (time since last match), missing_field_ratio (None values in MatchStatistic / total fields), provider_availability (unique provider_sources), feature_confidence (0.0-1.0 score based on sample_size and freshness).

- [ ] 8. Create features/aggregator.py: Implement FeatureAggregator(session_factory, min_matches=5) orchestrating all calculators. Provide extract_features_for_match(match_id) -> FeatureSet. FeatureSet is Pydantic model with: match_id, home_team_features: Dict[str, Optional[float]], away_team_features: Dict, match_context_features: Dict, data_quality_features: Dict, features_available: bool, calculated_at: datetime, notes: Optional[List[str]].

- [ ] 9. Update app/config.py: Add TEAM_FORM_WINDOW: int = 5, MIN_SAMPLE_SIZE: int = 3, FEATURE_CONFIDENCE_THRESHOLD: float = 0.5 to Settings. Update .env.example.

- [ ] 10. Update prediction/service.py: Modify PredictionService to use DatabaseFeatureExtractor and FeatureAggregator when database available, fall back to in-memory for DevelopmentProvider. Add feature_set to AnalysisContext.

- [ ] 11. Create tests/test_features_database.py: Test DatabaseFeatureExtractor queries only historical matches (before scheduled_at, never after). Test TeamStrengthFeatureCalculator with 10 matches (calculates), with 2 matches (returns None). Test AttackDefenceFeatureCalculator with xG available (calculates), with xG=None (feature is None not 0). Test DataQualityFeatureCalculator. Test FeatureAggregator produces FeatureSet with features_available flag. Test no future data leakage: create match at T, historical match at T-1 (included), future match at T+1 (excluded).

**Files:** features/database_extractor.py, features/attack_defence.py, features/match_context.py, features/data_quality.py, features/aggregator.py, features/team_strength.py (updated), features/form.py (updated), app/config.py (updated), .env.example (updated), prediction/service.py (updated), tests/test_features_database.py

**Verify:** `cd c:\FootballIntelligence\backend && .venv\Scripts\python.exe -m pytest tests/test_features_database.py -v`. Verify existing tests still pass: `pytest tests/test_features.py -v`.

---

## FEAT-005: Prediction Integration and API Enhancement

**Objective:** Complete intelligence pipeline by integrating database-backed features into PredictionService, enriching API responses with metadata, confidence, latency, and preserving all existing contracts.

### Steps

- [ ] 1. Update prediction/service.py: Modify __init__ to accept session_factory and feature_aggregator. Use DatabaseFeatureExtractor if database available, else fall back to in-memory. Preserve all existing methods/signatures.

- [ ] 2. Modify generate_prediction: use FeatureAggregator.extract_features_for_match if available, extract confidence from FeatureSet.data_quality_features['feature_confidence'], add selected_provider from match.provider_source.name, calculate most_likely_score from score_distribution (max probability scoreline).

- [ ] 3. Modify build_analysis_context: include feature_set from FeatureAggregator, data_freshness_seconds from LatencyLog, provider_metadata (selected_provider, fetched_at, source_updated_at), update data_completeness with 'database_features', add missing_data_notes for unavailable xG, insufficient sample size.

- [ ] 4. Update domain/prediction.py: Add most_likely_score: Optional[str], confidence: Optional[float], selected_provider: Optional[str], data_freshness_seconds: Optional[int] to Prediction model.

- [ ] 5. Update domain/analysis.py: Add feature_set: Optional[FeatureSet], data_freshness_seconds: Optional[int], provider_metadata: Optional[Dict] to AnalysisContext model.

- [ ] 6. Update app/api/v1/schemas.py: Add most_likely_score, confidence, selected_provider, data_freshness_seconds to MatchPredictionResponse (all optional). Add selected_provider, fetched_at, data_freshness_seconds to MatchDetailResponse.

- [ ] 7. Update app/api/v1/endpoints/matches.py: Modify get_match to include provider metadata. Modify get_match_prediction to include new fields, retrieve LatencyLog if database match.

- [ ] 8. Update app/config.py: Ensure USE_REAL_PROVIDERS default=False. Document in comments.

- [ ] 9. Update .env.example: Add USE_REAL_PROVIDERS=false with comment about enabling real provider data and database persistence.

- [ ] 10. Create tests/test_integration_pipeline.py: End-to-end test. Setup: in-memory SQLite, run migrations, create ProviderSource, ingest mock ProviderMatch with metadata. Test: IngestionService → verify Match/Competition/Team/LatencyLog in database → PredictionService.generate_prediction → verify confidence, most_likely_score, selected_provider → build_analysis_context → verify feature_set, provider_metadata, data_quality → simulate API call → verify all new fields. Test insufficient data (confidence low, features_available=False, prediction with warnings). Test xG=None (Prediction.xg from features not missing xG, AnalysisContext notes 'xG not available').

- [ ] 11. Run full test suite: `.venv\Scripts\python.exe -m pytest tests/ -v`. Fix regressions (all changes additive, existing tests should pass).

**Files:** prediction/service.py (updated), domain/prediction.py (updated), domain/analysis.py (updated), app/api/v1/schemas.py (updated), app/api/v1/endpoints/matches.py (updated), app/config.py (updated), .env.example (updated), tests/test_integration_pipeline.py

**Verify:** `cd c:\FootballIntelligence\backend && .venv\Scripts\python.exe -m pytest tests/test_integration_pipeline.py -v`. Then: `pytest tests/ -v` (all tests).

---

## Final Verification

After completing all FEATs:

**Run full test suite:**
```powershell
cd c:\FootballIntelligence\backend
.venv\Scripts\python.exe -m pytest tests/ -v
```

**Expected:** All tests pass (existing + new tests). No regressions.

**Verify API compatibility:**
- GET /api/v1/matches still works (preserved)
- GET /api/v1/matches/{id} still works (preserved, new fields optional)
- GET /api/v1/matches/{id}/prediction still works (preserved, new fields optional)

**Verify configuration:**
- USE_REAL_PROVIDERS default=false in config.py
- .env.example documents all new settings
- Database layer functional (migrations, upserts, queries)
- Ingestion preserves metadata, never overwrites valid data with None
- Features use database, no future leakage, xG preserved as None if unavailable
- Latency tracked with nullable metrics
- API responses enriched with confidence, provider metadata, latency

**Update docs/PROGRESS.md:** Document completed work, verification results, next steps.

---

## Dependencies Between FEATs

- FEAT-001 (Database) must complete before FEAT-002 (Ingestion)
- FEAT-002 (Ingestion) must complete before FEAT-003 (Latency) and FEAT-004 (Features)
- FEAT-003 and FEAT-004 are independent of each other (can be implemented in parallel conceptually, but sequential in workflow)
- FEAT-005 (Integration) requires FEAT-001, FEAT-002, FEAT-003, FEAT-004 all complete

**Feature Order:** FEAT-001 → FEAT-002 → FEAT-003 → FEAT-004 → FEAT-005


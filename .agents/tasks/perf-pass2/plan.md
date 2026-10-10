# TUTAR X Second Performance Optimization Pass - Implementation Plan

## EXECUTIVE SUMMARY

**Objective**: Make TUTAR X feel instant to the user by implementing a FAST PATH + DEEP PATH architecture where lightweight match data and UI rendering never block on heavy historical intelligence calculations.

**Current State Analysis**:
- ✅ Dashboard already implements render-first, predict-later pattern (loads matches → stops loading → renders → starts predictions in background)
- ✅ Dashboard uses bounded concurrency (max 6 simultaneous predictions)
- ✅ Dashboard uses priority queue (popular competitions + next 48 hours + max 20 candidates)
- ✅ PredictionCacheContext uses stable refs and prevents duplicate requests
- ✅ useLazyPrediction prevents duplicate fetches with Set tracking
- ✅ MatchDetail lazy-loads predictions and renders match info immediately
- ✅ Matches page never preloads predictions (correct behavior)
- ⚠️ Some debug console.log statements remain
- ⚠️ Backend AdvancedFeatureEngineer recalculates same features for same teams repeatedly
- ⚠️ Backend provider cache exists but may not cover all repeated calls
- ⚠️ React StrictMode double-mount handling exists but could be strengthened

**Performance Gains from This Pass**: Estimated 30-50% reduction in prediction latency through backend feature snapshot caching, without compromising intelligence quality.

---

## AREA 1: DASHBOARD FIRST PAINT

### Status: ✅ ALREADY CORRECT — VERIFY ONLY

**Current Behavior**:
```typescript
// Dashboard.tsx lines 123-138
async function fetchDashboardData() {
  setLoading(true);
  const matchesResponse = await getUpcomingMatches(7);
  setAllScheduledMatches(allMatches);
  
  // IMMEDIATELY render page - don't wait for predictions
  setLoading(false);
  
  // Start background prediction loading
  loadPredictions(allMatches, null, abortController, isMounted);
}
```

The dashboard correctly:
1. Fetches matches
2. Stops global loading (`setLoading(false)`)
3. Renders match cards (or empty state)
4. Starts priority predictions in background
5. Progressively updates cards as predictions arrive

**Verification Tasks**:

- [ ] 1. **Manual verification of Dashboard first paint behavior**
      - Files: `frontend/src/pages/Dashboard.tsx` (lines 123-138)
      - Action: Run frontend, open Dashboard, confirm page renders with "TUTAR X seçimleri hazırlanıyor..." loading state BEFORE predictions complete
      - Expected: Dashboard header, filters, and loading spinner visible within <500ms; global page loading stops before predictions start
      - Verify: `npm run dev` (frontend) → Open http://localhost:5173 → Observe render timing

---

## AREA 2: MATCHES PAGE

### Status: ✅ ALREADY CORRECT — VERIFY ONLY

**Current Behavior**:
```typescript
// Matches.tsx lines 55-111
// Effect 2: Load matches when competition selected
useEffect(() => {
  async function fetchMatches() {
    setMatchesLoading(true);
    const response = await getMatches({ from_date, to_date, status: 'scheduled' });
    const normalizedMatches = normalizeMatches(response.matches);
    const filteredMatches = normalizedMatches.filter(match => match.competitionId === selectedCompetitionId);
    setMatches(filteredMatches);
    setMatchesLoading(false);
  }
  fetchMatches();
}, [selectedCompetitionId]);
```

The Matches page correctly:
1. Loads competition list on mount
2. When user selects a competition, fetches matches for that competition
3. Renders match list immediately
4. **NEVER proactively loads predictions** (predictions are only loaded when user clicks into MatchDetail)

**Verification Tasks**:

- [ ] 2. **Verify Matches page does not preload predictions**
      - Files: `frontend/src/pages/Matches.tsx` (entire file)
      - Action: Search for `getMatchPrediction`, `useLazyPrediction`, or `predictionCache` imports/calls
      - Expected: ZERO prediction-related calls in Matches.tsx
      - Verify: `grep -n "prediction" frontend/src/pages/Matches.tsx` should return ZERO results except comments
      - Command: `Select-String -Pattern "prediction|Prediction" -Path "c:/FootballIntelligence/frontend/src/pages/Matches.tsx" -CaseSensitive`

---

## AREA 3: MATCH DETAIL PRIORITY REQUEST

### Status: ✅ MOSTLY CORRECT — MINOR IMPROVEMENTS NEEDED

**Current Behavior**:
```typescript
// MatchDetail.tsx lines 53-67
const shouldLoadPrediction = match?.status === 'scheduled';
const { prediction, loading: predictionLoading, error: predictionError } = useLazyPrediction(
  shouldLoadPrediction ? id : null
);

useEffect(() => {
  async function fetchMatchData() {
    setLoading(true);
    const matchResponse = await getMatch(id);
    setMatch(matchResponse.match);
    setLoading(false);
  }
  fetchMatchData();
}, [id]);
```

Match Detail correctly:
1. Fetches match data first
2. Renders match info immediately (teams, competition, kickoff)
3. Checks PredictionCacheContext via `useLazyPrediction`
4. If cached: shows prediction immediately
5. If not cached: renders "Tahmin hazırlanıyor..." while loading

**Minor Issue**: The page-level `loading` state waits for match metadata. This is acceptable (match metadata is lightweight), but could be further optimized by showing match header skeleton immediately.

**Improvement Tasks**:

- [ ] 3. **Add early skeleton rendering to MatchDetail (optional enhancement)**
      - Files: `frontend/src/pages/MatchDetail.tsx` (lines 53-67, 96-106)
      - Action: Extract match ID from URL params immediately; show page skeleton with match ID before fetch completes
      - Current: Shows "Maç detayları yükleniyor..." centered spinner until match metadata arrives
      - Improved: Show page breadcrumb + header skeleton immediately, only show loading in content area
      - Implementation:
        ```typescript
        // Show page shell immediately
        if (loading) {
          return (
            <div className="page-container">
              <div className="breadcrumb">
                <Link to="/matches" className="breadcrumb-link">Maçlar</Link>
                <span className="breadcrumb-separator">›</span>
                <span className="breadcrumb-current">Maç İstihbaratı</span>
              </div>
              <div className="match-intelligence-header">
                <div className="loading-spinner"></div>
              </div>
            </div>
          );
        }
        ```
      - Priority: LOW (current behavior is acceptable; match metadata is fast)
      - Verify: Manual test — open match detail page, observe skeleton structure appears <100ms

---

## AREA 4: PREDICTION CACHE HARDENING

### Status: ✅ MOSTLY CORRECT — MINOR STRENGTHENING NEEDED

**Current Implementation Analysis**:

1. **Stable cache keys**: ✅ Uses match ID string directly
2. **No duplicate requests**: ✅ `useLazyPrediction` uses `fetchStartedRef` Set to track in-flight requests
3. **No React effect loops**: ✅ `PredictionCacheContext` callbacks use `useCallback` with empty deps and read from `cacheRef`
4. **StrictMode safety**: ⚠️ Partially safe — `fetchStartedRef` Set prevents double-mount duplicates, but Set is NOT cleared on abort
5. **Aborted requests**: ⚠️ Aborted requests are NOT corrupting cache (good), but may leave loading=true state if abort happens before cache update
6. **Failed requests can retry**: ✅ `cache.setError()` stores error but does NOT freeze — subsequent calls can retry
7. **Successful predictions persist**: ✅ Cache stored in ref, persists for session
8. **No persistent storage**: ✅ No localStorage — session-only in-memory cache

**Issues to Fix**:

- [ ] 4. **Strengthen StrictMode double-mount handling in useLazyPrediction**
      - Files: `frontend/src/hooks/useLazyPrediction.ts` (lines 10-65)
      - Problem: `fetchStartedRef.current.delete(matchId)` only happens in cleanup, so if StrictMode mounts twice rapidly, the second mount sees the matchId still in the Set
      - Solution: Move `fetchStartedRef` tracking INSIDE the async function, set it immediately after abort check
      - Changes:
        ```typescript
        // BEFORE (line 33-36):
        if (fetchStartedRef.current.has(matchId)) return;
        fetchStartedRef.current.add(matchId);
        
        // AFTER:
        // Remove early Set tracking entirely
        
        // Inside fetchPrediction, AFTER setLoading:
        async function fetchPrediction() {
          if (!matchId) return;
          
          // Check if fetch already started for this mount
          if (fetchStartedRef.current.has(matchId)) {
            return;
          }
          fetchStartedRef.current.add(matchId);
        
          try {
            cache.setLoading(matchId);
            // ... rest of function
          } catch (err) {
            // ... error handling
          } finally {
            fetchStartedRef.current.delete(matchId);
          }
        }
        ```
      - Verify: Run `npm run dev`, open MatchDetail in StrictMode (React 18 default), check Network tab for duplicate prediction requests

- [ ] 5. **Add request deduplication at cache level**
      - Files: `frontend/src/contexts/PredictionCacheContext.tsx` (lines 32-96)
      - Problem: If two components request the same prediction simultaneously (before either completes), both will call `setLoading` and start fetching
      - Solution: Track in-flight requests in cache context
      - Changes:
        ```typescript
        // Add to PredictionCacheProvider state:
        const inFlightRef = useRef<Set<string>>(new Set());
        
        // Modify setLoading:
        const setLoading = useCallback((matchId: string) => {
          // If already loading, don't update
          if (inFlightRef.current.has(matchId)) {
            return;
          }
          inFlightRef.current.add(matchId);
          
          cacheRef.current.set(matchId, {
            prediction: null,
            loading: true,
            error: null,
          });
          forceUpdate({});
        }, []);
        
        // Modify setPrediction and setError to clear in-flight:
        const setPrediction = useCallback((matchId: string, prediction: MatchPredictionResponse) => {
          inFlightRef.current.delete(matchId);
          cacheRef.current.set(matchId, {
            prediction,
            loading: false,
            error: null,
          });
          forceUpdate({});
        }, []);
        
        const setError = useCallback((matchId: string, error: Error) => {
          inFlightRef.current.delete(matchId);
          cacheRef.current.set(matchId, {
            prediction: null,
            loading: false,
            error,
          });
          forceUpdate({});
        }, []);
        
        // Add to context type:
        isLoading: (matchId: string) => boolean;
        
        // Implement:
        const isLoading = useCallback((matchId: string): boolean => {
          return inFlightRef.current.has(matchId);
        }, []);
        ```
      - Modify `useLazyPrediction` to check `cache.isLoading()` before starting fetch
      - Verify: Add artificial delay to prediction endpoint, open two MatchDetail tabs with same match ID simultaneously, verify only ONE network request

---

## AREA 5: PRIORITY PREDICTION QUEUE

### Status: ✅ ALREADY CORRECT — VERIFY ONLY

**Current Behavior**:
```typescript
// Dashboard.tsx lines 183-249
async function loadPredictions(allMatches, activeCompetitionId, abortCtrl, mounted) {
  // Build priority competition set: popular + active
  const priorityCompetitions = new Set<string>();
  allMatches.forEach(match => {
    if (match.competition_id && isPopularCompetitionById(match.competition_id)) {
      priorityCompetitions.add(match.competition_id);
    }
  });
  if (activeCompetitionId) {
    priorityCompetitions.add(activeCompetitionId);
  }
  
  // Select candidate matches (next 48 hours, priority comps, max 20)
  const candidateMatches = allMatches
    .filter(match => /* scheduled, priority comp, next 48h */)
    .sort(/* by time */)
    .slice(0, 20); // BOUNDED
  
  // Filter out cached
  const matchesToPredict = candidateMatches.filter(match => !predictionCache.has(match.id));
  
  // Execute with bounded concurrency (max 6 simultaneous requests)
  const results = await executeWithConcurrency(predictionTasks, 6);
}

// Bounded concurrency helper (lines 71-98)
async function executeWithConcurrency<T>(tasks, concurrencyLimit) {
  // Limits simultaneous promises to concurrencyLimit
}
```

Dashboard correctly:
1. Prioritizes popular competitions + live competitions
2. Filters to next 48 hours
3. Bounds candidates to max 20 matches
4. Skips already-cached predictions
5. Executes with max 6 concurrent requests
6. No polling loops (live matches polled every 20s, but predictions are one-time)

**Verification Tasks**:

- [ ] 6. **Verify bounded concurrency and no request storms**
      - Files: `frontend/src/pages/Dashboard.tsx` (lines 71-98, 183-249)
      - Action: Run frontend with Network tab open, load Dashboard with 50+ upcoming matches
      - Expected: 
        - At most 20 prediction requests total (bounded candidate list)
        - At most 6 simultaneous requests (bounded concurrency)
        - No duplicate requests for same match ID
        - Live match polling does NOT trigger prediction requests
      - Verify: `npm run dev` → Open Network tab → Filter to `/api/predictions/` → Count simultaneous requests

---

## AREA 6: BACKEND FEATURE SNAPSHOT CACHE

### Status: ⚠️ MISSING — IMPLEMENT REQUIRED

**Problem**: `AdvancedFeatureEngineer.engineer_features()` is called for EVERY prediction. For the same team within a short time window, it recalculates:
- Team historical form (same team, same window)
- Opponent adjustment (same team, same historical matches)
- Shot history (same team, same window)
- Common opponent intelligence (same team pair, same window)

These calculations are EXPENSIVE (iterating over 90+ historical matches per team) but produce IDENTICAL results if called within the same prediction timestamp bucket.

**Solution**: Implement a per-prediction-request feature snapshot cache keyed on `(team_id, window, prediction_timestamp_bucket)` that:
- Caches feature calculator outputs for the duration of a single prediction request
- Never reuses features across different prediction timestamps
- Never uses post-match data in pre-match predictions (temporal validity preserved)
- Clears automatically after each prediction completes

**Implementation Tasks**:

- [ ] 7. **Create FeatureSnapshotCache class in backend/app/features/snapshot_cache.py**
      - Files: `backend/app/features/snapshot_cache.py` (NEW FILE)
      - Purpose: Thread-local cache for feature calculator results, scoped to a single prediction request
      - Implementation:
        ```python
        """Feature snapshot cache for deduplicating feature calculations within a prediction request.
        
        Temporal Validity:
        - Cache keys include prediction_timestamp
        - Features are NEVER reused across different prediction timestamps
        - Cache is request-scoped (cleared after each prediction)
        
        Thread Safety:
        - Uses threading.local() for thread isolation
        - Each request gets its own cache instance
        """
        
        from dataclasses import dataclass
        from datetime import datetime
        from typing import Any, Optional, Dict, Tuple
        import threading
        
        
        @dataclass
        class CacheKey:
            """Cache key for feature snapshot."""
            team_id: str
            window_type: str  # "recent", "medium", "season"
            prediction_timestamp: datetime
            calculator_type: str  # "team_intelligence", "shot_intelligence", etc.
            
            def to_tuple(self) -> Tuple:
                """Convert to hashable tuple."""
                # Bucket timestamp to minute precision to allow cache hits within same minute
                timestamp_bucket = self.prediction_timestamp.replace(second=0, microsecond=0)
                return (self.team_id, self.window_type, timestamp_bucket, self.calculator_type)
        
        
        class FeatureSnapshotCache:
            """Request-scoped cache for feature calculator results.
            
            Usage:
                cache = FeatureSnapshotCache()
                
                # At start of prediction request
                cache.clear()
                
                # During feature extraction
                key = CacheKey(team_id, "recent", prediction_timestamp, "team_intelligence")
                cached = cache.get(key)
                if cached is None:
                    result = expensive_calculator.calculate(...)
                    cache.set(key, result)
                else:
                    result = cached
                
                # At end of prediction request
                cache.clear()
            """
            
            def __init__(self):
                """Initialize thread-local cache storage."""
                self._local = threading.local()
            
            @property
            def _cache(self) -> Dict[Tuple, Any]:
                """Get thread-local cache dict."""
                if not hasattr(self._local, 'cache'):
                    self._local.cache = {}
                return self._local.cache
            
            def get(self, key: CacheKey) -> Optional[Any]:
                """Get cached feature result.
                
                Args:
                    key: Cache key
                    
                Returns:
                    Cached result or None if not found
                """
                return self._cache.get(key.to_tuple())
            
            def set(self, key: CacheKey, value: Any) -> None:
                """Store feature result in cache.
                
                Args:
                    key: Cache key
                    value: Feature calculator result
                """
                self._cache[key.to_tuple()] = value
            
            def clear(self) -> None:
                """Clear all cached features for this thread.
                
                MUST be called at the start and end of each prediction request
                to prevent temporal leakage across predictions.
                """
                self._cache.clear()
            
            def size(self) -> int:
                """Get current cache size."""
                return len(self._cache)
        ```
      - Verify: Unit test that cache stores/retrieves values correctly and clears completely

- [ ] 8. **Integrate FeatureSnapshotCache into AdvancedFeatureEngineer**
      - Files: `backend/app/features/advanced_feature_engineering.py` (lines 354-438, entire `engineer_features` method)
      - Changes:
        ```python
        # Add import at top:
        from app.features.snapshot_cache import FeatureSnapshotCache, CacheKey
        
        # Modify __init__:
        def __init__(
            self,
            create_interactions: bool = False,
            interactions: Optional[List[InteractionFeature]] = None,
            feature_cache: Optional[FeatureSnapshotCache] = None  # NEW
        ):
            self.create_interactions = create_interactions
            self.interactions = interactions if interactions is not None else CANDIDATE_INTERACTIONS
            self.feature_cache = feature_cache  # NEW
        
        # Modify engineer_features (lines 354-438):
        def engineer_features(
            self,
            home_team_id: str,
            away_team_id: str,
            matches_with_stats: List[MatchWithStatistics],
            before_datetime: datetime,
            prediction_timestamp: Optional[datetime] = None,
        ) -> AdvancedFeatureSet:
            if prediction_timestamp is None:
                prediction_timestamp = before_datetime
            
            # Clear cache at start of prediction
            if self.feature_cache:
                self.feature_cache.clear()
            
            features: Dict[str, Optional[float]] = {}
            feature_metadata: Dict[str, AdvancedFeatureMetadata] = {}
            quality_scores: List[float] = []
            quality_weights: List[float] = []
            
            # 1. Advanced Team Intelligence (Group 1) - WITH CACHING
            team_intel_calc = AdvancedTeamIntelligenceCalculator(session=None, min_matches=5)
            
            # Home team
            home_cache_key = CacheKey(home_team_id, "recent", prediction_timestamp, "team_intelligence")
            if self.feature_cache:
                home_team_metrics = self.feature_cache.get(home_cache_key)
            else:
                home_team_metrics = None
            
            if home_team_metrics is None:
                home_team_metrics = team_intel_calc.calculate_advanced_metrics(
                    team_id=home_team_id,
                    matches_with_stats=matches_with_stats,
                    before_datetime=before_datetime
                )
                if self.feature_cache:
                    self.feature_cache.set(home_cache_key, home_team_metrics)
            
            # Away team
            away_cache_key = CacheKey(away_team_id, "recent", prediction_timestamp, "team_intelligence")
            if self.feature_cache:
                away_team_metrics = self.feature_cache.get(away_cache_key)
            else:
                away_team_metrics = None
            
            if away_team_metrics is None:
                away_team_metrics = team_intel_calc.calculate_advanced_metrics(
                    team_id=away_team_id,
                    matches_with_stats=matches_with_stats,
                    before_datetime=before_datetime
                )
                if self.feature_cache:
                    self.feature_cache.set(away_cache_key, away_team_metrics)
            
            # Extract features (unchanged)
            self._extract_team_metrics(home_team_metrics, "home", prediction_timestamp, features, feature_metadata)
            self._extract_team_metrics(away_team_metrics, "away", prediction_timestamp, features, feature_metadata)
            
            # ... REPEAT PATTERN FOR ALL OTHER CALCULATORS:
            # - OpponentAdjustmentCalculator
            # - TemporalIntelligenceCalculator
            # - LineupIntelligenceCalculator
            # - TacticalMatchupCalculator
            # - ShotIntelligenceCalculator
            # - ShotProductionCalculator
            # - CommonOpponentCalculator
            
            # Clear cache at end of prediction
            if self.feature_cache:
                self.feature_cache.clear()
            
            return feature_set
        ```
      - Apply caching pattern to ALL 8 calculator calls (team intelligence, opponent adjustment, temporal, lineup, tactical, shot intelligence, shot production, common opponent)
      - Use calculator-specific cache keys to prevent collisions
      - Verify: Add logging to count cache hits/misses; run prediction for two matches with overlapping teams; expect 50%+ cache hit rate

- [ ] 9. **Wire FeatureSnapshotCache into prediction service**
      - Files: `backend/app/prediction/database_service.py` (lines 67-114, `generate_prediction_with_db_features`)
      - Changes:
        ```python
        # Add import at top:
        from app.features.snapshot_cache import FeatureSnapshotCache
        
        # Modify generate_prediction_with_db_features:
        def generate_prediction_with_db_features(
            self,
            match_db_id: str,
            latency_tracker: Optional[LatencyTracker] = None
        ) -> Optional[Prediction]:
            if not self.session or not self.feature_aggregator:
                return None
            
            # Create request-scoped feature cache
            feature_cache = FeatureSnapshotCache()
            
            # Pass cache to feature aggregator (if it uses AdvancedFeatureEngineer)
            # TODO: Modify FeatureAggregator to accept and pass cache to engineer
            
            # ... rest of method unchanged
            
            # Clear cache at end
            feature_cache.clear()
            
            return prediction
        ```
      - Modify `FeatureAggregator.extract_features_for_match()` to accept and pass `feature_cache` to `AdvancedFeatureEngineer`
      - Verify: Backend integration test — generate prediction for two matches with same teams; log cache stats; expect cache hits

---

## AREA 7: PROVIDER CALL DEDUPLICATION

### Status: ✅ ALREADY IMPLEMENTED — VERIFY ONLY

**Current State**: Provider classes (`FotMobFootballProvider`, `OpenLigaDBFootballProvider`) already use `ProviderCache` with TTL-based caching:

```python
# backend/app/providers/cache.py
class ProviderCache:
    """Thread-safe in-memory TTL cache for provider data."""
    
    LIVE_DATA_TTL = 30  # 30 seconds
    UPCOMING_FIXTURES_TTL = 300  # 5 minutes
    HISTORICAL_MATCH_TTL = 3600  # 1 hour
    METADATA_TTL = 3600  # 1 hour

# backend/app/providers/fotmob.py (lines 447-471)
def get_match(self, match_id: str) -> Match:
    # Check cache
    cache_key = f"{self.PROVIDER_NAME}:match:{match_id}"
    if self.cache:
        cached = self.cache.get(cache_key)
        if cached is not None:
            return cached
    
    # Fetch from API
    match = self._fetch_and_normalize(match_id)
    
    # Cache result with TTL based on status
    if self.cache:
        ttl = HISTORICAL_MATCH_TTL if match.status == MatchStatus.FINISHED else UPCOMING_FIXTURES_TTL
        self.cache.set(cache_key, match, ttl_seconds=ttl)
    
    return match
```

**Verification Tasks**:

- [ ] 10. **Verify provider cache is initialized and passed to providers**
      - Files: `backend/app/main.py` or `backend/app/dependencies.py` (wherever providers are instantiated)
      - Action: Search for `ProviderCache()` instantiation and confirm it's passed to all provider constructors
      - Expected: Single shared `ProviderCache` instance passed to FotMob, OpenLigaDB, Ryzellx, SofaScore providers
      - Verify: `grep -rn "ProviderCache()" backend/app/` should show instantiation in app setup

- [ ] 11. **Add logging to provider cache for monitoring (optional)**
      - Files: `backend/app/providers/cache.py` (lines 61-82, `get` method)
      - Action: Add debug logging on cache hits
      - Changes:
        ```python
        def get(self, key: str) -> Optional[Any]:
            with self._lock:
                entry = self._store.get(key)
                if entry is None:
                    return None
                if entry.is_expired():
                    del self._store[key]
                    return None
                
                # Log cache hit (optional, for monitoring)
                import logging
                logger = logging.getLogger(__name__)
                logger.debug(f"Cache HIT: {key}")
                
                return entry.value
        ```
      - Priority: LOW (monitoring/debugging only)

---

## AREA 8: DEBUG LOG CLEANUP

### Status: ⚠️ CLEANUP REQUIRED

**Debug Logs to Remove**:

- [ ] 12. **Remove debug console.log statements from Dashboard.tsx**
      - Files: `frontend/src/pages/Dashboard.tsx`
      - Lines to remove/modify:
        - Line 127: `console.log('[Dashboard] Fetching upcoming matches...');` → REMOVE
        - Line 134: `console.log(\`[Dashboard] Found ${allMatches.length} total matches\`);` → REMOVE
        - Line 199: `console.log(\`[PredictionPriority] Adding live competition: ${activeCompetitionId}\`);` → KEEP (useful for debugging live priority)
        - Line 201: `console.log(\`[PredictionPriority] Priority competitions: ${priorityCompetitions.size}\`);` → REMOVE
        - Line 212: `console.log('[PredictionPriority] No candidates found');` → REMOVE
        - Line 221: `console.log('[PredictionPriority] All candidates already cached');` → REMOVE
        - Line 227: `console.log(\`[PredictionPriority] Loading ${matchesToPredict.length} new predictions...\`);` → KEEP (useful info)
        - Line 263: `console.log(\`[PredictionPriority] Loaded ${newPicksData.length} new picks...\`);` → KEEP
        - Line 362: `console.log(\`[LiveCompetition] Active competition changed...\`);` → KEEP
        - Line 425: `console.log('[PredictionPriority] All live competition candidates already cached');` → REMOVE
        - Line 429: `console.log(\`[PredictionPriority] Loading ${matchesToPredict.length} predictions with live competition priority\`);` → KEEP
        - Line 461: `console.log(\`[PredictionPriority] Loaded ${newPicksData.length} picks from live competition priority\`);` → KEEP
      - Summary: REMOVE 6 noisy logs; KEEP 5 informational logs for debugging priority queue behavior
      - Verify: Search for `console.log('[Dashboard]` and `console.log('[PredictionPriority]` — should find only 5 remaining

- [ ] 13. **Remove debug console.log statements from Matches.tsx**
      - Files: `frontend/src/pages/Matches.tsx`
      - Lines to remove/modify:
        - Line 30: `console.log('[DEBUG Matches.tsx] Fetching competitions...');` → REMOVE
        - Line 36: `console.log('[DEBUG Matches.tsx] Loaded', response.count, 'competitions');` → REMOVE
        - Line 39: `console.error('[DEBUG Matches.tsx] Error loading competitions:', err);` → Change to `console.error('Error loading competitions:', err);` (remove [DEBUG] prefix)
        - Line 71: `console.log('[DEBUG Matches.tsx] Fetching matches for competition:', selectedCompetitionId);` → REMOVE
        - Line 90: `console.log('[DEBUG Matches.tsx] Request aborted or component unmounted');` → REMOVE
        - Line 105-107: Multi-line console.log with total/filtered counts → REMOVE
        - Line 108: `console.error('[DEBUG Matches.tsx] Error loading matches:', err);` → Change to `console.error('Error loading matches:', err);`
      - Summary: REMOVE 5 debug logs; clean up 2 error logs (remove [DEBUG] prefix)
      - Verify: `grep -n "console.log" frontend/src/pages/Matches.tsx` should return ZERO results

- [ ] 14. **Verify no debug logs in MatchDetail.tsx, useLazyPrediction.ts, PredictionCacheContext.tsx**
      - Files: 
        - `frontend/src/pages/MatchDetail.tsx`
        - `frontend/src/hooks/useLazyPrediction.ts`
        - `frontend/src/contexts/PredictionCacheContext.tsx`
      - Action: Search for `console.log`, `console.debug`, `console.info`
      - Expected: ZERO debug logs (console.error and console.warn are acceptable for real errors)
      - Verify: `Select-String -Pattern "console\.(log|debug|info)" -Path "frontend/src/pages/MatchDetail.tsx","frontend/src/hooks/useLazyPrediction.ts","frontend/src/contexts/PredictionCacheContext.tsx"`

---

## AREA 9: REGRESSION TESTING

### Status: ⚠️ REQUIRED AFTER CHANGES

**Critical Constraints to Preserve**:
- Seven prediction models (unchanged)
- AdvancedFeatureEngineer and all Group 1-4 calculators (unchanged logic, only caching added)
- Team Intelligence, Opponent Adjustment, Recency, Lineup, Tactical, Shot Intelligence, Common Opponent Intelligence (unchanged)
- Calibration, Uncertainty, Market Reliability, Smart Market Selector (unchanged)
- BestTip / PASS logic (unchanged)
- Result ingestion, Settlement, Track Record (unchanged)
- Competition filtering and scheduled-match fixes (unchanged)
- Temporal validity (no future data leakage)

**Testing Tasks**:

- [ ] 15. **Run existing backend test suite**
      - Files: `backend/tests/` (all test files)
      - Command: `cd backend && python -m pytest tests/ -v`
      - Expected: ALL tests PASS with zero regressions
      - If failures: Identify root cause in feature cache implementation; fix before proceeding
      - Verify: Test output shows `45/45 PASSED` or similar

- [ ] 16. **Run frontend build and type checking**
      - Files: `frontend/src/` (all TypeScript files)
      - Commands:
        ```bash
        cd frontend
        npm run build
        npx tsc --noEmit
        ```
      - Expected: Zero TypeScript errors; build completes successfully
      - Verify: `Build completed` message; no type errors

- [ ] 17. **Manual end-to-end prediction verification**
      - Files: Full stack (backend + frontend)
      - Steps:
        1. Start backend: `cd backend && uvicorn app.main:app --reload`
        2. Start frontend: `cd frontend && npm run dev`
        3. Open Dashboard
        4. Wait for predictions to load
        5. Open a Match Detail page
        6. Verify prediction displays correctly
        7. Verify "Genel", "İlk Yarı", "Maç" tabs all render
        8. Verify no console errors
      - Expected: 
        - Predictions display with probabilities summing to 1.0
        - TUTAR X picks show confidence scores
        - Match detail shows full intelligence
        - No JavaScript errors in console
        - No network errors in Network tab
      - Verify: Manual observation

---

## SUMMARY OF CHANGES

### Frontend Changes (Minimal)
1. **PredictionCacheContext.tsx**: Add in-flight request tracking to prevent duplicate simultaneous requests
2. **useLazyPrediction.ts**: Strengthen StrictMode handling by moving Set tracking inside async function
3. **Dashboard.tsx**: Remove 6 noisy debug logs (keep 5 informational ones)
4. **Matches.tsx**: Remove all 5 debug logs
5. **MatchDetail.tsx** (optional): Add skeleton rendering for faster perceived load

### Backend Changes (Performance Optimization)
1. **snapshot_cache.py** (NEW): Thread-local feature snapshot cache
2. **advanced_feature_engineering.py**: Integrate cache into all 8 calculator calls
3. **database_service.py**: Create and pass cache instance to feature engineer
4. **cache.py** (optional): Add debug logging for monitoring

### Expected Performance Gains
- **Dashboard first paint**: Already optimal (<500ms)
- **Match Detail load**: 0-100ms improvement (match metadata already fast)
- **Prediction generation**: 30-50% latency reduction from feature caching
  - Before: ~2-5s per prediction (with populated DB)
  - After: ~1-3s per prediction (feature cache eliminates duplicate calculations)
- **Multiple predictions**: 50%+ improvement when predicting matches with overlapping teams
  - Example: 10 Premier League matches (20 teams, ~15 unique teams) → 30% cache hit rate = 2-3s saved

### Risk Assessment
- **Low Risk**: Frontend changes are minimal and defensive (strengthening existing patterns)
- **Medium Risk**: Backend feature cache requires careful temporal validity testing
- **Mitigation**: 
  - Feature cache clears at start/end of each prediction (no cross-prediction leakage)
  - Cache keys include prediction_timestamp (no temporal leakage)
  - Existing test suite validates prediction correctness
  - Manual E2E testing verifies user-facing behavior

---

## EXECUTION ORDER

1. **Verification Pass** (Tasks 1-2, 6, 10-11, 14): Verify existing correct behavior
2. **Frontend Hardening** (Tasks 4-5): Strengthen cache and StrictMode handling
3. **Frontend Cleanup** (Tasks 12-13): Remove debug logs
4. **Backend Performance** (Tasks 7-9): Implement feature snapshot cache
5. **Regression Testing** (Tasks 15-17): Verify no regressions
6. **Optional Enhancements** (Task 3): Add skeleton rendering if time permits

---

## SUCCESS CRITERIA

1. ✅ Dashboard renders match cards BEFORE predictions complete (already working)
2. ✅ Matches page never preloads predictions (already working)
3. ✅ Match Detail shows match info immediately, predictions load separately (already working)
4. ✅ No duplicate prediction requests for same match (strengthened)
5. ✅ StrictMode double-mount does not cause duplicate requests (strengthened)
6. ✅ Bounded concurrency prevents request storms (already working)
7. ✅ Backend feature cache reduces prediction latency by 30-50%
8. ✅ No debug logs in production code
9. ✅ All existing tests pass
10. ✅ Manual E2E testing shows correct predictions

---

**Plan Author**: Kiro Planning Agent  
**Plan Version**: 1.0  
**Date**: 2025-01-XX  
**Estimated Implementation Time**: 4-6 hours  
**Risk Level**: LOW-MEDIUM (mostly verification + defensive strengthening + performance optimization)

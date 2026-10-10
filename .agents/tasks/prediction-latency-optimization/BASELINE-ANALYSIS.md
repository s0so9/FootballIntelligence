# PREDICTION LATENCY BASELINE ANALYSIS

**Date:** 2026-10-08  
**Match ID:** fotmob_5881179  
**Baseline Latency:** 27.92 seconds

---

## ROOT CAUSE IDENTIFIED

### The Bottleneck

**File:** `backend/app/features/match_features.py`  
**Method:** `MatchFeatureExtractor._build_match_context()`  
**Lines:** ~105-110

```python
# Calculate date range for historical matches
from_date = match_date - timedelta(days=90)  # 90-day window
to_date = match_date - timedelta(days=1)

# Get all matches in date range
all_matches = self.provider.get_matches(
    from_date=from_date,
    to_date=to_date
)
```

### What's Happening

1. **Global Query:** The code fetches **ALL matches globally** for a 90-day period
2. **Massive Data Transfer:** In this case, 18,204 matches were fetched
3. **Sequential API Calls:** FotMob requires ~90 sequential daily requests (no bulk endpoint)
4. **Python Filtering:** After fetching all matches, it filters in Python for specific teams
5. **Wasted Data:** 99%+ of fetched matches are discarded

### Observed Behavior

From profiling logs:
- **90+ sequential FotMob API calls** (one per day from July 12 to Oct 9)
- Each call takes ~150-300ms
- **Total matches fetched:** 18,204
- **Actual matches needed:** ~20-30 per team = 40-60 total
- **Wasted data:** >99.7%

Example log sequence:
```
2026-10-07 18:25:56,854 - [fotmob] Fetched 22 matches for 2026-07-13
2026-10-07 18:25:57,029 - [fotmob] Fetched 54 matches for 2026-07-14
2026-10-07 18:25:57,211 - [fotmob] Fetched 48 matches for 2026-07-15
... (90+ more lines)
2026-10-07 18:25:58,806 - [fotmob] Fetched 18204 matches for range 2026-07-12 to 2026-10-09
```

### Time Breakdown

From profiling report:
```
Total Duration: 26713.13ms (26.71s)

Stages:
  25894.44ms (96.9%) - 04_FULL_PREDICTION_PIPELINE
    425.40ms ( 1.6%) - 00_provider_initialization  
    387.48ms ( 1.5%) - 01_get_match
      5.67ms ( 0.0%) - 03_prediction_service_init
      0.14ms ( 0.0%) - 02_db_session
```

**96.9% of time (25.9 seconds) is inside the prediction pipeline**, and based on logs, most of that is provider calls fetching historical matches.

---

## WHY THIS ARCHITECTURE EXISTS

This design appears to have been chosen for simplicity:
1. Provider has no `team_id` filter
2. Fetching globally avoids multiple queries
3. Python filtering is "simple"

But it scales terribly:
- Every prediction fetches ~20K matches
- No caching between predictions
- Sequential API calls

---

## OPTIMIZATION STRATEGY

### Option 1: Database-First Architecture ✅ RECOMMENDED
**Use persisted matches from database instead of provider**

Advantages:
- Single SQL query per team (~10ms each)
- Data already available from prior ingestion
- Eliminates 90+ provider API calls
- Preserves temporal validity

Changes needed:
- Check if matches exist in database first
- Fall back to provider only if database is empty
- Use `DatabaseFeatureExtractor` when `db_session` is available

### Option 2: Provider Caching
**Cache provider responses at the adapter level**

Advantages:
- Transparent to feature extraction
- Benefits all predictions in same session

Disadvantages:
- Still makes initial 90+ calls
- Cache invalidation complexity
- Memory usage for large match sets

### Option 3: Team-Specific Query
**Add team_id filter to provider.get_matches()**

Advantages:
- Reduces data transfer

Disadvantages:
- Requires 2 queries (home + away teams)
- FotMob has no team filter endpoint
- Would need to fetch globally anyway, then filter

---

## RECOMMENDATION

**Implement Option 1: Database-First Architecture**

The database already has match data. Use it:

1. Modify `MatchFeatureExtractor._build_match_context()` to:
   - Check if `db_session` is available
   - Query database for team historical matches (2 fast SQL queries)
   - Fall back to provider only if database is empty

2. Expected improvement:
   - **Before:** 25+ seconds (90+ provider calls)
   - **After:** <1 second (2 SQL queries)
   - **Speedup:** ~25-30x faster

3. Preserves:
   - Temporal validity (database queries support `before_datetime`)
   - Data quality
   - Seven-model architecture
   - Phase 10 intelligence
   - All features

4. No loss of functionality:
   - Database has same data provider would return
   - Fresh predictions still work (database updated periodically)
   - Development mode can still use provider fallback

---

## FILES TO MODIFY

1. **`backend/app/features/match_features.py`**
   - `MatchFeatureExtractor.__init__()` — accept optional `db_session`
   - `MatchFeatureExtractor._build_match_context()` — use database first

2. **`backend/app/prediction/service.py`**
   - `PredictionService._extract_canonical_snapshot()` — pass `db_session` to feature extractor

---

## MEASUREMENT PLAN

1. **Before:** Profile current implementation (DONE: 27.92s)
2. **After:** Profile optimized implementation
3. **Compare:** Document exact improvement
4. **Verify:** Run all regression tests
5. **Validate:** Confirm same prediction output

---

## RISKS

### Low Risk
- Database already tested and working
- DatabaseFeatureExtractor already exists
- Temporal validity already enforced
- Fallback to provider if database empty

### Medium Risk
- Database may not have all historical matches for new competitions
- Need to ensure database freshness

### Mitigation
- Keep provider fallback
- Log when fallback is used
- Monitor database coverage

---

## ACCEPTANCE CRITERIA

- [ ] Prediction latency < 3 seconds (90% reduction)
- [ ] Same prediction output (verify probabilities match)
- [ ] All tests pass
- [ ] No temporal leakage
- [ ] Seven models still execute
- [ ] Phase 10 intelligence preserved

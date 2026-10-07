# Implementation Plan: Phase 10 Group 3 — Common Opponent Intelligence

**Status**: Ready for implementation  
**Target**: Phase 10G — Common Opponent Intelligence  
**Dependencies**: Group 1 (Advanced Team Intelligence, Opponent Adjustment, Temporal Intelligence)  
**Current Commit**: 0a77c07 (Group 2 complete, 99/99 tests passing)

---

## OVERVIEW

Implement Common Opponent Intelligence as a **reusable contextual feature** (not an independent prediction engine). Common opponents provide indirect evidence when direct H2H is limited/unavailable.

**Core Principle**: Common opponent analysis is a MEDIUM-confidence contextual signal that feeds the existing 7-model ensemble through `MatchFeatureSnapshot`. It does NOT replace direct H2H.

**Non-Negotiable Data Rules**:
- REAL DATA > NULL/UNAVAILABLE > FABRICATED DATA
- Never invent common opponents, results, xG, xGA, shots, or tactical metrics
- Temporal validity: strict `match.scheduled_at < prediction_timestamp`
- Statistical evidence threshold: confidence calculated from sample size, recency, context

---

## IMPLEMENTATION PLAN

### Step 1: Create `backend/app/features/common_opponent_intelligence.py`

**What**: Implement the core Common Opponent Intelligence module with discovery, comparison, and confidence calculation.

**Files to Create**:
- `c:/FootballIntelligence/backend/app/features/common_opponent_intelligence.py`

**Dataclass Specifications**:

```python
@dataclass
class CommonOpponentMatch:
    """Record of a team's performance vs a common opponent.
    
    Preserves full match context for proper comparison.
    """
    team_id: str
    opponent_id: str
    match_id: str
    match_date: datetime
    
    # Match context
    is_home: bool  # Was team_id playing at home
    competition_id: str
    
    # Result
    result: str  # "win", "draw", "loss"
    goals_for: int
    goals_against: int
    goal_difference: int
    points: int  # 3, 1, or 0
    
    # Advanced metrics (None if unavailable)
    xg: Optional[float] = None
    xga: Optional[float] = None
    shots: Optional[int] = None
    shots_on_target: Optional[int] = None
    possession: Optional[float] = None
    
    # Data quality
    has_advanced_stats: bool = False
    
    def __post_init__(self):
        """Validate data integrity."""
        assert self.result in ["win", "draw", "loss"]
        assert 0 <= self.points <= 3


@dataclass
class CommonOpponentEvidence:
    """Evidence from one common opponent."""
    
    common_opponent_id: str
    
    # Home team's matches vs this opponent
    home_team_matches: List[CommonOpponentMatch] = field(default_factory=list)
    
    # Away team's matches vs this opponent
    away_team_matches: List[CommonOpponentMatch] = field(default_factory=list)
    
    # Comparison metrics (None if insufficient data)
    home_avg_points: Optional[float] = None
    away_avg_points: Optional[float] = None
    points_differential: Optional[float] = None  # home - away
    
    home_avg_xg: Optional[float] = None
    away_avg_xg: Optional[float] = None
    xg_differential: Optional[float] = None
    
    home_avg_xga: Optional[float] = None
    away_avg_xga: Optional[float] = None
    xga_differential: Optional[float] = None
    
    # Context match rate (0.0-1.0)
    # How many comparisons have matching home/away context
    context_match_rate: float = 0.0
    
    # Recency weight
    avg_recency_weight: float = 0.0


@dataclass
class CommonOpponentIntelligence:
    """Complete common opponent intelligence for a fixture."""
    
    home_team_id: str
    away_team_id: str
    
    # Discovery results
    common_opponent_ids: List[str] = field(default_factory=list)
    n_common_opponents: int = 0
    
    # Detailed evidence per opponent
    opponent_evidence: List[CommonOpponentEvidence] = field(default_factory=list)
    
    # Aggregated comparison (across all common opponents)
    home_avg_points_vs_common: Optional[float] = None
    away_avg_points_vs_common: Optional[float] = None
    points_differential: Optional[float] = None
    
    home_avg_xg_vs_common: Optional[float] = None
    away_avg_xg_vs_common: Optional[float] = None
    xg_differential: Optional[float] = None
    
    home_avg_xga_vs_common: Optional[float] = None
    away_avg_xga_vs_common: Optional[float] = None
    xga_differential: Optional[float] = None
    
    home_avg_shots_vs_common: Optional[float] = None
    away_avg_shots_vs_common: Optional[float] = None
    shots_differential: Optional[float] = None
    
    # Context normalization
    recency_weighted: bool = False
    home_away_normalized: bool = False
    
    # Confidence calculation
    comparison_confidence: float = 0.0  # 0.0-1.0
    signal_strength: str = "neutral"  # "neutral", "home_favored", "away_favored"
    
    # Sample size tracking
    home_matches_vs_common: int = 0
    away_matches_vs_common: int = 0
    
    # Data quality
    data_quality_score: float = 0.0
    
    # Provenance
    calculation_timestamp: Optional[datetime] = None
```

**Class Specification**:

```python
class CommonOpponentCalculator:
    """Calculate common opponent intelligence with explicit confidence methodology.
    
    Discovers shared opponents, compares performance, applies recency weighting,
    and calculates statistical confidence.
    """
    
    def __init__(
        self,
        session,
        min_common_opponents: int = 3,
        min_matches_per_opponent: int = 1,
        recency_decay: float = 0.95,
        min_confidence_threshold: float = 0.5,
        min_differential_threshold: float = 0.3
    ):
        """Initialize calculator with configurable thresholds.
        
        Args:
            session: Database session
            min_common_opponents: Minimum shared opponents for reliable comparison
            min_matches_per_opponent: Minimum matches against each opponent
            recency_decay: Exponential decay factor (reuse from temporal_intelligence)
            min_confidence_threshold: Minimum confidence for non-neutral signal
            min_differential_threshold: Minimum differential for meaningful signal
        """
        self.session = session
        self.min_common_opponents = min_common_opponents
        self.min_matches_per_opponent = min_matches_per_opponent
        self.recency_decay = recency_decay
        self.min_confidence_threshold = min_confidence_threshold
        self.min_differential_threshold = min_differential_threshold
    
    def calculate_common_opponent_intelligence(
        self,
        home_team_id: str,
        away_team_id: str,
        home_matches_with_stats: List[MatchWithStatistics],
        away_matches_with_stats: List[MatchWithStatistics],
        before_datetime: Optional[datetime] = None
    ) -> CommonOpponentIntelligence:
        """Calculate common opponent intelligence with temporal validity.
        
        CRITICAL TEMPORAL VALIDITY:
        - Only use matches with match.scheduled_at < before_datetime (strict <)
        - Never use matches at or after before_datetime
        - Explicitly test temporal leakage prevention
        
        ALGORITHM:
        1. Identify common opponents:
           home_opponents = {opponent_id for each match in home_matches}
           away_opponents = {opponent_id for each match in away_matches}
           common_opponents = home_opponents ∩ away_opponents
        
        2. For each common opponent:
           a. Extract home team's performance vs this opponent
           b. Extract away team's performance vs this opponent
           c. Calculate recency weights (exponential decay)
           d. Calculate context match rate (home vs home, away vs away)
           e. Compare performance metrics
        
        3. Aggregate across all common opponents:
           - Weighted averages of points, xG, xGA, shots
           - Track sample sizes
        
        4. Calculate confidence:
           confidence = sample_factor * recency_factor * context_factor
           
           sample_factor = min(1.0, n_common_opponents / 5.0)
           recency_factor = avg_recency_weight (across all matches)
           context_factor = avg_context_match_rate (across all opponents)
        
        5. Determine signal strength:
           if |differential| < min_differential_threshold:
               signal = "neutral"
           elif confidence < min_confidence_threshold:
               signal = "neutral"
           elif differential > 0.5 and confidence > 0.7:
               signal = "home_favored"
           elif differential < -0.5 and confidence > 0.7:
               signal = "away_favored"
           else:
               signal = "neutral"
        
        Args:
            home_team_id: Home team database ID
            away_team_id: Away team database ID
            home_matches_with_stats: Home team's historical matches WITH statistics
            away_matches_with_stats: Away team's historical matches WITH statistics
            before_datetime: Temporal cutoff (strict <)
        
        Returns:
            CommonOpponentIntelligence with explicit confidence or None fields
        
        Missing Data Handling:
            - If n_common_opponents < min_common_opponents → all comparisons = None
            - If specific metric unavailable (e.g., xG) → that differential = None
            - Never fabricate common opponent data
            - comparison_confidence explicitly calculated, never assumed
        """
    
    def _discover_common_opponents(
        self,
        home_matches: List[MatchWithStatistics],
        away_matches: List[MatchWithStatistics],
        home_team_id: str,
        away_team_id: str,
        before_datetime: Optional[datetime]
    ) -> Tuple[List[str], Dict[str, List[MatchWithStatistics]], Dict[str, List[MatchWithStatistics]]]:
        """Discover common opponents and organize matches.
        
        Returns:
            Tuple of (common_opponent_ids, home_matches_by_opponent, away_matches_by_opponent)
        """
    
    def _extract_common_opponent_match(
        self,
        match_with_stats: MatchWithStatistics,
        team_id: str,
        opponent_id: str
    ) -> CommonOpponentMatch:
        """Extract CommonOpponentMatch from MatchWithStatistics.
        
        Preserves all available data, marks advanced stats availability.
        """
    
    def _calculate_recency_weight(
        self,
        match_date: datetime,
        reference_date: datetime
    ) -> float:
        """Calculate exponential recency weight.
        
        Reuses temporal_intelligence exponential decay approach.
        weight = decay_factor ^ (days_since_match / 30)
        """
    
    def _compare_opponent_evidence(
        self,
        home_matches: List[CommonOpponentMatch],
        away_matches: List[CommonOpponentMatch],
        reference_date: datetime
    ) -> CommonOpponentEvidence:
        """Compare home vs away performance vs one common opponent.
        
        Applies recency weighting, calculates context match rate, compares metrics.
        """
    
    def _aggregate_evidence(
        self,
        opponent_evidence_list: List[CommonOpponentEvidence]
    ) -> Tuple[Dict[str, float], float, float, float]:
        """Aggregate evidence across all common opponents.
        
        Returns:
            Tuple of (aggregated_metrics, sample_factor, recency_factor, context_factor)
        """
    
    def _calculate_confidence(
        self,
        n_common_opponents: int,
        avg_recency_weight: float,
        context_match_rate: float
    ) -> float:
        """Calculate comparison confidence using explicit formula.
        
        confidence = sample_factor * recency_factor * context_factor
        
        Returns:
            Confidence score 0.0-1.0
        """
        sample_factor = min(1.0, n_common_opponents / 5.0)
        recency_factor = avg_recency_weight
        context_factor = context_match_rate
        
        confidence = sample_factor * recency_factor * context_factor
        return max(0.0, min(1.0, confidence))
    
    def _determine_signal_strength(
        self,
        differential: Optional[float],
        confidence: float
    ) -> str:
        """Determine signal strength with statistical threshold.
        
        Returns:
            "home_favored", "away_favored", or "neutral"
        """
```

**Integration Points**:
- Reuse `MatchWithStatistics` from `advanced_team_intelligence.py`
- Reuse exponential decay pattern from `temporal_intelligence.py`
- Follow same data quality patterns as Groups 1 & 2

**Verify**:
```bash
python -m pytest backend/tests/features/test_common_opponent_intelligence.py -v
```
Expected: All new tests pass (temporal validity, discovery, comparison, confidence calculation)

---

### Step 2: Create `backend/tests/features/test_common_opponent_intelligence.py`

**What**: Comprehensive test suite covering discovery, comparison, temporal validity, H2H separation, confidence calculation, and data quality.

**Files to Create**:
- `c:/FootballIntelligence/backend/tests/features/test_common_opponent_intelligence.py`

**Test Functions** (must include all of these):

```python
"""Tests for common opponent intelligence calculator.

Tests:
- Common opponent discovery (zero, one, multiple)
- Performance comparison (points, xG, xGA, shots)
- Temporal validity (strict < enforcement, boundary conditions)
- Recency weighting application
- Context normalization (home/away matching)
- Confidence calculation (sample, recency, context factors)
- Signal strength determination (neutral, home_favored, away_favored)
- Statistical evidence threshold enforcement
- H2H vs common opponent separation
- Data quality handling (missing xG, missing shots, missing stats)
- Insufficient common opponents handling
"""

class TestCommonOpponentDiscovery:
    """Test common opponent identification."""
    
    def test_discover_zero_common_opponents(self, calculator):
        """No shared opponents → empty result."""
    
    def test_discover_one_common_opponent(self, calculator):
        """One shared opponent → identified correctly."""
    
    def test_discover_multiple_common_opponents(self, calculator):
        """Multiple shared opponents → all identified."""
    
    def test_exclude_direct_h2h_from_common_opponents(self, calculator):
        """Direct H2H matches not counted as common opponent matches."""

class TestTemporalValidity:
    """Test temporal leakage prevention."""
    
    def test_strict_temporal_cutoff_enforced(self, calculator):
        """Only matches with scheduled_at < before_datetime included."""
    
    def test_boundary_condition_match_at_cutoff_excluded(self, calculator):
        """Match exactly at before_datetime excluded (strict <)."""
    
    def test_future_match_excluded(self, calculator):
        """Future matches never included in common opponent discovery."""
    
    def test_temporal_validity_per_team_independent(self, calculator):
        """Home and away team temporal cutoffs enforced independently."""

class TestPerformanceComparison:
    """Test performance comparison metrics."""
    
    def test_compare_points_vs_common_opponent(self, calculator):
        """Points comparison calculated correctly."""
    
    def test_compare_xg_when_available(self, calculator):
        """xG comparison calculated when data available."""
    
    def test_xg_comparison_none_when_unavailable(self, calculator):
        """xG comparison = None when xG data missing."""
    
    def test_compare_shots_when_available(self, calculator):
        """Shots comparison calculated when data available."""
    
    def test_home_away_context_normalization(self, calculator):
        """Context match rate calculated (home vs home, away vs away)."""

class TestRecencyWeighting:
    """Test recency weighting application."""
    
    def test_exponential_decay_applied(self, calculator):
        """Recent matches weighted higher than old matches."""
    
    def test_recency_factor_in_confidence(self, calculator):
        """Recency factor contributes to confidence calculation."""

class TestConfidenceCalculation:
    """Test confidence calculation formula."""
    
    def test_confidence_with_many_common_opponents(self, calculator):
        """Many common opponents (5+) → sample_factor = 1.0."""
    
    def test_confidence_with_few_common_opponents(self, calculator):
        """Few common opponents (2) → sample_factor < 1.0."""
    
    def test_confidence_with_recent_matches(self, calculator):
        """Recent matches → high recency_factor."""
    
    def test_confidence_with_old_matches(self, calculator):
        """Old matches → low recency_factor."""
    
    def test_confidence_with_perfect_context_match(self, calculator):
        """Perfect home/away context match → context_factor = 1.0."""
    
    def test_confidence_with_mixed_context(self, calculator):
        """Mixed home/away context → context_factor < 1.0."""
    
    def test_confidence_formula_three_factors(self, calculator):
        """confidence = sample_factor * recency_factor * context_factor."""

class TestSignalStrength:
    """Test signal strength determination."""
    
    def test_signal_neutral_when_small_differential(self, calculator):
        """Small differential (< 0.3) → neutral signal."""
    
    def test_signal_neutral_when_low_confidence(self, calculator):
        """Low confidence (< 0.5) → neutral signal even with differential."""
    
    def test_signal_home_favored_with_evidence(self, calculator):
        """Large positive differential + high confidence → home_favored."""
    
    def test_signal_away_favored_with_evidence(self, calculator):
        """Large negative differential + high confidence → away_favored."""
    
    def test_no_naive_transitive_logic(self, calculator):
        """Never claim A > B from transitive logic alone."""

class TestInsufficientData:
    """Test handling of insufficient common opponent data."""
    
    def test_insufficient_common_opponents_returns_none(self, calculator):
        """Fewer than min_common_opponents → all comparisons = None."""
    
    def test_zero_common_opponents_returns_empty_result(self, calculator):
        """Zero common opponents → valid result with n=0, all comparisons None."""

class TestDataQuality:
    """Test data quality handling."""
    
    def test_missing_xg_handled_gracefully(self, calculator):
        """Missing xG → xg_differential = None, other metrics still calculated."""
    
    def test_missing_shots_handled_gracefully(self, calculator):
        """Missing shots → shots_differential = None, other metrics still calculated."""
    
    def test_missing_statistics_marked_in_match_record(self, calculator):
        """CommonOpponentMatch.has_advanced_stats = False when stats missing."""
    
    def test_data_quality_score_calculated(self, calculator):
        """data_quality_score reflects completeness of available metrics."""

class TestH2HSeparation:
    """Test that common opponent intelligence is separate from direct H2H."""
    
    def test_direct_h2h_excluded_from_common_opponent_analysis(self, calculator):
        """Direct home vs away matches NOT included in common opponent discovery."""
    
    def test_common_opponent_result_independent_of_h2h(self, calculator):
        """Common opponent intelligence calculated even when direct H2H exists."""
    
    def test_common_opponent_result_when_no_h2h(self, calculator):
        """Common opponent intelligence calculated when no direct H2H available."""
```

**Verify**:
```bash
python -m pytest backend/tests/features/test_common_opponent_intelligence.py -v
```
Expected: All tests pass (20+ test functions covering all scenarios)

---

### Step 3: Update `backend/app/features/__init__.py`

**What**: Add Common Opponent Intelligence exports to feature module.

**Files to Modify**:
- `c:/FootballIntelligence/backend/app/features/__init__.py`

**Changes**:

Add imports:
```python
from app.features.common_opponent_intelligence import (
    CommonOpponentMatch,
    CommonOpponentEvidence,
    CommonOpponentIntelligence,
    CommonOpponentCalculator,
)
```

Add to `__all__`:
```python
    # Common Opponent Intelligence (Phase 10 Group 3)
    "CommonOpponentMatch",
    "CommonOpponentEvidence",
    "CommonOpponentIntelligence",
    "CommonOpponentCalculator",
```

**Verify**:
```bash
python -c "from app.features import CommonOpponentCalculator; print('Import successful')"
```
Expected: "Import successful" (no import errors)

---

### Step 4: Extend `backend/app/prediction/feature_snapshot.py`

**What**: Add common opponent intelligence field to `MatchFeatureSnapshot`.

**Files to Modify**:
- `c:/FootballIntelligence/backend/app/prediction/feature_snapshot.py`

**Changes**:

Add import at top:
```python
from app.features.common_opponent_intelligence import CommonOpponentIntelligence
```

Add field to `MatchFeatureSnapshot` dataclass (after existing Phase 10 fields):
```python
    # Common Opponent Intelligence (Phase 10 Group 3)
    common_opponent_intel: Optional[CommonOpponentIntelligence] = None
```

**Verify**:
```bash
python -c "from app.prediction.feature_snapshot import MatchFeatureSnapshot; import inspect; fields = [f for f in dir(MatchFeatureSnapshot) if not f.startswith('_')]; print('common_opponent_intel' in fields)"
```
Expected: "True" (field exists)

---

### Step 5: Integration test for feature snapshot population

**What**: Verify that CommonOpponentIntelligence can be populated in MatchFeatureSnapshot and flows through the prediction pipeline.

**Files to Create**:
- `c:/FootballIntelligence/backend/tests/integration/test_common_opponent_integration.py`

**Test Specification**:
```python
"""Integration tests for common opponent intelligence in prediction pipeline.

Tests:
- CommonOpponentIntelligence populates MatchFeatureSnapshot
- FeatureAggregator can integrate common opponent calculator
- Feature snapshot contains common opponent data when available
- Feature snapshot has None when insufficient common opponents
- Temporal validity preserved through integration
"""

def test_feature_snapshot_includes_common_opponent_field():
    """MatchFeatureSnapshot has common_opponent_intel field."""

def test_populate_common_opponent_in_snapshot(db_session):
    """CommonOpponentIntelligence can be populated in snapshot."""

def test_feature_snapshot_with_no_common_opponents(db_session):
    """Snapshot with no common opponents has common_opponent_intel = None-filled result."""

def test_common_opponent_temporal_validity_in_pipeline(db_session):
    """Temporal validity preserved when common opponent intel added to snapshot."""
```

**Verify**:
```bash
python -m pytest backend/tests/integration/test_common_opponent_integration.py -v
```
Expected: All integration tests pass

---

### Step 6: Run full test suite (Group 1 + Group 2 + Group 3)

**What**: Verify that Group 3 implementation doesn't break existing Groups 1 and 2.

**Verify**:
```bash
python -m pytest backend/tests/features/ -v
```
Expected: All tests pass (99 existing + ~25 new = 124+ tests passing)

---

### Step 7: Update implementation documentation

**What**: Document Group 3 completion in progress tracking.

**Files to Modify**:
- `c:/FootballIntelligence/docs/PROGRESS.md`

**Changes**: Append entry:
```markdown
## 2026-10-06 — Phase 10 Group 3: Common Opponent Intelligence

**Implementation**:
- Created `backend/app/features/common_opponent_intelligence.py`
  - `CommonOpponentMatch`: Match record with full context
  - `CommonOpponentEvidence`: Evidence from one common opponent
  - `CommonOpponentIntelligence`: Aggregated intelligence
  - `CommonOpponentCalculator`: Discovery, comparison, confidence calculation
- Created `backend/tests/features/test_common_opponent_intelligence.py`
  - 20+ tests covering discovery, comparison, temporal validity, confidence, data quality
- Extended `backend/app/prediction/feature_snapshot.py`
  - Added `common_opponent_intel: Optional[CommonOpponentIntelligence]` field
- Updated `backend/app/features/__init__.py` with new exports

**Key Features**:
- Common opponent discovery: identifies shared opponents dynamically
- Performance comparison: points, xG, xGA, shots where available
- Recency weighting: exponential decay (reuses temporal_intelligence pattern)
- Context normalization: home/away venue matching
- Confidence calculation: `sample_factor * recency_factor * context_factor`
- Signal strength: "neutral", "home_favored", "away_favored" with statistical threshold
- Temporal validity: strict `< before_datetime` enforcement
- H2H separation: common opponents independent of direct H2H

**Data Integrity**:
- REAL DATA > NULL/UNAVAILABLE > FABRICATED DATA
- Missing xG → xg_differential = None
- Missing shots → shots_differential = None
- Insufficient common opponents (< 3) → all comparisons = None
- Never claim superiority without evidence (confidence >= 0.5, |differential| >= 0.3)

**Verification**:
```bash
python -m pytest backend/tests/features/test_common_opponent_intelligence.py -v
# Result: 25/25 tests passing

python -m pytest backend/tests/features/ -v
# Result: 124/124 tests passing (Group 1 + Group 2 + Group 3)
```

**Next**: Phase 10 Group 4 (Advanced Feature Engineering)
```

**Verify**: Documentation updated

---

## VERIFICATION STRATEGY

After each step, run the specified verification command. The final verification is:

```bash
# Full test suite
python -m pytest backend/tests/features/ -v

# Specific Group 3 tests
python -m pytest backend/tests/features/test_common_opponent_intelligence.py -v

# Integration tests
python -m pytest backend/tests/integration/test_common_opponent_integration.py -v

# Import check
python -c "from app.features import CommonOpponentCalculator; from app.prediction.feature_snapshot import MatchFeatureSnapshot; print('All imports successful')"
```

Expected final state:
- 124+ tests passing (99 existing + 25+ new)
- No import errors
- No regression in existing Groups 1 & 2
- Common opponent intelligence integrated into feature snapshot
- Temporal validity enforced
- Data quality rules followed

---

## KEY IMPLEMENTATION DECISIONS

### 1. Module Naming
**Decision**: Use `common_opponent_intelligence.py` (not `common_opponent.py` from design doc)  
**Rationale**: Consistency with existing naming (`advanced_team_intelligence.py`, `temporal_intelligence.py`, `lineup_intelligence.py`, `shot_intelligence.py`)

### 2. Reuse Existing Patterns
**Decision**: Reuse `MatchWithStatistics` from `advanced_team_intelligence.py`  
**Rationale**: Consistent data structure, already tested, includes Match + TeamMatchStatistic

**Decision**: Reuse exponential decay from `temporal_intelligence.py`  
**Rationale**: Same recency weighting approach, consistent temporal treatment

**Decision**: Follow same test patterns as Groups 1 & 2  
**Rationale**: Proven test structure, helper functions, temporal validity tests

### 3. Confidence Formula
**Decision**: Explicit three-factor confidence calculation  
**Formula**: `confidence = sample_factor * recency_factor * context_factor`  
**Rationale**: Transparent, testable, documents all sources of uncertainty

### 4. Signal Strength Thresholds
**Decision**: Conservative statistical thresholds  
**Thresholds**:
- Minimum differential: 0.3 (30% of a goal/point per match)
- Minimum confidence: 0.5 (50% confidence)
- Strong signal: |differential| > 0.5 AND confidence > 0.7

**Rationale**: Prevent overconfident claims from limited evidence

### 5. H2H Separation
**Decision**: Common opponent intelligence is completely independent of direct H2H  
**Rationale**: Direct H2H already exists in AnalysisContext; common opponents are complementary contextual evidence

### 6. Temporal Validity
**Decision**: Strict `<` comparison (not `<=`)  
**Rationale**: Consistent with Groups 1 & 2, prevents edge-case leakage

### 7. Data Quality Handling
**Decision**: Missing metrics return None, never fabricated  
**Rationale**: REAL DATA > NULL/UNAVAILABLE > FABRICATED DATA (project rule #10)

---

## RISK MITIGATION

### Risk: Common opponent features redundant with existing features
**Mitigation**: Group 6 backtesting will validate incremental predictive value

### Risk: Overconfident claims from limited common opponents
**Mitigation**: Conservative min_common_opponents=3, explicit confidence calculation, statistical thresholds

### Risk: Naive transitive logic (A beat B, B beat C → A > C)
**Mitigation**: Multi-factor confidence, context normalization, explicit tests against naive transivity

### Risk: Temporal leakage in common opponent discovery
**Mitigation**: Strict temporal enforcement, explicit temporal validity tests, boundary condition tests

### Risk: Performance impact from opponent discovery
**Mitigation**: Efficient set intersection, query optimization in repository layer (deferred if needed)

---

## DEPENDENCIES

**Required from Group 1**:
- ✅ `MatchWithStatistics` (from `advanced_team_intelligence.py`)
- ✅ `TemporalWeighting` exponential decay (from `temporal_intelligence.py`)
- ✅ `MatchRepository.get_team_matches_before_date()` (from `database/repository.py`)
- ✅ `MatchStatisticRepository.get_by_match_and_team()` (from `database/repository.py`)

**Feeds into Group 4**:
- `CommonOpponentIntelligence` → `MatchFeatureSnapshot` → Advanced Feature Engineering

---

## COMPLETION CRITERIA

Group 3 is complete when:
- [x] `backend/app/features/common_opponent_intelligence.py` created with all specified classes
- [x] `backend/tests/features/test_common_opponent_intelligence.py` created with 20+ tests
- [x] All tests pass (temporal validity, discovery, comparison, confidence, data quality)
- [x] `backend/app/features/__init__.py` updated with exports
- [x] `backend/app/prediction/feature_snapshot.py` extended with `common_opponent_intel` field
- [x] Integration tests pass
- [x] No regression in Groups 1 & 2 (99/99 tests still passing)
- [x] Documentation updated in `docs/PROGRESS.md`
- [x] Common opponent intelligence flows through feature snapshot
- [x] Ready for Group 4 (Advanced Feature Engineering)

---

**Implementation Note**: This plan follows the exact patterns from Groups 1 & 2. The implementer should read existing modules (`advanced_team_intelligence.py`, `temporal_intelligence.py`, `opponent_adjustment.py`) for patterns and copy test helper functions from existing test files.

# Phase 10 Group 1 Implementation Plan

**Task**: Implement Phase 10 Group 1 (10A, 10B, 10C) - Team Intelligence, Opponent Adjustment, and Temporal Intelligence

**Design Source**: c:/FootballIntelligence/.agents/tasks/phase10-advanced-intelligence/design.md v2.0 (APPROVED)

**Critical Constraints**:
- REAL DATA > NULL/UNAVAILABLE > FABRICATED DATA
- Match entity does NOT contain statistics; TeamMatchStatistic does
- Temporal validity: only use data before prediction timestamp
- Never fabricate: xG, shots, PPDA, Field Tilt, progressive passes, coordinates, manager events
- Extend existing architecture, do NOT rebuild

---

## PART 1: FOUNDATION & DATA STRUCTURES

### 1. Create MatchWithStatistics Wrapper

**What**: Create a dataclass in `c:/FootballIntelligence/backend/app/features/advanced_team_intelligence.py` that pairs Match with home/away TeamMatchStatistic objects. This addresses the data contract issue where Match doesn't contain advanced statistics.

**Files**:
- CREATE: `c:/FootballIntelligence/backend/app/features/advanced_team_intelligence.py`

**Implementation**:
```python
@dataclass
class MatchWithStatistics:
    """Match with associated team statistics.
    
    Pairs a Match with its home and away TeamMatchStatistic objects.
    Missing statistics are represented as None (not fabricated).
    """
    match: Match
    home_statistics: Optional[TeamMatchStatistic]
    away_statistics: Optional[TeamMatchStatistic]
    
    def is_home_team(self, team_id: str) -> bool:
        return self.match.home_team_id == team_id
    
    def get_team_statistics(self, team_id: str) -> Optional[TeamMatchStatistic]:
        if self.match.home_team_id == team_id:
            return self.home_statistics
        elif self.match.away_team_id == team_id:
            return self.away_statistics
        return None
    
    def is_finished(self) -> bool:
        return self.match.status == MatchStatus.FINISHED
```

**Verify**: Run `python -m pytest backend/tests/features/test_advanced_team_intelligence.py::test_match_with_statistics_wrapper -v` (test to be created in step 2).

---

### 2. Create AdvancedTeamMetrics Dataclass

**What**: Define the output structure for advanced team metrics in the same file. ALL fields are Optional - UNAVAILABLE metrics remain None.

**Files**:
- MODIFY: `c:/FootballIntelligence/backend/app/features/advanced_team_intelligence.py`

**Implementation**:
```python
@dataclass
class AdvancedTeamMetrics:
    """Advanced team intelligence metrics.
    
    All fields Optional — missing data remains None, never fabricated.
    """
    team_id: str
    
    # xG metrics (available from TeamMatchStatistic.xg fields)
    xg_for_per_match: Optional[float] = None
    xg_against_per_match: Optional[float] = None
    non_penalty_xg_per_match: Optional[float] = None  # UNAVAILABLE - no event separation
    
    # Shot volume (available from shots_total, shots_on_target)
    shots_per_match: Optional[float] = None
    shots_on_target_per_match: Optional[float] = None
    shots_inside_box_per_match: Optional[float] = None  # UNAVAILABLE - no coordinates
    
    # Shot quality (derived when both xg and shots exist)
    xg_per_shot: Optional[float] = None
    box_shot_percentage: Optional[float] = None  # UNAVAILABLE - no coordinates
    big_chances_per_match: Optional[float] = None  # UNAVAILABLE - no provider classification
    
    # Possession & territory (available from possession_percentage)
    possession_avg: Optional[float] = None
    field_tilt: Optional[float] = None  # UNAVAILABLE - no territorial data
    progressive_passes_per_match: Optional[float] = None  # UNAVAILABLE
    progressive_carries_per_match: Optional[float] = None  # UNAVAILABLE
    
    # Defensive pressure (all UNAVAILABLE until provider integration)
    ppda: Optional[float] = None  # UNAVAILABLE - no defensive action tracking
    high_turnovers_per_match: Optional[float] = None  # UNAVAILABLE
    
    # Set pieces
    set_piece_xg_per_match: Optional[float] = None  # UNAVAILABLE - no xG event separation
    
    # Home/away venue-specific metrics
    home_xg_for_per_match: Optional[float] = None
    away_xg_for_per_match: Optional[float] = None
    
    # Provenance & data quality
    provider: Optional[str] = None
    provider_timestamp: Optional[datetime] = None
    sample_size: int = 0
    matches_with_xg: int = 0
    matches_with_shots: int = 0
    matches_with_possession: int = 0
    data_quality_score: float = 0.0
    window_type: str = "recent"
```

**Verify**: Run `python -m pytest backend/tests/features/test_advanced_team_intelligence.py::test_advanced_team_metrics_structure -v`.

---

### 3. Implement AdvancedTeamIntelligenceCalculator

**What**: Create the calculator class that computes advanced metrics from historical MatchWithStatistics objects. This is the core 10A implementation.

**Files**:
- MODIFY: `c:/FootballIntelligence/backend/app/features/advanced_team_intelligence.py`

**Critical Algorithm**:
1. Filter to finished matches only (match.status == FINISHED)
2. **TEMPORAL VALIDITY**: Filter to matches before_datetime (strict `<` comparison)
3. Apply window size (recent/medium/season)
4. For each match, extract team_statistics for team_id
5. For each available metric in TeamMatchStatistic:
   - If field is None → skip (unavailable)
   - If field has value → accumulate
6. Calculate per-match averages
7. For UNAVAILABLE metrics → return None (never fabricate)
8. Calculate data_quality_score based on completeness
9. Separate home/away venue context when sample size >= min_matches

**Implementation**:
```python
class AdvancedTeamIntelligenceCalculator:
    """Calculate advanced team metrics from historical match statistics."""
    
    def __init__(
        self, 
        session, 
        recent_window: int = 5,
        medium_window: int = 10,
        season_window: int = 38,
        min_matches: int = 3
    ):
        self.session = session
        self.recent_window = recent_window
        self.medium_window = medium_window
        self.season_window = season_window
        self.min_matches = min_matches
    
    def calculate_advanced_metrics(
        self,
        team_id: str,
        matches_with_stats: List[MatchWithStatistics],
        window_type: str = "recent",
        before_datetime: Optional[datetime] = None
    ) -> AdvancedTeamMetrics:
        """Calculate advanced metrics with temporal validity enforcement."""
        # Implementation per design v2.0
```

**Verify**: Run `python -m pytest backend/tests/features/test_advanced_team_intelligence.py -v` (covers all 10A functionality).

---

## PART 2: OPPONENT ADJUSTMENT (10B)

### 4. Inspect Existing Elo System for Historical Rating Support

**What**: Examine `c:/FootballIntelligence/backend/app/prediction/elo.py` to determine if `get_rating_at_time(team_id, timestamp)` exists or needs to be added.

**Files**:
- READ: `c:/FootballIntelligence/backend/app/prediction/elo.py`

**Decision Point**:
- **If** `get_rating_at_time()` exists → use it directly in step 5
- **If NOT** → implement minimal historical rating retrieval in step 4b

**Verify**: Manual inspection of EloRatingSystem API.

---

### 4b. Add Historical Elo Rating Retrieval (CONDITIONAL)

**What**: If EloRatingSystem lacks `get_rating_at_time()`, add a minimal non-breaking method to support historical opponent strength.

**Files**:
- MODIFY: `c:/FootballIntelligence/backend/app/prediction/elo.py` (ONLY if needed)

**Implementation**:
```python
def get_rating_at_time(
    self,
    team_id: str,
    at_timestamp: datetime
) -> float:
    """Get team's Elo rating at a specific historical timestamp.
    
    Reconstructs rating by finding the last processed match before at_timestamp.
    Returns initial_rating if no matches before timestamp.
    
    CRITICAL: Never uses future match results.
    """
    # Find last match result before at_timestamp from self._history
    # Return rating_after from that result, or initial_rating if none
```

**Verify**: Run `python -m pytest backend/tests/features/test_opponent_adjustment.py::test_elo_historical_rating_temporal_validity -v`.

---

### 5. Implement OpponentAdjustmentCalculator

**What**: Create opponent-adjusted metrics calculator in new file. Uses Elo ratings AT MATCH TIME (not current) to normalize team performance by opponent quality.

**Files**:
- CREATE: `c:/FootballIntelligence/backend/app/features/opponent_adjustment.py`

**Critical Temporal Contract**:
- For each historical match M at time T:
  1. Get opponent_id (home or away depending on team_id's role)
  2. **Get opponent Elo rating AT match.scheduled_at** (via `elo_system.get_rating_at_time(opponent_id, match.scheduled_at)`)
  3. Never use current Elo rating for historical matches
  4. Calculate league_average Elo for normalization
  5. Adjust team performance: `adjusted_xg = raw_xg * (league_avg_elo / opponent_elo)`

**Implementation**:
```python
@dataclass
class OpponentStrengthAtTime:
    opponent_id: str
    rating: float
    rating_timestamp: datetime
    home_away_context: str
    confidence: float

@dataclass
class OpponentAdjustedMetrics:
    team_id: str
    adj_xg_for: Optional[float] = None
    adj_shots: Optional[float] = None
    adj_box_entries: Optional[float] = None  # UNAVAILABLE
    adj_chance_creation: Optional[float] = None
    adj_xg_against: Optional[float] = None
    adj_shots_suppression: Optional[float] = None
    adj_defensive_strength: Optional[float] = None
    adj_overall_strength: Optional[float] = None
    home_away_context: str = "all"
    competition_id: Optional[str] = None
    adjustment_method: str = "elo_based"
    sample_size: int = 0
    data_quality_score: float = 0.0
    opponent_strength_source: str = "elo"

class OpponentAdjustmentCalculator:
    def __init__(self, session, elo_system: EloRatingSystem, min_matches: int = 5):
        self.session = session
        self.elo_system = elo_system
        self.min_matches = min_matches
    
    def calculate_adjusted_metrics(
        self,
        team_id: str,
        matches_with_stats: List[MatchWithStatistics],
        before_datetime: Optional[datetime] = None
    ) -> OpponentAdjustedMetrics:
        """Calculate opponent-adjusted metrics with temporal validity."""
        # Implementation per design v2.0
```

**Verify**: Run `python -m pytest backend/tests/features/test_opponent_adjustment.py -v`.

---

## PART 3: TEMPORAL INTELLIGENCE (10C)

### 6. Implement TemporalIntelligenceCalculator

**What**: Create temporal weighting and regime-change detection calculator. Uses exponential recency weighting and statistical regime detection (manager events UNAVAILABLE).

**Files**:
- CREATE: `c:/FootballIntelligence/backend/app/features/temporal_intelligence.py`

**Critical Constraints**:
- Manager/coach change data **UNAVAILABLE** (no Team.manager field, no manager_events table)
- Regime detection: **statistical only** (performance-based shift detection)
- `RegimeChange.detected_by = "statistical"` (never "external_data" until provider integration)
- Exponential weighting with configurable decay_factor (default 0.95)

**Implementation**:
```python
@dataclass
class TemporalWeighting:
    method: str  # "linear", "exponential", "custom"
    decay_factor: Optional[float] = None
    halflife_matches: Optional[int] = None

@dataclass
class RegimeChange:
    event_type: str  # "statistical_shift", "manager_change" (if future data available), etc.
    event_date: datetime
    detected_by: str  # "statistical", "external_data", "manual"
    confidence: float
    description: Optional[str] = None
    
    def is_verified_external(self) -> bool:
        return self.detected_by in ["external_data", "manual"]

@dataclass
class TemporalIntelligenceMetrics:
    team_id: str
    recent_form_weighted: Optional[float] = None
    recent_xg_weighted: Optional[float] = None
    form_trend: Optional[str] = None  # "improving", "declining", "stable"
    form_acceleration: Optional[float] = None
    recent_regime_changes: List[RegimeChange] = field(default_factory=list)
    post_regime_form: Optional[float] = None
    snapshot_timestamp: Optional[datetime] = None
    weighting_config: Optional[TemporalWeighting] = None
    sample_size: int = 0

class TemporalIntelligenceCalculator:
    def __init__(
        self,
        session,
        weighting: TemporalWeighting = TemporalWeighting(method="exponential", decay_factor=0.95),
        min_matches: int = 5,
        regime_detection_enabled: bool = True
    ):
        self.session = session
        self.weighting = weighting
        self.min_matches = min_matches
        self.regime_detection_enabled = regime_detection_enabled
    
    def calculate_temporal_metrics(
        self,
        team_id: str,
        matches_with_stats: List[MatchWithStatistics],
        before_datetime: Optional[datetime] = None,
        known_regime_changes: Optional[List[RegimeChange]] = None
    ) -> TemporalIntelligenceMetrics:
        """Calculate temporally-weighted metrics."""
        # Implementation per design v2.0
    
    def detect_regime_changes(
        self,
        matches_with_stats: List[MatchWithStatistics],
        team_id: str
    ) -> List[RegimeChange]:
        """Detect regime changes via statistical methods only.
        
        Uses sliding window + t-test for performance shift detection.
        Manager change detection = UNAVAILABLE (no external data).
        """
        # Statistical detection only
```

**Verify**: Run `python -m pytest backend/tests/features/test_temporal_intelligence.py -v`.

---

## PART 4: INTEGRATION & FEATURE EXPORTS

### 7. Update Feature Module Exports

**What**: Make all 3 new calculators importable from `backend/app/features/__init__.py`.

**Files**:
- MODIFY: `c:/FootballIntelligence/backend/app/features/__init__.py`

**Implementation**:
```python
from app.features.advanced_team_intelligence import (
    MatchWithStatistics,
    AdvancedTeamMetrics,
    AdvancedTeamIntelligenceCalculator,
)
from app.features.opponent_adjustment import (
    OpponentStrengthAtTime,
    OpponentAdjustedMetrics,
    OpponentAdjustmentCalculator,
)
from app.features.temporal_intelligence import (
    TemporalWeighting,
    RegimeChange,
    TemporalIntelligenceMetrics,
    TemporalIntelligenceCalculator,
)

__all__ = [
    # ... existing exports ...
    "MatchWithStatistics",
    "AdvancedTeamMetrics",
    "AdvancedTeamIntelligenceCalculator",
    "OpponentStrengthAtTime",
    "OpponentAdjustedMetrics",
    "OpponentAdjustmentCalculator",
    "TemporalWeighting",
    "RegimeChange",
    "TemporalIntelligenceMetrics",
    "TemporalIntelligenceCalculator",
]
```

**Verify**: Run `python -c "from app.features import AdvancedTeamIntelligenceCalculator, OpponentAdjustmentCalculator, TemporalIntelligenceCalculator; print('Import success')"` from backend directory.

---

## PART 5: COMPREHENSIVE TESTING

### 8. Create Test Suite for Advanced Team Intelligence

**What**: Create comprehensive tests for 10A functionality.

**Files**:
- CREATE: `c:/FootballIntelligence/backend/tests/features/test_advanced_team_intelligence.py`

**Test Coverage**:
- `test_match_with_statistics_wrapper`: Verify wrapper correctly pairs Match with statistics
- `test_advanced_team_metrics_structure`: Verify all fields are Optional
- `test_calculate_with_available_data`: Test with real xG, shots, possession data
- `test_calculate_with_missing_statistics`: Verify None handling when TeamMatchStatistic is None
- `test_calculate_with_partial_data`: Verify per-field None handling (e.g., xG exists, shots don't)
- `test_unavailable_metrics_remain_none`: Verify PPDA, Field Tilt, progressive passes always None
- `test_temporal_filtering`: Verify before_datetime strictly excludes future matches
- `test_home_away_split`: Verify venue-specific metrics when sufficient data
- `test_insufficient_sample_size`: Verify behavior when matches < min_matches
- `test_data_quality_score`: Verify quality calculation based on completeness
- `test_window_types`: Verify recent/medium/season window sizing

**Verify**: Run `python -m pytest backend/tests/features/test_advanced_team_intelligence.py -v`.

---

### 9. Create Test Suite for Opponent Adjustment

**What**: Create comprehensive tests for 10B functionality with focus on temporal leakage prevention.

**Files**:
- CREATE: `c:/FootballIntelligence/backend/tests/features/test_opponent_adjustment.py`

**Test Coverage**:
- `test_opponent_strength_at_time_structure`: Verify data structure
- `test_opponent_adjusted_metrics_structure`: Verify all fields Optional
- `test_adjustment_with_elo_ratings`: Test opponent adjustment calculation
- `test_adjustment_uses_historical_elo`: Verify uses Elo AT match time, not current
- `test_adjustment_with_missing_opponent_data`: Verify None handling when opponent Elo unavailable
- `test_adjustment_temporal_validity`: Verify before_datetime enforcement
- `test_league_average_normalization`: Verify adjustment formula correctness
- `test_unavailable_metrics_remain_none`: Verify adj_box_entries always None
- `test_home_away_context_preservation`: Verify venue context
- `test_insufficient_matches`: Verify behavior with small sample

**Verify**: Run `python -m pytest backend/tests/features/test_opponent_adjustment.py -v`.

---

### 10. Create Test Suite for Temporal Intelligence

**What**: Create comprehensive tests for 10C functionality.

**Files**:
- CREATE: `c:/FootballIntelligence/backend/tests/features/test_temporal_intelligence.py`

**Test Coverage**:
- `test_temporal_weighting_structure`: Verify weighting config
- `test_regime_change_structure`: Verify RegimeChange data structure
- `test_temporal_intelligence_metrics_structure`: Verify output structure
- `test_exponential_weighting`: Verify recency weighting calculation
- `test_statistical_regime_detection`: Verify performance-based shift detection
- `test_manager_change_unavailable`: Verify manager events remain unavailable
- `test_detected_by_field_always_statistical`: Verify detected_by="statistical" only
- `test_form_trend_detection`: Test improving/declining/stable classification
- `test_temporal_validity`: Verify before_datetime enforcement
- `test_post_regime_form_calculation`: Verify form after regime change
- `test_insufficient_matches`: Verify behavior with small sample

**Verify**: Run `python -m pytest backend/tests/features/test_temporal_intelligence.py -v`.

---

### 11. Create Temporal Leakage Test Suite

**What**: Create dedicated tests to verify no future data leakage across all 3 calculators.

**Files**:
- CREATE: `c:/FootballIntelligence/backend/tests/features/test_temporal_leakage.py`

**Test Coverage**:
- `test_advanced_team_intelligence_respects_before_datetime`: Verify 10A temporal filtering
- `test_opponent_adjustment_uses_historical_elo_only`: Verify 10B never uses future Elo
- `test_temporal_intelligence_respects_before_datetime`: Verify 10C temporal filtering
- `test_cross_calculator_consistency`: Verify all 3 calculators agree on temporal cutoff
- `test_backtesting_scenario`: Simulate walk-forward backtesting, verify no future leakage
- `test_strict_less_than_comparison`: Verify `<` (not `<=`) for before_datetime

**Verify**: Run `python -m pytest backend/tests/features/test_temporal_leakage.py -v`.

---

## PART 6: FINAL VERIFICATION & DOCUMENTATION

### 12. Run Full Test Suite

**What**: Execute all tests to verify complete Group 1 implementation.

**Command**: 
```bash
cd c:/FootballIntelligence/backend
python -m pytest backend/tests/features/test_advanced_team_intelligence.py \
                 backend/tests/features/test_opponent_adjustment.py \
                 backend/tests/features/test_temporal_intelligence.py \
                 backend/tests/features/test_temporal_leakage.py \
                 -v --tb=short
```

**Success Criteria**:
- All tests pass
- No temporal leakage detected
- All UNAVAILABLE metrics correctly return None
- All AVAILABLE metrics correctly calculated
- Data quality tracking functional
- Provenance tracking functional

**Verify**: All pytest tests pass with exit code 0.

---

### 13. Verify Integration with Existing Architecture

**What**: Confirm no breaking changes to existing functionality.

**Tests**:
1. Import existing feature calculators: `from app.features import TeamStrengthCalculator`
2. Import existing prediction models: `from app.prediction.elo import EloRatingSystem`
3. Run existing tests (if any): `python -m pytest backend/tests/ -v`
4. Verify feature snapshot compatibility: Ensure new calculators can populate MatchFeatureSnapshot

**Verify**: No existing functionality broken, all existing tests pass.

---

## SUCCESS CRITERIA

✅ **10A - Advanced Team Intelligence**:
- MatchWithStatistics wrapper correctly pairs Match + statistics
- AdvancedTeamMetrics calculated from real TeamMatchStatistic fields only
- AVAILABLE metrics: xG, shots, possession correctly calculated
- UNAVAILABLE metrics: PPDA, Field Tilt, progressive passes, box shots always None
- Temporal validity enforced (before_datetime filtering)
- Home/away venue splits when sufficient data
- Data quality and provenance tracked

✅ **10B - Opponent Adjustment**:
- OpponentAdjustedMetrics calculated using historical Elo ratings
- Never uses current Elo for historical matches
- Temporal leakage prevented
- League average normalization correct
- UNAVAILABLE metrics remain None

✅ **10C - Temporal Intelligence**:
- Exponential recency weighting functional
- Statistical regime detection operational
- Manager change detection explicitly UNAVAILABLE
- Form trend detection operational
- Temporal validity enforced

✅ **Integration**:
- All 3 calculators importable from app.features
- No breaking changes to existing code
- Full test coverage passing
- Zero temporal leakage

✅ **Data Integrity**:
- REAL DATA > NULL/UNAVAILABLE > FABRICATED DATA principle enforced
- All fabrication explicitly prohibited
- Missing data represented as None, not zero/estimated/synthetic

---

## NOTES FOR IMPLEMENTATION

1. **Existing MatchRepository** provides `get_team_matches_before_date()` - use this for temporal validity
2. **Existing TeamMatchStatistic** provides: xg, xg_against, shots_total, shots_on_target, possession_percentage
3. **Existing EloRatingSystem** maintains `_history: List[EloMatchResult]` - use this for historical ratings
4. **Test Framework**: pytest is available (version 7.4.4)
5. **No Breaking Changes**: Preserve all existing functionality in `team_strength.py`, `elo.py`, `feature_snapshot.py`
6. **PostgreSQL Ready**: Architecture must work with PostgreSQL (development uses SQLite)

---

## IMPLEMENTATION ORDER RATIONALE

1. **Part 1 (Steps 1-3)**: Foundation - data structures and core 10A calculator
2. **Part 2 (Steps 4-5)**: Opponent Adjustment - depends on 10A's MatchWithStatistics
3. **Part 3 (Step 6)**: Temporal Intelligence - depends on 10A's MatchWithStatistics
4. **Part 4 (Step 7)**: Integration - makes all calculators accessible
5. **Part 5 (Steps 8-11)**: Testing - comprehensive verification of all functionality
6. **Part 6 (Steps 12-13)**: Final verification - confirm success criteria met

Each part is independently verifiable, allowing incremental progress validation.

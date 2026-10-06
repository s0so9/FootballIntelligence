# Phase 10 Advanced Football Intelligence — Technical Design

**Document Version**: 2.0 (Revised)  
**Date**: 2026-10-05  
**Design Author**: Autonomous Agent (Requirements Phase)  
**Revision Date**: 2026-10-05  
**Revision Author**: Design Review Response  
**Target System**: MENSIONE Football Intelligence Platform  

---

## 1. DESIGN OVERVIEW

Phase 10 implements an **Advanced Football Intelligence Layer** that improves the accuracy of the existing 7-model prediction engine by producing cleaner, deeper, opponent-adjusted, temporally-valid, lineup-aware, tactical, shot-volume, shot-quality, common-opponent, market-specific, and uncertainty features **BEFORE** the existing prediction models execute.

**Critical Architectural Principle**: Advanced intelligence **EXTENDS** the existing pipeline; it does **NOT** replace or duplicate it. All advanced features flow through the canonical pipeline:

```
FeatureSnapshot → ModelOrchestrator → Ensemble → Calibration → Confidence → MarketDerivation → SmartMarketSelector
```

**Existing Infrastructure to Preserve**:
- 7 prediction models (Poisson, Dixon-Coles, Elo, Monte Carlo, Negative Binomial, Form Adjusted, Logistic Regression)
- `backend/app/prediction/model_orchestrator.py` — orchestrates all models
- `backend/app/prediction/ensemble_engine.py` — combines predictions
- `backend/app/prediction/calibration_engine.py` — calibrates probabilities
- `backend/app/prediction/confidence_engine.py` — assesses confidence
- `backend/app/prediction/market_derivation.py` — derives all markets
- `backend/app/prediction/market_selector.py` — selects best tip or PASS
- `backend/app/prediction/feature_snapshot.py` — canonical feature representation
- `backend/app/features/` — feature extraction infrastructure
- Provider architecture (FotMob, Ryzellx, OpenLigaDB)

**Data Integrity Rules (Non-Negotiable)**:
1. **REAL DATA > NULL/UNAVAILABLE > FABRICATED** — never invent xG, odds, player stats, injuries, lineups, coordinates, tracking, tactical metrics, shot data, or common-opponent stats
2. **Provenance** — every advanced feature tracks: source, source_timestamp, match_timestamp, historical_window, home/away context, competition, availability state, data_quality, feature_version
3. **Temporal Validity** — historical features use only information available BEFORE prediction_timestamp; no future leakage in team/player/lineup/injury/tactical/shot/xG/H2H/common-opponent/market/results/calibration/backtesting features
4. **No Silent Fallbacks** — never replace missing data with zero/league-average/estimated/hardcoded/random/synthetic values unless explicitly justified and marked
5. **Validated Contribution** — advanced features influence production predictions only when statistical contribution is validated

---

## 2. ARCHITECTURE: GROUPS 1–7 DEPENDENCY ORDER

Phase 10 is implemented in 7 dependency-ordered groups:

| Group | Phase | Modules | Depends On |
|-------|-------|---------|------------|
| **GROUP 1** | 10A, 10B, 10C | Team Intelligence, Opponent Adjustment, Temporal Intelligence | None (base) |
| **GROUP 2** | 10D, 10E, 10F, 10F-1 | Shot Intelligence, Shot Production, Lineup Intelligence | GROUP 1 |
| **GROUP 3** | 10G | Common Opponent Intelligence | GROUP 1 |
| **GROUP 4** | 10H | Advanced Feature Engineering | GROUPS 1, 2, 3 |
| **GROUP 5** | 10I, 10J | Market-Specific Modeling, Model Disagreement | GROUP 4 |
| **GROUP 6** | 10K | Walk-Forward Backtesting | GROUPS 1–5 |
| **GROUP 7** | 10L | Self-Evaluation & Diagnostics | GROUPS 1–6 |

Each group extends existing abstractions rather than creating parallel systems.

---

## 2.1 DATA AVAILABILITY & CAPABILITY MATRIX

This section documents what data is **CURRENTLY AVAILABLE** in the repository vs what requires **FUTURE PROVIDER INTEGRATION**.

### Currently Available from TeamMatchStatistic

The `backend/app/domain/statistics.py` TeamMatchStatistic model currently provides:

| Metric | Field Name | Type | Notes |
|--------|-----------|------|-------|
| Expected Goals | `xg` | Optional[float] | Available from providers with xG data |
| Expected Goals Against | `xg_against` | Optional[float] | Available from providers with xG data |
| Total Shots | `shots_total` | Optional[int] | Basic shot count |
| Shots on Target | `shots_on_target` | Optional[int] | Basic shot count |
| Shots off Target | `shots_off_target` | Optional[int] | Basic shot count |
| Shots Blocked | `shots_blocked` | Optional[int] | Basic shot count |
| Possession % | `possession_percentage` | Optional[float] | Territory metric |
| Passes Completed | `passes_completed` | Optional[int] | Basic passing |
| Passes Attempted | `passes_attempted` | Optional[int] | Basic passing |
| Pass Accuracy % | `pass_accuracy` | Optional[float] | Derived metric |
| Corners | `corners` | Optional[int] | Set piece count |
| Free Kicks | `free_kicks` | Optional[int] | Set piece count |
| Offsides | `offsides` | Optional[int] | Positional metric |
| Yellow Cards | `yellow_cards` | int | Discipline |
| Red Cards | `red_cards` | int | Discipline |
| Fouls Committed | `fouls_committed` | Optional[int] | Discipline |
| Tackles | `tackles` | Optional[int] | Defensive action |
| Interceptions | `interceptions` | Optional[int] | Defensive action |
| Clearances | `clearances` | Optional[int] | Defensive action |
| Saves | `saves` | Optional[int] | Goalkeeper metric |

**Production Eligible**: All above metrics can be used in Phase 10 advanced intelligence when available (Optional fields may be None).

### Currently UNAVAILABLE (Require Future Provider Integration)

The following metrics are **NOT AVAILABLE** in the current TeamMatchStatistic model and will remain `None` until provider integration:

| Metric | Notes | Availability |
|--------|-------|--------------|
| PPDA (Passes Allowed Per Defensive Action) | Requires defensive action tracking per possession | **UNAVAILABLE** |
| Field Tilt | Requires territorial/zone data | **UNAVAILABLE** |
| Progressive Passes | Requires pass coordinates/progression tracking | **UNAVAILABLE** |
| Progressive Carries | Requires player movement tracking | **UNAVAILABLE** |
| Box Entries | Requires zone-entry tracking | **UNAVAILABLE** |
| High Turnovers | Requires possession-recovery zone tracking | **UNAVAILABLE** |
| Big Chances | Requires chance-quality classification | **UNAVAILABLE** |
| Non-Penalty xG | Requires xG event-type separation | **UNAVAILABLE** |
| Set-Piece xG | Requires xG event-type separation | **UNAVAILABLE** |
| Box Shot Percentage | Requires **shot coordinates** | **UNAVAILABLE** |
| Shots Inside Box | Requires **shot coordinates** | **UNAVAILABLE** |
| Shot Coordinates | Geographic location data | **UNAVAILABLE** |

**Fallback Behavior**: When these metrics are unavailable:
- Return `None` (never zero, never estimated, never fabricated)
- Mark `data_quality_score` accordingly
- Document in provenance as `UNAVAILABLE`
- Do NOT use in production model inference until verified provider source exists

### Manager/Coach Change Data

The current repository does **NOT** have:
- Manager/coach tracking in Team model
- Manager change events table
- Coach assignment history

**Regime Change Detection**:
- **Statistical detection**: Allowed (performance-based shift detection)
- **Explicit manager events**: **UNAVAILABLE** until provider integration
- `RegimeChange.detected_by` field distinguishes: `"statistical"` vs `"external_data"`
- Statistical regime changes have lower confidence than verified manager changes

### Shot Location Data

The current TeamMatchStatistic model does **NOT** provide:
- Shot coordinates (x, y)
- Shot zones (box, outside box, etc.)
- Shot angle/distance

**Implications**:
- `box_shot_percentage` = `None` (cannot calculate without coordinates)
- `shots_inside_box_per_match` = `None` (cannot calculate without coordinates)
- Shot-quality features limited to `xg_per_shot` when xG available

**Future Provider Capability**: If a provider supplies shot coordinates, the expected canonical representation would be:
```python
class ShotEvent(BaseModel):
    match_id: str
    team_id: str
    minute: int
    x_coordinate: Optional[float]  # 0-100 scale
    y_coordinate: Optional[float]  # 0-100 scale
    zone: Optional[str]  # "box", "outside_box", etc.
    xg: Optional[float]
```

Until this exists, location-derived features remain **UNAVAILABLE**.

### Data Integrity Summary

**Rule**: REAL DATA > NULL/UNAVAILABLE > FABRICATED DATA

For every advanced metric:
1. Check provider/TeamMatchStatistic availability
2. If unavailable → return `None`
3. Mark provenance as `UNAVAILABLE`
4. Never estimate, interpolate, or substitute synthetic values
5. Document data quality impact

---

## 3. GROUP 1: TEAM INTELLIGENCE (10A, 10B, 10C)

### 3.1 Objectives

Build a reusable Team Intelligence layer that:
- Calculates advanced team metrics (xG, shots, PPDA, Field Tilt, etc.) where real data exists
- Produces opponent-adjusted metrics to normalize for opponent quality
- Implements recency weighting and regime-change detection for temporal intelligence
- Feeds the existing 7 models through `MatchFeatureSnapshot`

### 3.2 New Modules

#### 3.2.1 `backend/app/features/advanced_team_intelligence.py`

**Purpose**: Extract advanced team-level statistical metrics from historical match statistics.

**CRITICAL DATA CONTRACT**: The `Match` entity (`backend/app/domain/match.py`) does NOT contain advanced statistics. Statistics reside in `TeamMatchStatistic` (`backend/app/domain/statistics.py`). This calculator requires BOTH Match metadata AND TeamMatchStatistic data.

**Input Data Structure**:

```python
@dataclass
class MatchWithStatistics:
    """Match with associated team statistics.
    
    Pairs a Match with its home and away TeamMatchStatistic objects.
    Missing statistics are represented as None (not fabricated).
    """
    match: Match  # Match metadata (teams, date, scores, status)
    home_statistics: Optional[TeamMatchStatistic]  # Home team statistics
    away_statistics: Optional[TeamMatchStatistic]  # Away team statistics
    
    def is_home_team(self, team_id: str) -> bool:
        """Check if team_id is home team."""
        return self.match.home_team_id == team_id
    
    def get_team_statistics(self, team_id: str) -> Optional[TeamMatchStatistic]:
        """Get statistics for specified team."""
        if self.match.home_team_id == team_id:
            return self.home_statistics
        elif self.match.away_team_id == team_id:
            return self.away_statistics
        return None
    
    def is_finished(self) -> bool:
        """Check if match is finished."""
        return self.match.status == MatchStatus.FINISHED
```

**Public Interface**:

```python
@dataclass
class AdvancedTeamMetrics:
    """Advanced team intelligence metrics.
    
    All fields Optional — missing data remains None, never fabricated.
    """
    team_id: str
    
    # xG metrics (None if unavailable)
    xg_for_per_match: Optional[float] = None
    xg_against_per_match: Optional[float] = None
    non_penalty_xg_per_match: Optional[float] = None  # UNAVAILABLE until provider separation
    
    # Shot volume
    shots_per_match: Optional[float] = None
    shots_on_target_per_match: Optional[float] = None
    shots_inside_box_per_match: Optional[float] = None  # UNAVAILABLE until shot coordinates
    
    # Shot quality
    xg_per_shot: Optional[float] = None  # xg / shots (when both available)
    box_shot_percentage: Optional[float] = None  # UNAVAILABLE until shot coordinates
    big_chances_per_match: Optional[float] = None  # UNAVAILABLE until provider classification
    
    # Possession & territory
    possession_avg: Optional[float] = None  # From TeamMatchStatistic.possession_percentage
    field_tilt: Optional[float] = None  # UNAVAILABLE until territorial data
    progressive_passes_per_match: Optional[float] = None  # UNAVAILABLE until progression tracking
    progressive_carries_per_match: Optional[float] = None  # UNAVAILABLE until movement tracking
    
    # Defensive pressure
    ppda: Optional[float] = None  # UNAVAILABLE until defensive action tracking
    high_turnovers_per_match: Optional[float] = None  # UNAVAILABLE until zone tracking
    
    # Set pieces
    set_piece_xg_per_match: Optional[float] = None  # UNAVAILABLE until xG event separation
    
    # Home/away separation (scalar values, not nested)
    home_xg_for_per_match: Optional[float] = None  # Separate home-only calculation
    away_xg_for_per_match: Optional[float] = None  # Separate away-only calculation
    
    # Provenance & data quality
    provider: Optional[str] = None
    provider_timestamp: Optional[datetime] = None
    sample_size: int = 0
    matches_with_xg: int = 0
    matches_with_shots: int = 0
    matches_with_possession: int = 0
    data_quality_score: float = 0.0  # 0.0-1.0 based on data completeness
    window_type: str = "recent"  # "recent", "medium", "season"

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
        """Initialize calculator with configurable windows."""
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
        """Calculate advanced metrics from historical match statistics.
        
        CRITICAL: This method requires MatchWithStatistics objects, NOT raw Match objects.
        Caller must fetch TeamMatchStatistic for each match from repository.
        
        Args:
            team_id: Team database ID
            matches_with_stats: List of MatchWithStatistics (Match + home/away stats)
            window_type: "recent", "medium", or "season"
            before_datetime: Only use matches before this timestamp (temporal validity)
            
        Returns:
            AdvancedTeamMetrics with calculated values or None where unavailable
            
        Algorithm:
            1. Filter to finished matches only (match.status == FINISHED)
            2. Filter to matches before_datetime if specified
            3. Apply window size based on window_type
            4. For each match, extract team_statistics for team_id
            5. For each available metric in TeamMatchStatistic:
               - If field is None → skip (unavailable)
               - If field has value → accumulate
            6. Calculate per-match averages
            7. For UNAVAILABLE metrics (PPDA, Field Tilt, etc.) → return None
            8. Calculate data_quality_score based on completeness
            9. Return AdvancedTeamMetrics with provenance
            
        Missing Data Handling:
            - If TeamMatchStatistic is None for a match → skip that match
            - If individual field (e.g., xg) is None → exclude from that metric's calculation
            - If ALL matches lack a field → metric remains None (not zero)
            - Sample size tracks total matches, matches_with_xg tracks xG availability
        """
```

**Data Integrity**:
- Every metric checked for availability before calculation
- `xg_for_per_match` = None if no matches have xG data
- `shots_per_match` = None if no matches have shot data
- `ppda` = None if no matches have defensive action data
- Provenance tracked: provider, timestamp, sample_size
- Data quality score calculated based on data completeness

**Integration Point**: Extends `backend/app/features/team_strength.py`:
- `team_strength.py` already calculates basic goals/match metrics
- New module adds advanced metrics when available
- Both modules populate `MatchFeatureSnapshot.home_strength` and `MatchFeatureSnapshot.away_strength` with richer `TeamStrengthMetrics`

#### 3.2.2 `backend/app/features/opponent_adjustment.py`

**Purpose**: Normalize team statistics for opponent quality to produce opponent-adjusted metrics.

**CRITICAL: Opponent Strength Reconstruction & Temporal Validity**

The opponent adjustment methodology requires historical opponent strength ratings at the CORRECT TIMESTAMP to prevent temporal leakage.

**Opponent Strength Source**: This design uses the existing Elo rating system (`backend/app/prediction/elo.py`) as the opponent strength metric. Elo is already implemented and provides:
- Historical rating reconstruction
- Temporal validity (rating at match time)
- Home/away adjustment
- Rating updates after each match

**Temporal Validity Contract**:

```python
@dataclass
class OpponentStrengthAtTime:
    """Opponent strength rating at a specific historical timestamp.
    
    Represents opponent's strength AS IT WAS at prediction_timestamp,
    not their current/future strength.
    """
    opponent_id: str
    rating: float  # Elo rating at prediction_timestamp
    rating_timestamp: datetime  # When this rating was valid
    home_away_context: str  # "home" or "away"
    confidence: float  # Rating confidence (sample size based)
    
    def __post_init__(self):
        """Validate temporal consistency."""
        assert self.rating_timestamp <= datetime.utcnow(), \
            "Cannot use future opponent rating"
```

**Data Flow for Historical Matches**:

```
1. Historical Match M at time T
2. Prediction cutoff = T (for backtesting) or T - buffer (for pre-match prediction)
3. Retrieve opponent Elo rating from history UP TO cutoff timestamp
4. Use opponent rating AS IT WAS at cutoff (not current rating)
5. Calculate opponent-adjusted metric
6. Temporal leakage prevented by timestamp enforcement
```

**Public Interface**:

```python
@dataclass
class OpponentAdjustedMetrics:
    """Opponent-adjusted team metrics.
    
    All adjustments relative to league average opponent quality.
    """
    team_id: str
    
    # Opponent-adjusted attacking
    adj_xg_for: Optional[float] = None
    adj_shots: Optional[float] = None
    adj_box_entries: Optional[float] = None  # UNAVAILABLE until tracking
    adj_chance_creation: Optional[float] = None
    
    # Opponent-adjusted defending
    adj_xg_against: Optional[float] = None
    adj_shots_suppression: Optional[float] = None
    adj_defensive_strength: Optional[float] = None
    
    # Overall adjusted strength
    adj_overall_strength: Optional[float] = None
    
    # Context
    home_away_context: str  # "home", "away", "all"
    competition_id: Optional[str] = None
    adjustment_method: str = "elo_based"  # "elo_based", "xGA_based", "unavailable"
    
    # Provenance
    sample_size: int = 0
    data_quality_score: float = 0.0
    opponent_strength_source: str = "elo"  # Documents strength metric used

class OpponentAdjustmentCalculator:
    """Calculate opponent-adjusted team metrics."""
    
    def __init__(self, session, elo_system: EloRatingSystem, min_matches: int = 5):
        """Initialize calculator with Elo system reference.
        
        Args:
            session: Database session
            elo_system: Existing EloRatingSystem instance for historical ratings
            min_matches: Minimum matches for reliable adjustment
        """
        self.session = session
        self.elo_system = elo_system
        self.min_matches = min_matches
    
    def calculate_adjusted_metrics(
        self,
        team_id: str,
        matches_with_stats: List[MatchWithStatistics],
        before_datetime: Optional[datetime] = None
    ) -> OpponentAdjustedMetrics:
        """Calculate opponent-adjusted metrics with temporal validity.
        
        CRITICAL TEMPORAL VALIDITY:
        - For each historical match, retrieve opponent's Elo rating AT THAT MATCH TIME
        - Never use opponent's current/future rating
        - If before_datetime specified, only use matches before that cutoff
        
        Algorithm:
        1. For each match in matches_with_stats:
           a. Get opponent_id (home or away depending on team_id role)
           b. Get opponent Elo rating AT match.scheduled_at (historical reconstruction)
           c. Calculate league_average Elo for normalization
           d. Adjust team's performance metric by opponent strength:
              adjusted_xg = raw_xg * (league_avg_elo / opponent_elo)
           e. Accumulate adjusted metrics
        2. Calculate per-match averages of adjusted metrics
        3. Return OpponentAdjustedMetrics with provenance
        
        Args:
            team_id: Team database ID
            matches_with_stats: List of MatchWithStatistics (Match + home/away stats)
            before_datetime: Temporal cutoff (only use matches before this timestamp)
            
        Returns:
            OpponentAdjustedMetrics or all None if insufficient data
            
        Temporal Leakage Prevention:
            - self.elo_system.get_rating_at_time(opponent_id, match.scheduled_at)
            - NEVER use self.elo_system.get_current_rating(opponent_id)
            - If historical rating cannot be reconstructed → exclude that match
            - If before_datetime specified → filter matches before cutoff
            
        Missing Opponent Data Handling:
            - If opponent Elo unavailable for a match → skip that match
            - If ALL matches lack opponent ratings → return None for adjusted metrics
            - Never assume opponent = league average without evidence
        """
    
    def _get_league_average_elo(
        self, 
        competition_id: str, 
        season_id: str,
        at_timestamp: datetime
    ) -> Optional[float]:
        """Get league average Elo at specific timestamp.
        
        Args:
            competition_id: Competition identifier
            season_id: Season identifier
            at_timestamp: Calculate average AT this timestamp
            
        Returns:
            League average Elo or None if insufficient data
        """
```

**Integration with Existing Elo System**:

The design reuses `backend/app/prediction/elo.py` EloRatingSystem:
- `EloRatingSystem` already maintains rating history
- Ratings updated after each match
- Historical ratings reconstructable by replaying matches up to timestamp
- No new rating system needed

**Avoiding Double-Counting with Elo**:

Since Elo already adjusts for opponent quality:
- Opponent-adjusted features provide COMPLEMENTARY information
- Elo captures overall strength differential
- Opponent-adjusted xG/shots capture performance-level adjustments
- Features are independent when both used in models
- GROUP 6 backtesting will validate whether opponent-adjusted features provide incremental value beyond Elo

**Risk Mitigation**: If backtesting shows opponent-adjusted features are redundant with Elo, they can be excluded from production without breaking the pipeline.    adj_overall_strength: Optional[float] = None
    
    # Context
    home_away_context: str  # "home", "away", "all"
    competition_id: Optional[str] = None
    adjustment_method: str = "league_relative"
    
    # Provenance
    sample_size: int = 0
    data_quality_score: float = 0.0

class OpponentAdjustmentCalculator:
    """Calculate opponent-adjusted team metrics."""
    
    def __init__(self, session, min_matches: int = 5):
        """Initialize calculator."""
    
    def calculate_adjusted_metrics(
        self,
        team_id: str,
        matches: List[Match],
        league_context: Optional[LeagueContext] = None,
        before_datetime: Optional[datetime] = None
    ) -> OpponentAdjustedMetrics:
        """Calculate opponent-adjusted metrics.
        
        Algorithm:
        1. For each match, calculate opponent's season-long defensive strength
        2. Adjust team's attacking output by opponent's defensive strength
        3. Aggregate adjusted values across all matches
        4. Normalize to league average = 1.0
        
        Args:
            team_id: Team database ID
            matches: List of finished matches
            league_context: League average metrics for normalization
            before_datetime: Only use matches before this timestamp
            
        Returns:
            OpponentAdjustedMetrics or all None if insufficient data
        """
```

**Data Integrity**:
- Requires opponent historical data for adjustment
- If opponent data unavailable, returns None for that metric (no assumption opponent = league average)
- Never double-count with existing Elo (which already adjusts for opponent quality)
- Adjustment method documented in `adjustment_method` field

**Integration Point**: Extends `MatchFeatureSnapshot`:
- Adds `home_strength_adjusted: Optional[OpponentAdjustedMetrics]`
- Adds `away_strength_adjusted: Optional[OpponentAdjustedMetrics]`
- ModelOrchestrator can choose to use raw or adjusted metrics based on model requirements

**Risk Mitigation**: Validate that opponent-adjusted features provide independent predictive value vs Elo before production use (deferred to GROUP 6 backtesting).

#### 3.2.3 `backend/app/features/temporal_intelligence.py`

**Purpose**: Implement recency weighting, exponential decay, regime-change detection for temporal intelligence.

#### 3.2.3 `backend/app/features/temporal_intelligence.py`

**Purpose**: Implement recency weighting, exponential decay, regime-change detection for temporal intelligence.

**CRITICAL: Manager/Coach Change Data Availability**

The current repository **DOES NOT** have:
- Manager/coach tracking in Team model (`backend/app/domain/entities.py`)
- Manager change events table
- Coach assignment history database

**Regime Change Detection Strategy**:

1. **Statistical Detection** (AVAILABLE NOW):
   - Performance-based shift detection from match results
   - Detects significant changes in form/results without knowing cause
   - Lower confidence than explicit manager events
   - `RegimeChange.detected_by = "statistical"`

2. **External Data Integration** (FUTURE):
   - If a provider supplies manager change events, can be integrated
   - Would increase confidence in regime detection
   - `RegimeChange.detected_by = "external_data"`
   - Until then, this remains **UNAVAILABLE**

3. **Manual Annotation** (OPTIONAL):
   - Expert-provided regime change events
   - `RegimeChange.detected_by = "manual"`

**Public Interface**:

```python
@dataclass
class TemporalWeighting:
    """Temporal weighting configuration."""
    method: str  # "linear", "exponential", "custom"
    decay_factor: Optional[float] = None  # For exponential decay (e.g., 0.95)
    halflife_matches: Optional[int] = None  # Alternative parameterization

@dataclass
class RegimeChange:
    """Detected regime change event.
    
    Represents a significant shift in team performance/context.
    May be statistical detection OR external event data.
    """
    event_type: str  # "statistical_shift", "manager_change", "tactical_shift", 
                     # "key_player_loss", "key_player_return"
    event_date: datetime
    detected_by: str  # "statistical", "external_data", "manual"
    confidence: float  # 0.0-1.0 (statistical detection has lower confidence)
    description: Optional[str] = None  # Human-readable description
    
    def is_verified_external(self) -> bool:
        """Check if this is a verified external event (not statistical inference)."""
        return self.detected_by in ["external_data", "manual"]

@dataclass
class TemporalIntelligenceMetrics:
    """Temporal intelligence for a team."""
    team_id: str
    
    # Recency-weighted form
    recent_form_weighted: Optional[float] = None  # Weighted points per match
    recent_xg_weighted: Optional[float] = None
    
    # Trend detection
    form_trend: Optional[str] = None  # "improving", "declining", "stable"
    form_acceleration: Optional[float] = None  # Rate of change
    
    # Regime changes
    recent_regime_changes: List[RegimeChange] = field(default_factory=list)
    post_regime_form: Optional[float] = None  # Form after most recent regime change
    
    # Temporal snapshots (for walk-forward validation)
    snapshot_timestamp: Optional[datetime] = None
    
    # Provenance
    weighting_config: Optional[TemporalWeighting] = None
    sample_size: int = 0

class TemporalIntelligenceCalculator:
    """Calculate temporally-weighted metrics and detect regime changes."""
    
    def __init__(
        self,
        session,
        weighting: TemporalWeighting = TemporalWeighting(method="exponential", decay_factor=0.95),
        min_matches: int = 5,
        regime_detection_enabled: bool = True
    ):
        """Initialize calculator with weighting configuration.
        
        Args:
            session: Database session
            weighting: Temporal weighting configuration
            min_matches: Minimum matches for reliable metrics
            regime_detection_enabled: Whether to detect statistical regime changes
        """
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
        """Calculate temporally-weighted metrics.
        
        Args:
            team_id: Team database ID
            matches_with_stats: List of MatchWithStatistics (chronologically ordered)
            before_datetime: Only use matches before this timestamp (temporal validity)
            known_regime_changes: Optional list of externally-verified regime changes
            
        Returns:
            TemporalIntelligenceMetrics with weighted values
            
        Algorithm:
            1. Filter matches before_datetime if specified
            2. Apply temporal weighting (exponential decay from most recent)
            3. Calculate weighted form metrics
            4. Detect statistical regime changes if enabled
            5. Combine with known_regime_changes if provided
            6. Return metrics with provenance
        """
    
    def detect_regime_changes(
        self,
        team_id: str,
        matches_with_stats: List[MatchWithStatistics],
        min_matches_before: int = 5,
        min_matches_after: int = 3,
        significance_threshold: float = 0.05
    ) -> List[RegimeChange]:
        """Detect potential regime changes from performance shifts.
        
        STATISTICAL DETECTION ONLY - does not know actual manager changes.
        
        Algorithm:
            1. Sliding window over match history
            2. For each potential changepoint:
               a. Split matches into before/after
               b. Calculate performance metrics (points/match, xG, etc.)
               c. Test for significant difference (t-test or equivalent)
            3. If significant shift detected:
               a. Create RegimeChange with detected_by="statistical"
               b. Confidence based on significance level and sample sizes
               c. event_type = "statistical_shift" (cannot determine cause)
            4. Return list of detected changes
        
        Returns:
            List of statistically-detected RegimeChange events
            
        Notes:
            - These are INFERRED changes, not ground truth
            - Lower confidence than external manager-change data
            - Should be validated in backtesting before production use
            - Cannot distinguish manager change from other causes
        """
```

**Integration with External Manager Data (Future)**:

If a provider supplies manager change events, define expected interface:

```python
@dataclass
class ManagerChangeEvent:
    """External manager change event from provider."""
    team_id: str
    event_date: datetime
    old_manager: Optional[str]
    new_manager: str
    source: str  # Provider name
    
    def to_regime_change(self) -> RegimeChange:
        """Convert to RegimeChange with high confidence."""
        return RegimeChange(
            event_type="manager_change",
            event_date=self.event_date,
            detected_by="external_data",
            confidence=0.95,  # High confidence for verified events
            description=f"Manager change: {self.old_manager} → {self.new_manager}"
        )
```

Until manager data exists, statistical detection is the only available method.
    ) -> TemporalIntelligenceMetrics:
        """Calculate temporally-weighted metrics.
        
        Args:
            team_id: Team database ID
            matches: List of finished matches (chronologically ordered)
            before_datetime: Only use matches before this timestamp
            known_regime_changes: Optional list of known regime changes
            
        Returns:
            TemporalIntelligenceMetrics with weighted values
        """
    
    def detect_regime_changes(
        self,
        team_id: str,
        matches: List[Match]
    ) -> List[RegimeChange]:
        """Detect potential regime changes from performance shifts.
        
        Statistical detection of significant performance shifts.
        
        Returns:
            List of detected RegimeChange events
        """
```

**Data Integrity**:
- Temporal weighting parameters configurable, prepared for walk-forward optimization (GROUP 6)
- Regime-change detection marks confidence level; low-confidence changes do not automatically influence predictions
- All temporal features respect `before_datetime` for temporal validity

**Integration Point**: Extends `MatchFeatureSnapshot`:
- Adds `home_temporal_intel: Optional[TemporalIntelligenceMetrics]`
- Adds `away_temporal_intel: Optional[TemporalIntelligenceMetrics]`
- `FormCalculator` in `features/form.py` can call temporal intelligence for recency-weighted form

### 3.3 Integration with Existing System

**Extension of `backend/app/features/team_strength.py`**:

```python
# EXISTING: team_strength.py calculates basic metrics
class TeamStrengthCalculator(FeatureCalculator):
    def calculate(self, context: MatchContext) -> Dict[str, Optional[float]]:
        # ... existing basic calculations ...
        
        # NEW: If advanced intelligence available, enrich features
        if self.use_advanced_intelligence:
            advanced_calc = AdvancedTeamIntelligenceCalculator(self.session)
            home_advanced = advanced_calc.calculate_advanced_metrics(
                team_id=context.home_team_id,
                matches=context.home_team_history.matches,
                window_type="recent"
            )
            # Add advanced metrics to feature dict
            if home_advanced.xg_for_per_match is not None:
                features["home_xg_for_advanced"] = home_advanced.xg_for_per_match
            # ... etc ...
```

**Extension of `backend/app/prediction/feature_snapshot.py`**:

```python
# EXTEND MatchFeatureSnapshot dataclass
@dataclass
class MatchFeatureSnapshot:
    # ... existing fields ...
    
    # NEW: Advanced team intelligence
    home_advanced_intel: Optional[AdvancedTeamMetrics] = None
    away_advanced_intel: Optional[AdvancedTeamMetrics] = None
    
    # NEW: Opponent-adjusted metrics
    home_strength_adjusted: Optional[OpponentAdjustedMetrics] = None
    away_strength_adjusted: Optional[OpponentAdjustedMetrics] = None
    
    # NEW: Temporal intelligence
    home_temporal_intel: Optional[TemporalIntelligenceMetrics] = None
    away_temporal_intel: Optional[TemporalIntelligenceMetrics] = None
    
    def get_feature_dict(self) -> Dict[str, Optional[float]]:
        """Extract flat feature dictionary for model compatibility."""
        features = {}
        
        # ... existing feature extraction ...
        
        # NEW: Advanced intelligence features
        if self.home_advanced_intel:
            if self.home_advanced_intel.xg_for_per_match is not None:
                features["home_xg_for_advanced"] = self.home_advanced_intel.xg_for_per_match
            if self.home_advanced_intel.shots_per_match is not None:
                features["home_shots_advanced"] = self.home_advanced_intel.shots_per_match
            # ... etc for all available advanced metrics ...
        
        return features
```

**Flow Through Canonical Pipeline**:

```
1. FeatureAggregator calls AdvancedTeamIntelligenceCalculator
2. FeatureAggregator calls OpponentAdjustmentCalculator
3. FeatureAggregator calls TemporalIntelligenceCalculator
4. All advanced metrics added to MatchFeatureSnapshot
5. MatchFeatureSnapshot.get_feature_dict() includes advanced features
6. ModelOrchestrator feeds enriched feature dict to all 7 models
7. Models use available features (models gracefully handle None values)
8. Ensemble → Calibration → Confidence → MarketDerivation → SmartMarketSelector
```

**No Parallel Prediction Engine**: Advanced features simply enrich the existing feature dict; no new prediction models are created in GROUP 1.

### 3.4 Data Integrity Handling

#### Availability Representation

```python
# CORRECT: Explicit None when unavailable
if len(matches_with_xg) == 0:
    xg_for_per_match = None  # ✓ Explicit unavailability
else:
    xg_for_per_match = total_xg / len(matches_with_xg)

# WRONG: Silent fallback
xg_for_per_match = 0.0  # ✗ Could be misinterpreted as real zero xG
```

#### Provenance Tracking

Every `AdvancedTeamMetrics`, `OpponentAdjustedMetrics`, and `TemporalIntelligenceMetrics` includes:
- `provider: Optional[str]` — data source (e.g., "FotMob", "Ryzellx")
- `provider_timestamp: Optional[datetime]` — when data was fetched
- `sample_size: int` — number of matches analyzed
- `matches_with_xg: int` — how many matches had xG data
- `data_quality_score: float` — 0.0-1.0 based on data completeness

#### Temporal Validity

All calculators accept `before_datetime: Optional[datetime]` parameter:
- Only matches with `scheduled_at < before_datetime` are used
- Feature snapshots can be reconstructed at any historical timestamp
- Prevents future leakage in backtesting (GROUP 6)

### 3.5 Testing Requirements

**Unit Tests** (per module):
- `tests/features/test_advanced_team_intelligence.py`
  - Test metric calculation with full data
  - Test metric calculation with partial data (some matches missing xG)
  - Test metric calculation with no data (all None)
  - Test data_quality_score calculation
  - Test temporal validity (before_datetime filtering)
  
- `tests/features/test_opponent_adjustment.py`
  - Test opponent-adjusted calculation
  - Test normalization to league average
  - Test handling of missing opponent data
  - Test home/away context separation
  
- `tests/features/test_temporal_intelligence.py`
  - Test exponential decay weighting
  - Test regime-change detection
  - Test temporal snapshots

**Integration Tests**:
- `tests/integration/test_advanced_features_integration.py`
  - Test advanced features populate MatchFeatureSnapshot
  - Test feature_dict includes advanced features
  - Test ModelOrchestrator receives enriched features
  - Test models handle None values in advanced features

**Regression Tests**:
- Existing baseline tests must pass with advanced features disabled
- Advanced features do not break existing prediction pipeline

---

## 4. GROUP 2: SHOT & LINEUP INTELLIGENCE (10D, 10E, 10F, 10F-1)

### 4.1 Objectives

Build shot-volume, shot-quality, and lineup-impact intelligence layers that:
- Produce shot market probabilities (Team Shots, Team Shots on Target)
- Estimate expected shot volume adjusted for opponent and context
- Calculate lineup impact when player absence data available
- Feed shot features to existing 7 models and extend MarketDerivation for shot markets

### 4.2 New Modules

#### 4.2.1 `backend/app/features/shot_intelligence.py`

**Purpose**: Calculate shot volume, shot quality, and expected shot production.

**Public Interface**:

```python
@dataclass
class ShotIntelligenceMetrics:
    """Shot intelligence metrics for a team."""
    team_id: str
    
    # Shot volume
    shots_total_per_match: Optional[float] = None
    shots_on_target_per_match: Optional[float] = None
    shots_home_per_match: Optional[float] = None
    shots_away_per_match: Optional[float] = None
    
    # Shot quality
    xg_per_shot: Optional[float] = None
    box_shot_percentage: Optional[float] = None
    shot_conversion_rate: Optional[float] = None
    
    # Expected shot volume (opponent-adjusted)
    expected_shots_vs_avg_opponent: Optional[float] = None
    expected_shots_on_target_vs_avg_opponent: Optional[float] = None
    
    # Shot suppression (defensive)
    shots_against_per_match: Optional[float] = None
    shots_on_target_against_per_match: Optional[float] = None
    shot_suppression_vs_avg_opponent: Optional[float] = None
    
    # Shot dominance
    shot_share: Optional[float] = None  # Team shots / (team + opponent shots)
    
    # Provenance
    provider: Optional[str] = None
    sample_size: int = 0
    matches_with_shot_data: int = 0
    data_quality_score: float = 0.0

class ShotIntelligenceCalculator:
    """Calculate shot intelligence metrics."""
    
    def __init__(self, session, min_matches: int = 5):
        """Initialize calculator."""
    
    def calculate_shot_metrics(
        self,
        team_id: str,
        matches: List[Match],
        opponent_adjustment: bool = True,
        before_datetime: Optional[datetime] = None
    ) -> ShotIntelligenceMetrics:
        """Calculate shot intelligence metrics.
        
        Args:
            team_id: Team database ID
            matches: List of finished matches
            opponent_adjustment: Whether to calculate opponent-adjusted expected shots
            before_datetime: Only use matches before this timestamp
            
        Returns:
            ShotIntelligenceMetrics with calculated values or None where unavailable
        """
```

**Data Integrity**:
- Shot data availability varies by provider
- `shots_total_per_match` = None if no matches have shot data
- `xg_per_shot` = None if no matches have both shot and xG data
- Never fabricate shot counts or shot locations

**Integration Point**: Extends `MatchFeatureSnapshot`:
- Adds `home_shot_intel: Optional[ShotIntelligenceMetrics]`
- Adds `away_shot_intel: Optional[ShotIntelligenceMetrics]`

#### 4.2.2 `backend/app/features/shot_production.py`

**Purpose**: Derive shot market probabilities (Team Shots, Team Shots on Target) with threshold logic.

**Public Interface**:

```python
@dataclass
class ShotMarketProbabilities:
    """Shot market probabilities for a team."""
    team_id: str
    
    # Shot volume distribution
    expected_shots_mean: Optional[float] = None
    expected_shots_variance: Optional[float] = None
    
    # Shot threshold probabilities
    over_10_shots_prob: Optional[float] = None
    over_12_shots_prob: Optional[float] = None
    over_15_shots_prob: Optional[float] = None
    over_18_shots_prob: Optional[float] = None
    over_20_shots_prob: Optional[float] = None
    
    # Shots on target thresholds
    over_3_sot_prob: Optional[float] = None
    over_4_sot_prob: Optional[float] = None
    over_5_sot_prob: Optional[float] = None
    over_6_sot_prob: Optional[float] = None
    
    # Distribution modeling
    distribution_model: str = "poisson"  # "poisson", "negative_binomial", "empirical"
    
    # Calibration metadata
    historical_calibration_available: bool = False
    brier_score_historical: Optional[float] = None
    
    # Provenance
    sample_size: int = 0
    data_quality_score: float = 0.0

#### Shot Distribution Methodology (EXPLICIT MATHEMATICAL SPECIFICATION)

**Critical Requirement**: Shot market probabilities (Team Shots 10+, 15+, 20+, etc.) must be calculated using explicit statistical distributions, NOT hardcoded.

**Step 1: Calculate Historical Shot Statistics**

For a team over a historical window:

```
μ (mean) = Σ(shots_per_match) / n_matches
σ² (variance) = Σ((shots_per_match - μ)²) / (n_matches - 1)
```

**Step 2: Distribution Selection**

```python
if variance > mean:
    # Overdispersed → use Negative Binomial
    distribution = "negative_binomial"
else:
    # Equidispersed or underdispersed → use Poisson
    distribution = "poisson"
```

**Step 3: Distribution Parameterization**

**For Negative Binomial** (when variance > mean):

```
r = μ² / (σ² - μ)
p = μ / σ²

# Validate parameters
if r <= 0 or p <= 0 or p >= 1:
    # Invalid parameters → insufficient data
    return None
```

**For Poisson** (when variance ≤ mean):

```
λ = μ

# Validate parameter
if λ <= 0:
    # Invalid parameter → insufficient data
    return None
```

**Step 4: Threshold Probability Calculation**

For a threshold T (e.g., 15 shots):

**Negative Binomial**:
```
P(X > T) = 1 - CDF_NB(T; r, p)
         = 1 - Σ(k=0 to T) [ (k+r-1 choose k) * p^r * (1-p)^k ]
```

**Poisson**:
```
P(X > T) = 1 - CDF_Poisson(T; λ)
         = 1 - Σ(k=0 to T) [ (λ^k * e^(-λ)) / k! ]
```

**Standard Thresholds**:
- Team Shots: 10+, 12+, 15+, 18+, 20+
- Team Shots on Target: 3+, 4+, 5+, 6+

**Step 5: Opponent Adjustment**

Expected shot mean can be adjusted for opponent:

```
μ_adjusted = μ_team + (opponent_suppression_effect)

Where:
opponent_suppression_effect = (opponent_shots_allowed - league_avg_shots_allowed)
```

Variance adjustment:
```
σ²_adjusted = σ²_team * adjustment_factor

Where:
adjustment_factor considers opponent variance contribution
```

**Step 6: Minimum Sample Size**

```python
MIN_MATCHES_FOR_SHOT_DISTRIBUTION = 5
MIN_MATCHES_WITH_SHOT_DATA = 3

if matches_with_shot_data < MIN_MATCHES_WITH_SHOT_DATA:
    # Insufficient sample → all threshold probabilities = None
    return ShotMarketProbabilities(
        team_id=team_id,
        expected_shots_mean=None,
        # All threshold probs = None
    )
```

**Step 7: Edge Cases**

```python
# Case 1: Mean = 0
if μ <= 0:
    return None  # Cannot fit distribution

# Case 2: Variance = 0
if σ² <= 0:
    return None  # All matches identical (highly unlikely)

# Case 3: Variance = Mean (exactly)
if abs(σ² - μ) < 0.01:
    distribution = "poisson"  # Treat as Poisson

# Case 4: Variance < Mean (underdispersed)
if σ² < μ:
    distribution = "poisson"  # Poisson more appropriate
```

**Step 8: Calibration Path**

Shot threshold probabilities flow through existing calibration:

```
Raw P(shots > T) from distribution
→ CalibrationEngine (if historical shot-market calibration data exists)
→ Calibrated P(shots > T)
→ SmartMarketSelector evaluation
→ MENSIONE PICK or PASS
```

**Step 9: Uncertainty Propagation**

```python
uncertainty_score = calculate_uncertainty(
    sample_size=n_matches,
    data_quality=shots_data_completeness,
    distribution_fit_quality=goodness_of_fit,
    opponent_adjustment_confidence=adj_confidence
)

# High uncertainty → lower confidence in SmartMarketSelector
# Very high uncertainty → PASS
```

**Integration with Existing Pipeline**:

Shot market probabilities are treated as additional markets in MarketProbabilities, flowing through:
- ModelOrchestrator (shot features feed models)
- Ensemble (if multiple models produce shot expectations)
- Calibration (shot threshold calibration)
- Confidence (shot market uncertainty)
- SmartMarketSelector (evaluate shot thresholds)
- MENSIONE PICK or PASS

**NO parallel shot prediction engine** — shot intelligence feeds existing pipeline.

class ShotProductionCalculator:
    """Calculate shot market probabilities."""
    
    def __init__(self, session, distribution_model: str = "negative_binomial"):
        """Initialize calculator with distribution model choice."""
    
    def calculate_shot_market_probs(
        self,
        shot_intel: ShotIntelligenceMetrics,
        opponent_shot_intel: Optional[ShotIntelligenceMetrics] = None
    ) -> ShotMarketProbabilities:
        """Calculate shot market probabilities.
        
        Algorithm:
        1. Estimate expected shot volume from historical average + opponent adjustment
        2. Fit distribution model (Poisson or Negative Binomial)
        3. Calculate P(shots > threshold) for each threshold
        4. Return calibration-ready probabilities
        
        Args:
            shot_intel: Team's shot intelligence metrics
            opponent_shot_intel: Opponent's shot suppression metrics
            
        Returns:
            ShotMarketProbabilities or all None if insufficient data
        """
```

**Data Integrity**:
- Shot market probabilities calculated only when shot data available
- If `expected_shots_mean` is None, all threshold probabilities are None
- Distribution model choice documented in `distribution_model` field

**Integration Point**: Extends `backend/app/prediction/market_derivation.py`:
- `MarketDerivationEngine` currently derives 1X2, O/U, BTTS, Correct Score, Handicap
- Extend to derive shot markets when shot intelligence available

```python
@dataclass
class MarketProbabilities:
    # ... existing markets ...
    
    # NEW: Shot markets
    home_shot_markets: Optional[ShotMarketProbabilities] = None
    away_shot_markets: Optional[ShotMarketProbabilities] = None
```

#### 4.2.3 `backend/app/features/lineup_intelligence.py`

**Purpose**: Estimate lineup impact when player absence data available.

**Public Interface**:

```python
@dataclass
class LineupImpactEstimate:
    """Estimated impact of lineup changes."""
    team_id: str
    
    # Lineup status
    lineup_confirmed: bool = False
    lineup_expected: bool = False
    lineup_unavailable: bool = True
    
    # Key player absences
    key_players_missing: List[str] = field(default_factory=list)
    injuries: List[Dict[str, Any]] = field(default_factory=list)
    suspensions: List[Dict[str, Any]] = field(default_factory=list)
    
    # Estimated impact (None if cannot estimate)
    estimated_attack_impact: Optional[float] = None  # -1.0 to +1.0, negative = weakened
    estimated_defense_impact: Optional[float] = None
    estimated_overall_impact: Optional[float] = None
    
    # Confidence in estimate
    impact_confidence: float = 0.0  # 0.0-1.0
    
    # Provenance
    impact_method: str = "unavailable"  # "unavailable", "statistical_replacement", "manual_expert"
    provider: Optional[str] = None

class LineupIntelligenceCalculator:
    """Calculate lineup impact estimates using statistical methodology."""
    
    def __init__(self, session, min_with_player: int = 3, min_without_player: int = 3):
        """Initialize calculator.
        
        Args:
            session: Database session
            min_with_player: Minimum matches WITH player for reliable estimate
            min_without_player: Minimum matches WITHOUT player for reliable estimate
        """
        self.session = session
        self.min_with_player = min_with_player
        self.min_without_player = min_without_player
    
    def calculate_lineup_impact(
        self,
        team_id: str,
        player_availability: PlayerAvailability,
        historical_matches_with_stats: List[MatchWithStatistics]
    ) -> LineupImpactEstimate:
        """Calculate lineup impact estimate using statistical replacement methodology.
        
        CRITICAL: NEVER fabricate impact if unavailable.
        
        **Statistical Methodology**:
        
        For each absent key player:
        1. Split historical matches into:
           - WITH player: matches where player appeared (from lineup data)
           - WITHOUT player: matches where player was absent
        
        2. Calculate performance differential:
           ```
           impact = (performance_with_player - performance_without_player)
           
           Where performance can be:
           - Goals scored per match
           - xG per match  
           - Points per match
           - xG against per match (defensive impact)
           ```
        
        3. Validate sample sizes:
           ```python
           if n_with < min_with_player or n_without < min_without_player:
               return None  # Insufficient sample
           ```
        
        4. Calculate confidence:
           ```
           confidence = min(1.0, 
                           (n_with / 10) * (n_without / 10) * 
                           (1 - abs(n_with - n_without) / (n_with + n_without)))
           
           # Confidence is lower when:
           # - Small sample sizes
           # - Imbalanced samples (many with, few without)
           ```
        
        5. Aggregate multiple player absences:
           ```
           total_attack_impact = sum(player_impacts for attacking players)
           total_defense_impact = sum(player_impacts for defensive players)
           ```
        
        6. Context normalization:
           - Adjust for opponent strength (using Elo)
           - Adjust for home/away context
           - Adjust for match importance
        
        7. Replacement player quality (if lineup data available):
           ```
           net_impact = absent_player_impact - replacement_player_impact
           ```
           If replacement unknown: use absent_player_impact only
        
        **NO Arbitrary Percentages**:
        - ✗ "Star player out = -15% attack"
        - ✓ Calculate from historical with/without samples
        
        Args:
            team_id: Team database ID
            player_availability: Player availability with absence reasons
            historical_matches_with_stats: Historical matches WITH lineup data
            
        Returns:
            LineupImpactEstimate with statistically-derived impact or None
            
        Missing Data Handling:
            - If no historical lineup data → all impacts = None
            - If insufficient with/without samples → all impacts = None
            - If player has never been absent → impact = None (cannot estimate)
            - If replacement player unknown → use absent player impact only
            - Never use hardcoded penalty values
        """
    
    def _get_player_match_splits(
        self,
        team_id: str,
        player_id: str,
        matches_with_stats: List[MatchWithStatistics]
    ) -> Tuple[List[MatchWithStatistics], List[MatchWithStatistics]]:
        """Split matches into WITH and WITHOUT player.
        
        Requires lineup data in historical matches.
        
        Returns:
            (matches_with_player, matches_without_player)
        """

**Integration Point**: Extends `MatchFeatureSnapshot`:

```python
@dataclass  
class MatchFeatureSnapshot:
    # ... existing fields ...
    
    # EXISTING: Player availability
    home_player_availability: Optional[PlayerAvailability] = None
    away_player_availability: Optional[PlayerAvailability] = None
    
    # NEW: Lineup impact (extends existing availability)
    home_lineup_impact: Optional[LineupImpactEstimate] = None
    away_lineup_impact: Optional[LineupImpactEstimate] = None
```

**Integration with ConfidenceEngine**:

Lineup uncertainty already flows to confidence through existing `player_availability` field. Enhancement:

```python
class ConfidenceEngine:
    def assess_with_disagreement(
        self,
        # ... existing params ...
        lineup_status: str = "unknown",  # EXISTING parameter
        lineup_impact_confidence: Optional[float] = None  # NEW: from LineupImpactEstimate
    ) -> ConfidenceAssessment:
        """Assess confidence with lineup uncertainty.
        
        Lineup uncertainty reduces overall confidence:
        - lineup_status = "confirmed" → no penalty
        - lineup_status = "expected" → small penalty  
        - lineup_status = "unknown" → larger penalty
        - If lineup_impact_confidence low → additional penalty
        """
```

**Backward Compatibility**: Existing predictions without lineup impact continue to function (all Optional fields).

### 4.3 Integration with Existing System

**Extension of `backend/app/prediction/market_derivation.py`**:

```python
class MarketDerivationEngine:
    def derive(
        self,
        score_distribution: Dict[Tuple[int, int], float],
        shot_intel: Optional[Tuple[ShotIntelligenceMetrics, ShotIntelligenceMetrics]] = None
    ) -> MarketProbabilities:
        """Derive all markets from score distribution.
        
        NEW: If shot_intel provided, derive shot markets.
        """
        # ... existing market derivation ...
        
        # NEW: Derive shot markets
        if shot_intel:
            home_shot_intel, away_shot_intel = shot_intel
            shot_calc = ShotProductionCalculator(session=None)
            markets.home_shot_markets = shot_calc.calculate_shot_market_probs(
                shot_intel=home_shot_intel,
                opponent_shot_intel=away_shot_intel
            )
            markets.away_shot_markets = shot_calc.calculate_shot_market_probs(
                shot_intel=away_shot_intel,
                opponent_shot_intel=home_shot_intel
            )
        
        return markets
```

**Extension of `backend/app/prediction/market_selector.py`**:

```python
class SmartMarketSelector:
    def evaluate_and_select(
        self,
        market_probs: MarketProbabilities,
        confidence_assessment: ConfidenceAssessment,
        odds_data: Optional[Dict[str, float]] = None,
        pipeline_version: str = "1.0.0"
    ):
        """Evaluate all available markets and select the best tip or issue a PASS.
        
        NEW: Evaluate shot markets if available.
        """
        # ... existing market evaluation (1X2, O/U, BTTS) ...
        
        # NEW: Evaluate shot markets
        if market_probs.home_shot_markets:
            self._evaluate_shot_markets(
                shot_markets=market_probs.home_shot_markets,
                team="home",
                candidates=candidates
            )
        
        if market_probs.away_shot_markets:
            self._evaluate_shot_markets(
                shot_markets=market_probs.away_shot_markets,
                team="away",
                candidates=candidates
            )
        
        # ... existing selection logic ...
```

### 4.4 Data Integrity Handling

#### Shot Data Availability

```python
# CORRECT: Check availability before calculation
if len(matches_with_shot_data) < min_matches:
    return ShotIntelligenceMetrics(
        team_id=team_id,
        shots_total_per_match=None,  # ✓ Explicit unavailability
        # ... all fields None ...
        matches_with_shot_data=len(matches_with_shot_data),
        data_quality_score=0.0
    )
```

#### Lineup Impact Fabrication Prevention

```python
# CORRECT: Only estimate impact when sufficient data exists
if not player_availability.has_key_player_absences:
    return LineupImpactEstimate(
        team_id=team_id,
        lineup_unavailable=True,
        estimated_attack_impact=None,  # ✓ Cannot estimate
        impact_confidence=0.0
    )

# WRONG: Assume default impact
if not player_availability.has_key_player_absences:
    return LineupImpactEstimate(
        team_id=team_id,
        estimated_attack_impact=-0.2,  # ✗ Fabricated assumption
        impact_confidence=0.5
    )
```

### 4.5 Testing Requirements

**Unit Tests**:
- `tests/features/test_shot_intelligence.py`
- `tests/features/test_shot_production.py`
- `tests/features/test_lineup_intelligence.py`

**Integration Tests**:
- `tests/integration/test_shot_markets_integration.py`
  - Test shot markets populate MarketProbabilities
  - Test SmartMarketSelector evaluates shot markets
  - Test PASS decision when shot data unavailable

**Regression Tests**:
- Existing markets (1X2, O/U, BTTS) unaffected by shot markets

---

## 5. GROUP 3: COMMON OPPONENT INTELLIGENCE (10G)

### 5.1 Objectives

Build common-opponent intelligence layer that:
- Identifies shared opponents between two teams
- Compares performance vs common opponents on result, xG, xGA, shots, shot quality when available
- Applies recency weighting and context normalization
- Separates direct H2H from common opponent in outputs

### 5.2 New Modules

#### 5.2.1 `backend/app/features/common_opponent.py`

**Purpose**: Calculate common-opponent comparison metrics.

**Public Interface**:

```python
@dataclass
class CommonOpponentComparison:
    """Comparison of two teams' performance vs common opponents."""
    
    home_team_id: str
    away_team_id: str
    
    # Common opponents identified
    common_opponent_ids: List[str] = field(default_factory=list)
    n_common_opponents: int = 0
    
    # Performance comparison (aggregated across all common opponents)
    home_avg_points_vs_common: Optional[float] = None
    away_avg_points_vs_common: Optional[float] = None
    points_differential: Optional[float] = None  # home - away
    
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
    home_away_normalized: bool = False  # Compared home vs home, away vs away
    
    # Statistical confidence
    comparison_confidence: float = 0.0  # 0.0-1.0 based on sample size + recency
    
    # Provenance
    home_matches_vs_common: int = 0
    away_matches_vs_common: int = 0
    data_quality_score: float = 0.0

class CommonOpponentCalculator:
    """Calculate common-opponent comparison with explicit confidence methodology."""
    
    def __init__(
        self, 
        session, 
        min_common_opponents: int = 3,
        min_matches_per_opponent: int = 1,
        recency_decay: float = 0.95
    ):
        """Initialize calculator.
        
        Args:
            session: Database session
            min_common_opponents: Minimum shared opponents for reliable comparison
            min_matches_per_opponent: Minimum matches against each opponent
            recency_decay: Exponential decay factor for recency weighting
        """
        self.session = session
        self.min_common_opponents = min_common_opponents
        self.min_matches_per_opponent = min_matches_per_opponent
        self.recency_decay = recency_decay
    
    def find_common_opponents(
        self,
        home_team_id: str,
        away_team_id: str,
        home_matches_with_stats: List[MatchWithStatistics],
        away_matches_with_stats: List[MatchWithStatistics],
        before_datetime: Optional[datetime] = None
    ) -> CommonOpponentComparison:
        """Find common opponents and compare performance with explicit confidence.
        
        **Common Opponent Confidence Calculation**:
        
        ```
        confidence = (sample_factor) * (recency_factor) * (context_factor)
        
        Where:
        
        sample_factor = min(1.0, n_common_opponents / 5)
        # More shared opponents → higher confidence
        # 5+ shared opponents = full sample confidence
        
        recency_factor = avg_match_recency_weight
        # Recent matches weighted higher
        # recency_weight = decay^(days_since_match / 30)
        
        context_factor = home_away_match_rate
        # Proportion of comparisons with matching home/away context
        # Perfect context match = 1.0
        # Mixed context = lower factor
        
        Final: confidence = sample_factor * recency_factor * context_factor
        ```
        
        **Statistical Evidence Threshold**:
        
        ```python
        def get_signal(differential: float, confidence: float) -> str:
            '''Determine comparison signal with statistical threshold.'''
            
            # Require BOTH significant differential AND sufficient confidence
            if abs(differential) < 0.3:
                return "neutral"  # Too small to be meaningful
            
            if confidence < 0.5:
                return "neutral"  # Insufficient confidence
            
            # Sufficient evidence exists
            if differential > 0.5 and confidence > 0.7:
                return "home_favored"
            elif differential < -0.5 and confidence > 0.7:
                return "away_favored"
            else:
                return "neutral"  # Evidence exists but not conclusive
        ```
        
        **Risk Classification**: MEDIUM RISK
        - Common opponent features are MEDIUM confidence/risk
        - Not LOW risk despite using historical data
        - Confidence depends on: sample size, recency, context, variance
        
        Algorithm:
        1. Identify opponents faced by BOTH teams
           ```python
           home_opponents = {m.away_team_id if m.match.home_team_id == home_team_id 
                            else m.match.home_team_id 
                            for m in home_matches}
           away_opponents = {m.away_team_id if m.match.home_team_id == away_team_id
                            else m.match.home_team_id
                            for m in away_matches}
           common_opponent_ids = home_opponents & away_opponents
           ```
        
        2. For each common opponent:
           a. Extract home team's performance vs this opponent
           b. Extract away team's performance vs this opponent  
           c. Apply recency weighting
           d. Apply home/away context normalization
        
        3. Aggregate across all common opponents:
           ```
           home_avg_points = weighted_mean(home_points_vs_each_opponent)
           away_avg_points = weighted_mean(away_points_vs_each_opponent)
           differential = home_avg_points - away_avg_points
           ```
        
        4. Calculate confidence using formula above
        
        5. Determine signal with statistical threshold
        
        6. NEVER claim superiority without:
           - Sufficient common opponents (n >= min_common_opponents)
           - Sufficient confidence (confidence >= 0.5)
           - Meaningful differential (|differential| >= 0.3)
        
        Args:
            home_team_id: Home team database ID
            away_team_id: Away team database ID
            home_matches_with_stats: Home team's historical matches WITH stats
            away_matches_with_stats: Away team's historical matches WITH stats
            before_datetime: Only use matches before this timestamp (temporal validity)
            
        Returns:
            CommonOpponentComparison with explicit confidence or None fields
            
        Missing Data Handling:
            - If n_common_opponents < min_common_opponents → all comparisons = None
            - If specific metric unavailable (e.g., xG) → that differential = None
            - Never fabricate common opponent data
            - comparison_confidence explicitly calculated, never assumed
        """
    
    def _calculate_confidence(
        self,
        n_common_opponents: int,
        avg_recency_weight: float,
        context_match_rate: float
    ) -> float:
        """Calculate comparison confidence using explicit formula.
        
        Returns:
            Confidence score 0.0-1.0
        """
        sample_factor = min(1.0, n_common_opponents / 5.0)
        recency_factor = avg_recency_weight
        context_factor = context_match_rate
        
        confidence = sample_factor * recency_factor * context_factor
        return max(0.0, min(1.0, confidence))
```

**Data Integrity**:
- Common-opponent comparison requires sufficient shared opponents (min 3 by default)
- If fewer than min_common_opponents, all comparison fields = None
- Statistical confidence tracked: low sample size → low confidence
- Never claim team A > team B based on insufficient evidence

**Integration Point**: Extends `MatchFeatureSnapshot`:
- Adds `common_opponent_intel: Optional[CommonOpponentComparison]`

#### 5.2.2 `backend/app/analysis/h2h_intelligence.py`

**Purpose**: Separate direct head-to-head (H2H) from common opponent in AnalysisContext.

**Public Interface**:

```python
@dataclass
class H2HIntelligence:
    """Direct head-to-head intelligence."""
    
    home_team_id: str
    away_team_id: str
    
    # Direct H2H record
    h2h_matches: int = 0
    home_wins: int = 0
    draws: int = 0
    away_wins: int = 0
    
    # Recent H2H form
    recent_h2h_form: Optional[str] = None  # e.g., "WWD" from home perspective
    
    # Data quality
    h2h_data_quality: str = "unavailable"  # "unavailable", "limited", "sufficient"
    
@dataclass
class IndirectIntelligence:
    """Indirect intelligence from common opponents."""
    
    common_opponent_comparison: Optional[CommonOpponentComparison] = None
    indirect_strength_signal: Optional[str] = None  # "home_favored", "neutral", "away_favored"
    signal_confidence: float = 0.0

class H2HIntelligenceCalculator:
    """Calculate direct H2H vs indirect common opponent intelligence."""
    
    def calculate_h2h_and_indirect(
        self,
        home_team_id: str,
        away_team_id: str,
        all_matches: List[Match],
        before_datetime: Optional[datetime] = None
    ) -> Tuple[H2HIntelligence, IndirectIntelligence]:
        """Calculate direct H2H and indirect common opponent intelligence.
        
        Returns:
            Tuple of (H2HIntelligence, IndirectIntelligence)
        """
```

**Integration Point**: Extends `backend/app/analysis/analysis_context.py`:
- AnalysisContext already exists for AI Analyst
- Add `h2h_intelligence: Optional[H2HIntelligence]`
- Add `indirect_intelligence: Optional[IndirectIntelligence]`
- AI Analyst can clearly distinguish direct H2H from common opponent in explanations

### 5.3 Integration with Existing System

**Flow**:
1. `CommonOpponentCalculator` called during feature extraction
2. Common opponent comparison added to `MatchFeatureSnapshot`
3. Common opponent features feed ModelOrchestrator (as additional features)
4. `H2HIntelligenceCalculator` called when building AnalysisContext
5. Direct H2H and indirect intelligence clearly separated in AnalysisContext
6. AI Analyst receives structured intelligence, explains both with proper attribution

### 5.4 Data Integrity Handling

#### Insufficient Common Opponents

```python
# CORRECT: Return None when insufficient data
if len(common_opponent_ids) < self.min_common_opponents:
    return CommonOpponentComparison(
        home_team_id=home_team_id,
        away_team_id=away_team_id,
        common_opponent_ids=common_opponent_ids,
        n_common_opponents=len(common_opponent_ids),
        # All comparison fields = None ✓
        comparison_confidence=0.0
    )
```

#### Statistical Evidence Requirement

```python
# CORRECT: Only claim superiority with evidence
if points_differential > 0.5 and comparison_confidence > 0.7:
    signal = "home_favored"
elif points_differential < -0.5 and comparison_confidence > 0.7:
    signal = "away_favored"
else:
    signal = "neutral"  # ✓ Neutral when insufficient evidence
```

### 5.5 Testing Requirements

**Unit Tests**:
- `tests/features/test_common_opponent.py`
  - Test common opponent discovery
  - Test performance comparison aggregation
  - Test handling of no common opponents
  - Test context normalization (home/away)
  
- `tests/analysis/test_h2h_intelligence.py`
  - Test direct H2H calculation
  - Test separation from common opponent
  - Test data quality levels

**Integration Tests**:
- `tests/integration/test_h2h_common_opponent_integration.py`
  - Test AnalysisContext contains both H2H and common opponent
  - Test AI Analyst can distinguish sources

---

## 6. GROUP 4: ADVANCED FEATURE ENGINEERING (10H)

### 6.1 Objectives

Build advanced feature engineering layer that:
- Selects most predictive features from GROUPS 1–3
- Normalizes features for model compatibility
- Creates interaction features where validated
- Tracks feature quality and prevents leakage
- Versions features for reproducibility

### 6.2 New Modules

#### 6.2.1 `backend/app/features/advanced_feature_engineering.py`

**Purpose**: Orchestrate advanced feature selection, normalization, and interaction creation.

**Public Interface**:

```python
@dataclass
class AdvancedFeatureSet:
    """Advanced engineered features for prediction."""
    
    # Selected features (flat dict for model compatibility)
    features: Dict[str, Optional[float]] = field(default_factory=dict)
    
    # Feature metadata
    feature_names: List[str] = field(default_factory=list)
    feature_sources: Dict[str, str] = field(default_factory=dict)  # feature_name -> source module
    feature_quality: Dict[str, float] = field(default_factory=dict)  # feature_name -> quality score
    
    # Normalization metadata
    normalization_applied: bool = False
    normalization_method: str = "none"  # "none", "standard", "minmax"
    
    # Interaction features
    interaction_features: List[str] = field(default_factory=list)
    
    # Versioning
    feature_version: str = "1.0.0"
    snapshot_timestamp: datetime = field(default_factory=datetime.utcnow)
    
    # Leakage prevention
    temporal_validity_checked: bool = False
    no_future_leakage: bool = True

### Feature Versioning Convention

**Format**: Semantic Versioning `MAJOR.MINOR.PATCH`

**Version Increments**:
- **MAJOR**: Breaking changes to feature calculation that invalidate historical comparisons
  - Example: Changing xG calculation methodology
  - Example: Changing opponent adjustment formula
- **MINOR**: New features added, existing features unchanged
  - Example: Adding progressive passes metric
  - Example: Adding new shot threshold
- **PATCH**: Bug fixes, no calculation changes
  - Example: Fixing data quality score calculation
  - Example: Correcting provenance timestamp

**Feature Version Tracking**:
```python
ADVANCED_INTELLIGENCE_VERSION = "1.0.0"  # Initial Phase 10 implementation

# Version attached to every AdvancedFeatureSet
feature_set = AdvancedFeatureSet(
    features={...},
    feature_version=ADVANCED_INTELLIGENCE_VERSION,
    snapshot_timestamp=datetime.utcnow()
)
```

**Backward Compatibility**:
- Predictions without advanced features (pre-Phase 10) continue functioning
- Feature version recorded in PredictionVersion for reproducibility
- Backtesting can filter by feature version for fair comparison
- Version mismatch warnings in production logs

**Version Storage**:
```python
@dataclass
class PredictionVersion:
    # ... existing fields ...
    
    # NEW: Feature version tracking
    feature_version: Optional[str] = None  # e.g., "1.0.0"
    advanced_features_enabled: bool = False
```

### Feature Provenance Metadata

Every advanced feature must preserve provenance for temporal validity verification:

```python
@dataclass
class FeatureProvenance:
    """Provenance metadata for a single feature."""
    
    feature_name: str
    source_module: str  # e.g., "advanced_team_intelligence"
    
    # Temporal validity
    source_timestamp: datetime  # When provider data was fetched
    match_timestamp: Optional[datetime]  # Match date for match-level features
    prediction_cutoff: datetime  # Only data before this timestamp used
    historical_window: str  # e.g., "recent_5", "season"
    
    # Context
    home_away_context: Optional[str]  # "home", "away", "all"
    competition_context: Optional[str]
    
    # Data quality
    availability: str  # "AVAILABLE", "PARTIAL", "UNAVAILABLE"
    data_quality_score: float  # 0.0-1.0
    sample_size: int
    
    # Feature version
    feature_version: str  # e.g., "1.0.0"
    
    def validate_temporal_consistency(self) -> bool:
        """Validate no future leakage."""
        if self.match_timestamp:
            # Historical feature must use data before match
            return self.source_timestamp <= self.match_timestamp
        return self.source_timestamp <= self.prediction_cutoff
```

**Provenance Storage**:
```python
@dataclass
class AdvancedFeatureSet:
    # ... existing fields ...
    
    # Feature provenance (keyed by feature_name)
    feature_provenance: Dict[str, FeatureProvenance] = field(default_factory=dict)
    
    def validate_no_leakage(self) -> bool:
        """Validate all features have valid temporal provenance."""
        return all(p.validate_temporal_consistency() 
                  for p in self.feature_provenance.values())
```

class AdvancedFeatureEngineer:
    """Advanced feature engineering orchestrator."""
    
    def __init__(
        self,
        feature_selection: bool = True,
        normalization: str = "standard",
        create_interactions: bool = False
    ):
        """Initialize feature engineer."""
    
    def engineer_features(
        self,
        snapshot: MatchFeatureSnapshot,
        feature_version: str = "1.0.0"
    ) -> AdvancedFeatureSet:
        """Engineer advanced features from MatchFeatureSnapshot.
        
        Algorithm:
        1. Extract all available features from snapshot (GROUPS 1-3)
        2. Apply feature selection (remove redundant/low-quality features)
        3. Normalize features for model compatibility
        4. Create interaction features where validated
        5. Track provenance: source, quality, version
        6. Validate no future leakage
        
        Args:
            snapshot: MatchFeatureSnapshot with all advanced intelligence
            feature_version: Version string for tracking
            
        Returns:
            AdvancedFeatureSet with engineered features
        """
    
    def validate_no_leakage(
        self,
        snapshot: MatchFeatureSnapshot
    ) -> bool:
        """Validate that snapshot contains no future information.
        
        Returns:
            True if no leakage detected, False otherwise
        """

### Interaction Features (Explicit Operations)

**Interaction Feature Definition**:

Interaction features capture nonlinear relationships between base features. Each interaction is explicitly defined as:

```python
@dataclass
class InteractionFeature:
    """Explicit interaction feature definition."""
    feature_a: str
    feature_b: str
    operation: str  # "multiply", "divide", "ratio", "difference"
    
    def compute(self, features: Dict[str, Optional[float]]) -> Optional[float]:
        """Compute interaction value."""
        a = features.get(self.feature_a)
        b = features.get(self.feature_b)
        
        # Missing value handling
        if a is None or b is None:
            return None
        
        # Compute based on operation
        if self.operation == "multiply":
            return a * b
        elif self.operation == "divide":
            return a / b if b != 0 else None
        elif self.operation == "ratio":
            return a / (a + b) if (a + b) != 0 else None
        elif self.operation == "difference":
            return a - b
        else:
            raise ValueError(f"Unknown operation: {self.operation}")
```

**Candidate Interactions for Phase 10**:

```python
CANDIDATE_INTERACTIONS = [
    # Attack vs Defense matchup
    InteractionFeature(
        feature_a="home_xg_for_advanced",
        feature_b="away_xg_against_advanced",
        operation="multiply"
    ),
    # Shot quality vs volume
    InteractionFeature(
        feature_a="home_xg_per_shot",
        feature_b="home_shots_advanced",
        operation="multiply"
    ),
    # Form vs home advantage
    InteractionFeature(
        feature_a="home_recent_form_weighted",
        feature_b="home_elo_advantage",
        operation="multiply"
    ),
    # Opponent-adjusted strength differential
    InteractionFeature(
        feature_a="home_adj_overall_strength",
        feature_b="away_adj_overall_strength",
        operation="difference"
    ),
]
```

**Validation Before Production**:

Interaction features are **CANDIDATES ONLY** until GROUP 6 backtesting validates:
1. Independent predictive value (not redundant with base features)
2. Statistical significance in out-of-sample testing
3. Stability across different competitions/seasons
4. Improvement in calibrated Brier score

**Integration**:
```python
class AdvancedFeatureEngineer:
    def __init__(
        self,
        feature_selection: bool = True,
        normalization: str = "standard",
        create_interactions: bool = False,  # Disabled by default
        interactions: Optional[List[InteractionFeature]] = None
    ):
        """Initialize with optional interaction feature creation."""
        self.create_interactions = create_interactions
        self.interactions = interactions or []
```

**Production Eligibility**: Interaction features remain DISABLED until GROUP 6 backtesting demonstrates measurable improvement.
```

**Data Integrity**:
- Feature selection never removes features the existing 7 models require
- Normalization metadata tracked for reproducibility
- Interaction features only created when statistically validated (deferred to GROUP 6)
- Leakage validation checks all timestamp fields in snapshot

**Integration Point**: Extends `backend/app/prediction/feature_snapshot.py`:
- `MatchFeatureSnapshot.get_feature_dict()` calls `AdvancedFeatureEngineer` if enabled
- Returns enriched feature dict with advanced features

```python
@dataclass
class MatchFeatureSnapshot:
    # ... existing fields ...
    
    # NEW: Advanced feature engineering
    advanced_feature_set: Optional[AdvancedFeatureSet] = None
    
    def get_feature_dict(self, use_advanced_engineering: bool = True) -> Dict[str, Optional[float]]:
        """Extract flat feature dictionary for model compatibility.
        
        Args:
            use_advanced_engineering: Whether to apply advanced feature engineering
            
        Returns:
            Feature dict with advanced features if enabled
        """
        if use_advanced_engineering and self.advanced_feature_set:
            return self.advanced_feature_set.features
        else:
            # Existing feature extraction logic
            features = {}
            # ... existing code ...
            return features
```

### 6.3 Integration with Existing System

**Flow Through Canonical Pipeline**:

```
1. FeatureAggregator populates MatchFeatureSnapshot with GROUPS 1-3 intelligence
2. AdvancedFeatureEngineer.engineer_features() called on snapshot
3. Advanced features added to snapshot.advanced_feature_set
4. ModelOrchestrator calls snapshot.get_feature_dict(use_advanced_engineering=True)
5. Enriched feature dict fed to all 7 models
6. Ensemble → Calibration → Confidence → MarketDerivation → SmartMarketSelector
```

### 6.4 Data Integrity Handling

#### Leakage Prevention

```python
def validate_no_leakage(self, snapshot: MatchFeatureSnapshot) -> bool:
    """Validate no future leakage."""
    prediction_time = snapshot.snapshot_created_at
    
    # Check all timestamp fields
    if snapshot.scheduled_at and snapshot.scheduled_at < prediction_time:
        pass  # ✓ Match is in future, features calculated before match
    else:
        return False  # ✗ Leakage detected
    
    # Check form data timestamps
    if snapshot.home_form and snapshot.home_form.matches_analyzed:
        # All analyzed matches should be before prediction_time
        pass  # (actual validation logic)
    
    return True
```

### 6.5 Testing Requirements

**Unit Tests**:
- `tests/features/test_advanced_feature_engineering.py`
  - Test feature selection
  - Test normalization
  - Test leakage validation
  - Test feature versioning

**Integration Tests**:
- `tests/integration/test_advanced_feature_pipeline.py`
  - Test feature engineering integrated into feature_snapshot
  - Test ModelOrchestrator receives advanced features

---

## 7. GROUP 5: MARKET-SPECIFIC & UNCERTAINTY (10I, 10J)

### 7.1 Objectives

Enhance market derivation and confidence assessment with:
- Market-specific feature selection and optimization
- Model disagreement as uncertainty signal
- Enhanced confidence assessment from pipeline components

### 7.2 Enhancements to Existing Modules

#### 7.2.1 Extension of `backend/app/prediction/market_derivation.py`

**Changes**: Add market-specific feature selection logic.

**New Interface**:

```python
class MarketDerivationEngine:
    def __init__(
        self,
        top_scorelines: int = 20,
        market_specific_optimization: bool = False
    ):
        """Initialize market derivation engine.
        
        Args:
            top_scorelines: Number of top scorelines for exact score market
            market_specific_optimization: Whether to apply market-specific feature selection
        """
    
    def derive_with_market_optimization(
        self,
        score_distribution: Dict[Tuple[int, int], float],
        snapshot: MatchFeatureSnapshot,
        market_type: str = "1X2"
    ) -> MarketProbabilities:
        """Derive market probabilities with market-specific optimization.
        
        For market_type "1X2": prioritize form, Elo, recent results
        For market_type "OVER_UNDER": prioritize xG, shots, goal averages
        For market_type "BTTS": prioritize defensive metrics, xGA
        For market_type "SHOT_MARKETS": prioritize shot intelligence
        
        This is experimental feature selection, validated in GROUP 6.
        
        Args:
            score_distribution: Score distribution from simulation
            snapshot: MatchFeatureSnapshot with all features
            market_type: Market type for feature selection
            
        Returns:
            MarketProbabilities optimized for market_type
        """
```

**Data Integrity**:
- Market-specific optimization is optional (disabled by default)
- Optimization logic validated in GROUP 6 backtesting
- Never changes score_distribution; only selects which features influenced upstream models

#### 7.2.2 Extension of `backend/app/prediction/confidence_engine.py`

**Changes**: Enhance confidence assessment with model disagreement as uncertainty signal.

**New Interface**:

```python
class ConfidenceEngine:
    def assess_with_disagreement(
        self,
        model_agreement: float,
        data_quality_score: float,
        n_matches: int,
        model_disagreement_detail: Optional[Dict[str, Any]] = None,
        brier_score: Optional[float] = None,
        lineup_status: str = "unknown",
        recent_predictions: Optional[List] = None
    ) -> ConfidenceAssessment:
        """Assess confidence with detailed model disagreement analysis.
        
        Args:
            model_agreement: 0.0-1.0 from ensemble
            data_quality_score: 0.0-1.0 from data quality report
            n_matches: Sample size
            model_disagreement_detail: Detailed disagreement metrics
                - std_dev_home_win: Std dev of home win probabilities
                - std_dev_draw: Std dev of draw probabilities
                - max_disagreement_model_ids: Models with highest disagreement
            brier_score: Historical Brier score (if available)
            lineup_status: "confirmed", "expected", "unknown"
            recent_predictions: Recent predictions for stability analysis
            
        Returns:
            ConfidenceAssessment with disagreement details
        """
```

**Data Integrity**:
- Model disagreement comes from actual ensemble calculation (not fabricated)
- High disagreement → lower confidence (validated against historical performance in GROUP 6)
- Never converts agreement to arbitrary confidence % without validation

#### 7.2.3 Extension of `backend/app/prediction/market_selector.py`

**Changes**: Support shot markets and enhanced PASS decision logic.

**New Interface**:

```python
class SmartMarketSelector:
    def __init__(
        self,
        min_confidence: float = 0.4,
        min_probability: float = 0.5,
        min_edge: float = 0.0,
        max_risk_level: str = "HIGH",
        enable_shot_markets: bool = False
    ):
        """Initialize smart market selector.
        
        Args:
            min_confidence: Minimum confidence threshold
            min_probability: Minimum probability threshold
            min_edge: Minimum edge threshold (when odds available)
            max_risk_level: Maximum acceptable risk level
            enable_shot_markets: Whether to evaluate shot markets
        """
    
    def _evaluate_shot_markets(
        self,
        shot_markets: ShotMarketProbabilities,
        team: str,
        candidates: List[Dict[str, Any]]
    ) -> None:
        """Evaluate shot markets and add to candidates.
        
        Args:
            shot_markets: Shot market probabilities
            team: "home" or "away"
            candidates: List of candidate markets
        """
```

**Data Integrity**:
- Shot markets only evaluated when `enable_shot_markets=True` and shot data available
- PASS decision includes reason (e.g., "no_shot_data" when shot markets unavailable)

### 7.3 Integration with Existing System

**No New Modules**: GROUP 5 extends existing modules only.

**Flow**:
1. Ensemble provides `model_agreement` and `model_disagreement_detail` to ConfidenceEngine
2. ConfidenceEngine assesses confidence with disagreement as uncertainty signal
3. MarketDerivationEngine optionally applies market-specific optimization
4. SmartMarketSelector evaluates shot markets if enabled and available
5. PASS decision enriched with disagreement/uncertainty reasoning

### 7.4 Testing Requirements

**Unit Tests**:
- `tests/prediction/test_market_derivation_optimization.py`
  - Test market-specific feature selection logic
  
- `tests/prediction/test_confidence_disagreement.py`
  - Test disagreement calculation
  - Test confidence reduction with high disagreement
  
- `tests/prediction/test_market_selector_shot_markets.py`
  - Test shot market evaluation
  - Test PASS decision with shot markets unavailable

**Integration Tests**:
- `tests/integration/test_market_specific_pipeline.py`
  - Test market-specific optimization end-to-end
  - Test disagreement flows through confidence assessment

---

## 8. GROUP 6: WALK-FORWARD BACKTESTING (10K)

### 8.1 Objectives

Validate advanced features through walk-forward backtesting:
- Enforce temporal validity (freeze prediction timestamp, load only pre-timestamp data)
- Compare BASELINE vs BASELINE+ADVANCED performance
- Validate shot markets
- Measure statistical significance of improvements

### 8.2 Enhancements to Existing Modules

#### 8.2.1 Extension of `backend/app/prediction/backtest.py`

**Changes**: Add walk-forward validation mode.

**New Interface**:

```python
class WalkForwardBacktester:
    """Walk-forward backtesting with strict temporal validity enforcement."""
    
    def __init__(
        self,
        initial_training_window_days: int = 180,
        test_window_days: int = 30,
        step_size_days: int = 30
    ):
        """Initialize walk-forward backtester.
        
        Args:
            initial_training_window_days: Initial training window
            test_window_days: Test window size
            step_size_days: Step size between windows
        """
    
    def run_walk_forward(
        self,
        matches_with_stats: List[MatchWithStatistics],
        use_advanced_features: bool = True
    ) -> WalkForwardBacktestResult:
        """Run walk-forward backtest with temporal validity enforcement.
        
        **CRITICAL TEMPORAL VALIDITY ENFORCEMENT**:
        
        For each test window, ALL feature calculators MUST respect before_datetime:
        
        1. **AdvancedTeamIntelligenceCalculator** (3.2.1):
           - calculate_advanced_metrics(before_datetime=prediction_timestamp)
           - Filters matches before cutoff
        
        2. **OpponentAdjustmentCalculator** (3.2.2):
           - calculate_adjusted_metrics(before_datetime=prediction_timestamp)
           - Retrieves opponent Elo AT prediction_timestamp
        
        3. **TemporalIntelligenceCalculator** (3.2.3):
           - calculate_temporal_metrics(before_datetime=prediction_timestamp)
           - Recency weights only pre-cutoff matches
        
        4. **ShotIntelligenceCalculator** (4.2.1):
           - calculate_shot_metrics(before_datetime=prediction_timestamp)
           - Shot statistics from pre-cutoff matches only
        
        5. **LineupIntelligenceCalculator** (4.2.3):
           - Uses historical_matches_with_stats filtered before cutoff
        
        6. **CommonOpponentCalculator** (5.2.1):
           - find_common_opponents(before_datetime=prediction_timestamp)
           - Common opponent comparisons from pre-cutoff data
        
        7. **AdvancedFeatureEngineer** (6.2.1):
           - Operates on MatchFeatureSnapshot already enforcing cutoff
           - validate_no_leakage() checks all provenance timestamps
        
        Algorithm:
        1. For each test window:
           a. **Freeze prediction_timestamp = test_window_start**
           b. Load only matches WHERE match.scheduled_at < prediction_timestamp
           c. Build FeatureSnapshot:
              - Pass before_datetime=prediction_timestamp to ALL calculators
              - Verify no match from test window in training data
           d. Run prediction using enriched features
           e. Compare vs actual result (loaded AFTER prediction)
        2. Aggregate metrics across all windows
        3. Validate temporal consistency post-hoc
        
        Args:
            matches_with_stats: All historical matches (chronologically ordered)
            use_advanced_features: Whether to use advanced features
            
        Returns:
            WalkForwardBacktestResult with temporal validity enforced
            
        Temporal Leakage Prevention:
            - Feature extraction called with explicit cutoff timestamp
            - No match after prediction_timestamp in feature calculation
            - Opponent ratings reconstructed at cutoff, not current
            - Result data loaded AFTER prediction recorded
        """
```

**Data Integrity**:
- `before_datetime` parameter enforced in all feature calculations
- No match from test window appears in training data
- Feature snapshot reconstructed at each prediction_timestamp

#### 8.2.2 New Module: `backend/app/prediction/baseline_comparison.py`

**Purpose**: Compare BASELINE (existing 7 models) vs BASELINE+ADVANCED (with Phase 10 features).

**Public Interface**:

```python
@dataclass
class BaselineComparisonResult:
    """Result of baseline vs advanced comparison."""
    
    # Baseline performance (existing 7 models, no advanced features)
    baseline_accuracy: float
    baseline_brier_score: float
    baseline_log_loss: float
    baseline_calibration_error: float
    
    # Advanced performance (existing 7 models + advanced features)
    advanced_accuracy: float
    advanced_brier_score: float
    advanced_log_loss: float
    advanced_calibration_error: float
    
    # Improvement
    accuracy_improvement: float
    brier_improvement: float
    log_loss_improvement: float
    calibration_improvement: float
    
    # Statistical significance
    accuracy_p_value: Optional[float] = None
    brier_p_value: Optional[float] = None
    
    # Sample size
    n_predictions_baseline: int = 0
    n_predictions_advanced: int = 0

class BaselineComparison:
    """Compare baseline vs advanced feature performance."""
    
    def run_comparison(
        self,
        matches: List[Match],
        test_period_start: datetime,
        test_period_end: datetime
    ) -> BaselineComparisonResult:
        """Run baseline vs advanced comparison.
        
        Returns:
            BaselineComparisonResult with statistical significance
        """
```

#### 8.2.3 New Module: `backend/app/prediction/market_backtesting.py`

**Purpose**: Backtest market-level performance including shot markets.

**Public Interface**:

```python
@dataclass
class MarketBacktestResult:
    """Backtest result for a specific market."""
    
    market_type: str  # "1X2", "OVER_UNDER", "BTTS", "SHOT_MARKETS"
    
    # Performance metrics
    accuracy: Optional[float] = None
    brier_score: Optional[float] = None
    log_loss: Optional[float] = None
    calibration_error: Optional[float] = None
    
    # Confidence bucket analysis
    high_confidence_accuracy: Optional[float] = None  # Predictions with confidence > 0.7
    medium_confidence_accuracy: Optional[float] = None  # 0.4 < confidence <= 0.7
    low_confidence_accuracy: Optional[float] = None  # confidence <= 0.4
    
    # Data quality bucket analysis
    high_quality_accuracy: Optional[float] = None  # data_quality > 0.7
    low_quality_accuracy: Optional[float] = None  # data_quality <= 0.7
    
    # Sample sizes
    n_predictions: int = 0
    n_high_confidence: int = 0
    n_high_quality: int = 0

class MarketBacktester:
    """Backtest market-level performance."""
    
    def backtest_market(
        self,
        market_type: str,
        predictions: List[PredictionRecord],
        actual_results: List[Any]
    ) -> MarketBacktestResult:
        """Backtest specific market.
        
        Args:
            market_type: Market type to backtest
            predictions: Prediction records
            actual_results: Actual match results
            
        Returns:
            MarketBacktestResult with confidence/quality bucket analysis
        """
```

**Data Integrity**:
- Shot market backtesting only runs when shot data available
- Confidence bucket analysis based on actual confidence scores (not fabricated thresholds)
- ROI calculation deliberately absent unless real historical odds provided

### 8.3 Integration with Existing System

**Flow**:
1. `WalkForwardBacktester` calls existing `ModelOrchestrator` twice:
   - Once with `use_advanced_features=False` (baseline)
   - Once with `use_advanced_features=True` (advanced)
2. `BaselineComparison` aggregates results and calculates statistical significance
3. `MarketBacktester` evaluates each market type separately
4. Results documented in `docs/PROGRESS.md` after each GROUP implementation

### 8.4 Testing Requirements

**Unit Tests**:
- `tests/prediction/test_walk_forward_backtest.py`
  - Test temporal validity enforcement
  - Test before_datetime filtering
  
- `tests/prediction/test_baseline_comparison.py`
  - Test baseline vs advanced comparison
  - Test statistical significance calculation
  
- `tests/prediction/test_market_backtesting.py`
  - Test market-level backtesting
  - Test confidence bucket analysis

**Integration Tests**:
- `tests/integration/test_walk_forward_pipeline.py`
  - Test full walk-forward backtest with actual matches
  - Test baseline comparison end-to-end

---

## 9. GROUP 7: SELF-EVALUATION & DIAGNOSTICS (10L)

### 9.1 Objectives

Build self-evaluation intelligence for diagnosing prediction failures and measuring feature contributions:
- Classify prediction failures (wrong favorite, underdog surprise, poor data, model disagreement)
- Measure feature contributions to predictions
- Diagnose shot market failures
- No automatic production changes — diagnostics only

### 9.2 New Modules

#### 9.2.1 `backend/app/prediction/error_analysis.py`

**Purpose**: Classify prediction failures with measurable diagnostics.

**Public Interface**:

```python
@dataclass
class PredictionError:
    """Classified prediction error."""
    
    prediction_id: str
    match_id: str
    
    # Error classification
    error_type: str  # "wrong_favorite", "underdog_surprise", "poor_data", 
                     # "model_disagreement", "tactical_mismatch", 
                     # "common_opponent_signal_failure", "shot_volume_error"
    
    # Diagnostics
    predicted_outcome: str
    actual_outcome: str
    prediction_probability: float
    model_agreement: float
    data_quality_score: float
    confidence_score: float
    
    # Contributing factors
    contributing_factors: List[str] = field(default_factory=list)
    
    # Suggested improvements
    suggested_improvements: List[str] = field(default_factory=list)

class ErrorAnalyzer:
    """Analyze prediction errors."""
    
    def classify_error(
        self,
        prediction: PredictionVersion,
        actual_result: Match
    ) -> PredictionError:
        """Classify prediction error.
        
        Algorithm:
        1. Determine error type based on probability, agreement, data quality
        2. Identify contributing factors (e.g., low data quality, high disagreement)
        3. Suggest improvements (e.g., "improve xG data availability")
        
        Args:
            prediction: Prediction version
            actual_result: Actual match result
            
        Returns:
            PredictionError with classification and diagnostics
        """
```

#### 9.2.2 `backend/app/prediction/feature_diagnostics.py`

**Purpose**: Measure feature contributions to predictions.

**Public Interface**:

```python
@dataclass
class FeatureContribution:
    """Contribution of a feature to prediction."""
    
    feature_name: str
    contribution_score: float  # 0.0-1.0
    direction: str  # "positive", "negative", "neutral"
    importance_rank: int

@dataclass
class FeatureDiagnostics:
    """Feature diagnostics for a prediction."""
    
    prediction_id: str
    
    # Feature contributions
    feature_contributions: List[FeatureContribution] = field(default_factory=list)
    
    # Redundancy detection
    redundant_features: List[Tuple[str, str]] = field(default_factory=list)  # (feature1, feature2)
    
    # Proposed improvements
    proposed_improvements: List[str] = field(default_factory=list)

class FeatureDiagnosticEngine:
    """Diagnose feature contributions."""
    
    def measure_contributions(
        self,
        prediction: PredictionVersion,
        snapshot: MatchFeatureSnapshot
    ) -> FeatureDiagnostics:
        """Measure feature contributions.
        
        Algorithm:
        1. For each feature, calculate contribution to ensemble prediction
        2. Rank features by contribution
        3. Detect redundant features (high correlation, low independent contribution)
        4. Propose improvements (e.g., "remove redundant feature X")
        
        Args:
            prediction: Prediction version
            snapshot: Feature snapshot
            
        Returns:
            FeatureDiagnostics with contributions and recommendations
        """
```

#### 9.2.3 `backend/app/prediction/shot_market_diagnostics.py`

**Purpose**: Diagnose shot market prediction failures.

**Public Interface**:

```python
@dataclass
class ShotMarketError:
    """Shot market prediction error."""
    
    match_id: str
    team: str  # "home" or "away"
    
    # Predicted vs actual
    predicted_shots_mean: float
    actual_shots: int
    error: float  # actual - predicted
    
    # Error classification
    error_type: str  # "volume_overestimate", "volume_underestimate", 
                     # "quality_mismatch", "opponent_suppression_error"
    
    # Contributing factors
    shot_intel_quality: float
    opponent_adjustment_available: bool
    
    # Diagnostics
    diagnostics: Dict[str, Any] = field(default_factory=dict)

class ShotMarketDiagnostics:
    """Diagnose shot market errors."""
    
    def diagnose_shot_error(
        self,
        prediction: PredictionVersion,
        actual_shots: int,
        team: str
    ) -> ShotMarketError:
        """Diagnose shot market error.
        
        Returns:
            ShotMarketError with classification and diagnostics
        """
```

### 9.3 Integration with Existing System

**Flow**:
1. After backtest (GROUP 6), ErrorAnalyzer classifies all prediction errors
2. FeatureDiagnosticEngine measures contributions for sample of predictions
3. ShotMarketDiagnostics analyzes shot market errors (when shot data available)
4. Diagnostics logged to database or file
5. **No automatic production changes** — diagnostics used for manual analysis

### 9.4 Testing Requirements

**Unit Tests**:
- `tests/prediction/test_error_analysis.py`
- `tests/prediction/test_feature_diagnostics.py`
- `tests/prediction/test_shot_market_diagnostics.py`

**Integration Tests**:
- `tests/integration/test_diagnostics_pipeline.py`
  - Test diagnostics run after backtest
  - Test diagnostics do not modify production pipeline

---

## 10. IMPLEMENTATION STRATEGY

### 10.1 Dependency-Ordered Implementation

Groups must be implemented in order due to dependencies:

```
GROUP 1 (Team Intelligence) → BASE
  ↓
GROUP 2 (Shot & Lineup Intelligence) → depends on GROUP 1
  ↓
GROUP 3 (Common Opponent Intelligence) → depends on GROUP 1
  ↓
GROUP 4 (Advanced Feature Engineering) → depends on GROUPS 1, 2, 3
  ↓
GROUP 5 (Market-Specific & Uncertainty) → depends on GROUP 4
  ↓
GROUP 6 (Walk-Forward Backtesting) → depends on GROUPS 1-5
  ↓
GROUP 7 (Self-Evaluation & Diagnostics) → depends on GROUPS 1-6
```

### 10.2 After Each Group

1. **Implement** all modules in group
2. **Write tests** (unit + integration + regression)
3. **Run baseline test suite** — verify existing functionality preserved
4. **Run new tests** — verify new functionality works
5. **Run integration test** — verify new features flow through pipeline
6. **Update `docs/PROGRESS.md`** — document what was done, how verified, what comes next
7. **Commit** before proceeding to next group

### 10.3 Verification Commands

After each group:

```powershell
# Backend tests
cd C:\FootballIntelligence\backend
.venv\Scripts\python.exe -m pytest tests/ -v

# Specific group tests
.venv\Scripts\python.exe -m pytest tests/features/test_advanced_team_intelligence.py -v

# Integration tests
.venv\Scripts\python.exe -m pytest tests/integration/ -v

# Regression tests (baseline)
.venv\Scripts\python.exe -m pytest tests/prediction/test_model_orchestrator.py -v
```

---

## 11. RISKS & MITIGATION

### 11.1 Data Availability Risks

| Risk | Mitigation |
|------|------------|
| **xG data unavailable from providers** | All xG metrics Optional; None when unavailable; no silent fallback |
| **Shot data unavailable from providers** | Shot markets only available when shot data exists; PASS otherwise |
| **Lineup data unavailable** | Lineup impact all None; uncertainty tracked in confidence |
| **Common opponents insufficient** | Common opponent comparison None when < 3 shared opponents |

### 11.2 Temporal Leakage Risks

| Risk | Mitigation |
|------|------------|
| **Future data in historical features** | All calculators accept `before_datetime`; enforced in walk-forward backtest |
| **Result known before prediction** | Feature snapshot timestamp checked against match scheduled_at |
| **Calibration data from future** | Calibration only uses historical predictions before test match |

### 11.3 Model Performance Risks

| Risk | Mitigation |
|------|------------|
| **Advanced features degrade existing models** | Baseline comparison (GROUP 6) validates improvement; rollback if degradation |
| **Opponent-adjusted features double-count Elo** | Validate independent contribution in GROUP 6; exclude if redundant |
| **Interaction features overfit** | Only create interactions validated in GROUP 6; disabled by default |
| **Shot markets perform worse than 1X2** | Shot markets optional; PASS when insufficient confidence |

### 11.4 Integration Risks

| Risk | Mitigation |
|------|------------|
| **Advanced features break existing pipeline** | Regression tests after each group; advanced features optional (feature flag) |
| **MatchFeatureSnapshot becomes too large** | Dataclass fields Optional; only populated when available |
| **Performance degradation from complexity** | Profile after each group; optimize hot paths |

---

## 12. SUMMARY

Phase 10 Advanced Football Intelligence extends the existing MENSIONE prediction engine with:

- **7 Groups** of dependency-ordered advanced intelligence modules
- **No parallel prediction engines** — all features flow through existing ModelOrchestrator → Ensemble → Calibration → Confidence → MarketDerivation → SmartMarketSelector
- **Data integrity enforced** — REAL DATA > NULL > FABRICATED; provenance tracked; temporal validity guaranteed
- **Existing functionality preserved** — all 7 models, pipeline components, API contracts unchanged
- **Validated contribution** — walk-forward backtesting (GROUP 6) validates each feature group before production use
- **Self-evaluation** — error analysis and feature diagnostics (GROUP 7) enable continuous improvement

**Implementation Path**:
1. GROUP 1 (Team Intelligence) — extends features/team_strength.py
2. GROUP 2 (Shot & Lineup Intelligence) — extends prediction/market_derivation.py, prediction/market_selector.py
3. GROUP 3 (Common Opponent Intelligence) — extends analysis/analysis_context.py
4. GROUP 4 (Advanced Feature Engineering) — extends prediction/feature_snapshot.py
5. GROUP 5 (Market-Specific & Uncertainty) — extends prediction/confidence_engine.py
6. GROUP 6 (Walk-Forward Backtesting) — extends prediction/backtest.py
7. GROUP 7 (Self-Evaluation & Diagnostics) — new diagnostic modules

**Critical Success Factors**:
- Never fabricate data (NULL when unavailable)
- Preserve existing functionality (regression tests pass)
- Enforce temporal validity (no future leakage)
- Validate contribution (baseline comparison shows improvement)
- Document progress (update docs/PROGRESS.md after each group)

---

**END OF DESIGN DOCUMENT**


---

## APPENDIX A: DESIGN REVISION SUMMARY

**Document Version**: 2.0 (Revised)  
**Revision Date**: 2026-10-05  
**Previous Review Verdict**: CHANGES_REQUESTED  

This appendix documents all design revisions made in response to the design review findings.

---

### HIGH FINDINGS - RESOLVED

#### HIGH #1 — Match vs TeamMatchStatistic Data Contract ✅ RESOLVED

**Issue**: Design incorrectly assumed Match contains statistics (xG, shots, etc.). These reside in TeamMatchStatistic.

**Resolution**:
- Added `MatchWithStatistics` dataclass (Section 3.2.1) pairing Match with home/away TeamMatchStatistic
- Changed ALL calculator signatures from `List[Match]` to `List[MatchWithStatistics]`
- Explicit documentation of missing statistics handling (None, not fabricated)
- Algorithm sections specify how to extract team statistics for home/away roles

**Affected Interfaces**:
- `AdvancedTeamIntelligenceCalculator.calculate_advanced_metrics()`
- `OpponentAdjustmentCalculator.calculate_adjusted_metrics()`
- `TemporalIntelligenceCalculator.calculate_temporal_metrics()`
- `ShotIntelligenceCalculator.calculate_shot_metrics()`
- All GROUP 1-3 calculators

---

#### HIGH #2 — Unavailable Tactical Metrics ✅ RESOLVED

**Issue**: Design referenced metrics not in current TeamMatchStatistic model (PPDA, Field Tilt, progressive passes, etc.).

**Resolution**:
- Added **DATA AVAILABILITY & CAPABILITY MATRIX** (Section 2.1)
- Documented CURRENTLY AVAILABLE vs UNAVAILABLE metrics with explicit table
- Marked unavailable metrics with comments: `# UNAVAILABLE until provider integration`
- Explicit fallback: return `None`, never zero or estimated
- Shot location features marked UNAVAILABLE until coordinates exist
- Production eligibility matrix clarifies what can be used now

**Key Additions**:
- Table of available TeamMatchStatistic fields
- Table of unavailable tactical metrics requiring future provider integration
- Shot location data availability note
- Manager change data availability note

---

#### HIGH #3 — Historical Opponent Strength & Temporal Validity ✅ RESOLVED

**Issue**: Opponent adjustment methodology lacked specification of historical rating reconstruction and temporal leakage prevention.

**Resolution**:
- Added **OpponentStrengthAtTime** dataclass (Section 3.2.2)
- Explicit use of existing `EloRatingSystem` for opponent strength
- Documented temporal validity contract: `rating_at_prediction_time`, not current rating
- Data flow diagram for historical opponent rating reconstruction
- `self.elo_system.get_rating_at_time(opponent_id, match.scheduled_at)` specified
- Temporal leakage prevention algorithm in calculate_adjusted_metrics()
- Home/away context handling documented

**Key Additions**:
- OpponentStrengthAtTime with timestamp validation
- Historical Elo reconstruction methodology
- Temporal consistency assertion
- Integration with existing EloRatingSystem
- Avoiding double-counting with Elo (validation deferred to backtesting)

---

#### HIGH #6 — Shot Distribution Methodology ✅ RESOLVED

**Issue**: Shot market probability calculation lacked explicit mathematical formulas.

**Resolution**:
- Added **Shot Distribution Methodology (EXPLICIT MATHEMATICAL SPECIFICATION)** section before ShotProductionCalculator
- Explicit formulas for:
  - Mean (μ) and variance (σ²) calculation
  - Distribution selection: `if variance > mean: use Negative Binomial, else: Poisson`
  - Negative Binomial parameterization: `r = μ² / (σ² - μ)`, `p = μ / σ²`
  - Poisson parameterization: `λ = μ`
  - Threshold probability: `P(X > T) = 1 - CDF(T)`
- Explicit edge cases (mean=0, variance=0, variance=mean, variance<mean)
- Opponent adjustment formula
- Minimum sample size requirements
- Calibration path integration
- Uncertainty propagation
- Integration with existing pipeline (no parallel shot engine)

**Mathematical Rigor**: Distribution selection, parameterization, and threshold calculation now fully specified.

---

### MEDIUM FINDINGS - RESOLVED

#### MEDIUM #4 — Manager Change Data ✅ RESOLVED

**Issue**: Repository lacks manager change tracking.

**Resolution**:
- Added **CRITICAL: Manager/Coach Change Data Availability** section (3.2.3)
- Documented repository does NOT have manager tracking
- Regime change strategy: Statistical detection (AVAILABLE) vs External data (FUTURE)
- `RegimeChange.detected_by` field distinguishes: "statistical", "external_data", "manual"
- Statistical detection has lower confidence than verified events
- `is_verified_external()` method to check source
- Future provider integration interface defined but not implemented

**Key Distinction**: Statistical performance shifts vs verified manager changes clearly separated.

---

#### MEDIUM #5 — Shot Location Data ✅ RESOLVED

**Issue**: Box shot percentage requires coordinates that don't exist.

**Resolution**:
- Shot location availability documented in Section 2.1 DATA AVAILABILITY MATRIX
- `box_shot_percentage` marked UNAVAILABLE until shot coordinates exist
- `shots_inside_box_per_match` marked UNAVAILABLE
- Future provider capability interface defined (ShotEvent with coordinates)
- Explicit: NO calculation without real location data

---

#### MEDIUM — Lineup Impact Methodology ✅ RESOLVED

**Issue**: Lineup impact lacked explicit historical methodology.

**Resolution**:
- Added **Statistical Methodology** section in LineupIntelligenceCalculator (4.2.3)
- With/without player sample split algorithm
- Performance differential calculation with formulas
- Confidence calculation based on sample sizes and balance
- Context normalization (opponent, home/away, importance)
- Replacement player quality handling
- Minimum sample size requirements
- Explicit: NO arbitrary percentage penalties
- Integration with existing ConfidenceEngine documented

---

#### MEDIUM — Common Opponent Confidence ✅ RESOLVED

**Issue**: Comparison confidence formula undefined.

**Resolution**:
- Added **Common Opponent Confidence Calculation** section (5.2.1)
- Explicit confidence formula:
  ```
  confidence = (sample_factor) * (recency_factor) * (context_factor)
  ```
- Sample factor: `min(1.0, n_common_opponents / 5)`
- Recency factor: `avg_match_recency_weight`
- Context factor: `home_away_match_rate`
- Statistical evidence threshold for signal classification
- Risk classification: MEDIUM RISK (not LOW)
- Never claim superiority without sufficient evidence (thresholds defined)

---

#### MEDIUM — Feature Versioning ✅ RESOLVED

**Issue**: Feature version convention undefined.

**Resolution**:
- Added **Feature Versioning Convention** section (6.2.1)
- Semantic versioning: `MAJOR.MINOR.PATCH`
- Version increment rules (breaking changes, new features, bug fixes)
- `ADVANCED_INTELLIGENCE_VERSION = "1.0.0"` constant
- Version attached to every AdvancedFeatureSet
- Backward compatibility strategy
- Version storage in PredictionVersion

---

#### MEDIUM — Interaction Features ✅ RESOLVED

**Issue**: Interaction features lacked concrete examples and operations.

**Resolution**:
- Added **Interaction Features (Explicit Operations)** section (6.2.1)
- `InteractionFeature` dataclass with explicit operations
- Supported operations: "multiply", "divide", "ratio", "difference"
- Missing value handling (None propagation)
- Candidate interactions with concrete examples:
  - home_xg_for × away_xg_against
  - xg_per_shot × shots
  - recent_form × home_advantage
  - strength differentials
- Validation requirement: disabled by default until GROUP 6 backtesting validates

---

#### MEDIUM — Walk-Forward Temporal Enforcement ✅ RESOLVED

**Issue**: Needed explicit list of all calculators that must enforce before_datetime.

**Resolution**:
- Added **CRITICAL TEMPORAL VALIDITY ENFORCEMENT** section in WalkForwardBacktester (8.2.1)
- Explicit list of ALL 7 feature calculators that MUST respect before_datetime:
  1. AdvancedTeamIntelligenceCalculator
  2. OpponentAdjustmentCalculator
  3. TemporalIntelligenceCalculator
  4. ShotIntelligenceCalculator
  5. LineupIntelligenceCalculator
  6. CommonOpponentCalculator
  7. AdvancedFeatureEngineer
- Each with specific parameter and behavior documentation
- Algorithm expanded with temporal leakage prevention steps

---

#### MEDIUM — Feature Provenance ✅ RESOLVED

**Issue**: Provenance metadata structure undefined.

**Resolution**:
- Added **Feature Provenance Metadata** section (6.2.1)
- `FeatureProvenance` dataclass with complete metadata:
  - Temporal: source_timestamp, match_timestamp, prediction_cutoff, historical_window
  - Context: home_away_context, competition_context
  - Quality: availability, data_quality_score, sample_size
  - Version: feature_version
- `validate_temporal_consistency()` method
- Provenance stored per-feature in AdvancedFeatureSet
- `validate_no_leakage()` checks all provenance

---

### LOW FINDINGS - RESOLVED

#### LOW — Recursive Model Structure ✅ RESOLVED

**Issue**: Potential recursive structures in home/away metrics.

**Resolution**:
- `home_xg_for_per_match` and `away_xg_for_per_match` documented as scalar Optional[float]
- Not nested AdvancedTeamMetrics objects
- Comment added: "# Separate home-only calculation" and "# Separate away-only calculation"
- No recursive structures in final design

---

#### LOW — Backtesting Cutoff ✅ RESOLVED

**Issue**: Explicit list of feature calculators needing before_datetime enforcement.

**Resolution**: Covered in MEDIUM Walk-Forward Temporal Enforcement above.

---

### DESIGN COMPLETENESS VERIFICATION

**Data Contract**: ✅ All interfaces use MatchWithStatistics, not raw Match  
**Tactical Metrics**: ✅ Availability matrix documents what exists vs what's unavailable  
**Opponent Strength**: ✅ Historical Elo reconstruction with temporal validity  
**Shot Distribution**: ✅ Complete mathematical specification with formulas  
**Manager Changes**: ✅ Statistical detection vs external data clearly distinguished  
**Shot Location**: ✅ Marked unavailable until coordinates exist  
**Lineup Impact**: ✅ Statistical methodology with sample requirements  
**Common Opponent**: ✅ Explicit confidence formula and thresholds  
**Feature Versioning**: ✅ Semantic versioning convention defined  
**Interaction Features**: ✅ Explicit operations with concrete examples  
**Walk-Forward**: ✅ All 7 calculators listed with temporal enforcement  
**Feature Provenance**: ✅ Complete metadata structure with validation  

---

### REMAINING LIMITATIONS

**Explicitly Documented as UNAVAILABLE** (not design flaws):

1. **Tactical Metrics**: PPDA, Field Tilt, progressive passes/carries, box entries, high turnovers require future provider integration
2. **Shot Coordinates**: Box shot percentage, shots inside box require shot location data
3. **Manager Changes**: Only statistical detection available initially; external events require provider
4. **Interaction Features**: Disabled by default until GROUP 6 backtesting validates
5. **Non-Penalty xG**: Requires xG event-type separation from provider
6. **Set-Piece xG**: Requires xG event-type separation from provider

These are **DATA LIMITATIONS**, not design deficiencies. Design handles unavailability correctly (return None, mark UNAVAILABLE, never fabricate).

---

### ARCHITECTURE PRESERVATION CONFIRMATION

✅ **7-Model Engine**: Preserved (Poisson, Dixon-Coles, Elo, Monte Carlo, Negative Binomial, Form Adjusted, Logistic Regression)  
✅ **Canonical Pipeline**: Advanced intelligence feeds existing FeatureSnapshot → ModelOrchestrator flow  
✅ **No Parallel Systems**: Shot intelligence flows through existing market derivation  
✅ **Backward Compatibility**: Predictions without advanced features continue functioning  
✅ **Existing Backtesting**: WalkForwardBacktester extends, not replaces  
✅ **Existing Confidence**: ConfidenceEngine extended compatibly  

---

### IMPLEMENTATION READINESS

This design (v2.0) resolves ALL HIGH and MEDIUM findings from the review verdict.

**Ready for semantic review approval** pending verification of:
- All interfaces implementable against actual repository models
- All temporal validity mechanisms enforceable
- All data availability constraints respected
- All mathematical methodologies complete and explicit
- No fabrication of unavailable data

**No production implementation performed in this revision** — design document only updated.


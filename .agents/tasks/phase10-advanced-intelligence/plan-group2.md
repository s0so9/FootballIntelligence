# Phase 10 Group 2 Implementation Plan

**Target**: Implement 10D (Lineup Intelligence), 10E (Tactical Matchup), 10F (Shot Intelligence), 10F-1 (Shot Production) for MENSIONE Football Intelligence Platform

**Context**: Group 1 (10A, 10B, 10C) is MERGED to main (commit 72d18af, 53/53 tests passing). Group 2 builds on existing MatchWithStatistics, TemporalIntelligenceCalculator, OpponentAdjustmentCalculator patterns.

**Critical Data Findings from Exploration**:
- **AVAILABLE** from TeamMatchStatistic: xg, xg_against, shots_total, shots_on_target, shots_off_target, shots_blocked, possession_percentage
- **UNAVAILABLE** (remain None): PPDA, Field Tilt, progressive passes, box entries, shot coordinates, big chances, non-penalty xG
- **Domain models exist**: Player, Lineup (in match.py), Injury, Suspension (in availability.py)
- **Lineup data**: Lineup model has starting_xi (List[str] of player_ids), substitutes (List[str]), formation
- **No manager tracking**: Team model has NO manager field, no manager_events table

---

## 10F — Shot Intelligence (Implement First — Needed by 10F-1)

### Item 1: Create backend/app/features/shot_intelligence.py

**What**: Implement ShotIntelligenceMetrics dataclass and ShotIntelligenceCalculator that extracts shot volume/quality metrics from TeamMatchStatistic historical data.

**Files**:
- Create: `c:/FootballIntelligence/backend/app/features/shot_intelligence.py`

**Implementation Details**:
```python
@dataclass
class ShotIntelligenceMetrics:
    """Shot intelligence metrics extracted from TeamMatchStatistic.
    
    AVAILABLE fields from current TeamMatchStatistic:
    - shots_total, shots_on_target, shots_off_target, shots_blocked
    - xg, xg_against
    - possession_percentage
    
    UNAVAILABLE fields (remain None until provider integration):
    - shots_inside_box (requires shot coordinates)
    - box_shot_percentage (requires shot coordinates)
    - big_chances (requires provider classification)
    - non_penalty_xg (requires xG event-type separation)
    """
    team_id: str
    
    # Shot volume (AVAILABLE)
    shots_total_per_match: Optional[float] = None
    shots_on_target_per_match: Optional[float] = None
    shots_off_target_per_match: Optional[float] = None
    shots_blocked_per_match: Optional[float] = None
    
    # Home/away split (AVAILABLE)
    shots_home_per_match: Optional[float] = None
    shots_away_per_match: Optional[float] = None
    shots_on_target_home_per_match: Optional[float] = None
    shots_on_target_away_per_match: Optional[float] = None
    
    # Shot quality (AVAILABLE when both xg and shots exist)
    xg_per_shot: Optional[float] = None
    shot_on_target_rate: Optional[float] = None  # SOT / total shots
    
    # Shot suppression (defensive - AVAILABLE)
    shots_against_per_match: Optional[float] = None
    shots_on_target_against_per_match: Optional[float] = None
    
    # Shot dominance (AVAILABLE)
    shot_share: Optional[float] = None  # Team shots / (team + opponent shots)
    
    # UNAVAILABLE FIELDS (explicitly None)
    shots_inside_box_per_match: Optional[float] = None  # UNAVAILABLE
    box_shot_percentage: Optional[float] = None  # UNAVAILABLE
    big_chances_per_match: Optional[float] = None  # UNAVAILABLE
    non_penalty_xg_per_match: Optional[float] = None  # UNAVAILABLE
    
    # Provenance
    provider: Optional[str] = None
    provider_timestamp: Optional[datetime] = None
    sample_size: int = 0
    matches_with_shot_data: int = 0
    matches_with_xg: int = 0
    data_quality_score: float = 0.0
    window_type: str = "recent"

class ShotIntelligenceCalculator:
    """Calculate shot intelligence from historical match statistics.
    
    Reuses MatchWithStatistics from Group 1 (advanced_team_intelligence.py).
    Follows temporal validity patterns from Group 1.
    """
    
    def __init__(self, session, recent_window: int = 5, min_matches: int = 3):
        self.session = session
        self.recent_window = recent_window
        self.min_matches = min_matches
    
    def calculate_shot_metrics(
        self,
        team_id: str,
        matches_with_stats: List[MatchWithStatistics],
        window_type: str = "recent",
        before_datetime: Optional[datetime] = None
    ) -> ShotIntelligenceMetrics:
        """Calculate shot intelligence metrics from historical data.
        
        TEMPORAL VALIDITY: Uses strict < comparison with before_datetime.
        REUSES: MatchWithStatistics from advanced_team_intelligence.py
        PATTERN: Same structure as AdvancedTeamIntelligenceCalculator.calculate_advanced_metrics
        
        Algorithm:
        1. Filter to finished matches (match.status == FINISHED)
        2. Filter to matches STRICTLY before before_datetime (< comparison)
        3. Apply window size based on window_type
        4. For each match, extract TeamMatchStatistic for team_id
        5. Accumulate shot metrics where available:
           - shots_total, shots_on_target, shots_off_target, shots_blocked
           - xg (for xg_per_shot calculation)
           - shots against from opponent's statistics
        6. Calculate per-match averages
        7. Calculate home/away venue splits when sample sufficient
        8. Calculate derived metrics (xg_per_shot, shot_share, SOT rate)
        9. Mark UNAVAILABLE metrics as None
        10. Calculate data_quality_score
        11. Return ShotIntelligenceMetrics with provenance
        """
```

**Pattern to Follow**: Mirror `AdvancedTeamIntelligenceCalculator` structure:
- Same `_get_window_size()` helper
- Same `_calculate_metrics_from_matches()` pattern with accumulators
- Same `_calculate_venue_split()` for home/away separation
- Same `_calculate_data_quality()` scoring
- Same temporal validity: `if mws.match.scheduled_at < before_datetime`

**Verify**: 
```bash
cd c:/FootballIntelligence/backend
python -m pytest tests/features/test_shot_intelligence.py -v
```
Expected: New test file tests pass (create tests in Item 6).

---

### Item 2: Create backend/app/features/shot_production.py

**What**: Implement ShotProduction dataclass and ShotProductionCalculator that derives shot-market threshold probabilities using Poisson/Negative Binomial distributions.

**Files**:
- Create: `c:/FootballIntelligence/backend/app/features/shot_production.py`

**Implementation Details**:
```python
@dataclass
class ShotProduction:
    """Shot production distribution and threshold probabilities.
    
    Models shot volume as count distribution (Poisson or Negative Binomial).
    Calculates P(shots > T) for configurable thresholds.
    """
    team_id: str
    
    # Distribution parameters
    expected_shots_mean: Optional[float] = None  # μ
    expected_shots_variance: Optional[float] = None  # σ²
    distribution_model: str = "none"  # "poisson", "negative_binomial", "none"
    
    # Negative Binomial parameters (when overdispersed)
    nb_r: Optional[float] = None  # r = μ²/(σ²-μ)
    nb_p: Optional[float] = None  # p = μ/σ²
    
    # Poisson parameter (when equidispersed)
    poisson_lambda: Optional[float] = None  # λ = μ
    
    # Shot threshold probabilities P(X > T)
    over_10_shots_prob: Optional[float] = None
    over_12_shots_prob: Optional[float] = None
    over_15_shots_prob: Optional[float] = None
    over_18_shots_prob: Optional[float] = None
    over_20_shots_prob: Optional[float] = None
    
    # Shots on target threshold probabilities
    over_3_sot_prob: Optional[float] = None
    over_4_sot_prob: Optional[float] = None
    over_5_sot_prob: Optional[float] = None
    over_6_sot_prob: Optional[float] = None
    
    # Opponent adjustment
    opponent_adjusted: bool = False
    opponent_suppression_effect: Optional[float] = None
    
    # Provenance
    sample_size: int = 0
    data_quality_score: float = 0.0

class ShotProductionCalculator:
    """Calculate shot production probabilities using statistical distributions.
    
    Mathematical specification from design.md lines 1100-1250:
    - Distribution selection: variance > mean → NegBin, else Poisson
    - NegBin params: r = μ²/(σ²-μ), p = μ/σ²
    - Poisson param: λ = μ
    - Threshold probabilities: P(X > T) = 1 - CDF(T)
    """
    
    MIN_MATCHES_FOR_DISTRIBUTION = 5
    MIN_MATCHES_WITH_SHOT_DATA = 3
    SHOT_THRESHOLDS = [10, 12, 15, 18, 20]
    SOT_THRESHOLDS = [3, 4, 5, 6]
    
    def __init__(self, session, min_matches: int = 5):
        self.session = session
        self.min_matches = min_matches
    
    def calculate_shot_production(
        self,
        shot_intel: ShotIntelligenceMetrics,
        opponent_shot_intel: Optional[ShotIntelligenceMetrics] = None
    ) -> ShotProduction:
        """Calculate shot production distribution and threshold probabilities.
        
        Algorithm (design.md section 4.2.2):
        
        Step 1: Extract mean and variance from shot_intel
        Step 2: Select distribution
            if variance > mean: use Negative Binomial (overdispersed)
            else: use Poisson (equidispersed)
        Step 3: Parameterize distribution
            NegBin: r = μ²/(σ²-μ), p = μ/σ²
            Poisson: λ = μ
            Validate parameters (r > 0, 0 < p < 1, λ > 0)
        Step 4: Calculate threshold probabilities
            For each threshold T in [10, 12, 15, 18, 20]:
                P(X > T) = 1 - CDF(T; params)
            Use scipy.stats.nbinom.cdf or scipy.stats.poisson.cdf
        Step 5: Opponent adjustment (if opponent_shot_intel provided)
            μ_adjusted = μ_team + opponent_suppression_effect
            opponent_suppression_effect = (opponent_shots_allowed - league_avg)
            Recalculate threshold probabilities with μ_adjusted
        Step 6: Repeat for shots on target using SOT thresholds [3, 4, 5, 6]
        Step 7: Return ShotProduction with all probabilities and provenance
        
        Args:
            shot_intel: Team's shot intelligence metrics (from ShotIntelligenceCalculator)
            opponent_shot_intel: Opponent's shot suppression metrics (optional)
        
        Returns:
            ShotProduction with threshold probabilities or all None if insufficient data
        """
```

**Dependencies**: 
- `from scipy.stats import poisson, nbinom` for CDF calculations
- ShotIntelligenceMetrics from shot_intelligence.py

**Edge Cases**:
```python
# Case 1: Insufficient sample
if shot_intel.matches_with_shot_data < MIN_MATCHES_WITH_SHOT_DATA:
    return ShotProduction(team_id=shot_intel.team_id, distribution_model="none")

# Case 2: Mean ≤ 0
if expected_shots_mean <= 0:
    return ShotProduction(team_id=shot_intel.team_id, distribution_model="none")

# Case 3: Variance ≤ 0
if expected_shots_variance <= 0:
    return ShotProduction(team_id=shot_intel.team_id, distribution_model="none")

# Case 4: Invalid NegBin parameters
if distribution == "negative_binomial" and (r <= 0 or p <= 0 or p >= 1):
    return ShotProduction(team_id=shot_intel.team_id, distribution_model="none")
```

**Verify**: 
```bash
cd c:/FootballIntelligence/backend
python -m pytest tests/features/test_shot_production.py -v
```
Expected: Distribution selection, parameter calculation, threshold probability tests pass.

---

## 10D — Lineup Intelligence

### Item 3: Create backend/app/features/lineup_intelligence.py

**What**: Implement player availability status tracking and lineup impact estimation using with/without player methodology.

**Files**:
- Create: `c:/FootballIntelligence/backend/app/features/lineup_intelligence.py`

**Implementation Details**:
```python
from enum import Enum
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Tuple, Any
from datetime import datetime

class PlayerAvailabilityStatus(str, Enum):
    """Player availability status for a match."""
    CONFIRMED_STARTING = "confirmed_starting"  # In confirmed starting XI
    CONFIRMED_SUBSTITUTE = "confirmed_substitute"  # In confirmed substitutes
    EXPECTED_STARTING = "expected_starting"  # Expected to start (lineup not confirmed)
    EXPECTED_SUBSTITUTE = "expected_substitute"  # Expected on bench
    INJURED = "injured"  # Out due to injury
    SUSPENDED = "suspended"  # Out due to suspension
    UNAVAILABLE = "unavailable"  # Out for other reasons
    UNKNOWN = "unknown"  # Status unknown

@dataclass
class PlayerAvailability:
    """Player availability information for a team."""
    team_id: str
    
    # Lineup confirmation status
    lineup_status: str = "unknown"  # "confirmed", "expected", "unknown"
    
    # Player lists
    confirmed_starting_xi: List[str] = field(default_factory=list)  # player_ids
    confirmed_substitutes: List[str] = field(default_factory=list)
    expected_absences: List[str] = field(default_factory=list)  # player_ids unavailable
    
    # Detailed availability by player_id
    player_statuses: Dict[str, PlayerAvailabilityStatus] = field(default_factory=dict)
    
    # Injury/suspension details
    injuries: List[Dict[str, Any]] = field(default_factory=list)  # From Injury model
    suspensions: List[Dict[str, Any]] = field(default_factory=list)  # From Suspension model
    
    # Provenance
    provider: Optional[str] = None
    last_updated: Optional[datetime] = None

@dataclass
class LineupImpactEstimate:
    """Statistical estimate of lineup changes impact.
    
    CRITICAL: NEVER fabricate impact if insufficient data.
    Uses with/without player methodology from historical matches.
    """
    team_id: str
    
    # Lineup status
    lineup_availability: PlayerAvailability = field(default_factory=lambda: PlayerAvailability(team_id=""))
    
    # Estimated impact (None if cannot estimate from data)
    estimated_attack_impact: Optional[float] = None  # -1.0 to +1.0, negative = weakened
    estimated_defense_impact: Optional[float] = None
    estimated_shot_impact: Optional[float] = None
    estimated_xg_impact: Optional[float] = None
    
    # Per-player impact breakdown (when calculable)
    player_impacts: Dict[str, Dict[str, Optional[float]]] = field(default_factory=dict)
    # Structure: {player_id: {"attack_impact": 0.2, "defense_impact": -0.1, ...}}
    
    # Confidence in estimates
    impact_confidence: float = 0.0  # 0.0-1.0
    
    # Methodology
    impact_method: str = "unavailable"  # "unavailable", "with_without_statistical", "insufficient_sample"
    sample_sizes: Dict[str, Tuple[int, int]] = field(default_factory=dict)
    # Structure: {player_id: (n_with, n_without)}
    
    # Provenance
    provider: Optional[str] = None

class LineupIntelligenceCalculator:
    """Calculate lineup impact using with/without player statistical methodology.
    
    CRITICAL DATA REQUIREMENT: Requires historical lineup data (Lineup.starting_xi).
    If lineup data unavailable, all impact estimates = None.
    """
    
    MIN_WITH_PLAYER = 3  # Minimum matches WITH player for reliable estimate
    MIN_WITHOUT_PLAYER = 3  # Minimum matches WITHOUT player for reliable estimate
    
    def __init__(
        self,
        session,
        min_with_player: int = 3,
        min_without_player: int = 3
    ):
        self.session = session
        self.min_with_player = min_with_player
        self.min_without_player = min_without_player
    
    def calculate_lineup_impact(
        self,
        team_id: str,
        player_availability: PlayerAvailability,
        matches_with_stats: List[MatchWithStatistics],
        before_datetime: Optional[datetime] = None
    ) -> LineupImpactEstimate:
        """Calculate lineup impact using with/without player methodology.
        
        CRITICAL: NEVER fabricate impact percentages.
        Only estimate impact when sufficient historical with/without samples exist.
        
        Algorithm (design.md section 4.2.3):
        
        1. Check if any key players unavailable
        2. For each absent player:
           a. Split historical matches into WITH/WITHOUT player using lineup data
           b. Calculate performance differential:
              - Goals/match WITH vs WITHOUT
              - xG/match WITH vs WITHOUT
              - Shots/match WITH vs WITHOUT
              - Points/match WITH vs WITHOUT
           c. Validate sample sizes (n_with >= 3, n_without >= 3)
           d. Calculate impact = performance_with - performance_without
           e. Calculate confidence based on sample sizes and balance
        3. Aggregate multiple player absences (sum impacts)
        4. Return LineupImpactEstimate with statistically-derived impacts or None
        
        Missing Data Handling:
        - If no historical lineup data exists → all impacts = None, method = "unavailable"
        - If insufficient with/without samples → all impacts = None, method = "insufficient_sample"
        - If player has never been absent → impact = None for that player
        - Never use hardcoded penalty values (e.g., "key player = -15%")
        
        Args:
            team_id: Team database ID
            player_availability: Player availability with absence reasons
            matches_with_stats: Historical matches WITH lineup data (Lineup.starting_xi)
            before_datetime: Only use matches before this timestamp (temporal validity)
        
        Returns:
            LineupImpactEstimate with calculated impacts or None where unavailable
        """
    
    def _split_matches_by_player(
        self,
        team_id: str,
        player_id: str,
        matches_with_stats: List[MatchWithStatistics]
    ) -> Tuple[List[MatchWithStatistics], List[MatchWithStatistics]]:
        """Split matches into WITH and WITHOUT player.
        
        REQUIRES: Lineup data in Match (match.lineup with starting_xi field).
        
        Algorithm:
        1. For each match in matches_with_stats:
           a. Fetch Lineup for team_id for that match_id from session
           b. Check if player_id in Lineup.starting_xi
           c. Add to WITH list if player started, WITHOUT list otherwise
        2. Return (matches_with_player, matches_without_player)
        
        Returns:
            (matches_with_player, matches_without_player)
        """
    
    def _calculate_player_impact(
        self,
        team_id: str,
        player_id: str,
        matches_with: List[MatchWithStatistics],
        matches_without: List[MatchWithStatistics]
    ) -> Dict[str, Optional[float]]:
        """Calculate player impact from with/without samples.
        
        Returns:
            Dictionary with impact metrics or None if insufficient sample
        """
```

**CRITICAL LIMITATION**: If the repository does NOT have historical Lineup.starting_xi data populated, this calculator will return `impact_method="unavailable"` and all impact fields = None. This is CORRECT behavior per design (REAL DATA > NULL > FABRICATED).

**Verify**: 
```bash
cd c:/FootballIntelligence/backend
python -m pytest tests/features/test_lineup_intelligence.py -v
```
Expected: Tests for with/without split, impact calculation, insufficient sample handling.

---

## 10E — Tactical Matchup Intelligence

### Item 4: Create backend/app/features/tactical_matchup.py

**What**: Implement tactical profile extraction and matchup advantage calculation using ONLY AVAILABLE metrics from TeamMatchStatistic.

**Files**:
- Create: `c:/FootballIntelligence/backend/app/features/tactical_matchup.py`

**Implementation Details**:
```python
@dataclass
class TacticalProfile:
    """Team tactical profile from available TeamMatchStatistic metrics.
    
    AVAILABLE metrics:
    - possession_percentage
    - shots_total, shots_on_target
    - passes_completed, passes_attempted
    - tackles, interceptions, clearances
    
    UNAVAILABLE metrics (remain None):
    - PPDA (no defensive action tracking)
    - Field Tilt (no territorial zone data)
    - progressive passes (no progression tracking)
    - box entries (no zone tracking)
    - high turnovers (no possession-recovery zone tracking)
    """
    team_id: str
    
    # Possession & control (AVAILABLE)
    possession_avg: Optional[float] = None
    pass_completion_rate: Optional[float] = None  # passes_completed / passes_attempted
    
    # Attacking (AVAILABLE)
    shots_per_match: Optional[float] = None
    shots_on_target_per_match: Optional[float] = None
    shot_accuracy: Optional[float] = None  # SOT / total shots
    
    # Defensive (AVAILABLE)
    tackles_per_match: Optional[float] = None
    interceptions_per_match: Optional[float] = None
    clearances_per_match: Optional[float] = None
    
    # UNAVAILABLE FIELDS (explicitly None until provider integration)
    ppda: Optional[float] = None  # UNAVAILABLE
    field_tilt: Optional[float] = None  # UNAVAILABLE
    progressive_passes_per_match: Optional[float] = None  # UNAVAILABLE
    box_entries_per_match: Optional[float] = None  # UNAVAILABLE
    high_turnovers_per_match: Optional[float] = None  # UNAVAILABLE
    
    # Provenance
    sample_size: int = 0
    data_quality_score: float = 0.0

@dataclass
class TacticalMatchupAdvantage:
    """Tactical matchup advantage between two teams.
    
    Quantifies interaction between team A's strengths and team B's weaknesses.
    All advantages bounded [-1.0, 1.0], positive favors home team.
    """
    home_team_id: str
    away_team_id: str
    
    # Matchup advantages (bounded -1 to +1)
    possession_advantage: Optional[float] = None  # Home possession style vs Away
    shot_volume_advantage: Optional[float] = None  # Home shot creation vs Away shot suppression
    shot_quality_advantage: Optional[float] = None  # Home shot accuracy vs Away
    defensive_solidity_advantage: Optional[float] = None  # Home defense vs Away attack
    
    # Overall matchup score (weighted combination)
    overall_matchup_advantage: Optional[float] = None  # -1 to +1, 0 = neutral
    
    # Provenance
    data_quality_score: float = 0.0

class TacticalMatchupCalculator:
    """Calculate tactical matchup advantages using AVAILABLE metrics only.
    
    Reuses MatchWithStatistics from Group 1.
    Calculates advantage scores as normalized differentials.
    """
    
    def __init__(self, session, min_matches: int = 5):
        self.session = session
        self.min_matches = min_matches
    
    def calculate_tactical_profile(
        self,
        team_id: str,
        matches_with_stats: List[MatchWithStatistics],
        before_datetime: Optional[datetime] = None
    ) -> TacticalProfile:
        """Extract tactical profile from historical matches.
        
        PATTERN: Same structure as AdvancedTeamIntelligenceCalculator.
        AVAILABLE METRICS ONLY: No PPDA, Field Tilt, progressive passes, box entries.
        
        Algorithm:
        1. Filter finished matches before before_datetime
        2. For each match, extract TeamMatchStatistic for team_id
        3. Accumulate AVAILABLE metrics:
           - possession_percentage
           - shots_total, shots_on_target
           - passes_completed, passes_attempted
           - tackles, interceptions, clearances
        4. Calculate per-match averages
        5. Calculate derived metrics (pass_completion_rate, shot_accuracy)
        6. Leave UNAVAILABLE metrics as None
        7. Return TacticalProfile with provenance
        """
    
    def calculate_matchup_advantage(
        self,
        home_profile: TacticalProfile,
        away_profile: TacticalProfile
    ) -> TacticalMatchupAdvantage:
        """Calculate tactical matchup advantage between two teams.
        
        Advantage calculation (bounded -1 to +1):
        
        possession_advantage = normalize(
            home_profile.possession_avg - away_profile.possession_avg,
            scale=20.0  # 20 percentage points difference → ±1.0
        )
        
        shot_volume_advantage = normalize(
            home_profile.shots_per_match - away_profile.shots_per_match,
            scale=10.0  # 10 shots difference → ±1.0
        )
        
        shot_quality_advantage = normalize(
            home_profile.shot_accuracy - away_profile.shot_accuracy,
            scale=0.3  # 30 percentage points difference → ±1.0
        )
        
        defensive_solidity_advantage = normalize(
            away_profile.tackles_per_match - home_profile.tackles_per_match,
            scale=5.0  # Inverted: more away tackles = home advantage in possession
        )
        
        overall_matchup_advantage = weighted_average([
            (possession_advantage, 0.25),
            (shot_volume_advantage, 0.35),
            (shot_quality_advantage, 0.25),
            (defensive_solidity_advantage, 0.15)
        ])
        
        Algorithm:
        1. Calculate individual advantage scores from profile differentials
        2. Normalize to [-1, 1] range using configurable scales
        3. Calculate weighted overall advantage
        4. Return TacticalMatchupAdvantage
        
        Args:
            home_profile: Home team tactical profile
            away_profile: Away team tactical profile
        
        Returns:
            TacticalMatchupAdvantage with calculated scores
        """
    
    def _normalize_advantage(
        self,
        differential: float,
        scale: float
    ) -> float:
        """Normalize differential to [-1, 1] range.
        
        Uses tanh-like bounded normalization:
        advantage = tanh(differential / scale)
        
        Returns value in [-1.0, 1.0].
        """
```

**Key Design Decision**: Since PPDA, Field Tilt, progressive passes, box entries are UNAVAILABLE from current TeamMatchStatistic, the tactical profile uses ONLY AVAILABLE metrics (possession, shots, passes, tackles/interceptions/clearances). This provides a LIMITED but REAL tactical profile vs fabricating unavailable metrics.

**Verify**: 
```bash
cd c:/FootballIntelligence/backend
python -m pytest tests/features/test_tactical_matchup.py -v
```
Expected: Tactical profile extraction, matchup advantage calculation, bounded output tests.

---

## Integration & Export

### Item 5: Update backend/app/features/__init__.py to export Group 2 modules

**What**: Add Group 2 classes to features module exports.

**Files**:
- Modify: `c:/FootballIntelligence/backend/app/features/__init__.py`

**Changes**:
```python
# Add imports
from app.features.shot_intelligence import (
    ShotIntelligenceMetrics,
    ShotIntelligenceCalculator,
)
from app.features.shot_production import (
    ShotProduction,
    ShotProductionCalculator,
)
from app.features.lineup_intelligence import (
    PlayerAvailabilityStatus,
    PlayerAvailability,
    LineupImpactEstimate,
    LineupIntelligenceCalculator,
)
from app.features.tactical_matchup import (
    TacticalProfile,
    TacticalMatchupAdvantage,
    TacticalMatchupCalculator,
)

# Add to __all__
__all__ = [
    # ... existing exports ...
    # Shot Intelligence (Phase 10 Group 2)
    "ShotIntelligenceMetrics",
    "ShotIntelligenceCalculator",
    "ShotProduction",
    "ShotProductionCalculator",
    # Lineup Intelligence (Phase 10 Group 2)
    "PlayerAvailabilityStatus",
    "PlayerAvailability",
    "LineupImpactEstimate",
    "LineupIntelligenceCalculator",
    # Tactical Matchup (Phase 10 Group 2)
    "TacticalProfile",
    "TacticalMatchupAdvantage",
    "TacticalMatchupCalculator",
]
```

**Verify**: 
```bash
cd c:/FootballIntelligence/backend
python -c "from app.features import ShotIntelligenceCalculator, ShotProductionCalculator, LineupIntelligenceCalculator, TacticalMatchupCalculator; print('All imports successful')"
```
Expected: "All imports successful" with no import errors.

---

## Testing

### Item 6: Create test_shot_intelligence.py

**What**: Unit tests for shot intelligence calculator covering data availability, temporal validity, home/away splits.

**Files**:
- Create: `c:/FootballIntelligence/backend/tests/features/test_shot_intelligence.py`

**Test Coverage**:
```python
"""Tests for shot intelligence calculator."""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock

from app.features.shot_intelligence import (
    ShotIntelligenceMetrics,
    ShotIntelligenceCalculator,
)
from app.features.advanced_team_intelligence import MatchWithStatistics
# ... use same test helpers as test_advanced_team_intelligence.py

class TestShotIntelligenceCalculator:
    def test_calculate_shot_metrics_with_full_data(self):
        """Test shot metrics calculation with complete shot data."""
    
    def test_calculate_shot_metrics_with_missing_xg(self):
        """Test shot metrics when xg unavailable (xg_per_shot should be None)."""
    
    def test_calculate_shot_metrics_with_no_shot_data(self):
        """Test shot metrics when no matches have shot data (all None)."""
    
    def test_home_away_venue_split(self):
        """Test home/away shot separation."""
    
    def test_temporal_validity_before_datetime(self):
        """Test that calculator respects before_datetime filter."""
    
    def test_shot_share_calculation(self):
        """Test shot dominance calculation (team shots / total shots in match)."""
    
    def test_data_quality_score(self):
        """Test data quality scoring based on shot data completeness."""
    
    def test_insufficient_sample_size(self):
        """Test behavior when matches < min_matches."""
    
    def test_coordinate_metrics_unavailable(self):
        """Test that box_shot_percentage, shots_inside_box remain None."""
```

**Pattern**: Follow test_advanced_team_intelligence.py structure with same test helpers.

**Verify**: 
```bash
cd c:/FootballIntelligence/backend
python -m pytest tests/features/test_shot_intelligence.py -v
```
Expected: All shot intelligence tests pass.

---

### Item 7: Create test_shot_production.py

**What**: Unit tests for shot production calculator covering distribution selection, parameter calculation, threshold probabilities.

**Files**:
- Create: `c:/FootballIntelligence/backend/tests/features/test_shot_production.py`

**Test Coverage**:
```python
"""Tests for shot production calculator."""

import pytest
from unittest.mock import Mock
import numpy as np

from app.features.shot_production import (
    ShotProduction,
    ShotProductionCalculator,
)
from app.features.shot_intelligence import ShotIntelligenceMetrics

class TestShotProductionCalculator:
    def test_poisson_distribution_selection(self):
        """Test Poisson selected when variance ≤ mean."""
    
    def test_negative_binomial_distribution_selection(self):
        """Test Negative Binomial selected when variance > mean."""
    
    def test_negative_binomial_parameter_calculation(self):
        """Test NegBin r and p parameter calculation."""
    
    def test_threshold_probability_calculation_poisson(self):
        """Test P(X > T) calculation for Poisson distribution."""
    
    def test_threshold_probability_calculation_negbin(self):
        """Test P(X > T) calculation for Negative Binomial distribution."""
    
    def test_opponent_adjustment(self):
        """Test opponent suppression effect adjustment."""
    
    def test_insufficient_sample(self):
        """Test behavior when matches_with_shot_data < MIN_MATCHES."""
    
    def test_invalid_parameters(self):
        """Test handling of invalid distribution parameters (r≤0, p≤0, p≥1)."""
    
    def test_shots_on_target_thresholds(self):
        """Test SOT threshold probability calculation."""
    
    def test_edge_case_mean_zero(self):
        """Test edge case when mean = 0."""
    
    def test_edge_case_variance_zero(self):
        """Test edge case when variance = 0."""
```

**Verify**: 
```bash
cd c:/FootballIntelligence/backend
python -m pytest tests/features/test_shot_production.py -v
```
Expected: All shot production tests pass.

---

### Item 8: Create test_lineup_intelligence.py

**What**: Unit tests for lineup intelligence calculator covering with/without player splits, impact estimation, insufficient sample handling.

**Files**:
- Create: `c:/FootballIntelligence/backend/tests/features/test_lineup_intelligence.py`

**Test Coverage**:
```python
"""Tests for lineup intelligence calculator."""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, MagicMock

from app.features.lineup_intelligence import (
    PlayerAvailabilityStatus,
    PlayerAvailability,
    LineupImpactEstimate,
    LineupIntelligenceCalculator,
)

class TestLineupIntelligenceCalculator:
    def test_split_matches_by_player_with_lineup_data(self):
        """Test splitting matches into WITH/WITHOUT player using lineup data."""
    
    def test_split_matches_no_lineup_data(self):
        """Test behavior when lineup data unavailable (method='unavailable')."""
    
    def test_calculate_player_impact_sufficient_sample(self):
        """Test player impact calculation with sufficient with/without samples."""
    
    def test_calculate_player_impact_insufficient_sample(self):
        """Test that impact=None when n_with < 3 or n_without < 3."""
    
    def test_aggregate_multiple_player_absences(self):
        """Test aggregation of multiple absent players' impacts."""
    
    def test_no_fabricated_impact(self):
        """Test that impact is NOT fabricated when data insufficient."""
    
    def test_confidence_calculation(self):
        """Test confidence score based on sample sizes and balance."""
    
    def test_temporal_validity(self):
        """Test that calculator respects before_datetime."""
    
    def test_player_never_absent(self):
        """Test that impact=None when player has never been absent."""
```

**CRITICAL TEST**: `test_no_fabricated_impact` must verify that when lineup data is insufficient, the calculator returns `impact_method="unavailable"` or `"insufficient_sample"` with all impact fields = None, NEVER hardcoded percentages.

**Verify**: 
```bash
cd c:/FootballIntelligence/backend
python -m pytest tests/features/test_lineup_intelligence.py -v
```
Expected: All lineup intelligence tests pass.

---

### Item 9: Create test_tactical_matchup.py

**What**: Unit tests for tactical matchup calculator covering profile extraction, advantage calculation, bounded outputs.

**Files**:
- Create: `c:/FootballIntelligence/backend/tests/features/test_tactical_matchup.py`

**Test Coverage**:
```python
"""Tests for tactical matchup calculator."""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock

from app.features.tactical_matchup import (
    TacticalProfile,
    TacticalMatchupAdvantage,
    TacticalMatchupCalculator,
)

class TestTacticalMatchupCalculator:
    def test_calculate_tactical_profile(self):
        """Test tactical profile extraction from available metrics."""
    
    def test_unavailable_metrics_remain_none(self):
        """Test that PPDA, Field Tilt, progressive passes remain None."""
    
    def test_calculate_matchup_advantage(self):
        """Test matchup advantage calculation from profiles."""
    
    def test_advantage_bounded_output(self):
        """Test that all advantage scores bounded to [-1, 1]."""
    
    def test_possession_advantage_calculation(self):
        """Test possession advantage normalization."""
    
    def test_shot_volume_advantage_calculation(self):
        """Test shot volume advantage normalization."""
    
    def test_overall_matchup_advantage_weighting(self):
        """Test weighted combination for overall advantage."""
    
    def test_temporal_validity(self):
        """Test that calculator respects before_datetime."""
    
    def test_insufficient_sample(self):
        """Test behavior when matches < min_matches."""
```

**Verify**: 
```bash
cd c:/FootballIntelligence/backend
python -m pytest tests/features/test_tactical_matchup.py -v
```
Expected: All tactical matchup tests pass.

---

### Item 10: Create test_group2_temporal_leakage.py

**What**: Cross-calculator temporal leakage verification for Group 2 calculators.

**Files**:
- Create: `c:/FootballIntelligence/backend/tests/features/test_group2_temporal_leakage.py`

**Test Coverage**:
```python
"""Cross-calculator temporal leakage verification for Phase 10 Group 2.

Verifies that ALL Group 2 calculators respect temporal validity:
- ShotIntelligenceCalculator (10F)
- ShotProductionCalculator (10F-1)
- LineupIntelligenceCalculator (10D)
- TacticalMatchupCalculator (10E)

CRITICAL: All calculators must use strict < comparison for before_datetime.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock

# ... import all Group 2 calculators

def test_shot_intelligence_respects_before_datetime():
    """Test ShotIntelligenceCalculator excludes matches at/after cutoff."""

def test_shot_production_uses_temporal_shot_intel():
    """Test ShotProductionCalculator uses temporally-valid shot intelligence."""

def test_lineup_intelligence_respects_before_datetime():
    """Test LineupIntelligenceCalculator excludes matches at/after cutoff."""

def test_tactical_matchup_respects_before_datetime():
    """Test TacticalMatchupCalculator excludes matches at/after cutoff."""

def test_all_group2_calculators_use_strict_less_than():
    """Test that ALL Group 2 calculators use < (not <=) for before_datetime."""
```

**Pattern**: Follow test_temporal_leakage.py from Group 1.

**Verify**: 
```bash
cd c:/FootballIntelligence/backend
python -m pytest tests/features/test_group2_temporal_leakage.py -v
```
Expected: All temporal leakage tests pass.

---

## Final Verification

### Item 11: Run full Group 2 test suite

**What**: Execute all Group 2 tests to verify complete implementation.

**Commands**:
```bash
cd c:/FootballIntelligence/backend
python -m pytest tests/features/test_shot_intelligence.py tests/features/test_shot_production.py tests/features/test_lineup_intelligence.py tests/features/test_tactical_matchup.py tests/features/test_group2_temporal_leakage.py -v
```

**Expected Output**:
- All tests pass (no failures, no errors)
- Temporal leakage tests verify strict < comparison
- Data integrity tests verify no fabricated metrics
- Insufficient sample tests verify None returns

**If Failures**: Fix the reported failures, re-run tests, iterate until all pass.

---

### Item 12: Run regression check against Group 1

**What**: Verify that Group 2 implementation does not break Group 1 functionality.

**Commands**:
```bash
cd c:/FootballIntelligence/backend
python -m pytest tests/features/test_advanced_team_intelligence.py tests/features/test_opponent_adjustment.py tests/features/test_temporal_intelligence.py tests/features/test_temporal_leakage.py -v
```

**Expected Output**:
- All Group 1 tests still pass (53/53 from commit 72d18af)
- No regressions introduced by Group 2 modules

**If Failures**: Investigate whether Group 2 changes broke Group 1 code. Fix and re-run.

---

### Item 13: Verify Python imports and module structure

**What**: Confirm all Group 2 modules are importable and properly structured.

**Commands**:
```bash
cd c:/FootballIntelligence/backend
python -c "from app.features import ShotIntelligenceCalculator, ShotProductionCalculator, LineupIntelligenceCalculator, TacticalMatchupCalculator; print('✓ All Group 2 modules importable')"

python -c "from app.features.shot_intelligence import ShotIntelligenceMetrics; from app.features.shot_production import ShotProduction; from app.features.lineup_intelligence import LineupImpactEstimate; from app.features.tactical_matchup import TacticalMatchupAdvantage; print('✓ All Group 2 dataclasses importable')"
```

**Expected Output**:
- "✓ All Group 2 modules importable"
- "✓ All Group 2 dataclasses importable"
- No ImportError exceptions

---

## Implementation Notes

### Data Integrity Rules (From AGENTS.md)

1. **REAL DATA > NULL/UNAVAILABLE > FABRICATED DATA** — never invent xG, odds, player stats, injuries, lineups, coordinates, PPDA, Field Tilt, progressive passes, box entries, shot locations
2. **Temporal Validity** — use strict `<` comparison with before_datetime, never `<=`
3. **No Silent Fallbacks** — never replace missing data with zero/league-average/estimated values
4. **Explicit Unavailability** — use `Optional[float] = None`, never `= 0.0` for missing data
5. **Provenance Tracking** — every metric includes provider, timestamp, sample_size, data_quality_score

### Reuse from Group 1

- **MatchWithStatistics**: Reuse from advanced_team_intelligence.py (do NOT duplicate)
- **Temporal patterns**: Follow TemporalIntelligenceCalculator strict `<` comparison
- **Window sizing**: Reuse `_get_window_size()` helper pattern
- **Data quality**: Reuse `_calculate_data_quality()` scoring pattern
- **Test helpers**: Reuse `create_match()`, `create_team_stats()` from existing test files

### Dependencies

- **scipy**: Required for `scipy.stats.poisson` and `scipy.stats.nbinom` in shot_production.py
- **numpy**: May be needed for statistical calculations
- Check if scipy is in requirements.txt, add if missing

### Post-Implementation

After all items complete and verified:
1. Update `docs/PROGRESS.md` with Group 2 completion summary
2. Commit locally on branch: `git add . && git commit -m "feat: Phase 10 Group 2 - Shot/Lineup/Tactical Intelligence"`
3. Do NOT push (merge step handles push)

---

## Summary

**Modules Created**:
- `backend/app/features/shot_intelligence.py` (10F)
- `backend/app/features/shot_production.py` (10F-1)
- `backend/app/features/lineup_intelligence.py` (10D)
- `backend/app/features/tactical_matchup.py` (10E)

**Tests Created**:
- `backend/tests/features/test_shot_intelligence.py`
- `backend/tests/features/test_shot_production.py`
- `backend/tests/features/test_lineup_intelligence.py`
- `backend/tests/features/test_tactical_matchup.py`
- `backend/tests/features/test_group2_temporal_leakage.py`

**Integration**:
- Updated `backend/app/features/__init__.py` with Group 2 exports

**Verification**:
- All Group 2 tests pass
- No Group 1 regressions
- Temporal leakage prevention verified
- Data integrity rules enforced (no fabricated metrics)
- All UNAVAILABLE metrics explicitly None

**Ready for**: Group 3 (Common Opponent Intelligence) after Group 2 merge.

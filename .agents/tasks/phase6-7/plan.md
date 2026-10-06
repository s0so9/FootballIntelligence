# Implementation Plan: Phase 6 & 7 — Result Ingestion, Settlement & Track Record

This plan implements result ingestion, prediction settlement, and track record functionality for the MENSIONE football intelligence platform.

## Architecture Decisions

### 1. Database Schema Extensions

**Decision: Extend PredictionVersionDB with frozen pick and settlement columns**
- Rationale: PredictionVersion dataclass already has these fields, but PredictionVersionDB ORM model lacks them. Adding columns ensures frozen pick integrity is persisted.

**Decision: Do NOT create separate SettlementDB table**
- Rationale: Settlement data (actual_result, profit_loss, settled_at) logically belongs on the prediction version itself. TrackRecordDB already exists for aggregated metrics.

**Columns to add to `prediction_versions` table:**
```sql
-- Frozen pick fields (immutable after creation)
selected_market VARCHAR(50) NULL
selection_text VARCHAR(200) NULL  
selection_probability FLOAT NULL
selection_confidence FLOAT NULL
selection_odds FLOAT NULL
selection_fair_odds FLOAT NULL
selection_edge FLOAT NULL
value_classification VARCHAR(50) NULL
risk_level VARCHAR(50) NULL

-- Settlement fields (populated after match finishes)
actual_result VARCHAR(20) NULL  -- 'WIN', 'LOSS', 'VOID'
profit_loss FLOAT NULL
settled_at TIMESTAMP WITH TIME ZONE NULL
```

### 2. Settlement Logic Architecture

**Decision: Implement SettlementEngine as separate service class**
- Rationale: Separation of concerns. PredictionVersionManager handles versioning; SettlementEngine handles outcome determination.
- Location: `backend/app/prediction/settlement.py`

**Decision: Implement ResultIngestionService as separate service**
- Rationale: Result fetching is distinct from settlement logic. Service coordinates provider calls and caching.
- Location: `backend/app/prediction/result_ingestion.py`

### 3. Market Settlement Rules

**MATCH_RESULT (1X2):**
- Determine actual outcome from (home_score, away_score): home_win / draw / away_win
- Compare with selection_text from frozen pick
- WIN if match, LOSS if not match

**OVER_UNDER:**
- Extract line from selected_market (e.g., "OVER_2_5" → line=2.5, selection="OVER")
- Calculate total_goals = home_score + away_score
- If selection=="OVER": WIN if total_goals > line, LOSS if total_goals < line, VOID if total_goals == line (push)
- If selection=="UNDER": WIN if total_goals < line, LOSS if total_goals > line, VOID if total_goals == line

**BTTS:**
- Check if both teams scored: btts_actual = (home_score > 0 and away_score > 0)
- If selection=="BTTS_YES": WIN if btts_actual, LOSS otherwise
- If selection=="BTTS_NO": WIN if not btts_actual, LOSS otherwise

**DOUBLE_CHANCE:**
- Parse selection from selection_text: "1X" | "12" | "X2"
- "1X": WIN if home_win OR draw
- "12": WIN if home_win OR away_win
- "X2": WIN if draw OR away_win

**HANDICAP:**
- Extract handicap from selected_market (e.g., "HANDICAP_-1.5_HOME")
- Apply handicap to home score: adjusted_home = home_score + handicap
- Compare adjusted_home with away_score to determine outcome
- Handle Asian handicap push scenarios (quarter-ball handicaps not in Phase 6 scope)

**Unsupported markets:**
- CORRECT_SCORE, TEAM_GOALS, TOTAL_GOALS, CORNERS, CARDS, PLAYER_MARKET
- Action: Raise ValueError with clear message indicating market settlement not yet implemented

### 4. Profit/Loss Calculation

**WIN:**
```python
profit_loss = (selection_odds - 1.0) * stake
```
Where stake = 1.0 unit (configurable in future)

**LOSS:**
```python
profit_loss = -1.0 * stake
```

**VOID:**
```python
profit_loss = 0.0
```

### 5. Track Record Integration

**Decision: Extend TrackRecordManager, do NOT modify TrackRecordDB schema**
- Rationale: TrackRecordDB currently stores 1X2 probability metrics. Settlement data lives on PredictionVersionDB. TrackRecordManager aggregates across both.

**New TrackRecordManager methods:**
- `get_settled_predictions(filters)` — query settled PredictionVersionDB records
- `calculate_market_performance(market_type)` — aggregate win rate, ROI, P/L by market
- `get_track_record_summary()` — overall metrics including settlement outcomes

### 6. API Endpoints

**New endpoints following existing `/api/v1/` pattern:**

```
GET /api/v1/predictions/history
- Query params: match_id?, stage?, from_date?, to_date?, limit?, offset?
- Returns: paginated list of prediction versions (both settled and unsettled)

GET /api/v1/predictions/settled
- Query params: market?, from_date?, to_date?, actual_result?, limit?, offset?
- Returns: paginated list of ONLY settled predictions with frozen pick + outcome

GET /api/v1/track-record/summary
- Query params: from_date?, to_date?, stage?
- Returns: aggregate metrics (total, wins, losses, voids, win_rate, roi, profit_loss, avg_odds, avg_confidence)

GET /api/v1/track-record/by-market
- Query params: market?, from_date?, to_date?
- Returns: per-market breakdown (market_type, sample_size, win_rate, roi, total_pl, avg_odds, avg_confidence)
```

### 7. Frontend TypeScript Types

**Location:** `frontend/src/types/predictions.ts`

Add types:
- `SettledPrediction` — frozen pick + settlement outcome
- `TrackRecordSummary` — aggregate metrics
- `MarketPerformance` — per-market metrics

**NO visual component changes, NO redesign**

---

## Implementation Steps

### Step 1: Database Migration for Frozen Pick & Settlement Fields

**What:** Create Alembic migration adding frozen pick and settlement columns to `prediction_versions` table.

**Files:**
- Create: `c:\FootballIntelligence\backend\alembic\versions\<revision>_add_frozen_pick_settlement_fields.py`

**Migration content:**
```python
def upgrade():
    # Add frozen pick columns
    op.add_column('prediction_versions', sa.Column('selected_market', sa.String(50), nullable=True))
    op.add_column('prediction_versions', sa.Column('selection_text', sa.String(200), nullable=True))
    op.add_column('prediction_versions', sa.Column('selection_probability', sa.Float(), nullable=True))
    op.add_column('prediction_versions', sa.Column('selection_confidence', sa.Float(), nullable=True))
    op.add_column('prediction_versions', sa.Column('selection_odds', sa.Float(), nullable=True))
    op.add_column('prediction_versions', sa.Column('selection_fair_odds', sa.Float(), nullable=True))
    op.add_column('prediction_versions', sa.Column('selection_edge', sa.Float(), nullable=True))
    op.add_column('prediction_versions', sa.Column('value_classification', sa.String(50), nullable=True))
    op.add_column('prediction_versions', sa.Column('risk_level', sa.String(50), nullable=True))
    
    # Add settlement columns
    op.add_column('prediction_versions', sa.Column('actual_result', sa.String(20), nullable=True))
    op.add_column('prediction_versions', sa.Column('profit_loss', sa.Float(), nullable=True))
    op.add_column('prediction_versions', sa.Column('settled_at', sa.DateTime(timezone=True), nullable=True))
    
    # Create index on actual_result for filtering
    op.create_index('ix_prediction_version_actual_result', 'prediction_versions', ['actual_result'])
    
    # Create index on settled_at for date filtering
    op.create_index('ix_prediction_version_settled_at', 'prediction_versions', ['settled_at'])

def downgrade():
    op.drop_index('ix_prediction_version_settled_at', 'prediction_versions')
    op.drop_index('ix_prediction_version_actual_result', 'prediction_versions')
    op.drop_column('prediction_versions', 'settled_at')
    op.drop_column('prediction_versions', 'profit_loss')
    op.drop_column('prediction_versions', 'actual_result')
    op.drop_column('prediction_versions', 'risk_level')
    op.drop_column('prediction_versions', 'value_classification')
    op.drop_column('prediction_versions', 'selection_edge')
    op.drop_column('prediction_versions', 'selection_fair_odds')
    op.drop_column('prediction_versions', 'selection_odds')
    op.drop_column('prediction_versions', 'selection_confidence')
    op.drop_column('prediction_versions', 'selection_probability')
    op.add_column('prediction_versions', 'selection_text')
    op.drop_column('prediction_versions', 'selected_market')
```

**Verify:**
```bash
cd c:\FootballIntelligence\backend
alembic upgrade head
# Should succeed with no errors
# Check database: prediction_versions table should have 12 new columns
```

---

### Step 2: Update PredictionVersionDB ORM Model

**What:** Add the 12 new columns to the `PredictionVersionDB` SQLAlchemy model in `models.py`.

**Files:**
- Modify: `c:\FootballIntelligence\backend\app\database\models.py`

**Changes in PredictionVersionDB class:**
```python
class PredictionVersionDB(BaseModel, Base):
    """Prediction version snapshot (immutable history)."""
    
    __tablename__ = "prediction_versions"
    
    # ... existing columns ...
    
    # Frozen MENSIONE Pick (immutable after creation)
    selected_market = Column(String(50), nullable=True)
    selection_text = Column(String(200), nullable=True)
    selection_probability = Column(Float, nullable=True)
    selection_confidence = Column(Float, nullable=True)
    selection_odds = Column(Float, nullable=True)
    selection_fair_odds = Column(Float, nullable=True)
    selection_edge = Column(Float, nullable=True)
    value_classification = Column(String(50), nullable=True)
    risk_level = Column(String(50), nullable=True)
    
    # Settlement (populated after match finishes)
    actual_result = Column(String(20), nullable=True)  # 'WIN', 'LOSS', 'VOID'
    profit_loss = Column(Float, nullable=True)
    settled_at = Column(DateTime(timezone=True), nullable=True)
    
    # Update __table_args__ to include new indexes
    __table_args__ = (
        Index("ix_prediction_version_match", "match_id", "stage"),
        Index("ix_prediction_version_created", "created_at"),
        Index("ix_prediction_version_actual_result", "actual_result"),
        Index("ix_prediction_version_settled_at", "settled_at"),
    )
```

**Verify:**
```bash
cd c:\FootballIntelligence\backend
python -c "from app.database.models import PredictionVersionDB; print([c.name for c in PredictionVersionDB.__table__.columns])"
# Should include selected_market, selection_text, ..., actual_result, profit_loss, settled_at
```

---

### Step 3: Update PredictionPersistenceService to Persist Frozen Pick Fields

**What:** Modify `save_version()` in `persistence.py` to map frozen pick fields from PredictionVersion to PredictionVersionDB.

**Files:**
- Modify: `c:\FootballIntelligence\backend\app\prediction\persistence.py`

**Changes in `save_version()` method:**
```python
def save_version(self, version: PredictionVersion) -> None:
    """Save prediction version to database."""
    from app.database.models import PredictionVersionDB
    
    db_version = PredictionVersionDB(
        id=version.version_id,
        match_id=version.match_id,
        stage=version.stage.value,
        created_at=version.created_at,
        prediction_data=version.prediction_data,
        model_versions=version.model_versions,
        data_quality_score=version.data_quality_score,
        confidence_score=version.confidence_score,
        notes=version.notes if version.notes else [],
        # NEW: Frozen pick fields
        selected_market=version.selected_market,
        selection_text=version.selection_text,
        selection_probability=version.selection_probability,
        selection_confidence=version.selection_confidence,
        selection_odds=version.selection_odds,
        selection_fair_odds=version.selection_fair_odds,
        selection_edge=version.selection_edge,
        value_classification=version.value_classification,
        risk_level=version.risk_level,
        # Settlement fields (None at creation)
        actual_result=version.actual_result,
        profit_loss=version.profit_loss,
        settled_at=version.settled_at,
    )
    
    self.session.add(db_version)
    self.session.commit()
```

**Changes in `_to_domain_version()` method:**
```python
def _to_domain_version(self, db_version) -> PredictionVersion:
    """Convert database model to domain model."""
    return PredictionVersion(
        version_id=db_version.id,
        match_id=db_version.match_id,
        stage=PredictionStage(db_version.stage),
        created_at=db_version.created_at,
        prediction_data=db_version.prediction_data,
        model_versions=db_version.model_versions or {},
        data_quality_score=db_version.data_quality_score,
        confidence_score=db_version.confidence_score,
        notes=db_version.notes or [],
        # NEW: Frozen pick fields
        selected_market=db_version.selected_market,
        selection_text=db_version.selection_text,
        selection_probability=db_version.selection_probability,
        selection_confidence=db_version.selection_confidence,
        selection_odds=db_version.selection_odds,
        selection_fair_odds=db_version.selection_fair_odds,
        selection_edge=db_version.selection_edge,
        value_classification=db_version.value_classification,
        risk_level=db_version.risk_level,
        # Settlement fields
        actual_result=db_version.actual_result,
        profit_loss=db_version.profit_loss,
        settled_at=db_version.settled_at,
    )
```

**Verify:**
```bash
cd c:\FootballIntelligence\backend
pytest tests/test_prediction_version.py::TestFrozenPickFields -v
# All frozen pick field tests should pass
```

---

### Step 4: Create ResultIngestionService

**What:** Implement service to fetch match results from existing providers. Uses FootballDataProvider.get_match() to retrieve final scores and status.

**Files:**
- Create: `c:\FootballIntelligence\backend\app\prediction\result_ingestion.py`

**Implementation:**
```python
"""Result ingestion service for match outcomes.

Fetches real match results from providers and prepares them for settlement.
Never fabricates results.
"""

from typing import Optional
from dataclasses import dataclass
from datetime import datetime

from app.providers.base import FootballDataProvider
from app.domain.enums import MatchStatus, MatchOutcome


@dataclass
class MatchResult:
    """Match result data for settlement."""
    
    match_id: str
    status: MatchStatus
    home_score: Optional[int]
    away_score: Optional[int]
    outcome: Optional[MatchOutcome]
    is_final: bool
    fetched_at: datetime
    
    def is_settleable(self) -> bool:
        """Check if result is valid for settlement."""
        return (
            self.is_final and
            self.status == MatchStatus.FINISHED and
            self.home_score is not None and
            self.away_score is not None and
            self.outcome is not None
        )


class ResultIngestionService:
    """Service for ingesting match results from providers."""
    
    def __init__(self, provider: FootballDataProvider):
        """Initialize result ingestion service.
        
        Args:
            provider: Football data provider
        """
        self.provider = provider
    
    def get_match_result(self, match_id: str) -> Optional[MatchResult]:
        """Get match result from provider.
        
        Args:
            match_id: Match identifier
        
        Returns:
            MatchResult if available, None if match not found
        
        Raises:
            ValueError: If match data is incomplete/invalid
        """
        # Fetch match from provider
        match = self.provider.get_match(match_id)
        
        if match is None:
            return None
        
        # Determine if match is final
        is_final = match.status == MatchStatus.FINISHED
        
        # For POSTPONED/CANCELLED, outcome is None but is_final could be True
        # (allows settlement as VOID)
        if match.status in (MatchStatus.POSTPONED, MatchStatus.CANCELLED):
            return MatchResult(
                match_id=match_id,
                status=match.status,
                home_score=None,
                away_score=None,
                outcome=None,
                is_final=True,  # Postponed/cancelled are "final" states
                fetched_at=datetime.utcnow()
            )
        
        # For FINISHED, scores and outcome must be present
        if is_final:
            if match.home_score is None or match.away_score is None:
                raise ValueError(
                    f"Match {match_id} status is FINISHED but scores are missing"
                )
            
            if match.outcome is None:
                raise ValueError(
                    f"Match {match_id} status is FINISHED but outcome is missing"
                )
        
        return MatchResult(
            match_id=match_id,
            status=match.status,
            home_score=match.home_score,
            away_score=match.away_score,
            outcome=match.outcome,
            is_final=is_final,
            fetched_at=datetime.utcnow()
        )
```

**Verify:**
```bash
cd c:\FootballIntelligence\backend
pytest tests/test_result_ingestion.py -v
# All result ingestion tests should pass
```

---

### Step 5: Create SettlementEngine

**What:** Implement market-specific settlement logic. Determines WIN/LOSS/VOID based on frozen pick and actual result.

**Files:**
- Create: `c:\FootballIntelligence\backend\app\prediction\settlement.py`

**Implementation:**
```python
"""Settlement engine for prediction outcomes.

Determines WIN/LOSS/VOID for different market types based on frozen pick and actual result.
NEVER modifies frozen pick fields.
"""

from typing import Optional, Tuple
from enum import Enum

from app.domain.enums import PredictionMarketType, MatchStatus, MatchOutcome
from app.prediction.result_ingestion import MatchResult


class SettlementOutcome(str, Enum):
    """Settlement outcome enumeration."""
    
    WIN = "WIN"
    LOSS = "LOSS"
    VOID = "VOID"


class SettlementEngine:
    """Engine for settling predictions based on match results."""
    
    def __init__(self, stake: float = 1.0):
        """Initialize settlement engine.
        
        Args:
            stake: Betting stake in units (default: 1.0)
        """
        self.stake = stake
    
    def settle_prediction(
        self,
        selected_market: str,
        selection_text: str,
        selection_odds: float,
        match_result: MatchResult
    ) -> Tuple[SettlementOutcome, float]:
        """Settle a prediction.
        
        Args:
            selected_market: Frozen market identifier (e.g., 'HOME_WIN', 'OVER_2_5')
            selection_text: Frozen selection text (e.g., 'Home Win', 'Over 2.5')
            selection_odds: Frozen bookmaker odds at prediction time
            match_result: Actual match result
        
        Returns:
            Tuple of (SettlementOutcome, profit_loss_amount)
        
        Raises:
            ValueError: If market type is unsupported or data is invalid
        """
        # Check if result is settleable
        if not match_result.is_settleable():
            # Postponed/cancelled matches
            if match_result.status in (MatchStatus.POSTPONED, MatchStatus.CANCELLED):
                return (SettlementOutcome.VOID, 0.0)
            
            # Match not finished yet or incomplete data
            raise ValueError(
                f"Match {match_result.match_id} is not settleable: "
                f"status={match_result.status}, scores={match_result.home_score}/{match_result.away_score}"
            )
        
        # Determine market type from selected_market
        market_type = self._parse_market_type(selected_market)
        
        # Route to appropriate settlement method
        if market_type == PredictionMarketType.MATCH_RESULT:
            outcome = self._settle_match_result(selection_text, match_result)
        elif market_type == PredictionMarketType.OVER_UNDER:
            outcome = self._settle_over_under(selected_market, selection_text, match_result)
        elif market_type == PredictionMarketType.BTTS:
            outcome = self._settle_btts(selection_text, match_result)
        elif market_type == PredictionMarketType.DOUBLE_CHANCE:
            outcome = self._settle_double_chance(selection_text, match_result)
        elif market_type == PredictionMarketType.HANDICAP:
            outcome = self._settle_handicap(selected_market, selection_text, match_result)
        else:
            raise ValueError(
                f"Settlement not implemented for market type: {market_type.value}. "
                f"Supported markets: MATCH_RESULT, OVER_UNDER, BTTS, DOUBLE_CHANCE, HANDICAP"
            )
        
        # Calculate profit/loss
        profit_loss = self._calculate_profit_loss(outcome, selection_odds)
        
        return (outcome, profit_loss)
    
    def _parse_market_type(self, selected_market: str) -> PredictionMarketType:
        """Parse market type from selected_market identifier."""
        market_upper = selected_market.upper()
        
        if market_upper in ('HOME_WIN', 'DRAW', 'AWAY_WIN', '1X2', 'MATCH_RESULT'):
            return PredictionMarketType.MATCH_RESULT
        elif market_upper.startswith('OVER_') or market_upper.startswith('UNDER_'):
            return PredictionMarketType.OVER_UNDER
        elif 'BTTS' in market_upper:
            return PredictionMarketType.BTTS
        elif market_upper in ('1X', '12', 'X2', 'DOUBLE_CHANCE'):
            return PredictionMarketType.DOUBLE_CHANCE
        elif 'HANDICAP' in market_upper:
            return PredictionMarketType.HANDICAP
        else:
            raise ValueError(f"Cannot parse market type from: {selected_market}")
    
    def _settle_match_result(
        self,
        selection_text: str,
        match_result: MatchResult
    ) -> SettlementOutcome:
        """Settle 1X2 market."""
        selection_upper = selection_text.upper()
        actual_outcome = match_result.outcome
        
        # Map selection to outcome
        if 'HOME' in selection_upper or selection_upper == '1':
            predicted_outcome = MatchOutcome.HOME_WIN
        elif 'DRAW' in selection_upper or selection_upper == 'X':
            predicted_outcome = MatchOutcome.DRAW
        elif 'AWAY' in selection_upper or selection_upper == '2':
            predicted_outcome = MatchOutcome.AWAY_WIN
        else:
            raise ValueError(f"Cannot parse 1X2 selection: {selection_text}")
        
        return SettlementOutcome.WIN if predicted_outcome == actual_outcome else SettlementOutcome.LOSS
    
    def _settle_over_under(
        self,
        selected_market: str,
        selection_text: str,
        match_result: MatchResult
    ) -> SettlementOutcome:
        """Settle Over/Under market."""
        # Extract line from selected_market (e.g., "OVER_2_5" or "UNDER_3_5")
        line = self._extract_line(selected_market)
        
        # Determine selection direction
        selection_upper = selection_text.upper()
        is_over = 'OVER' in selection_upper
        
        # Calculate total goals
        total_goals = match_result.home_score + match_result.away_score
        
        if total_goals > line:
            return SettlementOutcome.WIN if is_over else SettlementOutcome.LOSS
        elif total_goals < line:
            return SettlementOutcome.LOSS if is_over else SettlementOutcome.WIN
        else:
            # Push: total_goals == line
            return SettlementOutcome.VOID
    
    def _settle_btts(
        self,
        selection_text: str,
        match_result: MatchResult
    ) -> SettlementOutcome:
        """Settle Both Teams To Score market."""
        btts_actual = match_result.home_score > 0 and match_result.away_score > 0
        
        selection_upper = selection_text.upper()
        predicted_btts_yes = 'YES' in selection_upper or selection_upper == 'BTTS'
        
        if predicted_btts_yes:
            return SettlementOutcome.WIN if btts_actual else SettlementOutcome.LOSS
        else:
            return SettlementOutcome.WIN if not btts_actual else SettlementOutcome.LOSS
    
    def _settle_double_chance(
        self,
        selection_text: str,
        match_result: MatchResult
    ) -> SettlementOutcome:
        """Settle Double Chance market."""
        selection_upper = selection_text.upper().replace(' ', '')
        actual_outcome = match_result.outcome
        
        # Parse selection
        if '1X' in selection_upper:
            win_outcomes = {MatchOutcome.HOME_WIN, MatchOutcome.DRAW}
        elif '12' in selection_upper:
            win_outcomes = {MatchOutcome.HOME_WIN, MatchOutcome.AWAY_WIN}
        elif 'X2' in selection_upper:
            win_outcomes = {MatchOutcome.DRAW, MatchOutcome.AWAY_WIN}
        else:
            raise ValueError(f"Cannot parse double chance selection: {selection_text}")
        
        return SettlementOutcome.WIN if actual_outcome in win_outcomes else SettlementOutcome.LOSS
    
    def _settle_handicap(
        self,
        selected_market: str,
        selection_text: str,
        match_result: MatchResult
    ) -> SettlementOutcome:
        """Settle Handicap market."""
        # Extract handicap value and team from selected_market
        # Example: "HANDICAP_-1.5_HOME" or "HANDICAP_+1_AWAY"
        handicap, team = self._extract_handicap(selected_market)
        
        # Apply handicap
        if 'HOME' in team.upper():
            adjusted_home = match_result.home_score + handicap
            adjusted_away = match_result.away_score
        else:
            adjusted_home = match_result.home_score
            adjusted_away = match_result.away_score + handicap
        
        # Determine outcome
        if adjusted_home > adjusted_away:
            actual_with_handicap = MatchOutcome.HOME_WIN
        elif adjusted_home < adjusted_away:
            actual_with_handicap = MatchOutcome.AWAY_WIN
        else:
            # Push on whole-number handicaps
            return SettlementOutcome.VOID
        
        # Check if prediction matches
        selection_upper = selection_text.upper()
        if 'HOME' in selection_upper:
            predicted_outcome = MatchOutcome.HOME_WIN
        elif 'AWAY' in selection_upper:
            predicted_outcome = MatchOutcome.AWAY_WIN
        else:
            raise ValueError(f"Cannot parse handicap selection: {selection_text}")
        
        return SettlementOutcome.WIN if predicted_outcome == actual_with_handicap else SettlementOutcome.LOSS
    
    def _extract_line(self, selected_market: str) -> float:
        """Extract Over/Under line from market identifier."""
        # Example: "OVER_2_5" → 2.5, "UNDER_3_5" → 3.5
        parts = selected_market.split('_')
        for part in parts:
            try:
                # Replace underscore with decimal point if present
                line_str = part.replace('_', '.')
                return float(line_str)
            except ValueError:
                continue
        
        raise ValueError(f"Cannot extract line from: {selected_market}")
    
    def _extract_handicap(self, selected_market: str) -> Tuple[float, str]:
        """Extract handicap value and team from market identifier."""
        # Example: "HANDICAP_-1.5_HOME" → (-1.5, "HOME")
        parts = selected_market.upper().split('_')
        
        handicap = None
        team = None
        
        for i, part in enumerate(parts):
            # Find handicap value (starts with + or -)
            if part.startswith(('+', '-')):
                try:
                    handicap = float(part)
                except ValueError:
                    pass
            # Find team
            if part in ('HOME', 'AWAY'):
                team = part
        
        if handicap is None or team is None:
            raise ValueError(f"Cannot extract handicap from: {selected_market}")
        
        return (handicap, team)
    
    def _calculate_profit_loss(
        self,
        outcome: SettlementOutcome,
        odds: float
    ) -> float:
        """Calculate profit/loss based on outcome and odds."""
        if outcome == SettlementOutcome.WIN:
            return (odds - 1.0) * self.stake
        elif outcome == SettlementOutcome.LOSS:
            return -1.0 * self.stake
        else:  # VOID
            return 0.0
```

**Verify:**
```bash
cd c:\FootballIntelligence\backend
pytest tests/test_settlement_engine.py -v
# All settlement logic tests should pass (created in Step 10)
```

---

### Step 6: Implement settle_prediction() in PredictionVersionManager

**What:** Replace NotImplementedError in `settle_prediction()` with actual implementation using SettlementEngine and ResultIngestionService.

**Files:**
- Modify: `c:\FootballIntelligence\backend\app\prediction\prediction_version.py`

**Changes:**
```python
def settle_prediction(
    self,
    version_id: str,
    provider: FootballDataProvider,
    stake: float = 1.0
) -> Optional[PredictionVersion]:
    """Settle a prediction with actual match result.
    
    Args:
        version_id: Version identifier to settle
        provider: Football data provider for fetching results
        stake: Betting stake in units (default: 1.0)
    
    Returns:
        Updated PredictionVersion with settlement data
    
    Raises:
        ValueError: If version not found, already settled, or result not available
    """
    from app.prediction.result_ingestion import ResultIngestionService
    from app.prediction.settlement import SettlementEngine
    
    # Get version
    version = self.get_version_by_id(version_id) if self.persistence_service else None
    
    if version is None:
        # Try memory store
        for match_versions in self._memory_store.values():
            for v in match_versions:
                if v.version_id == version_id:
                    version = v
                    break
            if version:
                break
    
    if version is None:
        raise ValueError(f"Version {version_id} not found")
    
    # Check if already settled
    if version.actual_result is not None:
        raise ValueError(f"Version {version_id} is already settled: {version.actual_result}")
    
    # Check if version has frozen pick
    if version.selected_market is None or version.selection_text is None or version.selection_odds is None:
        raise ValueError(
            f"Version {version_id} has no frozen pick data. "
            f"Cannot settle predictions without selected_market, selection_text, and selection_odds."
        )
    
    # Fetch match result
    ingestion = ResultIngestionService(provider)
    match_result = ingestion.get_match_result(version.match_id)
    
    if match_result is None:
        raise ValueError(f"Match {version.match_id} not found in provider")
    
    if not match_result.is_settleable():
        raise ValueError(
            f"Match {version.match_id} is not settleable: "
            f"status={match_result.status}"
        )
    
    # Settle prediction
    engine = SettlementEngine(stake=stake)
    outcome, profit_loss = engine.settle_prediction(
        selected_market=version.selected_market,
        selection_text=version.selection_text,
        selection_odds=version.selection_odds,
        match_result=match_result
    )
    
    # Update version (create new object to maintain immutability principle)
    settled_version = PredictionVersion(
        version_id=version.version_id,
        match_id=version.match_id,
        stage=version.stage,
        created_at=version.created_at,
        prediction_data=version.prediction_data,
        model_versions=version.model_versions,
        data_quality_score=version.data_quality_score,
        confidence_score=version.confidence_score,
        notes=version.notes,
        # Frozen pick fields (unchanged)
        selected_market=version.selected_market,
        selection_text=version.selection_text,
        selection_probability=version.selection_probability,
        selection_confidence=version.selection_confidence,
        selection_odds=version.selection_odds,
        selection_fair_odds=version.selection_fair_odds,
        selection_edge=version.selection_edge,
        value_classification=version.value_classification,
        risk_level=version.risk_level,
        # Settlement fields (NEW)
        actual_result=outcome.value,
        profit_loss=profit_loss,
        settled_at=datetime.utcnow()
    )
    
    # Persist settlement
    if self.persistence_service:
        # Update database record
        from app.database.models import PredictionVersionDB
        db_version = self.persistence_service.session.query(PredictionVersionDB).filter(
            PredictionVersionDB.id == version_id
        ).first()
        
        if db_version:
            db_version.actual_result = outcome.value
            db_version.profit_loss = profit_loss
            db_version.settled_at = settled_version.settled_at
            self.persistence_service.session.commit()
    else:
        # Update memory store
        for match_id, versions in self._memory_store.items():
            for i, v in enumerate(versions):
                if v.version_id == version_id:
                    self._memory_store[match_id][i] = settled_version
                    break
    
    return settled_version
```

**Verify:**
```bash
cd c:\FootballIntelligence\backend
pytest tests/test_prediction_version.py::test_settle_prediction -v
# Settlement tests should pass
```

---

### Step 7: Implement get_settled_picks_by_market() in PredictionVersionManager

**What:** Replace NotImplementedError with query implementation.

**Files:**
- Modify: `c:\FootballIntelligence\backend\app\prediction\prediction_version.py`

**Changes:**
```python
def get_settled_picks_by_market(
    self,
    market_type: str,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None
) -> List[PredictionVersion]:
    """Get all settled picks for a specific market type.
    
    Args:
        market_type: Market identifier (e.g. 'HOME_WIN', 'OVER_2_5', 'BTTS_YES')
        start_date: Optional start date filter (settled_at >= start_date)
        end_date: Optional end date filter (settled_at <= end_date)
    
    Returns:
        List of settled PredictionVersion objects for the market
    """
    if self.persistence_service:
        from app.database.models import PredictionVersionDB
        from sqlalchemy import and_
        
        query = self.persistence_service.session.query(PredictionVersionDB).filter(
            PredictionVersionDB.actual_result.isnot(None),  # Only settled
            PredictionVersionDB.selected_market.isnot(None)  # Only with picks
        )
        
        # Filter by market type (flexible matching)
        market_upper = market_type.upper()
        query = query.filter(
            PredictionVersionDB.selected_market.ilike(f'%{market_upper}%')
        )
        
        # Date filtering
        if start_date:
            query = query.filter(PredictionVersionDB.settled_at >= start_date)
        
        if end_date:
            query = query.filter(PredictionVersionDB.settled_at <= end_date)
        
        # Order by settlement date
        query = query.order_by(PredictionVersionDB.settled_at.desc())
        
        db_versions = query.all()
        
        return [self.persistence_service._to_domain_version(v) for v in db_versions]
    else:
        # Memory store fallback
        settled = []
        for match_versions in self._memory_store.values():
            for version in match_versions:
                # Check if settled
                if version.actual_result is None or version.selected_market is None:
                    continue
                
                # Check market match
                if market_type.upper() not in version.selected_market.upper():
                    continue
                
                # Check date filters
                if start_date and version.settled_at < start_date:
                    continue
                
                if end_date and version.settled_at > end_date:
                    continue
                
                settled.append(version)
        
        # Sort by settlement date
        settled.sort(key=lambda v: v.settled_at, reverse=True)
        
        return settled
```

**Verify:**
```bash
cd c:\FootballIntelligence\backend
pytest tests/test_prediction_version.py::test_get_settled_picks_by_market -v
# Query tests should pass
```

---

### Step 8: Extend TrackRecordManager with Settlement Metrics

**What:** Add methods to calculate track record metrics from settled predictions.

**Files:**
- Modify: `c:\FootballIntelligence\backend\app\prediction\track_record.py`

**Add new methods:**
```python
def get_settled_summary(
    self,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    market_type: Optional[str] = None
) -> Dict[str, any]:
    """Get summary of settled predictions.
    
    Args:
        start_date: Optional start date filter
        end_date: Optional end date filter
        market_type: Optional market type filter
    
    Returns:
        Dict with settlement metrics
    """
    # Get settled predictions from persistence layer
    if self.persistence_service:
        from app.database.models import PredictionVersionDB
        
        query = self.persistence_service.session.query(PredictionVersionDB).filter(
            PredictionVersionDB.actual_result.isnot(None)
        )
        
        if start_date:
            query = query.filter(PredictionVersionDB.settled_at >= start_date)
        
        if end_date:
            query = query.filter(PredictionVersionDB.settled_at <= end_date)
        
        if market_type:
            query = query.filter(
                PredictionVersionDB.selected_market.ilike(f'%{market_type.upper()}%')
            )
        
        settled_versions = query.all()
    else:
        # Fallback to memory (not implemented in base TrackRecordManager)
        settled_versions = []
    
    if not settled_versions:
        return {
            'total_predictions': 0,
            'settled_predictions': 0,
            'wins': 0,
            'losses': 0,
            'voids': 0,
            'win_rate': 0.0,
            'roi': 0.0,
            'total_profit_loss': 0.0,
            'average_odds': 0.0,
            'average_confidence': 0.0,
            'average_probability': 0.0
        }
    
    # Calculate metrics
    total = len(settled_versions)
    wins = sum(1 for v in settled_versions if v.actual_result == 'WIN')
    losses = sum(1 for v in settled_versions if v.actual_result == 'LOSS')
    voids = sum(1 for v in settled_versions if v.actual_result == 'VOID')
    
    # Win rate (exclude voids)
    non_void = wins + losses
    win_rate = wins / non_void if non_void > 0 else 0.0
    
    # Profit/loss
    total_pl = sum(v.profit_loss for v in settled_versions if v.profit_loss is not None)
    total_stake = sum(1.0 for v in settled_versions if v.actual_result in ('WIN', 'LOSS'))
    roi = total_pl / total_stake if total_stake > 0 else 0.0
    
    # Averages
    odds_list = [v.selection_odds for v in settled_versions if v.selection_odds is not None]
    avg_odds = sum(odds_list) / len(odds_list) if odds_list else 0.0
    
    conf_list = [v.selection_confidence for v in settled_versions if v.selection_confidence is not None]
    avg_confidence = sum(conf_list) / len(conf_list) if conf_list else 0.0
    
    prob_list = [v.selection_probability for v in settled_versions if v.selection_probability is not None]
    avg_probability = sum(prob_list) / len(prob_list) if prob_list else 0.0
    
    return {
        'total_predictions': total,
        'settled_predictions': total,
        'wins': wins,
        'losses': losses,
        'voids': voids,
        'win_rate': win_rate,
        'roi': roi,
        'total_profit_loss': total_pl,
        'average_odds': avg_odds,
        'average_confidence': avg_confidence,
        'average_probability': avg_probability
    }

def get_market_performance(
    self,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None
) -> List[Dict[str, any]]:
    """Get performance breakdown by market type.
    
    Args:
        start_date: Optional start date filter
        end_date: Optional end date filter
    
    Returns:
        List of per-market performance dicts
    """
    if not self.persistence_service:
        return []
    
    from app.database.models import PredictionVersionDB
    from sqlalchemy import func
    
    query = self.persistence_service.session.query(
        PredictionVersionDB.selected_market,
        func.count(PredictionVersionDB.id).label('total'),
        func.sum(
            func.cast(PredictionVersionDB.actual_result == 'WIN', sa.Integer)
        ).label('wins'),
        func.sum(
            func.cast(PredictionVersionDB.actual_result == 'LOSS', sa.Integer)
        ).label('losses'),
        func.sum(
            func.cast(PredictionVersionDB.actual_result == 'VOID', sa.Integer)
        ).label('voids'),
        func.sum(PredictionVersionDB.profit_loss).label('total_pl'),
        func.avg(PredictionVersionDB.selection_odds).label('avg_odds'),
        func.avg(PredictionVersionDB.selection_confidence).label('avg_confidence'),
    ).filter(
        PredictionVersionDB.actual_result.isnot(None),
        PredictionVersionDB.selected_market.isnot(None)
    )
    
    if start_date:
        query = query.filter(PredictionVersionDB.settled_at >= start_date)
    
    if end_date:
        query = query.filter(PredictionVersionDB.settled_at <= end_date)
    
    query = query.group_by(PredictionVersionDB.selected_market)
    
    results = query.all()
    
    performance = []
    for row in results:
        non_void = (row.wins or 0) + (row.losses or 0)
        win_rate = (row.wins or 0) / non_void if non_void > 0 else 0.0
        
        total_stake = non_void  # 1 unit per bet
        roi = (row.total_pl or 0.0) / total_stake if total_stake > 0 else 0.0
        
        performance.append({
            'market_type': row.selected_market,
            'sample_size': row.total,
            'wins': row.wins or 0,
            'losses': row.losses or 0,
            'voids': row.voids or 0,
            'win_rate': win_rate,
            'roi': roi,
            'total_profit_loss': row.total_pl or 0.0,
            'average_odds': row.avg_odds or 0.0,
            'average_confidence': row.avg_confidence or 0.0,
        })
    
    return performance
```

**Verify:**
```bash
cd c:\FootballIntelligence\backend
pytest tests/test_track_record.py::test_settled_summary -v
pytest tests/test_track_record.py::test_market_performance -v
# Settlement summary tests should pass
```

---

### Step 9: Create API Endpoints for Predictions and Track Record

**What:** Add 4 new API endpoints following existing FastAPI patterns in `/api/v1/endpoints/`.

**Files:**
- Create: `c:\FootballIntelligence\backend\app\api\v1\endpoints\predictions.py`
- Modify: `c:\FootballIntelligence\backend\app\api\v1\__init__.py` (register router)
- Modify: `c:\FootballIntelligence\backend\app\api\v1\schemas.py` (add response schemas)

**predictions.py implementation:**
```python
"""Prediction history and settlement endpoints."""

from typing import Optional, List
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.api.v1.schemas import (
    PredictionHistoryResponse,
    SettledPredictionResponse,
    TrackRecordSummaryResponse,
    MarketPerformanceResponse,
)
from app.prediction.prediction_version import PredictionVersionManager
from app.prediction.persistence import PredictionPersistenceService
from app.prediction.track_record import TrackRecordManager


router = APIRouter(prefix="/predictions", tags=["predictions"])


@router.get(
    "/history",
    response_model=PredictionHistoryResponse,
    summary="Get prediction history",
    description="Get prediction versions with optional filtering"
)
async def get_prediction_history(
    match_id: Optional[str] = Query(None, description="Filter by match ID"),
    stage: Optional[str] = Query(None, description="Filter by prediction stage"),
    from_date: Optional[datetime] = Query(None, description="Filter from creation date"),
    to_date: Optional[datetime] = Query(None, description="Filter to creation date"),
    limit: int = Query(50, ge=1, le=200, description="Results per page"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    db: Session = Depends(get_db),
) -> PredictionHistoryResponse:
    """Get prediction version history."""
    persistence = PredictionPersistenceService(db)
    manager = PredictionVersionManager(persistence)
    
    if match_id:
        # Get all versions for specific match
        versions = manager.get_versions(match_id)
    else:
        # Query all versions with filters (requires new method)
        from app.database.models import PredictionVersionDB
        
        query = db.query(PredictionVersionDB)
        
        if stage:
            query = query.filter(PredictionVersionDB.stage == stage)
        
        if from_date:
            query = query.filter(PredictionVersionDB.created_at >= from_date)
        
        if to_date:
            query = query.filter(PredictionVersionDB.created_at <= to_date)
        
        query = query.order_by(PredictionVersionDB.created_at.desc())
        query = query.limit(limit).offset(offset)
        
        db_versions = query.all()
        versions = [persistence._to_domain_version(v) for v in db_versions]
    
    # Convert to response
    return PredictionHistoryResponse(
        predictions=[
            {
                "version_id": v.version_id,
                "match_id": v.match_id,
                "stage": v.stage.value,
                "created_at": v.created_at,
                "selected_market": v.selected_market,
                "selection_text": v.selection_text,
                "selection_probability": v.selection_probability,
                "selection_confidence": v.selection_confidence,
                "selection_odds": v.selection_odds,
                "actual_result": v.actual_result,
                "profit_loss": v.profit_loss,
                "settled_at": v.settled_at,
            }
            for v in versions
        ],
        total=len(versions),
        limit=limit,
        offset=offset
    )


@router.get(
    "/settled",
    response_model=List[SettledPredictionResponse],
    summary="Get settled predictions",
    description="Get only settled predictions with outcomes"
)
async def get_settled_predictions(
    market: Optional[str] = Query(None, description="Filter by market type"),
    actual_result: Optional[str] = Query(None, description="Filter by outcome (WIN/LOSS/VOID)"),
    from_date: Optional[datetime] = Query(None, description="Filter from settlement date"),
    to_date: Optional[datetime] = Query(None, description="Filter to settlement date"),
    limit: int = Query(50, ge=1, le=200, description="Results per page"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    db: Session = Depends(get_db),
) -> List[SettledPredictionResponse]:
    """Get settled predictions."""
    persistence = PredictionPersistenceService(db)
    manager = PredictionVersionManager(persistence)
    
    from app.database.models import PredictionVersionDB
    
    query = db.query(PredictionVersionDB).filter(
        PredictionVersionDB.actual_result.isnot(None)
    )
    
    if market:
        query = query.filter(
            PredictionVersionDB.selected_market.ilike(f'%{market.upper()}%')
        )
    
    if actual_result:
        query = query.filter(PredictionVersionDB.actual_result == actual_result.upper())
    
    if from_date:
        query = query.filter(PredictionVersionDB.settled_at >= from_date)
    
    if to_date:
        query = query.filter(PredictionVersionDB.settled_at <= to_date)
    
    query = query.order_by(PredictionVersionDB.settled_at.desc())
    query = query.limit(limit).offset(offset)
    
    db_versions = query.all()
    versions = [persistence._to_domain_version(v) for v in db_versions]
    
    return [
        SettledPredictionResponse(
            version_id=v.version_id,
            match_id=v.match_id,
            stage=v.stage.value,
            created_at=v.created_at,
            selected_market=v.selected_market,
            selection_text=v.selection_text,
            selection_probability=v.selection_probability,
            selection_confidence=v.selection_confidence,
            selection_odds=v.selection_odds,
            selection_fair_odds=v.selection_fair_odds,
            selection_edge=v.selection_edge,
            value_classification=v.value_classification,
            risk_level=v.risk_level,
            actual_result=v.actual_result,
            profit_loss=v.profit_loss,
            settled_at=v.settled_at,
        )
        for v in versions
    ]


@router.get(
    "/track-record/summary",
    response_model=TrackRecordSummaryResponse,
    summary="Get track record summary",
    description="Get aggregate performance metrics"
)
async def get_track_record_summary(
    from_date: Optional[datetime] = Query(None, description="Filter from settlement date"),
    to_date: Optional[datetime] = Query(None, description="Filter to settlement date"),
    stage: Optional[str] = Query(None, description="Filter by prediction stage"),
    db: Session = Depends(get_db),
) -> TrackRecordSummaryResponse:
    """Get track record summary."""
    persistence = PredictionPersistenceService(db)
    manager = TrackRecordManager(persistence)
    
    summary = manager.get_settled_summary(
        start_date=from_date,
        end_date=to_date
    )
    
    return TrackRecordSummaryResponse(**summary)


@router.get(
    "/track-record/by-market",
    response_model=List[MarketPerformanceResponse],
    summary="Get track record by market",
    description="Get performance breakdown by market type"
)
async def get_track_record_by_market(
    from_date: Optional[datetime] = Query(None, description="Filter from settlement date"),
    to_date: Optional[datetime] = Query(None, description="Filter to settlement date"),
    db: Session = Depends(get_db),
) -> List[MarketPerformanceResponse]:
    """Get market performance breakdown."""
    persistence = PredictionPersistenceService(db)
    manager = TrackRecordManager(persistence)
    
    performance = manager.get_market_performance(
        start_date=from_date,
        end_date=to_date
    )
    
    return [MarketPerformanceResponse(**p) for p in performance]
```

**Add schemas to schemas.py:**
```python
class PredictionHistoryItemResponse(BaseModel):
    """Single prediction history item."""
    version_id: str
    match_id: str
    stage: str
    created_at: datetime
    selected_market: Optional[str] = None
    selection_text: Optional[str] = None
    selection_probability: Optional[float] = None
    selection_confidence: Optional[float] = None
    selection_odds: Optional[float] = None
    actual_result: Optional[str] = None
    profit_loss: Optional[float] = None
    settled_at: Optional[datetime] = None


class PredictionHistoryResponse(BaseModel):
    """Prediction history response."""
    predictions: List[PredictionHistoryItemResponse]
    total: int
    limit: int
    offset: int


class SettledPredictionResponse(BaseModel):
    """Settled prediction response."""
    version_id: str
    match_id: str
    stage: str
    created_at: datetime
    # Frozen pick
    selected_market: str
    selection_text: str
    selection_probability: float
    selection_confidence: float
    selection_odds: float
    selection_fair_odds: Optional[float] = None
    selection_edge: Optional[float] = None
    value_classification: Optional[str] = None
    risk_level: Optional[str] = None
    # Settlement
    actual_result: str
    profit_loss: float
    settled_at: datetime


class TrackRecordSummaryResponse(BaseModel):
    """Track record summary response."""
    total_predictions: int
    settled_predictions: int
    wins: int
    losses: int
    voids: int
    win_rate: float
    roi: float
    total_profit_loss: float
    average_odds: float
    average_confidence: float
    average_probability: float


class MarketPerformanceResponse(BaseModel):
    """Market performance response."""
    market_type: str
    sample_size: int
    wins: int
    losses: int
    voids: int
    win_rate: float
    roi: float
    total_profit_loss: float
    average_odds: float
    average_confidence: float
```

**Register router in `__init__.py`:**
```python
from app.api.v1.endpoints import matches, live_matches, predictions

# Create API v1 router
api_router = APIRouter(prefix="/api/v1")

# Include endpoint routers
api_router.include_router(live_matches.router)
api_router.include_router(matches.router)
api_router.include_router(predictions.router)
```

**Verify:**
```bash
cd c:\FootballIntelligence\backend
pytest tests/test_api_predictions.py -v
# API endpoint tests should pass
```

---

### Step 10: Create Comprehensive Test Suite

**What:** Create tests covering all settlement scenarios, frozen pick integrity, track record calculation, and API endpoints.

**Files:**
- Create: `c:\FootballIntelligence\backend\tests\test_result_ingestion.py`
- Create: `c:\FootballIntelligence\backend\tests\test_settlement_engine.py`
- Create: `c:\FootballIntelligence\backend\tests\test_settlement_integration.py`
- Create: `c:\FootballIntelligence\backend\tests\test_api_predictions.py`
- Modify: `c:\FootballIntelligence\backend\tests\test_prediction_version.py` (add settlement tests)
- Modify: `c:\FootballIntelligence\backend\tests\test_track_record.py` (add settlement metrics tests)

**Test coverage must include:**

**Settlement scenarios:**
- Match result: home win, draw, away win
- Over/Under: over wins, under wins, push (void)
- BTTS: yes wins, no wins
- Double chance: 1X, 12, X2
- Handicap: -1.5 home, +1 away, push
- Void: postponed match, cancelled match
- Invalid: match not finished, incomplete result

**Frozen pick integrity:**
- Verify settlement NEVER modifies: selected_market, selection_text, selection_probability, selection_confidence, selection_odds, selection_fair_odds, selection_edge, value_classification, risk_level
- Verify settle_prediction() raises error if already settled
- Verify settle_prediction() raises error if no frozen pick exists

**Track record:**
- Verify totals calculation
- Verify win rate calculation (excludes voids)
- Verify ROI calculation
- Verify profit/loss aggregation
- Verify market aggregation
- Verify empty state handling
- Verify date filtering

**API endpoints:**
- GET /predictions/history: pagination, filtering, response structure
- GET /predictions/settled: filtering by market/result/date
- GET /track-record/summary: correct metric calculation
- GET /track-record/by-market: per-market breakdown

**Test file structure (example for test_settlement_engine.py):**
```python
"""Tests for settlement engine - Phase 6."""

import pytest
from app.prediction.settlement import SettlementEngine, SettlementOutcome
from app.prediction.result_ingestion import MatchResult
from app.domain.enums import MatchStatus, MatchOutcome
from datetime import datetime


class TestMatchResultSettlement:
    """Test 1X2 market settlement."""
    
    def test_home_win_correct(self):
        """Test home win prediction wins when home wins."""
        engine = SettlementEngine(stake=1.0)
        result = MatchResult(
            match_id="test",
            status=MatchStatus.FINISHED,
            home_score=2,
            away_score=1,
            outcome=MatchOutcome.HOME_WIN,
            is_final=True,
            fetched_at=datetime.utcnow()
        )
        
        outcome, pl = engine.settle_prediction(
            selected_market="HOME_WIN",
            selection_text="Home Win",
            selection_odds=2.10,
            match_result=result
        )
        
        assert outcome == SettlementOutcome.WIN
        assert pl == pytest.approx((2.10 - 1.0) * 1.0)
    
    def test_home_win_incorrect(self):
        """Test home win prediction loses when away wins."""
        engine = SettlementEngine(stake=1.0)
        result = MatchResult(
            match_id="test",
            status=MatchStatus.FINISHED,
            home_score=0,
            away_score=2,
            outcome=MatchOutcome.AWAY_WIN,
            is_final=True,
            fetched_at=datetime.utcnow()
        )
        
        outcome, pl = engine.settle_prediction(
            selected_market="HOME_WIN",
            selection_text="Home Win",
            selection_odds=2.10,
            match_result=result
        )
        
        assert outcome == SettlementOutcome.LOSS
        assert pl == pytest.approx(-1.0)
    
    # ... more 1X2 tests ...


class TestOverUnderSettlement:
    """Test Over/Under market settlement."""
    
    def test_over_25_wins(self):
        """Test over 2.5 wins when total goals > 2.5."""
        engine = SettlementEngine(stake=1.0)
        result = MatchResult(
            match_id="test",
            status=MatchStatus.FINISHED,
            home_score=2,
            away_score=1,
            outcome=MatchOutcome.HOME_WIN,
            is_final=True,
            fetched_at=datetime.utcnow()
        )
        
        outcome, pl = engine.settle_prediction(
            selected_market="OVER_2_5",
            selection_text="Over 2.5",
            selection_odds=1.90,
            match_result=result
        )
        
        assert outcome == SettlementOutcome.WIN
        assert pl == pytest.approx((1.90 - 1.0) * 1.0)
    
    def test_over_25_push(self):
        """Test over 2.5 voids when total goals == 2.5 (impossible, but test push logic)."""
        # Note: 2.5 can't equal integer, but test the logic for whole-number lines
        engine = SettlementEngine(stake=1.0)
        result = MatchResult(
            match_id="test",
            status=MatchStatus.FINISHED,
            home_score=2,
            away_score=1,  # Total = 3, not a push for 2.5
            outcome=MatchOutcome.HOME_WIN,
            is_final=True,
            fetched_at=datetime.utcnow()
        )
        
        # Use OVER_3_0 for actual push test
        outcome, pl = engine.settle_prediction(
            selected_market="OVER_3_0",
            selection_text="Over 3.0",
            selection_odds=1.90,
            match_result=result
        )
        
        assert outcome == SettlementOutcome.VOID
        assert pl == 0.0
    
    # ... more O/U tests ...


class TestBTTSSettlement:
    """Test BTTS market settlement."""
    
    def test_btts_yes_correct(self):
        """Test BTTS yes wins when both teams score."""
        # ... implementation ...
    
    def test_btts_yes_incorrect(self):
        """Test BTTS yes loses when one team doesn't score."""
        # ... implementation ...


class TestDoubleChanceSettlement:
    """Test double chance market settlement."""
    
    def test_1x_home_win(self):
        """Test 1X wins on home win."""
        # ... implementation ...
    
    def test_1x_draw(self):
        """Test 1X wins on draw."""
        # ... implementation ...
    
    def test_1x_away_loss(self):
        """Test 1X loses on away win."""
        # ... implementation ...


class TestHandicapSettlement:
    """Test handicap market settlement."""
    
    def test_handicap_minus_15_home_win(self):
        """Test -1.5 home handicap wins."""
        # ... implementation ...
    
    def test_handicap_push(self):
        """Test handicap push on whole-number handicap."""
        # ... implementation ...


class TestVoidScenarios:
    """Test void/cancelled scenarios."""
    
    def test_postponed_match(self):
        """Test postponed match results in VOID."""
        # ... implementation ...
    
    def test_cancelled_match(self):
        """Test cancelled match results in VOID."""
        # ... implementation ...


class TestUnsupportedMarkets:
    """Test unsupported market error handling."""
    
    def test_correct_score_raises_error(self):
        """Test correct score market raises ValueError."""
        engine = SettlementEngine()
        result = MatchResult(
            match_id="test",
            status=MatchStatus.FINISHED,
            home_score=2,
            away_score=1,
            outcome=MatchOutcome.HOME_WIN,
            is_final=True,
            fetched_at=datetime.utcnow()
        )
        
        with pytest.raises(ValueError, match="not implemented"):
            engine.settle_prediction(
                selected_market="CORRECT_SCORE_2_1",
                selection_text="2-1",
                selection_odds=9.0,
                match_result=result
            )
```

**Verify:**
```bash
cd c:\FootballIntelligence\backend
pytest tests/test_settlement_engine.py -v
pytest tests/test_result_ingestion.py -v
pytest tests/test_settlement_integration.py -v
pytest tests/test_prediction_version.py -v
pytest tests/test_track_record.py -v
pytest tests/test_api_predictions.py -v
# All tests should pass
```

---

### Step 11: Add Frontend TypeScript Types (Minimal)

**What:** Add TypeScript type definitions for settled predictions and track record API responses. NO component implementation, NO visual changes.

**Files:**
- Create: `c:\FootballIntelligence\frontend\src\types\predictions.ts`

**Implementation:**
```typescript
/**
 * Prediction and settlement types for Phase 6/7.
 * 
 * These types define the API contract for prediction history,
 * settled predictions, and track record endpoints.
 */

export interface PredictionHistoryItem {
  version_id: string;
  match_id: string;
  stage: string;
  created_at: string;
  selected_market?: string;
  selection_text?: string;
  selection_probability?: number;
  selection_confidence?: number;
  selection_odds?: number;
  actual_result?: 'WIN' | 'LOSS' | 'VOID';
  profit_loss?: number;
  settled_at?: string;
}

export interface PredictionHistoryResponse {
  predictions: PredictionHistoryItem[];
  total: number;
  limit: number;
  offset: number;
}

export interface SettledPrediction {
  version_id: string;
  match_id: string;
  stage: string;
  created_at: string;
  // Frozen pick
  selected_market: string;
  selection_text: string;
  selection_probability: number;
  selection_confidence: number;
  selection_odds: number;
  selection_fair_odds?: number;
  selection_edge?: number;
  value_classification?: string;
  risk_level?: string;
  // Settlement
  actual_result: 'WIN' | 'LOSS' | 'VOID';
  profit_loss: number;
  settled_at: string;
}

export interface TrackRecordSummary {
  total_predictions: number;
  settled_predictions: number;
  wins: number;
  losses: number;
  voids: number;
  win_rate: number;
  roi: number;
  total_profit_loss: number;
  average_odds: number;
  average_confidence: number;
  average_probability: number;
}

export interface MarketPerformance {
  market_type: string;
  sample_size: number;
  wins: number;
  losses: number;
  voids: number;
  win_rate: number;
  roi: number;
  total_profit_loss: number;
  average_odds: number;
  average_confidence: number;
}
```

**Verify:**
```bash
cd c:\FootballIntelligence\frontend
npm run type-check
# Should succeed with no type errors
```

---

### Step 12: Run Full Test Suite

**What:** Execute the complete backend test suite to ensure no regressions and all new functionality passes.

**Commands:**
```bash
cd c:\FootballIntelligence\backend

# Run focused Phase 6/7 tests
pytest tests/test_settlement_engine.py -v
pytest tests/test_result_ingestion.py -v
pytest tests/test_settlement_integration.py -v
pytest tests/test_prediction_version.py -v
pytest tests/test_track_record.py -v
pytest tests/test_api_predictions.py -v

# Run FULL backend test suite
pytest tests/ -v --tb=short

# If any failures, fix them before proceeding
```

**Verify:**
- All settlement tests pass
- All frozen pick integrity tests pass
- All track record tests pass
- All API endpoint tests pass
- Existing tests continue to pass (no regressions)

---

### Step 13: Update Documentation

**What:** Update PROGRESS.md with Phase 6/7 completion status, implemented features, and remaining limitations.

**Files:**
- Modify: `c:\FootballIntelligence\docs\PROGRESS.md`

**Add entry:**
```markdown
## Entry: 2026-[DATE] - Phase 6 & 7: Result Ingestion, Settlement & Track Record

### Completed Work

**Phase 6 — Result Ingestion + Prediction Settlement:**

1. **Database Schema Extensions**
   - Added 12 columns to `prediction_versions` table:
     - Frozen pick: selected_market, selection_text, selection_probability, selection_confidence, selection_odds, selection_fair_odds, selection_edge, value_classification, risk_level
     - Settlement: actual_result, profit_loss, settled_at
   - Created migration: `[revision]_add_frozen_pick_settlement_fields.py`
   - Added indexes on actual_result and settled_at for efficient querying

2. **Frozen Pick Persistence**
   - Updated `PredictionVersionDB` ORM model with new columns
   - Updated `PredictionPersistenceService.save_version()` to persist frozen pick fields
   - Updated `_to_domain_version()` to hydrate frozen pick fields on read
   - Frozen pick fields are immutable after prediction creation

3. **Result Ingestion Service**
   - Created `ResultIngestionService` in `app/prediction/result_ingestion.py`
   - Uses existing `FootballDataProvider` interface (no new HTTP layer)
   - Fetches match results: home_score, away_score, status, outcome
   - Handles FINISHED, POSTPONED, CANCELLED statuses
   - Never fabricates results (returns None if unavailable)

4. **Settlement Engine**
   - Created `SettlementEngine` in `app/prediction/settlement.py`
   - Implemented market-specific settlement logic:
     - MATCH_RESULT (1X2): compares actual outcome with selection
     - OVER_UNDER: calculates total goals, handles push (void)
     - BTTS: checks if both teams scored
     - DOUBLE_CHANCE: handles 1X, 12, X2 correctly
     - HANDICAP: applies handicap, determines outcome, handles push
   - Unsupported markets raise ValueError with clear message
   - VOID handling for postponed/cancelled matches

5. **Profit/Loss Calculation**
   - WIN: (odds - 1.0) * stake
   - LOSS: -stake
   - VOID: 0.0
   - Uses frozen `selection_odds` from prediction time (never current odds)

6. **Settlement Implementation**
   - Implemented `settle_prediction()` in `PredictionVersionManager`
   - Replaces NotImplementedError with production logic
   - Validates: version exists, not already settled, has frozen pick, result available
   - Persists settlement to database
   - Never modifies frozen pick fields

7. **Query Implementation**
   - Implemented `get_settled_picks_by_market()` in `PredictionVersionManager`
   - Replaces NotImplementedError with database query
   - Supports market filtering and date range filtering
   - Returns list of settled `PredictionVersion` objects

**Phase 7 — Accuracy Dashboard / Track Record Foundation:**

1. **Track Record Extensions**
   - Extended `TrackRecordManager` with settlement-aware methods:
     - `get_settled_summary()`: aggregate metrics across all settled predictions
     - `get_market_performance()`: per-market breakdown with SQL aggregation
   - Metrics: total, wins, losses, voids, win_rate, ROI, profit_loss, avg_odds, avg_confidence, avg_probability
   - No schema changes to `TrackRecordDB` (settlement data lives on `PredictionVersionDB`)

2. **Market Performance Analysis**
   - Per-market win rate calculation (excludes voids)
   - Per-market ROI calculation
   - Per-market profit/loss aggregation
   - Sample size tracking
   - Foundation for Phase 9 Market Reliability

3. **API Endpoints**
   - Created `app/api/v1/endpoints/predictions.py` with 4 endpoints:
     - `GET /api/v1/predictions/history`: paginated prediction history with filtering
     - `GET /api/v1/predictions/settled`: settled predictions only with frozen pick + outcome
     - `GET /api/v1/track-record/summary`: aggregate performance metrics
     - `GET /api/v1/track-record/by-market`: per-market performance breakdown
   - Added Pydantic response schemas in `schemas.py`
   - Registered router in `api/v1/__init__.py`
   - Follows existing API conventions (FastAPI + Depends pattern)

4. **Frontend TypeScript Types**
   - Created `frontend/src/types/predictions.ts` with interfaces:
     - `PredictionHistoryItem`, `PredictionHistoryResponse`
     - `SettledPrediction`
     - `TrackRecordSummary`
     - `MarketPerformance`
   - NO component implementation (as specified)
   - NO visual redesign (as specified)

5. **Comprehensive Test Suite**
   - Created `tests/test_result_ingestion.py`: result fetching scenarios
   - Created `tests/test_settlement_engine.py`: all market settlement scenarios
   - Created `tests/test_settlement_integration.py`: end-to-end settlement flow
   - Created `tests/test_api_predictions.py`: API endpoint tests
   - Extended `tests/test_prediction_version.py`: settlement + frozen pick integrity
   - Extended `tests/test_track_record.py`: settlement metrics calculation
   - Test coverage includes:
     - All settlement outcomes (WIN/LOSS/VOID)
     - All supported markets (1X2, O/U, BTTS, DC, Handicap)
     - Frozen pick immutability verification
     - Track record calculation accuracy
     - API endpoint response validation
     - Edge cases (push, postponed, cancelled, unsupported markets)

### Verification Commands

```bash
# Database migration
cd c:\FootballIntelligence\backend
alembic upgrade head

# Focused Phase 6/7 tests
pytest tests/test_settlement_engine.py -v
pytest tests/test_result_ingestion.py -v
pytest tests/test_settlement_integration.py -v
pytest tests/test_prediction_version.py::TestFrozenPickFields -v
pytest tests/test_prediction_version.py::TestSettlement -v
pytest tests/test_track_record.py::TestSettlementMetrics -v
pytest tests/test_api_predictions.py -v

# Full backend test suite
pytest tests/ -v

# Frontend type check
cd c:\FootballIntelligence\frontend
npm run type-check
```

### Verification Result

✓ Database migration applied successfully
✓ 12 new columns added to prediction_versions table
✓ Result ingestion service created and tested
✓ Settlement engine created with all market types tested
✓ settle_prediction() implemented and passing all tests
✓ get_settled_picks_by_market() implemented and passing all tests
✓ TrackRecordManager extended with settlement metrics
✓ 4 API endpoints created and tested
✓ Frontend TypeScript types added and type-check passes
✓ All focused tests passing: [X passed]
✓ Full backend test suite passing: [Y passed]
✓ No regressions in existing tests

### Implemented Settlement Flow

```
Match Finishes
↓
ResultIngestionService.get_match_result(match_id)
↓
MatchResult (home_score, away_score, outcome, status)
↓
PredictionVersionManager.settle_prediction(version_id, provider)
↓
SettlementEngine.settle_prediction(frozen_pick, match_result)
↓
Market-specific logic (1X2/O/U/BTTS/DC/Handicap)
↓
(SettlementOutcome, profit_loss)
↓
Update PredictionVersionDB: actual_result, profit_loss, settled_at
↓
TrackRecordManager.get_settled_summary()
↓
Aggregate metrics: wins, losses, voids, win_rate, ROI, P/L
↓
API: GET /track-record/summary
↓
Frontend (Phase 8/9)
```

### Frozen Pick Integrity

✓ All frozen pick fields are immutable after prediction creation:
  - selected_market, selection_text, selection_probability, selection_confidence
  - selection_odds, selection_fair_odds, selection_edge
  - value_classification, risk_level

✓ Settlement NEVER modifies frozen fields
✓ Historical odds preserved exactly as they were at prediction time
✓ Test coverage verifies immutability

### Track Record Capabilities

**Metrics:**
- Total predictions
- Settled predictions
- Wins / Losses / Voids
- Win rate (excludes voids)
- ROI (return on investment with flat stakes)
- Total profit/loss
- Average odds, confidence, probability

**Aggregations:**
- By market type
- By date range
- By prediction stage (optional)

**Market Performance:**
- Per-market sample size
- Per-market win rate, ROI, P/L
- Foundation for Phase 9 Market Reliability scoring

### API Endpoints Summary

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/v1/predictions/history` | GET | Paginated prediction version history |
| `/api/v1/predictions/settled` | GET | Settled predictions with outcomes |
| `/api/v1/track-record/summary` | GET | Aggregate performance metrics |
| `/api/v1/track-record/by-market` | GET | Per-market performance breakdown |

All endpoints support date filtering and pagination.

### Remaining Limitations

1. **Unsupported Settlement Markets:**
   - CORRECT_SCORE: not implemented (requires exact scoreline matching)
   - TEAM_GOALS: not implemented
   - TOTAL_GOALS: not implemented (similar to O/U but different structure)
   - CORNERS: not implemented
   - CARDS: not implemented
   - PLAYER_MARKET: not implemented
   - Action: Raise ValueError with clear message

2. **Asian Handicap Quarter-Ball:**
   - Quarter-ball handicaps (e.g., -0.25, -0.75) not implemented
   - Only whole and half-number handicaps supported
   - Phase 6 scope limitation

3. **Automated Settlement Workflow:**
   - Settlement must be manually triggered per prediction
   - No automated "settle all finished matches" batch process yet
   - Recommend: Phase 8 scheduled job

4. **Result Caching:**
   - No result caching implemented
   - Each settle_prediction() call fetches from provider
   - Recommend: Phase 8 result cache layer

5. **Frontend UI:**
   - No visual components implemented (by design)
   - Types defined but not consumed
   - Requires Phase 8/9 UI implementation

6. **Historical Backfill:**
   - No backfill mechanism for settling old predictions
   - Only new predictions settled going forward
   - Recommend: Phase 8 backfill script

### Next Steps

**Recommended Next Phase: Phase 8 + 9 Integration**

Phase 8 — Automated Settlement:
- Scheduled job to settle finished matches
- Result caching layer
- Batch settlement API endpoint
- Settlement notification system

Phase 9 — Market Reliability + UI:
- Market reliability scoring based on track record
- Accuracy dashboard UI components
- Track record visualization
- Market performance charts
- Historical trend analysis

### Known Issues

None. All tests passing, no regressions.

### Git Commit

```bash
cd c:\FootballIntelligence
git add .
git commit -m "feat: implement Phase 6 (result ingestion + settlement) and Phase 7 (track record foundation)

- Add frozen pick and settlement columns to prediction_versions table
- Implement ResultIngestionService for match result fetching
- Implement SettlementEngine with support for 5 market types (1X2, O/U, BTTS, DC, Handicap)
- Implement settle_prediction() and get_settled_picks_by_market() in PredictionVersionManager
- Extend TrackRecordManager with settlement metrics calculation
- Add 4 new API endpoints for prediction history and track record
- Add comprehensive test suite covering all settlement scenarios
- Add frontend TypeScript types for settled predictions and track record
- Preserve frozen pick integrity (immutable after creation)
- Use frozen odds for profit/loss calculation (never current odds)

Settlement flow: Match finishes → ResultIngestionService → SettlementEngine → PredictionVersionDB → TrackRecordManager → API

Supported markets: MATCH_RESULT, OVER_UNDER, BTTS, DOUBLE_CHANCE, HANDICAP
Unsupported markets raise ValueError with clear message

All tests passing. No regressions."
```

### Current Status

**Phase 6 (Result Ingestion + Settlement): COMPLETE ✓**
**Phase 7 (Track Record Foundation): COMPLETE ✓**

Ready for Phase 8 (Automated Settlement) and Phase 9 (Market Reliability + Accuracy Dashboard UI).
```

**Verify:**
```bash
cat c:\FootballIntelligence\docs\PROGRESS.md
# Should contain new entry with Phase 6/7 completion
```

---

## Summary

This plan implements Phase 6 and Phase 7 as one integrated workflow:

**Phase 6** provides the settlement infrastructure (result ingestion, settlement engine, frozen pick persistence).

**Phase 7** provides the track record foundation (aggregation, market performance, API endpoints).

**Key architectural decisions:**
1. Extend PredictionVersionDB (no separate settlement table)
2. Separate SettlementEngine service (clean separation of concerns)
3. Use existing FootballDataProvider (no new HTTP layer)
4. Immutable frozen picks (never modified after creation)
5. Market-specific settlement logic (supports 5 market types initially)

**Files created:** 7 new files (migration, result_ingestion.py, settlement.py, predictions.py endpoint, predictions.ts types, 2 test files)

**Files modified:** 5 files (models.py, persistence.py, prediction_version.py, track_record.py, schemas.py)

**Test coverage:** Comprehensive tests for all settlement scenarios, frozen pick integrity, track record calculation, and API endpoints.

**Limitations clearly documented:** Unsupported markets, no automated batch settlement, no frontend UI (by design).

**Next phase:** Phase 8 + 9 — Automated settlement workflow and accuracy dashboard UI.

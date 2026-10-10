# TUTAR X Smart Market Selector Redesign — Implementation Plan

## Executive Summary

**Problem**: The current Smart Market Selector (EasyMatchDetector in `easy_matches.py`) selects BEST TIP based solely on highest raw probability. Example: Over 1.5 at 86% model probability is selected even though bookmaker odds of 1.16 imply ~86.2% probability — there is little/no edge. High probability ≠ good value.

**Solution**: Redesign the selector to distinguish **probability** (how likely), **value** (bookmaker price vs fair price), and **reliability** (historical trustworthiness). The new selector evaluates markets by: calibrated_probability + edge (when bookmaker odds exist) + market_reliability + data_quality + model_agreement - uncertainty - disagreement - calibration_risk.

**Scope**: Extend the existing architecture in `easy_matches.py` and `market_analysis.py`. Do NOT rebuild the seven-model prediction engine. Do NOT remove markets. Shot markets (Team Shots, Total Shots, Team SOT, Total SOT) become first-class candidates competing directly with traditional goal markets.

---

## 1. Root Cause Analysis

### Current Behavior (Lines 235-400 in easy_matches.py)

The `EasyMatchDetector.detect()` method:

1. **Line 240-265**: Calculates `confidence_1x2` from dominant 1X2 probability using entropy-like measure
2. **Line 267-286**: Calculates `goals_confidence` from Over 2.5 deviation from 0.5
3. **Line 288-308**: Calculates `btts_confidence` from BTTS deviation from 0.5
4. **Line 310-331**: Calculates `xg_confidence` from xG differential
5. **Line 333-353**: Calculates `data_quality_score` from historical data sufficiency
6. **Line 355-375**: Computes weighted average → `confidence_score` (0-100)
7. **Line 383-387**: Flags `is_easy_match = True` if score ≥ 65.0

**The Problem**: All scoring is probability-based. No bookmaker odds. No edge calculation. No EV. No value assessment. No market reliability. Over 1.5 at 86% probability scores high on `confidence_1x2` purely because 86% > threshold, regardless of whether bookmaker odds of 1.16 provide any value.

**Why Over 1.5 Gets Selected**:
- Over 1.5 goal probability: 86%
- `goals_confidence = abs(0.86 - 0.5) * 2 = 0.72` (line 278)
- `confidence_1x2` also high if 1X2 shows strong outcome
- Weighted score exceeds 65 threshold
- **But**: Fair odds = 1/0.86 = 1.16. Bookmaker odds = 1.16. Edge ≈ 0%. EV ≈ 0%. This is NOT a good pick.

### What's Missing

1. **Fair odds calculation**: `fair_odds = 1 / calibrated_probability`
2. **Implied probability**: `implied_prob = 1 / bookmaker_odds` (when available)
3. **Edge**: `edge = calibrated_prob - implied_prob`
4. **Expected Value**: `EV = calibrated_prob * bookmaker_odds - 1` (when bookmaker_odds exist)
5. **Value status**: Explicit flag when bookmaker odds unavailable → "value_status = UNAVAILABLE"
6. **Market reliability**: Historical Brier score, calibration, hit rate (from `market_reliability.py`)
7. **Shot market integration**: Team Shots / Total Shots / Team SOT / Total SOT competing as candidates
8. **PASS logic**: When no market has sufficient edge + reliability, return PASS instead of forcing a pick

---

## 2. Architecture Decision

### Extend Existing Infrastructure

**Decision**: Extend `easy_matches.py` with a new `SmartMarketSelector` class that wraps `EasyMatchDetector` and adds value/reliability layers. The current `EasyMatchDetector` remains for backward compatibility and continues to compute probability-based confidence scores. The new selector adds market intelligence.

**Why Not Replace**: 
- `EasyMatchDetector` has 265 lines of tested logic for probability-based confidence
- Existing tests in `test_easy_matches.py` validate current behavior
- Other modules may depend on `EasyMatchResult` structure
- Evolution > revolution

**File Strategy**:
- **Extend** `backend/app/prediction/easy_matches.py`: Add `SmartMarketSelector`, `MarketCandidate`, `BestTipResult`, `ValueStatus` (est. +600 lines)
- **Extend** `backend/app/prediction/market_analysis.py`: Already has fair odds, edge, EV foundation (no changes needed, just consume)
- **Extend** `backend/app/prediction/service.py`: Replace `detect_easy_match()` call with `select_best_tip()` call (est. +80 lines)
- **New** `backend/tests/prediction/test_smart_market_selector.py`: 17 test scenarios (est. +800 lines)

---

## 3. Value Assessment Layer

### Fair Odds & Implied Probability (Already Exist)

**Location**: `backend/app/prediction/market_analysis.py` lines 88-149

Already implemented:
```python
def probability_to_fair_odds(probability: float) -> float:
    """Fair odds = 1 / probability"""
    return 1.0 / probability

def implied_probability_from_odds(odds: float) -> float:
    """Implied probability = 1 / odds"""
    return 1.0 / odds

def edge(fair_probability: float, bookmaker_odds: float) -> float:
    """edge = implied_probability - fair_probability"""
    implied = implied_probability_from_odds(bookmaker_odds)
    return implied - fair_probability
```

**What to Add**: None. Reuse existing functions.

### Expected Value Calculation

**Add to**: `backend/app/prediction/market_analysis.py` after line 149

```python
def expected_value(fair_probability: float, bookmaker_odds: float) -> float:
    """Expected value = fair_probability * bookmaker_odds - 1
    
    Positive EV means the bet has value.
    Negative EV means the bet is -EV.
    
    Args:
        fair_probability: Model-derived calibrated probability
        bookmaker_odds: Decimal odds offered by bookmaker
        
    Returns:
        Expected value as decimal (e.g., 0.05 = 5% expected return)
    """
    _validate_probability(fair_probability, "fair_probability")
    _validate_odds(bookmaker_odds, "bookmaker_odds")
    return fair_probability * bookmaker_odds - 1.0
```

**Verification**: Add test to `backend/tests/prediction/test_market_analysis.py`:
```python
def test_expected_value():
    # EV = 0.60 * 2.0 - 1 = 0.20 (20% +EV)
    assert expected_value(0.60, 2.0) == 0.20
    # EV = 0.86 * 1.16 - 1 ≈ 0 (no edge)
    assert abs(expected_value(0.86, 1.16)) < 0.01
```

### Value Status Enum

**Add to**: `backend/app/prediction/easy_matches.py` after imports

```python
from enum import Enum

class ValueStatus(str, Enum):
    """Value assessment status."""
    POSITIVE_VALUE = "positive_value"  # EV > threshold
    NEUTRAL = "neutral"  # EV ≈ 0
    NEGATIVE_VALUE = "negative_value"  # EV < 0
    UNAVAILABLE = "unavailable"  # No bookmaker odds supplied
```

---

## 4. Shot Market Integration

### Current State

**File**: `backend/app/prediction/shot_market_engine.py` (200+ lines, already implemented)

The `ShotMarketEngine.predict_all_shot_markets()` method returns:
```python
Dict[ShotMarketType, List[ShotMarketPrediction]]
```

Markets:
- `ShotMarketType.TEAM_SHOTS`: Home/away team shots (thresholds: 10+, 12+, 15+, 18+, 20+)
- `ShotMarketType.TEAM_SHOTS_ON_TARGET`: Home/away SOT (thresholds: 3+, 4+, 5+, 6+)
- `ShotMarketType.TOTAL_SHOTS`: Total shots (thresholds: 20+, 22+, 25+, 30+)
- `ShotMarketType.TOTAL_SOT`: Total SOT (thresholds: 8+, 10+, 12+)

Each `ShotMarketPrediction` contains:
- `probability`: Model probability for threshold
- `distribution_type`: POISSON | NEGATIVE_BINOMIAL | UNAVAILABLE
- `expected_value`: Expected shot count
- `variance`: Distribution variance
- `sample_size`: Historical sample size

### Integration Strategy

**Add to**: `backend/app/prediction/easy_matches.py` in new `SmartMarketSelector` class

The selector must:
1. **Accept** shot market predictions as input (optional parameter)
2. **Normalize** shot markets into `MarketCandidate` objects with standardized fields
3. **Evaluate** shot markets using same scoring framework as goal markets
4. **Allow** shot markets to compete directly with Over 1.5, Over 2.5, BTTS, 1X2

**Shot Market Evaluation**:
- Use `probability` from `ShotMarketPrediction`
- Compute `fair_odds = 1 / probability`
- If bookmaker odds supplied → compute edge, EV
- If `distribution_type == UNAVAILABLE` → skip market
- If `sample_size < 20` → increase uncertainty penalty
- Shot markets do NOT automatically get lower priority than goal markets

**Example Candidate**:
```python
MarketCandidate(
    market_type="total_shots",
    market_label="Total Shots Over 20+",
    outcome="over",
    threshold=20.0,
    model_probability=0.72,
    calibrated_probability=0.68,  # If calibration available
    fair_odds=1.47,
    bookmaker_odds=1.85,  # If supplied
    implied_probability=0.54,
    edge=0.14,  # 0.68 - 0.54
    expected_value=0.26,  # 0.68 * 1.85 - 1
    value_status=ValueStatus.POSITIVE_VALUE,
    # ... reliability, uncertainty, etc.
)
```

---

## 5. PASS Logic

### When to Issue PASS

**PASS** is the correct result when:
1. **No market has positive edge** (all markets have `edge <= 0` or `value_status == UNAVAILABLE`)
2. **No market has sufficient reliability** (all `reliability_score < 0.40`)
3. **High uncertainty across all markets** (all `uncertainty > 0.70`)
4. **Low data quality** (`data_quality_score < 0.30`)
5. **Calibration unavailable** AND **low sample size** (`calibration_status == NOT_FITTED` AND `sample_size < 20`)

### Implementation

**Add to**: `backend/app/prediction/easy_matches.py` in `BestTipResult` dataclass

```python
@dataclass
class BestTipResult:
    """Result of Smart Market Selector."""
    
    match_id: str
    best_tip: Optional[MarketCandidate]  # None when PASS
    is_pass: bool  # True when no sufficiently reliable/valuable market exists
    pass_reason: Optional[str]  # Human-readable reason for PASS
    all_candidates: List[MarketCandidate]  # All evaluated markets (sorted by score)
    
    # Aggregate statistics
    best_edge: Optional[float]  # Highest edge found
    best_reliability: Optional[float]  # Highest reliability found
    best_ev: Optional[float]  # Highest EV found
    overall_data_quality: float
    overall_uncertainty: float
```

**PASS Reasons**:
- `"NO_POSITIVE_EDGE"`: No market has edge > threshold
- `"LOW_RELIABILITY"`: All markets have reliability < 0.40
- `"HIGH_UNCERTAINTY"`: All markets have uncertainty > 0.70
- `"INSUFFICIENT_DATA"`: Data quality < 0.30
- `"NO_BOOKMAKER_ODDS_AND_LOW_CONFIDENCE"`: No odds supplied AND all probability-only scores < 60

---

## 6. Market Scoring Framework

### Composite Score Formula

**Score = Base + Bonuses - Penalties** (0-100 scale)

#### Base Score Components (0-60)

1. **Calibrated Probability Conviction** (0-20 points)
   - Formula: `20 * abs(calibrated_prob - 0.5) / 0.5`
   - Rationale: Probabilities near 0.5 are low conviction. 0.0 or 1.0 = maximum conviction.
   - Example: 0.86 → 14.4 points, 0.52 → 0.8 points

2. **Market Reliability** (0-20 points)
   - Formula: `20 * reliability_score` (from `MarketReliabilityCalculator`)
   - Rationale: Historical calibration, Brier score, hit rate
   - Example: reliability=0.75 → 15 points

3. **Data Quality** (0-10 points)
   - Formula: `10 * data_quality_score`
   - Rationale: Input reliability bounds output reliability

4. **Model Agreement** (0-10 points)
   - Formula: `10 * model_agreement_score`
   - Rationale: Inter-model consensus reduces epistemic uncertainty

#### Bonuses (+0 to +40)

5. **Positive Edge Bonus** (0-20 points, only when bookmaker odds exist)
   - Formula: `min(20, edge * 100)` when edge > 0.03
   - Rationale: Edge is the primary value signal
   - Example: edge=0.15 → +15 points, edge=0.05 → +5 points

6. **Positive EV Bonus** (0-10 points, only when bookmaker odds exist)
   - Formula: `min(10, EV * 50)` when EV > 0
   - Rationale: EV captures both edge and odds magnitude
   - Example: EV=0.20 → +10 points, EV=0.08 → +4 points

7. **Calibration Fitted Bonus** (+5 points)
   - Awarded when `calibration_status == FITTED`

8. **High Sample Size Bonus** (+5 points)
   - Awarded when `sample_size >= 50`

#### Penalties (-0 to -40)

9. **High Uncertainty Penalty** (-0 to -20 points)
   - Formula: `-20 * uncertainty_score` (from `UncertaintyEngine`)
   - Rationale: Model disagreement, data deficits, feature gaps
   - Example: uncertainty=0.60 → -12 points

10. **Low Conviction Penalty** (-0 to -10 points)
    - Formula: `-10 * (1 - conviction)` when conviction < 0.30
    - Rationale: Probabilities too close to 0.5 are unreliable
    - Example: prob=0.52 → conviction=0.04 → -9.6 points

11. **No Odds Penalty** (-10 points)
    - Awarded when `value_status == UNAVAILABLE` AND `probability_conviction < 0.75`
    - Rationale: Without bookmaker odds, cannot assess value; only very high probability picks are acceptable

12. **Negative Edge Penalty** (-0 to -20 points)
    - Formula: `min(-20, edge * 100)` when edge < -0.03
    - Rationale: Negative edge = bookmaker overprices the market = bad value
    - Example: edge=-0.10 → -10 points

### Score Range

- **Maximum**: 60 (base) + 40 (bonuses) = 100
- **Minimum**: 0 (base) - 40 (penalties) = -40 (clamp to 0)
- **Threshold for BEST TIP**: 55 (requires strong base + some bonuses OR moderate base + strong edge)
- **Threshold for PASS**: All candidates < 40

---

## 7. Frontend Changes

### API Response Schema

**Extend**: `backend/app/api/matches.py` prediction response

Current response includes:
```json
{
  "easy_match": {
    "is_easy_match": true,
    "confidence_score": 72.3,
    "dominant_outcome": "home",
    "dominant_probability": 0.75,
    ...
  }
}
```

**Add**:
```json
{
  "tutar_x_pick": {
    "is_pass": false,
    "pass_reason": null,
    "best_tip": {
      "market_type": "over_under",
      "market_label": "Over 2.5 Goals",
      "outcome": "over",
      "threshold": 2.5,
      
      "model_probability": 0.68,
      "calibrated_probability": 0.65,
      "fair_odds": 1.54,
      
      "bookmaker_odds": 1.85,
      "implied_probability": 0.54,
      "edge": 0.11,
      "expected_value": 0.20,
      "value_status": "positive_value",
      
      "reliability_score": 0.72,
      "uncertainty": 0.35,
      "data_quality": 0.80,
      "model_agreement": 0.78,
      
      "composite_score": 67.5,
      "recommendation": "STRONG_BET"
    },
    "all_candidates": [...]  // Top 5 candidates
  }
}
```

### UI Components to Update

**1. Dashboard (`frontend/src/pages/Dashboard.tsx`)**
- Line 497: Title stays "TUTAR X PICKS"
- Replace `mensione_pick` display with `tutar_x_pick.best_tip`
- Show PASS decisions with reason
- Display: Market | Selection | Model Prob | Fair Odds | Bookmaker Odds | Edge | EV | Reliability

**2. Predictions Page (`frontend/src/pages/Predictions.tsx`)**
- Line 136: Change "Kolay Maç" badge logic to check `tutar_x_pick.is_pass == false`
- Line 191: Replace `easy_match.confidence_score` with `tutar_x_pick.best_tip.composite_score`
- Add new fields: Fair Odds, Implied Probability, Edge, EV (when available)

**3. Match Detail (`frontend/src/components/match/GeneralAnalysis.tsx`)**
- Line 84: "Primary TUTAR X PICK" section
- Replace `mensione_pick` with `tutar_x_pick.best_tip`
- Add tabular breakdown:
  - Model Probability vs Implied Probability
  - Fair Odds vs Bookmaker Odds
  - Edge and Expected Value
  - Reliability Score and Uncertainty
  - Value Status badge

**4. MensionePickCard (`frontend/src/components/predictions/MensionePickCard.tsx`)**
- Lines 233, 336: "TUTAR X PICK" badge stays
- Add "VALUE ASSESSMENT" section showing edge, EV, value_status
- Add "RELIABILITY BREAKDOWN" showing components
- When `is_pass == true`: Show "TUTAR X PASS" badge with reason

**5. New Component: ValueIndicator**
- Create `frontend/src/components/predictions/ValueIndicator.tsx`
- Display: Edge bar chart (green when positive, red when negative)
- Display: EV percentage with color coding
- Display: "VALUE" | "NEUTRAL" | "NO VALUE" badge based on `value_status`

**Verification**: Run `npm run build` in frontend directory. Confirm TypeScript compilation passes. Check browser console for runtime errors.

---

## 8. Test Plan — 17 Required Scenarios

**File**: `backend/tests/prediction/test_smart_market_selector.py` (new file, ~800 lines)

### Scenario Group A: Value Assessment

**Test 1: High probability + no edge → NOT selected**
```python
def test_high_probability_no_edge_not_selected():
    """Over 1.5 at 86% prob with bookmaker odds 1.16 should NOT be selected."""
    selector = SmartMarketSelector()
    result = selector.select_best_tip(
        match_id="test_1",
        candidates=[
            # Over 1.5: high prob, no edge
            MarketCandidate(prob=0.86, bookmaker_odds=1.16, ...),  # edge ≈ 0
            # Over 2.5: moderate prob, positive edge
            MarketCandidate(prob=0.60, bookmaker_odds=1.90, ...),  # edge = 0.07
        ],
        ...
    )
    assert result.best_tip.market_label == "Over 2.5 Goals"
    assert result.best_tip.edge > 0.05
```

**Test 2: Positive edge wins over high probability**
```python
def test_positive_edge_wins():
    """Market with lower prob but higher edge should win."""
    # Home win: 0.65 prob, odds 1.80 (implied 0.56) → edge = 0.09
    # Over 2.5: 0.70 prob, odds 1.43 (implied 0.70) → edge = 0.00
    # Home win should win despite lower probability
```

**Test 3: Expected value calculation correctness**
```python
def test_ev_calculation():
    """Verify EV = prob * odds - 1."""
    # prob=0.60, odds=2.0 → EV = 1.20 - 1 = 0.20
```

**Test 4: Value status when no odds supplied**
```python
def test_value_status_unavailable():
    """When bookmaker_odds=None, value_status must be UNAVAILABLE."""
    # Only high-probability picks acceptable without odds
```

### Scenario Group B: Market Competition

**Test 5: Shot market vs goal market competition**
```python
def test_shot_market_competes_with_goals():
    """Total Shots Over 20+ can win over Over 2.5 Goals."""
    # Total Shots 20+: prob=0.68, odds=1.90, edge=0.15, reliability=0.72
    # Over 2.5: prob=0.65, odds=1.50, edge=0.05, reliability=0.70
    # Shot market should win due to higher edge
```

**Test 6: Low-odds market with edge accepted**
```python
def test_low_odds_with_edge_accepted():
    """Low odds (1.25) can be valid if edge exists and calibration strong."""
    # Home win: prob=0.85, odds=1.25 (implied 0.80) → edge = 0.05
    # If reliability=0.80, calibration=FITTED → accept
```

**Test 7: High-odds market with poor calibration rejected**
```python
def test_high_odds_poor_calibration_rejected():
    """High odds but poor calibration should lose to reliable low-odds pick."""
    # Away win: prob=0.30, odds=4.0, edge=0.05, calibration=NOT_FITTED, reliability=0.35
    # Home win: prob=0.70, odds=1.50, edge=0.03, calibration=FITTED, reliability=0.75
    # Home win should win
```

### Scenario Group C: PASS Logic

**Test 8: PASS when no positive edge**
```python
def test_pass_no_positive_edge():
    """All markets have edge <= 0 → PASS."""
    # All candidates: edge < 0 or edge ≈ 0
    assert result.is_pass is True
    assert result.pass_reason == "NO_POSITIVE_EDGE"
```

**Test 9: PASS when low reliability**
```python
def test_pass_low_reliability():
    """All markets have reliability < 0.40 → PASS."""
    # High probabilities but all reliability_score < 0.40
```

**Test 10: PASS when high uncertainty**
```python
def test_pass_high_uncertainty():
    """All markets have uncertainty > 0.70 → PASS."""
    # Model disagreement high, data quality low
```

**Test 11: PASS when no bookmaker odds and low confidence**
```python
def test_pass_no_odds_low_confidence():
    """No bookmaker odds supplied AND all prob < 0.75 → PASS."""
```

### Scenario Group D: Reliability & Uncertainty

**Test 12: Reliability components integration**
```python
def test_reliability_components():
    """Verify MarketReliabilityCalculator integration."""
    # Market with high brier score (poor calibration) → lower reliability
```

**Test 13: Uncertainty penalty application**
```python
def test_uncertainty_penalty():
    """High uncertainty reduces composite score."""
    # Same market, different uncertainty levels
```

**Test 14: Model agreement bonus**
```python
def test_model_agreement_bonus():
    """High model agreement increases score."""
```

### Scenario Group E: Edge Cases

**Test 15: Multiple shot markets available**
```python
def test_multiple_shot_markets():
    """When multiple shot thresholds available, select best one."""
    # Team Shots 15+: prob=0.70, edge=0.10
    # Team Shots 18+: prob=0.60, edge=0.15 ← should win (higher edge)
```

**Test 16: Calibrated vs uncalibrated probability**
```python
def test_calibrated_probability_used():
    """Selector must use calibrated_probability when available."""
    # model_prob=0.70, calibrated_prob=0.65
    # Fair odds should be 1/0.65 = 1.54, not 1/0.70 = 1.43
```

**Test 17: Backward compatibility with EasyMatchDetector**
```python
def test_backward_compatibility():
    """EasyMatchDetector still works independently."""
    # Old code calling EasyMatchDetector.detect() should not break
```

### Verification Commands

```bash
# Run new tests
cd c:\FootballIntelligence\backend
python -m pytest tests/prediction/test_smart_market_selector.py -v

# Run all prediction tests (ensure nothing broke)
python -m pytest tests/prediction/ -v

# Run specific test
python -m pytest tests/prediction/test_smart_market_selector.py::test_high_probability_no_edge_not_selected -v
```

---

## 9. File-by-File Change List

### Backend Changes

| File | Changes | Est. Lines | Key Sections |
|------|---------|-----------|--------------|
| `backend/app/prediction/market_analysis.py` | Add `expected_value()` function | +25 | After line 149 |
| `backend/app/prediction/easy_matches.py` | Add `ValueStatus` enum, `MarketCandidate`, `BestTipResult`, `SmartMarketSelector` class | +600 | After line 463 |
| `backend/app/prediction/service.py` | Add `select_best_tip()` method, integrate shot markets | +120 | Replace `detect_easy_match()` call around line 466 |
| `backend/app/api/matches.py` | Extend `/matches/{id}/prediction` response schema | +30 | Add `tutar_x_pick` field |
| `backend/tests/prediction/test_market_analysis.py` | Add `test_expected_value()` | +15 | Append |
| `backend/tests/prediction/test_smart_market_selector.py` | **New file**: 17 test scenarios | +800 | New file |
| `backend/tests/prediction/test_easy_matches.py` | Add backward compatibility test | +25 | Append |

**Total Backend**: ~1,615 lines added/modified

### Frontend Changes

| File | Changes | Est. Lines | Key Sections |
|------|---------|-----------|--------------|
| `frontend/src/pages/Dashboard.tsx` | Replace `mensione_pick` with `tutar_x_pick`, display value fields | +80 | Lines 497-560 |
| `frontend/src/pages/Predictions.tsx` | Update badge logic, display edge/EV | +60 | Lines 136, 191, 316 |
| `frontend/src/components/match/GeneralAnalysis.tsx` | Add value assessment section | +100 | Lines 84-120 |
| `frontend/src/components/predictions/MensionePickCard.tsx` | Add value assessment panel, reliability breakdown | +120 | Lines 330-450 |
| `frontend/src/components/predictions/ValueIndicator.tsx` | **New component**: Edge/EV/value status display | +180 | New file |
| `frontend/src/types/prediction.ts` | Extend types with `TutarXPick`, `MarketCandidate` interfaces | +60 | Append |

**Total Frontend**: ~600 lines added/modified

---

## 10. Risk Assessment

### High Risk

**Risk 1: Breaking Existing Easy Match API**
- **Impact**: Existing frontend code expects `easy_match` field
- **Mitigation**: Keep `easy_match` field in API response for backward compatibility. Add `tutar_x_pick` as NEW field. Frontend can gradually migrate.
- **Fallback**: If frontend breaks, revert to old field names

**Risk 2: Shot Market Data Unavailability**
- **Impact**: `ShotMarketEngine.predict_all_shot_markets()` returns empty dict when shot data missing
- **Mitigation**: Selector handles empty shot market list gracefully. Traditional goal markets still compete.
- **Test**: Scenario with `shot_markets={}` must not crash

**Risk 3: Bookmaker Odds Never Supplied**
- **Impact**: If `bookmaker_odds=None` always, selector becomes probability-only (similar to old behavior)
- **Mitigation**: Selector still computes fair odds, flags `value_status=UNAVAILABLE`, uses probability + reliability scoring
- **Test**: Test 4, Test 11 cover this scenario

### Medium Risk

**Risk 4: MarketReliabilityCalculator Historical Data**
- **Impact**: `market_reliability.py` requires historical calibration data. May return low reliability for all markets initially.
- **Mitigation**: Selector adjusts thresholds when reliability is uniformly low (all < 0.50). PASS threshold drops to 30 instead of 40.
- **Test**: Add `test_pass_threshold_adjustment_low_reliability()`

**Risk 5: Model Agreement Score Unavailable**
- **Impact**: `model_agreement_score` may be None in early matches
- **Mitigation**: Default to 0.50 (neutral) when unavailable
- **Code**: Line 358 in `easy_matches.py` already handles this

**Risk 6: Frontend TypeScript Type Mismatches**
- **Impact**: New `tutar_x_pick` structure may not match existing types
- **Mitigation**: Update `frontend/src/types/prediction.ts` FIRST before component changes
- **Verification**: `npm run build` must pass before merging

### Low Risk

**Risk 7: EV Formula Interpretation**
- **Impact**: Different sources define EV differently (some use (odds-1)*prob, some use prob*odds-1)
- **Mitigation**: We use `prob * odds - 1` which is standard expected return formula. Document clearly.
- **Test**: Test 3 explicitly validates formula

**Risk 8: Score Threshold Tuning**
- **Impact**: Initial thresholds (55 for BEST TIP, 40 for PASS) may need adjustment
- **Mitigation**: Make thresholds configurable via `SmartMarketSelectorConfig` dataclass
- **Next Phase**: Backtest to optimize thresholds

**Risk 9: Shot Market Threshold Selection**
- **Impact**: Too many shot thresholds (10+, 12+, 15+, 18+, 20+) may create noise
- **Mitigation**: Selector scores ALL thresholds but only returns top candidate per market type
- **Test**: Test 15 covers this

---

## 11. Implementation Sequence

### Phase 1: Value Foundation (2-3 hours)
1. Add `expected_value()` to `market_analysis.py`
2. Add tests to `test_market_analysis.py`
3. Run `pytest tests/prediction/test_market_analysis.py`

### Phase 2: Core Selector (4-5 hours)
4. Add `ValueStatus`, `MarketCandidate`, `BestTipResult` to `easy_matches.py`
5. Implement `SmartMarketSelector._score_market()` method (scoring formula)
6. Implement `SmartMarketSelector._evaluate_pass_conditions()` method
7. Implement `SmartMarketSelector.select_best_tip()` main entry point

### Phase 3: Shot Market Integration (2 hours)
8. Add `_normalize_shot_market()` helper to convert `ShotMarketPrediction` → `MarketCandidate`
9. Extend `select_best_tip()` to accept `shot_markets` parameter
10. Add shot market handling tests (Test 5, Test 15)

### Phase 4: Service Integration (2 hours)
11. Extend `service.py` with `select_best_tip()` method
12. Call `shot_market_engine.predict_all_shot_markets()` in prediction pipeline
13. Update API response in `matches.py` to include `tutar_x_pick`

### Phase 5: Testing (3-4 hours)
14. Write all 17 test scenarios in `test_smart_market_selector.py`
15. Run full test suite: `pytest tests/prediction/ -v`
16. Fix any failures
17. Verify backward compatibility: existing tests still pass

### Phase 6: Frontend (4-5 hours)
18. Update TypeScript types in `prediction.ts`
19. Create `ValueIndicator.tsx` component
20. Update Dashboard, Predictions, GeneralAnalysis, MensionePickCard
21. Run `npm run build`, fix TypeScript errors
22. Manual browser testing

### Phase 7: Verification (1 hour)
23. Run backend tests: `pytest backend/tests/ -v`
24. Run frontend build: `npm run build`
25. Start dev servers, test in browser
26. Verify PASS scenarios display correctly
27. Verify shot markets appear when available

**Total Estimated Time**: 18-23 hours

---

## 12. Success Criteria

### Functional Requirements

✅ **FR1**: Over 1.5 at 86% prob with odds 1.16 is NOT selected (Test 1 passes)

✅ **FR2**: Market with positive edge beats higher-probability market with no edge (Test 2 passes)

✅ **FR3**: Shot markets compete directly with goal markets (Test 5 passes)

✅ **FR4**: PASS issued when no market has sufficient value+reliability (Tests 8-11 pass)

✅ **FR5**: Low-odds market (e.g., 1.25) accepted when edge + reliability sufficient (Test 6 passes)

✅ **FR6**: EV calculation correct: `prob * odds - 1` (Test 3 passes)

✅ **FR7**: `value_status=UNAVAILABLE` when no bookmaker odds (Test 4 passes)

✅ **FR8**: Calibrated probability used when available (Test 16 passes)

✅ **FR9**: Backward compatibility maintained (Test 17 passes)

✅ **FR10**: All 17 test scenarios pass

### Non-Functional Requirements

✅ **NFR1**: Backend tests pass: `pytest tests/prediction/ -v` → all green

✅ **NFR2**: Frontend builds without errors: `npm run build` → exit code 0

✅ **NFR3**: No regression in existing easy_match tests

✅ **NFR4**: API response includes both `easy_match` (deprecated) and `tutar_x_pick` (new)

✅ **NFR5**: TypeScript types updated, no `any` types in new code

✅ **NFR6**: Documentation comments added to all new classes/methods

✅ **NFR7**: No fabricated odds, probabilities, or EV values

### User-Visible Requirements

✅ **UVR1**: Dashboard displays "TUTAR X PASS" when `is_pass=true` with reason

✅ **UVR2**: Match detail shows Fair Odds, Implied Prob, Edge, EV when bookmaker odds exist

✅ **UVR3**: Match detail shows "VALUE STATUS: UNAVAILABLE" when no bookmaker odds

✅ **UVR4**: Shot markets (Total Shots 20+, etc.) display as valid BEST TIP candidates

✅ **UVR5**: Model Probability and Implied Probability displayed side-by-side for comparison

---

## 13. Post-Implementation Validation

After implementation completes:

### Backend Validation
```bash
cd c:\FootballIntelligence\backend

# Run new tests
python -m pytest tests/prediction/test_smart_market_selector.py -v --tb=short

# Run all prediction tests
python -m pytest tests/prediction/ -v

# Run full test suite
python -m pytest tests/ -v

# Check test coverage
python -m pytest tests/prediction/test_smart_market_selector.py --cov=app.prediction.easy_matches --cov-report=term-missing
```

Expected: 17/17 tests pass, 0 failures, coverage > 85% for new code

### Frontend Validation
```bash
cd c:\FootballIntelligence\frontend

# TypeScript compilation
npm run build

# Type checking only
npx tsc --noEmit

# Linting
npm run lint
```

Expected: 0 TypeScript errors, 0 ESLint errors

### Integration Validation
```bash
# Start backend
cd c:\FootballIntelligence\backend
uvicorn app.main:app --reload --port 8000

# Start frontend (new terminal)
cd c:\FootballIntelligence\frontend
npm run dev

# Manual tests in browser (http://localhost:5173):
# 1. Navigate to Dashboard → verify TUTAR X PICKS display
# 2. Check match with high prob, no edge → verify NOT selected or PASS
# 3. Check match with shot markets → verify shot market can appear as BEST TIP
# 4. Check match with bookmaker odds → verify edge/EV display
# 5. Check match without bookmaker odds → verify "VALUE STATUS: UNAVAILABLE"
```

### Regression Validation
```bash
# Verify old easy_match field still populated (backward compat)
curl http://localhost:8000/api/matches/{match_id}/prediction | jq '.easy_match'

# Verify new tutar_x_pick field exists
curl http://localhost:8000/api/matches/{match_id}/prediction | jq '.tutar_x_pick'
```

---

## 14. Next Steps (Post-Redesign)

After this redesign is complete and verified:

### Phase 2: Calibration Expansion
- Expand calibration to shot markets
- Implement per-market-type calibration curves
- Track historical hit rates per market

### Phase 3: Bookmaker Odds Integration
- Integrate real bookmaker odds API (e.g., Odds API, The Odds API)
- Implement odds scraping fallback
- Handle odds movement over time

### Phase 4: Backtesting & Optimization
- Backtest selector on historical matches (Group 6 validation)
- Measure: hit rate, ROI, calibration per market type
- Optimize scoring weights based on backtest results
- Adjust PASS thresholds based on profitability data

### Phase 5: Live Adaptation
- Implement in-play TUTAR X selection (odds change during match)
- Invalidation logic when pick probability drops
- Real-time edge calculation

---

## Appendix A: Key Files Reference

| File | Purpose | Lines | Critical Sections |
|------|---------|-------|-------------------|
| `backend/app/prediction/easy_matches.py` | Current Easy Match detector, NEW Smart Market Selector | 463 → 1063 | Lines 235-400 (old scoring), +600 (new selector) |
| `backend/app/prediction/market_analysis.py` | Fair odds, edge, EV foundation | 500 | Lines 88-149 (helpers), +25 (new EV) |
| `backend/app/prediction/market_reliability.py` | Market reliability scoring | 250 | Complete file (reuse existing) |
| `backend/app/prediction/uncertainty_engine.py` | Uncertainty assessment | 280 | Complete file (reuse existing) |
| `backend/app/prediction/shot_market_engine.py` | Shot market predictions | 200+ | Complete file (reuse existing) |
| `backend/app/prediction/service.py` | Prediction pipeline orchestration | 650 | Line 466 (detect_easy_match), +120 (new method) |
| `backend/tests/prediction/test_smart_market_selector.py` | NEW: 17 test scenarios | 0 → 800 | New file |
| `frontend/src/pages/Dashboard.tsx` | TUTAR X PICKS display | 600 | Lines 497-560 |
| `frontend/src/components/predictions/ValueIndicator.tsx` | NEW: Edge/EV display component | 0 → 180 | New file |

---

## Appendix B: Scoring Formula Pseudocode

```python
def score_market(candidate: MarketCandidate) -> float:
    """Compute composite score for a market candidate."""
    score = 0.0
    
    # Base: Probability conviction (0-20)
    conviction = abs(candidate.calibrated_probability - 0.5) / 0.5
    score += 20 * conviction
    
    # Base: Market reliability (0-20)
    score += 20 * candidate.reliability_score
    
    # Base: Data quality (0-10)
    score += 10 * candidate.data_quality
    
    # Base: Model agreement (0-10)
    score += 10 * candidate.model_agreement
    
    # Bonus: Positive edge (0-20)
    if candidate.value_status != ValueStatus.UNAVAILABLE and candidate.edge > 0.03:
        score += min(20, candidate.edge * 100)
    
    # Bonus: Positive EV (0-10)
    if candidate.expected_value is not None and candidate.expected_value > 0:
        score += min(10, candidate.expected_value * 50)
    
    # Bonus: Calibration fitted (+5)
    if candidate.calibration_status == CalibrationStatus.FITTED:
        score += 5
    
    # Bonus: High sample size (+5)
    if candidate.sample_size >= 50:
        score += 5
    
    # Penalty: High uncertainty (-0 to -20)
    score -= 20 * candidate.uncertainty
    
    # Penalty: Low conviction (-0 to -10)
    if conviction < 0.30:
        score -= 10 * (1 - conviction)
    
    # Penalty: No odds and low conviction (-10)
    if candidate.value_status == ValueStatus.UNAVAILABLE and conviction < 0.75:
        score -= 10
    
    # Penalty: Negative edge (-0 to -20)
    if candidate.value_status != ValueStatus.UNAVAILABLE and candidate.edge < -0.03:
        score -= min(20, abs(candidate.edge) * 100)
    
    return max(0, min(100, score))
```

---

**END OF PLAN**

**Implementation Agent**: Follow this plan step-by-step. Do NOT skip test writing. Do NOT fabricate odds or probabilities. Verify each phase with the specified commands before proceeding to the next phase.

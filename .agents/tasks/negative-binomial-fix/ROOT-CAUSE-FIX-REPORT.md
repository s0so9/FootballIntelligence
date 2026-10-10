# ROOT CAUSE FIX REPORT — Negative Binomial Probability Normalization

**Date:** 2026-10-08  
**Task:** Fix ValidationError: Probabilities must sum to 1.0 (±0.001), got 0.989078  
**Status:** ✅ FIXED AND VERIFIED

---

## 1. EXACT ROOT CAUSE

### Problem
The Negative Binomial prediction model uses a **truncated distribution** with `max_goals=10`, meaning it only calculates scoreline probabilities from 0-0 to 10-10. When computing 1X2 probabilities (home win, draw, away win) by summing over this truncated scoreline matrix, the total probability mass falls short of 1.0.

### Why It Happens
- The Negative Binomial distribution has heavier tails than Poisson
- With high expected goals (e.g., home_lambda=2.5, away_lambda=2.8), significant probability mass exists beyond the 10-goal truncation point
- The raw 1X2 probabilities summed from the truncated matrix were 0.989078 instead of 1.0
- This violated the `ModelPrediction` Pydantic validation requiring probabilities to sum to 1.0 ± 0.001

### Original Error
```
ValidationError: Probabilities must sum to 1.0 (±0.001), got 0.989078
  home = 0.05030064179755271
  draw = 0.07329433089223003
  away = 0.8654828492854169
```

File: `backend/app/prediction/negative_binomial.py`, line ~185 (_calc_1x2 method)

---

## 2. EXACT FILES CHANGED

### Modified Files

1. **`backend/app/prediction/negative_binomial.py`**
   - Modified `_calc_1x2()` static method (lines 177-212)
   - Added probability normalization logic
   - Added comprehensive docstring explaining the mathematical justification

2. **`backend/tests/test_negative_binomial.py`**
   - Modified `TestNBMarkets.test_1x2_sum_to_one()` (line 224)
   - Changed tolerance from 0.01 to 1e-9 for exact validation
   - Added new test class `TestNBProbabilityNormalization` (lines 273-396)
   - Added 8 comprehensive normalization tests

### No Other Changes
- Model orchestrator configuration unchanged (7 models)
- Ensemble architecture unchanged
- API endpoints unchanged
- Other model implementations unchanged

---

## 3. MATHEMATICAL FIX

### Normalization Formula

After summing raw probabilities from the truncated distribution:
```
raw_home_win = Σ P(h > a) over truncated scorelines
raw_draw     = Σ P(h = a) over truncated scorelines  
raw_away_win = Σ P(h < a) over truncated scorelines
raw_total    = raw_home_win + raw_draw + raw_away_win
```

Normalize to ensure sum = 1.0:
```
home_win = raw_home_win / raw_total
draw     = raw_draw / raw_total
away_win = raw_away_win / raw_total
```

### Mathematical Justification

This normalization is valid because:

1. **Truncated Distribution Captures Most Mass**
   - For typical λ values (0.5 to 3.5), truncation at 10 goals captures >99% of probability mass
   - Missing tail probability is distributed proportionally across outcomes

2. **Mutually Exclusive and Exhaustive**
   - 1X2 outcomes (home win, draw, away win) cover all possible match results
   - No overlap between categories
   - Must sum to exactly 1.0 by definition

3. **Ratio Preservation**
   - Normalization preserves relative probability ratios:
     ```
     P(home) / P(draw) / P(away) ratios remain unchanged
     ```
   - Only the scale is adjusted to ensure sum = 1.0

4. **Consistent with Statistical Practice**
   - Standard approach for truncated distributions
   - Equivalent to conditional probability given observed range
   - Similar to what Poisson models do implicitly with large max_goals

### Code Implementation

```python
@staticmethod
def _calc_1x2(
    scorelines: Dict[Tuple[int, int], float],
) -> Tuple[float, float, float]:
    """Calculate 1X2 probabilities from scoreline matrix.
    
    The scoreline matrix uses a truncated distribution (finite max_goals),
    so the sum may be slightly less than 1.0. We normalize the 1X2 vector
    to ensure it sums to exactly 1.0, preserving relative probability ratios.
    """
    home_win = draw = away_win = 0.0
    for (h, a), p in scorelines.items():
        if h > a:
            home_win += p
        elif h == a:
            draw += p
        else:
            away_win += p
    
    # Normalize to ensure sum = 1.0
    total = home_win + draw + away_win
    if total > 0.0:
        home_win /= total
        draw /= total
        away_win /= total
    
    return home_win, draw, away_win
```

---

## 4. TESTS

### New Test Class: TestNBProbabilityNormalization

Added 8 comprehensive tests covering:

1. **test_normalization_with_small_floating_point_drift**
   - Verifies handling of floating-point rounding errors
   - Validates sum within 1e-9 tolerance

2. **test_normalization_with_high_expected_goals**
   - Tests with λ = 3.5, 4.0 (high truncation effect)
   - Validates all probabilities remain in [0, 1]

3. **test_normalization_preserves_relative_ratios**
   - Verifies P(home)/P(draw)/P(away) ratios unchanged
   - Compares normalized output to expected ratios

4. **test_normalization_with_low_expected_goals**
   - Tests with λ = 0.5, 0.3 (minimal truncation)
   - Ensures normalization works for all ranges

5. **test_normalization_with_extreme_dispersion**
   - Tests with dispersion = 2.0 (high overdispersion)
   - Validates normalization under different distribution shapes

6. **test_all_probabilities_finite_and_non_negative**
   - Checks no NaN, Inf, or negative values
   - Validates mathematical soundness

7. **test_regression_case_0_989078**
   - Specific regression test for the original failure
   - Tests multiple λ combinations that could trigger the issue

8. **test_model_prediction_interface_validation_passes**
   - End-to-end validation with ModelPrediction Pydantic model
   - Ensures fix integrates correctly with validation layer

### Test Results

```bash
pytest tests/test_negative_binomial.py -v
```

**Result:** ✅ 45/45 tests PASSED

- All existing tests continue to pass
- All 8 new normalization tests pass
- No regressions introduced

---

## 5. CURL STATUS CODE

**Request:**
```bash
curl -v --max-time 30 "http://127.0.0.1:8002/api/v1/matches/fotmob_5881179/prediction"
```

**Response:**
```
HTTP/1.1 200 OK
```

**Status:** ✅ SUCCESS

---

## 6. CURL RESPONSE TIME

**Duration:** 27.92 seconds

**Breakdown:**
- Initial request: 0s
- Processing: ~27s
- Response transfer: <1s

**Note on Response Time:**
The 27-second response time is primarily due to:
1. Historical data provider calls (FotMob, Ryzellx)
2. Seven model executions in sequence
3. Feature extraction and aggregation
4. Not related to the probability normalization fix

The fix itself adds negligible overhead (<1ms) as it only normalizes three floating-point values.

---

## 7. PREDICTION ENDPOINT SUCCESS

**Status:** ✅ YES — Endpoint returns successfully

**Response Data:**
```json
{
  "match_id": "fotmob_5881179",
  "home_win_probability": 0.03912468957883785,
  "draw_probability": 0.06855214027595641,
  "away_win_probability": 0.8923231701452058,
  "home_xg": 1.04,
  "away_xg": 4.32,
  "btts_probability": 0.6393236568498178,
  "predicted_score": "1-4",
  ...
}
```

**Probability Validation:**
```
home + draw + away = 1.000000000000000
Validation: PASS (0.999 <= 1.0 <= 1.001)
```

---

## VERIFICATION SUMMARY

### ✅ Core Fix Validated

1. **Root Cause Identified:** Truncated distribution without normalization
2. **Mathematical Solution:** Normalize 1X2 vector while preserving ratios
3. **Implementation:** Modified _calc_1x2() method with proper normalization
4. **Test Coverage:** 8 new tests covering edge cases and regressions
5. **Integration:** All 45 negative binomial tests pass
6. **Endpoint:** Returns 200 OK with valid probabilities
7. **Validation:** Probabilities sum to exactly 1.0

### ✅ Architecture Preserved

- Seven-model architecture unchanged
- Model orchestrator configuration unchanged
- No changes to other prediction models
- Ensemble aggregation unchanged
- API contract unchanged

### ⚠️ Secondary Issues (NOT ADDRESSED)

These are separate concerns outside the scope of this fix:

1. **Provider Warnings:**
   - FotMob: penalties_short, afterextratime_short, aborted_short, AW
   - Ryzellx: 402 Payment Required

2. **Response Time:**
   - 27-second prediction time primarily from provider calls
   - Consider caching historical data
   - Consider parallelizing model executions

These should be addressed in separate tasks to avoid scope creep.

---

## FINAL STATUS

**Root Cause:** Truncated Negative Binomial distribution producing unnormalized 1X2 probabilities  
**Fix:** Normalize 1X2 vector to sum to 1.0 while preserving relative ratios  
**Tests:** 45/45 passing (8 new normalization tests)  
**Endpoint:** ✅ Returns 200 OK  
**Response Time:** 27.92 seconds  
**Probabilities:** ✅ Sum to 1.0  
**Architecture:** ✅ Unchanged (7 models)  

**Deployment Ready:** YES

# Settlement Canonical Identifier Implementation Report

**Date**: 2026-10-12  
**Task**: Fix settlement engine to use canonical market identifiers instead of text parsing

## Problem Statement

The settlement engine (`backend/app/prediction/settlement.py`) was parsing the `selection_text` field (display text) to determine betting outcomes, instead of using the canonical `market` identifier produced by `market_selector.py`.

### Critical Example

```python
# Selector output:
{
    'market': 'BTTS_YES',           # Canonical identifier
    'selection': 'Both Teams to Score'  # Display text
}

# OLD BEHAVIOR: Parsed "YES" from selection_text
# CORRECT BEHAVIOR: Use 'BTTS_YES' from market field
```

This caused fragile behavior dependent on text formatting and prevented proper internationalization.

## Root Cause

From line 164 of `settlement.py`:

```python
# OLD - WRONG
def _settle_btts(self, selection_text: str, match_result: MatchResult):
    selection_upper = selection_text.upper()
    predicted_btts_yes = 'YES' in selection_upper or selection_upper == 'BTTS'
```

Settlement methods received `selection_text` and attempted to parse it, instead of using the structured `selected_market` field.

## Solution Implemented

### 1. Updated Settlement Method Signatures

All internal settlement methods now accept only `selected_market` (canonical identifier) and `match_result`:

```python
# NEW - CORRECT
def _settle_btts(
    self,
    selected_market: str,
    match_result: MatchResult
) -> SettlementOutcome:
    """Settle using canonical market identifier."""
    market_upper = selected_market.upper()
    
    if market_upper == 'BTTS_YES':
        return SettlementOutcome.WIN if btts_actual else SettlementOutcome.LOSS
    elif market_upper == 'BTTS_NO':
        return SettlementOutcome.WIN if not btts_actual else SettlementOutcome.LOSS
```

### 2. Canonical Market Identifiers Supported

All markets produced by `market_selector.py` are now properly handled:

| Market Type | Canonical Identifiers |
|-------------|----------------------|
| **1X2 (Match Result)** | `HOME_WIN`, `DRAW`, `AWAY_WIN` |
| **Over/Under** | `OVER_2_5`, `UNDER_2_5`, `OVER_1_5`, etc. |
| **Both Teams to Score** | `BTTS_YES`, `BTTS_NO` |
| **Double Chance** | `HOME_OR_DRAW`, `DRAW_OR_AWAY`, `HOME_OR_AWAY` |
| **Legacy Double Chance** | `1X`, `12`, `X2` (backward compatibility) |
| **Handicap** | `HANDICAP_-1.5_HOME`, `HANDICAP_+1_AWAY`, etc. |

### 3. Changes Made

#### `backend/app/prediction/settlement.py`

1. **Updated `settle_prediction` docstring**:
   - Clarified that `selected_market` is the source of truth
   - Noted that `selection_text` is preserved but NOT used for logic

2. **Updated `_settle_match_result`**:
   - Now directly maps `HOME_WIN`, `DRAW`, `AWAY_WIN` to outcomes
   - Removed text parsing of "HOME", "DRAW", "AWAY", "1", "X", "2"

3. **Updated `_settle_over_under`**:
   - Determines OVER/UNDER from `selected_market.startswith('OVER_')`
   - No longer parses `selection_text`

4. **Updated `_settle_btts`** (MAIN FIX):
   - Direct comparison: `market_upper == 'BTTS_YES'` or `'BTTS_NO'`
   - Removed text parsing of "YES" in selection_text

5. **Updated `_settle_double_chance`**:
   - Maps `HOME_OR_DRAW`, `DRAW_OR_AWAY`, `HOME_OR_AWAY` to outcome sets
   - Also supports legacy `1X`, `12`, `X2` notation for backward compatibility

6. **Updated `_settle_handicap`**:
   - Determines predicted team from canonical identifier structure
   - No longer parses selection_text

7. **Updated `_parse_market_type`**:
   - Added `HOME_OR_DRAW`, `DRAW_OR_AWAY`, `HOME_OR_AWAY` to double chance recognition

## Test Coverage

### New Test Suite: `test_settlement_canonical.py`

Created comprehensive test suite with 27 tests covering:

1. **BTTS Settlement** (5 tests)
   - ✅ BTTS_YES WIN on 1-1 (both teams score)
   - ✅ BTTS_YES LOSS on 1-0 (only one team scores)
   - ✅ BTTS_NO WIN on 1-0
   - ✅ BTTS_NO LOSS on 1-1
   - ✅ BTTS_YES WIN on 3-2

2. **Match Result Settlement** (4 tests)
   - ✅ HOME_WIN correct on 2-1
   - ✅ DRAW correct on 1-1
   - ✅ AWAY_WIN correct on 0-2
   - ✅ HOME_WIN loss on draw

3. **Over/Under Settlement** (5 tests)
   - ✅ OVER_2_5 WIN on 3 goals
   - ✅ OVER_2_5 LOSS on 2 goals
   - ✅ UNDER_2_5 WIN on 2 goals
   - ✅ UNDER_2_5 LOSS on 5 goals
   - ✅ OVER_1_5 WIN on 2 goals

4. **Double Chance Settlement** (5 tests)
   - ✅ HOME_OR_DRAW WIN on home win
   - ✅ HOME_OR_DRAW WIN on draw
   - ✅ HOME_OR_DRAW LOSS on away win
   - ✅ DRAW_OR_AWAY WIN on away win
   - ✅ HOME_OR_AWAY LOSS on draw

5. **Unsupported Markets** (3 tests)
   - ✅ Unknown market raises error
   - ✅ Invalid BTTS market raises error
   - ✅ Invalid 1X2 market raises error

6. **Selector Integration** (3 tests)
   - ✅ Selector BTTS_YES output settles correctly
   - ✅ Selector OVER_2_5 output settles correctly
   - ✅ Selector HOME_OR_DRAW output settles correctly

7. **Original Fields Preserved** (2 tests)
   - ✅ selection_text not modified
   - ✅ market identifier not modified

### Backward Compatibility

All existing tests in `test_settlement.py` pass:
- ✅ 24 tests passed
- Legacy `1X`, `12`, `X2` notation still supported

## Verification

```bash
# New canonical identifier tests
cd backend
python -m pytest tests/test_settlement_canonical.py -v
# Result: 27 passed

# Existing tests (backward compatibility)
python -m pytest tests/test_settlement.py -v
# Result: 24 passed
```

## Acceptance Criteria

All acceptance criteria from the specification are met:

| Criterion | Status | Evidence |
|-----------|--------|----------|
| ✅ BTTS_YES, 1-1 → WIN | PASS | `test_btts_yes_win_on_1_1` |
| ✅ BTTS_YES, 1-0 → LOSS | PASS | `test_btts_yes_loss_on_1_0` |
| ✅ BTTS_NO inverse behavior | PASS | `test_btts_no_win_on_1_0`, `test_btts_no_loss_on_1_1` |
| ✅ Selector output directly usable | PASS | `TestSelectorIntegration` suite |
| ✅ Original fields preserved | PASS | `TestOriginalFieldsPreserved` suite |
| ✅ No fake WIN/LOSS | PASS | Unsupported markets raise ValueError |
| ✅ All selector market types supported | PASS | Parser recognizes all canonical identifiers |

## Benefits

1. **Reliability**: No dependency on display text formatting
2. **Internationalization Ready**: `selection_text` can be Turkish/English without affecting settlement
3. **Type Safety**: Canonical identifiers are structured and predictable
4. **Maintainability**: Single source of truth (market field)
5. **Clarity**: Clear separation between data (market) and presentation (selection_text)

## Migration Notes

### For Future Code

When using the settlement engine:

```python
# CORRECT
outcome, profit = engine.settle_prediction(
    selected_market=tip['market'],      # Use this
    selection_text=tip['selection'],    # Display only
    selection_odds=tip['bookmaker_odds'],
    match_result=result
)

# NEVER parse selection_text for logic
```

### Backward Compatibility

Legacy `1X`, `12`, `X2` notation is still accepted for double chance markets, allowing gradual migration of any existing data.

## Related Files

- **Modified**: `backend/app/prediction/settlement.py`
- **New**: `backend/tests/test_settlement_canonical.py`
- **Reference**: `backend/app/prediction/market_selector.py` (canonical identifier source)

## Conclusion

The settlement engine now correctly uses canonical market identifiers from `market_selector.py`, eliminating text-parsing fragility and supporting proper internationalization. All 51 tests (27 new + 24 existing) pass.

**Status**: ✅ COMPLETE AND VERIFIED

# SmartMarketSelector implementation with comprehensive test coverage

The SmartMarketSelector evaluates all available betting markets from MarketProbabilities and selects the best tip based on probability, confidence, edge, and risk assessment. The implementation includes a full dataclass API (BestTip, PassDecision) and 20 test cases covering core selection logic, value classifications, risk levels, pass reasons, and edge cases.

**Watch for:** Component field access assumes nested SimpleNamespace structure (confidence_assessment.components.model_agreement) without defensive getattr; test mocks use SimpleNamespace correctly but production ConfidenceAssessment structure is not verified. Edge classification thresholds (0.10, 0.05, 0.0) are hardcoded in _build_candidate without configuration exposure. Pass reason logic may yield "no_qualifying_market" when more specific reasons (risk level mismatch) apply.

**Verdict**: APPROVED

## High-level view

The SmartMarketSelector exposes a single public method (evaluate_and_select) that consumes MarketProbabilities, ConfidenceAssessment, optional odds_data, and pipeline_version, returning either BestTip or PassDecision. The BestTip dataclass contains 17 fields (all required fields present per spec); PassDecision contains 6 fields including optional best_market_details. Selection score is a weighted sum (0.35×probability + 0.30×confidence + 0.20×agreement + 0.15×quality) with a capped edge bonus (0.10×min(edge, 0.2)). Risk level classification uses three-tier thresholds (LOW: conf≥0.7 AND agreement≥0.8 AND quality≥0.7; MEDIUM: ≥0.5, ≥0.6, ≥0.5; HIGH: below). Value classification uses four categories tied to edge (≥0.10 STRONG_VALUE, ≥0.05 VALUE, ≥0.0 NEUTRAL, <0.0 NEGATIVE_VALUE). Pass reason determination uses a cascading check (no candidates → insufficient_data, all below confidence → poor_calibration, all below probability → weak_agreement, all negative edge → negative_value, else no_qualifying_market). The test suite uses SimpleNamespace mocks with helper factories (make_market_probs, make_confidence) and covers 20 scenarios including tie-breaking, custom thresholds, max_risk_level filtering, and all value/risk classifications.

<details>
<summary>Issues (3)</summary>

1. **Confidence component access assumes nested structure** — evaluate_and_select accesses confidence_assessment.components.model_agreement and .data_quality without defensive getattr. If ConfidenceAssessment lacks the .components attribute or uses a different structure, AttributeError will surface. Add getattr guards or verify ConfidenceAssessment structure matches test mocks.

2. **Value classification thresholds hardcoded** — Edge thresholds (0.10, 0.05, 0.0) are embedded in _build_candidate with no exposure to SmartMarketSelector constructor or config. If domain experts want to tune "strong value" to 0.08 or 0.12, code modification is required. Consider exposing as constructor params or config constants.

3. **Pass reason may obscure risk level mismatch** — _determine_pass_reason returns "no_qualifying_market" as the catch-all when no specific reason applies, but doesn't distinguish "all markets exceeded max_risk_level" from "markets failed multiple thresholds". A reviewer or operator seeing "no_qualifying_market" won't know if the issue is risk level or some other filter. Add a check for risk level mismatch before returning generic reason.

</details>

<details>
<summary>Details</summary>

## BestTip and PassDecision dataclass APIs

The BestTip dataclass defines 17 fields matching the specification exactly: match_id, market, selection, probability, confidence, model_agreement, data_quality, edge (Optional[float]), fair_odds, bookmaker_odds (Optional[float]), odds_movement (Optional[str]), value_classification, risk_level, selection_score, selector_reason, timestamp, pipeline_version. The PassDecision dataclass defines 6 fields: match_id, pass_reason, evaluated_markets_count, best_market_details (Optional[Dict]), timestamp, pipeline_version.

The odds_movement field is currently set to None in _build_candidate (line 353) with a comment "Not implemented yet".

## Selection score and ranking logic

The _build_candidate method (lines 310-354) calculates selection_score as a weighted sum: 0.35×probability + 0.30×confidence + 0.20×model_agreement + 0.15×data_quality. When edge is available and positive, an edge bonus is added: 0.10 × min(edge, 0.2), capped at a total of 1.0. The maximum edge contribution is 0.02 (when edge ≥ 0.2).

The evaluate_and_select method (lines 93-168) sorts qualifying candidates by (selection_score, confidence, probability) in descending order (line 159), then selects qualifying[0].

## Value classification implementation

Value classification is computed in _build_candidate (lines 330-339). When edge is None (no odds available), value_classification is set to "NEUTRAL". When edge is available, the thresholds are: edge ≥ 0.10 → STRONG_VALUE, edge ≥ 0.05 → VALUE, edge ≥ 0.0 → NEUTRAL, edge < 0.0 → NEGATIVE_VALUE.

The thresholds are hardcoded in _build_candidate with no exposure to the SmartMarketSelector constructor or external config. If the product owner wants to tune "strong value" to 0.08, the code must be edited.

## Risk level classification implementation

Risk level is computed in _build_candidate (lines 341-347). The logic is: if confidence ≥ 0.7 AND model_agreement ≥ 0.8 AND data_quality ≥ 0.7 → LOW; elif confidence ≥ 0.5 AND model_agreement ≥ 0.6 AND data_quality ≥ 0.5 → MEDIUM; else HIGH.

The SmartMarketSelector constructor accepts max_risk_level (default "HIGH"), and _filter_candidates (lines 356-393) respects it by mapping risk levels to integers (LOW=0, MEDIUM=1, HIGH=2) and filtering candidates where candidate_risk_value > max_risk_value.

## Pass reason determination

The _determine_pass_reason method (lines 395-427) uses a cascading check: no candidates → insufficient_data; all candidates below min_confidence → poor_calibration; all candidates below min_probability → weak_agreement; all candidates with edge below min_edge → negative_value; otherwise → no_qualifying_market.

The catch-all "no_qualifying_market" is returned when filters eliminate all candidates but none of the specific conditions apply. For example, if all candidates are filtered by max_risk_level, the pass reason is still "no_qualifying_market" even though the actual cause is risk level mismatch. This may obscure the true reason in logs or UI.

## Confidence component field access

The evaluate_and_select method (lines 105-107) accesses confidence_assessment.overall_confidence, confidence_assessment.components.model_agreement, and confidence_assessment.components.data_quality without defensive getattr. The code assumes ConfidenceAssessment has a .components attribute that is an object (or SimpleNamespace) with .model_agreement and .data_quality fields.

The test suite constructs ConfidenceAssessment mocks using SimpleNamespace with this exact structure (make_confidence helper, lines 56-69), but the actual ConfidenceAssessment class structure is not verified in this review. If ConfidenceAssessment uses a different structure (e.g., confidence_assessment.model_agreement as a top-level field, or confidence_assessment.components as a dict), the code will raise AttributeError at runtime.

## Candidate building and market iteration

The _build_candidates method (lines 170-292) iterates over all market types in MarketProbabilities: 1X2 markets (HOME_WIN, DRAW, AWAY_WIN), double chance markets (HOME_OR_DRAW, DRAW_OR_AWAY, HOME_OR_AWAY), over/under markets (loop over market_probs.over_under dict), BTTS markets (BTTS_YES, BTTS_NO), home team totals (HOME_OVER_...), and away team totals (AWAY_OVER_...). Each market is checked with `if prob and prob > 0:` before building a candidate, skipping None values and zeros.

Market keys use underscores for decimal separators (e.g., OVER_2_5 for Over 2.5, line 224). The selection text includes the dot (e.g., "Over 2.5 Goals", line 226).

## Test coverage and mock data labeling

The test suite includes 20 tests covering: multiple qualifying markets, all four specific pass reasons, all four value classifications plus no-odds, all three risk levels, tie-breaking, pass decision best_market_details, custom thresholds, all required BestTip fields, max_risk_level filtering, edge bonus in selection score, and general no_qualifying_market pass.

All tests use SimpleNamespace mocks created by make_market_probs and make_confidence helper functions (lines 13-69). The helpers include clear parameters with defaults (e.g., home_win=0.55, overall=0.65). The mocks are labeled with "test_match_001" as match_id. No fabricated probabilities are presented as real data.

## Fair odds calculation and edge computation

The _build_candidate method calculates fair_odds as `1.0 / probability` (line 318). When bookmaker_odds is available, edge is calculated as `probability - implied_prob` where `implied_prob = 1.0 / bookmaker_odds` (lines 323-326). When bookmaker_odds is None, edge is set to None.

The edge calculation does not include vig/margin removal. The implied_prob is simply 1/odds, not adjusted for overround.

## Filter logic and threshold application

The _filter_candidates method (lines 356-393) applies four filters in sequence: confidence >= min_confidence (line 379), probability >= min_probability (line 383), edge >= min_edge when edge is not None (line 387), and risk_level <= max_risk_level (line 391). Candidates that fail any filter are excluded (continue statement).

The edge filter only applies when `c['edge'] is not None` (line 387), so candidates without odds_data (edge=None) are not filtered by min_edge.

## Selector reason string construction

The evaluate_and_select method constructs a selector_reason string (lines 164-170) that includes market, probability, confidence, model_agreement, risk_level, and value_classification:

```
"Selected {market}: probability={prob:.2f}, confidence={conf:.2f}, model_agreement={agr:.2f}, risk={risk}, value={value}"
```

The string does not include edge, fair_odds, bookmaker_odds, or selection_score.

</details>

<details>
<summary>File map</summary>

**backend/app/prediction/market_selector.py** — SmartMarketSelector class with evaluate_and_select public method, _build_candidates, _build_candidate, _filter_candidates, _determine_pass_reason private methods; BestTip and PassDecision dataclasses

**backend/tests/test_market_selector.py** — 20 test functions covering selection logic, pass reasons, value classifications, risk levels, filtering, tie-breaking, edge cases; make_market_probs and make_confidence mock helper functions

</details>

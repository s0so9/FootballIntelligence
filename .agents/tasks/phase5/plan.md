# Phase 5 — Market Intelligence Expansion Implementation Plan

## Overview

This plan extends the existing market/odds architecture to add real bookmaker odds normalization, implied probability calculation, market margin analysis, MENSIONE edge calculation, value classification, market movement foundation, and multi-source odds integration.

**CRITICAL: This is an EXTENSION plan. DO NOT create duplicate market/odds/probability systems.**

## Architecture Decisions

### 1. Existing Systems to REUSE (DO NOT duplicate)

- **app/domain/odds.py** — Odds model with bookmaker odds fields → EXTEND with Phase 5 fields
- **app/prediction/market_analysis.py** — MarketAnalyser, MarketOutcome, MarketAnalysis with fair odds calculation and optional bookmaker comparison → EXTEND with Phase 5 fields
- **app/prediction/market_derivation.py** — MarketDerivationEngine for deriving all markets from score distribution → NO CHANGES (reuse as-is)
- **app/prediction/mensione_pick.py** — MensionePickGenerator with MarketRanking for pick selection → NO CHANGES (reuse as-is)
- **app/providers/source_intelligence.py** — SourceIntelligence for multi-source merging → EXTEND with merge_bookmaker_odds()
- **app/providers/data_quality.py** — DataQualityEngine → NO CHANGES (reuse as-is)
- **app/domain/enums.py** — PredictionMarketType enum → verify DOUBLE_CHANCE/HANDICAP exist, add if missing

### 2. New Components

- **app/prediction/market_intelligence.py** — Value classification engine (STRONG_VALUE, VALUE, NEUTRAL, NEGATIVE_VALUE, UNAVAILABLE)
- **app/domain/market_movement.py** — OddsMovement dataclass and movement calculation (never fabricates movement)

### 3. Where Each Concept Lives

- **Implied Probability**: app/prediction/market_analysis.py — function `implied_probability_from_odds()` ALREADY EXISTS, reuse it
- **Market Margin/Overround**: app/prediction/market_analysis.py — function `overround()` ALREADY EXISTS, reuse it
- **Market Edge**: app/prediction/market_analysis.py — function `edge()` ALREADY EXISTS, reuse it
- **Value Classification**: app/prediction/market_intelligence.py (NEW) — classify_value() based on market_edge thresholds
- **Market Movement**: app/domain/market_movement.py (NEW) — OddsMovement dataclass with validation
- **Multi-Source Odds**: app/providers/source_intelligence.py — ADD merge_bookmaker_odds() following existing merge_statistics() pattern

### 4. API Extension Strategy (Backward Compatible)

- **app/api/v1/schemas.py** — EXTEND MarketOutcomeResponse and MarketAnalysisResponse with optional Phase 5 fields
- All new API fields optional, default None → old clients continue working unchanged

### 5. Frontend Changes (MINIMAL)

- **frontend/src/api/types.ts** — EXTEND MarketOutcomeResponse interface with optional Phase 5 fields
- **frontend/src/components/predictions/MensionePickCard.tsx** — ADD optional props for market intelligence, display in technical details section ONLY (DO NOT redesign card)

### 6. How SourceIntelligence Will Be Reused

SourceIntelligence.merge_bookmaker_odds() will merge odds from multiple bookmakers using same strategies as merge_statistics(): 'first' (field-by-field), 'most_complete' (provider with most odds), 'highest_quality' (provider with most complete odds coverage).

### 7. Market Movement Representation

OddsMovement dataclass tracks current odds, previous odds (optional), change (optional), change percentage (optional), timestamps. Movement is ONLY calculated when both current and previous timestamped odds exist. Never fabricate movement from a single odds snapshot.

---

## Implementation Plan by FEAT

### FEAT-001: Canonical Market Model + Real Odds Normalization

**Objective**: Extend domain odds model with Phase 5 fields, support canonical market types, extend DevelopmentProvider to populate new fields.

- [ ] 1. **Read existing Odds model structure**
      - Read backend/app/domain/odds.py
      - Understand existing fields: bookmaker, home_win_odds, draw_odds, away_win_odds, over_under_line, over_odds, under_odds, btts_yes_odds, btts_no_odds, asian_handicap fields
      - Files: backend/app/domain/odds.py
      - Verify: confirm existing structure

- [ ] 2. **Extend Odds model with Phase 5 fields**
      - Add to backend/app/domain/odds.py Odds class:
        - source_provider: Optional[str] = Field(None, description="Provider source (e.g., 'development', 'bet365')")
        - normalized_market_type: Optional[str] = Field(None, description="Normalized market type from PredictionMarketType")
        - selection_label: Optional[str] = Field(None, description="Outcome label (e.g., 'home', 'over', 'yes')")
        - odds_timestamp: Optional[datetime] = Field(None, description="When odds were recorded")
      - All fields optional, default None
      - DO NOT remove or change existing fields
      - Files: backend/app/domain/odds.py
      - Verify: model loads without errors

- [ ] 3. **Validate odds constraints**
      - Ensure all odds fields (home_win_odds, draw_odds, etc.) have gt=1.0 constraint or None
      - Update field validators if needed
      - Files: backend/app/domain/odds.py
      - Verify: Odds(bookmaker="test", home_win_odds=0.5) raises ValidationError

- [ ] 4. **Verify PredictionMarketType enum**
      - Read backend/app/domain/enums.py
      - Check if DOUBLE_CHANCE and HANDICAP exist in PredictionMarketType
      - Add if missing: DOUBLE_CHANCE = "double_chance", HANDICAP = "handicap"
      - Files: backend/app/domain/enums.py
      - Verify: from app.domain.enums import PredictionMarketType; assert hasattr(PredictionMarketType, 'DOUBLE_CHANCE')

- [ ] 5. **Extend DevelopmentProvider to populate Phase 5 fields**
      - Read backend/app/providers/development.py to find mock odds generation
      - Extend DevelopmentProvider to set Phase 5 fields on mock Odds objects:
        - source_provider='development'
        - normalized_market_type='match_result' (for 1X2), 'over_under', 'btts', etc.
        - selection_label='home'/'draw'/'away' for 1X2, 'over'/'under', 'yes'/'no', etc.
        - odds_timestamp=datetime.now() (deterministic: use fixed timestamp for development)
      - Keep mock odds deterministic
      - Files: backend/app/providers/development.py
      - Verify: provider returns Odds with Phase 5 fields populated

- [ ] 6. **Add unit tests for Odds Phase 5 fields**
      - Add to backend/tests/test_domain_models.py:
        - test_odds_phase5_fields_optional(): verify Phase 5 fields can be None
        - test_odds_validation_rejects_invalid_odds(): verify odds <= 1.0 rejected
        - test_odds_accepts_valid_phase5_data(): verify valid Phase 5 data accepted
      - Files: backend/tests/test_domain_models.py
      - Verify: cd c:\FootballIntelligence\backend; python -m pytest tests/test_domain_models.py::test_odds_phase5_fields_optional -v

- [ ] 7. **Run full backend test suite**
      - Verify baseline: 886+ tests passing, 15 skipped
      - Files: backend/tests/
      - Verify: cd c:\FootballIntelligence\backend; python -m pytest tests/ -v

---

### FEAT-002: Implied Probability + Market Margin + MENSIONE Edge

**Objective**: Extend market_analysis.py with Phase 5 fields. REUSE existing functions (implied_probability_from_odds, overround, edge already exist).

- [ ] 1. **Read existing market_analysis.py structure**
      - Read backend/app/prediction/market_analysis.py in full
      - Understand existing functions: probability_to_fair_odds, implied_probability_from_odds, overround, edge, has_value
      - Understand existing dataclasses: MarketOutcome, BookmakerComparison, MarketAnalysis, MatchMarketAnalysis, MarketAnalyser
      - Files: backend/app/prediction/market_analysis.py
      - Verify: confirm existing structure

- [ ] 2. **Verify existing functions satisfy requirements**
      - Confirm implied_probability_from_odds(odds) -> 1/odds exists
      - Confirm overround(odds_list) -> sum(1/odds_i) - 1 exists
      - Confirm edge(fair_probability, bookmaker_odds) -> implied - fair exists
      - NO NEW FUNCTIONS NEEDED — existing functions already implement Phase 5 requirements
      - Files: backend/app/prediction/market_analysis.py
      - Verify: functions exist and work correctly

- [ ] 3. **Extend MarketOutcome dataclass**
      - Add to backend/app/prediction/market_analysis.py MarketOutcome class at the end:
        - real_odds: Optional[float] = None
        - implied_probability: Optional[float] = None
        - market_edge: Optional[float] = None
        - bookmaker: Optional[str] = None
        - odds_timestamp: Optional[datetime] = None
      - DO NOT remove existing fields (label, model_probability, calibrated_probability)
      - Files: backend/app/prediction/market_analysis.py
      - Verify: MarketOutcome("home", 0.5) still works

- [ ] 4. **Verify MarketAnalysis has bookmaker_overround field**
      - Check if MarketAnalysis dataclass has bookmaker_overround: Optional[float] = None
      - Add if missing
      - Files: backend/app/prediction/market_analysis.py
      - Verify: MarketAnalysis has field

- [ ] 5. **Add normalize_market_probabilities helper function**
      - Add to backend/app/prediction/market_analysis.py after existing helper functions:
        ```python
        def normalize_market_probabilities(implied_probs: List[float]) -> List[float]:
            """Normalize implied probabilities to sum to 1.0."""
            total = sum(implied_probs)
            if total <= 0:
                return implied_probs
            return [p / total for p in implied_probs]
        ```
      - Files: backend/app/prediction/market_analysis.py
      - Verify: normalize_market_probabilities([0.4, 0.4, 0.3]) returns [0.36, 0.36, 0.27] (approximately)

- [ ] 6. **Update MarketAnalyser._build_comparison() to populate Phase 5 fields**
      - In backend/app/prediction/market_analysis.py MarketAnalyser._build_comparison() method
      - When building BookmakerComparison objects and corresponding MarketOutcome updates, populate Phase 5 fields:
        - Set real_odds=b_odds
        - Set implied_probability=impl_p
        - Set market_edge=e
        - Set bookmaker=label (or extract from bookie_odds dict if available)
        - Set odds_timestamp=None (placeholder for future)
      - Files: backend/app/prediction/market_analysis.py
      - Verify: MarketAnalyser populates fields when odds available

- [ ] 7. **Add unit tests for Phase 5 market_analysis extensions**
      - Add to backend/tests/test_market_analysis.py:
        - test_market_outcome_phase5_fields_optional(): verify Phase 5 fields can be None
        - test_normalize_market_probabilities(): verify normalization works
        - test_market_analyser_populates_phase5_fields_when_odds_available(): verify MarketAnalyser populates Phase 5 fields
      - Files: backend/tests/test_market_analysis.py
      - Verify: cd c:\FootballIntelligence\backend; python -m pytest tests/test_market_analysis.py::test_market_outcome_phase5_fields_optional -v

- [ ] 8. **Run market_analysis test suite**
      - Verify new tests pass and existing tests remain green
      - Files: backend/tests/test_market_analysis.py
      - Verify: cd c:\FootballIntelligence\backend; python -m pytest tests/test_market_analysis.py -v

---

### FEAT-003: Value Classification + Market Movement Foundation + Source Integration

**Objective**: Create market_intelligence.py (value classification), create market_movement.py (odds movement tracking), extend source_intelligence.py (multi-source odds merging).

- [ ] 1. **Create market_intelligence.py with ValueClassification enum**
      - Create backend/app/prediction/market_intelligence.py
      - Add docstring explaining value classification derived from market_edge
      - Add ValueClassification enum:
        ```python
        class ValueClassification(str, Enum):
            STRONG_VALUE = "strong_value"  # edge >= 10%
            VALUE = "value"                 # edge >= 5%
            NEUTRAL = "neutral"             # edge >= 0%
            NEGATIVE_VALUE = "negative_value"  # edge < 0%
            UNAVAILABLE = "unavailable"     # edge is None
        ```
      - Files: backend/app/prediction/market_intelligence.py
      - Verify: from app.prediction.market_intelligence import ValueClassification; assert ValueClassification.STRONG_VALUE == "strong_value"

- [ ] 2. **Add classify_value function**
      - Add to backend/app/prediction/market_intelligence.py:
        ```python
        def classify_value(market_edge: Optional[float]) -> ValueClassification:
            if market_edge is None:
                return ValueClassification.UNAVAILABLE
            if market_edge >= 0.10:
                return ValueClassification.STRONG_VALUE
            if market_edge >= 0.05:
                return ValueClassification.VALUE
            if market_edge >= 0.0:
                return ValueClassification.NEUTRAL
            return ValueClassification.NEGATIVE_VALUE
        ```
      - Files: backend/app/prediction/market_intelligence.py
      - Verify: classify_value(0.12) returns STRONG_VALUE

- [ ] 3. **Add MarketValueAssessment dataclass**
      - Add to backend/app/prediction/market_intelligence.py:
        ```python
        @dataclass
        class MarketValueAssessment:
            market_name: str
            model_probability: float
            real_odds: Optional[float]
            implied_probability: Optional[float]
            market_edge: Optional[float]
            value_classification: ValueClassification
            bookmaker: Optional[str]
        ```
      - Files: backend/app/prediction/market_intelligence.py
      - Verify: dataclass instantiates correctly

- [ ] 4. **Create market_movement.py with OddsMovement dataclass**
      - Create backend/app/domain/market_movement.py
      - Add docstring stating movement is ONLY calculated from actual timestamped odds, never fabricated
      - Add OddsMovement dataclass:
        ```python
        @dataclass
        class OddsMovement:
            market_name: str
            selection_label: str
            bookmaker: str
            current_odds: float
            previous_odds: Optional[float]
            odds_change: Optional[float]
            odds_change_percentage: Optional[float]
            movement_timestamp: datetime
            previous_timestamp: Optional[datetime]
            
            def __post_init__(self):
                if self.current_odds <= 1.0:
                    raise ValueError("current_odds must be > 1.0")
                if self.previous_odds is not None and self.previous_odds <= 1.0:
                    raise ValueError("previous_odds must be > 1.0")
        ```
      - Files: backend/app/domain/market_movement.py
      - Verify: OddsMovement(..., current_odds=0.5) raises ValueError

- [ ] 5. **Add calculate_odds_movement helper function**
      - Add to backend/app/domain/market_movement.py:
        ```python
        def calculate_odds_movement(
            current_odds: float,
            previous_odds: Optional[float]
        ) -> Tuple[Optional[float], Optional[float]]:
            if previous_odds is None:
                return (None, None)
            change = current_odds - previous_odds
            change_pct = (change / previous_odds) * 100
            return (change, change_pct)
        ```
      - Files: backend/app/domain/market_movement.py
      - Verify: calculate_odds_movement(2.2, 2.0) returns (0.2, 10.0)

- [ ] 6. **Extend SourceIntelligence with merge_bookmaker_odds()**
      - Read backend/app/providers/source_intelligence.py to understand merge_statistics() pattern
      - Add merge_bookmaker_odds() method to SourceIntelligence class:
        ```python
        def merge_bookmaker_odds(
            self,
            odds_list: List[Odds],
            strategy: str = 'first'
        ) -> Optional[Odds]:
            # Follow same pattern as merge_statistics()
            # Strategies: 'first', 'most_complete', 'highest_quality'
        ```
      - Implementation: 'first' = first non-None odds per field, 'most_complete' = provider with most non-None odds fields, 'highest_quality' = provider with highest odds coverage score
      - Files: backend/app/providers/source_intelligence.py
      - Verify: merge_bookmaker_odds([odds1, odds2], 'first') returns merged Odds

- [ ] 7. **Add unit tests for market_intelligence**
      - Create backend/tests/test_market_intelligence.py
      - Add tests:
        - test_classify_value_thresholds(): verify classification thresholds
        - test_classify_value_unavailable_when_none(): verify UNAVAILABLE for None
        - test_market_value_assessment_dataclass(): verify dataclass works
      - Files: backend/tests/test_market_intelligence.py
      - Verify: cd c:\FootballIntelligence\backend; python -m pytest tests/test_market_intelligence.py -v

- [ ] 8. **Add unit tests for market_movement**
      - Create backend/tests/test_market_movement.py
      - Add tests:
        - test_odds_movement_dataclass(): verify OddsMovement works
        - test_calculate_odds_movement(): verify calculation
        - test_odds_movement_validation_rejects_invalid_odds(): verify validation
      - Files: backend/tests/test_market_movement.py
      - Verify: cd c:\FootballIntelligence\backend; python -m pytest tests/test_market_movement.py -v

- [ ] 9. **Add unit tests for merge_bookmaker_odds**
      - Add to backend/tests/test_source_intelligence.py:
        - test_merge_bookmaker_odds_first_strategy(): verify field-by-field merge
        - test_merge_bookmaker_odds_most_complete_strategy(): verify most complete provider wins
      - Files: backend/tests/test_source_intelligence.py
      - Verify: cd c:\FootballIntelligence\backend; python -m pytest tests/test_source_intelligence.py::test_merge_bookmaker_odds_first_strategy -v

- [ ] 10. **Run all Phase 3 tests**
      - Verify all new tests pass
      - Files: backend/tests/
      - Verify: cd c:\FootballIntelligence\backend; python -m pytest tests/test_market_intelligence.py tests/test_market_movement.py tests/test_source_intelligence.py -v

---

### FEAT-004: API + Minimal Frontend Integration

**Objective**: Extend API schemas with optional Phase 5 fields (backward compatible), extend frontend types, extend MensionePickCard with minimal UI additions.

- [ ] 1. **Read existing API schema structure**
      - Read backend/app/api/v1/schemas.py
      - Understand existing MarketOutcomeResponse and MarketAnalysisResponse structures
      - Files: backend/app/api/v1/schemas.py
      - Verify: confirm existing structure

- [ ] 2. **Extend MarketOutcomeResponse with Phase 5 fields**
      - Add to backend/app/api/v1/schemas.py MarketOutcomeResponse class:
        - real_odds: Optional[float] = Field(None, description="Real bookmaker odds if available")
        - implied_probability: Optional[float] = Field(None, description="Implied probability from real odds")
        - market_edge: Optional[float] = Field(None, description="Market edge (model_prob - implied_prob)")
        - bookmaker: Optional[str] = Field(None, description="Bookmaker source")
        - odds_timestamp: Optional[datetime] = Field(None, description="When odds were recorded")
      - All fields optional, default None (backward compatible)
      - Files: backend/app/api/v1/schemas.py
      - Verify: MarketOutcomeResponse schema loads without errors

- [ ] 3. **Verify MarketAnalysisResponse has bookmaker_overround field**
      - Check if MarketAnalysisResponse has bookmaker_overround: Optional[float] = Field(None)
      - Add if missing
      - Files: backend/app/api/v1/schemas.py
      - Verify: field exists

- [ ] 4. **Verify API endpoint mapping**
      - Read backend/app/api/v1/endpoints/predictions.py (or wherever prediction endpoints are defined)
      - Verify MarketOutcomeResponse is mapped from MarketOutcome domain objects
      - If mapping exists, extend it to include Phase 5 fields when available
      - Files: backend/app/api/v1/endpoints/ (find prediction endpoints)
      - Verify: API returns Phase 5 fields when domain objects have them

- [ ] 5. **Extend frontend MarketOutcomeResponse interface**
      - Read frontend/src/api/types.ts
      - Extend MarketOutcomeResponse interface with optional Phase 5 fields:
        - real_odds?: number | null
        - implied_probability?: number | null
        - market_edge?: number | null
        - bookmaker?: string | null
        - odds_timestamp?: string | null
      - Files: frontend/src/api/types.ts
      - Verify: npm run type-check passes

- [ ] 6. **Read MensionePickCard structure**
      - Read frontend/src/components/predictions/MensionePickCard.tsx
      - Understand current structure: tabs (general, first-half, full-match), existing props, technical details section
      - DO NOT redesign the card
      - Files: frontend/src/components/predictions/MensionePickCard.tsx
      - Verify: understand structure

- [ ] 7. **Extend MensionePickCardProps interface**
      - Add to frontend/src/components/predictions/MensionePickCard.tsx MensionePickCardProps interface at the end:
        - marketEdge?: number | null
        - impliedProbability?: number | null
        - bookmakerSource?: string | null
        - valueClassification?: string | null
      - Files: frontend/src/components/predictions/MensionePickCard.tsx
      - Verify: TypeScript compiles

- [ ] 8. **Add minimal Phase 5 UI to technical details section**
      - In frontend/src/components/predictions/MensionePickCard.tsx, find technical details section (likely in 'general' tab)
      - ADD conditional rendering ONLY when Phase 5 props are available:
        - Display market edge as percentage if marketEdge !== null: `{(marketEdge * 100).toFixed(1)}%`
        - Display implied probability as percentage if impliedProbability !== null: `{(impliedProbability * 100).toFixed(1)}%`
        - Display bookmaker source if bookmakerSource !== null: `{bookmakerSource}`
        - Display value classification badge if valueClassification !== null: `<span className="value-badge">{valueClassification}</span>`
      - Use existing card styling patterns
      - Maximum 4-5 lines of new UI
      - Files: frontend/src/components/predictions/MensionePickCard.tsx
      - Verify: card displays Phase 5 data when available, unchanged when not available

- [ ] 9. **Run frontend type-check**
      - Verify no TypeScript errors
      - Files: frontend/
      - Verify: cd c:\FootballIntelligence\frontend; npm run type-check (must pass with 0 errors)

- [ ] 10. **Run backend tests**
      - Verify all tests still pass (886+ passing, 15 skipped)
      - Files: backend/tests/
      - Verify: cd c:\FootballIntelligence\backend; python -m pytest tests/ -v

- [ ] 11. **Run API tests**
      - Verify API endpoints still work
      - Files: backend/tests/test_api_matches.py
      - Verify: cd c:\FootballIntelligence\backend; python -m pytest tests/test_api_matches.py -v

---

## Final Verification

After all FEATs complete:

1. **Backend full test suite**: cd c:\FootballIntelligence\backend; python -m pytest tests/ -v
   - Expected: 886+ tests passing, 15 skipped (baseline maintained or improved)

2. **Frontend type-check**: cd c:\FootballIntelligence\frontend; npm run type-check
   - Expected: 0 errors

3. **Frontend build**: cd c:\FootballIntelligence\frontend; npm run build
   - Expected: successful build

4. **Verify Phase 4 intact**:
   - cd c:\FootballIntelligence\backend; python -m pytest tests/test_source_intelligence.py tests/test_data_quality.py -v
   - Expected: all tests pass

5. **Verify existing odds/market/KOMBİNE behavior intact**:
   - cd c:\FootballIntelligence\backend; python -m pytest tests/test_market_analysis.py tests/test_market_derivation.py tests/test_mensione_pick.py -v
   - Expected: all tests pass

---

## Summary of Architecture Changes

### Files Extended (NOT replaced)

- backend/app/domain/odds.py — added Phase 5 fields
- backend/app/prediction/market_analysis.py — added Phase 5 fields to dataclasses, added normalize_market_probabilities()
- backend/app/providers/source_intelligence.py — added merge_bookmaker_odds()
- backend/app/api/v1/schemas.py — added Phase 5 fields to responses
- frontend/src/api/types.ts — added Phase 5 fields to interfaces
- frontend/src/components/predictions/MensionePickCard.tsx — added Phase 5 props and minimal UI

### Files Created

- backend/app/prediction/market_intelligence.py — value classification
- backend/app/domain/market_movement.py — odds movement tracking
- backend/tests/test_market_intelligence.py — unit tests
- backend/tests/test_market_movement.py — unit tests

### Formulas

- Implied Probability: 1 / odds (existing function: implied_probability_from_odds)
- Market Overround: sum(1/odds_i) - 1 (existing function: overround)
- Market Edge: model_prob - implied_prob (existing function: edge)
- Normalized Probabilities: [p/sum(probs) for p in probs] (new function: normalize_market_probabilities)
- Odds Movement: (current - previous) and (change/previous)*100 (new function: calculate_odds_movement)
- Value Classification: if edge >= 10%: STRONG_VALUE; elif edge >= 5%: VALUE; elif edge >= 0%: NEUTRAL; else: NEGATIVE_VALUE (new function: classify_value)

### Data Integrity Guarantees

1. Real bookmaker odds remain distinct from MENSIONE fair odds — separate fields in MarketOutcome
2. MENSIONE probability remains distinct from market implied probability — separate fields
3. Confidence is never converted into odds — confidence and odds remain separate concepts
4. Fair odds are never treated as bookmaker odds — separate fields with clear labels
5. Missing real odds remain None/null, never fabricated — validation enforces this
6. Market movement only from actual timestamped odds — OddsMovement requires timestamps
7. Source/bookmaker provenance preserved — bookmaker field tracks source
8. Existing KOMBİNE logic uses real bookmaker odds only — no changes to KOMBİNE
9. Phase 4 DataQualityEngine and SourceIntelligence reused — extended, not duplicated
10. DevelopmentProvider remains deterministic — Phase 5 fields populated with deterministic values
11. No real network calls in unit tests — all tests use DevelopmentProvider
12. Existing API contracts backward compatible — all Phase 5 fields optional

---

## Warnings

- DO NOT create duplicate market/odds/probability systems
- DO NOT modify existing prediction, confidence, or KOMBİNE logic
- DO NOT fabricate odds, movement, or probabilities
- DO NOT mix MENSIONE probability with market implied probability
- DO NOT make breaking API changes
- DO NOT redesign MensionePickCard
- DO NOT add real network calls to tests
- DO NOT make DevelopmentProvider non-deterministic

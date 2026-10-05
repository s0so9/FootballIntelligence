"""Tests for market analysis module."""

import pytest
from app.prediction.market_analysis import (
    MarketAnalyser,
    probability_to_fair_odds,
    implied_probability_from_odds,
    overround,
    edge,
    has_value,
)


class TestConversionFunctions:
    """Test core conversion functions."""
    
    def test_probability_to_fair_odds(self):
        """Test probability to fair odds conversion."""
        # 50% probability = 2.0 odds
        assert probability_to_fair_odds(0.5) == pytest.approx(2.0)
        
        # 25% probability = 4.0 odds
        assert probability_to_fair_odds(0.25) == pytest.approx(4.0)
        
        # 100% probability = 1.0 odds
        assert probability_to_fair_odds(1.0) == pytest.approx(1.0)
        
        # 10% probability = 10.0 odds
        assert probability_to_fair_odds(0.1) == pytest.approx(10.0)
    
    def test_probability_to_fair_odds_invalid(self):
        """Test invalid probabilities."""
        # Zero probability should raise error
        with pytest.raises(ValueError, match="division by zero"):
            probability_to_fair_odds(0.0)
        
        # Negative probability should raise error
        with pytest.raises(ValueError, match="Invalid probability"):
            probability_to_fair_odds(-0.1)
        
        # Probability > 1 should raise error
        with pytest.raises(ValueError, match="Invalid probability"):
            probability_to_fair_odds(1.5)
    
    def test_implied_probability_from_odds(self):
        """Test implied probability from odds."""
        # 2.0 odds = 50% probability
        assert implied_probability_from_odds(2.0) == pytest.approx(0.5)
        
        # 4.0 odds = 25% probability
        assert implied_probability_from_odds(4.0) == pytest.approx(0.25)
        
        # 1.0 odds = 100% probability
        assert implied_probability_from_odds(1.0) == pytest.approx(1.0)
    
    def test_implied_probability_invalid_odds(self):
        """Test invalid odds."""
        # Odds below 1.0 are invalid
        with pytest.raises(ValueError, match="Invalid decimal odds"):
            implied_probability_from_odds(0.5)
        
        with pytest.raises(ValueError, match="Invalid decimal odds"):
            implied_probability_from_odds(0.0)
    
    def test_overround(self):
        """Test overround calculation."""
        # Fair market: 50-50
        assert overround([2.0, 2.0]) == pytest.approx(0.0)
        
        # Fair three-way market
        assert overround([3.0, 3.0, 3.0]) == pytest.approx(0.0)
        
        # Market with 5% margin
        # 1.9 + 1.9 odds = 0.526 + 0.526 = 1.052 total, 0.052 overround
        assert overround([1.9, 1.9]) == pytest.approx(0.0526, abs=0.001)
    
    def test_edge(self):
        """Test edge calculation."""
        # Fair odds match fair probability: edge = 0
        assert edge(0.5, 2.0) == pytest.approx(0.0)
        
        # Bookmaker overprices (odds too low): positive edge
        assert edge(0.5, 1.8) > 0
        
        # Bookmaker underprices (odds too high): negative edge (value!)
        assert edge(0.5, 2.2) < 0
    
    def test_has_value(self):
        """Test value detection."""
        # No value when odds match probability
        assert has_value(0.5, 2.0, threshold=0.03) is False
        
        # Value when bookmaker odds significantly exceed fair odds
        # Fair: 0.5 prob = 2.0 odds, Bookmaker: 2.5 odds = 0.4 implied
        # Edge = 0.4 - 0.5 = -0.1 (bookmaker underestimates)
        # This is good value
        assert has_value(0.5, 2.5, threshold=0.03) is True
        
        # No value when edge is below threshold
        assert has_value(0.5, 2.05, threshold=0.03) is False


class TestMarketAnalyser:
    """Test MarketAnalyser class."""
    
    def test_analyse_match_1x2_only(self):
        """Test market analysis with 1X2 probabilities only."""
        analyser = MarketAnalyser(is_development_data=True)
        
        result = analyser.analyse_match(
            match_id="test_match_1",
            home_win_prob=0.50,
            draw_prob=0.28,
            away_win_prob=0.22,
        )
        
        assert result.match_id == "test_match_1"
        assert result.is_development_data is True
        assert len(result.markets) == 1  # Only 1X2
        
        market_1x2 = result.markets[0]
        assert market_1x2.market_type == "match_result"
        assert len(market_1x2.outcomes) == 3
        
        # Check fair odds
        home_outcome = next(o for o in market_1x2.outcomes if o.label == "home")
        assert home_outcome.model_probability == 0.50
        assert home_outcome.fair_odds == pytest.approx(2.0)
        
        # No bookmaker comparison
        assert market_1x2.bookmaker_comparison is None
        assert market_1x2.has_bookmaker_odds is False
        assert result.any_value_found is False
    
    def test_analyse_match_with_all_markets(self):
        """Test analysis with all supported markets."""
        analyser = MarketAnalyser(is_development_data=True)
        
        result = analyser.analyse_match(
            match_id="test_match_2",
            home_win_prob=0.45,
            draw_prob=0.30,
            away_win_prob=0.25,
            btts_prob=0.60,
            over_2_5_prob=0.65,
            over_3_5_prob=0.38,
            correct_score_probs={"1-1": 0.12, "2-1": 0.10, "0-0": 0.08},
        )
        
        assert len(result.markets) == 5  # 1X2, BTTS, O/U 2.5, O/U 3.5, Correct Score
        
        # Check BTTS market
        btts_market = next(m for m in result.markets if m.market_type == "btts")
        yes_outcome = next(o for o in btts_market.outcomes if o.label == "yes")
        assert yes_outcome.model_probability == 0.60
        
        # Check O/U markets
        ou_25 = next(m for m in result.markets if m.market_type == "over_under" and m.line == 2.5)
        over_outcome = next(o for o in ou_25.outcomes if o.label == "over")
        assert over_outcome.model_probability == 0.65
    
    def test_analyse_match_with_bookmaker_odds(self):
        """Test analysis with real bookmaker odds."""
        analyser = MarketAnalyser(value_threshold=0.03, is_development_data=True)
        
        result = analyser.analyse_match(
            match_id="test_match_3",
            home_win_prob=0.60,  # Model says 60%
            draw_prob=0.25,
            away_win_prob=0.15,
            bookmaker_1x2={
                "home": 2.2,  # Bookmaker: 2.2 odds = 45.5% implied
                "draw": 3.5,  # 28.6% implied
                "away": 5.0,  # 20% implied
            },
        )
        
        # Should have bookmaker comparison
        market_1x2 = result.markets[0]
        assert market_1x2.has_bookmaker_odds is True
        assert market_1x2.bookmaker_comparison is not None
        assert len(market_1x2.bookmaker_comparison) == 3
        
        # Check home value
        home_comp = next(c for c in market_1x2.bookmaker_comparison if c.label == "home")
        assert home_comp.fair_probability == 0.60
        assert home_comp.bookmaker_odds == 2.2
        assert home_comp.implied_probability == pytest.approx(1/2.2)
        
        # Edge should be negative (value) since model prob > implied prob
        assert home_comp.edge_value < 0
        
        # Should flag as having value
        assert home_comp.has_value_flag is True
        assert result.any_value_found is True
    
    def test_analyse_match_invalid_probabilities(self):
        """Test handling of invalid probabilities."""
        analyser = MarketAnalyser(is_development_data=True)
        
        # Probabilities that don't sum to 1.0 should still work
        # (normalization happens in the models, not here)
        result = analyser.analyse_match(
            match_id="test_match_4",
            home_win_prob=0.40,
            draw_prob=0.30,
            away_win_prob=0.20,  # Sum = 0.90
        )
        
        # Should still create market
        assert len(result.markets) == 1
        assert len(result.warnings) == 0
    
    def test_analyse_match_missing_data(self):
        """Test analysis with missing/insufficient data."""
        analyser = MarketAnalyser(is_development_data=True)
        
        result = analyser.analyse_match(
            match_id="test_match_5",
            # No probabilities provided
        )
        
        # Should return empty markets
        assert len(result.markets) == 0
        assert result.any_value_found is False
        assert result.bookmaker_odds_available is False
    
    def test_calibrated_probabilities(self):
        """Test that calibrated probabilities are used when available."""
        analyser = MarketAnalyser(is_development_data=True)
        
        result = analyser.analyse_match(
            match_id="test_match_6",
            home_win_prob=0.50,
            draw_prob=0.28,
            away_win_prob=0.22,
            home_win_calibrated=0.55,  # Calibrated higher
            draw_calibrated=0.26,
            away_win_calibrated=0.19,
        )
        
        market_1x2 = result.markets[0]
        home_outcome = next(o for o in market_1x2.outcomes if o.label == "home")
        
        # Should use calibrated probability for fair odds
        assert home_outcome.model_probability == 0.50
        assert home_outcome.calibrated_probability == 0.55
        assert home_outcome.best_probability == 0.55
        assert home_outcome.fair_odds == pytest.approx(1/0.55)
    
    def test_deterministic_output(self):
        """Test that same inputs produce same outputs."""
        analyser = MarketAnalyser(is_development_data=True)
        
        inputs = {
            "match_id": "test_match_7",
            "home_win_prob": 0.47,
            "draw_prob": 0.29,
            "away_win_prob": 0.24,
            "btts_prob": 0.58,
            "over_2_5_prob": 0.63,
        }
        
        result1 = analyser.analyse_match(**inputs)
        result2 = analyser.analyse_match(**inputs)
        
        # Should produce identical results
        assert len(result1.markets) == len(result2.markets)
        
        for m1, m2 in zip(result1.markets, result2.markets):
            assert m1.market_type == m2.market_type
            assert len(m1.outcomes) == len(m2.outcomes)
            
            for o1, o2 in zip(m1.outcomes, m2.outcomes):
                assert o1.label == o2.label
                assert o1.model_probability == o2.model_probability
                assert o1.fair_odds == pytest.approx(o2.fair_odds)
    
    def test_no_fabricated_bookmaker_odds(self):
        """Test that bookmaker odds are never fabricated."""
        analyser = MarketAnalyser(is_development_data=True)
        
        # Analyse without providing bookmaker odds
        result = analyser.analyse_match(
            match_id="test_match_8",
            home_win_prob=0.50,
            draw_prob=0.28,
            away_win_prob=0.22,
            btts_prob=0.60,
            over_2_5_prob=0.65,
        )
        
        # No market should have bookmaker comparison
        for market in result.markets:
            assert market.bookmaker_comparison is None
            assert market.bookmaker_overround is None
            assert market.has_bookmaker_odds is False
        
        # Should not claim any value found
        assert result.any_value_found is False
        assert result.bookmaker_odds_available is False


class TestPhase5MarketIntelligence:
    """Test Phase 5 market intelligence enhancements."""
    
    def test_market_outcome_phase5_fields_optional(self):
        """Test that Phase 5 fields on MarketOutcome are optional."""
        from app.prediction.market_analysis import MarketOutcome
        
        # Should create outcome without Phase 5 fields
        outcome = MarketOutcome(
            label="home",
            model_probability=0.50,
            calibrated_probability=None,
        )
        
        assert outcome.label == "home"
        assert outcome.model_probability == 0.50
        assert outcome.real_odds is None
        assert outcome.implied_probability is None
        assert outcome.market_edge is None
        assert outcome.bookmaker is None
        assert outcome.odds_timestamp is None
    
    def test_normalize_market_probabilities(self):
        """Test normalize_market_probabilities helper function."""
        from app.prediction.market_analysis import normalize_market_probabilities
        
        # Standard case: probabilities with overround
        implied = [0.526, 0.526]  # Sum = 1.052 (5.2% overround)
        normalized = normalize_market_probabilities(implied)
        
        assert len(normalized) == 2
        assert normalized[0] == pytest.approx(0.50, abs=0.01)
        assert normalized[1] == pytest.approx(0.50, abs=0.01)
        assert sum(normalized) == pytest.approx(1.0)
        
        # Three-way market
        implied_3way = [0.45, 0.30, 0.25]  # Already sums to 1.0
        normalized_3way = normalize_market_probabilities(implied_3way)
        
        assert sum(normalized_3way) == pytest.approx(1.0)
        assert normalized_3way[0] == pytest.approx(0.45)
        assert normalized_3way[1] == pytest.approx(0.30)
        assert normalized_3way[2] == pytest.approx(0.25)
        
        # Edge case: zero total
        zero_probs = [0.0, 0.0]
        normalized_zero = normalize_market_probabilities(zero_probs)
        assert normalized_zero == [0.0, 0.0]
    
    def test_market_analyser_populates_phase5_fields_when_odds_available(self):
        """Test that MarketAnalyser populates Phase 5 fields when bookmaker odds are supplied."""
        from app.prediction.market_analysis import MarketAnalyser
        
        analyser = MarketAnalyser(value_threshold=0.03, is_development_data=True)
        
        result = analyser.analyse_match(
            match_id="test_phase5_1",
            home_win_prob=0.60,
            draw_prob=0.25,
            away_win_prob=0.15,
            bookmaker_1x2={
                "home": 2.2,
                "draw": 3.5,
                "away": 5.0,
            },
        )
        
        market_1x2 = result.markets[0]
        
        # Find home outcome
        home_outcome = next(o for o in market_1x2.outcomes if o.label == "home")
        
        # Phase 5 fields should be populated
        assert home_outcome.real_odds == 2.2
        assert home_outcome.implied_probability == pytest.approx(1/2.2)
        assert home_outcome.market_edge is not None
        assert home_outcome.bookmaker == "home"
        assert home_outcome.odds_timestamp is None  # Placeholder
        
        # Verify edge calculation is correct
        # Edge = implied_probability - fair_probability
        # Fair prob = 0.60, Implied = 1/2.2 = 0.4545
        # Edge = 0.4545 - 0.60 = -0.1455 (negative = value)
        expected_edge = (1/2.2) - 0.60
        assert home_outcome.market_edge == pytest.approx(expected_edge)
    
    def test_phase5_fields_remain_none_when_no_odds(self):
        """Test that Phase 5 fields remain None when no bookmaker odds supplied."""
        from app.prediction.market_analysis import MarketAnalyser
        
        analyser = MarketAnalyser(is_development_data=True)
        
        result = analyser.analyse_match(
            match_id="test_phase5_2",
            home_win_prob=0.50,
            draw_prob=0.28,
            away_win_prob=0.22,
            # No bookmaker odds
        )
        
        market_1x2 = result.markets[0]
        
        # All outcomes should have None for Phase 5 fields
        for outcome in market_1x2.outcomes:
            assert outcome.real_odds is None
            assert outcome.implied_probability is None
            assert outcome.market_edge is None
            assert outcome.bookmaker is None
            assert outcome.odds_timestamp is None

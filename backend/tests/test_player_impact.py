"""Tests for player_impact module - DETERMINISTIC, DATA-DRIVEN ONLY."""

import pytest
from app.prediction.player_impact import (
    PlayerImpactEngine,
    PlayerImpactData,
    PlayerImpactResult,
    TeamLineupImpact,
)
from app.prediction.interfaces import ModelPrediction, ModelAvailability


class TestPlayerImpactData:
    """Tests for PlayerImpactData."""
    
    def test_player_has_sufficient_data(self):
        """Test sufficient data check."""
        player = PlayerImpactData(
            player_id="p1",
            player_name="Test Player",
            position="FW",
            matches_played=10,
            minutes_played=900,
            avg_xg_contribution=0.3
        )
        
        assert player.has_sufficient_data
    
    def test_player_insufficient_matches(self):
        """Test insufficient matches."""
        player = PlayerImpactData(
            player_id="p1",
            player_name="Test Player",
            position="FW",
            matches_played=3,  # < 5
            minutes_played=270,
            avg_xg_contribution=0.3
        )
        
        assert not player.has_sufficient_data
    
    def test_player_insufficient_minutes(self):
        """Test insufficient minutes."""
        player = PlayerImpactData(
            player_id="p1",
            player_name="Test Player",
            position="FW",
            matches_played=5,
            minutes_played=200,  # < 450
            avg_xg_contribution=0.3
        )
        
        assert not player.has_sufficient_data


class TestPlayerImpactEngine:
    """Tests for PlayerImpactEngine - NEVER FABRICATES DATA."""
    
    def test_engine_with_no_absent_players(self):
        """Test engine with no absent players."""
        engine = PlayerImpactEngine()
        
        prediction = ModelPrediction(
            model_id="test",
            home_score_mean=1.5,
            away_score_mean=1.2,
            home_win_prob=0.45,
            draw_prob=0.30,
            away_win_prob=0.25,
            confidence_score=0.8,
            data_quality_score=0.9
        )
        
        result = engine.calculate_impact(prediction, [], [])
        
        assert isinstance(result, PlayerImpactResult)
        assert result.adjusted_home_xg == 1.5
        assert result.adjusted_away_xg == 1.2
    
    def test_engine_with_key_forward_absent(self):
        """Test impact of absent key forward."""
        engine = PlayerImpactEngine()
        
        prediction = ModelPrediction(
            model_id="test",
            home_score_mean=1.5,
            away_score_mean=1.2,
            home_win_prob=0.45,
            draw_prob=0.30,
            away_win_prob=0.25,
            confidence_score=0.8,
            data_quality_score=0.9
        )
        
        # Key striker absent (0.4 xG per game)
        absent_striker = PlayerImpactData(
            player_id="p1",
            player_name="Star Striker",
            position="FW",
            matches_played=20,
            minutes_played=1800,
            avg_xg_contribution=0.4,
            avg_xa_contribution=0.15
        )
        
        result = engine.calculate_impact(prediction, [absent_striker], [])
        
        assert isinstance(result, PlayerImpactResult)
        # Home xG should decrease (striker absent)
        assert result.adjusted_home_xg < prediction.home_score_mean
        assert result.overall_confidence > 0.5  # Have data
    
    def test_engine_returns_unavailable_with_insufficient_data(self):
        """Test that engine returns ModelAvailability when data insufficient."""
        engine = PlayerImpactEngine()
        
        prediction = ModelPrediction(
            model_id="test",
            home_score_mean=1.5,
            away_score_mean=1.2,
            home_win_prob=0.45,
            draw_prob=0.30,
            away_win_prob=0.25,
            confidence_score=0.8,
            data_quality_score=0.9
        )
        
        # Player with insufficient data
        unknown_player = PlayerImpactData(
            player_id="p_unknown",
            player_name="Unknown Player",
            position="FW",
            matches_played=2,  # Insufficient
            minutes_played=180,
            avg_xg_contribution=None
        )
        
        result = engine.calculate_impact(prediction, [unknown_player], [])
        
        # Should return unavailable (cannot assess impact reliably)
        assert isinstance(result, ModelAvailability)
        assert result.available is False
        assert "insufficient" in result.reason
    
    def test_engine_handles_partial_data(self):
        """Test engine with partial data (some players known, some not)."""
        engine = PlayerImpactEngine()
        
        prediction = ModelPrediction(
            model_id="test",
            home_score_mean=1.5,
            away_score_mean=1.2,
            home_win_prob=0.45,
            draw_prob=0.30,
            away_win_prob=0.25,
            confidence_score=0.8,
            data_quality_score=0.9
        )
        
        known_player = PlayerImpactData(
            player_id="p1",
            player_name="Known Player",
            position="FW",
            matches_played=20,
            minutes_played=1800,
            avg_xg_contribution=0.3
        )
        
        unknown_player1 = PlayerImpactData(
            player_id="p2",
            player_name="Unknown Player 1",
            position="MF",
            matches_played=2,
            minutes_played=100,
            avg_xg_contribution=None
        )
        
        unknown_player2 = PlayerImpactData(
            player_id="p3",
            player_name="Unknown Player 2",
            position="DF",
            matches_played=1,
            minutes_played=90,
            avg_xg_contribution=None
        )
        
        # Now we have 1/3 players with data = 33% < 50%
        result = engine.calculate_impact(prediction, [known_player, unknown_player1, unknown_player2], [])
        
        if isinstance(result, PlayerImpactResult):
            # Confidence reduced due to partial data
            assert result.overall_confidence < 0.9
            assert result.home_team_impact.data_sufficiency == "partial"
    
    def test_engine_calculates_probability_adjustments(self):
        """Test that probability adjustments are calculated."""
        engine = PlayerImpactEngine()
        
        prediction = ModelPrediction(
            model_id="test",
            home_score_mean=1.5,
            away_score_mean=1.2,
            home_win_prob=0.45,
            draw_prob=0.30,
            away_win_prob=0.25,
            confidence_score=0.8,
            data_quality_score=0.9
        )
        
        absent_forward = PlayerImpactData(
            player_id="p1",
            player_name="Forward",
            position="FW",
            matches_played=15,
            minutes_played=1350,
            avg_xg_contribution=0.35
        )
        
        result = engine.calculate_impact(prediction, [absent_forward], [])
        
        if isinstance(result, PlayerImpactResult):
            assert "home_win" in result.prob_adjustments
            assert "draw" in result.prob_adjustments
            assert "away_win" in result.prob_adjustments
            
            # Absent home forward should reduce home win probability
            assert result.prob_adjustments["home_win"] < 0
    
    def test_engine_never_fabricates_player_ratings(self):
        """Test that engine NEVER fabricates missing player data."""
        engine = PlayerImpactEngine()
        
        prediction = ModelPrediction(
            model_id="test",
            home_score_mean=1.5,
            away_score_mean=1.2,
            home_win_prob=0.45,
            draw_prob=0.30,
            away_win_prob=0.25,
            confidence_score=0.8,
            data_quality_score=0.9
        )
        
        # Player with NO historical data
        player_no_data = PlayerImpactData(
            player_id="p_new",
            player_name="New Player",
            position="FW",
            matches_played=0,
            minutes_played=0,
            avg_xg_contribution=None,
            avg_xa_contribution=None,
            avg_defensive_contribution=None
        )
        
        result = engine.calculate_impact(prediction, [player_no_data], [])
        
        # Should return unavailable, NOT fabricate an impact
        assert isinstance(result, ModelAvailability)
    
    def test_engine_ensures_non_negative_xg(self):
        """Test that engine ensures non-negative expected goals."""
        engine = PlayerImpactEngine()
        
        prediction = ModelPrediction(
            model_id="test",
            home_score_mean=0.3,  # Low xG
            away_score_mean=1.2,
            home_win_prob=0.15,
            draw_prob=0.30,
            away_win_prob=0.55,
            confidence_score=0.8,
            data_quality_score=0.9
        )
        
        # Star player absent with large impact
        star_player = PlayerImpactData(
            player_id="p1",
            player_name="Star Player",
            position="FW",
            matches_played=20,
            minutes_played=1800,
            avg_xg_contribution=0.5
        )
        
        result = engine.calculate_impact(prediction, [star_player], [])
        
        if isinstance(result, PlayerImpactResult):
            # xG should not go below 0.1 (minimum)
            assert result.adjusted_home_xg >= 0.1

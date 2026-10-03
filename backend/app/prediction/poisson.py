"""Poisson-based football match prediction model.

This module implements a foundational Poisson prediction model for football matches.
The Poisson distribution models the number of goals scored by each team independently.

Mathematical Foundation:
- P(X = k) = (λ^k * e^(-λ)) / k!
- where λ (lambda) is the expected goals parameter
- k is the number of goals

The model calculates:
1. Expected goals for home and away teams (lambda parameters)
2. Probability distribution for each team's goals (0 to max_goals)
3. Joint probability for all scorelines
4. Market probabilities (1X2, BTTS, Over/Under, Correct Score)
"""

import math
from typing import Dict, Tuple, Optional, List
from dataclasses import dataclass


@dataclass
class PoissonPrediction:
    """Result of Poisson prediction."""
    
    home_lambda: float
    away_lambda: float
    max_goals: int
    
    # Goal probabilities
    home_goal_probabilities: List[float]  # P(home scores 0), P(home scores 1), ...
    away_goal_probabilities: List[float]  # P(away scores 0), P(away scores 1), ...
    
    # Scoreline matrix
    scoreline_probabilities: Dict[Tuple[int, int], float]  # (home_goals, away_goals) -> probability
    
    # Market probabilities
    home_win_probability: float
    draw_probability: float
    away_win_probability: float
    
    btts_yes_probability: float
    btts_no_probability: float
    
    over_under_probabilities: Dict[float, Tuple[float, float]]  # line -> (over_prob, under_prob)
    
    # Top N correct scores
    top_scorelines: List[Tuple[Tuple[int, int], float]]  # [(scoreline, probability), ...]
    
    # Probability mass captured (should be close to 1.0)
    probability_mass_captured: float


class PoissonModel:
    """Poisson-based football prediction model.
    
    This model assumes:
    1. Goals scored by each team follow independent Poisson distributions
    2. The expected goals (lambda) can be estimated from team strength features
    3. Match outcomes are determined by the joint goal distribution
    
    Limitations:
    - Assumes independence between home and away goals (simplification)
    - Does not account for correlation in low-scoring matches
    - Truncates distribution at max_goals
    """
    
    def __init__(self, max_goals: int = 10):
        """Initialize Poisson model.
        
        Args:
            max_goals: Maximum goals to consider in distributions (default: 10)
                      Higher values capture more probability mass but increase computation
        
        Raises:
            ValueError: If max_goals < 1
        """
        if max_goals < 1:
            raise ValueError("max_goals must be at least 1")
        
        self.max_goals = max_goals
    
    def predict(
        self,
        home_lambda: float,
        away_lambda: float,
    ) -> PoissonPrediction:
        """Generate prediction for a match using Poisson model.
        
        Args:
            home_lambda: Expected goals for home team (must be >= 0)
            away_lambda: Expected goals for away team (must be >= 0)
        
        Returns:
            PoissonPrediction with all probabilities
        
        Raises:
            ValueError: If lambda values are invalid
        """
        # Validate inputs
        if home_lambda < 0:
            raise ValueError(f"home_lambda must be >= 0, got {home_lambda}")
        if away_lambda < 0:
            raise ValueError(f"away_lambda must be >= 0, got {away_lambda}")
        
        # Calculate goal probabilities for each team
        home_probs = self._calculate_goal_probabilities(home_lambda)
        away_probs = self._calculate_goal_probabilities(away_lambda)
        
        # Calculate scoreline matrix
        scoreline_probs = self._calculate_scoreline_probabilities(home_probs, away_probs)
        
        # Calculate market probabilities
        home_win, draw, away_win = self._calculate_1x2_probabilities(scoreline_probs)
        btts_yes, btts_no = self._calculate_btts_probabilities(scoreline_probs)
        over_under = self._calculate_over_under_probabilities(scoreline_probs)
        
        # Get top scorelines
        top_scorelines = self._get_top_scorelines(scoreline_probs, n=10)
        
        # Calculate probability mass captured
        total_prob = sum(scoreline_probs.values())
        
        return PoissonPrediction(
            home_lambda=home_lambda,
            away_lambda=away_lambda,
            max_goals=self.max_goals,
            home_goal_probabilities=home_probs,
            away_goal_probabilities=away_probs,
            scoreline_probabilities=scoreline_probs,
            home_win_probability=home_win,
            draw_probability=draw,
            away_win_probability=away_win,
            btts_yes_probability=btts_yes,
            btts_no_probability=btts_no,
            over_under_probabilities=over_under,
            top_scorelines=top_scorelines,
            probability_mass_captured=total_prob,
        )
    
    def _calculate_goal_probabilities(self, lambda_: float) -> List[float]:
        """Calculate Poisson probability mass function for 0 to max_goals.
        
        Uses the Poisson PMF: P(X = k) = (λ^k * e^(-λ)) / k!
        
        Args:
            lambda_: Expected goals parameter
        
        Returns:
            List of probabilities [P(0 goals), P(1 goal), ..., P(max_goals)]
        """
        probabilities = []
        
        for k in range(self.max_goals + 1):
            prob = self._poisson_pmf(k, lambda_)
            probabilities.append(prob)
        
        return probabilities
    
    @staticmethod
    def _poisson_pmf(k: int, lambda_: float) -> float:
        """Calculate Poisson probability mass function.
        
        P(X = k) = (λ^k * e^(-λ)) / k!
        
        Args:
            k: Number of events (goals)
            lambda_: Expected number of events (expected goals)
        
        Returns:
            Probability of exactly k events
        """
        # Handle edge case: lambda = 0
        if lambda_ == 0:
            return 1.0 if k == 0 else 0.0
        
        # Calculate using logarithms for numerical stability
        # log(P(X = k)) = k * log(λ) - λ - log(k!)
        log_prob = k * math.log(lambda_) - lambda_ - math.lgamma(k + 1)
        return math.exp(log_prob)
    
    def _calculate_scoreline_probabilities(
        self,
        home_probs: List[float],
        away_probs: List[float],
    ) -> Dict[Tuple[int, int], float]:
        """Calculate joint probability for all scorelines.
        
        Assumes independence: P(home=i, away=j) = P(home=i) * P(away=j)
        
        Args:
            home_probs: Home team goal probabilities
            away_probs: Away team goal probabilities
        
        Returns:
            Dictionary mapping (home_goals, away_goals) to probability
        """
        scorelines = {}
        
        for home_goals in range(self.max_goals + 1):
            for away_goals in range(self.max_goals + 1):
                prob = home_probs[home_goals] * away_probs[away_goals]
                scorelines[(home_goals, away_goals)] = prob
        
        return scorelines
    
    @staticmethod
    def _calculate_1x2_probabilities(
        scoreline_probs: Dict[Tuple[int, int], float]
    ) -> Tuple[float, float, float]:
        """Calculate match result probabilities (1X2).
        
        Home win: home_goals > away_goals
        Draw: home_goals == away_goals
        Away win: home_goals < away_goals
        
        Args:
            scoreline_probs: Scoreline probability matrix
        
        Returns:
            (home_win_prob, draw_prob, away_win_prob)
        """
        home_win = 0.0
        draw = 0.0
        away_win = 0.0
        
        for (home_goals, away_goals), prob in scoreline_probs.items():
            if home_goals > away_goals:
                home_win += prob
            elif home_goals == away_goals:
                draw += prob
            else:  # home_goals < away_goals
                away_win += prob
        
        return home_win, draw, away_win
    
    @staticmethod
    def _calculate_btts_probabilities(
        scoreline_probs: Dict[Tuple[int, int], float]
    ) -> Tuple[float, float]:
        """Calculate Both Teams To Score probabilities.
        
        BTTS Yes: Both teams score at least 1 goal
        BTTS No: At least one team scores 0 goals
        
        Args:
            scoreline_probs: Scoreline probability matrix
        
        Returns:
            (btts_yes_prob, btts_no_prob)
        """
        btts_yes = 0.0
        btts_no = 0.0
        
        for (home_goals, away_goals), prob in scoreline_probs.items():
            if home_goals >= 1 and away_goals >= 1:
                btts_yes += prob
            else:
                btts_no += prob
        
        return btts_yes, btts_no
    
    @staticmethod
    def _calculate_over_under_probabilities(
        scoreline_probs: Dict[Tuple[int, int], float]
    ) -> Dict[float, Tuple[float, float]]:
        """Calculate Over/Under probabilities for common lines.
        
        Args:
            scoreline_probs: Scoreline probability matrix
        
        Returns:
            Dictionary mapping line to (over_prob, under_prob)
            Lines: 0.5, 1.5, 2.5, 3.5, 4.5, 5.5
        """
        lines = [0.5, 1.5, 2.5, 3.5, 4.5, 5.5]
        over_under = {}
        
        for line in lines:
            over = 0.0
            under = 0.0
            
            for (home_goals, away_goals), prob in scoreline_probs.items():
                total_goals = home_goals + away_goals
                
                if total_goals > line:
                    over += prob
                else:
                    under += prob
            
            over_under[line] = (over, under)
        
        return over_under
    
    @staticmethod
    def _get_top_scorelines(
        scoreline_probs: Dict[Tuple[int, int], float],
        n: int = 10
    ) -> List[Tuple[Tuple[int, int], float]]:
        """Get top N most likely scorelines.
        
        Args:
            scoreline_probs: Scoreline probability matrix
            n: Number of top scorelines to return
        
        Returns:
            List of (scoreline, probability) tuples, sorted by probability descending
        """
        sorted_scorelines = sorted(
            scoreline_probs.items(),
            key=lambda x: x[1],
            reverse=True
        )
        
        return sorted_scorelines[:n]
    
    def estimate_lambda_from_features(
        self,
        team_attack_strength: float,
        opponent_defense_strength: float,
        venue_adjustment: float = 1.0,
    ) -> float:
        """Estimate lambda (expected goals) from team features.
        
        Simple estimation: λ = attack_strength * opponent_defense_weakness * venue_adjustment
        
        This is a basic approach. More sophisticated models could:
        - Use league average adjustments
        - Apply regression coefficients
        - Include additional features
        
        Args:
            team_attack_strength: Goals scored per match by team
            opponent_defense_strength: Goals conceded per match by opponent
            venue_adjustment: Home advantage factor (typically 1.1-1.3 for home)
        
        Returns:
            Estimated lambda (expected goals)
        """
        if team_attack_strength < 0 or opponent_defense_strength < 0:
            raise ValueError("Strength values must be non-negative")
        
        # Basic estimation
        lambda_ = team_attack_strength * venue_adjustment
        
        # Adjust based on opponent defense
        # If opponent defense is strong (low conceding rate), reduce lambda
        # If opponent defense is weak (high conceding rate), increase lambda
        if opponent_defense_strength > 0:
            lambda_ *= opponent_defense_strength
        
        return max(0.0, lambda_)  # Ensure non-negative

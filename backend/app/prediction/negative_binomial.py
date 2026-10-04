"""Negative Binomial goal prediction model.

The Negative Binomial (NB) distribution generalises the Poisson distribution
by adding a dispersion parameter r that allows the variance to exceed the mean.
This is useful for football because goal counts often show overdispersion —
the variance is slightly higher than a Poisson model would predict.

Mathematical foundation:
  NB PMF:  P(X = k) = C(k+r-1, k) * p^k * (1-p)^r

  Where:
    r = dispersion parameter (r > 0)
    p = μ / (μ + r)     (μ is the expected goals)
    C(n, k) = n! / (k! * (n-k)!)   (binomial coefficient)

  Alternative parameterisation used here (mean + dispersion):
    P(X = k) = Γ(k+r) / (k! * Γ(r)) * (r/(r+μ))^r * (μ/(r+μ))^k

  Properties:
    Mean     = μ
    Variance = μ + μ²/r

  When r → ∞, the NB distribution converges to Poisson(μ).

  Typical dispersion values for football: r ∈ [5, 50].
  Smaller r = more overdispersion; larger r ≈ Poisson.

The model is compatible with the existing PoissonPrediction interface:
it produces the same market outputs (1X2, BTTS, Over/Under, scorelines)
using the NB distribution instead of Poisson for goal probabilities.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class NegativeBinomialPrediction:
    """Result of Negative Binomial prediction.

    Interface mirrors PoissonPrediction for compatibility with the
    ensemble layer (ModelPredictionInput).
    """

    home_lambda: float
    """Expected goals for home team (distribution mean)."""
    away_lambda: float
    """Expected goals for away team (distribution mean)."""
    dispersion: float
    """Negative Binomial dispersion parameter r."""
    max_goals: int

    # Goal probability arrays
    home_goal_probabilities: List[float]
    away_goal_probabilities: List[float]

    # Scoreline matrix
    scoreline_probabilities: Dict[Tuple[int, int], float]

    # 1X2
    home_win_probability: float
    draw_probability: float
    away_win_probability: float

    # BTTS
    btts_yes_probability: float
    btts_no_probability: float

    # Over/Under
    over_under_probabilities: Dict[float, Tuple[float, float]]

    # Top scorelines
    top_scorelines: List[Tuple[Tuple[int, int], float]]

    # Probability mass captured
    probability_mass_captured: float


# ---------------------------------------------------------------------------
# Negative Binomial model
# ---------------------------------------------------------------------------

class NegativeBinomialModel:
    """Negative Binomial goal prediction model.

    Drop-in complement to PoissonModel.  Uses the NB distribution for
    goal probabilities, which allows variance > mean (overdispersion).

    Usage:
        model = NegativeBinomialModel(dispersion=10.0, max_goals=10)
        result = model.predict(home_lambda=1.5, away_lambda=1.1)

    Dispersion guideline:
        r = 5   → high overdispersion (goals very clumped)
        r = 20  → moderate overdispersion (typical for football)
        r = 100 → near-Poisson behavior
        r → ∞   → converges to Poisson
    """

    DEFAULT_DISPERSION = 20.0
    """Default dispersion parameter (moderately overdispersed)."""

    def __init__(
        self,
        dispersion: float = DEFAULT_DISPERSION,
        max_goals: int = 10,
    ):
        """Initialise the Negative Binomial model.

        Args:
            dispersion: Dispersion parameter r (must be > 0).
                        Higher values → less overdispersion → closer to Poisson.
            max_goals:  Maximum goals to consider in distributions.

        Raises:
            ValueError: If dispersion <= 0 or max_goals < 1.
        """
        if dispersion <= 0.0:
            raise ValueError(f"dispersion must be > 0, got {dispersion}")
        if max_goals < 1:
            raise ValueError(f"max_goals must be >= 1, got {max_goals}")

        self.dispersion = dispersion
        self.max_goals = max_goals

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def predict(
        self,
        home_lambda: float,
        away_lambda: float,
    ) -> NegativeBinomialPrediction:
        """Generate prediction using Negative Binomial distribution.

        Goals for each team are modelled independently.

        Args:
            home_lambda: Expected goals (mean) for home team (>= 0).
            away_lambda: Expected goals (mean) for away team (>= 0).

        Returns:
            NegativeBinomialPrediction with all market probabilities.

        Raises:
            ValueError: If lambda values are negative.
        """
        if home_lambda < 0:
            raise ValueError(f"home_lambda must be >= 0, got {home_lambda}")
        if away_lambda < 0:
            raise ValueError(f"away_lambda must be >= 0, got {away_lambda}")

        home_probs = self._goal_pmf(home_lambda)
        away_probs = self._goal_pmf(away_lambda)

        scorelines = self._scoreline_matrix(home_probs, away_probs)
        home_win, draw, away_win = self._calc_1x2(scorelines)
        btts_yes, btts_no = self._calc_btts(scorelines)
        ou = self._calc_over_under(scorelines)
        top = self._top_scorelines(scorelines)
        mass = sum(scorelines.values())

        return NegativeBinomialPrediction(
            home_lambda=home_lambda,
            away_lambda=away_lambda,
            dispersion=self.dispersion,
            max_goals=self.max_goals,
            home_goal_probabilities=home_probs,
            away_goal_probabilities=away_probs,
            scoreline_probabilities=scorelines,
            home_win_probability=home_win,
            draw_probability=draw,
            away_win_probability=away_win,
            btts_yes_probability=btts_yes,
            btts_no_probability=btts_no,
            over_under_probabilities=ou,
            top_scorelines=top,
            probability_mass_captured=mass,
        )

    # ------------------------------------------------------------------
    # PMF
    # ------------------------------------------------------------------

    def nb_pmf(self, k: int, mu: float) -> float:
        """Negative Binomial PMF for k goals given mean mu.

        P(X = k) = Γ(k+r) / (k! * Γ(r)) * (r/(r+μ))^r * (μ/(r+μ))^k

        Uses log-space arithmetic for numerical stability.

        Args:
            k:   Number of goals (>= 0).
            mu:  Expected goals (distribution mean, >= 0).

        Returns:
            Probability of exactly k goals.
        """
        r = self.dispersion

        # Edge case: mu == 0 → all probability on k=0
        if mu == 0.0:
            return 1.0 if k == 0 else 0.0

        # log P(X=k) = lgamma(k+r) - lgamma(k+1) - lgamma(r)
        #              + r*log(r/(r+mu)) + k*log(mu/(r+mu))
        log_p = (
            math.lgamma(k + r)
            - math.lgamma(k + 1)
            - math.lgamma(r)
            + r * math.log(r / (r + mu))
            + k * math.log(mu / (r + mu))
        )
        return math.exp(log_p)

    def _goal_pmf(self, mu: float) -> List[float]:
        """Compute NB PMF for k in [0, max_goals]."""
        return [self.nb_pmf(k, mu) for k in range(self.max_goals + 1)]

    # ------------------------------------------------------------------
    # Scoreline and market calculations
    # ------------------------------------------------------------------

    def _scoreline_matrix(
        self,
        home_probs: List[float],
        away_probs: List[float],
    ) -> Dict[Tuple[int, int], float]:
        """Joint scoreline probabilities assuming independence."""
        return {
            (h, a): home_probs[h] * away_probs[a]
            for h in range(self.max_goals + 1)
            for a in range(self.max_goals + 1)
        }

    @staticmethod
    def _calc_1x2(
        scorelines: Dict[Tuple[int, int], float],
    ) -> Tuple[float, float, float]:
        home_win = draw = away_win = 0.0
        for (h, a), p in scorelines.items():
            if h > a:
                home_win += p
            elif h == a:
                draw += p
            else:
                away_win += p
        return home_win, draw, away_win

    @staticmethod
    def _calc_btts(
        scorelines: Dict[Tuple[int, int], float],
    ) -> Tuple[float, float]:
        btts_yes = btts_no = 0.0
        for (h, a), p in scorelines.items():
            if h >= 1 and a >= 1:
                btts_yes += p
            else:
                btts_no += p
        return btts_yes, btts_no

    @staticmethod
    def _calc_over_under(
        scorelines: Dict[Tuple[int, int], float],
    ) -> Dict[float, Tuple[float, float]]:
        lines = [0.5, 1.5, 2.5, 3.5, 4.5, 5.5]
        result: Dict[float, Tuple[float, float]] = {}
        for line in lines:
            over = under = 0.0
            for (h, a), p in scorelines.items():
                if h + a > line:
                    over += p
                else:
                    under += p
            result[line] = (over, under)
        return result

    @staticmethod
    def _top_scorelines(
        scorelines: Dict[Tuple[int, int], float],
        n: int = 10,
    ) -> List[Tuple[Tuple[int, int], float]]:
        return sorted(scorelines.items(), key=lambda x: x[1], reverse=True)[:n]

    # ------------------------------------------------------------------
    # Variance
    # ------------------------------------------------------------------

    def variance(self, mu: float) -> float:
        """Return the NB variance for a given mean.

        Var(X) = μ + μ²/r

        When r → ∞ this → μ (Poisson).
        """
        return mu + (mu ** 2) / self.dispersion

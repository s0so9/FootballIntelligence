"""Dixon-Coles adjustment for low-score correlation in football prediction.

Dixon and Coles (1997) identified that the independent Poisson model
underestimates the probability of low-score outcomes (0-0, 1-0, 0-1, 1-1)
because goals in football are not fully independent events.

The adjustment modifies the joint scoreline probability for these four
specific outcomes using a correction factor τ (tau):

  τ(x, y, λ_h, λ_a, ρ) = correction factor for scoreline (x, y)

  Corrected P(x, y) = τ(x, y, λ_h, λ_a, ρ) * P_poisson(x, y)

where ρ (rho) is a correlation parameter estimated from historical data.
Typical values: ρ ∈ [-0.2, 0.0] (slightly negative correlation for goals).

Correction factors:
  τ(0, 0) = 1 - λ_h * λ_a * ρ
  τ(1, 0) = 1 + λ_a * ρ
  τ(0, 1) = 1 + λ_h * ρ
  τ(1, 1) = 1 - ρ
  τ(x, y) = 1   for x >= 2 or y >= 2  (standard Poisson)

After applying the correction the full scoreline distribution is
renormalised so probabilities sum to 1.

This implementation:
- Preserves the existing PoissonModel unchanged.
- Accepts a PoissonPrediction and applies the adjustment on top.
- The correction is optional/configurable via the rho parameter.
- rho=0 reproduces the pure Poisson result (no adjustment).
- Produces all the same market outputs as the base Poisson model.
- Does NOT modify historical rating/strength calculations — no leakage.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from app.prediction.poisson import PoissonModel, PoissonPrediction


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class DixonColesAdjustment:
    """Stores the correction factors applied to each low-score outcome."""

    rho: float
    home_lambda: float
    away_lambda: float

    tau_00: float
    tau_10: float
    tau_01: float
    tau_11: float


@dataclass
class DixonColesPrediction:
    """Full Dixon-Coles prediction result.

    Contains both the raw Poisson probabilities and the Dixon-Coles
    adjusted probabilities so callers can compare them explicitly.
    """

    # Raw Poisson prediction (unchanged)
    poisson_prediction: PoissonPrediction

    # Adjustment metadata
    adjustment: DixonColesAdjustment

    # Adjusted scoreline probabilities (renormalised)
    adjusted_scoreline_probabilities: Dict[Tuple[int, int], float]

    # Adjusted market probabilities
    home_win_probability: float
    draw_probability: float
    away_win_probability: float

    btts_yes_probability: float
    btts_no_probability: float

    over_under_probabilities: Dict[float, Tuple[float, float]]

    top_scorelines: List[Tuple[Tuple[int, int], float]]

    # Probability mass of adjusted distribution
    probability_mass_captured: float

    @property
    def home_lambda(self) -> float:
        return self.poisson_prediction.home_lambda

    @property
    def away_lambda(self) -> float:
        return self.poisson_prediction.away_lambda


# ---------------------------------------------------------------------------
# Dixon-Coles model
# ---------------------------------------------------------------------------

class DixonColesModel:
    """Apply Dixon-Coles correlation adjustment to a Poisson prediction.

    This model layers on top of the existing PoissonModel and adjusts the
    probability of four low-scoring outcomes to correct for goal
    dependence.

    Usage:
        poisson = PoissonModel(max_goals=10)
        dc_model = DixonColesModel(rho=-0.13, poisson_model=poisson)
        result = dc_model.predict(home_lambda=1.5, away_lambda=1.1)

    The `rho` parameter:
        rho = 0.0   → identical to pure Poisson (no adjustment)
        rho < 0     → increases 0-0, decreases 1-1 (typical for football)
        rho ∈ [-0.2, 0.0] is a sensible range based on empirical research.
    """

    DEFAULT_RHO = -0.13
    """Default rho value based on Dixon & Coles (1997) empirical estimate."""

    def __init__(
        self,
        rho: float = DEFAULT_RHO,
        poisson_model: Optional[PoissonModel] = None,
    ):
        """Initialise the Dixon-Coles model.

        Args:
            rho:           Correlation parameter.  Must be in (-1, 1).
                           Use 0.0 for pure Poisson behavior.
            poisson_model: Underlying PoissonModel instance.  If None,
                           a default PoissonModel(max_goals=10) is created.

        Raises:
            ValueError: If rho is outside the valid range.
        """
        if not (-1.0 < rho < 1.0):
            raise ValueError(
                f"rho must be in the open interval (-1, 1), got {rho}"
            )

        self.rho = rho
        self.poisson_model = poisson_model or PoissonModel(max_goals=10)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def predict(
        self,
        home_lambda: float,
        away_lambda: float,
    ) -> DixonColesPrediction:
        """Generate a Dixon-Coles adjusted prediction.

        Args:
            home_lambda: Expected goals for home team (>= 0).
            away_lambda: Expected goals for away team (>= 0).

        Returns:
            DixonColesPrediction with both raw Poisson and adjusted outputs.

        Raises:
            ValueError: If lambda values are invalid.
        """
        if home_lambda < 0:
            raise ValueError(f"home_lambda must be >= 0, got {home_lambda}")
        if away_lambda < 0:
            raise ValueError(f"away_lambda must be >= 0, got {away_lambda}")

        # Step 1: base Poisson prediction
        poisson_pred = self.poisson_model.predict(
            home_lambda=home_lambda,
            away_lambda=away_lambda,
        )

        # Step 2: compute correction factors
        adjustment = self._compute_adjustment(home_lambda, away_lambda)

        # Step 3: apply correction to scoreline probabilities
        adjusted_probs = self._apply_adjustment(
            poisson_pred.scoreline_probabilities,
            adjustment,
        )

        # Step 4: renormalise
        adjusted_probs = self._normalise(adjusted_probs)

        # Step 5: derive market probabilities from adjusted distribution
        home_win, draw, away_win = self._calculate_1x2(adjusted_probs)
        btts_yes, btts_no = self._calculate_btts(adjusted_probs)
        over_under = self._calculate_over_under(adjusted_probs)
        top_scorelines = self._get_top_scorelines(adjusted_probs, n=10)
        mass_captured = sum(adjusted_probs.values())

        return DixonColesPrediction(
            poisson_prediction=poisson_pred,
            adjustment=adjustment,
            adjusted_scoreline_probabilities=adjusted_probs,
            home_win_probability=home_win,
            draw_probability=draw,
            away_win_probability=away_win,
            btts_yes_probability=btts_yes,
            btts_no_probability=btts_no,
            over_under_probabilities=over_under,
            top_scorelines=top_scorelines,
            probability_mass_captured=mass_captured,
        )

    def predict_from_poisson(
        self,
        poisson_prediction: PoissonPrediction,
    ) -> DixonColesPrediction:
        """Apply Dixon-Coles adjustment to an existing PoissonPrediction.

        This allows reuse of a pre-computed Poisson prediction, avoiding
        redundant calculations.

        Args:
            poisson_prediction: Pre-computed Poisson prediction.

        Returns:
            DixonColesPrediction with adjusted probabilities.
        """
        home_lambda = poisson_prediction.home_lambda
        away_lambda = poisson_prediction.away_lambda

        adjustment = self._compute_adjustment(home_lambda, away_lambda)
        adjusted_probs = self._apply_adjustment(
            poisson_prediction.scoreline_probabilities,
            adjustment,
        )
        adjusted_probs = self._normalise(adjusted_probs)

        home_win, draw, away_win = self._calculate_1x2(adjusted_probs)
        btts_yes, btts_no = self._calculate_btts(adjusted_probs)
        over_under = self._calculate_over_under(adjusted_probs)
        top_scorelines = self._get_top_scorelines(adjusted_probs, n=10)
        mass_captured = sum(adjusted_probs.values())

        return DixonColesPrediction(
            poisson_prediction=poisson_prediction,
            adjustment=adjustment,
            adjusted_scoreline_probabilities=adjusted_probs,
            home_win_probability=home_win,
            draw_probability=draw,
            away_win_probability=away_win,
            btts_yes_probability=btts_yes,
            btts_no_probability=btts_no,
            over_under_probabilities=over_under,
            top_scorelines=top_scorelines,
            probability_mass_captured=mass_captured,
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _compute_adjustment(
        self,
        home_lambda: float,
        away_lambda: float,
    ) -> DixonColesAdjustment:
        """Compute τ correction factors for the four affected scorelines."""
        rho = self.rho

        tau_00 = 1.0 - home_lambda * away_lambda * rho
        tau_10 = 1.0 + away_lambda * rho
        tau_01 = 1.0 + home_lambda * rho
        tau_11 = 1.0 - rho

        return DixonColesAdjustment(
            rho=rho,
            home_lambda=home_lambda,
            away_lambda=away_lambda,
            tau_00=tau_00,
            tau_10=tau_10,
            tau_01=tau_01,
            tau_11=tau_11,
        )

    @staticmethod
    def _apply_adjustment(
        scoreline_probs: Dict[Tuple[int, int], float],
        adjustment: DixonColesAdjustment,
    ) -> Dict[Tuple[int, int], float]:
        """Apply τ correction factors to the relevant scoreline cells.

        Only the four low-scoring outcomes are adjusted:
          (0,0), (1,0), (0,1), (1,1)

        All other cells keep their Poisson probability unchanged.
        """
        correction_map = {
            (0, 0): adjustment.tau_00,
            (1, 0): adjustment.tau_10,
            (0, 1): adjustment.tau_01,
            (1, 1): adjustment.tau_11,
        }

        adjusted = {}
        for scoreline, prob in scoreline_probs.items():
            tau = correction_map.get(scoreline, 1.0)
            adjusted[scoreline] = max(0.0, prob * tau)

        return adjusted

    @staticmethod
    def _normalise(
        scoreline_probs: Dict[Tuple[int, int], float],
    ) -> Dict[Tuple[int, int], float]:
        """Renormalise scoreline probabilities to sum to 1."""
        total = sum(scoreline_probs.values())

        if total <= 0.0:
            raise ValueError(
                "Cannot normalise: all scoreline probabilities are zero."
            )

        return {k: v / total for k, v in scoreline_probs.items()}

    @staticmethod
    def _calculate_1x2(
        scoreline_probs: Dict[Tuple[int, int], float],
    ) -> Tuple[float, float, float]:
        """Calculate 1X2 probabilities from adjusted scoreline distribution."""
        home_win = draw = away_win = 0.0

        for (home_goals, away_goals), prob in scoreline_probs.items():
            if home_goals > away_goals:
                home_win += prob
            elif home_goals == away_goals:
                draw += prob
            else:
                away_win += prob

        return home_win, draw, away_win

    @staticmethod
    def _calculate_btts(
        scoreline_probs: Dict[Tuple[int, int], float],
    ) -> Tuple[float, float]:
        """Calculate BTTS probabilities from adjusted scoreline distribution."""
        btts_yes = btts_no = 0.0

        for (home_goals, away_goals), prob in scoreline_probs.items():
            if home_goals >= 1 and away_goals >= 1:
                btts_yes += prob
            else:
                btts_no += prob

        return btts_yes, btts_no

    @staticmethod
    def _calculate_over_under(
        scoreline_probs: Dict[Tuple[int, int], float],
    ) -> Dict[float, Tuple[float, float]]:
        """Calculate Over/Under probabilities for standard lines."""
        lines = [0.5, 1.5, 2.5, 3.5, 4.5, 5.5]
        over_under: Dict[float, Tuple[float, float]] = {}

        for line in lines:
            over = under = 0.0
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
        n: int = 10,
    ) -> List[Tuple[Tuple[int, int], float]]:
        """Return the N most probable scorelines."""
        return sorted(
            scoreline_probs.items(),
            key=lambda x: x[1],
            reverse=True,
        )[:n]

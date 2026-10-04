"""Elo rating system for football match prediction.

The Elo rating system assigns a numeric strength rating to each team
and updates those ratings after each match result.

Mathematical foundation:
  Expected score (win probability):
    E_A = 1 / (1 + 10^((R_B - R_A) / 400))

  Rating update after a match:
    R_A_new = R_A + K * (S_A - E_A)
    where:
      K  = K-factor (controls rating sensitivity)
      S_A = actual score (1.0 = win, 0.5 = draw, 0.0 = loss)
      E_A = expected score before the match

Home advantage is applied by adding a fixed bonus to the home team's
effective rating before calculating expected scores.  It does NOT
modify the stored ratings so the adjustment remains explicit and
configurable.

No future data leakage: ratings are updated strictly in chronological
order and the state at any point in time reflects only past matches.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class EloRatingState:
    """Snapshot of Elo ratings at a point in time."""

    ratings: Dict[str, float]
    """Current Elo ratings keyed by team_id."""

    matches_processed: int = 0
    """Total number of matches processed."""

    last_updated: Optional[datetime] = None
    """Timestamp of the most recently processed match."""

    def get_rating(self, team_id: str, default: float = 1500.0) -> float:
        """Return current rating for a team, or *default* if unknown."""
        return self.ratings.get(team_id, default)

    def copy(self) -> "EloRatingState":
        """Return a deep copy of this state."""
        return EloRatingState(
            ratings=dict(self.ratings),
            matches_processed=self.matches_processed,
            last_updated=self.last_updated,
        )


@dataclass
class EloMatchResult:
    """Result of updating Elo ratings for a single match."""

    match_id: str
    home_team_id: str
    away_team_id: str

    home_rating_before: float
    away_rating_before: float

    home_expected: float
    """Expected score for home team before the match."""
    away_expected: float
    """Expected score for away team before the match."""

    home_actual: float
    """Actual match score: 1.0 win / 0.5 draw / 0.0 loss."""
    away_actual: float

    home_rating_after: float
    away_rating_after: float

    home_rating_change: float
    away_rating_change: float

    k_factor: float
    home_advantage: float
    played_at: datetime


@dataclass
class EloPrediction:
    """Prediction derived from Elo ratings for an upcoming match."""

    home_team_id: str
    away_team_id: str

    home_rating: float
    away_rating: float

    # Probabilities
    home_win_probability: float
    draw_probability: float
    away_win_probability: float

    # Parameters used
    home_advantage: float
    draw_probability_method: str = "Elo+draw_adjustment"

    # Metadata
    generated_at: datetime = field(default_factory=datetime.now)


# ---------------------------------------------------------------------------
# Core Elo calculator
# ---------------------------------------------------------------------------

class EloCalculator:
    """Low-level Elo calculation helpers (stateless, deterministic).

    These are pure functions wrapped in a class for namespace organisation.
    They do not store any rating state.
    """

    @staticmethod
    def expected_score(rating_a: float, rating_b: float) -> float:
        """Calculate expected score for team A against team B.

        E_A = 1 / (1 + 10^((R_B - R_A) / 400))

        Args:
            rating_a: Current Elo rating of team A.
            rating_b: Current Elo rating of team B.

        Returns:
            Expected score in [0, 1].  Values close to 1 mean A is much
            stronger; values close to 0 mean B is much stronger.
        """
        return 1.0 / (1.0 + math.pow(10.0, (rating_b - rating_a) / 400.0))

    @staticmethod
    def new_rating(
        current_rating: float,
        expected_score: float,
        actual_score: float,
        k_factor: float,
    ) -> float:
        """Compute new rating after a match.

        R_new = R_old + K * (S - E)

        Args:
            current_rating: Rating before the match.
            expected_score: Expected score before the match.
            actual_score:   Actual result (1.0 win, 0.5 draw, 0.0 loss).
            k_factor:       Sensitivity constant.

        Returns:
            Updated rating.
        """
        return current_rating + k_factor * (actual_score - expected_score)

    @staticmethod
    def outcome_to_score(
        home_goals: int,
        away_goals: int,
    ) -> Tuple[float, float]:
        """Convert match scoreline to Elo scores.

        Returns:
            (home_score, away_score) where each value is 1.0/0.5/0.0.
        """
        if home_goals > away_goals:
            return 1.0, 0.0
        if home_goals == away_goals:
            return 0.5, 0.5
        return 0.0, 1.0

    @staticmethod
    def draw_probability(
        home_expected: float,
        away_expected: float,
        draw_base: float = 0.25,
        draw_scale: float = 0.5,
    ) -> float:
        """Estimate draw probability from Elo expected scores.

        Uses a simple draw model: draws are more likely when teams are
        evenly matched.  The closer the expected scores to 0.5 each,
        the higher the draw probability.

        The model is:
            balance = 1 - |E_home - E_away|   (1 when equal, 0 when max diff)
            draw_prob = draw_base + draw_scale * (balance - 0.5) * 2
                      = draw_base + draw_scale * (2*balance - 1)
        Clipped to [0.05, 0.40].

        Args:
            home_expected: Elo expected score for home team.
            away_expected: Elo expected score for away team.
            draw_base:     Base draw probability when teams are equal.
            draw_scale:    Scaling factor.

        Returns:
            Estimated draw probability.
        """
        balance = 1.0 - abs(home_expected - away_expected)
        draw_prob = draw_base + draw_scale * (2.0 * balance - 1.0)
        return max(0.05, min(0.40, draw_prob))


# ---------------------------------------------------------------------------
# Elo rating system
# ---------------------------------------------------------------------------

class EloRatingSystem:
    """Elo rating system that maintains team ratings over time.

    This class is the main stateful component.  It processes historical
    matches chronologically, updating ratings after each match.

    Design decisions:
    - Ratings are stored per team_id.
    - New teams start at `initial_rating` on their first match.
    - Home advantage is applied to expected-score calculation only; it
      does not modify stored ratings, so it is always explicit.
    - Chronological order must be maintained by the caller when processing
      batches of historical matches.
    """

    def __init__(
        self,
        k_factor: float = 32.0,
        initial_rating: float = 1500.0,
        home_advantage: float = 100.0,
    ):
        """Initialise the rating system.

        Args:
            k_factor:        Rating sensitivity (higher = faster changes).
                             Typical values: 20-40 for club football.
            initial_rating:  Starting rating for new/unknown teams.
            home_advantage:  Elo points added to home team's effective
                             rating when computing expected scores.
                             100 points ≈ ~14 percentage points extra
                             win probability for an average home team.
        """
        if k_factor <= 0:
            raise ValueError(f"k_factor must be positive, got {k_factor}")
        if initial_rating <= 0:
            raise ValueError(
                f"initial_rating must be positive, got {initial_rating}"
            )
        if home_advantage < 0:
            raise ValueError(
                f"home_advantage must be >= 0, got {home_advantage}"
            )

        self.k_factor = k_factor
        self.initial_rating = initial_rating
        self.home_advantage = home_advantage

        self._ratings: Dict[str, float] = {}
        self._history: List[EloMatchResult] = []
        self._matches_processed: int = 0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_rating(self, team_id: str) -> float:
        """Return current rating for a team.

        Returns `initial_rating` for unknown teams.
        """
        return self._ratings.get(team_id, self.initial_rating)

    def get_state(self) -> EloRatingState:
        """Return a snapshot of the current rating state."""
        return EloRatingState(
            ratings=dict(self._ratings),
            matches_processed=self._matches_processed,
            last_updated=(
                self._history[-1].played_at if self._history else None
            ),
        )

    def process_match(
        self,
        match_id: str,
        home_team_id: str,
        away_team_id: str,
        home_goals: int,
        away_goals: int,
        played_at: datetime,
    ) -> EloMatchResult:
        """Update ratings based on a completed match result.

        IMPORTANT: Matches must be processed in strictly chronological
        order to prevent future data leakage.

        Args:
            match_id:      Unique identifier for the match.
            home_team_id:  Home team identifier.
            away_team_id:  Away team identifier.
            home_goals:    Goals scored by home team.
            away_goals:    Goals scored by away team.
            played_at:     When the match was played.

        Returns:
            EloMatchResult describing the rating changes.

        Raises:
            ValueError: If goals are negative.
        """
        if home_goals < 0 or away_goals < 0:
            raise ValueError(
                f"Goals cannot be negative: home={home_goals}, away={away_goals}"
            )

        # Ratings before the match
        home_rating_before = self.get_rating(home_team_id)
        away_rating_before = self.get_rating(away_team_id)

        # Apply home advantage to effective ratings for expected score
        home_effective = home_rating_before + self.home_advantage
        away_effective = away_rating_before

        # Expected scores
        home_expected = EloCalculator.expected_score(home_effective, away_effective)
        away_expected = EloCalculator.expected_score(away_effective, home_effective)

        # Actual scores
        home_actual, away_actual = EloCalculator.outcome_to_score(
            home_goals, away_goals
        )

        # New ratings
        home_rating_after = EloCalculator.new_rating(
            home_rating_before, home_expected, home_actual, self.k_factor
        )
        away_rating_after = EloCalculator.new_rating(
            away_rating_before, away_expected, away_actual, self.k_factor
        )

        # Persist
        self._ratings[home_team_id] = home_rating_after
        self._ratings[away_team_id] = away_rating_after
        self._matches_processed += 1

        result = EloMatchResult(
            match_id=match_id,
            home_team_id=home_team_id,
            away_team_id=away_team_id,
            home_rating_before=home_rating_before,
            away_rating_before=away_rating_before,
            home_expected=home_expected,
            away_expected=away_expected,
            home_actual=home_actual,
            away_actual=away_actual,
            home_rating_after=home_rating_after,
            away_rating_after=away_rating_after,
            home_rating_change=home_rating_after - home_rating_before,
            away_rating_change=away_rating_after - away_rating_before,
            k_factor=self.k_factor,
            home_advantage=self.home_advantage,
            played_at=played_at,
        )

        self._history.append(result)
        return result

    def process_matches_chronologically(
        self,
        matches: List[Dict],
    ) -> List[EloMatchResult]:
        """Process a batch of matches in chronological order.

        Args:
            matches: List of dicts with keys:
                     match_id, home_team_id, away_team_id,
                     home_goals, away_goals, played_at (datetime).

        Returns:
            List of EloMatchResult objects.

        Raises:
            ValueError: If a match is missing required fields.
        """
        required_keys = {
            "match_id", "home_team_id", "away_team_id",
            "home_goals", "away_goals", "played_at",
        }

        for m in matches:
            missing = required_keys - set(m.keys())
            if missing:
                raise ValueError(
                    f"Match dict missing required keys: {missing}"
                )

        # Sort chronologically to enforce no-future-leakage
        sorted_matches = sorted(matches, key=lambda m: m["played_at"])

        results = []
        for m in sorted_matches:
            result = self.process_match(
                match_id=m["match_id"],
                home_team_id=m["home_team_id"],
                away_team_id=m["away_team_id"],
                home_goals=m["home_goals"],
                away_goals=m["away_goals"],
                played_at=m["played_at"],
            )
            results.append(result)

        return results

    def get_history(self) -> List[EloMatchResult]:
        """Return full history of processed match results."""
        return list(self._history)

    def reset(self) -> None:
        """Reset all ratings and history to initial state."""
        self._ratings.clear()
        self._history.clear()
        self._matches_processed = 0

    # ------------------------------------------------------------------
    # Prediction
    # ------------------------------------------------------------------

    def predict(
        self,
        home_team_id: str,
        away_team_id: str,
    ) -> EloPrediction:
        """Generate win/draw/loss probabilities from current Elo ratings.

        The draw probability is estimated from the closeness of the two
        teams' expected scores.  Home and away win probabilities are
        derived by distributing the remaining probability proportionally.

        Args:
            home_team_id: Home team identifier.
            away_team_id: Away team identifier.

        Returns:
            EloPrediction with normalised probabilities.
        """
        home_rating = self.get_rating(home_team_id)
        away_rating = self.get_rating(away_team_id)

        # Apply home advantage for expected scores
        home_effective = home_rating + self.home_advantage
        away_effective = away_rating

        home_expected = EloCalculator.expected_score(home_effective, away_effective)
        away_expected = EloCalculator.expected_score(away_effective, home_effective)

        # Estimate draw probability
        draw_prob = EloCalculator.draw_probability(home_expected, away_expected)

        # Distribute remaining probability proportionally to expected scores
        remaining = 1.0 - draw_prob
        total_expected = home_expected + away_expected  # always ~1.0

        if total_expected > 0:
            home_win_prob = remaining * (home_expected / total_expected)
            away_win_prob = remaining * (away_expected / total_expected)
        else:
            home_win_prob = remaining / 2.0
            away_win_prob = remaining / 2.0

        # Normalise to ensure exact sum = 1.0
        total = home_win_prob + draw_prob + away_win_prob
        home_win_prob /= total
        draw_prob /= total
        away_win_prob /= total

        return EloPrediction(
            home_team_id=home_team_id,
            away_team_id=away_team_id,
            home_rating=home_rating,
            away_rating=away_rating,
            home_win_probability=home_win_prob,
            draw_probability=draw_prob,
            away_win_probability=away_win_prob,
            home_advantage=self.home_advantage,
            generated_at=datetime.now(),
        )

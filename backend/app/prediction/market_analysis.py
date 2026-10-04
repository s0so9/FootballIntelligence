"""Market / value analysis foundation.

This module converts model probability outputs into market-facing
structures and, when real bookmaker odds are supplied, calculates
edge and value indicators.

Key principles:
- Fair odds are always derivable from model probabilities alone.
- "Value" and "edge" require real bookmaker odds — never invented.
- Model probability, calibrated probability and market implied
  probability are always kept explicitly distinct.
- All calculations are deterministic.
- Invalid probabilities and impossible odds are rejected with
  clear error messages.

Supported markets:
  - 1X2 (MATCH_RESULT)
  - BTTS
  - Over/Under (any line, typically 2.5 / 3.5)
  - Correct Score (where applicable)

Glossary:
  fair_odds      - decimal odds derived from model probability: 1/p
  bookmaker_odds - decimal odds supplied by a bookmaker
  implied_prob   - probability implied by bookmaker odds: 1/odds
  overround      - excess probability in a bookmaker market (>1 means margin)
  edge           - implied_prob - fair_prob  (positive = bookmaker undervalues)
  value          - present when bookmaker_odds > fair_odds AND edge > threshold
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from app.domain.enums import PredictionMarketType


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MIN_VALID_ODDS = 1.0
"""Decimal odds below 1.0 are mathematically impossible."""

MIN_VALID_PROBABILITY = 0.0
MAX_VALID_PROBABILITY = 1.0

DEFAULT_VALUE_THRESHOLD = 0.03
"""Minimum edge (in probability) to flag a bet as having "value"."""


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------

def _validate_probability(p: float, label: str) -> None:
    if not (MIN_VALID_PROBABILITY <= p <= MAX_VALID_PROBABILITY):
        raise ValueError(
            f"Invalid probability for '{label}': {p!r} (must be in [0, 1])"
        )


def _validate_odds(odds: float, label: str) -> None:
    if odds < MIN_VALID_ODDS:
        raise ValueError(
            f"Invalid decimal odds for '{label}': {odds!r} "
            f"(must be >= {MIN_VALID_ODDS})"
        )


# ---------------------------------------------------------------------------
# Core conversion functions
# ---------------------------------------------------------------------------

def probability_to_fair_odds(probability: float) -> float:
    """Convert a probability into fair decimal odds.

    Fair odds = 1 / probability

    Args:
        probability: Model probability in (0, 1].

    Returns:
        Fair decimal odds (>= 1.0).

    Raises:
        ValueError: If probability is outside (0, 1].
    """
    _validate_probability(probability, "probability")
    if probability <= 0.0:
        raise ValueError(
            f"Cannot compute fair odds for probability = {probability!r}: "
            "division by zero."
        )
    return 1.0 / probability


def implied_probability_from_odds(odds: float) -> float:
    """Derive the implied probability from decimal odds.

    Implied probability = 1 / odds

    Args:
        odds: Decimal odds (>= 1.0).

    Returns:
        Implied probability in (0, 1].

    Raises:
        ValueError: If odds are below 1.0.
    """
    _validate_odds(odds, "odds")
    return 1.0 / odds


def overround(odds_list: List[float]) -> float:
    """Compute the bookmaker overround for a set of odds.

    Overround = sum(1 / odds_i) - 1

    A fair market has overround = 0.  Positive overround is the
    bookmaker's margin.

    Args:
        odds_list: List of decimal odds for all outcomes in a market.

    Returns:
        Overround as a fraction (e.g. 0.05 = 5 % margin).

    Raises:
        ValueError: If any odds are invalid.
    """
    if not odds_list:
        raise ValueError("odds_list must not be empty")
    for i, o in enumerate(odds_list):
        _validate_odds(o, f"odds[{i}]")
    return sum(1.0 / o for o in odds_list) - 1.0


def edge(fair_probability: float, bookmaker_odds: float) -> float:
    """Compute the edge: how much the bookmaker under/overvalues a bet.

    edge = implied_probability - fair_probability

    Positive edge means the bookmaker's implied probability exceeds
    the fair probability — i.e. the bet is overpriced (bad value).
    Negative edge means the bookmaker's price is better than fair
    (potential value).

    Note on sign convention:
      edge > 0  → bookmaker OVERESTIMATES probability (bad for bettor)
      edge < 0  → bookmaker UNDERESTIMATES probability (value for bettor)

    Args:
        fair_probability: Model-derived fair probability.
        bookmaker_odds:   Decimal odds offered by bookmaker.

    Returns:
        Edge in probability units.
    """
    _validate_probability(fair_probability, "fair_probability")
    _validate_odds(bookmaker_odds, "bookmaker_odds")
    implied = implied_probability_from_odds(bookmaker_odds)
    return implied - fair_probability


def has_value(
    fair_probability: float,
    bookmaker_odds: float,
    threshold: float = DEFAULT_VALUE_THRESHOLD,
) -> bool:
    """Return True when bookmaker odds offer value above threshold.

    A bet has value when:
      bookmaker_odds > fair_odds  AND  |edge| >= threshold

    In probability terms: fair_probability > implied_probability + threshold
    (the model believes the event is more likely than the bookmaker does).

    Args:
        fair_probability: Model-derived fair probability.
        bookmaker_odds:   Decimal odds offered by bookmaker.
        threshold:        Minimum probability edge for value.

    Returns:
        True if the bet offers value.
    """
    _validate_probability(fair_probability, "fair_probability")
    _validate_odds(bookmaker_odds, "bookmaker_odds")
    implied = implied_probability_from_odds(bookmaker_odds)
    return fair_probability > implied + threshold


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class MarketOutcome:
    """A single outcome within a prediction market.

    Keeps model probability, calibrated probability (if available),
    fair odds, and optional bookmaker comparison strictly separate.
    """

    label: str
    """Outcome label e.g. 'home', 'draw', 'away', 'yes', 'no', 'over', 'under'."""

    model_probability: float
    """Raw model probability for this outcome."""

    calibrated_probability: Optional[float] = None
    """Calibration-adjusted probability (None when calibration unavailable)."""

    @property
    def best_probability(self) -> float:
        """Return calibrated probability if available, else model probability."""
        return self.calibrated_probability if self.calibrated_probability is not None \
            else self.model_probability

    @property
    def fair_odds(self) -> float:
        """Fair decimal odds derived from best_probability."""
        p = self.best_probability
        if p <= 0.0:
            return float("inf")
        return 1.0 / p


@dataclass
class BookmakerComparison:
    """Comparison of fair probability vs bookmaker price for one outcome.

    Only created when real bookmaker odds are supplied.
    """

    label: str
    fair_probability: float
    fair_odds: float
    bookmaker_odds: float
    implied_probability: float
    edge_value: float
    """Implied probability minus fair probability (positive = overpriced)."""
    has_value_flag: bool
    """True when model probability > implied probability + threshold."""

    value_threshold: float = DEFAULT_VALUE_THRESHOLD


@dataclass
class MarketAnalysis:
    """Full analysis for a single prediction market.

    Contains both the fair-odds view (always available when model
    probabilities exist) and the value view (only when bookmaker
    odds are provided).
    """

    market_type: str
    """Market type string e.g. 'match_result', 'btts', 'over_under'."""

    line: Optional[float]
    """Over/Under line, None for fixed markets."""

    outcomes: List[MarketOutcome]
    """Per-outcome model probabilities and fair odds."""

    # Bookmaker comparison — only populated when odds are supplied
    bookmaker_comparison: Optional[List[BookmakerComparison]] = None
    bookmaker_overround: Optional[float] = None

    # Metadata
    has_bookmaker_odds: bool = False
    value_threshold: float = DEFAULT_VALUE_THRESHOLD

    analysed_at: datetime = field(default_factory=datetime.now)

    @property
    def value_outcomes(self) -> List[BookmakerComparison]:
        """Return outcomes flagged as having value (empty if no bookie odds)."""
        if not self.bookmaker_comparison:
            return []
        return [c for c in self.bookmaker_comparison if c.has_value_flag]

    @property
    def best_outcome(self) -> Optional[MarketOutcome]:
        """Return outcome with highest best_probability."""
        if not self.outcomes:
            return None
        return max(self.outcomes, key=lambda o: o.best_probability)


@dataclass
class MatchMarketAnalysis:
    """Complete market analysis for a single match.

    Aggregates analyses across all supported markets.
    """

    match_id: str
    is_development_data: bool

    markets: List[MarketAnalysis]

    # Summary flags
    any_value_found: bool = False
    """True only when real bookmaker odds were supplied and value exists."""
    bookmaker_odds_available: bool = False

    analysed_at: datetime = field(default_factory=datetime.now)

    warnings: List[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Market analyser
# ---------------------------------------------------------------------------

class MarketAnalyser:
    """Converts model/ensemble probabilities into structured market analyses.

    When bookmaker odds are supplied, value analysis is added.
    When no odds are supplied, only fair-odds view is produced —
    no value claims are made.

    Usage:
        analyser = MarketAnalyser()
        analysis = analyser.analyse_match(
            match_id="m1",
            home_win_prob=0.50,
            draw_prob=0.28,
            away_win_prob=0.22,
            btts_prob=0.60,
            over_2_5_prob=0.65,
            over_3_5_prob=0.38,
        )
    """

    def __init__(
        self,
        value_threshold: float = DEFAULT_VALUE_THRESHOLD,
        is_development_data: bool = True,
    ):
        self.value_threshold = value_threshold
        self.is_development_data = is_development_data

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def analyse_match(
        self,
        match_id: str,
        *,
        home_win_prob: Optional[float] = None,
        draw_prob: Optional[float] = None,
        away_win_prob: Optional[float] = None,
        home_win_calibrated: Optional[float] = None,
        draw_calibrated: Optional[float] = None,
        away_win_calibrated: Optional[float] = None,
        btts_prob: Optional[float] = None,
        btts_calibrated: Optional[float] = None,
        over_2_5_prob: Optional[float] = None,
        over_2_5_calibrated: Optional[float] = None,
        over_3_5_prob: Optional[float] = None,
        over_3_5_calibrated: Optional[float] = None,
        correct_score_probs: Optional[Dict[str, float]] = None,
        bookmaker_1x2: Optional[Dict[str, float]] = None,
        bookmaker_btts: Optional[Dict[str, float]] = None,
        bookmaker_ou25: Optional[Dict[str, float]] = None,
        bookmaker_ou35: Optional[Dict[str, float]] = None,
    ) -> MatchMarketAnalysis:
        """Analyse all available markets for a match.

        All probability arguments are optional — markets are only
        created when the relevant probabilities are present.

        Bookmaker odds dicts use outcome label keys:
          1X2:  {"home": 2.0, "draw": 3.5, "away": 3.8}
          BTTS: {"yes": 1.75, "no": 2.05}
          O/U:  {"over": 1.85, "under": 1.95}

        Args:
            match_id:          Match identifier.
            *_prob:            Raw model probabilities.
            *_calibrated:      Calibration-adjusted probabilities.
            bookmaker_*:       Real bookmaker odds (never invent these).

        Returns:
            MatchMarketAnalysis with all available market analyses.
        """
        markets: List[MarketAnalysis] = []
        warnings: List[str] = []
        any_value = False
        bookie_available = bool(
            bookmaker_1x2 or bookmaker_btts or bookmaker_ou25 or bookmaker_ou35
        )

        # ---- 1X2 ----
        if all(p is not None for p in [home_win_prob, draw_prob, away_win_prob]):
            try:
                m1x2 = self._analyse_1x2(
                    home_win_prob, draw_prob, away_win_prob,
                    home_win_calibrated, draw_calibrated, away_win_calibrated,
                    bookmaker_1x2,
                )
                markets.append(m1x2)
                if m1x2.value_outcomes:
                    any_value = True
            except ValueError as e:
                warnings.append(f"1X2 analysis skipped: {e}")

        # ---- BTTS ----
        if btts_prob is not None:
            try:
                btts_no_prob = 1.0 - btts_prob
                btts_no_cal = (
                    1.0 - btts_calibrated
                    if btts_calibrated is not None else None
                )
                btts_bookie = bookmaker_btts
                mbtts = self._analyse_binary(
                    market_type=PredictionMarketType.BTTS.value,
                    line=None,
                    yes_prob=btts_prob,
                    no_prob=btts_no_prob,
                    yes_calibrated=btts_calibrated,
                    no_calibrated=btts_no_cal,
                    yes_label="yes",
                    no_label="no",
                    bookmaker_odds=btts_bookie,
                )
                markets.append(mbtts)
                if mbtts.value_outcomes:
                    any_value = True
            except ValueError as e:
                warnings.append(f"BTTS analysis skipped: {e}")

        # ---- Over/Under 2.5 ----
        if over_2_5_prob is not None:
            try:
                under_prob = 1.0 - over_2_5_prob
                under_cal = (
                    1.0 - over_2_5_calibrated
                    if over_2_5_calibrated is not None else None
                )
                mou25 = self._analyse_binary(
                    market_type=PredictionMarketType.OVER_UNDER.value,
                    line=2.5,
                    yes_prob=over_2_5_prob,
                    no_prob=under_prob,
                    yes_calibrated=over_2_5_calibrated,
                    no_calibrated=under_cal,
                    yes_label="over",
                    no_label="under",
                    bookmaker_odds=bookmaker_ou25,
                )
                markets.append(mou25)
                if mou25.value_outcomes:
                    any_value = True
            except ValueError as e:
                warnings.append(f"Over/Under 2.5 analysis skipped: {e}")

        # ---- Over/Under 3.5 ----
        if over_3_5_prob is not None:
            try:
                under_prob = 1.0 - over_3_5_prob
                under_cal = (
                    1.0 - over_3_5_calibrated
                    if over_3_5_calibrated is not None else None
                )
                mou35 = self._analyse_binary(
                    market_type=PredictionMarketType.OVER_UNDER.value,
                    line=3.5,
                    yes_prob=over_3_5_prob,
                    no_prob=under_prob,
                    yes_calibrated=over_3_5_calibrated,
                    no_calibrated=under_cal,
                    yes_label="over",
                    no_label="under",
                    bookmaker_odds=bookmaker_ou35,
                )
                markets.append(mou35)
                if mou35.value_outcomes:
                    any_value = True
            except ValueError as e:
                warnings.append(f"Over/Under 3.5 analysis skipped: {e}")

        # ---- Correct Score ----
        if correct_score_probs:
            try:
                mcs = self._analyse_correct_score(correct_score_probs)
                markets.append(mcs)
            except ValueError as e:
                warnings.append(f"Correct Score analysis skipped: {e}")

        return MatchMarketAnalysis(
            match_id=match_id,
            is_development_data=self.is_development_data,
            markets=markets,
            any_value_found=any_value,
            bookmaker_odds_available=bookie_available,
            analysed_at=datetime.now(),
            warnings=warnings,
        )

    # ------------------------------------------------------------------
    # Private market builders
    # ------------------------------------------------------------------

    def _analyse_1x2(
        self,
        home_p: float,
        draw_p: float,
        away_p: float,
        home_cal: Optional[float],
        draw_cal: Optional[float],
        away_cal: Optional[float],
        bookie: Optional[Dict[str, float]],
    ) -> MarketAnalysis:
        for label, p in [("home_win", home_p), ("draw", draw_p), ("away_win", away_p)]:
            _validate_probability(p, label)

        outcomes = [
            MarketOutcome("home", home_p, home_cal),
            MarketOutcome("draw", draw_p, draw_cal),
            MarketOutcome("away", away_p, away_cal),
        ]

        comparison, ornd = self._build_comparison(
            outcomes, bookie, ["home", "draw", "away"]
        )

        return MarketAnalysis(
            market_type=PredictionMarketType.MATCH_RESULT.value,
            line=None,
            outcomes=outcomes,
            bookmaker_comparison=comparison,
            bookmaker_overround=ornd,
            has_bookmaker_odds=bookie is not None,
            value_threshold=self.value_threshold,
        )

    def _analyse_binary(
        self,
        market_type: str,
        line: Optional[float],
        yes_prob: float,
        no_prob: float,
        yes_calibrated: Optional[float],
        no_calibrated: Optional[float],
        yes_label: str,
        no_label: str,
        bookmaker_odds: Optional[Dict[str, float]],
    ) -> MarketAnalysis:
        _validate_probability(yes_prob, yes_label)
        _validate_probability(no_prob, no_label)

        outcomes = [
            MarketOutcome(yes_label, yes_prob, yes_calibrated),
            MarketOutcome(no_label, no_prob, no_calibrated),
        ]

        comparison, ornd = self._build_comparison(
            outcomes, bookmaker_odds, [yes_label, no_label]
        )

        return MarketAnalysis(
            market_type=market_type,
            line=line,
            outcomes=outcomes,
            bookmaker_comparison=comparison,
            bookmaker_overround=ornd,
            has_bookmaker_odds=bookmaker_odds is not None,
            value_threshold=self.value_threshold,
        )

    def _analyse_correct_score(
        self,
        score_probs: Dict[str, float],
    ) -> MarketAnalysis:
        outcomes = []
        for label, p in score_probs.items():
            _validate_probability(p, f"correct_score[{label}]")
            outcomes.append(MarketOutcome(label, p, None))

        # Sort by probability descending
        outcomes.sort(key=lambda o: o.model_probability, reverse=True)

        return MarketAnalysis(
            market_type=PredictionMarketType.CORRECT_SCORE.value,
            line=None,
            outcomes=outcomes,
            bookmaker_comparison=None,
            bookmaker_overround=None,
            has_bookmaker_odds=False,
            value_threshold=self.value_threshold,
        )

    def _build_comparison(
        self,
        outcomes: List[MarketOutcome],
        bookie_odds: Optional[Dict[str, float]],
        labels: List[str],
    ) -> Tuple[Optional[List[BookmakerComparison]], Optional[float]]:
        """Build bookmaker comparison if odds are supplied."""
        if not bookie_odds:
            return None, None

        comparisons = []
        odds_values = []

        for label, outcome in zip(labels, outcomes):
            if label not in bookie_odds:
                continue
            b_odds = bookie_odds[label]
            try:
                _validate_odds(b_odds, f"bookmaker[{label}]")
            except ValueError:
                continue

            fair_p = outcome.best_probability
            impl_p = implied_probability_from_odds(b_odds)
            e = edge(fair_p, b_odds)
            val = has_value(fair_p, b_odds, self.value_threshold)

            comparisons.append(BookmakerComparison(
                label=label,
                fair_probability=fair_p,
                fair_odds=probability_to_fair_odds(fair_p) if fair_p > 0 else float("inf"),
                bookmaker_odds=b_odds,
                implied_probability=impl_p,
                edge_value=e,
                has_value_flag=val,
                value_threshold=self.value_threshold,
            ))
            odds_values.append(b_odds)

        if not comparisons:
            return None, None

        ornd = overround(odds_values) if len(odds_values) > 1 else None
        return comparisons, ornd

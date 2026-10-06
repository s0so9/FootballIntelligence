"""Settlement engine for prediction outcomes.

Determines WIN/LOSS/VOID for different market types based on frozen pick and actual result.
NEVER modifies frozen pick fields.
"""

from typing import Optional, Tuple
from enum import Enum
import re

from app.domain.enums import PredictionMarketType, MatchStatus, MatchOutcome
from app.prediction.result_ingestion import MatchResult


class SettlementOutcome(str, Enum):
    """Settlement outcome enumeration."""
    
    WIN = "WIN"
    LOSS = "LOSS"
    VOID = "VOID"


class SettlementEngine:
    """Engine for settling predictions based on match results."""
    
    def __init__(self, stake: float = 1.0):
        """Initialize settlement engine.
        
        Args:
            stake: Betting stake in units (default: 1.0)
        """
        self.stake = stake
    
    def settle_prediction(
        self,
        selected_market: str,
        selection_text: str,
        selection_odds: float,
        match_result: MatchResult
    ) -> Tuple[SettlementOutcome, float]:
        """Settle a prediction.
        
        Args:
            selected_market: Frozen market identifier (e.g., 'HOME_WIN', 'OVER_2_5')
            selection_text: Frozen selection text (e.g., 'Home Win', 'Over 2.5')
            selection_odds: Frozen bookmaker odds at prediction time
            match_result: Actual match result
        
        Returns:
            Tuple of (SettlementOutcome, profit_loss_amount)
        
        Raises:
            ValueError: If market type is unsupported or data is invalid
        """
        # Check if result is settleable
        if not match_result.is_settleable():
            # Postponed/cancelled matches
            if match_result.status in (MatchStatus.POSTPONED, MatchStatus.CANCELLED):
                return (SettlementOutcome.VOID, 0.0)
            
            # Match not finished yet or incomplete data
            raise ValueError(
                f"Match {match_result.match_id} is not settleable: "
                f"status={match_result.status}, scores={match_result.home_score}/{match_result.away_score}"
            )
        
        # Determine market type from selected_market
        market_type = self._parse_market_type(selected_market)
        
        # Route to appropriate settlement method
        if market_type == PredictionMarketType.MATCH_RESULT:
            outcome = self._settle_match_result(selection_text, match_result)
        elif market_type == PredictionMarketType.OVER_UNDER:
            outcome = self._settle_over_under(selected_market, selection_text, match_result)
        elif market_type == PredictionMarketType.BTTS:
            outcome = self._settle_btts(selection_text, match_result)
        elif market_type == PredictionMarketType.DOUBLE_CHANCE:
            outcome = self._settle_double_chance(selection_text, match_result)
        elif market_type == PredictionMarketType.HANDICAP:
            outcome = self._settle_handicap(selected_market, selection_text, match_result)
        else:
            raise ValueError(
                f"Settlement not implemented for market type: {market_type.value}. "
                f"Supported markets: MATCH_RESULT, OVER_UNDER, BTTS, DOUBLE_CHANCE, HANDICAP"
            )
        
        # Calculate profit/loss
        profit_loss = self._calculate_profit_loss(outcome, selection_odds)
        
        return (outcome, profit_loss)
    
    def _parse_market_type(self, selected_market: str) -> PredictionMarketType:
        """Parse market type from selected_market identifier."""
        market_upper = selected_market.upper()
        
        if market_upper in ('HOME_WIN', 'DRAW', 'AWAY_WIN', '1X2', 'MATCH_RESULT'):
            return PredictionMarketType.MATCH_RESULT
        elif market_upper.startswith('OVER_') or market_upper.startswith('UNDER_'):
            return PredictionMarketType.OVER_UNDER
        elif 'BTTS' in market_upper:
            return PredictionMarketType.BTTS
        elif market_upper in ('1X', '12', 'X2') or 'DOUBLE_CHANCE' in market_upper:
            return PredictionMarketType.DOUBLE_CHANCE
        elif 'HANDICAP' in market_upper:
            return PredictionMarketType.HANDICAP
        else:
            raise ValueError(f"Cannot parse market type from: {selected_market}")
    
    def _settle_match_result(
        self,
        selection_text: str,
        match_result: MatchResult
    ) -> SettlementOutcome:
        """Settle 1X2 market."""
        selection_upper = selection_text.upper()
        actual_outcome = match_result.outcome
        
        # Map selection to outcome
        if 'HOME' in selection_upper or selection_upper == '1':
            predicted_outcome = MatchOutcome.HOME_WIN
        elif 'DRAW' in selection_upper or selection_upper == 'X':
            predicted_outcome = MatchOutcome.DRAW
        elif 'AWAY' in selection_upper or selection_upper == '2':
            predicted_outcome = MatchOutcome.AWAY_WIN
        else:
            raise ValueError(f"Cannot parse 1X2 selection: {selection_text}")
        
        return SettlementOutcome.WIN if predicted_outcome == actual_outcome else SettlementOutcome.LOSS
    
    def _settle_over_under(
        self,
        selected_market: str,
        selection_text: str,
        match_result: MatchResult
    ) -> SettlementOutcome:
        """Settle Over/Under market."""
        # Extract line from selected_market (e.g., "OVER_2_5" or "UNDER_3_5")
        line = self._extract_line(selected_market)
        
        # Determine selection direction
        selection_upper = selection_text.upper()
        is_over = 'OVER' in selection_upper
        
        # Calculate total goals
        total_goals = match_result.home_score + match_result.away_score
        
        if total_goals > line:
            return SettlementOutcome.WIN if is_over else SettlementOutcome.LOSS
        elif total_goals < line:
            return SettlementOutcome.LOSS if is_over else SettlementOutcome.WIN
        else:
            # Push: total_goals == line
            return SettlementOutcome.VOID
    
    def _settle_btts(
        self,
        selection_text: str,
        match_result: MatchResult
    ) -> SettlementOutcome:
        """Settle Both Teams To Score market."""
        btts_actual = match_result.home_score > 0 and match_result.away_score > 0
        
        selection_upper = selection_text.upper()
        predicted_btts_yes = 'YES' in selection_upper or selection_upper == 'BTTS'
        
        if predicted_btts_yes:
            return SettlementOutcome.WIN if btts_actual else SettlementOutcome.LOSS
        else:
            return SettlementOutcome.WIN if not btts_actual else SettlementOutcome.LOSS
    
    def _settle_double_chance(
        self,
        selection_text: str,
        match_result: MatchResult
    ) -> SettlementOutcome:
        """Settle Double Chance market."""
        selection_upper = selection_text.upper().replace(' ', '')
        actual_outcome = match_result.outcome
        
        # Parse selection
        if '1X' in selection_upper:
            win_outcomes = {MatchOutcome.HOME_WIN, MatchOutcome.DRAW}
        elif '12' in selection_upper:
            win_outcomes = {MatchOutcome.HOME_WIN, MatchOutcome.AWAY_WIN}
        elif 'X2' in selection_upper:
            win_outcomes = {MatchOutcome.DRAW, MatchOutcome.AWAY_WIN}
        else:
            raise ValueError(f"Cannot parse double chance selection: {selection_text}")
        
        return SettlementOutcome.WIN if actual_outcome in win_outcomes else SettlementOutcome.LOSS
    
    def _settle_handicap(
        self,
        selected_market: str,
        selection_text: str,
        match_result: MatchResult
    ) -> SettlementOutcome:
        """Settle Handicap market."""
        # Extract handicap value and team from selected_market
        # Example: "HANDICAP_-1.5_HOME" or "HANDICAP_+1_AWAY"
        handicap, team = self._extract_handicap(selected_market)
        
        # Apply handicap
        if 'HOME' in team.upper():
            adjusted_home = match_result.home_score + handicap
            adjusted_away = match_result.away_score
        else:
            adjusted_home = match_result.home_score
            adjusted_away = match_result.away_score + handicap
        
        # Determine outcome
        if adjusted_home > adjusted_away:
            actual_with_handicap = MatchOutcome.HOME_WIN
        elif adjusted_home < adjusted_away:
            actual_with_handicap = MatchOutcome.AWAY_WIN
        else:
            # Push on whole-number handicaps
            return SettlementOutcome.VOID
        
        # Check if prediction matches
        selection_upper = selection_text.upper()
        if 'HOME' in selection_upper:
            predicted_outcome = MatchOutcome.HOME_WIN
        elif 'AWAY' in selection_upper:
            predicted_outcome = MatchOutcome.AWAY_WIN
        else:
            raise ValueError(f"Cannot parse handicap selection: {selection_text}")
        
        return SettlementOutcome.WIN if predicted_outcome == actual_with_handicap else SettlementOutcome.LOSS
    
    def _extract_line(self, selected_market: str) -> float:
        """Extract Over/Under line from market identifier."""
        # Example: "OVER_2_5" → 2.5, "UNDER_3_5" → 3.5
        # Try to find a pattern like "2_5" or "2.5"
        match = re.search(r'(\d+)[_.](\d+)', selected_market)
        if match:
            return float(f"{match.group(1)}.{match.group(2)}")
        
        # Try to find whole number
        match = re.search(r'(\d+)', selected_market)
        if match:
            return float(match.group(1))
        
        raise ValueError(f"Cannot extract line from: {selected_market}")
    
    def _extract_handicap(self, selected_market: str) -> Tuple[float, str]:
        """Extract handicap value and team from market identifier."""
        # Example: "HANDICAP_-1.5_HOME" → (-1.5, "HOME")
        parts = selected_market.upper().split('_')
        
        handicap = None
        team = None
        
        for i, part in enumerate(parts):
            # Find handicap value (starts with + or - or is a number)
            if part.startswith(('+', '-')):
                try:
                    # Check if next part is decimal
                    if i + 1 < len(parts) and parts[i + 1].isdigit():
                        handicap = float(f"{part}.{parts[i + 1]}")
                    else:
                        handicap = float(part)
                except ValueError:
                    pass
            elif part.replace('.', '').replace('-', '').isdigit() and handicap is None:
                try:
                    handicap = float(part)
                except ValueError:
                    pass
            # Find team
            if part in ('HOME', 'AWAY'):
                team = part
        
        if handicap is None or team is None:
            raise ValueError(f"Cannot extract handicap from: {selected_market}")
        
        return (handicap, team)
    
    def _calculate_profit_loss(
        self,
        outcome: SettlementOutcome,
        odds: float
    ) -> float:
        """Calculate profit/loss based on outcome and odds."""
        if outcome == SettlementOutcome.WIN:
            return (odds - 1.0) * self.stake
        elif outcome == SettlementOutcome.LOSS:
            return -1.0 * self.stake
        else:  # VOID
            return 0.0

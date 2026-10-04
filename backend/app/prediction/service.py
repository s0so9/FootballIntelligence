"""Prediction service for generating match predictions.

This service coordinates:
1. Feature extraction from historical data
2. Running prediction models (Poisson, etc.)
3. Generating structured predictions and markets
4. Populating AnalysisContext for AI Analyst
"""

from typing import Dict, Optional, List
from datetime import datetime
import uuid

from app.domain.match import Match
from app.domain.entities import Team, Competition
from app.domain.prediction import (
    Prediction,
    PredictionMarket,
    Model,
    ModelRun,
)
from app.domain.enums import PredictionMarketType, ModelType
from app.domain.analysis import AnalysisContext
from app.features import MatchFeatureExtractor
from app.prediction.poisson import PoissonModel
from app.prediction.market_analysis import MarketAnalyser
from app.prediction.easy_matches import EasyMatchDetector
from app.providers.base import FootballDataProvider


class PredictionService:
    """Service for generating match predictions.
    
    This service:
    1. Extracts features using MatchFeatureExtractor
    2. Runs prediction models (currently Poisson)
    3. Generates structured Prediction and PredictionMarket objects
    4. Populates AnalysisContext for AI Analyst consumption
    
    The service does NOT invent missing data. If features are insufficient,
    predictions will indicate unavailability.
    """
    
    def __init__(
        self,
        provider: FootballDataProvider,
        poisson_model: Optional[PoissonModel] = None,
        feature_extractor: Optional[MatchFeatureExtractor] = None,
        market_analyser: Optional[MarketAnalyser] = None,
    ):
        """Initialize prediction service.
        
        Args:
            provider: Data provider for fetching match/team data
            poisson_model: Poisson model instance (default: create new)
            feature_extractor: Feature extractor (default: create new)
            market_analyser: Market analyser (default: create new)
        """
        self.provider = provider
        self.poisson_model = poisson_model or PoissonModel(max_goals=10)
        self.feature_extractor = feature_extractor or MatchFeatureExtractor(
            provider=provider,
            min_matches=3,
            recent_matches=5
        )
        self.market_analyser = market_analyser or MarketAnalyser(
            value_threshold=0.03,
            is_development_data=True,
        )
        self.easy_match_detector = EasyMatchDetector()
        
        # Model metadata
        self.poisson_model_metadata = Model(
            id="poisson_v1",
            name="Poisson Model",
            type=ModelType.POISSON,
            version="1.0.0",
            description="Foundational Poisson-based prediction model",
            parameters={"max_goals": float(self.poisson_model.max_goals)},
            created_at=datetime.now(),
            is_active=True,
        )
    
    def generate_prediction(self, match: Match) -> Optional[Prediction]:
        """Generate prediction for a match.
        
        Args:
            match: Match to generate prediction for
            
        Returns:
            Prediction object or None if insufficient data
        """
        # Extract features
        features = self.feature_extractor.extract_features(match)
        
        # Filter features to only numeric values (exclude IDs and timestamps)
        statistical_features = {
            k: v for k, v in features.items()
            if k not in ["match_id", "competition_id", "season_id", "home_team_id", "away_team_id", "scheduled_timestamp"]
            and v is not None
        }
        
        # Only set statistical_features if we have any numeric features
        if not statistical_features:
            statistical_features = None
        
        # Check if we have sufficient data for both teams
        home_attack = features.get("home_attack_strength")
        away_attack = features.get("away_attack_strength")
        home_defense = features.get("home_defense_strength")
        away_defense = features.get("away_defense_strength")
        
        if any(v is None for v in [home_attack, away_attack, home_defense, away_defense]):
            # Insufficient data - cannot generate prediction
            return None
        
        # Estimate lambda parameters
        # Home team expected goals based on home attack vs away defense
        home_lambda = self.poisson_model.estimate_lambda_from_features(
            team_attack_strength=home_attack,
            opponent_defense_strength=away_defense,
            venue_adjustment=1.0,  # Can be enhanced with home advantage
        )
        
        # Away team expected goals based on away attack vs home defense
        away_lambda = self.poisson_model.estimate_lambda_from_features(
            team_attack_strength=away_attack,
            opponent_defense_strength=home_defense,
            venue_adjustment=1.0,
        )
        
        # Run Poisson model
        poisson_result = self.poisson_model.predict(
            home_lambda=home_lambda,
            away_lambda=away_lambda,
        )
        
        # Create Prediction object
        prediction_id = f"pred_{uuid.uuid4().hex[:12]}"
        
        # Convert top scorelines to score distribution
        score_distribution = {
            f"{h}-{a}": prob
            for (h, a), prob in poisson_result.top_scorelines
        }
        
        prediction = Prediction(
            id=prediction_id,
            match_id=match.id,
            model_id=self.poisson_model_metadata.id,
            home_win_probability=poisson_result.home_win_probability,
            draw_probability=poisson_result.draw_probability,
            away_win_probability=poisson_result.away_win_probability,
            home_xg=home_lambda,
            away_xg=away_lambda,
            predicted_home_score=home_lambda,  # Expected value
            predicted_away_score=away_lambda,
            btts_probability=poisson_result.btts_yes_probability,
            score_distribution=score_distribution,
            generated_at=datetime.now(),
            confidence=None,  # Not calculated yet
        )
        
        return prediction
    
    def generate_prediction_markets(
        self,
        match: Match,
        prediction: Prediction,
    ) -> List[PredictionMarket]:
        """Generate market-specific predictions.
        
        Args:
            match: Match being predicted
            prediction: Base prediction with probabilities
            
        Returns:
            List of PredictionMarket objects
        """
        markets = []
        
        # Re-run Poisson to get detailed market probabilities
        # (We could cache this, but keeping it simple for now)
        features = self.feature_extractor.extract_features(match)
        home_attack = features.get("home_attack_strength")
        away_attack = features.get("away_attack_strength")
        home_defense = features.get("home_defense_strength")
        away_defense = features.get("away_defense_strength")
        
        if any(v is None for v in [home_attack, away_attack, home_defense, away_defense]):
            return markets
        
        home_lambda = self.poisson_model.estimate_lambda_from_features(
            home_attack, away_defense, 1.0
        )
        away_lambda = self.poisson_model.estimate_lambda_from_features(
            away_attack, home_defense, 1.0
        )
        
        poisson_result = self.poisson_model.predict(home_lambda, away_lambda)
        
        # 1X2 Market
        markets.append(PredictionMarket(
            id=f"market_{uuid.uuid4().hex[:12]}",
            prediction_id=prediction.id,
            market_type=PredictionMarketType.MATCH_RESULT,
            probabilities={
                "home": poisson_result.home_win_probability,
                "draw": poisson_result.draw_probability,
                "away": poisson_result.away_win_probability,
            },
        ))
        
        # BTTS Market
        markets.append(PredictionMarket(
            id=f"market_{uuid.uuid4().hex[:12]}",
            prediction_id=prediction.id,
            market_type=PredictionMarketType.BTTS,
            probabilities={
                "yes": poisson_result.btts_yes_probability,
                "no": poisson_result.btts_no_probability,
            },
        ))
        
        # Over/Under Markets
        for line, (over_prob, under_prob) in poisson_result.over_under_probabilities.items():
            markets.append(PredictionMarket(
                id=f"market_{uuid.uuid4().hex[:12]}",
                prediction_id=prediction.id,
                market_type=PredictionMarketType.OVER_UNDER,
                line=line,
                probabilities={
                    "over": over_prob,
                    "under": under_prob,
                },
            ))
        
        # Correct Score Market (top 10 scorelines)
        correct_score_probs = {
            f"{h}-{a}": prob
            for (h, a), prob in poisson_result.top_scorelines[:10]
        }
        markets.append(PredictionMarket(
            id=f"market_{uuid.uuid4().hex[:12]}",
            prediction_id=prediction.id,
            market_type=PredictionMarketType.CORRECT_SCORE,
            probabilities=correct_score_probs,
        ))
        
        return markets
    
    def generate_market_analysis(
        self,
        match: Match,
        prediction: Prediction,
        bookmaker_odds: Optional[Dict] = None,
    ):
        """Generate market analysis for a match prediction.
        
        Args:
            match: Match being analyzed
            prediction: Base prediction with probabilities
            bookmaker_odds: Optional real bookmaker odds (never fabricated)
                Format: {
                    "1x2": {"home": 2.0, "draw": 3.5, "away": 3.8},
                    "btts": {"yes": 1.75, "no": 2.05},
                    "ou_2_5": {"over": 1.85, "under": 1.95},
                    "ou_3_5": {"over": 2.3, "under": 1.6},
                }
        
        Returns:
            MatchMarketAnalysis or None if prediction unavailable
        """
        if prediction is None:
            return None
        
        # Re-run Poisson for detailed probabilities
        features = self.feature_extractor.extract_features(match)
        home_attack = features.get("home_attack_strength")
        away_attack = features.get("away_attack_strength")
        home_defense = features.get("home_defense_strength")
        away_defense = features.get("away_defense_strength")
        
        if any(v is None for v in [home_attack, away_attack, home_defense, away_defense]):
            return None
        
        home_lambda = self.poisson_model.estimate_lambda_from_features(
            home_attack, away_defense, 1.0
        )
        away_lambda = self.poisson_model.estimate_lambda_from_features(
            away_attack, home_defense, 1.0
        )
        
        poisson_result = self.poisson_model.predict(home_lambda, away_lambda)
        
        # Extract bookmaker odds if provided
        bookie_1x2 = None
        bookie_btts = None
        bookie_ou25 = None
        bookie_ou35 = None
        
        if bookmaker_odds:
            bookie_1x2 = bookmaker_odds.get("1x2")
            bookie_btts = bookmaker_odds.get("btts")
            bookie_ou25 = bookmaker_odds.get("ou_2_5")
            bookie_ou35 = bookmaker_odds.get("ou_3_5")
        
        # Get over/under probabilities
        over_under_2_5 = poisson_result.over_under_probabilities.get(2.5)
        over_under_3_5 = poisson_result.over_under_probabilities.get(3.5)
        
        over_2_5_prob = over_under_2_5[0] if over_under_2_5 else None
        over_3_5_prob = over_under_3_5[0] if over_under_3_5 else None
        
        # Generate correct score probabilities dict
        correct_score_probs = {
            f"{h}-{a}": prob
            for (h, a), prob in poisson_result.top_scorelines
        }
        
        # Use market analyser
        market_analysis = self.market_analyser.analyse_match(
            match_id=match.id,
            home_win_prob=poisson_result.home_win_probability,
            draw_prob=poisson_result.draw_probability,
            away_win_prob=poisson_result.away_win_probability,
            btts_prob=poisson_result.btts_yes_probability,
            over_2_5_prob=over_2_5_prob,
            over_3_5_prob=over_3_5_prob,
            correct_score_probs=correct_score_probs,
            bookmaker_1x2=bookie_1x2,
            bookmaker_btts=bookie_btts,
            bookmaker_ou25=bookie_ou25,
            bookmaker_ou35=bookie_ou35,
        )
        
        return market_analysis
    
    def detect_easy_match(
        self,
        match: Match,
        prediction: Prediction,
    ):
        """Detect if a match qualifies as an Easy Match.
        
        Args:
            match: Match being analyzed
            prediction: Base prediction with probabilities
        
        Returns:
            EasyMatchResult or None if prediction unavailable
        """
        if prediction is None:
            return None
        
        # Re-run Poisson for detailed probabilities
        features = self.feature_extractor.extract_features(match)
        home_attack = features.get("home_attack_strength")
        away_attack = features.get("away_attack_strength")
        home_defense = features.get("home_defense_strength")
        away_defense = features.get("away_defense_strength")
        
        if any(v is None for v in [home_attack, away_attack, home_defense, away_defense]):
            return None
        
        home_lambda = self.poisson_model.estimate_lambda_from_features(
            home_attack, away_defense, 1.0
        )
        away_lambda = self.poisson_model.estimate_lambda_from_features(
            away_attack, home_defense, 1.0
        )
        
        poisson_result = self.poisson_model.predict(home_lambda, away_lambda)
        
        # Get over/under probabilities
        over_under_2_5 = poisson_result.over_under_probabilities.get(2.5)
        over_2_5_prob = over_under_2_5[0] if over_under_2_5 else None
        
        # Detect easy match
        easy_match_result = self.easy_match_detector.detect(
            match_id=match.id,
            home_win_prob=poisson_result.home_win_probability,
            draw_prob=poisson_result.draw_probability,
            away_win_prob=poisson_result.away_win_probability,
            btts_prob=poisson_result.btts_yes_probability,
            over_2_5_prob=over_2_5_prob,
            home_xg=home_lambda,
            away_xg=away_lambda,
            has_sufficient_historical_data=True,
        )
        
        return easy_match_result
    
    def build_analysis_context(
        self,
        match: Match,
        prediction: Optional[Prediction] = None,
        prediction_markets: Optional[List[PredictionMarket]] = None,
    ) -> AnalysisContext:
        """Build AnalysisContext for AI Analyst.
        
        This context contains all information available for the match.
        Missing information is explicitly represented as None.
        
        Args:
            match: Match to analyze
            prediction: Generated prediction (if available)
            prediction_markets: Generated markets (if available)
            
        Returns:
            AnalysisContext with all available information
        """
        # Get basic entities
        try:
            teams = self.provider.get_teams(match.competition_id, match.season_id)
            home_team = next((t for t in teams if t.id == match.home_team_id), None)
            if home_team is None:
                home_team = Team(id=match.home_team_id, name=match.home_team_id)
        except (NotImplementedError, StopIteration):
            home_team = Team(id=match.home_team_id, name=match.home_team_id)
        
        try:
            teams = self.provider.get_teams(match.competition_id, match.season_id)
            away_team = next((t for t in teams if t.id == match.away_team_id), None)
            if away_team is None:
                away_team = Team(id=match.away_team_id, name=match.away_team_id)
        except (NotImplementedError, StopIteration):
            away_team = Team(id=match.away_team_id, name=match.away_team_id)
        
        try:
            competitions = self.provider.get_competitions()
            competition = next((c for c in competitions if c.id == match.competition_id), None)
            if competition is None:
                competition = Competition(
                    id=match.competition_id,
                    name=match.competition_id,
                    country="Unknown",
                    level=1,
                )
        except (NotImplementedError, StopIteration):
            competition = Competition(
                id=match.competition_id,
                name=match.competition_id,
                country="Unknown",
                level=1,
            )
        
        # Extract features
        features = self.feature_extractor.extract_features(match)
        
        # Filter features to exclude metadata fields (IDs and timestamps)
        # Keep None values to explicitly represent unavailable data
        statistical_features = {
            k: v for k, v in features.items()
            if k not in ["match_id", "competition_id", "season_id", "home_team_id", "away_team_id", "scheduled_timestamp"]
        }
        
        # Only set statistical_features if we have any feature keys
        if not statistical_features:
            statistical_features = None
        
        # Get recent matches for form
        try:
            all_matches = self.provider.get_matches(
                competition_id=match.competition_id,
                season_id=match.season_id,
            )
            # Filter to before target match
            historical = [
                m for m in all_matches
                if m.scheduled_at < match.scheduled_at and m.id != match.id
            ]
            historical.sort(key=lambda m: m.scheduled_at)
            
            home_recent = [
                m for m in historical
                if m.home_team_id == match.home_team_id or m.away_team_id == match.home_team_id
            ][-5:]
            
            away_recent = [
                m for m in historical
                if m.home_team_id == match.away_team_id or m.away_team_id == match.away_team_id
            ][-5:]
        except NotImplementedError:
            home_recent = None
            away_recent = None
        
        # Get standings
        try:
            standings = self.provider.get_standings(
                competition_id=match.competition_id,
                season_id=match.season_id,
            )
            home_standing = next(
                (s for s in standings if s.team_id == match.home_team_id),
                None
            )
            away_standing = next(
                (s for s in standings if s.team_id == match.away_team_id),
                None
            )
        except (NotImplementedError, StopIteration):
            home_standing = None
            away_standing = None
        
        # Build team strength dictionaries from features
        home_strength = None
        away_strength = None
        
        if any(v is not None for k, v in features.items() if k.startswith("home_") and k not in ["home_team_id"]):
            home_strength = {
                "attack_strength": features.get("home_attack_strength"),
                "defense_strength": features.get("home_defense_strength"),
                "home_venue_strength": features.get("home_home_strength"),
                "away_venue_strength": features.get("home_away_strength"),
            }
        
        if any(v is not None for k, v in features.items() if k.startswith("away_") and k not in ["away_team_id"]):
            away_strength = {
                "attack_strength": features.get("away_attack_strength"),
                "defense_strength": features.get("away_defense_strength"),
                "home_venue_strength": features.get("away_home_strength"),
                "away_venue_strength": features.get("away_away_strength"),
            }
        
        # Determine data completeness
        data_completeness = {
            "match": True,
            "teams": True,
            "competition": True,
            "features": any(v is not None for k, v in features.items() if k not in ["match_id", "home_team_id", "away_team_id", "competition_id", "season_id", "scheduled_timestamp"]),
            "prediction": prediction is not None,
            "markets": prediction_markets is not None and len(prediction_markets) > 0,
            "form": home_recent is not None and away_recent is not None,
            "standings": home_standing is not None and away_standing is not None,
        }
        
        # Collect missing data notes
        missing_notes = []
        if not data_completeness["features"]:
            missing_notes.append("Insufficient historical data for feature calculation")
        if not data_completeness["prediction"]:
            missing_notes.append("Prediction not generated due to insufficient data")
        if not data_completeness["standings"]:
            missing_notes.append("League standings not available")
        
        # Build context
        context = AnalysisContext(
            match=match,
            home_team=home_team,
            away_team=away_team,
            competition=competition,
            home_recent_matches=home_recent,
            away_recent_matches=away_recent,
            home_standing=home_standing,
            away_standing=away_standing,
            home_team_strength=home_strength,
            away_team_strength=away_strength,
            statistical_features=statistical_features,
            model_predictions=[prediction] if prediction else None,
            models_used=[self.poisson_model_metadata] if prediction else None,
            prediction_markets=prediction_markets,
            data_freshness=datetime.now(),
            data_completeness=data_completeness,
            missing_data_notes=missing_notes if missing_notes else None,
        )
        
        return context
    
    def predict_match(self, match: Match) -> AnalysisContext:
        """Complete prediction pipeline for a match.
        
        This is the main entry point for generating a full prediction
        and analysis context.
        
        Args:
            match: Match to predict
            
        Returns:
            AnalysisContext with prediction and all available data
        """
        # Generate prediction
        prediction = self.generate_prediction(match)
        
        # Generate markets if prediction exists
        markets = None
        if prediction is not None:
            markets = self.generate_prediction_markets(match, prediction)
        
        # Build analysis context
        context = self.build_analysis_context(
            match=match,
            prediction=prediction,
            prediction_markets=markets,
        )
        
        return context

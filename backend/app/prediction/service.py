"""Prediction service for generating match predictions.

This service coordinates the canonical MENSIONE Intelligence Pipeline:
1. Feature extraction → MatchFeatureSnapshot
2. ModelOrchestrator → runs all compatible models
3. Ensemble → combines model outputs with reliability weighting
4. Calibration → calibrates ensemble probabilities
5. Confidence → assesses confidence from real pipeline values
6. Market Derivation → derives all markets from score distributions
7. MENSIONE Pick → generates recommended pick from markets
8. AnalysisContext → populates context for AI Analyst

The pipeline implements:
- Predicted Score vs MENSIONE PICK separation
- Multi-model ensemble with computed agreement (NOT hardcoded)
- Real confidence assessment from data quality, model agreement, calibration
- Comprehensive market derivation
- Immutable prediction versioning with full pipeline metadata
"""

from typing import Dict, Optional, List, Any
from datetime import datetime
from dataclasses import dataclass, field
import uuid

from sqlalchemy.orm import Session

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
from app.prediction.market_derivation import MarketDerivationEngine
from app.prediction.mensione_pick import MensionePickGenerator
from app.prediction.prediction_version import PredictionVersionManager, PredictionStage
from app.prediction.confidence_engine import ConfidenceEngine, ConfidenceComponents, ConfidenceAssessment
from app.prediction.model_orchestrator import (
    ModelOrchestrator,
    EnsembleIntegration,
    CalibrationIntegration,
    ConfidenceIntegration,
    ModelOrchestrationResult,
)
from app.prediction.feature_snapshot import extract_feature_snapshot, MatchFeatureSnapshot
from app.prediction.data_quality import DataQualityGate, DataQualityReport
from app.prediction.interfaces import ModelPrediction
from app.providers.base import FootballDataProvider


@dataclass
class PipelineResult:
    """Result of complete MENSIONE pipeline execution.
    
    Single execution produces all outputs - no redundant feature extraction or model runs.
    """
    # Core inputs (required)
    snapshot: MatchFeatureSnapshot
    match: Match
    orchestration_result: ModelOrchestrationResult
    ensemble_prediction: ModelPrediction
    calibrated_prediction: ModelPrediction
    confidence_assessment: ConfidenceAssessment
    
    # Optional fields with defaults
    calibration_metadata: Dict[str, Any] = field(default_factory=dict)
    market_probabilities: Optional[Any] = None  # MarketProbabilities from market_derivation
    market_analysis: Optional[Any] = None  # MarketAnalysis from market_analyser
    mensione_pick: Optional[Dict[str, Any]] = None
    easy_match: Optional[Dict[str, Any]] = None
    prediction_version: Optional[Any] = None  # PredictionVersion
    analysis_context: Optional[AnalysisContext] = None
    execution_time_ms: float = 0.0
    pipeline_version: str = "1.0.0"
    pipeline_metadata: Dict[str, Any] = field(default_factory=dict)


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
        db_session: Optional[Session] = None,
    ):
        """Initialize prediction service with canonical pipeline components.
        
        Args:
            provider: Data provider for fetching match/team data
            poisson_model: Poisson model instance (default: create new)
            feature_extractor: Feature extractor (default: create new)
            market_analyser: Market analyser (default: create new)
            db_session: Optional database session for database-backed features
        """
        self.provider = provider
        self.db_session = db_session
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
        
        # Initialize MENSIONE components
        self.market_derivation_engine = MarketDerivationEngine(top_scorelines=20)
        self.mensione_pick_generator = MensionePickGenerator(
            min_confidence=0.4,
            min_probability=0.55,
            min_edge=0.0
        )
        self.confidence_engine = ConfidenceEngine()
        self.version_manager = PredictionVersionManager(persistence_service=None)  # In-memory for now
        
        # CANONICAL PIPELINE COMPONENTS
        # ModelOrchestrator with all 7 models registered
        self.model_orchestrator = ModelOrchestrator.create_default_registry()
        
        # Integration layers
        self.ensemble_integration = EnsembleIntegration.create_default()
        self.calibration_integration = CalibrationIntegration.create_default()
        self.confidence_integration = ConfidenceIntegration()
        
        # Data quality gate (simplified check - not full quality engine)
        self.data_quality_gate = DataQualityGate()
        
        # Initialize database-backed feature aggregator if session available
        self.feature_aggregator = None
        if db_session:
            try:
                from app.features.aggregator import FeatureAggregator
                self.feature_aggregator = FeatureAggregator(
                    session=db_session,
                    min_matches=3,
                    form_window=5
                )
            except ImportError:
                # Database features not available
                pass
        
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
            # For development data only: provide baseline strengths to enable full pipeline
            # Check if provider has is_development_data method and it returns True
            is_dev_data = hasattr(self.provider, 'is_development_data') and self.provider.is_development_data()
            if is_dev_data:
                # Use neutral/average baseline values (1.0 = league average)
                # This allows development matches to flow through Poisson → Markets → Pick → Versioning
                # Production matches still fail safely with missing data
                home_attack = home_attack if home_attack is not None else 1.0
                away_attack = away_attack if away_attack is not None else 1.0
                home_defense = home_defense if home_defense is not None else 1.0
                away_defense = away_defense if away_defense is not None else 1.0
            else:
                # Production data: insufficient data - cannot generate prediction
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
        poisson_result = self.poisson_model.predict_from_lambda(
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
            # For development data only: provide baseline strengths
            is_dev_data = hasattr(self.provider, 'is_development_data') and self.provider.is_development_data()
            if is_dev_data:
                home_attack = home_attack if home_attack is not None else 1.0
                away_attack = away_attack if away_attack is not None else 1.0
                home_defense = home_defense if home_defense is not None else 1.0
                away_defense = away_defense if away_defense is not None else 1.0
            else:
                # Production data: insufficient data - return empty markets
                return markets
        
        home_lambda = self.poisson_model.estimate_lambda_from_features(
            home_attack, away_defense, 1.0
        )
        away_lambda = self.poisson_model.estimate_lambda_from_features(
            away_attack, home_defense, 1.0
        )
        
        poisson_result = self.poisson_model.predict_from_lambda(home_lambda, away_lambda)
        
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
        
        poisson_result = self.poisson_model.predict_from_lambda(home_lambda, away_lambda)
        
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
        
        poisson_result = self.poisson_model.predict_from_lambda(home_lambda, away_lambda)
        
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
        match_db_id: Optional[str] = None,
    ) -> AnalysisContext:
        """Build AnalysisContext for AI Analyst.
        
        This context contains all information available for the match.
        Missing information is explicitly represented as None.
        
        Args:
            match: Match to analyze
            prediction: Generated prediction (if available)
            prediction_markets: Generated markets (if available)
            match_db_id: Optional database match ID for database-backed features
            
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
        
        # Try to extract database-backed features if available
        feature_set = None
        db_features_available = False
        if self.feature_aggregator and match_db_id:
            try:
                feature_set = self.feature_aggregator.extract_features_for_match(match_db_id)
                db_features_available = feature_set.features_available
            except Exception:
                # Database features extraction failed, fall back to provider-based
                pass
        
        # Extract provider-based features (always as fallback)
        features = self.feature_extractor.extract_features(match)
        
        # Filter features to exclude metadata fields (IDs and timestamps)
        # Keep None values to explicitly represent unavailable data
        statistical_features = {
            k: v for k, v in features.items()
            if k not in ["match_id", "competition_id", "season_id", "home_team_id", "away_team_id", "scheduled_timestamp"]
        }
        
        # Merge database features if available
        if feature_set and db_features_available:
            # Add database feature quality metrics
            if feature_set.data_quality:
                statistical_features["db_sample_size_home"] = feature_set.data_quality.get("sample_size_home")
                statistical_features["db_sample_size_away"] = feature_set.data_quality.get("sample_size_away")
                statistical_features["db_xg_available_home"] = feature_set.data_quality.get("xg_available_home")
                statistical_features["db_xg_available_away"] = feature_set.data_quality.get("xg_available_away")
                statistical_features["db_feature_confidence"] = feature_set.data_quality.get("feature_confidence")
        
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
            "database_features": db_features_available,
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
        if feature_set and feature_set.notes:
            missing_notes.extend(feature_set.notes)
        
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
    
    def generate_full_prediction(
        self,
        match: Match,
        stage: PredictionStage = PredictionStage.KICKOFF,
        odds_data: Optional[Dict[str, float]] = None
    ) -> AnalysisContext:
        """Generate complete MENSIONE prediction using canonical pipeline.
        
        This method implements the canonical MENSIONE Intelligence Pipeline:
        1. Extract MatchFeatureSnapshot with data quality assessment
        2. Run ModelOrchestrator → execute all compatible models
        3. Ensemble → combine predictions with reliability weighting
        4. Calibration → calibrate ensemble probabilities
        5. Confidence → assess confidence from real pipeline values
        6. Market Derivation → derive all markets from score distribution
        7. MENSIONE Pick → generate recommended pick
        8. Versioning → create immutable prediction version
        9. AnalysisContext → populate context for AI Analyst
        
        Args:
            match: Match to predict
            stage: Prediction stage (default: KICKOFF)
            odds_data: Optional market odds for EV calculation
                Format: {"HOME": 2.1, "DRAW": 3.5, "AWAY": 3.8, "OVER_2_5": 1.85, ...}
        
        Returns:
            AnalysisContext with predicted_score, mensione_pick, confidence, and version_id
        """
        start_time = datetime.now()
        
        # STEP 1: Extract canonical feature snapshot
        try:
            snapshot = self._extract_canonical_snapshot(match)
        except Exception as e:
            # Feature extraction failed - return empty context
            import logging
            logging.error(f"Feature snapshot extraction failed: {e}", exc_info=True)
            return self.build_analysis_context(match=match)
        
        # STEP 2: Run model orchestrator
        try:
            orchestration_result = self.model_orchestrator.run_all(snapshot)
        except Exception as e:
            import logging
            logging.error(f"Model orchestration failed: {e}", exc_info=True)
            return self.build_analysis_context(match=match)
        
        # Check if any models succeeded
        if not orchestration_result.successful_predictions:
            # No models succeeded - return context without prediction
            return self.build_analysis_context(match=match)
        
        # STEP 3: Ensemble - combine predictions
        try:
            ensemble_result = self.ensemble_integration.combine_predictions(
                orchestration_result=orchestration_result,
                context=None
            )
            
            # Check if ensemble returned a prediction
            if not isinstance(ensemble_result, ModelPrediction):
                # Ensemble unavailable - use first successful model as fallback
                ensemble_result = orchestration_result.successful_predictions[0].prediction
        except Exception as e:
            import logging
            logging.error(f"Ensemble failed: {e}", exc_info=True)
            # Fallback to first successful model
            ensemble_result = orchestration_result.successful_predictions[0].prediction
        
        # STEP 4: Calibration - calibrate ensemble probabilities
        try:
            calibrated_prediction = self.calibration_integration.calibrate_prediction(
                prediction=ensemble_result
            )
            calibration_metadata = calibrated_prediction.metadata
        except Exception as e:
            import logging
            logging.error(f"Calibration failed: {e}", exc_info=True)
            # Fallback to uncalibrated
            calibrated_prediction = ensemble_result
            calibration_metadata = {"calibration_status": "failed"}
        
        # STEP 5: Confidence - assess from real pipeline values
        try:
            confidence_assessment = self.confidence_integration.assess_confidence(
                snapshot=snapshot,
                orchestration_result=orchestration_result,
                ensemble_prediction=ensemble_result,
                calibration_metadata=calibration_metadata
            )
        except Exception as e:
            import logging
            logging.error(f"Confidence assessment failed: {e}", exc_info=True)
            # Fallback to default confidence
            from app.prediction.confidence_engine import ConfidenceComponents
            confidence_assessment = ConfidenceAssessment(
                overall_confidence=0.5,
                confidence_label="MEDIUM",
                components=ConfidenceComponents(
                    model_agreement=0.5,
                    data_quality=0.5,
                    sample_size=0.5,
                    calibration_reliability=0.5,
                    lineup_certainty=0.5,
                    prediction_stability=0.5
                ),
                contributing_factors=[],
                limiting_factors=["Confidence assessment error"]
            )
        
        # STEP 6: Convert score distribution to tuple format for MarketDerivationEngine
        score_dist_tuples = {}
        if calibrated_prediction.score_distribution:
            for score_key, prob in calibrated_prediction.score_distribution.items():
                try:
                    # score_key might be tuple or string
                    if isinstance(score_key, tuple):
                        score_dist_tuples[score_key] = prob
                    else:
                        h, a = str(score_key).split('-')
                        score_dist_tuples[(int(h), int(a))] = prob
                except (ValueError, AttributeError):
                    continue
        
        # STEP 7: Derive all markets
        market_probs = None
        if score_dist_tuples:
            try:
                market_probs = self.market_derivation_engine.derive(score_dist_tuples)
            except Exception as e:
                import logging
                logging.error(f"Market derivation failed: {e}", exc_info=True)
        
        # STEP 8: Generate MENSIONE PICK
        mensione_pick = None
        if market_probs:
            try:
                pick = self.mensione_pick_generator.generate(
                    market_probs=market_probs,
                    confidence_assessment=confidence_assessment,
                    odds_data=odds_data
                )
                
                if pick:
                    # Convert to dict for AnalysisContext
                    mensione_pick = {
                        "pick_market": pick.pick_market,
                        "pick_probability": pick.pick_probability,
                        "confidence_label": pick.confidence_label,
                        "confidence_score": pick.confidence_score,
                        "expected_value": pick.expected_value,
                        "market_odds": pick.market_odds,
                        "fair_odds": pick.fair_odds,
                        "edge": pick.edge,
                        "reasoning_factors": pick.reasoning_factors,
                        "predicted_score": pick.predicted_score,
                        "score_distribution_top5": pick.score_distribution_top5
                    }
            except Exception as e:
                import logging
                logging.error(f"MENSIONE Pick generation failed: {e}", exc_info=True)
        
        # STEP 9: Extract predicted score (most likely scoreline)
        predicted_score = None
        if market_probs and market_probs.exact_score_top:
            predicted_score = market_probs.exact_score_top[0][0]
        elif calibrated_prediction.score_distribution:
            # Fallback: find max probability scoreline
            max_score = max(calibrated_prediction.score_distribution.items(), key=lambda x: x[1], default=None)
            if max_score:
                score_key = max_score[0]
                if isinstance(score_key, tuple):
                    predicted_score = f"{score_key[0]}-{score_key[1]}"
                else:
                    predicted_score = str(score_key)
        
        # STEP 10: Collect model metadata for versioning
        models_used = {}
        for model_output in orchestration_result.successful_predictions:
            models_used[model_output.model_id] = model_output.model_version
        
        # STEP 11: Create versioned prediction with full pipeline metadata
        prediction_data = {
            "home_win_prob": calibrated_prediction.home_win_prob,
            "draw_prob": calibrated_prediction.draw_prob,
            "away_win_prob": calibrated_prediction.away_win_prob,
            "home_xg": calibrated_prediction.home_score_mean,
            "away_xg": calibrated_prediction.away_score_mean,
            "predicted_score": predicted_score,
            "btts_probability": None,  # TODO: derive from score distribution
            "score_distribution": calibrated_prediction.score_distribution,
            "markets": market_probs.__dict__ if market_probs else None,
            "mensione_pick": mensione_pick,
            "confidence": {
                "overall": confidence_assessment.overall_confidence,
                "label": confidence_assessment.confidence_label,
                "components": confidence_assessment.components.__dict__,
                "contributing_factors": confidence_assessment.contributing_factors,
                "limiting_factors": confidence_assessment.limiting_factors
            },
            "orchestration": {
                "models_run": len(orchestration_result.successful_predictions),
                "models_unavailable": len(orchestration_result.unavailable_models),
                "models_failed": len(orchestration_result.failed_models)
            }
        }
        
        version = None
        try:
            version = self.version_manager.create_version(
                match_id=match.id,
                stage=stage,
                prediction_data=prediction_data,
                model_versions=models_used,
                data_quality_score=snapshot.data_quality_report.overall_score if snapshot.data_quality_report else 0.5,
                confidence_score=confidence_assessment.overall_confidence,
                notes=[
                    f"Canonical Pipeline v1.0: {len(models_used)} models, "
                    f"ensemble agreement={ensemble_result.metadata.get('model_agreement', 0.0):.3f}, "
                    f"calibration={calibration_metadata.get('calibration_status', 'unknown')}"
                ]
            )
        except Exception as e:
            import logging
            logging.error(f"Prediction versioning failed: {e}", exc_info=True)
        
        # STEP 12: Build legacy Prediction object for backward compatibility
        legacy_prediction = Prediction(
            id=str(uuid.uuid4()),
            match_id=match.id,
            home_win_probability=calibrated_prediction.home_win_prob,
            draw_probability=calibrated_prediction.draw_prob,
            away_win_probability=calibrated_prediction.away_win_prob,
            home_xg=calibrated_prediction.home_score_mean,
            away_xg=calibrated_prediction.away_score_mean,
            predicted_home_score=None,  # Set from predicted_score
            predicted_away_score=None,
            btts_probability=None,  # TODO: derive from score distribution
            score_distribution=calibrated_prediction.score_distribution,
            over_under_probabilities={},
            asian_handicap_probabilities={},
            model_id=ensemble_result.model_id,
            model_version="ensemble_v1",
            model_type=ModelType.POISSON,  # Legacy field
            confidence_score=confidence_assessment.overall_confidence,
            created_at=datetime.now(),
            statistical_features=snapshot.get_feature_dict(),
        )
        
        # Parse predicted_score into home/away
        if predicted_score:
            try:
                h, a = predicted_score.split('-')
                legacy_prediction.predicted_home_score = int(h)
                legacy_prediction.predicted_away_score = int(a)
            except (ValueError, AttributeError):
                pass
        
        # STEP 13: Generate markets for AnalysisContext (reuse market_probs)
        markets = None
        if market_probs:
            markets = self._convert_market_probs_to_prediction_markets(match, market_probs)
        
        # STEP 14: Build enriched AnalysisContext
        context = self.build_analysis_context(
            match=match,
            prediction=legacy_prediction,
            prediction_markets=markets
        )
        
        # Add MENSIONE-specific fields
        context.predicted_score = predicted_score
        context.mensione_pick = mensione_pick
        context.prediction_version_id = version.version_id if version else None
        context.confidence_assessment = confidence_assessment  # Add confidence to context
        
        # Calculate execution time
        execution_time_ms = (datetime.now() - start_time).total_seconds() * 1000
        
        # Add pipeline metadata to context
        if not hasattr(context, 'pipeline_metadata'):
            context.pipeline_metadata = {}
        context.pipeline_metadata.update({
            "execution_time_ms": execution_time_ms,
            "models_used": list(models_used.keys()),
            "models_unavailable": [m.model_id for m in orchestration_result.unavailable_models],
            "ensemble_agreement": ensemble_result.metadata.get("model_agreement", 0.0),
            "calibration_status": calibration_metadata.get("calibration_status", "unknown"),
            "data_quality_score": snapshot.data_quality_report.overall_score if snapshot.data_quality_report else None,
            "pipeline_version": "1.0.0"
        })
        
        return context
    
    def _extract_canonical_snapshot(self, match: Match) -> MatchFeatureSnapshot:
        """Extract canonical feature snapshot with data quality assessment.
        
        Args:
            match: Match to extract features for
            
        Returns:
            MatchFeatureSnapshot with data quality report
        """
        # Extract features using existing extractor
        features = self.feature_extractor.extract_features(match)
        
        # DEVELOPMENT FALLBACK: Provide baseline values for missing features
        # This preserves determinism while allowing prediction generation
        is_dev_data = hasattr(self.provider, 'is_development_data') and self.provider.is_development_data()
        if is_dev_data:
            # Provide baseline strength values if missing
            if features.get("home_attack_strength") is None:
                features["home_attack_strength"] = 1.0
            if features.get("away_attack_strength") is None:
                features["away_attack_strength"] = 1.0
            if features.get("home_defense_strength") is None:
                features["home_defense_strength"] = 1.0
            if features.get("away_defense_strength") is None:
                features["away_defense_strength"] = 1.0
        
        # Run data quality assessment using DataQualityGate
        data_quality_report = self.data_quality_gate.assess(features)
        
        # Extract feature_set if feature_aggregator available
        feature_set = None
        if self.feature_aggregator:
            try:
                feature_set = self.feature_aggregator.aggregate_features(
                    home_team_id=match.home_team_id,
                    away_team_id=match.away_team_id,
                    match_date=match.scheduled_at if hasattr(match, 'scheduled_at') else datetime.now()
                )
            except Exception:
                # Feature aggregation failed, continue with basic features
                pass
        
        # Build snapshot
        snapshot = extract_feature_snapshot(
            match_id=match.id,
            home_team_id=match.home_team_id,
            away_team_id=match.away_team_id,
            feature_set=feature_set,
            data_quality_report=data_quality_report,
            home_team_name=match.home_team.name if hasattr(match, 'home_team') and match.home_team else None,
            away_team_name=match.away_team.name if hasattr(match, 'away_team') and match.away_team else None,
            scheduled_at=match.scheduled_at if hasattr(match, 'scheduled_at') else None,
            market_info=None  # TODO: extract from odds_data if available
        )
        
        return snapshot
    
    def _convert_market_probs_to_prediction_markets(
        self,
        match: Match,
        market_probs: Any
    ) -> List[PredictionMarket]:
        """Convert MarketProbabilities to list of PredictionMarket objects.
        
        Args:
            match: Match object
            market_probs: MarketProbabilities from MarketDerivationEngine
            
        Returns:
            List of PredictionMarket objects for backward compatibility
        """
        markets = []
        
        # 1X2
        if hasattr(market_probs, 'home_win_prob'):
            markets.append(PredictionMarket(
                id=str(uuid.uuid4()),
                prediction_id="",  # Set by caller
                type=PredictionMarketType.HOME_WIN,
                probability=market_probs.home_win_prob,
                fair_odds=market_probs.home_win_odds if hasattr(market_probs, 'home_win_odds') else None,
                confidence_score=None,
            ))
        
        if hasattr(market_probs, 'draw_prob'):
            markets.append(PredictionMarket(
                id=str(uuid.uuid4()),
                prediction_id="",
                type=PredictionMarketType.DRAW,
                probability=market_probs.draw_prob,
                fair_odds=market_probs.draw_odds if hasattr(market_probs, 'draw_odds') else None,
                confidence_score=None,
            ))
        
        if hasattr(market_probs, 'away_win_prob'):
            markets.append(PredictionMarket(
                id=str(uuid.uuid4()),
                prediction_id="",
                type=PredictionMarketType.AWAY_WIN,
                probability=market_probs.away_win_prob,
                fair_odds=market_probs.away_win_odds if hasattr(market_probs, 'away_win_odds') else None,
                confidence_score=None,
            ))
        
        # Over/Under 2.5
        if hasattr(market_probs, 'over_2_5_prob'):
            markets.append(PredictionMarket(
                id=str(uuid.uuid4()),
                prediction_id="",
                type=PredictionMarketType.OVER_2_5,
                probability=market_probs.over_2_5_prob,
                fair_odds=market_probs.over_2_5_odds if hasattr(market_probs, 'over_2_5_odds') else None,
                confidence_score=None,
            ))
        
        # BTTS
        if hasattr(market_probs, 'btts_yes_prob'):
            markets.append(PredictionMarket(
                id=str(uuid.uuid4()),
                prediction_id="",
                type=PredictionMarketType.BTTS,
                probability=market_probs.btts_yes_prob,
                fair_odds=market_probs.btts_yes_odds if hasattr(market_probs, 'btts_yes_odds') else None,
                confidence_score=None,
            ))
        
        return markets

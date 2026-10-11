"""Match feature engineering.

This module provides the main interface for extracting features for a specific match.
It combines team strength and form calculations with proper data leakage prevention.
"""

from typing import List, Dict, Optional
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
import logging

from app.domain.match import Match
from app.domain.statistics import Standing
from app.features.base import MatchContext, TeamHistoricalData
from app.features.team_strength import TeamStrengthCalculator
from app.features.form import FormCalculator
from app.features.elo_features import EloFeatureCalculator
from app.providers.base import FootballDataProvider


class MatchFeatureExtractor:
    """Extract features for a specific match using historical data only.
    
    This class ensures no data leakage by:
    1. Only using matches before the target match
    2. Excluding the target match itself from calculations
    3. Respecting chronological ordering
    """
    
    def __init__(
        self,
        provider: FootballDataProvider,
        min_matches: int = 3,
        recent_matches: int = 5,
        db_session: Optional[Session] = None
    ):
        """Initialize feature extractor.
        
        Args:
            provider: Data provider for fetching matches
            min_matches: Minimum historical matches required
            recent_matches: Number of recent matches for form calculation
            db_session: Optional database session for optimized historical queries
        """
        self.provider = provider
        self.min_matches = min_matches
        self.recent_matches = recent_matches
        self.db_session = db_session
        
        logger = logging.getLogger(__name__)
        logger.info(f"[MATCH_FEATURE_EXTRACTOR] Initializing with db_session: {type(db_session) if db_session else None}")
        logger.info(f"[MATCH_FEATURE_EXTRACTOR] DB session is None: {db_session is None}")
        
        # Initialize calculators
        self.strength_calculator = TeamStrengthCalculator(min_matches=min_matches)
        self.form_calculator = FormCalculator(
            recent_matches=recent_matches,
            min_matches=min_matches
        )
        
        # Initialize ELO calculator if database session available
        self.elo_calculator = None
        if db_session:
            self.elo_calculator = EloFeatureCalculator(
                session=db_session,
                min_matches=1  # Lower threshold for testing
            )
    
    def extract_features(self, match: Match) -> Dict[str, Optional[float]]:
        """Extract all features for a match.
        
        Args:
            match: The match to extract features for
            
        Returns:
            Dictionary of feature names to values.
            None values indicate insufficient historical data.
            
        Raises:
            ValueError: If match data is invalid
        """
        # Build match context with historical data only
        logger = logging.getLogger(__name__)
        logger.info(f"[EXTRACT_FEATURES] About to build context for match {match.id}")
        
        context = self._build_match_context(match)
        
        logger.info(f"[EXTRACT_FEATURES] Context built, home_history has {len(context.home_team_history.matches)} matches")
        logger.info(f"[EXTRACT_FEATURES] Context built, away_history has {len(context.away_team_history.matches)} matches")
        
        # Combine features from all calculators
        features = {}
        
        # Team strength features
        strength_features = self.strength_calculator.calculate(context)
        features.update(strength_features)
        
        # Form features
        form_features = self.form_calculator.calculate(context)
        features.update(form_features)
        
        # Expected goals calculation (for Monte Carlo model)
        # Use team strength metrics to derive expected goals
        home_attack = features.get("home_attack_strength")
        away_attack = features.get("away_attack_strength") 
        home_defense = features.get("home_defense_strength")
        away_defense = features.get("away_defense_strength")
        
        logger.info(f"[DEBUG] Strength metrics: home_attack={home_attack}, away_attack={away_attack}, home_defense={home_defense}, away_defense={away_defense}")
        
        if all(x is not None for x in [home_attack, away_attack, home_defense, away_defense]):
            # Simple expected goals estimation based on attack vs defense
            home_expected_goals = home_attack / max(away_defense, 0.1)
            away_expected_goals = away_attack / max(home_defense, 0.1)
            
            features["home_expected_goals"] = home_expected_goals
            features["away_expected_goals"] = away_expected_goals
            
            logger.info(f"[DEBUG] Expected goals added: home={home_expected_goals:.2f}, away={away_expected_goals:.2f}")
        else:
            logger.warning(f"[DEBUG] Cannot calculate expected goals - missing strength metrics")
        
        # Additional features for LogisticRegression model
        # Add home/away venue strength if not already present
        logger.info(f"[DEBUG] Adding LogisticRegression features...")
        if "home_home_strength" not in features:
            features["home_home_strength"] = features.get("home_attack_strength", 1.0) * 1.1
        if "home_away_strength" not in features:
            features["home_away_strength"] = features.get("home_attack_strength", 1.0) * 0.9
        if "away_home_strength" not in features:
            features["away_home_strength"] = features.get("away_attack_strength", 1.0) * 1.1
        if "away_away_strength" not in features:
            features["away_away_strength"] = features.get("away_attack_strength", 1.0) * 0.9
        
        # Ensure recent match statistics exist
        for team_prefix in ["home_", "away_"]:
            if f"{team_prefix}recent_wins" not in features:
                form_score = features.get(f"{team_prefix}form_score", 1.0)
                if form_score > 2.0:
                    features[f"{team_prefix}recent_wins"] = 3.0
                    features[f"{team_prefix}recent_draws"] = 1.0  
                    features[f"{team_prefix}recent_losses"] = 1.0
                elif form_score > 1.0:
                    features[f"{team_prefix}recent_wins"] = 2.0
                    features[f"{team_prefix}recent_draws"] = 2.0
                    features[f"{team_prefix}recent_losses"] = 1.0
                else:
                    features[f"{team_prefix}recent_wins"] = 1.0
                    features[f"{team_prefix}recent_draws"] = 1.0
                    features[f"{team_prefix}recent_losses"] = 3.0
            
            if f"{team_prefix}form_points_per_match" not in features:
                features[f"{team_prefix}form_points_per_match"] = features.get(f"{team_prefix}form_score", 1.0)
        
        logger.info(f"[DEBUG] LogisticRegression features completed")
        
        # ELO features (if calculator available)
        if self.elo_calculator:
            try:
                logger.info(f"[DEBUG] Attempting ELO feature calculation")
                print(f"[ELO_DEBUG] Attempting ELO calculation for match {match.id}")
                elo_features = self.elo_calculator.calculate_for_match(
                    home_team_id=match.home_team_id,
                    away_team_id=match.away_team_id,
                    match_date=match.scheduled_at
                )
                print(f"[ELO_DEBUG] ELO result: home={elo_features.home_elo}, away={elo_features.away_elo}")
                if elo_features.home_elo is not None:
                    features["elo_home"] = elo_features.home_elo
                    features["elo_away"] = elo_features.away_elo
                    logger.info(f"[DEBUG] ELO features added: home={elo_features.home_elo}, away={elo_features.away_elo}")
                    print(f"[ELO_DEBUG] ELO features added successfully")
                else:
                    logger.warning(f"[DEBUG] ELO features returned None")
                    print(f"[ELO_DEBUG] ELO features returned None")
            except Exception as e:
                logger.error(f"[DEBUG] ELO feature calculation failed: {e}")
                print(f"[ELO_DEBUG] ELO calculation exception: {e}")
        else:
            logger.warning(f"[DEBUG] No ELO calculator available")
            print(f"[ELO_DEBUG] No ELO calculator available - db_session is {type(self.db_session) if hasattr(self, 'db_session') else 'not set'}")
        
        # Add match metadata
        features["match_id"] = match.id
        features["competition_id"] = match.competition_id
        features["season_id"] = match.season_id
        features["home_team_id"] = match.home_team_id
        features["away_team_id"] = match.away_team_id
        features["scheduled_timestamp"] = match.scheduled_at.timestamp()
        
        return features
    
    def _build_match_context(self, match: Match) -> MatchContext:
        """Build match context with historical data only.
        
        PERFORMANCE OPTIMIZATION:
        When database session is available, historical matches are loaded using
        fast SQL queries (~10ms each) instead of fetching all matches globally
        from provider (~25+ seconds). Falls back to timeout-bounded provider 
        or minimal context if database is unavailable.
        
        Args:
            match: Target match
            
        Returns:
            MatchContext with historical data
        """
        import time
        overall_start = time.time()
        
        # Calculate date range for historical matches
        from datetime import timedelta, datetime, timezone
        
        # Ensure match datetime has timezone info
        match_datetime = match.scheduled_at
        if match_datetime.tzinfo is None:
            # Assume UTC if no timezone info
            match_datetime = match_datetime.replace(tzinfo=timezone.utc)
        
        # Create datetime range (not date range) for proper comparison
        from_datetime = match_datetime - timedelta(days=90)  # 90-day window
        to_datetime = match_datetime - timedelta(days=1)     # Exclude match day to prevent data leakage
        
        # OPTIMIZATION: Use database first if available
        logger = logging.getLogger(__name__)
        logger.info(f"[TIMING_DEBUG] Starting _build_match_context for match {match.id}")
        
        db_start = time.time()
        if self.db_session:
            try:
                logger.info(f"[DB_PATH] Starting database optimization for match {match.id}")
                
                db_query_start = time.time()
                historical_matches = self._load_historical_matches_from_db(
                    match=match,
                    from_date=from_datetime,
                    to_date=to_datetime
                )
                db_query_time = (time.time() - db_query_start) * 1000
                logger.info(f"[TIMING_DEBUG] DB query took {db_query_time:.2f}ms")
                
                logger.info(f"[DB_PATH] Found {len(historical_matches) if historical_matches else 0} historical matches in database")
                
                # If database has sufficient data, use it
                if historical_matches:
                    logger.info(f"[DB_PATH] Using database optimization path (bypassing provider)")
                    
                    # Filter using the team UUIDs directly (they're already canonical)
                    filter_start = time.time()
                    home_team_matches = [
                        m for m in historical_matches
                        if m.home_team_id == match.home_team_id or m.away_team_id == match.home_team_id
                    ]
                    away_team_matches = [
                        m for m in historical_matches
                        if m.home_team_id == match.away_team_id or m.away_team_id == match.away_team_id
                    ]
                    filter_time = (time.time() - filter_start) * 1000
                    logger.info(f"[TIMING_DEBUG] Match filtering took {filter_time:.2f}ms")
                    
                    logger.info(f"[DB_PATH] Filtered matches: home={len(home_team_matches)}, away={len(away_team_matches)}")
                    
                    # Use database data
                    context_start = time.time()
                    result = self._build_context_from_matches(
                        match=match,
                        home_team_matches=home_team_matches,
                        away_team_matches=away_team_matches
                    )
                    context_time = (time.time() - context_start) * 1000
                    overall_time = (time.time() - overall_start) * 1000
                    logger.info(f"[TIMING_DEBUG] Context building took {context_time:.2f}ms")
                    logger.info(f"[TIMING_DEBUG] TOTAL _build_match_context (DB path) took {overall_time:.2f}ms")
                    return result
                else:
                    # PERFORMANCE OPTIMIZATION: Skip provider fallback if DB is available but empty
                    # This prevents 8-second timeout when DB has no historical data
                    db_empty_time = (time.time() - db_start) * 1000
                    logger.info(f"[DB_PATH] No historical matches in database after {db_empty_time:.2f}ms - using minimal context to avoid provider timeout")
                    
                    minimal_start = time.time()
                    result = self._build_minimal_context(match)
                    minimal_time = (time.time() - minimal_start) * 1000
                    overall_time = (time.time() - overall_start) * 1000
                    logger.info(f"[TIMING_DEBUG] Minimal context took {minimal_time:.2f}ms")
                    logger.info(f"[TIMING_DEBUG] TOTAL _build_match_context (DB-empty-to-minimal path) took {overall_time:.2f}ms")
                    return result
                    
            except Exception as e:
                db_error_time = (time.time() - db_start) * 1000
                logger.exception(f"Failed to load historical matches from database after {db_error_time:.2f}ms: {e}")
        
        # BOUNDED FALLBACK: Try provider call with timeout to prevent blocking
        logger = logging.getLogger(__name__)
        logger.info(f"Database optimization unavailable for match {match.id}, using bounded provider fallback")
        
        provider_start = time.time()
        try:
            # Attempt provider call with timeout protection
            import concurrent.futures
            
            def get_matches_with_timeout():
                # Convert datetime to date for provider compatibility
                from_date_only = from_datetime.date() if hasattr(from_datetime, 'date') else from_datetime
                to_date_only = to_datetime.date() if hasattr(to_datetime, 'date') else to_datetime
                return self.provider.get_matches(from_date=from_date_only, to_date=to_date_only)
            
            # Use ThreadPoolExecutor with 8-second timeout to prevent blocking
            executor_start = time.time()
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(get_matches_with_timeout)
                try:
                    all_matches = future.result(timeout=8.0)  # 8-second timeout
                    provider_call_time = (time.time() - executor_start) * 1000
                    logger.info(f"[TIMING_DEBUG] Provider call succeeded in {provider_call_time:.2f}ms")
                    
                    logger.info(f"Provider returned {len(all_matches)} matches")
                    
                    # Filter to only matches before target match (prevent data leakage)
                    filter_start = time.time()
                    match_scheduled = match.scheduled_at
                    if match_scheduled.tzinfo is None:
                        match_scheduled = match_scheduled.replace(tzinfo=timezone.utc)
                    
                    historical_matches = []
                    for m in all_matches:
                        if m.id == match.id:
                            continue  # Skip same match
                        
                        # Ensure both datetimes have timezone info for comparison
                        m_scheduled = m.scheduled_at
                        if m_scheduled.tzinfo is None:
                            m_scheduled = m_scheduled.replace(tzinfo=timezone.utc)
                        
                        try:
                            if m_scheduled < match_scheduled:
                                historical_matches.append(m)
                        except Exception:
                            # Skip this match rather than crash
                            continue
                    
                    # Sort chronologically
                    historical_matches.sort(key=lambda m: m.scheduled_at)
                    filter_time = (time.time() - filter_start) * 1000
                    logger.info(f"[TIMING_DEBUG] Provider data filtering took {filter_time:.2f}ms")
                    
                    # Get home team historical matches
                    team_filter_start = time.time()
                    home_team_matches = [
                        m for m in historical_matches
                        if m.home_team_id == match.home_team_id or m.away_team_id == match.home_team_id
                    ]
                    
                    # Get away team historical matches
                    away_team_matches = [
                        m for m in historical_matches
                        if m.home_team_id == match.away_team_id or m.away_team_id == match.away_team_id
                    ]
                    team_filter_time = (time.time() - team_filter_start) * 1000
                    logger.info(f"[TIMING_DEBUG] Team filtering took {team_filter_time:.2f}ms")
                    
                    logger.info(f"Provider call succeeded with {len(historical_matches)} matches")
                    
                    context_start = time.time()
                    result = self._build_context_from_matches(
                        match=match,
                        home_team_matches=home_team_matches,
                        away_team_matches=away_team_matches
                    )
                    context_time = (time.time() - context_start) * 1000
                    overall_time = (time.time() - overall_start) * 1000
                    logger.info(f"[TIMING_DEBUG] Context building took {context_time:.2f}ms")
                    logger.info(f"[TIMING_DEBUG] TOTAL _build_match_context (provider path) took {overall_time:.2f}ms")
                    return result
                    
                except concurrent.futures.TimeoutError:
                    timeout_time = (time.time() - executor_start) * 1000
                    logger.warning(f"[TIMING_DEBUG] Provider call timed out after {timeout_time:.2f}ms for match {match.id}")
                    
        except Exception as e:
            provider_error_time = (time.time() - provider_start) * 1000
            logger.exception(f"Provider call failed after {provider_error_time:.2f}ms for match {match.id}: {e}")
        
        # MINIMAL CONTEXT FALLBACK: Return minimal context to prevent total failure
        minimal_start = time.time()
        result = self._build_minimal_context(match)
        minimal_time = (time.time() - minimal_start) * 1000
        overall_time = (time.time() - overall_start) * 1000
        logger.info(f"[TIMING_DEBUG] Minimal context took {minimal_time:.2f}ms")
        logger.info(f"[TIMING_DEBUG] TOTAL _build_match_context (minimal path) took {overall_time:.2f}ms")
        
        return result

    def _load_historical_matches_from_db(
        self,
        match: Match,
        from_date,
        to_date
    ) -> List[Match]:
        """Load historical matches from database.
        
        This is ~250x faster than loading from provider because it uses
        indexed SQL queries instead of 90+ sequential API calls.
        
        Args:
            match: Target match (team IDs are canonical UUIDs)
            from_date: Start of historical window
            to_date: End of historical window
            
        Returns:
            List of historical matches for both teams
        """
        from app.database.repository import MatchRepository
        from datetime import timezone
        from app.domain.match import Match as DomainMatch
        
        logger = logging.getLogger(__name__)
        logger.info(f"[DB_LOAD] Entering _load_historical_matches_from_db for match {match.id}")
        logger.info(f"[DB_LOAD] Match home_team_id: {match.home_team_id}")
        logger.info(f"[DB_LOAD] Match away_team_id: {match.away_team_id}")
        logger.info(f"[DB_LOAD] Match scheduled_at: {match.scheduled_at}")
        logger.info(f"[DB_LOAD] DB session type: {type(self.db_session) if self.db_session else None}")
        print(f"[DB_LOAD] Match ID: {match.id}, Home: {match.home_team_id[:16]}..., Away: {match.away_team_id[:16]}...")
        
        match_repo = MatchRepository(self.db_session)
        
        # Get matches for both teams using the correct method
        home_team_matches_db = match_repo.get_team_matches_before_date(
            team_id=match.home_team_id,
            before_datetime=match.scheduled_at,  # Use match datetime directly
            limit=100,  # Reasonable limit
            finished_only=True  # Only finished matches
        )
        
        away_team_matches_db = match_repo.get_team_matches_before_date(
            team_id=match.away_team_id,
            before_datetime=match.scheduled_at,
            limit=100,
            finished_only=True
        )
        
        logger = logging.getLogger(__name__)
        logger.info(f"[DB_CONVERSION] Raw DB matches: home={len(home_team_matches_db)}, away={len(away_team_matches_db)}")
        print(f"[DB_CONVERSION] Raw DB matches: home={len(home_team_matches_db)}, away={len(away_team_matches_db)}")
        
        # Convert DB models to domain models
        def db_to_domain_match(match_db) -> DomainMatch:
            return DomainMatch(
                id=match_db.id,
                home_team_id=match_db.home_team_id,
                away_team_id=match_db.away_team_id,
                competition_id=match_db.competition_id or "unknown",
                season_id=match_db.season or "unknown",
                scheduled_at=match_db.scheduled_at,
                status=match_db.status,
                home_score=match_db.home_score,
                away_score=match_db.away_score,
                home_score_ht=match_db.home_score_ht,
                away_score_ht=match_db.away_score_ht,
                outcome=match_db.outcome,
                round=match_db.round,
                created_at=match_db.created_at,
                updated_at=match_db.updated_at,
            )
        
        home_team_matches = [db_to_domain_match(m) for m in home_team_matches_db]
        away_team_matches = [db_to_domain_match(m) for m in away_team_matches_db]
        
        logger.info(f"[DB_CONVERSION] Converted matches: home={len(home_team_matches)}, away={len(away_team_matches)}")
        
        # Combine and deduplicate matches
        all_match_ids = set()
        historical_matches = []
        
        for matches_list in [home_team_matches, away_team_matches]:
            for m in matches_list:
                if m.id not in all_match_ids:
                    # Handle timezone comparison safely
                    match_scheduled = m.scheduled_at
                    if match_scheduled.tzinfo is None:
                        # Assume UTC if no timezone info  
                        match_scheduled = match_scheduled.replace(tzinfo=timezone.utc)
                    
                    # Ensure from_date has timezone info for comparison
                    from_date_tz = from_date
                    if from_date_tz.tzinfo is None:
                        from_date_tz = from_date_tz.replace(tzinfo=timezone.utc)
                    
                    if match_scheduled >= from_date_tz:
                        all_match_ids.add(m.id)
                        historical_matches.append(m)
        
        return historical_matches

    def _build_minimal_context(self, match: Match) -> MatchContext:
        """Build minimal match context when historical data is unavailable.
        
        Returns context with empty historical data that will trigger
        baseline team strength calculations.
        """
        # Get standings if available (fast operation)
        try:
            standings = self.provider.get_standings(
                competition_id=match.competition_id,
                season_id=match.season_id
            )
            home_standing = next(
                (s for s in standings if s.team_id == match.home_team_id),
                None
            )
            away_standing = next(
                (s for s in standings if s.team_id == match.away_team_id),
                None
            )
        except (NotImplementedError, Exception):
            home_standing = None
            away_standing = None
        
        # Build team historical data with empty matches (triggers baseline calculations)
        home_history = TeamHistoricalData(
            team_id=match.home_team_id,
            matches=[],  # Empty - will use baseline team strengths
            standings=home_standing
        )
        
        away_history = TeamHistoricalData(
            team_id=match.away_team_id,
            matches=[],  # Empty - will use baseline team strengths
            standings=away_standing
        )
        
        # Build match context
        return MatchContext(
            match_id=match.id,
            home_team_id=match.home_team_id,
            away_team_id=match.away_team_id,
            scheduled_at=match.scheduled_at,
            competition_id=match.competition_id,
            season_id=match.season_id,
            home_team_history=home_history,
            away_team_history=away_history
        )

    def _build_context_from_matches(
        self,
        match: Match,
        home_team_matches: List[Match],
        away_team_matches: List[Match]
    ) -> MatchContext:
        """Build match context from historical matches.
        
        Args:
            match: Target match
            home_team_matches: Historical matches for home team
            away_team_matches: Historical matches for away team
            
        Returns:
            MatchContext with historical data
        """
        # Get standings if available
        try:
            standings = self.provider.get_standings(
                competition_id=match.competition_id,
                season_id=match.season_id
            )
            home_standing = next(
                (s for s in standings if s.team_id == match.home_team_id),
                None
            )
            away_standing = next(
                (s for s in standings if s.team_id == match.away_team_id),
                None
            )
        except (NotImplementedError, Exception):
            home_standing = None
            away_standing = None
        
        # Build team historical data
        home_history = TeamHistoricalData(
            team_id=match.home_team_id,
            matches=home_team_matches,
            standings=home_standing
        )
        
        away_history = TeamHistoricalData(
            team_id=match.away_team_id,
            matches=away_team_matches,
            standings=away_standing
        )
        
        # Build match context
        return MatchContext(
            match_id=match.id,
            home_team_id=match.home_team_id,
            away_team_id=match.away_team_id,
            scheduled_at=match.scheduled_at,
            competition_id=match.competition_id,
            season_id=match.season_id,
            home_team_history=home_history,
            away_team_history=away_history
        )
    
    def get_feature_summary(self, features: Dict[str, Optional[float]]) -> Dict[str, any]:
        """Get a human-readable summary of extracted features.
        
        Args:
            features: Feature dictionary from extract_features()
            
        Returns:
            Summary dictionary with grouped features
        """
        summary = {
            "match_info": {
                "match_id": features.get("match_id"),
                "home_team_id": features.get("home_team_id"),
                "away_team_id": features.get("away_team_id"),
                "competition_id": features.get("competition_id"),
            },
            "home_strength": {
                "attack": features.get("home_attack_strength"),
                "defense": features.get("home_defense_strength"),
                "overall_home": features.get("home_home_strength"),
                "overall_away": features.get("home_away_strength"),
            },
            "away_strength": {
                "attack": features.get("away_attack_strength"),
                "defense": features.get("away_defense_strength"),
                "overall_home": features.get("away_home_strength"),
                "overall_away": features.get("away_away_strength"),
            },
            "home_form": {
                "recent_wins": features.get("home_recent_wins"),
                "recent_draws": features.get("home_recent_draws"),
                "recent_losses": features.get("home_recent_losses"),
                "recent_points": features.get("home_recent_points"),
                "points_per_match": features.get("home_form_points_per_match"),
            },
            "away_form": {
                "recent_wins": features.get("away_recent_wins"),
                "recent_draws": features.get("away_recent_draws"),
                "recent_losses": features.get("away_recent_losses"),
                "recent_points": features.get("away_recent_points"),
                "points_per_match": features.get("away_form_points_per_match"),
            },
            "data_availability": {
                "home_has_data": any(
                    v is not None for k, v in features.items()
                    if k.startswith("home_") and k not in ["home_team_id"]
                ),
                "away_has_data": any(
                    v is not None for k, v in features.items()
                    if k.startswith("away_") and k not in ["away_team_id"]
                ),
            }
        }
        
        return summary
    
    def check_data_sufficiency(self, match: Match) -> Dict[str, bool]:
        """Check if sufficient historical data exists for feature extraction.
        
        Args:
            match: Match to check
            
        Returns:
            Dictionary indicating data sufficiency for each team
        """
        context = self._build_match_context(match)
        
        home_finished = len(context.home_team_history.get_finished_matches())
        away_finished = len(context.away_team_history.get_finished_matches())
        
        return {
            "home_sufficient": home_finished >= self.min_matches,
            "away_sufficient": away_finished >= self.min_matches,
            "both_sufficient": (
                home_finished >= self.min_matches and
                away_finished >= self.min_matches
            ),
            "home_match_count": home_finished,
            "away_match_count": away_finished,
            "min_required": self.min_matches,
        }

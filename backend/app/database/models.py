"""SQLAlchemy ORM models for football data persistence.

All models include:
- UUID primary key
- created_at/updated_at timestamps (UTC)
- provider_source_id FK to track data source
- provider_id to track external provider identifier
- Composite unique constraints on (provider_source_id, provider_id)

This ensures idempotent ingestion: same provider data can be upserted safely.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Column,
    String,
    Integer,
    Float,
    Boolean,
    DateTime,
    Text,
    ForeignKey,
    UniqueConstraint,
    Index,
    JSON,
    Enum as SQLEnum,
)
from sqlalchemy.orm import relationship

from app.database.base import Base, BaseModel
from app.domain.enums import MatchStatus, MatchOutcome, MatchEventType


class ProviderSource(BaseModel, Base):
    """Track football data provider sources.
    
    Each provider (ryzellx, fotmob, openligadb) is registered here.
    All data records link back to their provider source.
    """
    
    __tablename__ = "provider_sources"
    
    name = Column(String(50), unique=True, nullable=False, index=True)
    base_url = Column(String(255), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    last_seen_at = Column(DateTime(timezone=True), nullable=True)
    
    # Relationships
    competitions = relationship("Competition", back_populates="provider_source")
    teams = relationship("Team", back_populates="provider_source")
    players = relationship("Player", back_populates="provider_source")
    matches = relationship("Match", back_populates="provider_source")
    match_events = relationship("MatchEvent", back_populates="provider_source")
    standings = relationship("Standing", back_populates="provider_source")
    match_statistics = relationship("MatchStatistic", back_populates="provider_source")


class Competition(BaseModel, Base):
    """Football competition/league.
    
    Examples: Premier League, La Liga, Champions League.
    """
    
    __tablename__ = "competitions"
    
    # Provider metadata
    provider_source_id = Column(String(36), ForeignKey("provider_sources.id"), nullable=False, index=True)
    provider_id = Column(String(100), nullable=False, index=True)
    
    # Competition data
    name = Column(String(200), nullable=False)
    country = Column(String(100), nullable=True)
    level = Column(Integer, nullable=True)  # 1=top tier, 2=second tier, etc.
    type = Column(String(50), nullable=True)  # e.g., 'league', 'cup', 'international'
    season = Column(String(20), nullable=True)  # e.g., '2023/24'
    logo_url = Column(String(500), nullable=True)
    
    # Relationships
    provider_source = relationship("ProviderSource", back_populates="competitions")
    matches = relationship("Match", back_populates="competition")
    standings = relationship("Standing", back_populates="competition")
    
    # Unique constraint: one record per (provider, provider_id)
    __table_args__ = (
        UniqueConstraint("provider_source_id", "provider_id", name="uq_competition_provider"),
        Index("ix_competition_name", "name"),
    )


class Team(BaseModel, Base):
    """Football team/club."""
    
    __tablename__ = "teams"
    
    # Provider metadata
    provider_source_id = Column(String(36), ForeignKey("provider_sources.id"), nullable=False, index=True)
    provider_id = Column(String(100), nullable=False, index=True)
    
    # Team data
    name = Column(String(200), nullable=False, index=True)
    short_name = Column(String(100), nullable=True)
    code = Column(String(10), nullable=True)  # e.g., 'MUN', 'ARS'
    country = Column(String(100), nullable=True)
    founded = Column(Integer, nullable=True)
    venue_name = Column(String(200), nullable=True)
    logo_url = Column(String(500), nullable=True)
    
    # Relationships
    provider_source = relationship("ProviderSource", back_populates="teams")
    home_matches = relationship("Match", foreign_keys="Match.home_team_id", back_populates="home_team")
    away_matches = relationship("Match", foreign_keys="Match.away_team_id", back_populates="away_team")
    players = relationship("Player", back_populates="team")
    standings = relationship("Standing", back_populates="team")
    match_statistics = relationship("MatchStatistic", back_populates="team")
    
    # Unique constraint: one record per (provider, provider_id)
    __table_args__ = (
        UniqueConstraint("provider_source_id", "provider_id", name="uq_team_provider"),
    )


class Player(BaseModel, Base):
    """Football player."""
    
    __tablename__ = "players"
    
    # Provider metadata
    provider_source_id = Column(String(36), ForeignKey("provider_sources.id"), nullable=False, index=True)
    provider_id = Column(String(100), nullable=False, index=True)
    
    # Player data
    name = Column(String(200), nullable=False, index=True)
    date_of_birth = Column(String(20), nullable=True)  # ISO date string
    nationality = Column(String(100), nullable=True)
    position = Column(String(50), nullable=True)
    shirt_number = Column(Integer, nullable=True)
    team_id = Column(String(36), ForeignKey("teams.id"), nullable=True, index=True)
    height_cm = Column(Integer, nullable=True)
    weight_kg = Column(Integer, nullable=True)
    photo_url = Column(String(500), nullable=True)
    
    # Relationships
    provider_source = relationship("ProviderSource", back_populates="players")
    team = relationship("Team", back_populates="players")
    
    # Unique constraint: one record per (provider, provider_id)
    __table_args__ = (
        UniqueConstraint("provider_source_id", "provider_id", name="uq_player_provider"),
    )


class Match(BaseModel, Base):
    """Football match.
    
    Stores both scheduled and completed matches with scores, status, and metadata.
    """
    
    __tablename__ = "matches"
    
    # Provider metadata
    provider_source_id = Column(String(36), ForeignKey("provider_sources.id"), nullable=False, index=True)
    provider_id = Column(String(100), nullable=False, index=True)
    
    # Match identifiers
    competition_id = Column(String(36), ForeignKey("competitions.id"), nullable=True, index=True)
    home_team_id = Column(String(36), ForeignKey("teams.id"), nullable=False, index=True)
    away_team_id = Column(String(36), ForeignKey("teams.id"), nullable=False, index=True)
    
    # Timing
    scheduled_at = Column(DateTime(timezone=True), nullable=False, index=True)
    status = Column(SQLEnum(MatchStatus), nullable=False, default=MatchStatus.SCHEDULED, index=True)
    minute = Column(Integer, nullable=True)
    added_time = Column(Integer, nullable=True)
    
    # Scores
    home_score = Column(Integer, nullable=True)
    away_score = Column(Integer, nullable=True)
    home_score_ht = Column(Integer, nullable=True)  # Half-time score
    away_score_ht = Column(Integer, nullable=True)
    
    # xG (expected goals) - may be None if not available
    home_xg = Column(Float, nullable=True)
    away_xg = Column(Float, nullable=True)
    
    # Outcome
    outcome = Column(SQLEnum(MatchOutcome), nullable=True)
    
    # Match context
    round = Column(Integer, nullable=True)
    season = Column(String(20), nullable=True)
    venue_name = Column(String(200), nullable=True)
    
    # Provider timestamps
    provider_fetched_at = Column(DateTime(timezone=True), nullable=True)
    provider_updated_at = Column(DateTime(timezone=True), nullable=True)
    last_provider_update = Column(DateTime(timezone=True), nullable=True)
    
    # Relationships
    provider_source = relationship("ProviderSource", back_populates="matches")
    competition = relationship("Competition", back_populates="matches")
    home_team = relationship("Team", foreign_keys=[home_team_id], back_populates="home_matches")
    away_team = relationship("Team", foreign_keys=[away_team_id], back_populates="away_matches")
    events = relationship("MatchEvent", back_populates="match", cascade="all, delete-orphan")
    statistics = relationship("MatchStatistic", back_populates="match", cascade="all, delete-orphan")
    
    # Unique constraint: one record per (provider, provider_id)
    __table_args__ = (
        UniqueConstraint("provider_source_id", "provider_id", name="uq_match_provider"),
        Index("ix_match_scheduled_at_status", "scheduled_at", "status"),
        Index("ix_match_teams", "home_team_id", "away_team_id"),
    )


class MatchEvent(BaseModel, Base):
    """Match event (goal, card, substitution, etc.)."""
    
    __tablename__ = "match_events"
    
    # Provider metadata
    provider_source_id = Column(String(36), ForeignKey("provider_sources.id"), nullable=False, index=True)
    provider_id = Column(String(100), nullable=False, index=True)
    
    # Event data
    match_id = Column(String(36), ForeignKey("matches.id"), nullable=False, index=True)
    type = Column(SQLEnum(MatchEventType), nullable=False, index=True)
    minute = Column(Integer, nullable=False)
    added_time = Column(Integer, nullable=True)
    team_id = Column(String(36), ForeignKey("teams.id"), nullable=False, index=True)
    player_id = Column(String(36), ForeignKey("players.id"), nullable=True, index=True)
    related_player_id = Column(String(36), ForeignKey("players.id"), nullable=True)
    description = Column(Text, nullable=True)
    
    # Provider timestamps
    provider_fetched_at = Column(DateTime(timezone=True), nullable=True)
    
    # Relationships
    provider_source = relationship("ProviderSource", back_populates="match_events")
    match = relationship("Match", back_populates="events")
    team = relationship("Team")
    player = relationship("Player", foreign_keys=[player_id])
    related_player = relationship("Player", foreign_keys=[related_player_id])
    
    # Unique constraint: one record per (match, provider, provider_id)
    __table_args__ = (
        UniqueConstraint("match_id", "provider_source_id", "provider_id", name="uq_match_event_provider"),
        Index("ix_match_event_minute", "match_id", "minute"),
    )


class Standing(BaseModel, Base):
    """League standing/table entry."""
    
    __tablename__ = "standings"
    
    # Provider metadata
    provider_source_id = Column(String(36), ForeignKey("provider_sources.id"), nullable=False, index=True)
    provider_id = Column(String(100), nullable=False, index=True)
    
    # Standing identifiers
    competition_id = Column(String(36), ForeignKey("competitions.id"), nullable=False, index=True)
    season = Column(String(20), nullable=False)
    team_id = Column(String(36), ForeignKey("teams.id"), nullable=False, index=True)
    
    # Table position
    position = Column(Integer, nullable=False)
    played = Column(Integer, nullable=False, default=0)
    won = Column(Integer, nullable=False, default=0)
    drawn = Column(Integer, nullable=False, default=0)
    lost = Column(Integer, nullable=False, default=0)
    
    # Goals
    goals_for = Column(Integer, nullable=False, default=0)
    goals_against = Column(Integer, nullable=False, default=0)
    goal_difference = Column(Integer, nullable=False, default=0)
    
    # Points
    points = Column(Integer, nullable=False, default=0)
    
    # Home/away splits (optional)
    home_played = Column(Integer, nullable=True)
    home_won = Column(Integer, nullable=True)
    home_drawn = Column(Integer, nullable=True)
    home_lost = Column(Integer, nullable=True)
    away_played = Column(Integer, nullable=True)
    away_won = Column(Integer, nullable=True)
    away_drawn = Column(Integer, nullable=True)
    away_lost = Column(Integer, nullable=True)
    
    # Form (e.g., 'WWDLL')
    form = Column(String(20), nullable=True)
    
    # Provider timestamps
    provider_fetched_at = Column(DateTime(timezone=True), nullable=True)
    
    # Relationships
    provider_source = relationship("ProviderSource", back_populates="standings")
    competition = relationship("Competition", back_populates="standings")
    team = relationship("Team", back_populates="standings")
    
    # Unique constraint: one record per (competition, season, team, provider)
    __table_args__ = (
        UniqueConstraint("competition_id", "season", "team_id", "provider_source_id", name="uq_standing_provider"),
        Index("ix_standing_position", "competition_id", "season", "position"),
    )


class MatchStatistic(BaseModel, Base):
    """Team match statistics.
    
    Stores detailed statistics for a team in a specific match.
    Each match can have two records (one per team).
    """
    
    __tablename__ = "match_statistics"
    
    # Provider metadata
    provider_source_id = Column(String(36), ForeignKey("provider_sources.id"), nullable=False, index=True)
    provider_id = Column(String(100), nullable=False, index=True)
    
    # Match and team
    match_id = Column(String(36), ForeignKey("matches.id"), nullable=False, index=True)
    team_id = Column(String(36), ForeignKey("teams.id"), nullable=False, index=True)
    
    # Goals
    goals_scored = Column(Integer, nullable=True)
    goals_conceded = Column(Integer, nullable=True)
    
    # Expected goals - may be None if unavailable
    xg = Column(Float, nullable=True)
    xg_against = Column(Float, nullable=True)
    
    # Shots
    shots_total = Column(Integer, nullable=True)
    shots_on_target = Column(Integer, nullable=True)
    shots_off_target = Column(Integer, nullable=True)
    shots_blocked = Column(Integer, nullable=True)
    
    # Possession
    possession_percentage = Column(Float, nullable=True)
    
    # Passing
    passes_completed = Column(Integer, nullable=True)
    passes_attempted = Column(Integer, nullable=True)
    pass_accuracy = Column(Float, nullable=True)
    
    # Set pieces
    corners = Column(Integer, nullable=True)
    free_kicks = Column(Integer, nullable=True)
    offsides = Column(Integer, nullable=True)
    
    # Discipline
    yellow_cards = Column(Integer, nullable=True)
    red_cards = Column(Integer, nullable=True)
    fouls_committed = Column(Integer, nullable=True)
    
    # Defensive
    tackles = Column(Integer, nullable=True)
    interceptions = Column(Integer, nullable=True)
    clearances = Column(Integer, nullable=True)
    saves = Column(Integer, nullable=True)
    
    # Provider timestamps
    provider_fetched_at = Column(DateTime(timezone=True), nullable=True)
    
    # Relationships
    provider_source = relationship("ProviderSource", back_populates="match_statistics")
    match = relationship("Match", back_populates="statistics")
    team = relationship("Team", back_populates="match_statistics")
    
    # Unique constraint: one record per (match, team, provider)
    __table_args__ = (
        UniqueConstraint("match_id", "team_id", "provider_source_id", name="uq_match_statistic_provider"),
    )


class LatencyLog(BaseModel, Base):
    """Log of data latency measurements.
    
    Tracks latency from provider event timestamp through to API response.
    """
    
    __tablename__ = "latency_logs"
    
    # Entity reference
    entity_type = Column(String(50), nullable=False, index=True)  # e.g., 'match', 'live_match'
    entity_id = Column(String(100), nullable=False, index=True)  # provider_id or internal ID
    
    # Latency data stored as JSON
    latency_json = Column(JSON, nullable=False)
    
    # Indexes
    __table_args__ = (
        Index("ix_latency_entity", "entity_type", "entity_id"),
        Index("ix_latency_created", "created_at"),
    )


class PredictionVersionDB(BaseModel, Base):
    """Prediction version snapshot (immutable history).
    
    Tracks prediction evolution through match lifecycle stages.
    Once written, a version is NEVER modified.
    """
    
    __tablename__ = "prediction_versions"
    
    # Match reference
    match_id = Column(String(100), nullable=False, index=True)
    
    # Lifecycle stage
    stage = Column(String(50), nullable=False, index=True)  # 7d_before, 24h_before, lineup_confirmed, kickoff, live
    
    # Prediction data (complete snapshot as JSON)
    prediction_data = Column(JSON, nullable=False)
    
    # Model metadata
    model_versions = Column(JSON, nullable=True)  # {model_id: version}
    
    # Quality scores
    data_quality_score = Column(Float, nullable=False, default=0.0)
    confidence_score = Column(Float, nullable=False, default=0.0)
    
    # Notes
    notes = Column(JSON, nullable=True)  # List of strings
    
    # Indexes
    __table_args__ = (
        Index("ix_prediction_version_match", "match_id", "stage"),
        Index("ix_prediction_version_created", "created_at"),
    )


class TrackRecordDB(BaseModel, Base):
    """Track record of prediction outcomes.
    
    Stores ALL predictions with outcomes for transparent performance evaluation.
    NO cherry-picking - includes successes and failures.
    """
    
    __tablename__ = "track_record"
    
    # Prediction reference
    prediction_version_id = Column(String(36), ForeignKey("prediction_versions.id"), nullable=False, index=True)
    match_id = Column(String(100), nullable=False, index=True)
    
    # Predicted probabilities
    predicted_home_win = Column(Float, nullable=False)
    predicted_draw = Column(Float, nullable=False)
    predicted_away_win = Column(Float, nullable=False)
    
    # Actual outcome
    actual_outcome = Column(String(20), nullable=False)  # home_win, draw, away_win
    actual_home_score = Column(Integer, nullable=False)
    actual_away_score = Column(Integer, nullable=False)
    
    # Timestamps
    prediction_timestamp = Column(DateTime(timezone=True), nullable=False, index=True)
    match_timestamp = Column(DateTime(timezone=True), nullable=False)
    
    # Market predictions (optional)
    over_2_5_predicted = Column(Float, nullable=True)
    over_2_5_actual = Column(Boolean, nullable=True)
    btts_predicted = Column(Float, nullable=True)
    btts_actual = Column(Boolean, nullable=True)
    
    # Betting odds (optional)
    home_odds = Column(Float, nullable=True)
    draw_odds = Column(Float, nullable=True)
    away_odds = Column(Float, nullable=True)
    
    # Grouping metadata
    league_id = Column(String(100), nullable=True, index=True)
    model_id = Column(String(100), nullable=True, index=True)
    stage = Column(String(50), nullable=True, index=True)
    
    # Indexes
    __table_args__ = (
        Index("ix_track_record_league", "league_id", "prediction_timestamp"),
        Index("ix_track_record_model", "model_id", "prediction_timestamp"),
    )

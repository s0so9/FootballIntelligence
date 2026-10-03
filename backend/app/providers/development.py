"""Development/Mock data provider.

⚠️  WARNING: ALL DATA IN THIS MODULE IS MOCK/DEVELOPMENT DATA ⚠️

This provider supplies fictitious football data for development and testing.
NEVER present this data as real football information to end users.

All teams, players, matches, and statistics are entirely fictional and
created for development purposes only.
"""

from datetime import datetime, date, timedelta
from typing import List, Optional

from app.domain.entities import Competition, Season, Team, Player, Venue
from app.domain.match import Match, MatchEvent, Lineup
from app.domain.statistics import Standing, TeamMatchStatistic
from app.domain.enums import MatchStatus, MatchOutcome, DataSource
from app.providers.base import FootballDataProvider


class DevelopmentProvider(FootballDataProvider):
    """
    Development data provider supplying mock football data.
    
    ⚠️  ALL DATA IS FICTITIOUS - FOR DEVELOPMENT ONLY ⚠️
    
    This provider returns predetermined, internally consistent mock data
    for development and testing. It does not connect to any external APIs
    or databases.
    
    Data characteristics:
    - Deterministic (same data on each call)
    - Internally consistent (IDs and relationships are valid)
    - Clearly labeled as DEVELOPMENT data
    - Small dataset (not production-scale)
    - No network requests
    - No real football information
    """
    
    def __init__(self):
        """Initialize development provider with mock data."""
        self._init_mock_data()
    
    def _init_mock_data(self):
        """Initialize mock data structures.
        
        ⚠️  ALL DATA CREATED HERE IS FICTITIOUS ⚠️
        """
        # === Mock Competitions ===
        self._competitions = [
            Competition(
                id="dev_comp_league_a",
                name="[DEV] League A",  # [DEV] prefix marks as development data
                country="DEV",
                level=1,
                type="league",
            ),
            Competition(
                id="dev_comp_league_b",
                name="[DEV] League B",
                country="DEV",
                level=2,
                type="league",
            ),
        ]
        
        # === Mock Seasons ===
        self._seasons = [
            Season(
                id="dev_season_2023_2024",
                competition_id="dev_comp_league_a",
                year="2023/2024",
                start_date=date(2023, 8, 1),
                end_date=date(2024, 5, 31),
                is_current=True,
            ),
        ]
        
        # === Mock Venues ===
        self._venues = [
            Venue(
                id="dev_venue_stadium_a",
                name="[DEV] Stadium A",
                city="Development City",
                country="DEV",
                capacity=50000,
                surface="Grass",
            ),
            Venue(
                id="dev_venue_stadium_b",
                name="[DEV] Stadium B",
                city="Development City",
                country="DEV",
                capacity=45000,
                surface="Grass",
            ),
        ]
        
        # === Mock Teams ===
        self._teams = [
            Team(
                id="dev_team_alpha",
                name="[DEV] Team Alpha",
                short_name="Alpha",
                code="ALP",
                country="DEV",
                founded=2000,
                venue_id="dev_venue_stadium_a",
            ),
            Team(
                id="dev_team_beta",
                name="[DEV] Team Beta",
                short_name="Beta",
                code="BET",
                country="DEV",
                founded=2001,
                venue_id="dev_venue_stadium_b",
            ),
            Team(
                id="dev_team_gamma",
                name="[DEV] Team Gamma",
                short_name="Gamma",
                code="GAM",
                country="DEV",
                founded=2002,
            ),
            Team(
                id="dev_team_delta",
                name="[DEV] Team Delta",
                short_name="Delta",
                code="DEL",
                country="DEV",
                founded=2003,
            ),
        ]
        
        # === Mock Players ===
        self._players = [
            # Team Alpha players
            Player(
                id="dev_player_alpha_1",
                name="[DEV] Player A1",
                date_of_birth=date(1995, 1, 15),
                nationality="DEV",
                position="Forward",
                shirt_number=9,
                team_id="dev_team_alpha",
            ),
            Player(
                id="dev_player_alpha_2",
                name="[DEV] Player A2",
                date_of_birth=date(1996, 3, 20),
                nationality="DEV",
                position="Midfielder",
                shirt_number=10,
                team_id="dev_team_alpha",
            ),
            # Team Beta players
            Player(
                id="dev_player_beta_1",
                name="[DEV] Player B1",
                date_of_birth=date(1994, 5, 10),
                nationality="DEV",
                position="Forward",
                shirt_number=9,
                team_id="dev_team_beta",
            ),
            Player(
                id="dev_player_beta_2",
                name="[DEV] Player B2",
                date_of_birth=date(1997, 7, 25),
                nationality="DEV",
                position="Defender",
                shirt_number=4,
                team_id="dev_team_beta",
            ),
        ]
        
        # === Mock Matches ===
        # Dates relative to "now" for testing
        today = date.today()
        
        self._matches = [
            # Past match
            Match(
                id="dev_match_001",
                competition_id="dev_comp_league_a",
                season_id="dev_season_2023_2024",
                home_team_id="dev_team_alpha",
                away_team_id="dev_team_beta",
                venue_id="dev_venue_stadium_a",
                scheduled_at=datetime.combine(today - timedelta(days=7), datetime.min.time()).replace(hour=15),
                status=MatchStatus.FINISHED,
                home_score=2,
                away_score=1,
                home_score_ht=1,
                away_score_ht=0,
                outcome=MatchOutcome.HOME_WIN,
                round=10,
            ),
            # Upcoming match
            Match(
                id="dev_match_002",
                competition_id="dev_comp_league_a",
                season_id="dev_season_2023_2024",
                home_team_id="dev_team_gamma",
                away_team_id="dev_team_delta",
                scheduled_at=datetime.combine(today + timedelta(days=3), datetime.min.time()).replace(hour=15),
                status=MatchStatus.SCHEDULED,
                round=11,
            ),
            # Another past match
            Match(
                id="dev_match_003",
                competition_id="dev_comp_league_a",
                season_id="dev_season_2023_2024",
                home_team_id="dev_team_beta",
                away_team_id="dev_team_gamma",
                scheduled_at=datetime.combine(today - timedelta(days=14), datetime.min.time()).replace(hour=15),
                status=MatchStatus.FINISHED,
                home_score=1,
                away_score=1,
                home_score_ht=1,
                away_score_ht=1,
                outcome=MatchOutcome.DRAW,
                round=9,
            ),
            # Recent match
            Match(
                id="dev_match_004",
                competition_id="dev_comp_league_a",
                season_id="dev_season_2023_2024",
                home_team_id="dev_team_delta",
                away_team_id="dev_team_alpha",
                scheduled_at=datetime.combine(today - timedelta(days=3), datetime.min.time()).replace(hour=15),
                status=MatchStatus.FINISHED,
                home_score=0,
                away_score=3,
                home_score_ht=0,
                away_score_ht=2,
                outcome=MatchOutcome.AWAY_WIN,
                round=10,
            ),
        ]
        
        # === Mock Standings ===
        self._standings = [
            Standing(
                id="dev_standing_alpha",
                competition_id="dev_comp_league_a",
                season_id="dev_season_2023_2024",
                team_id="dev_team_alpha",
                position=1,
                played=10,
                won=7,
                drawn=2,
                lost=1,
                goals_for=22,
                goals_against=10,
                goal_difference=12,
                points=23,
                form="WWDWW",
            ),
            Standing(
                id="dev_standing_beta",
                competition_id="dev_comp_league_a",
                season_id="dev_season_2023_2024",
                team_id="dev_team_beta",
                position=2,
                played=10,
                won=6,
                drawn=3,
                lost=1,
                goals_for=18,
                goals_against=12,
                goal_difference=6,
                points=21,
                form="WDWDL",
            ),
            Standing(
                id="dev_standing_gamma",
                competition_id="dev_comp_league_a",
                season_id="dev_season_2023_2024",
                team_id="dev_team_gamma",
                position=3,
                played=10,
                won=5,
                drawn=2,
                lost=3,
                goals_for=15,
                goals_against=13,
                goal_difference=2,
                points=17,
                form="WLDWL",
            ),
            Standing(
                id="dev_standing_delta",
                competition_id="dev_comp_league_a",
                season_id="dev_season_2023_2024",
                team_id="dev_team_delta",
                position=4,
                played=10,
                won=2,
                drawn=3,
                lost=5,
                goals_for=10,
                goals_against=18,
                goal_difference=-8,
                points=9,
                form="LLDLL",
            ),
        ]
        
        # === Mock Team Match Statistics ===
        self._team_statistics = [
            TeamMatchStatistic(
                id="dev_team_stat_001_home",
                match_id="dev_match_001",
                team_id="dev_team_alpha",
                goals_scored=2,
                goals_conceded=1,
                xg=2.1,
                xg_against=0.8,
                shots_total=15,
                shots_on_target=7,
                possession_percentage=58.0,
                passes_completed=450,
                passes_attempted=520,
                corners=6,
                yellow_cards=2,
                red_cards=0,
            ),
            TeamMatchStatistic(
                id="dev_team_stat_001_away",
                match_id="dev_match_001",
                team_id="dev_team_beta",
                goals_scored=1,
                goals_conceded=2,
                xg=0.8,
                xg_against=2.1,
                shots_total=8,
                shots_on_target=3,
                possession_percentage=42.0,
                passes_completed=320,
                passes_attempted=400,
                corners=3,
                yellow_cards=3,
                red_cards=0,
            ),
        ]
    
    # === Provider Interface Implementation ===
    
    def get_provider_name(self) -> str:
        """Return provider name."""
        return "DevelopmentProvider (Mock Data)"
    
    def is_development_data(self) -> bool:
        """
        Return True - this provider supplies MOCK data only.
        
        ⚠️  ALL DATA IS FICTITIOUS ⚠️
        """
        return True
    
    # === Competition and Season ===
    
    def get_competitions(self) -> List[Competition]:
        """Get mock competitions."""
        return self._competitions.copy()
    
    def get_competition(self, competition_id: str) -> Optional[Competition]:
        """Get a specific mock competition."""
        for comp in self._competitions:
            if comp.id == competition_id:
                return comp
        return None
    
    def get_seasons(self, competition_id: str) -> List[Season]:
        """Get mock seasons for a competition."""
        return [s for s in self._seasons if s.competition_id == competition_id]
    
    def get_current_season(self, competition_id: str) -> Optional[Season]:
        """Get current mock season for a competition."""
        for season in self._seasons:
            if season.competition_id == competition_id and season.is_current:
                return season
        return None
    
    # === Teams ===
    
    def get_teams(self, competition_id: str, season_id: str) -> List[Team]:
        """Get mock teams in a competition season."""
        # For development, return all teams for League A
        if competition_id == "dev_comp_league_a":
            return self._teams.copy()
        return []
    
    def get_team(self, team_id: str) -> Optional[Team]:
        """Get a specific mock team."""
        for team in self._teams:
            if team.id == team_id:
                return team
        return None
    
    # === Players ===
    
    def get_team_players(self, team_id: str) -> List[Player]:
        """Get mock players for a team."""
        return [p for p in self._players if p.team_id == team_id]
    
    def get_player(self, player_id: str) -> Optional[Player]:
        """Get a specific mock player."""
        for player in self._players:
            if player.id == player_id:
                return player
        return None
    
    # === Venues ===
    
    def get_venue(self, venue_id: str) -> Optional[Venue]:
        """Get a specific mock venue."""
        for venue in self._venues:
            if venue.id == venue_id:
                return venue
        return None
    
    # === Matches ===
    
    def get_matches(
        self,
        competition_id: Optional[str] = None,
        season_id: Optional[str] = None,
        team_id: Optional[str] = None,
        from_date: Optional[date] = None,
        to_date: Optional[date] = None,
        status: Optional[str] = None,
    ) -> List[Match]:
        """Get mock matches with optional filters."""
        matches = self._matches.copy()
        
        if competition_id:
            matches = [m for m in matches if m.competition_id == competition_id]
        
        if season_id:
            matches = [m for m in matches if m.season_id == season_id]
        
        if team_id:
            matches = [m for m in matches if m.home_team_id == team_id or m.away_team_id == team_id]
        
        if from_date:
            matches = [m for m in matches if m.scheduled_at.date() >= from_date]
        
        if to_date:
            matches = [m for m in matches if m.scheduled_at.date() <= to_date]
        
        if status:
            matches = [m for m in matches if m.status.value == status]
        
        return matches
    
    def get_match(self, match_id: str) -> Optional[Match]:
        """Get a specific mock match."""
        for match in self._matches:
            if match.id == match_id:
                return match
        return None
    
    # === Statistics ===
    
    def get_standings(self, competition_id: str, season_id: str) -> List[Standing]:
        """Get mock league standings."""
        return [
            s for s in self._standings
            if s.competition_id == competition_id and s.season_id == season_id
        ]
    
    def get_team_match_statistics(self, match_id: str) -> List[TeamMatchStatistic]:
        """Get mock team statistics for a match."""
        return [s for s in self._team_statistics if s.match_id == match_id]

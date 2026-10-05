/**
 * API Response Types
 * 
 * Type definitions matching the backend API schemas.
 */

export type MatchStatus = 
  | 'scheduled' 
  | 'live' 
  | 'finished' 
  | 'postponed' 
  | 'cancelled' 
  | 'abandoned';

export type MatchOutcome = 'home_win' | 'draw' | 'away_win';

export interface TeamInfoResponse {
  id: string;
  name: string;
  short_name: string | null;
  code: string | null;
  logo_url: string | null;
}

export interface MatchStatisticsResponse {
  goals_scored: number | null;
  goals_conceded: number | null;
  xg: number | null;
  xg_against: number | null;
  shots_total: number | null;
  shots_on_target: number | null;
  shots_off_target: number | null;
  shots_blocked: number | null;
  possession_percentage: number | null;
  passes_completed: number | null;
  passes_attempted: number | null;
  pass_accuracy: number | null;
  corners: number | null;
  free_kicks: number | null;
  offsides: number | null;
  yellow_cards: number | null;
  red_cards: number | null;
  fouls_committed: number | null;
  tackles: number | null;
  interceptions: number | null;
  clearances: number | null;
  saves: number | null;
}

export interface MatchResponse {
  id: string;
  competition_id: string;
  season_id: string;
  home_team_id: string;
  away_team_id: string;
  venue_id: string | null;
  home_team: TeamInfoResponse | null;
  away_team: TeamInfoResponse | null;
  scheduled_at: string;
  status: MatchStatus;
  home_score: number | null;
  away_score: number | null;
  home_score_ht: number | null;
  away_score_ht: number | null;
  home_statistics: MatchStatisticsResponse | null;
  away_statistics: MatchStatisticsResponse | null;
  home_statistics_ht: MatchStatisticsResponse | null;
  away_statistics_ht: MatchStatisticsResponse | null;
  minute: number | null;
  added_time: number | null;
  outcome: MatchOutcome | null;
  round: number | null;
  created_at: string | null;
  updated_at: string | null;
}

export interface MatchListResponse {
  matches: MatchResponse[];
  count: number;
  is_development_data: boolean;
}

export interface MatchDetailResponse {
  match: MatchResponse;
  is_development_data: boolean;
}

export interface MarketOutcomeResponse {
  label: string;
  model_probability: number;
  calibrated_probability: number | null;
  fair_odds: number;
}

export interface BookmakerComparisonResponse {
  label: string;
  fair_probability: number;
  fair_odds: number;
  bookmaker_odds: number;
  implied_probability: number;
  edge_value: number;
  has_value_flag: boolean;
}

export interface MarketAnalysisResponse {
  market_type: string;
  line: number | null;
  outcomes: MarketOutcomeResponse[];
  bookmaker_comparison: BookmakerComparisonResponse[] | null;
  bookmaker_overround: number | null;
  has_bookmaker_odds: boolean;
}

export interface EasyMatchSignalResponse {
  name: string;
  value: number;
  weight: number;
  available: boolean;
  description: string | null;
}

export interface EasyMatchResponse {
  match_id: string;
  is_easy_match: boolean;
  confidence_score: number;
  threshold: number;
  signals: EasyMatchSignalResponse[];
  dominant_outcome: string | null;
  dominant_probability: number | null;
  reasons: string[];
  warnings: string[];
  data_sufficient: boolean;
}

export interface MensionePickResponse {
  pick_market: string;
  pick_probability: number;
  confidence_label: string;
  confidence_score: number;
  expected_value: number | null;
  market_odds: number | null;
  fair_odds: number;
  edge: number | null;
  reasoning_factors: string[];
  predicted_score: string;
  score_distribution_top5: string[];
}

export interface MatchPredictionResponse {
  match_id: string;
  home_win_probability: number;
  draw_probability: number;
  away_win_probability: number;
  home_xg: number;
  away_xg: number;
  btts_probability: number;
  predicted_score: string | null;
  mensione_pick: MensionePickResponse | null;
  prediction_version_id: string | null;
  market_analysis: MarketAnalysisResponse[] | null;
  easy_match: EasyMatchResponse | null;
  is_development_data: boolean;
}

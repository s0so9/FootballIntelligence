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
  // Phase 5: Market Intelligence fields (optional, backward compatible)
  real_odds?: number | null;
  implied_probability?: number | null;
  market_edge?: number | null;
  bookmaker?: string | null;
  odds_timestamp?: string | null;
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

/**
 * TUTAR X Pick Response - SmartMarketSelector format
 * Can be either BestTip or PassDecision
 */
export interface MensionePickResponse {
  // Common fields
  match_id: string;
  pass_decision: boolean;
  timestamp: string;
  pipeline_version: string;
  
  // BestTip fields (present when pass_decision === false)
  market?: string;  // e.g., "OVER_0_5", "HOME_WIN", "BTTS_YES"
  selection?: string;  // Human-readable selection
  probability?: number;  // Calibrated model probability
  confidence?: number;  // Overall confidence score (0.0-1.0)
  model_agreement?: number;  // Agreement between models (0.0-1.0)
  data_quality?: number;  // Data quality score (0.0-1.0)
  edge?: number | null;  // Edge over bookmaker odds (when available)
  fair_odds?: number;  // Fair odds from model probability
  bookmaker_odds?: number | null;  // Bookmaker odds (when available)
  odds_movement?: string | null;  // "rising", "falling", "stable"
  value_classification?: string;  // "STRONG_VALUE", "VALUE", "NEUTRAL", "NEGATIVE_VALUE"
  risk_level?: string;  // "LOW", "MEDIUM", "HIGH"
  selection_score?: number;  // Overall selection score (0.0-1.0)
  selector_reason?: string;  // Why this market was selected
  
  // PassDecision fields (present when pass_decision === true)
  pass_reason?: string;  // Why no market qualified
  evaluated_markets_count?: number;
  best_market_details?: Record<string, unknown> | null;
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

/**
 * Competition API Response Types
 */

export interface CompetitionResponse {
  id: string;
  name: string;
  country: string | null;
}

export interface CompetitionListResponse {
  competitions: CompetitionResponse[];
  count: number;
  is_development_data: boolean;
}

/**
 * Live Matches API Response Types (Phase 10A)
 */

export interface LiveMatchResponse {
  match_id: string;
  home_team: string;
  away_team: string;
  home_score: number;
  away_score: number;
  status: MatchStatus;
  minute: number | null;
  added_time: number | null;
  data_quality_flags: {
    has_xg: boolean;
    has_events: boolean;
    has_shots: boolean;
    has_player_positions: boolean;
    has_ball_tracking: boolean;
  };
}

export interface ProviderHealthResponse {
  is_available: boolean;
  availability_code: string;
  last_check_utc: string;
  consecutive_failures: number;
  error_detail: string | null;
}

export interface LiveMatchesResponse {
  matches: LiveMatchResponse[];
  provider_health: Record<string, ProviderHealthResponse>;
  data_quality: {
    total_matches: number;
    matches_with_xg: number;
    matches_with_events: number;
    matches_with_shots: number;
    matches_with_player_positions: number;
    matches_with_ball_tracking: number;
  };
  timestamp: string;
  provider_used: string | null;
  total_count: number;
}

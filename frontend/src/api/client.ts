/**
 * API Client
 * 
 * Centralized HTTP client for backend API calls.
 */

import type {
  MatchListResponse,
  MatchDetailResponse,
  MatchPredictionResponse,
  LiveMatchesResponse,
} from './types';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1';

// Debug: log the actual API base URL being used
console.log('[DEBUG client.ts] API_BASE_URL:', API_BASE_URL);
console.log('[DEBUG client.ts] import.meta.env.VITE_API_BASE_URL:', import.meta.env.VITE_API_BASE_URL);

export class ApiError extends Error {
  constructor(
    message: string,
    public status?: number,
    public detail?: string
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

/**
 * Make an HTTP request to the API.
 */
async function request<T>(endpoint: string, options?: RequestInit): Promise<T> {
  const url = `${API_BASE_URL}${endpoint}`;

  try {
    const response = await fetch(url, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...options?.headers,
      },
    });

    if (!response.ok) {
      let detail = `HTTP ${response.status}: ${response.statusText}`;
      
      try {
        const errorData = await response.json();
        detail = errorData.detail || detail;
      } catch {
        // Ignore JSON parse errors for error responses
      }

      throw new ApiError(
        `API request failed: ${detail}`,
        response.status,
        detail
      );
    }

    return await response.json();
  } catch (error) {
    if (error instanceof ApiError) {
      throw error;
    }

    // Network or other errors
    throw new ApiError(
      error instanceof Error ? error.message : 'Network error occurred',
      undefined,
      'Unable to connect to the backend server'
    );
  }
}

/**
 * Get list of matches.
 */
export async function getMatches(params?: {
  competition_id?: string;
  season_id?: string;
  team_id?: string;
  from_date?: string;
  to_date?: string;
  status?: string;
}): Promise<MatchListResponse> {
  const searchParams = new URLSearchParams();
  
  if (params) {
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined) {
        searchParams.append(key, value);
      }
    });
  }

  const query = searchParams.toString();
  const endpoint = query ? `/matches?${query}` : '/matches';

  console.log('[DEBUG] getMatches URL:', `${API_BASE_URL}${endpoint}`);
  console.log('[DEBUG] getMatches params:', params);

  const response = await request<MatchListResponse>(endpoint);
  
  console.log('[DEBUG] getMatches response:', {
    count: response.count,
    matchesLength: response.matches.length,
    isDevelopmentData: response.is_development_data,
    firstThreeMatches: response.matches.slice(0, 3).map(m => ({
      id: m.id,
      status: m.status,
      scheduled_at: m.scheduled_at,
      home_team_id: m.home_team_id,
      away_team_id: m.away_team_id,
    }))
  });

  return response;
}

/**
 * Get upcoming matches (shortcut).
 */
export async function getUpcomingMatches(days: number = 7): Promise<MatchListResponse> {
  // Use local date to avoid UTC/local timezone mismatches
  const today = new Date();
  const fromDate = formatDateForAPI(today);
  
  const futureDate = new Date(today);
  futureDate.setDate(futureDate.getDate() + days);
  const toDate = formatDateForAPI(futureDate);

  console.log('[DEBUG] getUpcomingMatches called with days:', days);
  console.log('[DEBUG] Date range:', { fromDate, toDate });

  return getMatches({
    from_date: fromDate,
    to_date: toDate,
    status: 'scheduled',
  });
}

/**
 * Format a Date object to YYYY-MM-DD string using local timezone.
 */
function formatDateForAPI(date: Date): string {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

/**
 * Get a single match by ID.
 */
export async function getMatch(matchId: string): Promise<MatchDetailResponse> {
  return request<MatchDetailResponse>(`/matches/${matchId}`);
}

/**
 * Get prediction for a match.
 */
export async function getMatchPrediction(matchId: string): Promise<MatchPredictionResponse> {
  return request<MatchPredictionResponse>(`/matches/${matchId}/prediction`);
}

/**
 * Get live matches with provider health and data quality information.
 */
export async function getLiveMatches(): Promise<LiveMatchesResponse> {
  return request<LiveMatchesResponse>('/matches/live');
}

/**
 * Get live match detail for a specific match.
 * Returns LiveMatchState when match is live, null otherwise.
 */
export async function getLiveMatchDetail(matchId: string): Promise<import('../types/live').LiveMatchState | null> {
  try {
    const response = await getMatch(matchId);
    
    // Only return live state if match is actually live
    if (response.match.status !== 'live') {
      return null;
    }
    
    // Transform MatchResponse to LiveMatchState
    return {
      matchId: response.match.id,
      status: response.match.status.toUpperCase() as import('../types/live').MatchStatusType,
      minute: response.match.minute ?? undefined,
      addedTime: response.match.added_time ?? undefined,
      homeScore: response.match.home_score ?? undefined,
      awayScore: response.match.away_score ?? undefined,
      homeTeam: response.match.home_team ? {
        id: response.match.home_team.id,
        name: response.match.home_team.name,
        code: response.match.home_team.code ?? undefined,
        logo: response.match.home_team.logo_url ?? undefined,
      } : undefined,
      awayTeam: response.match.away_team ? {
        id: response.match.away_team.id,
        name: response.match.away_team.name,
        code: response.match.away_team.code ?? undefined,
        logo: response.match.away_team.logo_url ?? undefined,
      } : undefined,
      homeStats: response.match.home_statistics ? transformStatsToLiveStats(response.match.home_statistics) : undefined,
      awayStats: response.match.away_statistics ? transformStatsToLiveStats(response.match.away_statistics) : undefined,
    };
  } catch (error) {
    console.error('[API] getLiveMatchDetail error:', error);
    throw error;
  }
}

/**
 * Transform MatchStatisticsResponse to LiveStats
 */
function transformStatsToLiveStats(stats: import('./types').MatchStatisticsResponse): import('../types/live').LiveStats {
  return {
    shots: stats.shots_total ?? undefined,
    shotsOnTarget: stats.shots_on_target ?? undefined,
    shotsOutsideBox: stats.shots_off_target ?? undefined,
    xG: stats.xg ?? undefined,
    possession: stats.possession_percentage ?? undefined,
    corners: stats.corners ?? undefined,
    fouls: stats.fouls_committed ?? undefined,
    offsides: stats.offsides ?? undefined,
    yellowCards: stats.yellow_cards ?? undefined,
    redCards: stats.red_cards ?? undefined,
    passes: stats.passes_attempted ?? undefined,
    passAccuracy: stats.pass_accuracy ?? undefined,
    tackles: stats.tackles ?? undefined,
    interceptions: stats.interceptions ?? undefined,
    saves: stats.saves ?? undefined,
  };
}

/**
 * Future: Get live events for a match (placeholder)
 */
export async function getLiveEvents(matchId: string): Promise<import('../types/live').LiveEvent[]> {
  // TODO: Implement when backend endpoint exists
  console.warn(`[API] getLiveEvents not implemented for match ${matchId} - backend endpoint not available`);
  return [];
}

/**
 * Future: Get live shots with coordinates for a match (placeholder)
 */
export async function getLiveShots(matchId: string): Promise<import('../types/live').LiveShot[]> {
  // TODO: Implement when backend endpoint exists
  console.warn(`[API] getLiveShots not implemented for match ${matchId} - backend endpoint not available`);
  return [];
}

/**
 * Future: Get live prediction for a match (placeholder)
 */
export async function getLivePrediction(matchId: string): Promise<import('../types/live').LivePrediction | null> {
  // TODO: Implement when backend endpoint exists
  console.warn(`[API] getLivePrediction not implemented for match ${matchId} - backend endpoint not available`);
  return null;
}

/**
 * Future: Get live markets for a match (placeholder)
 */
export async function getLiveMarkets(matchId: string): Promise<import('../types/live').LiveMarket[]> {
  // TODO: Implement when backend endpoint exists
  console.warn(`[API] getLiveMarkets not implemented for match ${matchId} - backend endpoint not available`);
  return [];
}

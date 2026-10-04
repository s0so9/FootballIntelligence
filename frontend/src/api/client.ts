/**
 * API Client
 * 
 * Centralized HTTP client for backend API calls.
 */

import type {
  MatchListResponse,
  MatchDetailResponse,
  MatchPredictionResponse,
} from './types';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1';

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

  return request<MatchListResponse>(endpoint);
}

/**
 * Get upcoming matches (shortcut).
 */
export async function getUpcomingMatches(days: number = 7): Promise<MatchListResponse> {
  const fromDate = new Date().toISOString().split('T')[0];
  const toDate = new Date(Date.now() + days * 24 * 60 * 60 * 1000)
    .toISOString()
    .split('T')[0];

  return getMatches({
    from_date: fromDate,
    to_date: toDate,
    status: 'scheduled',
  });
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

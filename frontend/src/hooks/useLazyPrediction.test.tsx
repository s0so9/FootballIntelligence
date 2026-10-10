import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { useLazyPrediction } from './useLazyPrediction';
import { PredictionCacheProvider } from '../contexts/PredictionCacheContext';
import * as apiClient from '../api/client';
import type { MatchPredictionResponse } from '../api/types';

// Mock the API client
vi.mock('../api/client', () => ({
  getMatchPrediction: vi.fn(),
}));

describe('useLazyPrediction', () => {
  const mockMatchId = 'test-match-123';
  const mockPrediction: MatchPredictionResponse = {
    match_id: mockMatchId,
    home_win_probability: 0.45,
    draw_probability: 0.25,
    away_win_probability: 0.30,
    home_xg: 1.5,
    away_xg: 1.2,
    btts_probability: 0.62,
    predicted_score: '2-1',
    mensione_pick: {
      match_id: mockMatchId,
      pass_decision: false,
      timestamp: '2026-10-10T04:00:00Z',
      pipeline_version: '1.0',
      market: 'OVER_2_5',
      selection: 'Over 2.5 Goals',
      probability: 0.68,
      confidence: 0.75,
      fair_odds: 1.47,
      selector_reason: 'High scoring expected',
    },
    prediction_version_id: 'test-version-1',
    market_analysis: null,
    easy_match: null,
    home_form: null,
    away_form: null,
    head_to_head: null,
    shot_markets: null,
    is_development_data: false,
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('should handle aborted requests and allow retry', async () => {
    // Create a mock that simulates an aborted request
    let abortCount = 0;
    const mockGetMatchPrediction = vi.mocked(apiClient.getMatchPrediction);
    
    mockGetMatchPrediction.mockImplementation(() => {
      abortCount++;
      
      if (abortCount === 1) {
        // First call: simulate abort
        return Promise.reject(new DOMException('Request aborted', 'AbortError'));
      } else {
        // Second call: return successful prediction
        return Promise.resolve(mockPrediction);
      }
    });

    // First render - will be aborted
    const { result: result1, unmount: unmount1 } = renderHook(
      () => useLazyPrediction(mockMatchId),
      {
        wrapper: PredictionCacheProvider,
      }
    );

    // Verify initial loading state
    expect(result1.current.loading).toBe(true);
    expect(result1.current.prediction).toBe(null);
    expect(result1.current.error).toBe(null);

    // Unmount quickly (simulating React StrictMode or rapid navigation)
    unmount1();

    // Wait a bit for abort to process
    await new Promise(resolve => setTimeout(resolve, 50));

    // Second render - should retry successfully
    const { result: result2 } = renderHook(
      () => useLazyPrediction(mockMatchId),
      {
        wrapper: PredictionCacheProvider,
      }
    );

    // Should start loading again (not stuck)
    expect(result2.current.loading).toBe(true);

    // Wait for the successful prediction
    await waitFor(() => {
      expect(result2.current.loading).toBe(false);
    }, { timeout: 2000 });

    // Verify prediction loaded successfully
    expect(result2.current.prediction).toEqual(mockPrediction);
    expect(result2.current.error).toBe(null);
    
    // Verify getMatchPrediction was called twice (once aborted, once successful)
    expect(mockGetMatchPrediction).toHaveBeenCalledTimes(2);
  });

  it('should not get stuck in loading state after abort', async () => {
    const mockGetMatchPrediction = vi.mocked(apiClient.getMatchPrediction);
    
    // Simulate abort
    mockGetMatchPrediction.mockRejectedValue(
      new DOMException('Request aborted', 'AbortError')
    );

    // Render and immediately unmount
    const { result, unmount } = renderHook(
      () => useLazyPrediction(mockMatchId),
      {
        wrapper: PredictionCacheProvider,
      }
    );

    expect(result.current.loading).toBe(true);
    unmount();

    // Wait for abort to process
    await new Promise(resolve => setTimeout(resolve, 50));

    // Second render with successful response
    mockGetMatchPrediction.mockResolvedValue(mockPrediction);

    const { result: result2 } = renderHook(
      () => useLazyPrediction(mockMatchId),
      {
        wrapper: PredictionCacheProvider,
      }
    );

    // CRITICAL: Should NOT be permanently stuck at loading=false with no prediction
    // This was the bug: loading=true forever because inFlightRef wasn't cleared
    await waitFor(() => {
      const state = result2.current;
      // Either still loading OR has completed with prediction
      const isValidState = 
        (state.loading === true && state.prediction === null) ||
        (state.loading === false && state.prediction !== null);
      expect(isValidState).toBe(true);
    }, { timeout: 2000 });

    // Eventually should have prediction
    await waitFor(() => {
      expect(result2.current.prediction).toEqual(mockPrediction);
    }, { timeout: 2000 });
  });

  it('should handle API errors without getting stuck', async () => {
    const mockGetMatchPrediction = vi.mocked(apiClient.getMatchPrediction);
    const testError = new Error('Network error');
    
    mockGetMatchPrediction.mockRejectedValue(testError);

    const { result } = renderHook(
      () => useLazyPrediction(mockMatchId),
      {
        wrapper: PredictionCacheProvider,
      }
    );

    // Wait for error state
    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    }, { timeout: 2000 });

    // Should have error, not be stuck loading
    expect(result.current.error).toBeTruthy();
    expect(result.current.error?.message).toBe('Network error');
    expect(result.current.prediction).toBe(null);
  });
});

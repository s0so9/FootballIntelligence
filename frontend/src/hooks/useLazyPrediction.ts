import { useEffect, useRef } from 'react';
import { getMatchPrediction } from '../api/client';
import { usePredictionCache } from '../contexts/PredictionCacheContext';

/**
 * Hook for lazy-loading predictions on demand.
 * 
 * Automatically fetches prediction when component mounts if not already cached.
 * Prevents duplicate requests and handles component unmount cleanup.
 */
export function useLazyPrediction(matchId: string | null | undefined) {
  const cache = usePredictionCache();
  const abortControllerRef = useRef<AbortController | null>(null);
  const fetchStartedRef = useRef<Set<string>>(new Set());

  useEffect(() => {
    if (!matchId) return;

    // Check if already cached or loading
    const cached = cache.getPrediction(matchId);

    if (cached) {
      // If we have a prediction or error, don't fetch again
      if (cached.prediction || cached.error) {
        return;
      }
      
      // If loading but no prediction/error, this might be a stuck state from aborted request
      // Allow refetch in this case (handles React StrictMode double-mount scenario)
    }

    // Check if another component is already loading this prediction
    if (cache.isLoading(matchId)) {
      return;
    }

    // Create abort controller for cleanup
    const abortController = new AbortController();
    abortControllerRef.current = abortController;

    async function fetchPrediction() {
      if (!matchId) return;

      // Prevent duplicate fetches INSIDE async function (StrictMode-safe)
      if (fetchStartedRef.current.has(matchId)) {
        return;
      }
      fetchStartedRef.current.add(matchId);

      try {
        // Mark as loading to prevent other components from fetching
        cache.setLoading(matchId);

        console.log('[useLazyPrediction] Fetching prediction for match:', matchId);
        const prediction = await getMatchPrediction(matchId, abortController.signal);
        console.log('[useLazyPrediction] Prediction received:', prediction ? 'SUCCESS' : 'NULL');

        // Only update if not aborted
        if (!abortController.signal.aborted) {
          cache.setPrediction(matchId, prediction);
        }
      } catch (err) {
        console.log('[useLazyPrediction] Error occurred:', err);
        
        // Don't update cache if request was aborted (component unmounted)
        if (err instanceof DOMException && err.name === 'AbortError') {
          console.log('[useLazyPrediction] Request aborted - clearing loading state');
          cache.clearLoading(matchId);
          return;
        }

        // Check ApiError wrapped AbortError  
        if (err instanceof Error && err.message.includes('aborted')) {
          console.log('[useLazyPrediction] Request aborted (wrapped) - clearing loading state');
          cache.clearLoading(matchId);
          return;
        }

        // For all other errors (timeout, network, API errors), set error state
        console.log('[useLazyPrediction] Setting error state for match:', matchId);
        if (!abortController.signal.aborted) {
          cache.setError(
            matchId,
            err instanceof Error ? err : new Error('Failed to fetch prediction')
          );
        } else {
          // Aborted but didn't throw AbortError - still need to clear loading state
          cache.clearLoading(matchId);
        }
      } finally {
        // Always cleanup fetch tracking
        fetchStartedRef.current.delete(matchId);
      }
    }

    fetchPrediction();

    return () => {
      // Abort request on unmount
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
      // Cleanup happens in finally block of fetchPrediction
    };
  }, [matchId]); // Only depend on matchId - cache callbacks are stable now

  // Return cached state
  if (!matchId) {
    return { prediction: null, loading: false, error: null };
  }

  const cached = cache.getPrediction(matchId);
  return {
    prediction: cached?.prediction ?? null,
    loading: cached?.loading ?? false,
    error: cached?.error ?? null,
  };
}

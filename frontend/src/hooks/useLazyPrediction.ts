import { useEffect, useRef } from 'react';
import { getMatchPrediction } from '../api/client';
import { usePredictionCache } from '../contexts/PredictionCacheContext';

/**
 * Hook for lazy-loading predictions on demand.
 * 
 * Automatically fetches prediction when component mounts if not already cached.
 * Prevents duplicate requests and handles component unmount cleanup.
 * 
 * REACT STRICTMODE SAFE: Handles double-mount/abort scenarios correctly.
 */
export function useLazyPrediction(matchId: string | null | undefined) {
  const cache = usePredictionCache();
  const abortControllerRef = useRef<AbortController | null>(null);
  const isMountedRef = useRef<boolean>(true);

  useEffect(() => {
    isMountedRef.current = true;
    return () => {
      isMountedRef.current = false;
    };
  }, []);

  useEffect(() => {
    if (!matchId) return;

    // Check if already cached or loading
    const cached = cache.getPrediction(matchId);

    if (cached) {
      // If we have a prediction or error, don't fetch again
      if (cached.prediction || cached.error) {
        return;
      }
    }

    // Check if another component is already loading this prediction
    // Allow current component to wait for shared request
    if (cache.isLoading(matchId)) {
      console.log('[useLazyPrediction] Already loading, waiting for result:', matchId);
      return;
    }

    // Create abort controller for cleanup
    const abortController = new AbortController();
    abortControllerRef.current = abortController;

    async function fetchPrediction() {
      if (!matchId || !isMountedRef.current) return;

      try {
        // Mark as loading to prevent other components from fetching
        cache.setLoading(matchId);

        console.log('[useLazyPrediction] Fetching prediction for match:', matchId);
        const prediction = await getMatchPrediction(matchId, abortController.signal);
        console.log('[useLazyPrediction] Prediction received:', prediction ? 'SUCCESS' : 'NULL');

        // Only update if still mounted and not aborted
        if (isMountedRef.current && !abortController.signal.aborted) {
          cache.setPrediction(matchId, prediction);
        }
      } catch (err) {
        console.log('[useLazyPrediction] Error occurred:', err);
        
        // Don't update cache if request was aborted (component unmounted)
        if (err instanceof DOMException && err.name === 'AbortError') {
          console.log('[useLazyPrediction] Request aborted - clearing loading state');
          if (isMountedRef.current) {
            cache.clearLoading(matchId);
          }
          return;
        }

        // Check ApiError wrapped AbortError  
        if (err instanceof Error && err.message.includes('aborted')) {
          console.log('[useLazyPrediction] Request aborted (wrapped) - clearing loading state');
          if (isMountedRef.current) {
            cache.clearLoading(matchId);
          }
          return;
        }

        // For all other errors (timeout, network, API errors), set error state
        console.log('[useLazyPrediction] Setting error state for match:', matchId);
        if (isMountedRef.current && !abortController.signal.aborted) {
          cache.setError(
            matchId,
            err instanceof Error ? err : new Error('Failed to fetch prediction')
          );
        } else {
          // Aborted but didn't throw AbortError - still need to clear loading state
          if (isMountedRef.current) {
            cache.clearLoading(matchId);
          }
        }
      }
    }

    fetchPrediction();

    return () => {
      // Abort request on unmount
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
    };
  }, [matchId]); // cache methods are stable, no need to include

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

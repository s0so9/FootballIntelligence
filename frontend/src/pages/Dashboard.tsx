import { useState, useEffect } from 'react';
import { getUpcomingMatches, getMatchPrediction, getLiveMatches } from '../api/client';
import type { MatchResponse, MatchPredictionResponse } from '../api/types';
import MensionePickCard from '../components/predictions/MensionePickCard';
import LiveMatchesPanel from '../components/dashboard/LiveMatchesPanel';
import CombinePanel from '../components/combine/CombinePanel';
import type { LiveMatch } from '../components/dashboard/LiveMatchesPanel';
import { useFavorites } from '../hooks/useFavorites';
import { useCombine } from '../hooks/useCombine';
import './Dashboard.css';

interface MensionePickData {
  match: MatchResponse;
  prediction: MatchPredictionResponse;
}

/**
 * Parse market field to extract market name and outcome for display
 * Handles both BestTip (market + selection) and null/undefined cases
 */
function parsePickMarket(market: string | undefined, selection: string | undefined): { marketName: string; outcome: string } {
  // Handle PASS or missing pick
  if (!market || !selection) {
    return {
      marketName: 'PASS',
      outcome: 'Seçim yapılmadı',
    };
  }

  // Use the selection as the outcome directly (it's already human-readable from backend)
  // Parse market to get the market name in Turkish
  
  if (market.startsWith('HOME_WIN') || market.startsWith('DRAW') || market.startsWith('AWAY_WIN') || 
      market === 'HOME' || market === 'DRAW' || market === 'AWAY') {
    return {
      marketName: 'Maç Sonucu',
      outcome: selection,
    };
  }
  
  if (market.startsWith('BTTS_')) {
    return {
      marketName: 'Karşılıklı Gol',
      outcome: selection,
    };
  }
  
  if (market.startsWith('OVER_') || market.startsWith('UNDER_')) {
    const lineMatch = market.match(/[0-9.]+/);
    const line = lineMatch ? lineMatch[0] : '?';
    return {
      marketName: `Alt/Üst ${line} Gol`,
      outcome: selection,
    };
  }
  
  // Default case - use market and selection as-is
  return {
    marketName: market,
    outcome: selection,
  };
}

/**
 * Execute promises with bounded concurrency.
 * Limits the number of simultaneously executing promises.
 * 
 * @param tasks - Array of promise-returning functions
 * @param concurrencyLimit - Maximum number of concurrent executions
 * @returns Promise that resolves when all tasks complete
 */
async function executeWithConcurrency<T>(
  tasks: (() => Promise<T>)[],
  concurrencyLimit: number
): Promise<PromiseSettledResult<T>[]> {
  const results: PromiseSettledResult<T>[] = [];
  const executing: Promise<void>[] = [];
  
  for (let i = 0; i < tasks.length; i++) {
    const task = tasks[i];
    
    const promise = task()
      .then(value => {
        results[i] = { status: 'fulfilled', value };
      })
      .catch(reason => {
        results[i] = { status: 'rejected', reason };
      });
    
    executing.push(promise);
    
    if (executing.length >= concurrencyLimit) {
      await Promise.race(executing);
      executing.splice(0, executing.findIndex(p => p === promise) + 1);
    }
  }
  
  await Promise.all(executing);
  return results;
}

export function Dashboard() {
  const [mensionePicksData, setMensionePicksData] = useState<MensionePickData[]>([]);
  const [liveMatches, setLiveMatches] = useState<LiveMatch[]>([]);
  const [liveMatchesLoading, setLiveMatchesLoading] = useState(true);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  
  const { isFavorite, toggleFavorite } = useFavorites();
  const { isInCombine, toggleCombine, combineItems, removeFromCombine, clearCombine } = useCombine();

  useEffect(() => {
    let isMounted = true;
    const abortController = new AbortController();

    async function fetchDashboardData() {
      try {
        setLoading(true);
        setError(null);

        console.log('[Dashboard] Fetching upcoming matches...');

        // Fetch upcoming matches (7 days)
        const matchesResponse = await getUpcomingMatches(7);
        
        if (!isMounted) return;
        
        const matches = matchesResponse.matches;
        console.log(`[Dashboard] Found ${matches.length} matches, fetching predictions with bounded concurrency (max 6 concurrent)...`);

        // Create prediction fetch tasks (lazy - not executed yet)
        const predictionTasks = matches.map(match => 
          () => getMatchPrediction(match.id, abortController.signal)
            .then(prediction => ({ match, prediction, success: true as const }))
            .catch(err => {
              // Only log if not aborted
              if (!abortController.signal.aborted) {
                console.warn(`Failed to fetch prediction for match ${match.id}:`, err);
              }
              return { match, error: err, success: false as const };
            })
        );

        // Execute with bounded concurrency (max 6 simultaneous requests)
        const results = await executeWithConcurrency(predictionTasks, 6);
        
        if (!isMounted) return;

        // Filter for successful predictions with mensione_pick (not PASS)
        const picksData: MensionePickData[] = [];
        let failedCount = 0;
        let insufficientDataCount = 0;

        for (const result of results) {
          if (result.status === 'fulfilled' && result.value.success) {
            const { match, prediction } = result.value;
            
            if (prediction.mensione_pick && !prediction.mensione_pick.pass_decision) {
              picksData.push({ match, prediction });
            }
          } else {
            failedCount++;
            // Check for insufficient data errors
            if (result.status === 'fulfilled' && !result.value.success) {
              const error = result.value.error;
              if (error instanceof Error && error.message.includes('Insufficient data')) {
                insufficientDataCount++;
              }
            }
          }
        }

        console.log(`[Dashboard] Successfully fetched ${picksData.length} picks (${failedCount} failed, ${insufficientDataCount} insufficient data)`);
        
        if (isMounted) {
          setMensionePicksData(picksData);
        }
      } catch (err) {
        if (isMounted) {
          console.error('[Dashboard] Error fetching dashboard data:', err);
          setError(err instanceof Error ? err.message : 'Veriler yüklenirken bir hata oluştu');
        }
      } finally {
        if (isMounted) {
          setLoading(false);
        }
      }
    }

    fetchDashboardData();

    return () => {
      isMounted = false;
      abortController.abort();
    };
  }, []);

  // Fetch live matches and poll every 20 seconds
  useEffect(() => {
    async function fetchLiveMatches() {
      try {
        const response = await getLiveMatches();
        
        // Map backend LiveMatchResponse to frontend LiveMatch format
        const mappedMatches: LiveMatch[] = response.matches.map(match => ({
          matchId: match.match_id,
          homeTeam: match.home_team,
          awayTeam: match.away_team,
          score: {
            home: match.home_score,
            away: match.away_score,
          },
          minute: match.minute ?? 0,
          status: match.status as 'live' | 'ht' | 'ft', // Map MatchStatus to component status
        }));
        
        setLiveMatches(mappedMatches);
        setLiveMatchesLoading(false);
      } catch (err) {
        console.error('Failed to fetch live matches:', err);
        setLiveMatchesLoading(false);
        // Don't set main error state - live matches are not critical
      }
    }

    // Initial fetch
    fetchLiveMatches();

    // Poll every 20 seconds
    const intervalId = setInterval(fetchLiveMatches, 20000);

    // Cleanup on unmount
    return () => {
      clearInterval(intervalId);
    };
  }, []);

  if (loading) {
    return (
      <div className="dashboard">
        <div className="dashboard-header">
          <h1 className="dashboard-title">TUTAR X PICKS</h1>
          <p className="dashboard-subtitle">Bugünün yapay zeka destekli maç seçimleri</p>
        </div>
        <div className="dashboard-layout">
          <main className="dashboard-main">
            <div className="loading-state">
              <div className="loading-spinner"></div>
              <p>Veriler yükleniyor...</p>
            </div>
          </main>
          <aside className="dashboard-live-panel">
            <LiveMatchesPanel liveMatches={[]} isLoading={true} />
          </aside>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="dashboard">
        <div className="dashboard-header">
          <h1 className="dashboard-title">TUTAR X PICKS</h1>
          <p className="dashboard-subtitle">Bugünün yapay zeka destekli maç seçimleri</p>
        </div>
        <div className="error-state">
          <p className="error-message">❌ {error}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="dashboard">
      <div className="dashboard-header">
        <h1 className="dashboard-title">TUTAR X PICKS</h1>
        <p className="dashboard-subtitle">Bugünün yapay zeka destekli maç seçimleri</p>
        
        <div className="dashboard-filters">
          <button className="filter-btn filter-btn--active">Tümü</button>
          <button className="filter-btn">Yaklaşan</button>
          <button className="filter-btn">Tamamlanan</button>
        </div>
      </div>

      <div className="dashboard-layout">
        {/* Main area - TUTAR X picks */}
        <main className="dashboard-main">
          {mensionePicksData.length === 0 ? (
            <div className="empty-state">
              <div className="empty-icon">⚽</div>
              <p className="empty-title">Şu anda TUTAR X seçimi yok</p>
              <p className="empty-description">
                Yaklaşan maçlar için yeterli veri mevcut olmayabilir veya modeller tarafından 
                güvenilir tahmin üretilememiş olabilir. Lütfen daha sonra tekrar kontrol edin.
              </p>
            </div>
          ) : (
            <div className="mensione-picks-grid">
              {mensionePicksData.map(({ match, prediction }) => {
                const pick = prediction.mensione_pick!; // Already filtered for non-null
                const { marketName, outcome } = parsePickMarket(pick.market, pick.selection);
                
                return (
                  <MensionePickCard
                    key={match.id}
                    homeTeam={match.home_team_id}
                    awayTeam={match.away_team_id}
                    marketName={marketName}
                    outcome={outcome}
                    confidence={pick.confidence ?? 0}
                    realOdds={pick.bookmaker_odds ?? 0} // Real bookmaker odds (or 0 if null)
                    isFavorite={isFavorite(match.id)}
                    onToggleFavorite={() => toggleFavorite(match.id)}
                    inCombine={isInCombine(match.id)}
                    onToggleCombine={() => {
                      // For combine calculation: use ONLY real market odds
                      // Never use confidence, fair odds, or fabricated values
                      toggleCombine({
                        matchId: match.id,
                        marketName,
                        outcome,
                        marketOdds: pick.bookmaker_odds !== undefined ? pick.bookmaker_odds : null,  // null if unavailable
                        confidence: pick.confidence ?? 0,
                        homeTeam: match.home_team_id,
                        awayTeam: match.away_team_id,
                      });
                    }}
                    // === Backend fields for testing/preview ===
                    predictedScore={prediction.predicted_score ?? 'N/A'}
                    homeXg={prediction.home_xg}
                    awayXg={prediction.away_xg}
                    bttsProbability={prediction.btts_probability}
                    homeWinProbability={prediction.home_win_probability}
                    drawProbability={prediction.draw_probability}
                    awayWinProbability={prediction.away_win_probability}
                    pickProbability={pick.probability ?? 0}
                    reasoningFactors={pick.selector_reason ? [pick.selector_reason] : []}
                    scoreDistributionTop5={[]}
                    fairOdds={pick.fair_odds ?? 0}
                    marketOdds={pick.bookmaker_odds !== undefined ? pick.bookmaker_odds : null}
                    predictionVersionId={prediction.prediction_version_id}
                  />
                );
              })}
            </div>
          )}
        </main>
        
        {/* Right panel - Live matches (desktop only) */}
        <aside className="dashboard-live-panel">
          <LiveMatchesPanel liveMatches={liveMatches} isLoading={liveMatchesLoading} />
        </aside>
      </div>
      
      {/* Combine Panel - Bottom Right Fixed */}
      <CombinePanel
        combineItems={combineItems}
        onRemoveItem={removeFromCombine}
        onClearAll={clearCombine}
      />
    </div>
  );
}

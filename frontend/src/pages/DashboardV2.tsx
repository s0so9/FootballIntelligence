/**
 * TUTAR X Intelligence Dashboard
 * Redesigned with new design system - preserving all functionality
 * Now includes match center integration
 */

import { useState, useEffect, useMemo } from 'react';
import { getUpcomingMatches, getMatchPrediction, getMatches, getCompetitions, formatDateForAPI } from '../api/client';
import type { MatchResponse, MatchPredictionResponse, CompetitionResponse } from '../api/types';
import { normalizeMatch } from '../utils/matchNormalizer';
import MensionePickCard from '../components/predictions/MensionePickCard';
import CombinePanel from '../components/combine/CombinePanel';
import { EmptyState, Skeleton } from '../components/ui';
import { DateStrip, LeagueGroup } from '../components/matches';
import type { MatchRowData } from '../components/matches';
import { useFavorites } from '../hooks/useFavorites';
import { useCombine } from '../hooks/useCombine';
import { usePredictionCache } from '../contexts/PredictionCacheContext';
import { isPopularCompetitionById } from '../utils/popularCompetitions';
import './DashboardV2.css';

interface PickData {
  match: MatchResponse;
  prediction: MatchPredictionResponse;
}

/**
 * Parse market field to extract market name and outcome for display
 */
function parsePickMarket(market: string | undefined, selection: string | undefined): { marketName: string; outcome: string } {
  if (!market || !selection) {
    return {
      marketName: 'PASS',
      outcome: 'Seçim yapılmadı',
    };
  }

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
  
  return {
    marketName: market,
    outcome: selection,
  };
}

/**
 * Execute promises with bounded concurrency
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

export function DashboardV2() {
  const [picksData, setPicksData] = useState<PickData[]>([]);
  const [loading, setLoading] = useState(true);
  const [predictionsLoading, setPredictionsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  // Match center state
  const [selectedDate, setSelectedDate] = useState(() => {
    const today = new Date();
    return formatDateForAPI(today);
  });
  const [competitions, setCompetitions] = useState<CompetitionResponse[]>([]);
  const [matches, setMatches] = useState<MatchResponse[]>([]);
  const [matchesLoading, setMatchesLoading] = useState(true);
  const [matchesError, setMatchesError] = useState<string | null>(null);
  
  const { isFavorite, toggleFavorite } = useFavorites();
  const { isInCombine, toggleCombine, combineItems, removeFromCombine, clearCombine } = useCombine();
  const predictionCache = usePredictionCache();

  useEffect(() => {
    let isMounted = true;
    const abortController = new AbortController();

    async function fetchDashboardData() {
      try {
        setLoading(true);
        setError(null);

        // Fetch upcoming matches (today only for faster load)
        const matchesResponse = await getUpcomingMatches(1);
        
        if (!isMounted) return;
        
        const allMatches = matchesResponse.matches;
        
        // IMMEDIATELY render page
        setLoading(false);
        
        // Start background prediction loading
        loadPredictions(allMatches, abortController, isMounted);
        
      } catch (err) {
        if (isMounted) {
          console.error('[DashboardV2] Error fetching data:', err);
          setError(err instanceof Error ? err.message : 'Veriler yüklenirken bir hata oluştu');
          setLoading(false);
          setPredictionsLoading(false);
        }
      }
    }

    async function loadPredictions(
      allMatches: MatchResponse[],
      abortCtrl: AbortController,
      mounted: boolean
    ) {
      if (!mounted || allMatches.length === 0) return;
      
      const now = new Date();
      const next24Hours = new Date(now.getTime() + 24 * 60 * 60 * 1000);
      
      // Select candidate matches from popular competitions
      const priorityCompetitions = new Set<string>();
      allMatches.forEach(match => {
        if (match.competition_id && isPopularCompetitionById(match.competition_id)) {
          priorityCompetitions.add(match.competition_id);
        }
      });
      
      const candidateMatches = allMatches
        .filter(match => {
          if (match.status !== 'SCHEDULED') return false;
          if (!match.competition_id || !priorityCompetitions.has(match.competition_id)) return false;
          const matchDate = new Date(match.scheduled_at);
          return matchDate >= now && matchDate <= next24Hours;
        })
        .sort((a, b) => new Date(a.scheduled_at).getTime() - new Date(b.scheduled_at).getTime())
        .slice(0, 5); // Max 5 predictions
      
      if (candidateMatches.length === 0) {
        setPredictionsLoading(false);
        return;
      }
      
      // Filter out cached
      const matchesToPredict = candidateMatches.filter(match => !predictionCache.has(match.id));
      
      if (matchesToPredict.length === 0) {
        setPredictionsLoading(false);
        return;
      }
      
      setPredictionsLoading(true);
      
      // Mark as loading
      matchesToPredict.forEach(match => predictionCache.setLoading(match.id));
      
      // Create prediction tasks
      const predictionTasks = matchesToPredict.map(match => 
        () => getMatchPrediction(match.id, abortCtrl.signal)
          .then(prediction => ({ match, prediction, success: true as const }))
          .catch(err => {
            const isAborted = err instanceof DOMException && err.name === 'AbortError';
            if (!isAborted) {
              console.warn(`Failed to fetch prediction for match ${match.id}:`, err);
            }
            return { match, error: err, success: false as const, aborted: isAborted };
          })
      );

      // Execute with bounded concurrency
      const results = await executeWithConcurrency(predictionTasks, 3);
      
      if (!mounted) return;

      // Process results
      const newPicksData: PickData[] = [];

      for (const result of results) {
        if (result.status === 'fulfilled' && result.value.success) {
          const { match, prediction } = result.value;
          
          // Cache the prediction
          predictionCache.setPrediction(match.id, prediction);
          
          // Only show picks with actual selections (not PASS)
          if (prediction.mensione_pick && !prediction.mensione_pick.pass_decision) {
            newPicksData.push({ match, prediction });
          }
        } else if (result.status === 'fulfilled' && !result.value.success && !result.value.aborted) {
          const error = result.value.error;
          predictionCache.setError(result.value.match.id, error instanceof Error ? error : new Error('Unknown error'));
        }
      }
      
      if (mounted) {
        setPicksData(prev => [...prev, ...newPicksData]);
        setPredictionsLoading(false);
      }
    }

    fetchDashboardData();

    return () => {
      isMounted = false;
      abortController.abort();
    };
  }, [predictionCache]);

  // Load matches for match center section
  useEffect(() => {
    let isMounted = true;

    async function loadMatches() {
      try {
        setMatchesLoading(true);
        setMatchesError(null);

        // Load competitions and matches in parallel
        const [compsResponse, matchesResponse] = await Promise.all([
          getCompetitions(),
          getMatches({
            from_date: selectedDate,
            to_date: selectedDate,
            limit: 200,
          }),
        ]);

        if (!isMounted) return;

        setCompetitions(compsResponse.competitions);
        setMatches(matchesResponse.matches);
      } catch (err) {
        if (!isMounted) return;
        console.error('[DashboardV2] Error loading matches:', err);
        setMatchesError(err instanceof Error ? err.message : 'Maçlar yüklenirken bir hata oluştu');
      } finally {
        if (isMounted) {
          setMatchesLoading(false);
        }
      }
    }

    loadMatches();

    return () => {
      isMounted = false;
    };
  }, [selectedDate]);

  // Group matches by competition
  const matchesByCompetition = useMemo(() => {
    const grouped = new Map<string, { name: string; matches: MatchRowData[] }>();

    matches.forEach((match) => {
      const compId = match.competition_id;
      const compName = match.competition_name || competitions.find(c => c.id === compId)?.name || compId;

      if (!grouped.has(compId)) {
        grouped.set(compId, { name: compName, matches: [] });
      }

      const matchData: MatchRowData = {
        id: match.id,
        homeTeam: {
          name: match.home_team?.name || 'Unknown',
          logoUrl: match.home_team?.logo_url,
          code: match.home_team?.code,
        },
        awayTeam: {
          name: match.away_team?.name || 'Unknown',
          logoUrl: match.away_team?.logo_url,
          code: match.away_team?.code,
        },
        scheduledAt: match.scheduled_at,
        status: match.status,
        homeScore: match.home_score,
        awayScore: match.away_score,
        minute: match.minute,
        competitionName: compName,
      };

      grouped.get(compId)!.matches.push(matchData);
    });

    // Sort groups by match count (descending)
    return Array.from(grouped.entries())
      .map(([id, data]) => ({ id, ...data }))
      .sort((a, b) => b.matches.length - a.matches.length);
  }, [matches, competitions]);

  const totalMatches = matches.length;

  if (loading) {
    return (
      <div className="tx-dashboard">
        <div className="tx-dashboard__header">
          <div className="tx-dashboard__badge">TUTAR X INTELLIGENCE</div>
          <h1 className="tx-dashboard__title">Bugünün Seçimleri</h1>
          <p className="tx-dashboard__subtitle">
            Model bazlı veri analizi ile oluşturulan maç tahminleri
          </p>
        </div>

        <div className="tx-dashboard__loading">
          <div className="tx-dashboard__loading-spinner"></div>
          <p className="tx-dashboard__loading-text">Veriler yükleniyor...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="tx-dashboard">
        <div className="tx-dashboard__header">
          <div className="tx-dashboard__badge">TUTAR X INTELLIGENCE</div>
          <h1 className="tx-dashboard__title">Bugünün Seçimleri</h1>
          <p className="tx-dashboard__subtitle">
            Model bazlı veri analizi ile oluşturulan maç tahminleri
          </p>
        </div>

        <div className="tx-dashboard__error">
          <p className="tx-dashboard__error-message">❌ {error}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="tx-dashboard">
      {/* Header */}
      <div className="tx-dashboard__header">
        <div className="tx-dashboard__badge">TUTAR X INTELLIGENCE</div>
        <h1 className="tx-dashboard__title">Bugünün Seçimleri</h1>
        <p className="tx-dashboard__subtitle">
          Model bazlı veri analizi ile oluşturulan maç tahminleri
        </p>
        
        {predictionsLoading && (
          <div className="tx-dashboard__status">
            <span className="tx-dashboard__status-dot"></span>
            Tahminler hazırlanıyor
          </div>
        )}
      </div>

      {/* Content */}
      {predictionsLoading && picksData.length === 0 ? (
        <div className="tx-dashboard__loading">
          <div className="tx-dashboard__loading-spinner"></div>
          <p className="tx-dashboard__loading-text">TUTAR X seçimleri hazırlanıyor...</p>
          <p className="tx-dashboard__loading-subtext">Popüler liglerdeki maçlar için tahminler oluşturuluyor</p>
        </div>
      ) : picksData.length === 0 ? (
        <div className="tx-dashboard__empty">
          <div className="tx-dashboard__empty-icon">⚽</div>
          <p className="tx-dashboard__empty-title">Şu Anda Seçim Yok</p>
          <p className="tx-dashboard__empty-description">
            Yaklaşan maçlar için yeterli veri mevcut olmayabilir veya modeller tarafından 
            güvenilir tahmin üretilememiş olabilir. Lütfen daha sonra tekrar kontrol edin.
          </p>
        </div>
      ) : (
        <div className="tx-dashboard__picks">
          {picksData.map(({ match, prediction }) => {
            const normalizedMatch = normalizeMatch(match);
            const pick = prediction.mensione_pick!;
            const { marketName, outcome } = parsePickMarket(pick.market, pick.selection);
            
            return (
              <MensionePickCard
                key={match.id}
                homeTeam={normalizedMatch.homeTeam.name}
                awayTeam={normalizedMatch.awayTeam.name}
                homeTeamLogoUrl={normalizedMatch.homeTeam.logoUrl || undefined}
                awayTeamLogoUrl={normalizedMatch.awayTeam.logoUrl || undefined}
                homeTeamCode={normalizedMatch.homeTeam.code || undefined}
                awayTeamCode={normalizedMatch.awayTeam.code || undefined}
                marketName={marketName}
                outcome={outcome}
                confidence={pick.confidence ?? 0}
                realOdds={pick.bookmaker_odds ?? 0}
                isFavorite={isFavorite(match.id)}
                onToggleFavorite={() => toggleFavorite(match.id)}
                inCombine={isInCombine(match.id)}
                onToggleCombine={() => {
                  toggleCombine({
                    matchId: match.id,
                    marketName,
                    outcome,
                    marketOdds: pick.bookmaker_odds !== undefined ? pick.bookmaker_odds : null,
                    confidence: pick.confidence ?? 0,
                    homeTeam: normalizedMatch.homeTeam.name,
                    awayTeam: normalizedMatch.awayTeam.name,
                  });
                }}
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
      
      {/* Match Center Section */}
      <div className="tx-dashboard__matches-section">
        <div className="tx-dashboard__section-header">
          <div className="tx-dashboard__section-title">
            <div className="tx-dashboard__section-badge">FUTBOLUN KALBİNDE</div>
            <h2 className="tx-dashboard__section-heading">Tüm Maçlar</h2>
            <p className="tx-dashboard__section-subtitle">
              Karşılaşmalar, skorlar ve veri odaklı analizler tek yerde.
            </p>
          </div>
          
          {!matchesLoading && (
            <div className="tx-dashboard__matches-stats">
              <div className="tx-dashboard__stat-item">
                <span className="tx-dashboard__stat-value tabular-nums">{totalMatches}</span>
                <span className="tx-dashboard__stat-label">Maç</span>
              </div>
              <div className="tx-dashboard__stat-item">
                <span className="tx-dashboard__stat-value tabular-nums">{matchesByCompetition.length}</span>
                <span className="tx-dashboard__stat-label">Lig</span>
              </div>
            </div>
          )}
        </div>

        {/* Date Strip */}
        <div className="tx-dashboard__date-filter">
          <DateStrip
            selectedDate={selectedDate}
            onDateChange={setSelectedDate}
          />
        </div>

        {/* Matches Content */}
        <div className="tx-dashboard__matches-content">
          {matchesLoading ? (
            <div className="tx-dashboard__matches-loading">
              <Skeleton width="100%" height={400} />
            </div>
          ) : matchesError ? (
            <div className="tx-dashboard__matches-error">
              <p className="tx-dashboard__error-message">❌ {matchesError}</p>
              <button 
                className="tx-dashboard__retry-button"
                onClick={() => {
                  setMatchesError(null);
                  setSelectedDate(formatDateForAPI(new Date()));
                }}
              >
                Tekrar Dene
              </button>
            </div>
          ) : totalMatches === 0 ? (
            <EmptyState
              icon="⚽"
              title="Maç Bulunamadı"
              description="Seçilen tarih için hiç maç bulunmuyor. Başka bir tarih seçin."
            />
          ) : (
            <div className="tx-dashboard__matches-groups">
              {matchesByCompetition.map((group) => (
                <LeagueGroup
                  key={group.id}
                  leagueName={group.name}
                  matches={group.matches}
                  defaultExpanded={true}
                />
              ))}
            </div>
          )}
        </div>
      </div>
      
      {/* Combine Panel */}
      <CombinePanel
        combineItems={combineItems}
        onRemoveItem={removeFromCombine}
        onClearAll={clearCombine}
      />
    </div>
  );
}

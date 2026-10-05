import { useState, useEffect } from 'react';
import { getUpcomingMatches, getMatchPrediction } from '../api/client';
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
 * Parse pick_market to extract market name and outcome
 */
function parsePickMarket(pickMarket: string): { marketName: string; outcome: string } {
  // Examples: "HOME", "OVER 2.5", "BTTS YES", "HOME OVER 1.5"
  const parts = pickMarket.trim().split(/\s+/);
  
  if (parts.length === 1) {
    // Single word like "HOME", "DRAW", "AWAY"
    const outcomes: Record<string, string> = {
      'HOME': 'Ev Sahibi',
      'DRAW': 'Beraberlik',
      'AWAY': 'Deplasman',
    };
    return {
      marketName: 'Maç Sonucu',
      outcome: outcomes[parts[0]] || parts[0],
    };
  }
  
  if (parts[0] === 'BTTS') {
    return {
      marketName: 'Karşılıklı Gol',
      outcome: parts[1] === 'YES' ? 'Evet' : 'Hayır',
    };
  }
  
  if (parts[0] === 'OVER' || parts[0] === 'UNDER') {
    const line = parts[1];
    return {
      marketName: `Alt/Üst ${line} Gol`,
      outcome: parts[0] === 'OVER' ? 'Üst' : 'Alt',
    };
  }
  
  // Fallback: use pick_market as-is
  return {
    marketName: pickMarket,
    outcome: '',
  };
}

export function Dashboard() {
  const [mensionePicksData, setMensionePicksData] = useState<MensionePickData[]>([]);
  const [liveMatches, setLiveMatches] = useState<LiveMatch[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  
  const { isFavorite, toggleFavorite } = useFavorites();
  const { isInCombine, toggleCombine, combineItems, removeFromCombine, clearCombine } = useCombine();

  useEffect(() => {
    async function fetchDashboardData() {
      try {
        setLoading(true);
        setError(null);

        // Fetch upcoming matches (7 days)
        const matchesResponse = await getUpcomingMatches(7);
        const matches = matchesResponse.matches;

        // Fetch predictions for each match and filter for mensione_pick
        const picksData: MensionePickData[] = [];
        
        for (const match of matches) {
          try {
            const prediction = await getMatchPrediction(match.id);
            
            if (prediction.mensione_pick) {
              picksData.push({
                match,
                prediction, // Store full prediction, not just pick
              });
            }
          } catch (err) {
            // Skip match if prediction fails
            console.warn(`Failed to fetch prediction for match ${match.id}:`, err);
          }
        }

        setMensionePicksData(picksData);

        // TODO: Fetch live matches when backend live intelligence available
        // For now, leave empty (will show empty state)
        setLiveMatches([]);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Veriler yüklenirken bir hata oluştu');
      } finally {
        setLoading(false);
      }
    }

    fetchDashboardData();
  }, []);

  if (loading) {
    return (
      <div className="dashboard">
        <div className="dashboard-header">
          <h1 className="dashboard-title">MENSIONE PICKS</h1>
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
          <h1 className="dashboard-title">MENSIONE PICKS</h1>
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
        <h1 className="dashboard-title">MENSIONE PICKS</h1>
        <p className="dashboard-subtitle">Bugünün yapay zeka destekli maç seçimleri</p>
        
        <div className="dashboard-filters">
          <button className="filter-btn filter-btn--active">Tümü</button>
          <button className="filter-btn">Yaklaşan</button>
          <button className="filter-btn">Tamamlanan</button>
        </div>
      </div>

      <div className="dashboard-layout">
        {/* Main area - MENSIONE picks */}
        <main className="dashboard-main">
          {mensionePicksData.length === 0 ? (
            <div className="empty-state">
              <div className="empty-icon">⚽</div>
              <p className="empty-title">Şu anda MENSIONE seçimi yok</p>
              <p className="empty-description">
                Yeni tahmin önerileri modeller tarafından analiz edildiğinde burada görünecektir.
              </p>
            </div>
          ) : (
            <div className="mensione-picks-grid">
              {mensionePicksData.map(({ match, prediction }) => {
                const pick = prediction.mensione_pick!; // Already filtered for non-null
                const { marketName, outcome } = parsePickMarket(pick.pick_market);
                
                return (
                  <MensionePickCard
                    key={match.id}
                    homeTeam={match.home_team_id}
                    awayTeam={match.away_team_id}
                    marketName={marketName}
                    outcome={outcome}
                    confidence={pick.confidence_score}
                    realOdds={pick.market_odds ?? 0} // Real bookmaker odds (or 0 if null)
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
                        marketOdds: pick.market_odds,  // null if unavailable
                        confidence: pick.confidence_score,
                        homeTeam: match.home_team_id,
                        awayTeam: match.away_team_id,
                      });
                    }}
                    // === Backend fields for testing/preview ===
                    predictedScore={pick.predicted_score}
                    homeXg={prediction.home_xg}
                    awayXg={prediction.away_xg}
                    bttsProbability={prediction.btts_probability}
                    homeWinProbability={prediction.home_win_probability}
                    drawProbability={prediction.draw_probability}
                    awayWinProbability={prediction.away_win_probability}
                    pickProbability={pick.pick_probability}
                    reasoningFactors={pick.reasoning_factors}
                    scoreDistributionTop5={pick.score_distribution_top5}
                    fairOdds={pick.fair_odds}
                    marketOdds={pick.market_odds}
                    predictionVersionId={prediction.prediction_version_id}
                  />
                );
              })}
            </div>
          )}
        </main>
        
        {/* Right panel - Live matches (desktop only) */}
        <aside className="dashboard-live-panel">
          <LiveMatchesPanel liveMatches={liveMatches} isLoading={false} />
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

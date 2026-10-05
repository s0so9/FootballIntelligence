import { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { getMatch, getMatchPrediction } from '../api';
import type { MatchResponse, MatchPredictionResponse } from '../api/types';
import { 
  formatTeamName, 
  formatCompetitionName, 
  formatMatchDateTime,
  formatMatchStatus 
} from '../utils/formatters';
import { useFavorites } from '../hooks/useFavorites';
import { useCombine } from '../hooks/useCombine';
import GeneralAnalysis from '../components/match/GeneralAnalysis';
import FirstHalfAnalysis from '../components/match/FirstHalfAnalysis';
import FullMatchAnalysis from '../components/match/FullMatchAnalysis';
import StatisticsComparison from '../components/match/StatisticsComparison';
import FormDisplay from '../components/match/FormDisplay';
import HeadToHead from '../components/match/HeadToHead';
import CombineDrawer from '../components/combine/CombineDrawer';
import './MatchDetail.css';

type TabType = 'general' | 'first-half' | 'full-match';

export function MatchDetail() {
  const { id } = useParams<{ id: string }>();
  const [match, setMatch] = useState<MatchResponse | null>(null);
  const [prediction, setPrediction] = useState<MatchPredictionResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isDevelopmentData, setIsDevelopmentData] = useState(false);
  const [activeTab, setActiveTab] = useState<TabType>('general');
  
  // Favorites and combine state
  const { isFavorite, toggleFavorite } = useFavorites();
  const { combineItems, isInCombine, toggleCombine, removeFromCombine, clearCombine } = useCombine();

  useEffect(() => {
    async function fetchMatchData() {
      if (!id) {
        setError('Geçersiz maç ID');
        setLoading(false);
        return;
      }

      try {
        setLoading(true);
        setError(null);

        // Fetch match details
        const matchResponse = await getMatch(id);
        setMatch(matchResponse.match);
        setIsDevelopmentData(matchResponse.is_development_data);

        // Fetch prediction if match is scheduled
        if (matchResponse.match.status === 'scheduled') {
          try {
            const predictionResponse = await getMatchPrediction(id);
            setPrediction(predictionResponse);
          } catch (predErr) {
            // Prediction might not be available - this is okay
            console.warn('Prediction not available:', predErr);
            setPrediction(null);
          }
        }
      } catch (err) {
        if (err instanceof Error && err.message.includes('404')) {
          setError('Maç bulunamadı');
        } else {
          setError(err instanceof Error ? err.message : 'Maç verileri yüklenirken bir hata oluştu');
        }
      } finally {
        setLoading(false);
      }
    }

    fetchMatchData();
  }, [id]);

  if (loading) {
    return (
      <div className="page-container">
        <div className="loading-state">
          <div className="loading-spinner"></div>
          <p>Maç detayları yükleniyor...</p>
        </div>
      </div>
    );
  }

  if (error || !match) {
    return (
      <div className="page-container">
        <div className="error-state">
          <p className="error-message">{error || 'Maç bulunamadı'}</p>
          <Link to="/matches" className="back-link">← Maçlara Dön</Link>
        </div>
      </div>
    );
  }

  const dateTime = formatMatchDateTime(match.scheduled_at);
  const homeTeam = formatTeamName(match.home_team_id);
  const awayTeam = formatTeamName(match.away_team_id);
  const competition = formatCompetitionName(match.competition_id);

  // Handle favorite toggle
  const handleToggleFavorite = () => {
    if (match) {
      toggleFavorite(match.id);
    }
  };

  // Handle combine toggle
  const handleToggleCombine = (matchId: string, marketName: string, confidence: number, odds: number) => {
    if (!match) return;
    
    toggleCombine({
      matchId,
      marketName,
      outcome: '', // Will be parsed from market name
      odds,
      confidence,
      homeTeam,
      awayTeam
    });
  };

  return (
    <div className="page-container">
      {/* Breadcrumb */}
      <div className="breadcrumb">
        <Link to="/matches" className="breadcrumb-link">Maçlar</Link>
        <span className="breadcrumb-separator">›</span>
        <span className="breadcrumb-current">Maç İstihbaratı</span>
      </div>

      {/* Match Header */}
      <div className="match-intelligence-header">
        <div className="match-header-info">
          <div className="match-competition">
            {competition}
            {match.round && ` - ${match.round}. Hafta`}
            {isDevelopmentData && (
              <span className="dev-badge">Geliştirme Verisi</span>
            )}
          </div>
          <div className="match-datetime">
            {dateTime.full}
          </div>
        </div>
        <span className={`match-status match-status--${match.status}`}>
          {formatMatchStatus(match.status)}
        </span>
      </div>

      {/* Match Teams */}
      <div className="match-teams-section">
        <div className="team-display team-display--home">
          <div className="team-display__name">{homeTeam}</div>
          {match.home_score !== null && (
            <div className="team-display__score">{match.home_score}</div>
          )}
        </div>

        <div className="match-vs">
          {match.home_score === null && match.away_score === null ? (
            <span className="vs-text">VS</span>
          ) : (
            <span className="score-separator">-</span>
          )}
        </div>

        <div className="team-display team-display--away">
          {match.away_score !== null && (
            <div className="team-display__score">{match.away_score}</div>
          )}
          <div className="team-display__name">{awayTeam}</div>
        </div>
      </div>

      {/* Tabs Navigation - Only for scheduled matches */}
      {match.status === 'scheduled' && prediction && (
        <>
          <nav className="tabs-navigation" role="tablist">
            <button
              role="tab"
              aria-selected={activeTab === 'general'}
              aria-controls="general-panel"
              className={`tab-button ${activeTab === 'general' ? 'tab-button--active' : ''}`}
              onClick={() => setActiveTab('general')}
            >
              Genel
            </button>
            <button
              role="tab"
              aria-selected={activeTab === 'first-half'}
              aria-controls="first-half-panel"
              className={`tab-button ${activeTab === 'first-half' ? 'tab-button--active' : ''}`}
              onClick={() => setActiveTab('first-half')}
            >
              İlk Yarı
            </button>
            <button
              role="tab"
              aria-selected={activeTab === 'full-match'}
              aria-controls="full-match-panel"
              className={`tab-button ${activeTab === 'full-match' ? 'tab-button--active' : ''}`}
              onClick={() => setActiveTab('full-match')}
            >
              Maç
            </button>
          </nav>

          {/* Tab Panels */}
          <div className="tab-content">
            {/* General Tab */}
            {activeTab === 'general' && (
              <div
                role="tabpanel"
                id="general-panel"
                aria-labelledby="general-tab"
                className="tab-panel"
              >
                <GeneralAnalysis
                  prediction={prediction}
                  match={match}
                  homeTeam={homeTeam}
                  awayTeam={awayTeam}
                  isFavorite={isFavorite(match.id)}
                  onToggleFavorite={handleToggleFavorite}
                  inCombine={isInCombine(match.id)}
                  onToggleCombine={handleToggleFavorite}
                />
                
                {/* Statistics Comparison */}
                <StatisticsComparison
                  homeTeam={homeTeam}
                  awayTeam={awayTeam}
                  prediction={prediction}
                />
                
                {/* Form Display - No data yet, shows empty state */}
                <div className="form-displays">
                  <FormDisplay teamName={homeTeam} />
                  <FormDisplay teamName={awayTeam} />
                </div>
                
                {/* Head to Head - No data yet, shows empty state */}
                <HeadToHead
                  homeTeam={homeTeam}
                  awayTeam={awayTeam}
                />
              </div>
            )}

            {/* First Half Tab */}
            {activeTab === 'first-half' && (
              <div
                role="tabpanel"
                id="first-half-panel"
                aria-labelledby="first-half-tab"
                className="tab-panel"
              >
                <FirstHalfAnalysis
                  prediction={prediction}
                  match={match}
                  isInCombine={isInCombine}
                  onToggleCombine={handleToggleCombine}
                />
              </div>
            )}

            {/* Full Match Tab */}
            {activeTab === 'full-match' && (
              <div
                role="tabpanel"
                id="full-match-panel"
                aria-labelledby="full-match-tab"
                className="tab-panel"
              >
                <FullMatchAnalysis
                  prediction={prediction}
                  match={match}
                  isInCombine={isInCombine}
                  onToggleCombine={handleToggleCombine}
                />
              </div>
            )}
          </div>
        </>
      )}

      {/* No prediction available */}
      {match.status === 'scheduled' && !prediction && (
        <div className="info-state">
          <div className="info-icon">ℹ️</div>
          <p className="info-title">Tahmin mevcut değil</p>
          <p className="info-description">
            Bu maç için tahmin verisi henüz oluşturulmadı veya yeterli veri bulunmamaktadır.
          </p>
        </div>
      )}

      {/* Finished Match - Show Results Only */}
      {match.status === 'finished' && (
        <div className="match-result-section">
          <h2 className="section-title">Maç Sonucu</h2>
          <div className="final-score">
            <span className="final-score__label">Sonuç:</span>
            <span className="final-score__value">
              {match.home_score} - {match.away_score}
            </span>
          </div>
          {match.outcome && (
            <div className="match-outcome">
              <span className="match-outcome__label">Kazanan:</span>
              <span className="match-outcome__value">
                {match.outcome === 'home_win' ? homeTeam : 
                 match.outcome === 'away_win' ? awayTeam : 
                 'Beraberlik'}
              </span>
            </div>
          )}
        </div>
      )}

      {/* Combine Drawer */}
      <CombineDrawer
        items={combineItems}
        onRemove={removeFromCombine}
        onClear={clearCombine}
      />
    </div>
  );
}

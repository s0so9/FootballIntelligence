/**
 * TUTAR X Match Intelligence
 * Redesigned match detail page with new design system
 * Preserves all existing functionality
 */

import { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { getMatch } from '../api';
import type { MatchResponse } from '../api/types';
import { 
  formatTeamName, 
  formatCompetitionName, 
  formatMatchDateTime,
  formatMatchStatus 
} from '../utils/formatters';
import { useFavorites } from '../hooks/useFavorites';
import { useCombine } from '../hooks/useCombine';
import { useLiveMatch } from '../hooks/useLiveMatch';
import { useLazyPrediction } from '../hooks/useLazyPrediction';
import { Badge, Skeleton } from '../components/ui';
import GeneralAnalysis from '../components/match/GeneralAnalysis';
import FirstHalfAnalysis from '../components/match/FirstHalfAnalysis';
import FullMatchAnalysis from '../components/match/FullMatchAnalysis';
import StatisticsComparison from '../components/match/StatisticsComparison';
import FormDisplay from '../components/match/FormDisplay';
import HeadToHead from '../components/match/HeadToHead';
import CombineDrawer from '../components/combine/CombineDrawer';
import {
  LiveMatchHeader,
  LiveScoreboard,
  LiveStats,
  LiveShotIntelligence,
  LiveTimeline,
  LivePrediction,
  LivePickCard
} from '../components/live';
import './MatchDetailV2.css';

type TabType = 'general' | 'statistics' | 'predictions' | 'form-h2h';

export function MatchDetailV2() {
  const { id } = useParams<{ id: string }>();
  const [match, setMatch] = useState<MatchResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isDevelopmentData, setIsDevelopmentData] = useState(false);
  const [activeTab, setActiveTab] = useState<TabType>('general');
  
  // Favorites and combine state
  const { isFavorite, toggleFavorite } = useFavorites();
  const { combineItems, isInCombine, toggleCombine, removeFromCombine, clearCombine } = useCombine();
  
  // Lazy load prediction (for matches that can have predictions)
  // Include scheduled and postponed matches - exclude only finished and live matches
  const shouldLoadPrediction = match?.status === 'SCHEDULED' || match?.status === 'POSTPONED';
  
  const { prediction, loading: predictionLoading, error: predictionError } = useLazyPrediction(
    shouldLoadPrediction ? id : null
  );
  
  // Live match polling (only when match is live)
  const isMatchLive = match?.status === 'LIVE';
  const { 
    liveMatch, 
    loading: liveLoading, 
    error: liveError,
    lastUpdated,
    connectionStatus 
  } = useLiveMatch(id || '', { 
    enabled: isMatchLive 
  });

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

        // Fetch match details only - prediction is loaded lazily via useLazyPrediction
        const matchResponse = await getMatch(id);
        setMatch(matchResponse.match);
        setIsDevelopmentData(matchResponse.is_development_data);
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
      <div className="tx-match-detail">
        <div className="tx-match-detail__loading">
          <Skeleton width="100%" height="400px" />
          <div style={{ marginTop: 'var(--space-6)' }}>
            <Skeleton width="100%" height="60px" />
          </div>
          <div style={{ marginTop: 'var(--space-6)' }}>
            <Skeleton width="100%" height="300px" />
          </div>
        </div>
      </div>
    );
  }

  if (error || !match) {
    return (
      <div className="tx-match-detail">
        <div className="tx-match-detail__error">
          <div className="tx-match-detail__error-icon">⚠️</div>
          <h2 className="tx-match-detail__error-title">{error || 'Maç bulunamadı'}</h2>
          <p className="tx-match-detail__error-description">
            {error || 'Aradığınız maç bulunamadı veya geçersiz bir ID girdiniz.'}
          </p>
          {error && (
            <button
              className="tx-match-detail__retry"
              onClick={() => {
                setError(null);
                setLoading(true);
                getMatch(id!).then((r) => {
                  setMatch(r.match);
                  setIsDevelopmentData(r.is_development_data);
                }).catch((err) => {
                  setError(err instanceof Error ? err.message : 'Maç verileri yüklenirken bir hata oluştu');
                }).finally(() => setLoading(false));
              }}
            >
              Tekrar Dene
            </button>
          )}
          <Link to="/matches" className="tx-match-detail__back-link">← Maçlara Dön</Link>
        </div>
      </div>
    );
  }

  const dateTime = formatMatchDateTime(match.scheduled_at);
  
  // Use team names from API response, or fallback to formatTeamName for IDs
  const homeTeam = match.home_team ? match.home_team.name : formatTeamName(match.home_team_id);
  const awayTeam = match.away_team ? match.away_team.name : formatTeamName(match.away_team_id);
  
  const competition = formatCompetitionName(match.competition_id);

  // Handle favorite toggle
  const handleToggleFavorite = () => {
    if (match) {
      toggleFavorite(match.id);
    }
  };

  // Handle combine toggle
  const handleToggleCombine = (matchId: string, marketName: string, confidence: number, marketOdds: number | null) => {
    if (!match) return;
    
    toggleCombine({
      matchId,
      marketName,
      outcome: '', // Will be parsed from market name
      marketOdds,
      confidence,
      homeTeam,
      awayTeam
    });
  };

  // Get status badge variant
  const getStatusVariant = (status: string): 'success' | 'warning' | 'danger' | 'info' | 'live' | 'neutral' => {
    switch (status) {
      case 'LIVE':
        return 'live';
      case 'FINISHED':
        return 'success';
      case 'SCHEDULED':
        return 'info';
      case 'POSTPONED':
        return 'warning';
      case 'CANCELLED':
        return 'danger';
      default:
        return 'neutral';
    }
  };

  return (
    <div className="tx-match-detail">
      {/* Breadcrumb */}
      <div className="tx-match-detail__breadcrumb">
        <Link to="/matches" className="tx-match-detail__breadcrumb-link">Maçlar</Link>
        <span className="tx-match-detail__breadcrumb-separator">›</span>
        <span className="tx-match-detail__breadcrumb-current">Maç İstihbaratı</span>
      </div>

      {/* Hero Section */}
      <div className="tx-match-detail__hero">
        <div className="tx-match-detail__hero-top">
          <div className="tx-match-detail__badge">TUTAR X MATCH INTELLIGENCE</div>
          <Badge variant={getStatusVariant(match.status)}>
            {formatMatchStatus(match.status)}
          </Badge>
        </div>
        
        <div className="tx-match-detail__competition">
          {competition}
          {match.round && ` - ${match.round}. Hafta`}
          {isDevelopmentData && (
            <span className="tx-match-detail__dev-badge">Geliştirme Verisi</span>
          )}
        </div>
        
        <div className="tx-match-detail__datetime">
          {dateTime.full}
        </div>
      </div>

      {/* Scoreboard */}
      <div className="tx-match-detail__scoreboard">
        <div className="tx-match-detail__team tx-match-detail__team--home">
          {match.home_team?.logo_url && (
            <img 
              src={match.home_team.logo_url} 
              alt={homeTeam}
              className="tx-match-detail__team-logo"
            />
          )}
          {!match.home_team?.logo_url && (
            <div className="tx-match-detail__team-logo-placeholder">
              {homeTeam.substring(0, 3).toUpperCase()}
            </div>
          )}
          <div className="tx-match-detail__team-info">
            <div className="tx-match-detail__team-name">{homeTeam}</div>
            {match.home_score !== null && (
              <div className="tx-match-detail__team-score">{match.home_score}</div>
            )}
          </div>
        </div>

        <div className="tx-match-detail__vs">
          {match.home_score === null && match.away_score === null ? (
            <span className="tx-match-detail__vs-text">VS</span>
          ) : (
            <span className="tx-match-detail__score-separator">-</span>
          )}
        </div>

        <div className="tx-match-detail__team tx-match-detail__team--away">
          <div className="tx-match-detail__team-info">
            <div className="tx-match-detail__team-name">{awayTeam}</div>
            {match.away_score !== null && (
              <div className="tx-match-detail__team-score">{match.away_score}</div>
            )}
          </div>
          {match.away_team?.logo_url && (
            <img 
              src={match.away_team.logo_url} 
              alt={awayTeam}
              className="tx-match-detail__team-logo"
            />
          )}
          {!match.away_team?.logo_url && (
            <div className="tx-match-detail__team-logo-placeholder">
              {awayTeam.substring(0, 3).toUpperCase()}
            </div>
          )}
        </div>

        {/* Favorite Button */}
        <button
          className={`tx-match-detail__favorite ${isFavorite(match.id) ? 'tx-match-detail__favorite--active' : ''}`}
          onClick={handleToggleFavorite}
          aria-label={isFavorite(match.id) ? 'Favorilerden çıkar' : 'Favorilere ekle'}
        >
          ★
        </button>
      </div>

      {/* Tabs Navigation - For matches that can have predictions */}
      {shouldLoadPrediction && (
        <>
          <nav className="tx-match-detail__tabs" role="tablist">
            <button
              role="tab"
              aria-selected={activeTab === 'general'}
              aria-controls="general-panel"
              className={`tx-match-detail__tab ${activeTab === 'general' ? 'tx-match-detail__tab--active' : ''}`}
              onClick={() => setActiveTab('general')}
            >
              Genel Bakış
            </button>
            <button
              role="tab"
              aria-selected={activeTab === 'statistics'}
              aria-controls="statistics-panel"
              className={`tx-match-detail__tab ${activeTab === 'statistics' ? 'tx-match-detail__tab--active' : ''}`}
              onClick={() => setActiveTab('statistics')}
            >
              İstatistikler
            </button>
            <button
              role="tab"
              aria-selected={activeTab === 'predictions'}
              aria-controls="predictions-panel"
              className={`tx-match-detail__tab ${activeTab === 'predictions' ? 'tx-match-detail__tab--active' : ''}`}
              onClick={() => setActiveTab('predictions')}
            >
              Tahminler
            </button>
            <button
              role="tab"
              aria-selected={activeTab === 'form-h2h'}
              aria-controls="form-h2h-panel"
              className={`tx-match-detail__tab ${activeTab === 'form-h2h' ? 'tx-match-detail__tab--active' : ''}`}
              onClick={() => setActiveTab('form-h2h')}
            >
              Form & H2H
            </button>
          </nav>

          {/* Tab Content */}
          <div className="tx-match-detail__content">
            {/* Loading State */}
            {predictionLoading && (
              <div className="tx-match-detail__info">
                <Skeleton width="100%" height="200px" />
                <div style={{ marginTop: 'var(--space-4)' }}>
                  <Skeleton width="100%" height="150px" />
                </div>
              </div>
            )}

            {/* Error State */}
            {predictionError && !predictionLoading && (
              <div className="tx-match-detail__prediction-error">
                <div className="tx-match-detail__error-icon">⚠️</div>
                <h3 className="tx-match-detail__error-title">Tahmin oluşturulamadı</h3>
                <p className="tx-match-detail__error-description">
                  {predictionError.message.includes('Insufficient data')
                    ? 'Bu maç için yeterli geçmiş veri bulunmamaktadır.'
                    : `Hata: ${predictionError.message}`}
                </p>
                <button
                  className="tx-match-detail__retry"
                  onClick={() => window.location.reload()}
                >
                  Tekrar Dene
                </button>
              </div>
            )}

            {/* General Tab */}
            {activeTab === 'general' && prediction && !predictionLoading && (
              <div
                role="tabpanel"
                id="general-panel"
                aria-labelledby="general-tab"
                className="tx-match-detail__panel"
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
              </div>
            )}

            {/* Statistics Tab */}
            {activeTab === 'statistics' && prediction && !predictionLoading && (
              <div
                role="tabpanel"
                id="statistics-panel"
                aria-labelledby="statistics-tab"
                className="tx-match-detail__panel"
              >
                <StatisticsComparison
                  homeTeam={homeTeam}
                  awayTeam={awayTeam}
                  prediction={prediction}
                />
              </div>
            )}

            {/* Predictions Tab */}
            {activeTab === 'predictions' && prediction && !predictionLoading && (
              <div
                role="tabpanel"
                id="predictions-panel"
                aria-labelledby="predictions-tab"
                className="tx-match-detail__panel"
              >
                <div className="tx-match-detail__predictions-grid">
                  <FirstHalfAnalysis
                    prediction={prediction}
                    match={match}
                    isInCombine={isInCombine}
                    onToggleCombine={handleToggleCombine}
                  />
                  <FullMatchAnalysis
                    prediction={prediction}
                    match={match}
                    isInCombine={isInCombine}
                    onToggleCombine={handleToggleCombine}
                  />
                </div>
              </div>
            )}

            {/* Form & H2H Tab */}
            {activeTab === 'form-h2h' && prediction && !predictionLoading && (
              <div
                role="tabpanel"
                id="form-h2h-panel"
                aria-labelledby="form-h2h-tab"
                className="tx-match-detail__panel"
              >
                <div className="tx-match-detail__form-grid">
                  <FormDisplay teamName={homeTeam} />
                  <FormDisplay teamName={awayTeam} />
                </div>
                <HeadToHead
                  homeTeam={homeTeam}
                  awayTeam={awayTeam}
                />
              </div>
            )}
          </div>
        </>
      )}

      {/* Live Match - Show Live Intelligence UI */}
      {match.status === 'LIVE' && (
        <div className="tx-match-detail__live">
          <LiveMatchHeader
            competition={competition}
            venue={liveMatch?.venue}
            connectionStatus={connectionStatus}
            lastUpdated={lastUpdated || undefined}
            dataQuality={undefined}
          />

          <LiveScoreboard
            homeTeam={liveMatch?.homeTeam}
            awayTeam={liveMatch?.awayTeam}
            homeScore={liveMatch?.homeScore}
            awayScore={liveMatch?.awayScore}
            minute={liveMatch?.minute}
            addedTime={liveMatch?.addedTime}
            period={liveMatch?.period}
            isLoading={liveLoading}
          />

          <LivePickCard
            homeTeam={homeTeam}
            awayTeam={awayTeam}
            pick={null}
            isLoading={liveLoading}
          />

          <LiveStats
            homeTeam={homeTeam}
            awayTeam={awayTeam}
            homeStats={liveMatch?.homeStats}
            awayStats={liveMatch?.awayStats}
            isLoading={liveLoading}
          />

          <LivePrediction
            homeTeam={homeTeam}
            awayTeam={awayTeam}
            prediction={null}
            isLoading={liveLoading}
          />

          <LiveShotIntelligence
            homeTeam={homeTeam}
            awayTeam={awayTeam}
            shots={[]}
            hasCoordinates={false}
            isLoading={liveLoading}
          />

          <LiveTimeline
            homeTeam={homeTeam}
            awayTeam={awayTeam}
            events={[]}
            isLoading={liveLoading}
          />

          {liveError && (
            <div className="tx-match-detail__prediction-error">
              <div className="tx-match-detail__error-icon">⚠️</div>
              <h3 className="tx-match-detail__error-title">Canlı veri yüklenemedi</h3>
              <p className="tx-match-detail__error-description">{liveError}</p>
            </div>
          )}
        </div>
      )}

      {/* Finished Match - Show Results Only */}
      {match.status === 'FINISHED' && (
        <div className="tx-match-detail__result">
          <h2 className="tx-match-detail__result-title">Maç Sonucu</h2>
          <div className="tx-match-detail__final-score">
            <span className="tx-match-detail__final-score-label">Sonuç:</span>
            <span className="tx-match-detail__final-score-value">
              {match.home_score} - {match.away_score}
            </span>
          </div>
          {match.outcome && (
            <div className="tx-match-detail__outcome">
              <span className="tx-match-detail__outcome-label">Kazanan:</span>
              <span className="tx-match-detail__outcome-value">
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
